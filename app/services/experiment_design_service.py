"""
实验方案设计服务 - 基于经验书生成具体实验参数和方案
提供智能实验设计、参数优化建议、风险评估
"""

import json
import asyncio
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.core.config import settings
from app.services.ai_service import AIService
from app.models.experience import ExperienceBook, MainExperience
from app.models.project import Project
from app.models.user import User
from app.models.literature import Literature, LiteratureSegment


class ExperimentDesignService:
    """实验方案设计服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.ai_service = AIService()
        
        # 实验设计模板
        self.experiment_templates = {
            "材料制备": {
                "name": "材料制备实验方案",
                "sections": {
                    "实验目标": {
                        "description": "明确实验目标和预期结果",
                        "fields": ["主要目标", "预期产物", "关键指标", "成功标准"]
                    },
                    "原料与设备": {
                        "description": "实验所需的原料和设备清单",
                        "fields": ["主要原料", "辅助材料", "实验设备", "安全防护"]
                    },
                    "实验步骤": {
                        "description": "详细的实验操作步骤",
                        "fields": ["预处理", "反应过程", "后处理", "产物分离"]
                    },
                    "工艺参数": {
                        "description": "关键工艺参数和控制条件",
                        "fields": ["温度", "压力", "时间", "气氛", "搅拌速度", "pH值"]
                    },
                    "表征方法": {
                        "description": "产物表征和性能测试方法",
                        "fields": ["结构表征", "形貌分析", "性能测试", "质量评估"]
                    },
                    "风险控制": {
                        "description": "实验风险识别和控制措施",
                        "fields": ["安全风险", "质量风险", "设备风险", "应急措施"]
                    }
                }
            },
            "性能测试": {
                "name": "性能测试实验方案",
                "sections": {
                    "测试目标": {
                        "description": "明确测试目标和评价指标",
                        "fields": ["测试目的", "关键指标", "评价标准", "对比基准"]
                    },
                    "样品准备": {
                        "description": "测试样品的制备和预处理",
                        "fields": ["样品制备", "预处理", "样品规格", "质量控制"]
                    },
                    "测试方法": {
                        "description": "具体的测试方法和程序",
                        "fields": ["测试设备", "测试条件", "操作步骤", "数据采集"]
                    },
                    "数据分析": {
                        "description": "数据处理和结果分析方法",
                        "fields": ["数据处理", "统计分析", "结果解释", "误差分析"]
                    }
                }
            },
            "机理研究": {
                "name": "机理研究实验方案",
                "sections": {
                    "研究目标": {
                        "description": "机理研究的目标和假设",
                        "fields": ["研究目标", "科学假设", "关键问题", "预期发现"]
                    },
                    "实验设计": {
                        "description": "机理验证的实验设计",
                        "fields": ["对照实验", "变量控制", "实验组合", "重复性验证"]
                    },
                    "检测手段": {
                        "description": "机理研究的检测和分析手段",
                        "fields": ["原位检测", "光谱分析", "显微观察", "电化学测试"]
                    },
                    "理论分析": {
                        "description": "理论计算和模拟分析",
                        "fields": ["计算方法", "模型建立", "参数设置", "结果验证"]
                    }
                }
            }
        }
        
        # 参数优化策略
        self.optimization_strategies = {
            "单因素优化": {
                "description": "逐一优化各个实验参数",
                "适用场景": "参数较少，相互影响较小",
                "优点": ["简单易行", "结果明确", "成本较低"],
                "缺点": ["无法考虑交互作用", "可能错过最优组合"]
            },
            "正交设计": {
                "description": "使用正交表安排实验",
                "适用场景": "多因素多水平优化",
                "优点": ["实验次数少", "能分析交互作用", "统计分析完整"],
                "缺点": ["设计较复杂", "需要统计知识"]
            },
            "响应面设计": {
                "description": "建立数学模型进行优化",
                "适用场景": "连续变量优化，需要预测模型",
                "优点": ["能建立预测模型", "优化效果好", "可视化强"],
                "缺点": ["实验设计复杂", "计算量大"]
            },
            "遗传算法": {
                "description": "使用智能算法进行全局优化",
                "适用场景": "复杂多目标优化",
                "优点": ["全局搜索能力强", "适用复杂问题"],
                "缺点": ["需要大量实验", "算法复杂"]
            }
        }
    
    async def design_experiment_scheme(
        self,
        project: Project,
        research_question: str,
        experiment_type: str = "材料制备",
        use_main_experience: bool = True,
        progress_callback = None
    ) -> Dict:
        """
        设计实验方案
        
        Args:
            project: 项目对象
            research_question: 研究问题
            experiment_type: 实验类型
            use_main_experience: 是否使用主经验
            progress_callback: 进度回调函数
            
        Returns:
            实验方案设计结果
        """
        try:
            logger.info(f"开始设计实验方案 - 项目: {project.name}, 问题: {research_question}")
            
            if progress_callback:
                await progress_callback("获取经验知识", 10, {"experiment_type": experiment_type})
            
            # 第一步：获取相关经验知识
            experience_data = await self._get_relevant_experience(
                project, research_question, use_main_experience
            )
            
            if progress_callback:
                await progress_callback("分析实验需求", 25, {})
            
            # 第二步：分析实验需求
            experiment_requirements = await self._analyze_experiment_requirements(
                research_question, experiment_type, experience_data
            )
            
            if progress_callback:
                await progress_callback("生成实验方案", 50, {})
            
            # 第三步：生成详细实验方案
            detailed_scheme = await self._generate_detailed_scheme(
                experiment_requirements, experiment_type, experience_data
            )
            
            if progress_callback:
                await progress_callback("参数优化建议", 70, {})
            
            # 第四步：生成参数优化建议
            optimization_suggestions = await self._generate_optimization_suggestions(
                detailed_scheme, experiment_requirements
            )
            
            if progress_callback:
                await progress_callback("风险评估", 85, {})
            
            # 第五步：风险评估和安全建议
            risk_assessment = await self._conduct_risk_assessment(
                detailed_scheme, experiment_type
            )
            
            if progress_callback:
                await progress_callback("方案完成", 100, {})
            
            # 第六步：整合最终方案
            final_scheme = {
                "success": True,
                "experiment_info": {
                    "research_question": research_question,
                    "experiment_type": experiment_type,
                    "project_id": project.id,
                    "generated_at": datetime.utcnow().isoformat()
                },
                "requirements_analysis": experiment_requirements,
                "detailed_scheme": detailed_scheme,
                "optimization_suggestions": optimization_suggestions,
                "risk_assessment": risk_assessment,
                "experience_sources": {
                    "main_experiences_used": len(experience_data.get("main_experiences", [])),
                    "experience_books_used": len(experience_data.get("experience_books", [])),
                    "literature_segments_used": len(experience_data.get("literature_segments", []))
                }
            }
            
            return final_scheme
            
        except Exception as e:
            logger.error(f"实验方案设计失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def optimize_experiment_parameters(
        self,
        project: Project,
        base_scheme: Dict,
        optimization_objectives: List[str],
        constraints: Dict = None,
        progress_callback = None
    ) -> Dict:
        """
        优化实验参数
        
        Args:
            project: 项目对象
            base_scheme: 基础实验方案
            optimization_objectives: 优化目标列表
            constraints: 约束条件
            progress_callback: 进度回调函数
            
        Returns:
            参数优化结果
        """
        try:
            logger.info(f"开始优化实验参数 - 项目: {project.name}")
            
            if progress_callback:
                await progress_callback("分析优化目标", 15, {"objectives": optimization_objectives})
            
            # 第一步：分析优化目标和约束
            optimization_analysis = await self._analyze_optimization_objectives(
                base_scheme, optimization_objectives, constraints
            )
            
            if progress_callback:
                await progress_callback("选择优化策略", 30, {})
            
            # 第二步：选择合适的优化策略
            optimization_strategy = await self._select_optimization_strategy(
                optimization_analysis, base_scheme
            )
            
            if progress_callback:
                await progress_callback("生成实验设计", 55, {})
            
            # 第三步：生成优化实验设计
            optimization_design = await self._generate_optimization_design(
                base_scheme, optimization_strategy, optimization_analysis
            )
            
            if progress_callback:
                await progress_callback("预测优化效果", 75, {})
            
            # 第四步：预测优化效果
            effect_prediction = await self._predict_optimization_effects(
                optimization_design, base_scheme
            )
            
            if progress_callback:
                await progress_callback("生成实施计划", 90, {})
            
            # 第五步：生成实施计划
            implementation_plan = await self._generate_implementation_plan(
                optimization_design, optimization_strategy
            )
            
            if progress_callback:
                await progress_callback("优化完成", 100, {})
            
            return {
                "success": True,
                "optimization_analysis": optimization_analysis,
                "selected_strategy": optimization_strategy,
                "optimization_design": optimization_design,
                "effect_prediction": effect_prediction,
                "implementation_plan": implementation_plan,
                "estimated_experiments": optimization_design.get("total_experiments", 0),
                "estimated_duration": implementation_plan.get("estimated_duration", "未知")
            }
            
        except Exception as e:
            logger.error(f"实验参数优化失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def generate_experimental_protocol(
        self,
        experiment_scheme: Dict,
        detail_level: str = "detailed"  # basic, detailed, expert
    ) -> Dict:
        """
        生成实验操作规程
        
        Args:
            experiment_scheme: 实验方案
            detail_level: 详细程度
            
        Returns:
            实验操作规程
        """
        try:
            logger.info(f"生成实验操作规程 - 详细程度: {detail_level}")
            
            protocol_prompt = f"""
