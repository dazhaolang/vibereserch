"""
渐进式批次策略 - 实现1-5篇→6-10篇的动态批次调整
解决问题：替代固定4篇/轮的策略，实现更灵活的渐进式文献处理
"""

import asyncio
import time
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from loguru import logger
from sqlalchemy.orm import Session

from app.models.literature import LiteratureSegment, Literature
from app.services.literature_reliability_service import LiteratureReliabilityService


class BatchPhase(Enum):
    """批次阶段"""
    EXPLORATION = "exploration"      # 探索阶段：1-5篇
    CONSOLIDATION = "consolidation"  # 巩固阶段：6-10篇
    REFINEMENT = "refinement"       # 精炼阶段：11-15篇
    OPTIMIZATION = "optimization"   # 优化阶段：16+篇


@dataclass
class BatchConfig:
    """批次配置"""
    min_size: int
    max_size: int
    quality_threshold: float
    information_gain_threshold: float
    phase_name: str

    @property
    def adaptive_size_range(self) -> Tuple[int, int]:
        """自适应大小范围"""
        return (self.min_size, self.max_size)


@dataclass
class BatchResult:
    """批次处理结果"""
    batch_id: str
    phase: BatchPhase
    literature_count: int
    information_gain: float
    quality_score: float
    processing_time: float
    success: bool
    next_batch_suggestion: Optional[Dict[str, Any]] = None


