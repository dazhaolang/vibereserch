"""
个性化推荐引擎和用户偏好学习系统
基于用户行为和专业背景提供个性化体验
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import asyncio
import json
import numpy as np
from pydantic import BaseModel
from enum import Enum
import logging
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)


class UserExpertiseLevel(Enum):
    """用户专业水平枚举"""
    UNDERGRADUATE = "undergraduate"  # 本科生
    GRADUATE = "graduate"  # 研究生
    POSTDOC = "postdoc"  # 博士后
    JUNIOR_RESEARCHER = "junior_researcher"  # 初级研究员
    SENIOR_RESEARCHER = "senior_researcher"  # 高级研究员
    PROFESSOR = "professor"  # 教授


class ResearchDomain(Enum):
    """研究领域枚举"""
    MATERIALS_SCIENCE = "materials_science"
    CHEMISTRY = "chemistry"
    PHYSICS = "physics"
    ENGINEERING = "engineering"
    BIOLOGY = "biology"
    INTERDISCIPLINARY = "interdisciplinary"


class UserPreference(BaseModel):
    """用户偏好模型"""
    user_id: str
    expertise_level: UserExpertiseLevel
    primary_domain: ResearchDomain
    secondary_domains: List[ResearchDomain] = []
    preferred_content_depth: str = "medium"  # shallow, medium, deep
    preferred_interaction_style: str = "guided"  # autonomous, guided, detailed
    language_preference: str = "zh"  # zh, en
    notification_preferences: Dict[str, bool] = {}
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()


class UserBehavior(BaseModel):
    """用户行为模型"""
    user_id: str
    session_id: str
    action: str
    context: Dict[str, Any] = {}
    timestamp: datetime = datetime.now()
    duration: Optional[float] = None  # 行为持续时间（秒）


class PersonalizationProfile(BaseModel):
    """个性化档案模型"""
    user_id: str
    expertise_score: float = 0.5  # 0-1，专业水平评分
    domain_interests: Dict[str, float] = {}  # 领域兴趣权重
    interaction_patterns: Dict[str, Any] = {}  # 交互模式
    content_preferences: Dict[str, Any] = {}  # 内容偏好
    success_patterns: Dict[str, Any] = {}  # 成功模式
    learning_trajectory: List[Dict[str, Any]] = []  # 学习轨迹
    last_updated: datetime = datetime.now()


class UserProfileAnalyzer:
    """用户档案分析器"""
    
    def __init__(self):
        self.domain_keywords = {
            ResearchDomain.MATERIALS_SCIENCE: [
                "nanomaterial", "composite", "polymer", "ceramic", "metal", "crystal",
                "纳米材料", "复合材料", "聚合物", "陶瓷", "金属", "晶体"
            ],
            ResearchDomain.CHEMISTRY: [
                "synthesis", "reaction", "catalyst", "organic", "inorganic", "analytical",
                "合成", "反应", "催化", "有机", "无机", "分析"
            ],
            ResearchDomain.PHYSICS: [
                "quantum", "optics", "mechanics", "thermodynamics", "electromagnetic",
                "量子", "光学", "力学", "热力学", "电磁"
            ]
        }
    
    async def analyze_user_expertise(self, user_behaviors: List[UserBehavior]) -> float:
        """分析用户专业水平"""
        
        if not user_behaviors:
            return 0.5  # 默认中等水平
        
        expertise_indicators = {
            "deep_question_asking": 0.2,
            "technical_term_usage": 0.3,
            "complex_workflow_completion": 0.3,
            "advanced_feature_usage": 0.2
        }
        
        expertise_score = 0.0
        
        # 分析深度问题提问
        deep_questions = sum(1 for b in user_behaviors 
                           if b.action == "ask_question" and len(b.context.get("message", "")) > 100)
        if deep_questions > 0:
            expertise_score += expertise_indicators["deep_question_asking"] * min(deep_questions / 10, 1.0)
        
        # 分析技术术语使用
        technical_terms = 0
        for behavior in user_behaviors:
            if behavior.action in ["ask_question", "provide_feedback"]:
                message = behavior.context.get("message", "").lower()
                for domain_keywords in self.domain_keywords.values():
                    technical_terms += sum(1 for keyword in domain_keywords if keyword in message)
        
        if technical_terms > 0:
            expertise_score += expertise_indicators["technical_term_usage"] * min(technical_terms / 20, 1.0)
        
        # 分析复杂工作流完成情况
        complex_workflows = sum(1 for b in user_behaviors 
                              if b.action == "complete_workflow" and 
                              b.context.get("complexity", "simple") in ["complex", "advanced"])
        if complex_workflows > 0:
            expertise_score += expertise_indicators["complex_workflow_completion"] * min(complex_workflows / 5, 1.0)
        
        # 分析高级功能使用
        advanced_features = sum(1 for b in user_behaviors 
                              if b.action in ["custom_template", "advanced_search", "batch_processing"])
        if advanced_features > 0:
            expertise_score += expertise_indicators["advanced_feature_usage"] * min(advanced_features / 8, 1.0)
        
        return min(expertise_score, 1.0)
    
    async def identify_domain_interests(self, user_behaviors: List[UserBehavior]) -> Dict[str, float]:
        """识别领域兴趣"""
        
        domain_scores = defaultdict(float)
        
        for behavior in user_behaviors:
            if behavior.action in ["search_literature", "ask_question", "view_content"]:
                message = behavior.context.get("message", "") + " " + behavior.context.get("keywords", "")
                message = message.lower()
                
                for domain, keywords in self.domain_keywords.items():
                    matches = sum(1 for keyword in keywords if keyword in message)
                    if matches > 0:
                        # 根据行为类型给予不同权重
                        weight = 1.0
                        if behavior.action == "search_literature":
                            weight = 1.5
                        elif behavior.action == "ask_question":
                            weight = 2.0
                        
                        domain_scores[domain.value] += matches * weight
        
        # 标准化分数
        total_score = sum(domain_scores.values())
        if total_score > 0:
            domain_scores = {domain: score / total_score for domain, score in domain_scores.items()}
        
        return dict(domain_scores)
    
    async def analyze_interaction_patterns(self, user_behaviors: List[UserBehavior]) -> Dict[str, Any]:
        """分析交互模式"""
        
        patterns = {
            "session_duration_avg": 0.0,
            "actions_per_session": 0.0,
            "preferred_time_of_day": "morning",
            "interaction_frequency": "regular",
            "help_seeking_tendency": "medium",
            "exploration_vs_efficiency": "balanced"
        }
        
        if not user_behaviors:
            return patterns
        
        # 按会话分组
        sessions = defaultdict(list)
        for behavior in user_behaviors:
            sessions[behavior.session_id].append(behavior)
        
        # 计算平均会话持续时间
        session_durations = []
        actions_per_session = []
        
        for session_behaviors in sessions.values():
            if len(session_behaviors) > 1:
                start_time = min(b.timestamp for b in session_behaviors)
                end_time = max(b.timestamp for b in session_behaviors)
                duration = (end_time - start_time).total_seconds() / 60  # 分钟
                session_durations.append(duration)
                actions_per_session.append(len(session_behaviors))
        
        if session_durations:
            patterns["session_duration_avg"] = np.mean(session_durations)
            patterns["actions_per_session"] = np.mean(actions_per_session)
        
        # 分析偏好时间
        hours = [b.timestamp.hour for b in user_behaviors]
        if hours:
            avg_hour = np.mean(hours)
            if 6 <= avg_hour < 12:
                patterns["preferred_time_of_day"] = "morning"
            elif 12 <= avg_hour < 18:
                patterns["preferred_time_of_day"] = "afternoon"
            else:
                patterns["preferred_time_of_day"] = "evening"
        
        # 分析求助倾向
        help_actions = sum(1 for b in user_behaviors if b.action in ["ask_help", "view_tutorial", "request_guidance"])
        total_actions = len(user_behaviors)
        help_ratio = help_actions / total_actions if total_actions > 0 else 0
        
        if help_ratio > 0.3:
            patterns["help_seeking_tendency"] = "high"
        elif help_ratio > 0.1:
            patterns["help_seeking_tendency"] = "medium"
        else:
            patterns["help_seeking_tendency"] = "low"
        
        return patterns


class ContentPersonalizer:
    """内容个性化器"""
    
    async def personalize_content(self, 
                                content: str, 
                                user_profile: PersonalizationProfile) -> str:
        """个性化内容"""
        
        expertise_level = user_profile.expertise_score
        content_depth = user_profile.content_preferences.get("depth", "medium")
        
        # 根据专业水平调整内容深度
        if expertise_level < 0.3:  # 初学者
            return await self._simplify_content(content)
        elif expertise_level > 0.7:  # 专家
            return await self._enrich_content(content)
        else:  # 中等水平
            return content
    
    async def _simplify_content(self, content: str) -> str:
        """简化内容（适合初学者）"""
        # 添加更多解释和背景信息
        simplified = "【背景介绍】\n"
        simplified += "本内容将为您详细介绍相关概念和方法。\n\n"
        simplified += content
        simplified += "\n\n【关键术语解释】\n"
        simplified += "• 如有不理解的术语，请随时询问\n"
        simplified += "• 建议先了解基础概念再深入学习"
        
        return simplified
    
    async def _enrich_content(self, content: str) -> str:
        """丰富内容（适合专家）"""
        # 添加更多技术细节和高级信息
        enriched = content
        enriched += "\n\n【高级分析】\n"
        enriched += "• 可考虑的优化方向和前沿发展\n"
        enriched += "• 相关的理论基础和计算模型\n"
        enriched += "• 潜在的应用扩展和创新点"
        
        return enriched
    
    async def recommend_next_actions(self, 
                                   user_profile: PersonalizationProfile, 
                                   current_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """推荐下一步操作"""
        
        recommendations = []
        
        # 基于专业水平推荐
        expertise_level = user_profile.expertise_score
        
        if expertise_level < 0.4:  # 初学者
            recommendations.extend([
                {"action": "view_tutorial", "label": "查看基础教程", "priority": "high"},
                {"action": "guided_workflow", "label": "使用引导模式", "priority": "high"},
                {"action": "ask_question", "label": "询问基础概念", "priority": "medium"}
            ])
        elif expertise_level > 0.7:  # 专家
            recommendations.extend([
                {"action": "advanced_analysis", "label": "高级分析功能", "priority": "high"},
                {"action": "custom_workflow", "label": "自定义工作流", "priority": "medium"},
                {"action": "batch_processing", "label": "批量处理", "priority": "medium"}
            ])
        else:  # 中等水平
            recommendations.extend([
                {"action": "standard_workflow", "label": "标准工作流程", "priority": "high"},
                {"action": "explore_features", "label": "探索功能", "priority": "medium"}
            ])
        
        # 基于领域兴趣推荐
        top_domain = max(user_profile.domain_interests.items(), 
                        key=lambda x: x[1], default=(None, 0))[0]
        
        if top_domain:
            recommendations.append({
                "action": "domain_specific_content",
                "label": f"查看{top_domain}相关内容",
                "priority": "medium",
                "domain": top_domain
            })
        
        # 基于交互模式推荐
        interaction_style = user_profile.interaction_patterns.get("help_seeking_tendency", "medium")
        
        if interaction_style == "high":
            recommendations.append({
                "action": "interactive_guidance",
                "label": "获取交互式指导",
                "priority": "high"
            })
        
        return sorted(recommendations, key=lambda x: x.get("priority", "low"), reverse=True)[:5]


class LearningTrajectoryTracker:
    """学习轨迹跟踪器"""
    
    async def track_learning_progress(self, 
                                    user_id: str, 
                                    completed_task: Dict[str, Any],
                                    user_profile: PersonalizationProfile) -> Dict[str, Any]:
        """跟踪学习进度"""
        
        # 分析任务复杂度
        task_complexity = await self._assess_task_complexity(completed_task)
        
        # 更新学习轨迹
        learning_event = {
            "timestamp": datetime.now(),
            "task_type": completed_task.get("type", "unknown"),
            "complexity": task_complexity,
            "success": completed_task.get("success", True),
            "time_spent": completed_task.get("duration", 0),
            "help_used": completed_task.get("help_requests", 0)
        }
        
        user_profile.learning_trajectory.append(learning_event)
        
        # 分析学习趋势
        progress_analysis = await self._analyze_learning_trend(user_profile.learning_trajectory)
        
        return {
            "current_level": progress_analysis["current_level"],
            "progress_rate": progress_analysis["progress_rate"],
            "strengths": progress_analysis["strengths"],
            "improvement_areas": progress_analysis["improvement_areas"],
            "next_challenges": progress_analysis["next_challenges"]
        }
    
    async def _assess_task_complexity(self, task: Dict[str, Any]) -> str:
        """评估任务复杂度"""
        
        complexity_indicators = {
            "literature_search": "simple",
            "structure_template_creation": "medium",
            "experience_enhancement": "complex",
            "custom_analysis": "complex",
            "batch_processing": "advanced"
        }
        
        task_type = task.get("type", "unknown")
        base_complexity = complexity_indicators.get(task_type, "simple")
        
        # 考虑其他因素
        if task.get("custom_parameters"):
            base_complexity = "complex" if base_complexity == "medium" else "advanced"
        
        if task.get("duration", 0) > 1800:  # 超过30分钟
            base_complexity = "complex" if base_complexity == "simple" else "advanced"
        
        return base_complexity
    
    async def _analyze_learning_trend(self, trajectory: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析学习趋势"""
        
        if not trajectory:
            return {
                "current_level": "beginner",
                "progress_rate": 0.0,
                "strengths": [],
                "improvement_areas": ["需要更多练习"],
                "next_challenges": ["开始基础任务"]
            }
        
        # 分析最近的任务
        recent_tasks = trajectory[-10:]  # 最近10个任务
        
        # 计算成功率
        success_rate = sum(1 for t in recent_tasks if t["success"]) / len(recent_tasks)
        
        # 分析复杂度趋势
        complexity_levels = {"simple": 1, "medium": 2, "complex": 3, "advanced": 4}
        recent_complexity = [complexity_levels.get(t["complexity"], 1) for t in recent_tasks]
        avg_complexity = np.mean(recent_complexity) if recent_complexity else 1
        
        # 确定当前水平
        if avg_complexity >= 3.5 and success_rate >= 0.8:
            current_level = "expert"
        elif avg_complexity >= 2.5 and success_rate >= 0.7:
            current_level = "advanced"
        elif avg_complexity >= 1.5 and success_rate >= 0.6:
            current_level = "intermediate"
        else:
            current_level = "beginner"
        
        # 计算进步率
        if len(trajectory) > 5:
            early_complexity = np.mean([complexity_levels.get(t["complexity"], 1) 
                                      for t in trajectory[:5]])
            progress_rate = (avg_complexity - early_complexity) / len(trajectory) * 10
        else:
            progress_rate = 0.0
        
        # 识别优势和改进领域
        task_types = Counter(t["task_type"] for t in recent_tasks)
        successful_tasks = Counter(t["task_type"] for t in recent_tasks if t["success"])
        
        strengths = [task_type for task_type, count in successful_tasks.most_common(3)]
        improvement_areas = [task_type for task_type in task_types 
                           if successful_tasks.get(task_type, 0) / task_types[task_type] < 0.6]
        
        # 推荐下一步挑战
        next_challenges = []
        if current_level == "beginner":
            next_challenges = ["尝试中等复杂度任务", "学习高级功能"]
        elif current_level == "intermediate":
            next_challenges = ["挑战复杂任务", "探索自定义功能"]
        elif current_level == "advanced":
            next_challenges = ["尝试批量处理", "开发自定义工作流"]
        else:
            next_challenges = ["分享经验", "指导其他用户"]
        
        return {
            "current_level": current_level,
            "progress_rate": progress_rate,
            "strengths": strengths[:3],
            "improvement_areas": improvement_areas[:3],
            "next_challenges": next_challenges
        }