基于以下实验方案，生成{detail_level}级别的实验操作规程：

实验方案:
{json.dumps(experiment_scheme.get('detailed_scheme', {}), ensure_ascii=False, indent=2)}

请生成实验操作规程，以JSON格式返回：
{{
    "protocol_info": {{
        "title": "实验操作规程标题",
        "version": "1.0",
        "detail_level": "{detail_level}",
        "estimated_duration": "预估实验时间"
    }},
    "safety_precautions": [
        "安全注意事项1",
        "安全注意事项2"
    ],
    "materials_and_equipment": {{
        "chemicals": [
            {{"name": "化学品名称", "purity": "纯度", "amount": "用量", "supplier": "供应商"}}
        ],
        "equipment": [
            {{"name": "设备名称", "model": "型号", "specifications": "规格要求"}}
        ],
        "consumables": ["消耗品1", "消耗品2"]
    }},
    "experimental_procedure": [
        {{
            "step": 1,
            "title": "步骤标题",
            "description": "详细描述",
            "parameters": {{"温度": "25°C", "时间": "2小时"}},
            "precautions": ["注意事项1"],
            "expected_result": "预期结果"
        }}
    ],
    "data_recording": {{
        "parameters_to_record": ["参数1", "参数2"],
        "observation_points": ["观察要点1", "观察要点2"],
        "measurement_methods": ["测量方法1", "测量方法2"]
    }},
    "troubleshooting": [
        {{
            "problem": "可能问题",
            "causes": ["原因1", "原因2"],
            "solutions": ["解决方案1", "解决方案2"]
        }}
    ]
}}