class ProgressiveBatchStrategy:
    """渐进式批次策略"""

    def __init__(self, reliability_service: LiteratureReliabilityService):
        self.reliability_service = reliability_service

        # 阶段配置
        self.phase_configs = {
            BatchPhase.EXPLORATION: BatchConfig(
                min_size=1,
                max_size=5,
                quality_threshold=6.0,
                information_gain_threshold=0.15,
                phase_name="探索阶段"
            ),
            BatchPhase.CONSOLIDATION: BatchConfig(
                min_size=3,
                max_size=10,
                quality_threshold=7.0,
                information_gain_threshold=0.12,
                phase_name="巩固阶段"
            ),
            BatchPhase.REFINEMENT: BatchConfig(
                min_size=5,
                max_size=15,
                quality_threshold=7.5,
                information_gain_threshold=0.10,
                phase_name="精炼阶段"
            ),
            BatchPhase.OPTIMIZATION: BatchConfig(
                min_size=8,
                max_size=20,
                quality_threshold=8.0,
                information_gain_threshold=0.08,
                phase_name="优化阶段"
            )
        }

        # 批次历史和状态
        self.batch_history: List[BatchResult] = []
        self.current_phase = BatchPhase.EXPLORATION
        self.consecutive_low_gain_count = 0
        self.total_processed = 0

        # 动态调整参数
        self.adaptation_enabled = True
        self.quality_trend_window = 3
        self.performance_metrics = {
            "avg_processing_time": 0.0,
            "avg_information_gain": 0.0,
            "avg_quality_score": 0.0,
            "phase_transition_count": 0
        }

    def determine_next_batch(
        self,
        available_segments: List[LiteratureSegment],
        current_experience: Optional[str] = None,
        project_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        确定下一个批次的配置和文献选择

        Args:
            available_segments: 可用的文献段落
            current_experience: 当前经验内容
            project_context: 项目上下文

        Returns:
            批次配置和选择的文献
        """
        try:
            logger.info(f"确定下一个批次，当前阶段: {self.current_phase.value}")

            # 1. 评估当前状态并调整阶段
            self._evaluate_and_adjust_phase()

            # 2. 获取当前阶段配置
            config = self.phase_configs[self.current_phase]

            # 3. 根据历史表现动态调整批次大小
            adaptive_size = self._calculate_adaptive_batch_size(config, available_segments)

            # 4. 选择最适合的文献段落
            selected_segments = self._select_optimal_segments(
                available_segments, adaptive_size, current_experience, project_context
            )

            # 5. 生成批次策略
            batch_strategy = {
                "batch_id": f"batch_{int(time.time())}_{len(self.batch_history)}",
                "phase": self.current_phase,
                "config": config,
                "selected_segments": selected_segments,
                "adaptive_size": adaptive_size,
                "strategy_reasoning": self._generate_strategy_reasoning(config, adaptive_size),
                "expected_outcomes": self._predict_batch_outcomes(selected_segments, config),
                "processing_hints": self._generate_processing_hints(config),
                "quality_controls": self._define_quality_controls(config)
            }

            logger.info(f"批次策略生成完成: {config.phase_name}, 选择文献 {len(selected_segments)} 篇")
            return batch_strategy

        except Exception as e:
            logger.error(f"批次策略确定失败: {e}")
            return self._fallback_batch_strategy(available_segments)

    def _evaluate_and_adjust_phase(self):
        """评估并调整当前阶段"""
        if not self.batch_history:
            return

        recent_results = self.batch_history[-self.quality_trend_window:]

        # 计算近期表现指标
        avg_gain = sum(r.information_gain for r in recent_results) / len(recent_results)
        avg_quality = sum(r.quality_score for r in recent_results) / len(recent_results)

        current_config = self.phase_configs[self.current_phase]

        # 阶段晋升条件
        if self._should_advance_phase(avg_gain, avg_quality, current_config):
            self._advance_to_next_phase()
        # 阶段降级条件（质量下降）
        elif self._should_regress_phase(avg_gain, avg_quality):
            self._regress_to_previous_phase()

    def _should_advance_phase(self, avg_gain: float, avg_quality: float, config: BatchConfig) -> bool:
        """判断是否应该进入下一阶段"""
        # 信息增益稳定且质量达标
        if avg_gain >= config.information_gain_threshold and avg_quality >= config.quality_threshold:
            # 连续成功的批次数量足够
            successful_batches = len([r for r in self.batch_history[-5:] if r.success])
            if successful_batches >= 2:
                return True

        return False

    def _should_regress_phase(self, avg_gain: float, avg_quality: float) -> bool:
        """判断是否应该回退到前一阶段"""
        # 连续低质量或低增益
        if self.consecutive_low_gain_count >= 3:
            return True

        # 质量急剧下降
        if len(self.batch_history) >= 2:
            recent_quality = self.batch_history[-1].quality_score
            previous_quality = self.batch_history[-2].quality_score
            if recent_quality < previous_quality - 1.0:  # 质量下降超过1分
                return True

        return False

    def _advance_to_next_phase(self):
        """进入下一阶段"""
        phase_order = [BatchPhase.EXPLORATION, BatchPhase.CONSOLIDATION,
                      BatchPhase.REFINEMENT, BatchPhase.OPTIMIZATION]

        current_index = phase_order.index(self.current_phase)
        if current_index < len(phase_order) - 1:
            self.current_phase = phase_order[current_index + 1]
            self.performance_metrics["phase_transition_count"] += 1
            logger.info(f"阶段晋升到: {self.current_phase.value}")
        else:
            logger.info("已处于最高阶段，保持不变")

    def _regress_to_previous_phase(self):
        """回退到前一阶段"""
        phase_order = [BatchPhase.EXPLORATION, BatchPhase.CONSOLIDATION,
                      BatchPhase.REFINEMENT, BatchPhase.OPTIMIZATION]

        current_index = phase_order.index(self.current_phase)
        if current_index > 0:
            self.current_phase = phase_order[current_index - 1]
            logger.warning(f"阶段回退到: {self.current_phase.value}")
        else:
            logger.warning("已处于最低阶段，保持不变")

    def _calculate_adaptive_batch_size(
        self,
        config: BatchConfig,
        available_segments: List[LiteratureSegment]
    ) -> int:
        """计算自适应批次大小"""
        if not self.adaptation_enabled:
            return config.min_size

        base_size = config.min_size

        # 根据历史表现调整
        if self.batch_history:
            recent_results = self.batch_history[-3:]
            avg_processing_time = sum(r.processing_time for r in recent_results) / len(recent_results)

            # 如果处理速度快，可以增加批次大小
            if avg_processing_time < 30:  # 30秒以内
                size_boost = min(3, (config.max_size - base_size) // 2)
                base_size += size_boost

            # 如果信息增益高，适度增加批次
            avg_gain = sum(r.information_gain for r in recent_results) / len(recent_results)
            if avg_gain > config.information_gain_threshold * 1.2:
                base_size += 1

        # 根据可用文献数量调整
        available_count = len(available_segments)
        if available_count < config.max_size:
            base_size = min(base_size, available_count)

        # 确保在配置范围内
        return max(config.min_size, min(base_size, config.max_size))

    def _select_optimal_segments(
        self,
        available_segments: List[LiteratureSegment],
        batch_size: int,
        current_experience: Optional[str] = None,
        project_context: Optional[Dict] = None
    ) -> List[LiteratureSegment]:
        """选择最优的文献段落"""
        try:
            if len(available_segments) <= batch_size:
                return available_segments

            # 1. 按可靠性排序
            literature_list = list(set(seg.literature for seg in available_segments))
            sorted_literature = self.reliability_service.sort_literature_by_reliability(
                literature_list, prioritize_high_reliability=True
            )

            # 2. 重新组织段落顺序（按可靠性）
            sorted_segments = []
            for literature in sorted_literature:
                lit_segments = [s for s in available_segments if s.literature_id == literature.id]
                sorted_segments.extend(lit_segments)

            # 3. 应用阶段特定的选择策略
            return self._apply_phase_selection_strategy(
                sorted_segments, batch_size, current_experience, project_context
            )

        except Exception as e:
            logger.error(f"文献选择失败: {e}")
            return available_segments[:batch_size]

    def _apply_phase_selection_strategy(
        self,
        sorted_segments: List[LiteratureSegment],
        batch_size: int,
        current_experience: Optional[str] = None,
        project_context: Optional[Dict] = None
    ) -> List[LiteratureSegment]:
        """应用阶段特定的选择策略"""

        if self.current_phase == BatchPhase.EXPLORATION:
            # 探索阶段：优先选择高质量和多样性
            return self._exploration_selection(sorted_segments, batch_size)

        elif self.current_phase == BatchPhase.CONSOLIDATION:
            # 巩固阶段：平衡质量和覆盖面
            return self._consolidation_selection(sorted_segments, batch_size, current_experience)

        elif self.current_phase == BatchPhase.REFINEMENT:
            # 精炼阶段：重点关注增量信息
            return self._refinement_selection(sorted_segments, batch_size, current_experience)

        elif self.current_phase == BatchPhase.OPTIMIZATION:
            # 优化阶段：选择最能提升经验的文献
            return self._optimization_selection(sorted_segments, batch_size, current_experience)

        return sorted_segments[:batch_size]

    def _exploration_selection(
        self,
        segments: List[LiteratureSegment],
        batch_size: int
    ) -> List[LiteratureSegment]:
        """探索阶段选择策略：多样性优先"""
        selected = []

        # 按文献类型和质量分组
        by_type = {}
        for segment in segments:
            seg_type = segment.segment_type or "general"
            if seg_type not in by_type:
                by_type[seg_type] = []
            by_type[seg_type].append(segment)

        # 每种类型选择最好的1-2个
        remaining_slots = batch_size
        for seg_type, type_segments in by_type.items():
            if remaining_slots <= 0:
                break

            # 按可靠性排序并选择前几个
            sorted_by_reliability = sorted(
                type_segments,
                key=lambda x: x.literature.reliability_score or 0.5,
                reverse=True
            )

            take_count = min(2, remaining_slots, len(sorted_by_reliability))
            selected.extend(sorted_by_reliability[:take_count])
            remaining_slots -= take_count

        # 如果还有剩余位置，按可靠性补充
        if remaining_slots > 0:
            remaining = [s for s in segments if s not in selected]
            remaining_sorted = sorted(
                remaining,
                key=lambda x: x.literature.reliability_score or 0.5,
                reverse=True
            )
            selected.extend(remaining_sorted[:remaining_slots])

        return selected

    def _consolidation_selection(
        self,
        segments: List[LiteratureSegment],
        batch_size: int,
        current_experience: Optional[str] = None
    ) -> List[LiteratureSegment]:
        """巩固阶段选择策略：质量和覆盖面平衡"""
        # 优先选择高可靠性文献，同时保证覆盖面
        high_reliability = [s for s in segments if (s.literature.reliability_score or 0.5) >= 0.7]
        medium_reliability = [s for s in segments if 0.5 <= (s.literature.reliability_score or 0.5) < 0.7]

        selected = []

        # 70%来自高可靠性文献
        high_count = min(len(high_reliability), int(batch_size * 0.7))
        selected.extend(high_reliability[:high_count])

        # 30%来自中等可靠性文献（保证多样性）
        remaining_count = batch_size - len(selected)
        if remaining_count > 0 and medium_reliability:
            selected.extend(medium_reliability[:remaining_count])

        # 如果还不够，用剩余的补充
        if len(selected) < batch_size:
            remaining = [s for s in segments if s not in selected]
            selected.extend(remaining[:batch_size - len(selected)])

        return selected

    def _refinement_selection(
        self,
        segments: List[LiteratureSegment],
        batch_size: int,
        current_experience: Optional[str] = None
    ) -> List[LiteratureSegment]:
        """精炼阶段选择策略：重点关注增量信息"""
        if not current_experience:
            return segments[:batch_size]

        # TODO: 实现与现有经验的相关性分析
        # 这里需要计算每个段落与现有经验的互补性
        # 简化实现：优先选择不同类型的高质量段落

        selected = []
        used_types = set()

        for segment in segments:
            if len(selected) >= batch_size:
                break

            seg_type = segment.segment_type or "general"
            reliability = segment.literature.reliability_score or 0.5

            # 偏好未使用过的类型且高可靠性的文献
            if seg_type not in used_types and reliability >= 0.6:
                selected.append(segment)
                used_types.add(seg_type)

        # 补充剩余位置
        for segment in segments:
            if len(selected) >= batch_size:
                break
            if segment not in selected:
                selected.append(segment)

        return selected

    def _optimization_selection(
        self,
        segments: List[LiteratureSegment],
        batch_size: int,
        current_experience: Optional[str] = None
    ) -> List[LiteratureSegment]:
        """优化阶段选择策略：选择最能提升经验的文献"""
        # 严格选择最高质量的文献
        high_impact_segments = [
            s for s in segments
            if (s.literature.reliability_score or 0.5) >= 0.8 and
               (s.literature.impact_factor or 0.0) >= 2.0
        ]

        if len(high_impact_segments) >= batch_size:
            return high_impact_segments[:batch_size]
        else:
            # 补充高可靠性文献
            high_reliability = [
                s for s in segments
                if (s.literature.reliability_score or 0.5) >= 0.7 and
                s not in high_impact_segments
            ]
            selected = high_impact_segments + high_reliability
            return selected[:batch_size]

    def _generate_strategy_reasoning(self, config: BatchConfig, batch_size: int) -> str:
        """生成策略推理说明"""
        return f"""
批次策略推理：
- 当前阶段：{config.phase_name}
- 批次大小：{batch_size} 篇文献
- 质量阈值：{config.quality_threshold}
- 信息增益阈值：{config.information_gain_threshold}
- 历史批次数：{len(self.batch_history)}
- 阶段转换次数：{self.performance_metrics["phase_transition_count"]}
"""

    def _predict_batch_outcomes(
        self,
        segments: List[LiteratureSegment],
        config: BatchConfig
    ) -> Dict[str, Any]:
        """预测批次处理结果"""
        avg_reliability = sum(s.literature.reliability_score or 0.5 for s in segments) / len(segments)
        avg_impact_factor = sum(s.literature.impact_factor or 0.0 for s in segments) / len(segments)

        return {
            "expected_quality_score": min(10.0, 5.0 + avg_reliability * 4.0),
            "expected_information_gain": min(0.3, 0.05 + avg_reliability * 0.15),
            "expected_processing_time": len(segments) * 15 + 30,  # 估算处理时间
            "confidence": avg_reliability,
            "literature_diversity_score": len(set(s.segment_type for s in segments))
        }

    def _generate_processing_hints(self, config: BatchConfig) -> List[str]:
        """生成处理提示"""
        hints = [
            f"重点关注质量评分达到 {config.quality_threshold} 分以上",
            f"确保信息增益不低于 {config.information_gain_threshold}",
            f"这是{config.phase_name}，适合采用相应的处理策略"
        ]

        if self.current_phase == BatchPhase.EXPLORATION:
            hints.append("探索阶段：注重发现新的方法和观点")
        elif self.current_phase == BatchPhase.CONSOLIDATION:
            hints.append("巩固阶段：整合已有信息，形成系统化认识")
        elif self.current_phase == BatchPhase.REFINEMENT:
            hints.append("精炼阶段：提升经验的精确度和实用性")
        elif self.current_phase == BatchPhase.OPTIMIZATION:
            hints.append("优化阶段：追求最高质量的经验总结")

        return hints

    def _define_quality_controls(self, config: BatchConfig) -> Dict[str, Any]:
        """定义质量控制措施"""
        return {
            "min_quality_score": config.quality_threshold,
            "min_information_gain": config.information_gain_threshold,
            "max_processing_time": 300,  # 5分钟最大处理时间
            "require_structured_data": True,
            "validate_semantic_coherence": True,
            "enable_deviation_detection": self.current_phase != BatchPhase.EXPLORATION  # 探索阶段不启用
        }

    def record_batch_result(self, result: BatchResult):
        """记录批次处理结果"""
        self.batch_history.append(result)
        self.total_processed += result.literature_count

        # 更新性能指标
        self._update_performance_metrics(result)

        # 更新连续低增益计数
        if result.information_gain < self.phase_configs[self.current_phase].information_gain_threshold:
            self.consecutive_low_gain_count += 1
        else:
            self.consecutive_low_gain_count = 0

        logger.info(f"批次结果记录完成: {result.batch_id}, 阶段: {result.phase.value}")

    def _update_performance_metrics(self, result: BatchResult):
        """更新性能指标"""
        total_batches = len(self.batch_history)

        # 使用滑动平均更新指标
        alpha = 0.3  # 平滑系数
        self.performance_metrics["avg_processing_time"] = (
            alpha * result.processing_time +
            (1 - alpha) * self.performance_metrics["avg_processing_time"]
        )

        self.performance_metrics["avg_information_gain"] = (
            alpha * result.information_gain +
            (1 - alpha) * self.performance_metrics["avg_information_gain"]
        )

        self.performance_metrics["avg_quality_score"] = (
            alpha * result.quality_score +
            (1 - alpha) * self.performance_metrics["avg_quality_score"]
        )

    def get_strategy_summary(self) -> Dict[str, Any]:
        """获取策略执行总结"""
        return {
            "current_phase": self.current_phase.value,
            "total_batches": len(self.batch_history),
            "total_processed": self.total_processed,
            "performance_metrics": self.performance_metrics.copy(),
            "consecutive_low_gain_count": self.consecutive_low_gain_count,
            "phase_distribution": {
                phase.value: len([r for r in self.batch_history if r.phase == phase])
                for phase in BatchPhase
            },
            "success_rate": len([r for r in self.batch_history if r.success]) / max(1, len(self.batch_history)),
            "avg_batch_size": sum(r.literature_count for r in self.batch_history) / max(1, len(self.batch_history)),
            "adaptation_enabled": self.adaptation_enabled
        }

    def _fallback_batch_strategy(self, available_segments: List[LiteratureSegment]) -> Dict[str, Any]:
        """降级批次策略"""
        logger.warning("使用降级批次策略")

        fallback_size = min(3, len(available_segments))
        selected = available_segments[:fallback_size]

        return {
            "batch_id": f"fallback_{int(time.time())}",
            "phase": self.current_phase,
            "config": self.phase_configs[self.current_phase],
            "selected_segments": selected,
            "adaptive_size": fallback_size,
            "strategy_reasoning": "降级策略：使用简单固定批次",
            "expected_outcomes": {"expected_quality_score": 6.0, "expected_information_gain": 0.1},
            "processing_hints": ["使用基础处理策略"],
            "quality_controls": {"min_quality_score": 5.0}
        }

    def reset_strategy(self):
        """重置策略状态"""
        self.batch_history.clear()
        self.current_phase = BatchPhase.EXPLORATION
        self.consecutive_low_gain_count = 0
        self.total_processed = 0
        self.performance_metrics = {
            "avg_processing_time": 0.0,
            "avg_information_gain": 0.0,
            "avg_quality_score": 0.0,
            "phase_transition_count": 0
        }
        logger.info("批次策略已重置")


# 工厂函数
def create_progressive_batch_strategy(
    reliability_service: LiteratureReliabilityService
) -> ProgressiveBatchStrategy:
    """创建渐进式批次策略实例"""
    return ProgressiveBatchStrategy(reliability_service)