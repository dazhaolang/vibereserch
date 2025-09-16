"""
增强个性化引擎
提供智能推荐、个性化设置、用户行为分析
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from dataclasses import dataclass
from enum import Enum
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
from loguru import logger

from app.core.database import redis_client
from app.models.user import User, MembershipType
from app.models.literature import Literature
from app.models.project import Project
from app.core.intelligent_cache import cached

class RecommendationType(Enum):
    LITERATURE = "literature"
    RESEARCH_DIRECTION = "research_direction"
    COLLABORATION = "collaboration"
    TOOLS = "tools"
    LEARNING = "learning"

class UserBehaviorType(Enum):
    SEARCH = "search"
    VIEW = "view"
    DOWNLOAD = "download"
    BOOKMARK = "bookmark"
    SHARE = "share"
    COMMENT = "comment"
    RATE = "rate"

@dataclass
class UserPreference:
    research_fields: List[str]
    preferred_journals: List[str]
    favorite_authors: List[str]
    methodology_preferences: List[str]
    reading_time_preference: str  # 'morning', 'afternoon', 'evening', 'night'
    complexity_preference: str    # 'simple', 'medium', 'advanced'
    language_preference: List[str]

@dataclass
class RecommendationItem:
    item_id: str
    item_type: RecommendationType
    title: str
    description: str
    relevance_score: float
    confidence_score: float
    reasoning: str
    metadata: Dict[str, Any]

class EnhancedPersonalizationEngine:
    """增强个性化引擎"""
    
    def __init__(self):
        self.user_profiles = {}
        self.interaction_matrix = defaultdict(lambda: defaultdict(float))
        self.content_features = {}
        self.collaborative_filters = {}
        
        # 推荐算法权重配置
        self.algorithm_weights = {
            'content_based': 0.4,      # 基于内容的推荐
            'collaborative': 0.3,      # 协同过滤
            'popularity': 0.15,        # 热门推荐
            'diversity': 0.15          # 多样性推荐
        }
    
    async def analyze_user_behavior(
        self, 
        user_id: int, 
        behavior_type: UserBehaviorType,
        target_item: Dict[str, Any],
        context: Optional[Dict] = None
    ):
        """分析和记录用户行为"""
        
        behavior_data = {
            'user_id': user_id,
            'behavior_type': behavior_type.value,
            'target_item': target_item,
            'context': context or {},
            'timestamp': datetime.now().isoformat(),
            'session_id': context.get('session_id') if context else None
        }
        
        try:
            # 记录到Redis
            behavior_key = f"user_behavior:{user_id}:{int(time.time())}"
            await redis_client.setex(behavior_key, 86400 * 30, json.dumps(behavior_data))  # 保留30天
            
            # 更新用户兴趣模型
            await self._update_user_interest_model(user_id, behavior_data)
            
            # 更新协同过滤矩阵
            await self._update_collaborative_matrix(user_id, target_item, behavior_type)
            
            logger.debug(f"记录用户行为: {user_id} -> {behavior_type.value}")
            
        except Exception as e:
            logger.error(f"记录用户行为失败: {e}")
    
    async def _update_user_interest_model(self, user_id: int, behavior_data: Dict):
        """更新用户兴趣模型"""
        
        # 行为权重
        behavior_weights = {
            UserBehaviorType.VIEW.value: 1.0,
            UserBehaviorType.DOWNLOAD.value: 3.0,
            UserBehaviorType.BOOKMARK.value: 2.5,
            UserBehaviorType.SHARE.value: 2.0,
            UserBehaviorType.RATE.value: 4.0,
            UserBehaviorType.COMMENT.value: 3.5,
            UserBehaviorType.SEARCH.value: 0.5
        }
        
        weight = behavior_weights.get(behavior_data['behavior_type'], 1.0)
        target_item = behavior_data['target_item']
        
        # 提取特征
        features = []
        if target_item.get('keywords'):
            features.extend(target_item['keywords'])
        if target_item.get('category'):
            features.append(target_item['category'])
        if target_item.get('research_field'):
            features.append(target_item['research_field'])
        
        # 更新用户兴趣向量
        user_interests = await self._get_user_interests(user_id)
        
        for feature in features:
            user_interests[feature] = user_interests.get(feature, 0.0) + weight
        
        # 归一化处理
        max_score = max(user_interests.values()) if user_interests else 1.0
        normalized_interests = {
            k: v / max_score for k, v in user_interests.items()
        }
        
        # 保存到Redis
        interests_key = f"user_interests:{user_id}"
        await redis_client.setex(interests_key, 86400 * 7, json.dumps(normalized_interests))
    
    async def _get_user_interests(self, user_id: int) -> Dict[str, float]:
        """获取用户兴趣向量"""
        try:
            interests_key = f"user_interests:{user_id}"
            data = await redis_client.get(interests_key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"获取用户兴趣失败: {e}")
        
        return {}
    
    @cached("literature_recommendations:{user_id}", ttl=1800)
    async def recommend_literature(
        self, 
        user_id: int, 
        project_id: Optional[int] = None,
        count: int = 10
    ) -> List[RecommendationItem]:
        """文献推荐"""
        
        try:
            # 获取用户兴趣和历史行为
            user_interests = await self._get_user_interests(user_id)
            user_history = await self._get_user_literature_history(user_id)
            
            # 多算法推荐
            content_recs = await self._content_based_literature_recommendation(
                user_interests, user_history, project_id, count
            )
            
            collaborative_recs = await self._collaborative_literature_recommendation(
                user_id, user_history, count
            )
            
            popularity_recs = await self._popularity_based_recommendation(
                user_interests, count
            )
            
            # 融合推荐结果
            final_recommendations = await self._merge_recommendations([
                (content_recs, self.algorithm_weights['content_based']),
                (collaborative_recs, self.algorithm_weights['collaborative']),
                (popularity_recs, self.algorithm_weights['popularity'])
            ], count)
            
            # 添加多样性
            diverse_recs = await self._add_diversity(final_recommendations, user_interests)
            
            return diverse_recs[:count]
            
        except Exception as e:
            logger.error(f"文献推荐失败: {e}")
            return []
    
    async def _content_based_literature_recommendation(
        self, 
        user_interests: Dict[str, float], 
        user_history: List[Dict],
        project_id: Optional[int],
        count: int
    ) -> List[RecommendationItem]:
        """基于内容的文献推荐"""
        
        recommendations = []
        
        try:
            # 构建查询条件
            interest_keywords = list(user_interests.keys())
            
            # 从数据库查询候选文献
            async with engine.begin() as conn:
                # 排除用户已读文献
                excluded_ids = [h['literature_id'] for h in user_history]
                excluded_clause = f"AND l.id NOT IN ({','.join(map(str, excluded_ids))})" if excluded_ids else ""
                
                project_clause = f"AND l.project_id != {project_id}" if project_id else ""
                
                query = f"""
                    SELECT l.id, l.title, l.abstract, l.keywords, l.authors, 
                           l.journal, l.publication_year, l.relevance_score
                    FROM literature l
                    WHERE l.status = 'processed'
                    {excluded_clause}
                    {project_clause}
                    ORDER BY l.relevance_score DESC, l.created_at DESC
                    LIMIT 100
                """
                
                result = await conn.execute(text(query))
                candidate_literature = result.fetchall()
            
            # 计算内容相似度
            for lit in candidate_literature:
                content_score = self._calculate_content_similarity(
                    user_interests, 
                    {
                        'keywords': lit.keywords or [],
                        'title': lit.title or '',
                        'abstract': lit.abstract or ''
                    }
                )
                
                if content_score > 0.3:  # 相似度阈值
                    recommendations.append(RecommendationItem(
                        item_id=str(lit.id),
                        item_type=RecommendationType.LITERATURE,
                        title=lit.title,
                        description=lit.abstract[:200] + "..." if lit.abstract else "",
                        relevance_score=content_score,
                        confidence_score=min(0.9, content_score + 0.1),
                        reasoning=f"基于您的兴趣关键词: {', '.join(list(user_interests.keys())[:3])}",
                        metadata={
                            'authors': lit.authors,
                            'journal': lit.journal,
                            'year': lit.publication_year,
                            'algorithm': 'content_based'
                        }
                    ))
            
            # 按相关性排序
            recommendations.sort(key=lambda x: x.relevance_score, reverse=True)
            
        except Exception as e:
            logger.error(f"基于内容的推荐失败: {e}")
        
        return recommendations[:count]
    
    def _calculate_content_similarity(self, user_interests: Dict[str, float], content: Dict) -> float:
        """计算内容相似度"""
        
        # 提取内容特征
        content_features = []
        content_features.extend(content.get('keywords', []))
        
        # 从标题和摘要中提取关键词
        text_content = f"{content.get('title', '')} {content.get('abstract', '')}"
        words = text_content.lower().split()
        content_features.extend([w for w in words if len(w) > 3])
        
        # 计算兴趣匹配度
        total_score = 0.0
        matched_features = 0
        
        for feature in content_features:
            if feature in user_interests:
                total_score += user_interests[feature]
                matched_features += 1
        
        # 归一化分数
        if matched_features > 0:
            avg_score = total_score / matched_features
            # 考虑匹配特征的比例
            coverage_bonus = min(0.2, matched_features / len(user_interests))
            return min(1.0, avg_score + coverage_bonus)
        
        return 0.0
    
    async def recommend_research_directions(
        self, 
        user_id: int, 
        current_field: Optional[str] = None
    ) -> List[RecommendationItem]:
        """研究方向推荐"""
        
        try:
            user_interests = await self._get_user_interests(user_id)
            
            # 分析当前研究趋势
            trending_topics = await self._analyze_research_trends()
            
            # 跨领域机会分析
            cross_field_opportunities = await self._find_cross_field_opportunities(
                user_interests, current_field
            )
            
            # 生成推荐
            recommendations = []
            
            # 趋势推荐
            for topic in trending_topics[:5]:
                if self._is_relevant_to_user(topic, user_interests):
                    recommendations.append(RecommendationItem(
                        item_id=f"trend_{topic['id']}",
                        item_type=RecommendationType.RESEARCH_DIRECTION,
                        title=f"热门研究方向: {topic['name']}",
                        description=topic['description'],
                        relevance_score=topic['relevance_score'],
                        confidence_score=0.8,
                        reasoning=f"基于最新研究趋势，与您的兴趣领域高度匹配",
                        metadata={
                            'trend_score': topic['trend_score'],
                            'paper_count': topic['paper_count'],
                            'growth_rate': topic['growth_rate']
                        }
                    ))
            
            # 跨领域推荐
            for opportunity in cross_field_opportunities[:3]:
                recommendations.append(RecommendationItem(
                    item_id=f"cross_field_{opportunity['id']}",
                    item_type=RecommendationType.RESEARCH_DIRECTION,
                    title=f"跨领域机会: {opportunity['title']}",
                    description=opportunity['description'],
                    relevance_score=opportunity['potential_score'],
                    confidence_score=0.7,
                    reasoning=f"结合{opportunity['fields']}领域的创新机会",
                    metadata={
                        'fields': opportunity['fields'],
                        'innovation_potential': opportunity['innovation_potential']
                    }
                ))
            
            return sorted(recommendations, key=lambda x: x.relevance_score, reverse=True)
            
        except Exception as e:
            logger.error(f"研究方向推荐失败: {e}")
            return []
    
    async def recommend_collaborators(
        self, 
        user_id: int, 
        project_id: Optional[int] = None
    ) -> List[RecommendationItem]:
        """协作者推荐"""
        
        try:
            user_interests = await self._get_user_interests(user_id)
            
            # 查找相似兴趣的用户
            similar_users = await self._find_similar_users(user_id, user_interests)
            
            # 查找互补技能的用户
            complementary_users = await self._find_complementary_users(user_id, user_interests)
            
            recommendations = []
            
            # 相似兴趣推荐
            for similar_user in similar_users[:5]:
                recommendations.append(RecommendationItem(
                    item_id=f"similar_{similar_user['user_id']}",
                    item_type=RecommendationType.COLLABORATION,
                    title=f"研究伙伴: {similar_user['username']}",
                    description=f"研究领域: {similar_user['research_field']}",
                    relevance_score=similar_user['similarity_score'],
                    confidence_score=0.8,
                    reasoning=f"具有相似的研究兴趣: {', '.join(similar_user['common_interests'][:3])}",
                    metadata={
                        'user_id': similar_user['user_id'],
                        'institution': similar_user['institution'],
                        'collaboration_history': similar_user['collaboration_count']
                    }
                ))
            
            # 互补技能推荐
            for comp_user in complementary_users[:3]:
                recommendations.append(RecommendationItem(
                    item_id=f"complementary_{comp_user['user_id']}",
                    item_type=RecommendationType.COLLABORATION,
                    title=f"技能互补: {comp_user['username']}",
                    description=f"擅长领域: {comp_user['expertise']}",
                    relevance_score=comp_user['complementary_score'],
                    confidence_score=0.75,
                    reasoning=f"技能互补，可以增强研究团队实力",
                    metadata={
                        'user_id': comp_user['user_id'],
                        'complementary_skills': comp_user['complementary_skills']
                    }
                ))
            
            return sorted(recommendations, key=lambda x: x.relevance_score, reverse=True)
            
        except Exception as e:
            logger.error(f"协作者推荐失败: {e}")
            return []
    
    async def generate_smart_suggestions(
        self, 
        user_id: int, 
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """生成智能建议"""
        
        suggestions = []
        
        try:
            # 基于当前上下文生成建议
            current_page = context.get('current_page')
            current_action = context.get('current_action')
            user_interests = await self._get_user_interests(user_id)
            
            if current_page == 'literature_list':
                suggestions.extend(await self._generate_literature_suggestions(user_id, context))
            elif current_page == 'project_dashboard':
                suggestions.extend(await self._generate_project_suggestions(user_id, context))
            elif current_page == 'analysis':
                suggestions.extend(await self._generate_analysis_suggestions(user_id, context))
            
            # 通用建议
            suggestions.extend(await self._generate_general_suggestions(user_id, user_interests))
            
            # 按优先级排序
            suggestions.sort(key=lambda x: x.get('priority', 0), reverse=True)
            
            return suggestions[:5]  # 返回前5个建议
            
        except Exception as e:
            logger.error(f"生成智能建议失败: {e}")
            return []
    
    async def _generate_literature_suggestions(self, user_id: int, context: Dict) -> List[Dict]:
        """生成文献相关建议"""
        suggestions = []
        
        # 检查是否有未读文献
        unread_count = context.get('unread_literature_count', 0)
        if unread_count > 10:
            suggestions.append({
                'id': 'batch_process_literature',
                'type': 'action',
                'title': '批量处理文献',
                'description': f'您有{unread_count}篇未处理的文献，建议使用批量操作提高效率',
                'action': 'open_batch_operations',
                'priority': 8,
                'icon': 'batch_process'
            })
        
        # 检查是否需要更新搜索关键词
        last_search = context.get('last_search_time')
        if last_search and (datetime.now() - datetime.fromisoformat(last_search)).days > 7:
            suggestions.append({
                'id': 'update_search_keywords',
                'type': 'suggestion',
                'title': '更新搜索关键词',
                'description': '距离上次搜索已过一周，建议更新关键词以获取最新文献',
                'action': 'open_search_settings',
                'priority': 6,
                'icon': 'refresh'
            })
        
        return suggestions
    
    async def _generate_project_suggestions(self, user_id: int, context: Dict) -> List[Dict]:
        """生成项目相关建议"""
        suggestions = []
        
        # 检查项目进度
        project_progress = context.get('project_progress', 0)
        if project_progress > 80:
            suggestions.append({
                'id': 'prepare_final_report',
                'type': 'milestone',
                'title': '准备最终报告',
                'description': '项目进度已达80%，建议开始准备最终研究报告',
                'action': 'open_report_generator',
                'priority': 9,
                'icon': 'report'
            })
        
        # 检查是否需要协作
        literature_count = context.get('literature_count', 0)
        if literature_count > 100 and context.get('collaborator_count', 0) == 0:
            suggestions.append({
                'id': 'invite_collaborators',
                'type': 'collaboration',
                'title': '邀请协作者',
                'description': '项目文献较多，建议邀请协作者共同处理',
                'action': 'open_collaboration_panel',
                'priority': 7,
                'icon': 'users'
            })
        
        return suggestions
    
    async def create_user_dashboard_widgets(self, user_id: int) -> List[Dict[str, Any]]:
        """创建个性化仪表板组件"""
        
        widgets = []
        
        try:
            user_interests = await self._get_user_interests(user_id)
            user_stats = await self._get_user_statistics(user_id)
            
            # 个人统计组件
            widgets.append({
                'id': 'personal_stats',
                'type': 'stats',
                'title': '个人统计',
                'size': 'medium',
                'data': {
                    'total_projects': user_stats['project_count'],
                    'total_literature': user_stats['literature_count'],
                    'this_month_activity': user_stats['monthly_activity'],
                    'efficiency_score': user_stats['efficiency_score']
                },
                'position': {'x': 0, 'y': 0, 'w': 6, 'h': 3}
            })
            
            # 推荐文献组件
            literature_recs = await self.recommend_literature(user_id, count=5)
            if literature_recs:
                widgets.append({
                    'id': 'recommended_literature',
                    'type': 'recommendations',
                    'title': '推荐文献',
                    'size': 'large',
                    'data': [
                        {
                            'id': rec.item_id,
                            'title': rec.title,
                            'description': rec.description,
                            'score': rec.relevance_score
                        } for rec in literature_recs
                    ],
                    'position': {'x': 6, 'y': 0, 'w': 6, 'h': 4}
                })
            
            # 研究趋势组件
            trends = await self._get_personalized_trends(user_interests)
            if trends:
                widgets.append({
                    'id': 'research_trends',
                    'type': 'trends',
                    'title': '研究趋势',
                    'size': 'medium',
                    'data': trends,
                    'position': {'x': 0, 'y': 3, 'w': 6, 'h': 3}
                })
            
            # 智能提示组件
            smart_tips = await self._generate_smart_tips(user_id, user_stats)
            if smart_tips:
                widgets.append({
                    'id': 'smart_tips',
                    'type': 'tips',
                    'title': '智能提示',
                    'size': 'small',
                    'data': smart_tips,
                    'position': {'x': 6, 'y': 4, 'w': 6, 'h': 2}
                })
            
        except Exception as e:
            logger.error(f"创建个性化组件失败: {e}")
        
        return widgets
    
    async def _get_user_statistics(self, user_id: int) -> Dict[str, Any]:
        """获取用户统计信息"""
        
        try:
            async with engine.begin() as conn:
                # 基础统计
                result = await conn.execute(text("""
                    SELECT 
                        COUNT(DISTINCT p.id) as project_count,
                        COUNT(DISTINCT l.id) as literature_count,
                        COUNT(DISTINCT CASE WHEN p.created_at >= NOW() - INTERVAL '30 days' THEN p.id END) as monthly_projects,
                        COUNT(DISTINCT CASE WHEN l.created_at >= NOW() - INTERVAL '30 days' THEN l.id END) as monthly_literature
                    FROM users u
                    LEFT JOIN projects p ON u.id = p.owner_id
                    LEFT JOIN literature l ON p.id = l.project_id
                    WHERE u.id = :user_id
                """), {"user_id": user_id})
                
                stats = dict(result.fetchone()._mapping)
                
                # 计算效率分数
                stats['efficiency_score'] = await self._calculate_efficiency_score(user_id)
                stats['monthly_activity'] = stats['monthly_projects'] + stats['monthly_literature']
                
                return stats
                
        except Exception as e:
            logger.error(f"获取用户统计失败: {e}")
            return {}
    
    async def _calculate_efficiency_score(self, user_id: int) -> float:
        """计算用户效率分数"""
        
        try:
            # 基于任务完成情况计算效率
            async with engine.begin() as conn:
                result = await conn.execute(text("""
                    SELECT 
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_tasks,
                        COUNT(*) as total_tasks,
                        AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_completion_time
                    FROM tasks t
                    JOIN projects p ON t.project_id = p.id
                    WHERE p.owner_id = :user_id
                    AND t.created_at >= NOW() - INTERVAL '30 days'
                """), {"user_id": user_id})
                
                data = result.fetchone()
                if data and data.total_tasks > 0:
                    completion_rate = data.completed_tasks / data.total_tasks
                    # 效率分数基于完成率和平均完成时间
                    time_factor = max(0.5, min(1.0, 3600 / (data.avg_completion_time or 3600)))
                    return min(1.0, completion_rate * 0.7 + time_factor * 0.3) * 100
                
        except Exception as e:
            logger.error(f"计算效率分数失败: {e}")
        
        return 75.0  # 默认分数
    
    async def personalize_interface(self, user_id: int) -> Dict[str, Any]:
        """个性化界面配置"""
        
        try:
            # 获取用户偏好
            preferences = await self._get_user_preferences(user_id)
            user_stats = await self._get_user_statistics(user_id)
            
            # 基于使用习惯调整界面
            interface_config = {
                'theme': preferences.get('theme', 'light'),
                'language': preferences.get('language', 'zh'),
                'density': preferences.get('density', 'comfortable'),
                'layout': await self._suggest_optimal_layout(user_stats),
                'shortcuts': await self._generate_personal_shortcuts(user_id),
                'widgets': await self.create_user_dashboard_widgets(user_id),
                'navigation': await self._customize_navigation(user_id, user_stats)
            }
            
            return interface_config
            
        except Exception as e:
            logger.error(f"个性化界面配置失败: {e}")
            return {}
    
    async def _suggest_optimal_layout(self, user_stats: Dict) -> Dict[str, Any]:
        """建议最优布局"""
        
        # 基于用户活动模式建议布局
        if user_stats.get('literature_count', 0) > 1000:
            return {
                'type': 'research_heavy',
                'sidebar_width': 'wide',
                'main_panels': ['literature_list', 'quick_analysis', 'batch_operations'],
                'secondary_panels': ['recommendations', 'trends']
            }
        elif user_stats.get('project_count', 0) > 10:
            return {
                'type': 'project_manager',
                'sidebar_width': 'normal',
                'main_panels': ['project_overview', 'task_management', 'collaboration'],
                'secondary_panels': ['statistics', 'notifications']
            }
        else:
            return {
                'type': 'beginner_friendly',
                'sidebar_width': 'normal',
                'main_panels': ['getting_started', 'simple_search', 'guided_analysis'],
                'secondary_panels': ['help', 'tutorials']
            }
    
    async def _generate_personal_shortcuts(self, user_id: int) -> List[Dict]:
        """生成个人快捷方式"""
        
        # 分析用户最常用的功能
        behavior_data = await self._get_recent_user_behavior(user_id, days=30)
        
        # 统计功能使用频率
        action_counts = Counter()
        for behavior in behavior_data:
            action = behavior.get('context', {}).get('action')
            if action:
                action_counts[action] += 1
        
        # 生成快捷方式
        shortcuts = []
        for action, count in action_counts.most_common(5):
            shortcuts.append({
                'action': action,
                'label': self._get_action_label(action),
                'icon': self._get_action_icon(action),
                'usage_count': count,
                'hotkey': self._suggest_hotkey(action)
            })
        
        return shortcuts

# 全局个性化引擎实例
personalization_engine = EnhancedPersonalizationEngine()