要求：
- 根据detail_level调整详细程度
- basic: 基本步骤和关键参数
- detailed: 详细操作和注意事项  
- expert: 专家级别的深度指导
- 确保操作的可重现性
- 包含安全和质量控制要求
"""
            
            response = await self.ai_service.generate_completion(
                protocol_prompt,
                model="gpt-4",
                max_tokens=2500,
                temperature=0.2
            )
            
            if response.get("success"):
                try:
                    protocol = json.loads(response["content"])
                    return {
                        "success": True,
                        "protocol": protocol,
                        "generated_at": datetime.utcnow().isoformat()
                    }
                except json.JSONDecodeError:
                    pass
            
            return {"success": False, "error": "操作规程生成失败"}
            
        except Exception as e:
            logger.error(f"生成实验操作规程失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_relevant_experience(
        self,
        project: Project,
        research_question: str,
        use_main_experience: bool
    ) -> Dict:
        """获取相关经验知识"""
        try:
            experience_data = {
                "main_experiences": [],
                "experience_books": [],
                "literature_segments": []
            }
            
            if use_main_experience:
                # 获取主经验
                main_experiences = self.db.query(MainExperience).filter(
                    MainExperience.project_id == project.id,
                    MainExperience.status == "active"
                ).all()
                
                for exp in main_experiences:
                    experience_data["main_experiences"].append({
                        "type": exp.experience_type,
                        "content": exp.content,
                        "methodology_summary": exp.methodology_summary,
                        "key_findings": exp.key_findings,
                        "practical_guidelines": exp.practical_guidelines
                    })
            
            # 获取相关经验书
            experience_books = self.db.query(ExperienceBook).filter(
                ExperienceBook.project_id == project.id,
                ExperienceBook.status == "completed"
            ).order_by(desc(ExperienceBook.quality_score)).limit(3).all()
            
            for book in experience_books:
                experience_data["experience_books"].append({
                    "title": book.title,
                    "content": book.content,
                    "research_question": book.research_question,
                    "quality_score": book.quality_score
                })
            
            # 获取相关文献段落（基于关键词匹配）
            project_keywords = project.keywords or []
            if project_keywords:
                # 简化的关键词匹配查询
                relevant_segments = self.db.query(LiteratureSegment).filter(
                    LiteratureSegment.project_id == project.id
                ).limit(10).all()  # 简化查询，实际应该基于关键词匹配
                
                for segment in relevant_segments:
                    experience_data["literature_segments"].append({
                        "content": segment.content,
                        "segment_type": segment.segment_type,
                        "structured_data": segment.structured_data
                    })
            
            return experience_data
            
        except Exception as e:
            logger.error(f"获取相关经验失败: {e}")
            return {"main_experiences": [], "experience_books": [], "literature_segments": []}
    
    async def _analyze_experiment_requirements(
        self,
        research_question: str,
        experiment_type: str,
        experience_data: Dict
    ) -> Dict:
        """分析实验需求"""
        try:
            analysis_prompt = f"""
