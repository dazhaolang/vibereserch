"""
会员服务管理 - 完整商业化会员体系
包括订阅管理、使用限制、升级建议、企业级功能
"""

import json
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from decimal import Decimal
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func

from app.core.config import settings
from app.models.user import User, UserMembership, MembershipType
from app.models.project import Project
from app.models.task import Task
from app.models.literature import Literature


class MembershipService:
    """会员服务管理"""
    
    def __init__(self, db: Session):
        self.db = db
        
        # 会员套餐配置
        self.membership_plans = {
            MembershipType.FREE: {
                "name": "免费版",
                "price": 0,
                "currency": "USD",
                "billing_cycle": "monthly",
                "features": {
                    "max_projects": 2,
                    "max_literature_per_project": 500,
                    "max_monthly_queries": 50,
                    "literature_sources": ["researchrabbit"],
                    "ai_screening": True,
                    "basic_analysis": True,
                    "export_formats": ["txt", "json"],
                    "support_level": "community",
                    "data_retention_days": 90
                },
                "limitations": [
                    "项目数量限制为2个",
                    "每个项目最多500篇文献",
                    "每月查询次数限制50次",
                    "仅支持基础文献源",
                    "数据保留90天"
                ]
            },
            MembershipType.PREMIUM: {
                "name": "专业版",
                "price": 49.99,
                "currency": "USD",
                "billing_cycle": "monthly",
                "features": {
                    "max_projects": 10,
                    "max_literature_per_project": 2000,
                    "max_monthly_queries": 500,
                    "literature_sources": ["researchrabbit"],
                    "ai_screening": True,
                    "advanced_analysis": True,
                    "experiment_design": True,
                    "innovation_discovery": True,
                    "export_formats": ["txt", "json", "pdf", "docx", "excel"],
                    "support_level": "email",
                    "data_retention_days": 365,
                    "api_access": True,
                    "collaboration_features": True,
                    "custom_templates": True
                },
                "limitations": [
                    "项目数量限制为10个",
                    "每个项目最多2000篇文献",
                    "每月查询次数限制500次"
                ]
            },
            MembershipType.ENTERPRISE: {
                "name": "企业版",
                "price": 199.99,
                "currency": "USD", 
                "billing_cycle": "monthly",
                "features": {
                    "max_projects": 100,
                    "max_literature_per_project": 10000,
                    "max_monthly_queries": 5000,
                    "literature_sources": ["researchrabbit"],
                    "ai_screening": True,
                    "advanced_analysis": True,
                    "experiment_design": True,
                    "innovation_discovery": True,
                    "trend_analysis": True,
                    "competitive_intelligence": True,
                    "export_formats": ["all"],
                    "support_level": "priority",
                    "data_retention_days": -1,  # 永久保留
                    "api_access": True,
                    "collaboration_features": True,
                    "custom_templates": True,
                    "white_label": True,
                    "dedicated_support": True,
                    "custom_integrations": True,
                    "advanced_security": True,
                    "audit_logs": True,
                    "sla_guarantee": "99.9%"
                },
                "limitations": []
            }
        }
        
        # 使用量追踪配置
        self.usage_tracking = {
            "literature_collection": {
                "unit": "篇",
                "reset_cycle": "monthly",
                "overage_policy": "block"  # block, charge, warn
            },
            "ai_queries": {
                "unit": "次",
                "reset_cycle": "monthly", 
                "overage_policy": "block"
            },
            "storage_space": {
                "unit": "GB",
                "reset_cycle": "never",
                "overage_policy": "charge"
            },
            "api_calls": {
                "unit": "次",
                "reset_cycle": "monthly",
                "overage_policy": "charge"
            }
        }
    
    async def check_usage_limits(
        self,
        user: User,
        action_type: str,
        requested_amount: int = 1
    ) -> Dict:
        """
        检查使用限制
        
        Args:
            user: 用户对象
            action_type: 操作类型 (literature_collection, ai_queries, etc.)
            requested_amount: 请求的使用量
            
        Returns:
            限制检查结果
        """
        try:
            # 获取用户会员信息
            membership = user.membership
            if not membership:
                # 创建默认免费会员
                membership = await self._create_default_membership(user)
            
            membership_type = membership.membership_type
            plan = self.membership_plans[membership_type]
            
            # 检查具体限制
            if action_type == "literature_collection":
                return await self._check_literature_limit(membership, plan, requested_amount)
            elif action_type == "ai_queries":
                return await self._check_query_limit(membership, plan, requested_amount)
            elif action_type == "project_creation":
                return await self._check_project_limit(membership, plan, requested_amount)
            else:
                return {"allowed": True, "message": "无限制"}
                
        except Exception as e:
            logger.error(f"检查使用限制失败: {e}")
            return {"allowed": False, "message": f"检查失败: {str(e)}"}
    
    async def record_usage(
        self,
        user: User,
        action_type: str,
        amount: int,
        metadata: Dict = None
    ):
        """
        记录使用量
        
        Args:
            user: 用户对象
            action_type: 操作类型
            amount: 使用量
            metadata: 额外元数据
        """
        try:
            membership = user.membership
            if not membership:
                return
            
            # 更新使用统计
            if action_type == "literature_collection":
                membership.monthly_literature_used += amount
            elif action_type == "ai_queries":
                membership.monthly_queries_used += amount
            
            self.db.commit()
            
            # 记录详细使用日志（如果需要）
            logger.info(f"用户 {user.username} 使用 {action_type}: {amount}")
            
        except Exception as e:
            logger.error(f"记录使用量失败: {e}")
            self.db.rollback()
    
    async def get_usage_statistics(self, user: User) -> Dict:
        """
        获取用户使用统计
        
        Args:
            user: 用户对象
            
        Returns:
            使用统计信息
        """
        try:
            membership = user.membership
            if not membership:
                return {"error": "未找到会员信息"}
            
            membership_type = membership.membership_type
            plan = self.membership_plans[membership_type]
            features = plan["features"]
            
            # 计算使用率
            literature_usage_rate = 0.0
            if features.get("max_literature_per_project", 0) > 0:
                # 计算所有项目的文献使用量
                total_literature_used = self.db.query(func.count(Literature.id)).join(
                    Literature.projects
                ).filter(Project.owner_id == user.id).scalar() or 0
                
                max_total_literature = features["max_literature_per_project"] * features.get("max_projects", 1)
                literature_usage_rate = min(total_literature_used / max_total_literature, 1.0) if max_total_literature > 0 else 0.0
            
            query_usage_rate = 0.0
            if features.get("max_monthly_queries", 0) > 0:
                query_usage_rate = membership.monthly_queries_used / features["max_monthly_queries"]
            
            # 获取项目统计
            user_projects = self.db.query(Project).filter(Project.owner_id == user.id).all()
            project_usage_rate = len(user_projects) / features.get("max_projects", 1) if features.get("max_projects", 1) > 0 else 0.0
            
            return {
                "membership_info": {
                    "type": membership_type.value,
                    "plan_name": plan["name"],
                    "subscription_start": membership.subscription_start.isoformat() if membership.subscription_start else None,
                    "subscription_end": membership.subscription_end.isoformat() if membership.subscription_end else None,
                    "auto_renewal": membership.auto_renewal
                },
                "usage_statistics": {
                    "projects": {
                        "used": len(user_projects),
                        "limit": features.get("max_projects", 0),
                        "usage_rate": round(project_usage_rate, 2)
                    },
                    "literature": {
                        "used_this_month": membership.monthly_literature_used,
                        "limit_per_project": features.get("max_literature_per_project", 0),
                        "usage_rate": round(literature_usage_rate, 2)
                    },
                    "queries": {
                        "used_this_month": membership.monthly_queries_used,
                        "monthly_limit": features.get("max_monthly_queries", 0),
                        "usage_rate": round(query_usage_rate, 2)
                    }
                },
                "feature_access": features,
                "limitations": plan.get("limitations", []),
                "upgrade_suggestions": await self._generate_upgrade_suggestions(
                    membership, literature_usage_rate, query_usage_rate, project_usage_rate
                )
            }
            
        except Exception as e:
            logger.error(f"获取使用统计失败: {e}")
            return {"error": str(e)}
    
    async def suggest_membership_upgrade(
        self,
        user: User,
        usage_pattern: Dict = None
    ) -> Dict:
        """
        建议会员升级
        
        Args:
            user: 用户对象
            usage_pattern: 使用模式分析
            
        Returns:
            升级建议
        """
        try:
            current_membership = user.membership
            if not current_membership:
                return {"suggestion": "建议注册会员"}
            
            current_type = current_membership.membership_type
            
            # 分析使用模式
            if usage_pattern is None:
                usage_pattern = await self._analyze_usage_pattern(user)
            
            # 生成升级建议
            upgrade_analysis = await self._analyze_upgrade_needs(
                current_type, usage_pattern
            )
            
            if upgrade_analysis["should_upgrade"]:
                recommended_plan = upgrade_analysis["recommended_plan"]
                
                return {
                    "should_upgrade": True,
                    "current_plan": current_type.value,
                    "recommended_plan": recommended_plan.value,
                    "upgrade_reasons": upgrade_analysis["reasons"],
                    "cost_benefit_analysis": await self._calculate_upgrade_benefits(
                        current_type, recommended_plan, usage_pattern
                    ),
                    "upgrade_incentives": await self._get_upgrade_incentives(
                        current_type, recommended_plan
                    )
                }
            else:
                return {
                    "should_upgrade": False,
                    "current_plan": current_type.value,
                    "satisfaction_reasons": upgrade_analysis["satisfaction_reasons"],
                    "optimization_suggestions": upgrade_analysis.get("optimization_suggestions", [])
                }
                
        except Exception as e:
            logger.error(f"生成升级建议失败: {e}")
            return {"should_upgrade": False, "error": str(e)}
    
    async def process_membership_upgrade(
        self,
        user: User,
        target_membership: MembershipType,
        payment_info: Dict = None
    ) -> Dict:
        """
        处理会员升级
        
        Args:
            user: 用户对象
            target_membership: 目标会员类型
            payment_info: 支付信息
            
        Returns:
            升级处理结果
        """
        try:
            logger.info(f"处理会员升级 - 用户: {user.username}, 目标: {target_membership.value}")
            
            current_membership = user.membership
            if not current_membership:
                current_membership = await self._create_default_membership(user)
            
            # 验证升级有效性
            if target_membership.value <= current_membership.membership_type.value:
                return {"success": False, "error": "无效的升级目标"}
            
            # 计算费用
            cost_calculation = await self._calculate_upgrade_cost(
                current_membership.membership_type, target_membership
            )
            
            # 模拟支付处理（实际应该集成支付网关）
            payment_result = await self._process_payment(
                user, cost_calculation, payment_info
            )
            
            if not payment_result["success"]:
                return {"success": False, "error": payment_result["error"]}
            
            # 更新会员信息
            old_type = current_membership.membership_type
            current_membership.membership_type = target_membership
            current_membership.subscription_start = datetime.utcnow()
            current_membership.subscription_end = datetime.utcnow() + timedelta(days=30)
            current_membership.auto_renewal = payment_info.get("auto_renewal", False) if payment_info else False
            
            # 重置使用统计
            current_membership.monthly_literature_used = 0
            current_membership.monthly_queries_used = 0
            
            self.db.commit()
            
            logger.info(f"会员升级成功 - {user.username}: {old_type.value} -> {target_membership.value}")
            
            return {
                "success": True,
                "upgrade_info": {
                    "from_plan": old_type.value,
                    "to_plan": target_membership.value,
                    "upgrade_date": datetime.utcnow().isoformat(),
                    "subscription_end": current_membership.subscription_end.isoformat(),
                    "cost": cost_calculation
                },
                "new_features": self._get_feature_differences(old_type, target_membership),
                "payment_info": payment_result
            }
            
        except Exception as e:
            logger.error(f"处理会员升级失败: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
    
    async def _create_default_membership(self, user: User) -> UserMembership:
        """创建默认会员"""
        try:
            membership = UserMembership(
                user_id=user.id,
                membership_type=MembershipType.FREE,
                monthly_literature_used=0,
                monthly_queries_used=0,
                total_projects=0,
                subscription_start=datetime.utcnow(),
                auto_renewal=False
            )
            
            self.db.add(membership)
            self.db.commit()
            
            # 刷新用户对象
            self.db.refresh(user)
            
            return membership
            
        except Exception as e:
            logger.error(f"创建默认会员失败: {e}")
            self.db.rollback()
            raise
    
    async def _check_literature_limit(
        self,
        membership: UserMembership,
        plan: Dict,
        requested_amount: int
    ) -> Dict:
        """检查文献采集限制"""
        try:
            max_per_project = plan["features"].get("max_literature_per_project", 0)
            
            if max_per_project == 0:
                return {"allowed": True, "message": "无限制"}
            
            if requested_amount <= max_per_project:
                return {
                    "allowed": True,
                    "message": f"允许采集{requested_amount}篇文献",
                    "remaining": max_per_project - requested_amount
                }
            else:
                return {
                    "allowed": False,
                    "message": f"超出限制：请求{requested_amount}篇，限制{max_per_project}篇",
                    "limit": max_per_project,
                    "upgrade_suggestion": await self._suggest_plan_for_amount(requested_amount, "literature")
                }
                
        except Exception as e:
            logger.error(f"检查文献限制失败: {e}")
            return {"allowed": False, "message": "检查失败"}
    
    async def _check_query_limit(
        self,
        membership: UserMembership,
        plan: Dict,
        requested_amount: int
    ) -> Dict:
        """检查查询限制"""
        try:
            monthly_limit = plan["features"].get("max_monthly_queries", 0)
            current_used = membership.monthly_queries_used
            
            if monthly_limit == 0:
                return {"allowed": True, "message": "无限制"}
            
            if current_used + requested_amount <= monthly_limit:
                return {
                    "allowed": True,
                    "message": f"允许查询{requested_amount}次",
                    "remaining": monthly_limit - current_used - requested_amount
                }
            else:
                return {
                    "allowed": False,
                    "message": f"超出月度限制：已使用{current_used}次，限制{monthly_limit}次",
                    "limit": monthly_limit,
                    "used": current_used,
                    "upgrade_suggestion": await self._suggest_plan_for_amount(
                        current_used + requested_amount, "queries"
                    )
                }
                
        except Exception as e:
            logger.error(f"检查查询限制失败: {e}")
            return {"allowed": False, "message": "检查失败"}
    
    async def _check_project_limit(
        self,
        membership: UserMembership,
        plan: Dict,
        requested_amount: int
    ) -> Dict:
        """检查项目创建限制"""
        try:
            max_projects = plan["features"].get("max_projects", 0)
            current_projects = membership.total_projects
            
            if max_projects == 0:
                return {"allowed": True, "message": "无限制"}
            
            if current_projects + requested_amount <= max_projects:
                return {
                    "allowed": True,
                    "message": f"允许创建{requested_amount}个项目",
                    "remaining": max_projects - current_projects - requested_amount
                }
            else:
                return {
                    "allowed": False,
                    "message": f"超出项目限制：已有{current_projects}个，限制{max_projects}个",
                    "limit": max_projects,
                    "used": current_projects,
                    "upgrade_suggestion": await self._suggest_plan_for_amount(
                        current_projects + requested_amount, "projects"
                    )
                }
                
        except Exception as e:
            logger.error(f"检查项目限制失败: {e}")
            return {"allowed": False, "message": "检查失败"}
    
    async def _suggest_plan_for_amount(self, required_amount: int, resource_type: str) -> Dict:
        """为所需资源量建议合适的套餐"""
        try:
            suitable_plans = []
            
            for membership_type, plan in self.membership_plans.items():
                features = plan["features"]
                
                if resource_type == "literature":
                    limit = features.get("max_literature_per_project", 0)
                elif resource_type == "queries":
                    limit = features.get("max_monthly_queries", 0)
                elif resource_type == "projects":
                    limit = features.get("max_projects", 0)
                else:
                    continue
                
                if limit == 0 or required_amount <= limit:
                    suitable_plans.append({
                        "membership_type": membership_type.value,
                        "plan_name": plan["name"],
                        "price": plan["price"],
                        "limit": limit,
                        "sufficient": True
                    })
            
            # 选择最经济的合适套餐
            if suitable_plans:
                recommended = min(suitable_plans, key=lambda x: x["price"])
                return {
                    "has_suggestion": True,
                    "recommended_plan": recommended,
                    "all_suitable_plans": suitable_plans
                }
            else:
                return {
                    "has_suggestion": False,
                    "message": "所需资源量超出所有套餐限制，请联系客服"
                }
                
        except Exception as e:
            logger.error(f"建议套餐失败: {e}")
            return {"has_suggestion": False}
    
    async def _analyze_usage_pattern(self, user: User) -> Dict:
        """分析用户使用模式"""
        try:
            # 获取用户项目和使用数据
            user_projects = self.db.query(Project).filter(Project.owner_id == user.id).all()
            
            # 计算平均文献使用量
            total_literature = 0
            for project in user_projects:
                project_literature_count = self.db.query(func.count(Literature.id)).join(
                    Literature.projects
                ).filter(Project.id == project.id).scalar() or 0
                total_literature += project_literature_count
            
            avg_literature_per_project = total_literature / len(user_projects) if user_projects else 0
            
            # 分析查询频率
            membership = user.membership
            monthly_queries = membership.monthly_queries_used if membership else 0
            
            # 分析使用时间模式
            recent_tasks = self.db.query(Task).join(Project).filter(
                Project.owner_id == user.id,
                Task.created_at >= datetime.utcnow() - timedelta(days=30)
            ).all()
            
            usage_pattern = {
                "total_projects": len(user_projects),
                "avg_literature_per_project": avg_literature_per_project,
                "monthly_queries": monthly_queries,
                "recent_task_count": len(recent_tasks),
                "usage_frequency": "high" if len(recent_tasks) > 10 else "medium" if len(recent_tasks) > 3 else "low",
                "project_complexity": "high" if avg_literature_per_project > 1000 else "medium" if avg_literature_per_project > 300 else "low"
            }
            
            return usage_pattern
            
        except Exception as e:
            logger.error(f"分析使用模式失败: {e}")
            return {"usage_frequency": "unknown"}
    
    async def _analyze_upgrade_needs(
        self,
        current_type: MembershipType,
        usage_pattern: Dict
    ) -> Dict:
        """分析升级需求"""
        try:
            current_plan = self.membership_plans[current_type]
            current_features = current_plan["features"]
            
            # 检查是否需要升级
            upgrade_reasons = []
            
            # 检查项目数量
            if usage_pattern.get("total_projects", 0) >= current_features.get("max_projects", 0) * 0.8:
                upgrade_reasons.append("项目数量接近限制")
            
            # 检查文献使用量
            if usage_pattern.get("avg_literature_per_project", 0) >= current_features.get("max_literature_per_project", 0) * 0.8:
                upgrade_reasons.append("文献使用量接近限制")
            
            # 检查查询频率
            if usage_pattern.get("monthly_queries", 0) >= current_features.get("max_monthly_queries", 0) * 0.8:
                upgrade_reasons.append("查询次数接近限制")
            
            # 检查使用频率
            if usage_pattern.get("usage_frequency") == "high" and current_type == MembershipType.FREE:
                upgrade_reasons.append("使用频率较高，建议升级获得更好体验")
            
            # 确定推荐的升级目标
            recommended_plan = current_type
            if current_type == MembershipType.FREE and upgrade_reasons:
                recommended_plan = MembershipType.PREMIUM
            elif current_type == MembershipType.PREMIUM and len(upgrade_reasons) >= 2:
                recommended_plan = MembershipType.ENTERPRISE
            
            should_upgrade = len(upgrade_reasons) > 0 and recommended_plan != current_type
            
            return {
                "should_upgrade": should_upgrade,
                "recommended_plan": recommended_plan,
                "reasons": upgrade_reasons,
                "satisfaction_reasons": [] if should_upgrade else ["当前套餐满足使用需求"],
                "optimization_suggestions": [
                    "优化项目结构，提高文献利用效率",
                    "合理安排查询时间，避免浪费配额"
                ] if not should_upgrade else []
            }
            
        except Exception as e:
            logger.error(f"分析升级需求失败: {e}")
            return {"should_upgrade": False}
    
    async def _calculate_upgrade_benefits(
        self,
        current_type: MembershipType,
        target_type: MembershipType,
        usage_pattern: Dict
    ) -> Dict:
        """计算升级收益"""
        try:
            current_plan = self.membership_plans[current_type]
            target_plan = self.membership_plans[target_type]
            
            cost_difference = target_plan["price"] - current_plan["price"]
            
            # 计算功能增益
            feature_benefits = []
            current_features = current_plan["features"]
            target_features = target_plan["features"]
            
            # 项目数量增益
            if target_features.get("max_projects", 0) > current_features.get("max_projects", 0):
                feature_benefits.append({
                    "feature": "项目数量",
                    "current": current_features.get("max_projects", 0),
                    "upgraded": target_features.get("max_projects", 0),
                    "benefit": f"可创建更多项目"
                })
            
            # 文献数量增益
            if target_features.get("max_literature_per_project", 0) > current_features.get("max_literature_per_project", 0):
                feature_benefits.append({
                    "feature": "文献数量",
                    "current": current_features.get("max_literature_per_project", 0),
                    "upgraded": target_features.get("max_literature_per_project", 0),
                    "benefit": "每个项目可处理更多文献"
                })
            
            # 查询次数增益
            if target_features.get("max_monthly_queries", 0) > current_features.get("max_monthly_queries", 0):
                feature_benefits.append({
                    "feature": "月度查询",
                    "current": current_features.get("max_monthly_queries", 0),
                    "upgraded": target_features.get("max_monthly_queries", 0),
                    "benefit": "更多的AI分析机会"
                })
            
            # 新功能
            new_features = []
            for feature, enabled in target_features.items():
                if enabled and not current_features.get(feature, False):
                    new_features.append(feature)
            
            return {
                "cost_difference": cost_difference,
                "feature_benefits": feature_benefits,
                "new_features": new_features,
                "estimated_value": cost_difference * 1.5,  # 简化的价值估算
                "roi_estimate": "positive" if len(feature_benefits) >= 2 else "neutral"
            }
            
        except Exception as e:
            logger.error(f"计算升级收益失败: {e}")
            return {"cost_difference": 0}
    
    async def _get_upgrade_incentives(
        self,
        current_type: MembershipType,
        target_type: MembershipType
    ) -> Dict:
        """获取升级激励"""
        try:
            incentives = {
                "discounts": [],
                "bonus_features": [],
                "limited_time_offers": [],
                "loyalty_rewards": []
            }
            
            # 首次升级优惠
            if current_type == MembershipType.FREE:
                incentives["discounts"].append({
                    "type": "首次升级优惠",
                    "discount": "20%",
                    "description": "首次升级到专业版享受20%折扣",
                    "valid_until": (datetime.utcnow() + timedelta(days=7)).isoformat()
                })
            
            # 年付优惠
            incentives["discounts"].append({
                "type": "年付优惠",
                "discount": "2个月免费",
                "description": "选择年付可享受2个月免费使用",
                "valid_until": None
            })
            
            # 功能预览
            target_plan = self.membership_plans[target_type]
            bonus_features = []
            for feature, enabled in target_plan["features"].items():
                if enabled and feature not in ["max_projects", "max_literature_per_project", "max_monthly_queries"]:
                    bonus_features.append(feature)
            
            incentives["bonus_features"] = bonus_features[:5]  # 限制数量
            
            return incentives
            
        except Exception as e:
            logger.error(f"获取升级激励失败: {e}")
            return {"discounts": [], "bonus_features": []}
    
    async def _process_payment(
        self,
        user: User,
        cost_calculation: Dict,
        payment_info: Dict
    ) -> Dict:
        """处理支付（模拟）"""
        try:
            # 这里应该集成真实的支付网关
            # 目前只是模拟支付成功
            
            payment_id = f"pay_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{user.id}"
            
            return {
                "success": True,
                "payment_id": payment_id,
                "amount": cost_calculation.get("cost_difference", 0),
                "currency": "USD",
                "payment_method": payment_info.get("method", "credit_card") if payment_info else "credit_card",
                "transaction_time": datetime.utcnow().isoformat(),
                "status": "completed"
            }
            
        except Exception as e:
            logger.error(f"处理支付失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _calculate_upgrade_cost(
        self,
        current_type: MembershipType,
        target_type: MembershipType
    ) -> Dict:
        """计算升级费用"""
        try:
            current_plan = self.membership_plans[current_type]
            target_plan = self.membership_plans[target_type]
            
            monthly_difference = target_plan["price"] - current_plan["price"]
            
            # 按比例计算（如果当前订阅还有剩余时间）
            prorated_cost = monthly_difference  # 简化计算
            
            return {
                "current_plan_price": current_plan["price"],
                "target_plan_price": target_plan["price"],
                "monthly_difference": monthly_difference,
                "prorated_cost": prorated_cost,
                "currency": target_plan["currency"],
                "billing_cycle": target_plan["billing_cycle"]
            }
            
        except Exception as e:
            logger.error(f"计算升级费用失败: {e}")
            return {"prorated_cost": 0}
    
    def _get_feature_differences(
        self,
        current_type: MembershipType,
        target_type: MembershipType
    ) -> Dict:
        """获取功能差异"""
        try:
            current_features = self.membership_plans[current_type]["features"]
            target_features = self.membership_plans[target_type]["features"]
            
            new_features = []
            enhanced_features = []
            
            for feature, value in target_features.items():
                if feature not in current_features:
                    new_features.append(feature)
                elif current_features[feature] != value:
                    if isinstance(value, (int, float)) and isinstance(current_features[feature], (int, float)):
                        if value > current_features[feature]:
                            enhanced_features.append({
                                "feature": feature,
                                "from": current_features[feature],
                                "to": value
                            })
                    elif value and not current_features[feature]:
                        new_features.append(feature)
            
            return {
                "new_features": new_features,
                "enhanced_features": enhanced_features
            }
            
        except Exception as e:
            logger.error(f"获取功能差异失败: {e}")
            return {"new_features": [], "enhanced_features": []}
    
    async def _generate_upgrade_suggestions(
        self,
        membership: UserMembership,
        literature_usage_rate: float,
        query_usage_rate: float,
        project_usage_rate: float
    ) -> List[str]:
        """生成升级建议"""
        try:
            suggestions = []
            
            # 基于使用率生成建议
            if literature_usage_rate > 0.8:
                suggestions.append("文献使用量较高，建议升级以获得更多文献配额")
            
            if query_usage_rate > 0.8:
                suggestions.append("查询次数接近限制，建议升级以获得更多查询配额")
            
            if project_usage_rate > 0.8:
                suggestions.append("项目数量接近限制，建议升级以创建更多项目")
            
            # 基于会员类型生成建议
            if membership.membership_type == MembershipType.FREE:
                if literature_usage_rate > 0.5 or query_usage_rate > 0.5:
                    suggestions.append("升级到专业版可享受更多功能和更高配额")
            
            if not suggestions:
                suggestions.append("当前套餐满足您的使用需求")
            
            return suggestions
            
        except Exception as e:
            logger.error(f"生成升级建议失败: {e}")
            return ["建议根据使用情况考虑升级"]