class PersonalizationEngine:
    """个性化引擎主控制器"""
    
    def __init__(self):
        self.profile_analyzer = UserProfileAnalyzer()
        self.content_personalizer = ContentPersonalizer()
        self.trajectory_tracker = LearningTrajectoryTracker()
        self.user_profiles = {}  # 存储用户档案
        self.user_behaviors = defaultdict(list)  # 存储用户行为
    
    async def initialize_user_profile(self, user_id: str, initial_preferences: UserPreference) -> PersonalizationProfile:
        """初始化用户档案"""
        
        profile = PersonalizationProfile(
            user_id=user_id,
            expertise_score=0.5,  # 默认中等水平
            domain_interests={initial_preferences.primary_domain.value: 1.0},
            interaction_patterns={},
            content_preferences={
                "depth": initial_preferences.preferred_content_depth,
                "style": initial_preferences.preferred_interaction_style,
                "language": initial_preferences.language_preference
            },
            success_patterns={},
            learning_trajectory=[]
        )
        
        self.user_profiles[user_id] = profile
        
        logger.info(f"Initialized user profile for user {user_id}")
        
        return profile
    
    async def update_user_profile(self, user_behavior: UserBehavior) -> PersonalizationProfile:
        """更新用户档案"""
        
        user_id = user_behavior.user_id
        
        # 记录用户行为
        self.user_behaviors[user_id].append(user_behavior)
        
        # 获取或创建用户档案
        if user_id not in self.user_profiles:
            # 创建默认档案
            default_preferences = UserPreference(
                user_id=user_id,
                expertise_level=UserExpertiseLevel.GRADUATE,
                primary_domain=ResearchDomain.MATERIALS_SCIENCE
            )
            profile = await self.initialize_user_profile(user_id, default_preferences)
        else:
            profile = self.user_profiles[user_id]
        
        # 定期更新档案（每10个行为更新一次）
        if len(self.user_behaviors[user_id]) % 10 == 0:
            await self._full_profile_update(user_id)
        
        return profile
    
    async def _full_profile_update(self, user_id: str):
        """完整的档案更新"""
        
        behaviors = self.user_behaviors[user_id]
        profile = self.user_profiles[user_id]
        
        # 更新专业水平
        profile.expertise_score = await self.profile_analyzer.analyze_user_expertise(behaviors)
        
        # 更新领域兴趣
        profile.domain_interests = await self.profile_analyzer.identify_domain_interests(behaviors)
        
        # 更新交互模式
        profile.interaction_patterns = await self.profile_analyzer.analyze_interaction_patterns(behaviors)
        
        # 更新时间戳
        profile.last_updated = datetime.now()
        
        logger.info(f"Updated full profile for user {user_id}")
    
    async def get_personalized_content(self, 
                                     user_id: str, 
                                     content: str, 
                                     context: Dict[str, Any] = {}) -> str:
        """获取个性化内容"""
        
        if user_id not in self.user_profiles:
            return content  # 返回原始内容
        
        profile = self.user_profiles[user_id]
        personalized_content = await self.content_personalizer.personalize_content(content, profile)
        
        return personalized_content
    
    async def get_personalized_recommendations(self, 
                                             user_id: str, 
                                             current_context: Dict[str, Any] = {}) -> List[Dict[str, Any]]:
        """获取个性化推荐"""
        
        if user_id not in self.user_profiles:
            return []  # 返回空推荐
        
        profile = self.user_profiles[user_id]
        recommendations = await self.content_personalizer.recommend_next_actions(profile, current_context)
        
        return recommendations
    
    async def track_task_completion(self, 
                                  user_id: str, 
                                  completed_task: Dict[str, Any]) -> Dict[str, Any]:
        """跟踪任务完成情况"""
        
        if user_id not in self.user_profiles:
            return {}
        
        profile = self.user_profiles[user_id]
        progress_analysis = await self.trajectory_tracker.track_learning_progress(
            user_id, completed_task, profile
        )
        
        return progress_analysis
    
    async def get_user_insights(self, user_id: str) -> Dict[str, Any]:
        """获取用户洞察"""
        
        if user_id not in self.user_profiles:
            return {"error": "User profile not found"}
        
        profile = self.user_profiles[user_id]
        behaviors = self.user_behaviors[user_id]
        
        # 计算活跃度
        recent_behaviors = [b for b in behaviors 
                          if b.timestamp > datetime.now() - timedelta(days=7)]
        activity_level = len(recent_behaviors)
        
        # 分析使用模式
        session_count = len(set(b.session_id for b in behaviors))
        avg_session_length = len(behaviors) / session_count if session_count > 0 else 0
        
        # 获取学习进度
        learning_progress = "初学者"
        if profile.expertise_score > 0.7:
            learning_progress = "专家"
        elif profile.expertise_score > 0.5:
            learning_progress = "中级"
        elif profile.expertise_score > 0.3:
            learning_progress = "初级"
        
        return {
            "user_id": user_id,
            "expertise_level": learning_progress,
            "primary_interests": list(profile.domain_interests.keys())[:3],
            "activity_level": activity_level,
            "total_sessions": session_count,
            "avg_session_length": avg_session_length,
            "learning_trajectory_length": len(profile.learning_trajectory),
            "last_active": max(b.timestamp for b in behaviors).isoformat() if behaviors else None,
            "profile_last_updated": profile.last_updated.isoformat()
        }
    
    async def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """导出用户数据"""
        
        if user_id not in self.user_profiles:
            return {"error": "User profile not found"}
        
        profile = self.user_profiles[user_id]
        behaviors = self.user_behaviors[user_id]
        
        return {
            "profile": {
                "user_id": profile.user_id,
                "expertise_score": profile.expertise_score,
                "domain_interests": profile.domain_interests,
                "interaction_patterns": profile.interaction_patterns,
                "content_preferences": profile.content_preferences,
                "learning_trajectory_count": len(profile.learning_trajectory),
                "last_updated": profile.last_updated.isoformat()
            },
            "behavior_summary": {
                "total_behaviors": len(behaviors),
                "unique_sessions": len(set(b.session_id for b in behaviors)),
                "date_range": {
                    "start": min(b.timestamp for b in behaviors).isoformat() if behaviors else None,
                    "end": max(b.timestamp for b in behaviors).isoformat() if behaviors else None
                },
                "top_actions": Counter(b.action for b in behaviors).most_common(10)
            }
        }


# 全局个性化引擎实例
personalization_engine = PersonalizationEngine()