基于研究问题和经验知识，分析实验需求：

研究问题: {research_question}
实验类型: {experiment_type}

相关经验知识:
主经验数量: {len(experience_data.get('main_experiences', []))}
经验书数量: {len(experience_data.get('experience_books', []))}
文献段落数量: {len(experience_data.get('literature_segments', []))}

经验内容摘要:
{json.dumps(experience_data, ensure_ascii=False, indent=2)[:2000]}

请分析实验需求并以JSON格式返回：
{{
    "research_objectives": ["具体研究目标1", "具体研究目标2"],
    "key_variables": [
        {{"name": "变量名", "type": "independent/dependent", "range": "变化范围", "importance": "high/medium/low"}}
    ],
    "required_equipment": ["设备1", "设备2"],
    "required_materials": ["材料1", "材料2"],
    "critical_parameters": [
        {{"parameter": "参数名", "typical_range": "典型范围", "control_precision": "控制精度"}}
    ],
    "expected_outcomes": ["预期结果1", "预期结果2"],
    "technical_challenges": ["技术挑战1", "技术挑战2"],
    "success_criteria": ["成功标准1", "成功标准2"],
    "complexity_level": "low/medium/high",
    "estimated_duration": "预估时间"
}}

要求：
- 基于经验知识进行分析
- 考虑实际可行性
- 识别关键技术难点
"""
            
            response = await self.ai_service.generate_completion(
                analysis_prompt,
                model="gpt-4",
                max_tokens=1200,
                temperature=0.3
            )
            
            if response.get("success"):
                try:
                    return json.loads(response["content"])
                except json.JSONDecodeError:
                    pass
            
            # 默认需求分析
            return {
                "research_objectives": [research_question],
                "complexity_level": "medium",
                "estimated_duration": "未知"
            }
            
        except Exception as e:
            logger.error(f"分析实验需求失败: {e}")
            return {"research_objectives": [research_question]}
    
    async def _generate_detailed_scheme(
        self,
        requirements: Dict,
        experiment_type: str,
        experience_data: Dict
    ) -> Dict:
        """生成详细实验方案"""
        try:
            template = self.experiment_templates.get(experiment_type, self.experiment_templates["材料制备"])
            
            scheme_prompt = f"""
