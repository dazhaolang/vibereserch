"""
经验增强引擎 - 商业化完整版本
实现主经验库、增量更新、动态停止机制
"""

import asyncio
import json
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.core.config import settings
from app.services.ai_service import AIService
from app.services.literature_reliability_service import LiteratureReliabilityService
from app.services.progressive_batch_strategy import create_progressive_batch_strategy, BatchResult, BatchPhase
from app.models.experience import ExperienceBook, MainExperience
from app.models.literature import LiteratureSegment, Literature
from app.models.task import Task, TaskProgress
from app.models.project import Project
from app.models.user import User, MembershipType

class EnhancedExperienceEngine:
    """增强版经验引擎 - 商业化版本"""
    
    def __init__(self, db: Session):
        self.db = db
        self.ai_service = AIService()
        self.reliability_service = LiteratureReliabilityService(db)

        # 初始化渐进式批次策略
        self.batch_strategy = create_progressive_batch_strategy(self.reliability_service)

        # 动态停止机制配置
        self.stop_conditions = {
            "min_information_gain": 0.05,  # 最小信息增益阈值
            "consecutive_low_gain_rounds": 3,  # 连续低增益轮次
            "max_iterations": 50,  # 最大迭代轮次
            "min_quality_threshold": 7.0  # 最小质量阈值
        }
        
        # 主经验类型配置
        self.main_experience_types = {
            "材料制备经验": {
                "description": "涵盖各种材料制备方法的通用经验",
                "keywords": ["制备", "合成", "工艺", "参数", "条件"],
                "priority": 1
            },
            "表征分析经验": {
                "description": "材料表征和分析测试的通用经验",
                "keywords": ["表征", "测试", "分析", "检测", "光谱"],
                "priority": 2
            },
            "性能优化经验": {
                "description": "材料性能提升和优化的通用经验", 
                "keywords": ["性能", "优化", "改进", "提升", "增强"],
                "priority": 3
            },
            "应用开发经验": {
                "description": "材料实际应用和产业化的通用经验",
                "keywords": ["应用", "器件", "产业", "工程", "实用"],
                "priority": 4
            }
        }
        
    async def run_experience_enhancement(
        self, 
        project_id: int,
        research_question: str,
        literature_segments: List[LiteratureSegment],
        task_id: Optional[int] = None
    ) -> Dict:
        """
        运行经验增强流程 - 集成可靠性排序和偏离检测
        
        Args:
            project_id: 项目ID
            research_question: 研究问题
            literature_segments: 文献段落列表
            task_id: 任务ID（用于进度更新）
            
        Returns:
            经验增强结果
        """
        try:
            logger.info(f"开始经验增强流程，项目ID: {project_id}")
            
            # 1. 获取文献并按可靠性排序
            if task_id:
                await self._update_task_progress(
                    task_id, "评估文献可靠性", 5.0, 
                    {"total_segments": len(literature_segments)}
                )
            
            # 获取文献对象并评估可靠性
            literature_list = []
            for segment in literature_segments:
                if segment.literature not in literature_list:
                    literature_list.append(segment.literature)
            
            # 批量评估文献可靠性
            await self.reliability_service.batch_evaluate_literature_reliability(literature_list)
            
            # 按可靠性排序文献
            sorted_literature = self.reliability_service.sort_literature_by_reliability(
                literature_list, prioritize_high_reliability=True
            )
            
            # 重新组织段落顺序
            sorted_segments = []
            for literature in sorted_literature:
                lit_segments = [s for s in literature_segments if s.literature_id == literature.id]
                sorted_segments.extend(lit_segments)
            
            # 2. 初始化变量
            current_experience = None
            iteration_round = 1
            consecutive_low_gain_rounds = 0
            total_literature_count = len(sorted_segments)
            processed_segments = 0
            skipped_segments = []

            # 重置批次策略状态（每个项目独立）
            self.batch_strategy.reset_strategy()

            if task_id:
                await self._update_task_progress(
                    task_id, "初始化渐进式批次策略", 10.0,
                    {
                        "sorted_literature": len(sorted_literature),
                        "strategy_phase": self.batch_strategy.current_phase.value,
                        "total_segments": total_literature_count
                    }
                )
            
            # 3. 使用渐进式批次策略处理文献
            remaining_segments = sorted_segments.copy()

            while remaining_segments and iteration_round <= self.stop_conditions["max_iterations"]:
                # 获取下一批次策略
                batch_strategy = self.batch_strategy.determine_next_batch(
                    available_segments=remaining_segments,
                    current_experience=current_experience,
                    project_context={
                        "project_id": project_id,
                        "research_question": research_question,
                        "iteration_round": iteration_round
                    }
                )

                current_batch = batch_strategy["selected_segments"]
                batch_size = len(current_batch)

                logger.info(
                    f"第{iteration_round}轮 - {batch_strategy['config'].phase_name}: "
                    f"选择 {batch_size} 篇文献 (策略: {batch_strategy['strategy_reasoning'][:100]}...)"
                )
                
                # 4. 对当前批次进行偏离检测（如果已有经验）
                valid_batch = []
                if current_experience and iteration_round > 1:
                    for segment in current_batch:
                        # 计算偏离度
                        deviation_result = await self.reliability_service.calculate_experience_deviation(
                            segment.content,
                            current_experience,
                            research_question
                        )
                        
                        # 判断是否跳过
                        skip_result = await self.reliability_service.should_skip_literature(
                            segment.literature,
                            deviation_result
                        )
                        
                        if skip_result["should_skip"]:
                            logger.info(f"跳过文献段落 {segment.id}: {skip_result['skip_reasons']}")
                            skipped_segments.append({
                                "segment_id": segment.id,
                                "literature_title": segment.literature.title[:100],
                                "skip_reasons": skip_result["skip_reasons"],
                                "reliability_score": skip_result["reliability_score"],
                                "deviation": skip_result["overall_deviation"]
                            })
                        else:
                            valid_batch.append(segment)
                else:
                    # 第一轮或无现有经验时，不进行偏离检测
                    valid_batch = current_batch
                
                if not valid_batch:
                    logger.info(f"第{iteration_round}轮所有文献段落被跳过，继续下一轮")

                    # 记录批次结果（失败）
                    batch_result = BatchResult(
                        batch_id=batch_strategy["batch_id"],
                        phase=batch_strategy["phase"],
                        literature_count=0,
                        information_gain=0.0,
                        quality_score=0.0,
                        processing_time=0.0,
                        success=False
                    )
                    self.batch_strategy.record_batch_result(batch_result)

                    # 从剩余列表中移除已处理的段落
                    for segment in current_batch:
                        if segment in remaining_segments:
                            remaining_segments.remove(segment)

                    iteration_round += 1
                    continue
                
                # 5. 准备有效批次的文献内容
                batch_start_time = asyncio.get_event_loop().time()
                batch_contents = []
                for segment in valid_batch:
                    batch_contents.append({
                        "structured_content": segment.structured_data or {},
                        "content": segment.content,
                        "segment_type": segment.segment_type,
                        "literature_reliability": segment.literature.reliability_score or 0.5,
                        "impact_factor": segment.literature.impact_factor or 0.0
                    })

                # 6. 生成经验书
                experience_result = await self.ai_service.generate_experience_book(
                    research_question, batch_contents, current_experience
                )

                if not experience_result["success"]:
                    logger.error(f"第{iteration_round}轮经验生成失败")

                    # 记录批次结果（失败）
                    batch_processing_time = asyncio.get_event_loop().time() - batch_start_time
                    batch_result = BatchResult(
                        batch_id=batch_strategy["batch_id"],
                        phase=batch_strategy["phase"],
                        literature_count=len(valid_batch),
                        information_gain=0.0,
                        quality_score=0.0,
                        processing_time=batch_processing_time,
                        success=False
                    )
                    self.batch_strategy.record_batch_result(batch_result)

                    # 从剩余列表中移除已处理的段落
                    for segment in current_batch:
                        if segment in remaining_segments:
                            remaining_segments.remove(segment)

                    iteration_round += 1
                    continue

                # 7. 更新经验内容
                batch_processing_time = asyncio.get_event_loop().time() - batch_start_time
                new_experience = experience_result["experience_content"]
                information_gain = experience_result["information_gain"]
                quality_score = experience_result.get("quality_score", 7.0)
                processed_segments += len(valid_batch)
                
                # 8. 保存经验书版本
                experience_book = ExperienceBook(
                    project_id=project_id,
                    title=f"经验书 - 第{iteration_round}轮 ({batch_strategy['config'].phase_name})",
                    research_question=research_question,
                    iteration_round=iteration_round,
                    total_literature_count=len(valid_batch),
                    current_batch_count=len(valid_batch),
                    content=new_experience,
                    information_gain=information_gain,
                    status="completed" if not remaining_segments else "generating"
                )

                self.db.add(experience_book)
                self.db.commit()

                # 9. 记录批次策略结果
                batch_result = BatchResult(
                    batch_id=batch_strategy["batch_id"],
                    phase=batch_strategy["phase"],
                    literature_count=len(valid_batch),
                    information_gain=information_gain,
                    quality_score=quality_score,
                    processing_time=batch_processing_time,
                    success=True
                )
                self.batch_strategy.record_batch_result(batch_result)
                
                # 10. 检查停止条件
                if information_gain < self.stop_conditions["min_information_gain"]:
                    consecutive_low_gain_rounds += 1
                    logger.info(f"信息增益较低: {information_gain:.3f}, 连续低增益轮次: {consecutive_low_gain_rounds}")
                else:
                    consecutive_low_gain_rounds = 0

                # 动态停止机制
                if consecutive_low_gain_rounds >= self.stop_conditions["consecutive_low_gain_rounds"]:
                    logger.info("触发动态停止机制，结束迭代")
                    experience_book.is_final = True
                    self.db.commit()
                    break

                # 11. 从剩余列表中移除已处理的段落
                for segment in current_batch:
                    if segment in remaining_segments:
                        remaining_segments.remove(segment)

                # 12. 更新进度
                progress = min(95.0, ((total_literature_count - len(remaining_segments)) / total_literature_count) * 85 + 10)
                if task_id:
                    await self._update_task_progress(
                        task_id, f"完成第{iteration_round}轮迭代 ({batch_strategy['config'].phase_name})", progress,
                        {
                            "iteration_round": iteration_round,
                            "batch_phase": batch_strategy['config'].phase_name,
                            "information_gain": information_gain,
                            "quality_score": quality_score,
                            "processed_segments": processed_segments,
                            "remaining_segments": len(remaining_segments),
                            "skipped_segments": len(skipped_segments),
                            "valid_batch_size": len(valid_batch),
                            "batch_strategy_summary": self.batch_strategy.get_strategy_summary()
                        }
                    )

                current_experience = new_experience
                iteration_round += 1
            
            # 13. 标记最终版本
            if current_experience:
                final_book = self.db.query(ExperienceBook).filter(
                    ExperienceBook.project_id == project_id,
                    ExperienceBook.iteration_round == iteration_round - 1
                ).first()

                if final_book:
                    final_book.is_final = True
                    self.db.commit()

            # 14. 完成任务
            strategy_summary = self.batch_strategy.get_strategy_summary()
            if task_id:
                await self._update_task_progress(
                    task_id, "渐进式经验增强完成", 100.0,
                    {
                        "final_round": iteration_round - 1,
                        "total_segments_processed": processed_segments,
                        "total_segments_skipped": len(skipped_segments),
                        "final_experience_id": final_book.id if final_book else None,
                        "skipped_details": skipped_segments,
                        "batch_strategy_summary": strategy_summary
                    }
                )

            return {
                "success": True,
                "final_experience": current_experience,
                "total_rounds": iteration_round - 1,
                "final_experience_id": final_book.id if final_book else None,
                "metadata": {
                    "total_segments": total_literature_count,
                    "processed_segments": processed_segments,
                    "skipped_segments": len(skipped_segments),
                    "skipped_details": skipped_segments,
                    "stopped_reason": "dynamic_stop" if consecutive_low_gain_rounds >= self.stop_conditions["consecutive_low_gain_rounds"] else "completed",
                    "reliability_filtering_enabled": True,
                    "batch_strategy_enabled": True,
                    "batch_strategy_summary": strategy_summary
                }
            }
            
        except Exception as e:
            logger.error(f"经验增强流程失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_main_experience_for_project(
        self,
        project_id: int,
        research_domain: str,
        task_id: Optional[int] = None
    ) -> Dict:
        """为项目生成主经验 - 优先使用高可靠性文献"""
        try:
            logger.info(f"开始生成项目主经验，项目ID: {project_id}")
            
            # 获取项目所有文献段落
            literature_segments = self.db.query(LiteratureSegment).join(
                LiteratureSegment.literature
            ).filter(
                LiteratureSegment.literature.has(
                    Literature.projects.any(id=project_id)
                )
            ).all()
            
            if not literature_segments:
                return {
                    "success": False,
                    "error": "项目中没有可用的文献段落"
                }
            
            # 更新进度
            if task_id:
                await self._update_task_progress(
                    task_id, "评估文献可靠性", 10.0,
                    {"literature_segments": len(literature_segments)}
                )
            
            # 获取文献对象并评估可靠性
            literature_list = []
            for segment in literature_segments:
                if segment.literature not in literature_list:
                    literature_list.append(segment.literature)
            
            # 批量评估文献可靠性
            await self.reliability_service.batch_evaluate_literature_reliability(literature_list)
            
            # 按可靠性排序文献
            sorted_literature = self.reliability_service.sort_literature_by_reliability(
                literature_list, prioritize_high_reliability=True
            )
            
            if task_id:
                await self._update_task_progress(
                    task_id, "准备高质量文献内容", 25.0,
                    {"sorted_literature": len(sorted_literature)}
                )
            
            # 优先选择高可靠性文献的段落
            high_quality_segments = []
            medium_quality_segments = []
            low_quality_segments = []
            
            for literature in sorted_literature:
                lit_segments = [s for s in literature_segments if s.literature_id == literature.id]
                reliability_score = literature.reliability_score or 0.5
                
                if reliability_score >= 0.8:
                    high_quality_segments.extend(lit_segments)
                elif reliability_score >= 0.5:
                    medium_quality_segments.extend(lit_segments)
                else:
                    low_quality_segments.extend(lit_segments)
            
            # 构建分层的文献内容
            literature_contents = []
            
            # 1. 优先使用高质量文献
            for segment in high_quality_segments:
                literature_contents.append({
                    "structured_content": segment.structured_data or {},
                    "content": segment.content,
                    "segment_type": segment.segment_type,
                    "reliability_score": segment.literature.reliability_score or 0.5,
                    "impact_factor": segment.literature.impact_factor or 0.0,
                    "quality_tier": "high"
                })
            
            # 2. 补充中等质量文献
            for segment in medium_quality_segments:
                literature_contents.append({
                    "structured_content": segment.structured_data or {},
                    "content": segment.content,
                    "segment_type": segment.segment_type,
                    "reliability_score": segment.literature.reliability_score or 0.5,
                    "impact_factor": segment.literature.impact_factor or 0.0,
                    "quality_tier": "medium"
                })
            
            # 3. 谨慎使用低质量文献（仅当高质量文献不足时）
            if len(high_quality_segments) + len(medium_quality_segments) < 10:
                for segment in low_quality_segments[:5]:  # 最多5个低质量段落
                    literature_contents.append({
                        "structured_content": segment.structured_data or {},
                        "content": segment.content,
                        "segment_type": segment.segment_type,
                        "reliability_score": segment.literature.reliability_score or 0.5,
                        "impact_factor": segment.literature.impact_factor or 0.0,
                        "quality_tier": "low"
                    })
            
            # 生成主经验
            if task_id:
                await self._update_task_progress(
                    task_id, "生成基于高质量文献的主经验", 60.0, 
                    {
                        "high_quality_segments": len(high_quality_segments),
                        "medium_quality_segments": len(medium_quality_segments),
                        "low_quality_segments_used": min(5, len(low_quality_segments))
                    }
                )
            
            main_exp_result = await self.ai_service.generate_main_experience(
                research_domain, literature_contents
            )
            
            if not main_exp_result["success"]:
                return main_exp_result
            
            # 计算质量指标
            avg_reliability = sum(content.get("reliability_score", 0.5) for content in literature_contents) / len(literature_contents)
            avg_impact_factor = sum(content.get("impact_factor", 0.0) for content in literature_contents) / len(literature_contents)
            
            # 保存主经验
            main_experience = MainExperience(
                project_id=project_id,
                title=f"{research_domain} - 主经验 (可靠性优化)",
                research_domain=research_domain,
                coverage_scope=main_exp_result.get("coverage_scope", []),
                content=main_exp_result["main_experience"],
                structured_knowledge=main_exp_result.get("structured_knowledge", {}),
                experience_type=main_exp_result.get("experience_type", "可靠性优化经验"),
                key_findings=main_exp_result.get("key_findings", []),
                practical_guidelines=main_exp_result.get("practical_guidelines", []),
                source_literature_count=len(literature_contents),
                literature_count=len(high_quality_segments) + len(medium_quality_segments) + len(low_quality_segments),
                completeness_score=min(0.95, 0.7 + avg_reliability * 0.25),  # 基于可靠性调整完整性
                accuracy_score=min(0.95, 0.6 + avg_reliability * 0.35),      # 基于可靠性调整准确性
                usefulness_score=min(0.95, 0.7 + avg_impact_factor * 0.05),   # 基于影响因子调整实用性
                quality_score=max(avg_reliability, avg_impact_factor / 10)
            )
            
            self.db.add(main_experience)
            self.db.commit()
            
            # 完成进度
            if task_id:
                await self._update_task_progress(
                    task_id, "主经验生成完成", 100.0,
                    {
                        "main_experience_id": main_experience.id,
                        "avg_reliability_score": avg_reliability,
                        "avg_impact_factor": avg_impact_factor
                    }
                )
            
            return {
                "success": True,
                "main_experience": main_exp_result["main_experience"],
                "main_experience_id": main_experience.id,
                "coverage_scope": main_exp_result.get("coverage_scope", []),
                "metadata": {
                    **main_exp_result.get("metadata", {}),
                    "reliability_optimization": True,
                    "avg_reliability_score": avg_reliability,
                    "avg_impact_factor": avg_impact_factor,
                    "quality_distribution": {
                        "high_quality_segments": len(high_quality_segments),
                        "medium_quality_segments": len(medium_quality_segments),
                        "low_quality_segments_used": min(5, len(low_quality_segments))
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"主经验生成失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _update_task_progress(
        self,
        task_id: int,
        step_name: str,
        progress: float,
        step_result: Dict = None
    ):
        """更新任务进度"""
        try:
            # 更新任务表
            task = self.db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.progress_percentage = progress
                task.current_step = step_name
                
                # 创建进度日志
                progress_log = TaskProgress(
                    task_id=task_id,
                    step_name=step_name,
                    progress_percentage=progress,
                    step_result=step_result or {}
                )
                
                self.db.add(progress_log)
                self.db.commit()
                
        except Exception as e:
            logger.error(f"更新任务进度失败: {e}")
    
    async def check_experience_relevance(
        self,
        question: str,
        main_experience: str
    ) -> float:
        """检查问题与主经验的相关性"""
        try:
            prompt = f"""
请评估以下研究问题与主经验内容的相关性。

研究问题：{question}

主经验内容（摘要）：
{main_experience[:1000]}

请以0-1之间的数值评估相关性，其中：
- 0.8-1.0: 高度相关，主经验可直接回答
- 0.5-0.8: 中度相关，主经验可部分回答
- 0.2-0.5: 低度相关，需要额外文献支持
- 0-0.2: 基本无关，需要重新收集文献

请只返回数值，如：0.75
"""
            
            response = await self.ai_service.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=50
            )
            
            relevance_text = response.choices[0].message.content.strip()
            relevance_score = float(relevance_text)
            
            return max(0.0, min(1.0, relevance_score))
            
        except Exception as e:
            logger.error(f"相关性检查失败: {e}")
            return 0.5  # 默认中等相关性
    
    async def create_main_experiences(
        self,
        project: Project,
        literature_segments: List[LiteratureSegment],
        progress_callback = None
    ) -> Dict:
        """
        创建主经验库 - 涵盖通用核心内容
        
        Args:
            project: 项目对象
            literature_segments: 文献段落列表
            progress_callback: 进度回调函数
            
        Returns:
            主经验创建结果
        """
        logger.info(f"开始为项目 {project.id} 创建主经验库")
        
        if progress_callback:
            await progress_callback("分析文献内容", 5, {"total_segments": len(literature_segments)})
        
        # 第一步：按类型分组文献段落
        grouped_segments = self._group_segments_by_type(literature_segments)
        
        if progress_callback:
            await progress_callback("创建主经验", 20, {"groups": len(grouped_segments)})
        
        # 第二步：为每种类型创建主经验
        main_experiences = {}
        total_types = len(self.main_experience_types)
        
        for i, (exp_type, config) in enumerate(self.main_experience_types.items()):
            logger.info(f"创建主经验: {exp_type}")
            
            # 获取相关文献段落
            relevant_segments = self._get_relevant_segments_for_type(
                grouped_segments, config["keywords"]
            )
            
            if relevant_segments:
                # 创建主经验
                main_exp = await self._create_single_main_experience(
                    project, exp_type, config, relevant_segments
                )
                
                if main_exp:
                    main_experiences[exp_type] = main_exp
            
            # 更新进度
            if progress_callback:
                progress = 20 + ((i + 1) / total_types) * 60
                await progress_callback(
                    f"创建主经验: {exp_type}", 
                    progress,
                    {"completed": i + 1, "total": total_types}
                )
        
        # 第三步：保存到数据库
        if progress_callback:
            await progress_callback("保存主经验库", 85, {})
        
        saved_count = 0
        for exp_type, exp_data in main_experiences.items():
            try:
                main_experience = MainExperience(
                    project_id=project.id,
                    experience_type=exp_type,
                    title=f"{project.name} - {exp_type}",
                    research_domain=project.research_direction or project.research_field or exp_type,
                    coverage_scope=exp_data.get("coverage_scope", []),
                    content=exp_data["content"],
                    structured_knowledge=exp_data.get("structured_knowledge", {}),
                    methodology_summary=exp_data.get("methodology_summary", {}),
                    key_findings=exp_data.get("key_findings", []),
                    practical_guidelines=exp_data.get("practical_guidelines", []),
                    source_literature_count=exp_data.get("source_literature_count", exp_data.get("literature_count", 0)),
                    literature_count=exp_data.get("literature_count", 0),
                    completeness_score=exp_data.get("completeness_score"),
                    accuracy_score=exp_data.get("accuracy_score"),
                    usefulness_score=exp_data.get("usefulness_score"),
                    quality_score=exp_data.get("quality_score"),
                    version="1.0",
                    status="active"
                )
                
                self.db.add(main_experience)
                saved_count += 1
                
            except Exception as e:
                logger.error(f"保存主经验失败 - {exp_type}: {e}")
        
        self.db.commit()
        
        if progress_callback:
            await progress_callback("主经验库创建完成", 100, {"created_count": saved_count})
        
        logger.info(f"主经验库创建完成，共创建 {saved_count} 个主经验")
        
        return {
            "success": True,
            "main_experiences_count": saved_count,
            "experience_types": list(main_experiences.keys()),
            "total_literature_processed": len(literature_segments)
        }
    
    async def incremental_update_main_experience(
        self,
        project: Project,
        new_literature_segments: List[LiteratureSegment],
        progress_callback = None
    ) -> Dict:
        """
        增量更新主经验库
        
        Args:
            project: 项目对象
            new_literature_segments: 新文献段落列表
            progress_callback: 进度回调函数
            
        Returns:
            更新结果
        """
        logger.info(f"开始增量更新项目 {project.id} 的主经验库")
        
        if progress_callback:
            await progress_callback("评估新文献关联性", 10, {"new_segments": len(new_literature_segments)})
        
        # 第一步：评估新文献的关联性
        relevant_segments = await self._assess_literature_relevance(
            project, new_literature_segments
        )
        
        if not relevant_segments:
            logger.info("新文献与项目主题关联度较低，跳过主经验更新")
            return {"success": True, "updated": False, "reason": "低关联度"}
        
        if progress_callback:
            await progress_callback("获取现有主经验", 25, {"relevant_segments": len(relevant_segments)})
        
        # 第二步：获取现有主经验
        existing_experiences = self.db.query(MainExperience).filter(
            MainExperience.project_id == project.id,
            MainExperience.status == "active"
        ).all()
        
        if not existing_experiences:
            logger.warning("未找到现有主经验，建议重新创建")
            return {"success": False, "error": "未找到现有主经验"}
        
        updated_count = 0
        total_experiences = len(existing_experiences)
        
        # 第三步：逐个更新主经验
        for i, main_exp in enumerate(existing_experiences):
            exp_type = (main_exp.experience_type or "未分类经验").strip()

            type_config = self.main_experience_types.get(exp_type)
            fallback_keywords = []
            if not type_config:
                fallback_keywords = [
                    "制备",
                    "表征",
                    "性能",
                    "应用",
                ]
            keywords = (type_config or {}).get("keywords", fallback_keywords)

            # 获取与此主经验相关的新文献段落
            type_relevant_segments = self._get_relevant_segments_for_type(
                {"new": relevant_segments},
                keywords,
            )
            
            if type_relevant_segments:
                logger.info(f"更新主经验: {exp_type}")
                
                # 执行增量更新
                update_result = await self._update_single_main_experience(
                    main_exp, type_relevant_segments
                )
                
                if update_result.get("success", False):
                    updated_count += 1
            
            # 更新进度
            if progress_callback:
                progress = 25 + ((i + 1) / total_experiences) * 65
                await progress_callback(
                    f"更新主经验: {exp_type}",
                    progress,
                    {"updated": updated_count, "total": total_experiences}
                )
        
        if progress_callback:
            await progress_callback("保存更新结果", 95, {})
        
        self.db.commit()
        
        if progress_callback:
            await progress_callback("增量更新完成", 100, {"updated_count": updated_count})
        
        logger.info(f"增量更新完成，更新了 {updated_count} 个主经验")
        
        return {
            "success": True,
            "updated": True,
            "updated_count": updated_count,
            "total_experiences": total_experiences,
            "new_literature_processed": len(relevant_segments)
        }
    
    def _group_segments_by_type(self, segments: List[LiteratureSegment]) -> Dict:
        """按类型分组文献段落"""
        grouped = {}
        for segment in segments:
            segment_type = segment.segment_type or "general"
            if segment_type not in grouped:
                grouped[segment_type] = []
            grouped[segment_type].append(segment)
        return grouped
    
    def _get_relevant_segments_for_type(self, grouped_segments: Dict, keywords: List[str]) -> List[LiteratureSegment]:
        """获取与特定类型相关的文献段落"""
        relevant = []
        for segments in grouped_segments.values():
            for segment in segments:
                # 检查段落内容是否包含关键词
                content = (segment.content or "").lower()
                if any(keyword.lower() in content for keyword in keywords):
                    relevant.append(segment)
        return relevant
    
    async def _create_single_main_experience(
        self, 
        project: Project, 
        exp_type: str, 
        config: Dict, 
        segments: List[LiteratureSegment]
    ) -> Optional[Dict]:
        """创建单个主经验"""
        try:
            # 构建主经验生成提示
            segments_content = []
            for segment in segments[:20]:  # 限制段落数量
                segments_content.append({
                    "content": segment.content[:500],  # 限制长度
                    "type": segment.segment_type,
                    "structured_data": segment.structured_data or {}
                })
            
            generation_prompt = f"""
作为科研经验专家，请基于以下文献内容创建关于"{exp_type}"的通用主经验。

经验类型描述: {config['description']}
关键词: {', '.join(config['keywords'])}

文献内容:
{json.dumps(segments_content, ensure_ascii=False, indent=2)[:3000]}

请生成一个完整的主经验，包含：
1. 方法学总结 (methodology_summary)
2. 关键发现 (key_findings) - 列表格式
3. 实用指南 (practical_guidelines) - 列表格式  
4. 详细内容 (content) - 结构化的经验内容

以JSON格式返回：
{{
    "methodology_summary": "方法学总结...",
    "key_findings": ["发现1", "发现2", ...],
    "practical_guidelines": ["指南1", "指南2", ...],
    "content": "详细的经验内容...",
    "literature_count": {len(segments)},
    "quality_score": 8.5
}}

要求：
- 内容要通用，覆盖多种方法和情况
- 避免直接复制原文，用总结性语言
- 突出实用性和指导价值
"""
            
            response = await self.ai_service.generate_completion(
                generation_prompt,
                model="gpt-4",
                max_tokens=2000,
                temperature=0.3
            )
            
            if response.get("success"):
                try:
                    experience_data = json.loads(response["content"])
                    experience_data["literature_count"] = len(segments)
                    return experience_data
                except json.JSONDecodeError:
                    logger.error(f"解析主经验JSON失败 - {exp_type}")
            
            return None
            
        except Exception as e:
            logger.error(f"创建主经验失败 - {exp_type}: {e}")
            return None
    
    async def _update_single_main_experience(
        self, 
        main_exp: MainExperience, 
        new_segments: List[LiteratureSegment]
    ) -> Dict:
        """更新单个主经验"""
        try:
            # 构建增量更新提示
            new_content = []
            for segment in new_segments[:10]:  # 限制新内容数量
                new_content.append({
                    "content": segment.content[:400],
                    "type": segment.segment_type
                })
            
            update_prompt = f"""
请基于新的文献内容，增量更新以下主经验：

现有主经验:
类型: {main_exp.experience_type}
内容: {main_exp.content[:1000]}...
方法学总结: {main_exp.methodology_summary}

新文献内容:
{json.dumps(new_content, ensure_ascii=False, indent=2)}

请更新主经验，保持原有结构，补充新的信息。返回JSON格式：
{{
    "content": "更新后的详细内容",
    "methodology_summary": "更新后的方法学总结", 
    "key_findings": ["更新后的关键发现"],
    "practical_guidelines": ["更新后的实用指南"],
    "information_gain": 0.15,
    "quality_score": 8.8
}}

要求：
- 保持原有经验的完整性
- 有机整合新信息
- 避免重复内容
- 提高经验的全面性
"""
            
            response = await self.ai_service.generate_completion(
                update_prompt,
                model="gpt-4",
                max_tokens=1500,
                temperature=0.2
            )
            
            if response.get("success"):
                try:
                    update_data = json.loads(response["content"])
                    
                    # 更新主经验对象
                    main_exp.content = update_data.get("content", main_exp.content)
                    main_exp.methodology_summary = update_data.get("methodology_summary", main_exp.methodology_summary)
                    main_exp.key_findings = update_data.get("key_findings", main_exp.key_findings)
                    main_exp.practical_guidelines = update_data.get("practical_guidelines", main_exp.practical_guidelines)
                    main_exp.quality_score = update_data.get("quality_score", main_exp.quality_score)
                    main_exp.literature_count += len(new_segments)
                    main_exp.updated_at = datetime.utcnow()
                    
                    # 更新版本号
                    current_version = float(main_exp.version)
                    main_exp.version = f"{current_version + 0.1:.1f}"
                    
                    return {"success": True, "information_gain": update_data.get("information_gain", 0.1)}
                    
                except json.JSONDecodeError:
                    logger.error(f"解析更新结果JSON失败")
            
            return {"success": False, "error": "AI更新失败"}
            
        except Exception as e:
            logger.error(f"更新主经验失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _assess_literature_relevance(
        self, 
        project: Project, 
        new_segments: List[LiteratureSegment]
    ) -> List[LiteratureSegment]:
        """评估新文献的关联性"""
        relevant_segments = []
        
        try:
            project_keywords = project.keywords or []
            
            for segment in new_segments:
                content = (segment.content or "").lower()
                
                # 简单的关键词匹配
                relevance_score = 0
                for keyword in project_keywords:
                    if keyword.lower() in content:
                        relevance_score += 1
                
                # 关联度阈值
                if relevance_score >= max(1, len(project_keywords) * 0.3):
                    relevant_segments.append(segment)
            
            return relevant_segments
            
        except Exception as e:
            logger.error(f"评估文献关联性失败: {e}")
            return new_segments  # 出错时返回所有段落
    
    def _should_stop_iteration(
        self, 
        iteration_round: int, 
        consecutive_low_gain_rounds: int, 
        quality_score: float
    ) -> Dict:
        """判断是否应该停止迭代"""
        
        # 检查最大迭代次数
        if iteration_round >= self.stop_conditions["max_iterations"]:
            return {"stop": True, "reason": f"达到最大迭代次数 {self.stop_conditions['max_iterations']}"}
        
        # 检查连续低增益轮次
        if consecutive_low_gain_rounds >= self.stop_conditions["consecutive_low_gain_rounds"]:
            return {"stop": True, "reason": f"连续 {consecutive_low_gain_rounds} 轮信息增益过低"}
        
        # 检查质量阈值
        if quality_score >= self.stop_conditions["min_quality_threshold"]:
            return {"stop": True, "reason": f"达到质量阈值 {quality_score}"}
        
        return {"stop": False, "reason": "继续迭代"}
    
    async def _generate_targeted_experience(
        self, 
        research_question: str, 
        batch_contents: List[Dict], 
        current_experience: Optional[str]
    ) -> Dict:
        """生成针对性经验内容"""
        try:
            # 构建针对性经验生成提示
            prompt = f"""
作为科研经验专家，请基于以下文献内容和现有经验，生成针对特定研究问题的经验内容。

研究问题: {research_question}

当前经验内容:
{current_experience or "无现有经验"}

新文献内容:
{json.dumps(batch_contents, ensure_ascii=False, indent=2)[:2000]}

请生成更新后的经验内容，要求：
1. 针对具体研究问题
2. 整合新文献的有价值信息
3. 保持经验的连续性和完整性
4. 提供实用的指导建议

返回JSON格式：
{{
    "experience_content": "更新后的完整经验内容",
    "information_gain": 0.12,
    "quality_score": 8.5,
    "key_insights": ["关键洞察1", "关键洞察2"]
}}

信息增益计算：新增有价值信息占总信息的比例
质量评分：内容的准确性、完整性和实用性综合评分（1-10分）
"""
            
            response = await self.ai_service.generate_completion(
                prompt,
                model="gpt-4",
                max_tokens=1500,
                temperature=0.3
            )
            
            if response.get("success"):
                try:
                    result = json.loads(response["content"])
                    result["success"] = True
                    return result
                except json.JSONDecodeError:
                    # 如果JSON解析失败，返回文本内容
                    return {
                        "success": True,
                        "experience_content": response["content"],
                        "information_gain": 0.1,
                        "quality_score": 7.0,
                        "key_insights": []
                    }
            
            return {"success": False, "error": "AI生成失败"}
            
        except Exception as e:
            logger.error(f"生成针对性经验失败: {e}")
            return {"success": False, "error": str(e)}