基于实验需求和模板，生成详细的实验方案：

实验需求:
{json.dumps(requirements, ensure_ascii=False, indent=2)}

实验模板:
{json.dumps(template, ensure_ascii=False, indent=2)}

经验知识摘要:
{json.dumps(experience_data, ensure_ascii=False, indent=2)[:1500]}

请生成详细实验方案，以JSON格式返回：
{{
    "scheme_overview": {{
        "title": "实验方案标题",
        "objective": "实验目标",
        "approach": "实验方法",
        "innovation_points": ["创新点1", "创新点2"]
    }},
    "detailed_sections": {{
        "section_name": {{
            "description": "部分描述",
            "content": {{
                "field1": "详细内容1",
                "field2": "详细内容2"
            }},
            "key_points": ["要点1", "要点2"],
            "references": ["参考来源1", "参考来源2"]
        }}
    }},
    "experimental_workflow": [
        {{
            "phase": "阶段名称",
            "steps": ["步骤1", "步骤2"],
            "duration": "预估时间",
            "critical_points": ["关键点1", "关键点2"]
        }}
    ],
    "quality_control": {{
        "monitoring_parameters": ["监控参数1", "监控参数2"],
        "quality_standards": ["质量标准1", "质量标准2"],
        "control_measures": ["控制措施1", "控制措施2"]
    }}
}}

要求：
- 基于模板结构生成内容
- 结合经验知识提供具体指导
- 确保方案的科学性和可行性
- 突出创新点和关键技术
"""
            
            response = await self.ai_service.generate_completion(
                scheme_prompt,
                model="gpt-4",
                max_tokens=2000,
                temperature=0.3
            )
            
            if response.get("success"):
                try:
                    return json.loads(response["content"])
                except json.JSONDecodeError:
                    pass
            
            # 默认方案
            return {
                "scheme_overview": {
                    "title": f"{experiment_type}实验方案",
                    "objective": requirements.get("research_objectives", ["实验目标"])[0]
                },
                "detailed_sections": {},
                "experimental_workflow": [],
                "quality_control": {}
            }
            
        except Exception as e:
            logger.error(f"生成详细实验方案失败: {e}")
            return {"scheme_overview": {"title": "实验方案"}}
    
    async def _generate_optimization_suggestions(
        self,
        detailed_scheme: Dict,
        requirements: Dict
    ) -> Dict:
        """生成参数优化建议"""
        try:
            optimization_prompt = f"""
基于实验方案和需求，生成参数优化建议：

实验方案:
{json.dumps(detailed_scheme, ensure_ascii=False, indent=2)[:1500]}

实验需求:
{json.dumps(requirements, ensure_ascii=False, indent=2)}

请生成优化建议并以JSON格式返回：
{{
    "optimization_targets": [
        {{"parameter": "参数名", "current_value": "当前值", "optimization_direction": "increase/decrease/optimize", "priority": "high/medium/low"}}
    ],
    "optimization_strategies": [
        {{
            "strategy_name": "优化策略名称",
            "description": "策略描述",
            "applicable_parameters": ["适用参数1", "适用参数2"],
            "advantages": ["优点1", "优点2"],
            "limitations": ["限制1", "限制2"],
            "recommended_conditions": "推荐使用条件"
        }}
    ],
    "parameter_interactions": [
        {{
            "parameters": ["参数1", "参数2"],
            "interaction_type": "synergistic/antagonistic/independent",
            "description": "交互作用描述",
            "optimization_advice": "优化建议"
        }}
    ],
    "optimization_sequence": [
        {{
            "step": 1,
            "parameters": ["首先优化的参数"],
            "reason": "优化原因",
            "expected_improvement": "预期改进"
        }}
    ],
    "success_indicators": ["成功指标1", "成功指标2"]
}}

要求：
- 识别关键优化参数
- 考虑参数间相互作用
- 提供可行的优化策略
- 给出优化顺序建议
"""
            
            response = await self.ai_service.generate_completion(
                optimization_prompt,
                model="gpt-4",
                max_tokens=1500,
                temperature=0.3
            )
            
            if response.get("success"):
                try:
                    return json.loads(response["content"])
                except json.JSONDecodeError:
                    pass
            
            # 默认优化建议
            return {
                "optimization_targets": [],
                "optimization_strategies": [],
                "parameter_interactions": [],
                "optimization_sequence": []
            }
            
        except Exception as e:
            logger.error(f"生成优化建议失败: {e}")
            return {"optimization_targets": []}
    
    async def _conduct_risk_assessment(
        self,
        detailed_scheme: Dict,
        experiment_type: str
    ) -> Dict:
        """进行风险评估"""
        try:
            risk_prompt = f"""
对以下实验方案进行风险评估：

实验类型: {experiment_type}
实验方案:
{json.dumps(detailed_scheme, ensure_ascii=False, indent=2)[:1500]}

请进行风险评估并以JSON格式返回：
{{
    "safety_risks": [
        {{
            "risk_type": "安全风险类型",
            "description": "风险描述",
            "severity": "high/medium/low",
            "probability": "high/medium/low",
            "mitigation_measures": ["缓解措施1", "缓解措施2"],
            "emergency_procedures": ["应急程序1", "应急程序2"]
        }}
    ],
    "technical_risks": [
        {{
            "risk_type": "技术风险类型",
            "description": "风险描述",
            "impact": "对实验结果的影响",
            "prevention_methods": ["预防方法1", "预防方法2"],
            "contingency_plans": ["应急方案1", "应急方案2"]
        }}
    ],
    "quality_risks": [
        {{
            "risk_type": "质量风险类型",
            "description": "风险描述",
            "quality_impact": "对产品质量的影响",
            "control_measures": ["控制措施1", "控制措施2"]
        }}
    ],
    "resource_risks": [
        {{
            "risk_type": "资源风险类型",
            "description": "风险描述",
            "resource_impact": "对资源需求的影响",
            "backup_plans": ["备用方案1", "备用方案2"]
        }}
    ],
    "overall_risk_level": "high/medium/low",
    "critical_control_points": ["关键控制点1", "关键控制点2"],
    "monitoring_requirements": ["监控要求1", "监控要求2"]
}}

要求：
- 全面识别各类风险
- 评估风险等级和影响
- 提供具体的控制措施
- 制定应急预案
"""
            
            response = await self.ai_service.generate_completion(
                risk_prompt,
                model="gpt-4",
                max_tokens=1500,
                temperature=0.2
            )
            
            if response.get("success"):
                try:
                    return json.loads(response["content"])
                except json.JSONDecodeError:
                    pass
            
            # 默认风险评估
            return {
                "safety_risks": [],
                "technical_risks": [],
                "quality_risks": [],
                "resource_risks": [],
                "overall_risk_level": "medium"
            }
            
        except Exception as e:
            logger.error(f"风险评估失败: {e}")
            return {"overall_risk_level": "unknown"}
    
    async def _analyze_optimization_objectives(
        self,
        base_scheme: Dict,
        objectives: List[str],
        constraints: Dict
    ) -> Dict:
        """分析优化目标"""
        try:
            analysis_prompt = f"""
分析实验优化目标和约束条件：

基础方案:
{json.dumps(base_scheme, ensure_ascii=False, indent=2)[:1000]}

优化目标:
{objectives}

约束条件:
{json.dumps(constraints or {}, ensure_ascii=False, indent=2)}

请分析并以JSON格式返回：
{{
    "objective_analysis": [
        {{
            "objective": "目标名称",
            "type": "maximize/minimize/target",
            "measurable_parameters": ["可测量参数1", "可测量参数2"],
            "priority": "high/medium/low",
            "feasibility": "high/medium/low",
            "complexity": "high/medium/low"
        }}
    ],
    "constraint_analysis": [
        {{
            "constraint": "约束名称",
            "type": "hard/soft",
            "impact_level": "high/medium/low",
            "flexibility": "rigid/flexible"
        }}
    ],
    "optimization_complexity": "low/medium/high",
    "recommended_approach": "推荐的优化方法",
    "expected_challenges": ["预期挑战1", "预期挑战2"]
}}
"""
            
            response = await self.ai_service.generate_completion(
                analysis_prompt,
                model="gpt-4",
                max_tokens=800,
                temperature=0.2
            )
            
            if response.get("success"):
                try:
                    return json.loads(response["content"])
                except json.JSONDecodeError:
                    pass
            
            return {"optimization_complexity": "medium"}
            
        except Exception as e:
            logger.error(f"分析优化目标失败: {e}")
            return {"optimization_complexity": "unknown"}
    
    async def _select_optimization_strategy(
        self,
        optimization_analysis: Dict,
        base_scheme: Dict
    ) -> Dict:
        """选择优化策略"""
        try:
            complexity = optimization_analysis.get("optimization_complexity", "medium")
            
            # 基于复杂度选择策略
            if complexity == "low":
                recommended_strategy = "单因素优化"
            elif complexity == "high":
                recommended_strategy = "遗传算法"
            else:
                recommended_strategy = "正交设计"
            
            strategy_info = self.optimization_strategies.get(
                recommended_strategy, 
                self.optimization_strategies["正交设计"]
            )
            
            return {
                "strategy_name": recommended_strategy,
                "strategy_info": strategy_info,
                "selection_reason": f"基于优化复杂度({complexity})选择",
                "alternative_strategies": list(self.optimization_strategies.keys())
            }
            
        except Exception as e:
            logger.error(f"选择优化策略失败: {e}")
            return {"strategy_name": "正交设计"}
    
    async def _generate_optimization_design(
        self,
        base_scheme: Dict,
        strategy: Dict,
        analysis: Dict
    ) -> Dict:
        """生成优化实验设计"""
        try:
            design_prompt = f"""
基于优化策略生成实验设计：

基础方案:
{json.dumps(base_scheme, ensure_ascii=False, indent=2)[:800]}

优化策略: {strategy.get('strategy_name', '正交设计')}
分析结果:
{json.dumps(analysis, ensure_ascii=False, indent=2)}

请生成优化实验设计并以JSON格式返回：
{{
    "design_overview": {{
        "strategy": "优化策略",
        "total_experiments": 16,
        "estimated_duration": "预估总时间",
        "resource_requirements": "资源需求"
    }},
    "experimental_matrix": [
        {{
            "experiment_id": "E1",
            "parameters": {{"参数1": "值1", "参数2": "值2"}},
            "expected_outcome": "预期结果",
            "priority": "high/medium/low"
        }}
    ],
    "measurement_plan": {{
        "response_variables": ["响应变量1", "响应变量2"],
        "measurement_methods": ["测量方法1", "测量方法2"],
        "data_analysis_plan": "数据分析计划"
    }},
    "execution_sequence": [
        {{
            "batch": 1,
            "experiments": ["E1", "E2", "E3"],
            "duration": "批次时间",
            "preparation": "准备工作"
        }}
    ]
}}
"""
            
            response = await self.ai_service.generate_completion(
                design_prompt,
                model="gpt-4",
                max_tokens=1200,
                temperature=0.3
            )
            
            if response.get("success"):
                try:
                    return json.loads(response["content"])
                except json.JSONDecodeError:
                    pass
            
            return {"design_overview": {"total_experiments": 9}}
            
        except Exception as e:
            logger.error(f"生成优化设计失败: {e}")
            return {"design_overview": {"total_experiments": 0}}
    
    async def _predict_optimization_effects(
        self,
        optimization_design: Dict,
        base_scheme: Dict
    ) -> Dict:
        """预测优化效果"""
        try:
            prediction_prompt = f"""
基于优化设计预测优化效果：

优化设计:
{json.dumps(optimization_design, ensure_ascii=False, indent=2)[:1000]}

基础方案:
{json.dumps(base_scheme, ensure_ascii=False, indent=2)[:800]}

请预测优化效果并以JSON格式返回：
{{
    "performance_predictions": [
        {{
            "metric": "性能指标",
            "baseline_value": "基线值",
            "predicted_improvement": "预期改进",
            "confidence_level": "high/medium/low",
            "improvement_percentage": 15.5
        }}
    ],
    "optimization_timeline": [
        {{
            "phase": "优化阶段",
            "duration": "持续时间",
            "expected_progress": "预期进展",
            "milestones": ["里程碑1", "里程碑2"]
        }}
    ],
    "resource_investment": {{
        "time_investment": "时间投入",
        "material_costs": "材料成本",
        "equipment_usage": "设备使用",
        "personnel_effort": "人员投入"
    }},
    "success_probability": {{
        "overall_success": 0.85,
        "partial_success": 0.95,
        "failure_risk": 0.05,
        "risk_factors": ["风险因素1", "风险因素2"]
    }},
    "recommendations": ["建议1", "建议2"]
}}
"""
            
            response = await self.ai_service.generate_completion(
                prediction_prompt,
                model="gpt-4",
                max_tokens=1000,
                temperature=0.3
            )
            
            if response.get("success"):
                try:
                    return json.loads(response["content"])
                except json.JSONDecodeError:
                    pass
            
            return {"success_probability": {"overall_success": 0.7}}
            
        except Exception as e:
            logger.error(f"预测优化效果失败: {e}")
            return {"success_probability": {"overall_success": 0.5}}
    
    async def _generate_implementation_plan(
        self,
        optimization_design: Dict,
        strategy: Dict
    ) -> Dict:
        """生成实施计划"""
        try:
            total_experiments = optimization_design.get("design_overview", {}).get("total_experiments", 0)
            
            # 简单的实施计划生成
            phases = []
            experiments_per_phase = max(3, total_experiments // 3)
            
            for i in range(0, total_experiments, experiments_per_phase):
                phase_experiments = min(experiments_per_phase, total_experiments - i)
                phases.append({
                    "phase": f"第{len(phases) + 1}阶段",
                    "experiments_count": phase_experiments,
                    "estimated_duration": f"{phase_experiments * 2}天",
                    "objectives": [f"完成{phase_experiments}个优化实验"],
                    "deliverables": ["实验数据", "阶段性分析报告"]
                })
            
            return {
                "implementation_phases": phases,
                "total_duration": f"{total_experiments * 2}天",
                "resource_allocation": {
                    "personnel": "1-2名研究人员",
                    "equipment_time": f"{total_experiments * 4}小时",
                    "materials": "根据实验设计准备"
                },
                "quality_checkpoints": [
                    "每阶段结束后数据审查",
                    "中期结果评估",
                    "最终优化效果验证"
                ],
                "risk_mitigation": [
                    "预备额外实验时间",
                    "准备备用材料",
                    "建立数据备份机制"
                ]
            }
            
        except Exception as e:
            logger.error(f"生成实施计划失败: {e}")
            return {"total_duration": "未知"}