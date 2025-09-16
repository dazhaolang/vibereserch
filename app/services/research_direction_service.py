"""
研究方向确定服务 - 智能化研究方向识别与确定
支持对话式交互、文件上传辅助、预设菜单选择
"""

import json
import asyncio
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.ai_service import AIService
from app.services.file_upload_service import FileUploadService
from app.models.user import User
from app.models.project import Project


class ResearchDirectionService:
    """研究方向确定服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.ai_service = AIService()
        self.file_upload_service = FileUploadService(db)
        
        # 预设学科分类体系
        self.discipline_hierarchy = {
            "化学": {
                "有机化学": {
                    "合成化学": ["有机合成", "药物合成", "天然产物合成", "催化合成"],
                    "结构化学": ["分子结构", "立体化学", "构效关系", "分子设计"],
                    "机理研究": ["反应机理", "催化机理", "动力学", "热力学"]
                },
                "无机化学": {
                    "配位化学": ["配合物", "金属有机", "配位聚合物", "分子磁性"],
                    "固体化学": ["晶体结构", "相变", "固体反应", "缺陷化学"],
                    "纳米化学": ["纳米材料", "纳米合成", "表面化学", "界面化学"]
                },
                "物理化学": {
                    "电化学": ["电池", "电催化", "腐蚀", "电解"],
                    "光化学": ["光催化", "光电转换", "荧光", "激光化学"],
                    "表面化学": ["吸附", "催化", "薄膜", "界面"]
                },
                "分析化学": {
                    "仪器分析": ["光谱", "色谱", "质谱", "电分析"],
                    "分离科学": ["萃取", "膜分离", "色谱分离", "结晶"],
                    "传感器": ["化学传感器", "生物传感器", "光学传感器", "电化学传感器"]
                }
            },
            "材料科学": {
                "金属材料": {
                    "结构材料": ["钢铁", "有色金属", "合金设计", "热处理"],
                    "功能材料": ["形状记忆", "超导材料", "磁性材料", "储氢材料"],
                    "表面工程": ["涂层", "表面改性", "腐蚀防护", "摩擦学"]
                },
                "无机非金属材料": {
                    "陶瓷材料": ["结构陶瓷", "功能陶瓷", "生物陶瓷", "陶瓷基复合材料"],
                    "玻璃材料": ["光学玻璃", "特种玻璃", "玻璃陶瓷", "纤维光学"],
                    "耐火材料": ["高温材料", "保温材料", "抗热震材料", "超高温陶瓷"]
                },
                "高分子材料": {
                    "聚合物合成": ["聚合反应", "功能聚合物", "生物聚合物", "导电聚合物"],
                    "塑料工程": ["工程塑料", "塑料改性", "塑料加工", "回收利用"],
                    "橡胶材料": ["合成橡胶", "橡胶改性", "橡胶制品", "弹性体"]
                },
                "复合材料": {
                    "纤维复合材料": ["碳纤维复合材料", "玻璃纤维复合材料", "天然纤维复合材料"],
                    "颗粒复合材料": ["金属基复合材料", "陶瓷基复合材料", "聚合物基复合材料"],
                    "层状复合材料": ["层压板", "夹芯结构", "梯度材料", "仿生材料"]
                }
            },
            "能源科学": {
                "新能源": {
                    "太阳能": ["光伏", "光热", "人工光合作用", "太阳能电池"],
                    "风能": ["风力发电", "海上风电", "小型风电", "风能存储"],
                    "生物质能": ["生物燃料", "生物发电", "生物制氢", "废物能源化"]
                },
                "储能技术": {
                    "电化学储能": ["锂离子电池", "钠离子电池", "固态电池", "超级电容器"],
                    "机械储能": ["抽水蓄能", "压缩空气", "飞轮储能", "重力储能"],
                    "化学储能": ["氢储能", "合成燃料", "氨储能", "甲醇储能"]
                },
                "能源转换": {
                    "燃料电池": ["质子交换膜", "固体氧化物", "碱性燃料电池", "直接醇类"],
                    "热电转换": ["热电材料", "热电器件", "废热回收", "温差发电"],
                    "光电转换": ["光伏材料", "光电器件", "光催化", "人工光合作用"]
                }
            },
            "环境科学": {
                "环境污染控制": {
                    "大气污染": ["空气净化", "VOCs治理", "PM2.5控制", "温室气体"],
                    "水污染": ["水处理", "污水处理", "水质净化", "海水淡化"],
                    "土壤污染": ["土壤修复", "重金属治理", "有机污染", "生物修复"]
                },
                "环境监测": {
                    "环境分析": ["污染物检测", "环境监测", "在线监测", "遥感监测"],
                    "生态评估": ["生态风险", "环境影响", "生物多样性", "生态系统"]
                },
                "清洁生产": {
                    "绿色化学": ["绿色合成", "原子经济", "可再生原料", "无废工艺"],
                    "循环经济": ["资源回收", "废物利用", "清洁工艺", "生命周期"]
                }
            }
        }
        
        # 常见研究方法关键词
        self.methodology_keywords = {
            "实验方法": ["合成", "制备", "表征", "测试", "分析", "实验"],
            "计算方法": ["DFT", "分子动力学", "量子化学", "第一性原理", "模拟", "计算"],
            "理论方法": ["理论分析", "模型建立", "机理研究", "热力学", "动力学"],
            "工程方法": ["工艺设计", "设备开发", "工程化", "产业化", "优化", "控制"]
        }
    
    async def determine_research_direction_interactive(
        self,
        user: User,
        initial_input: str = None,
        conversation_history: List[Dict] = None,
        progress_callback = None
    ) -> Dict:
        """
        交互式确定研究方向
        
        Args:
            user: 用户对象
            initial_input: 初始输入（可选）
            conversation_history: 对话历史
            progress_callback: 进度回调函数
            
        Returns:
            研究方向确定结果
        """
        try:
            logger.info(f"开始交互式研究方向确定 - 用户: {user.username}")
            
            if progress_callback:
                await progress_callback("开始分析", 10, {"user": user.username})
            
            # 初始化对话历史
            if conversation_history is None:
                conversation_history = []
            
            # 如果有初始输入且对话历史为空，添加到对话历史
            # 否则假设前端已经处理了当前输入的添加
            if initial_input and len(conversation_history) == 0:
                conversation_history.append({
                    "role": "user",
                    "content": initial_input,
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            if progress_callback:
                await progress_callback("分析用户输入", 30, {})
            
            # 分析当前对话内容
            analysis_result = await self._analyze_conversation_content(conversation_history)
            
            if progress_callback:
                await progress_callback("生成引导问题", 60, {})
            
            # 生成下一步引导问题或确定结果
            guidance_result = await self._generate_guidance_or_conclusion(
                conversation_history, analysis_result
            )
            
            # 如果生成了引导问题但未完成，将AI回复添加到对话历史
            if not guidance_result.get("is_complete", False) and guidance_result.get("next_questions"):
                assistant_message = {
                    "role": "assistant",
                    "content": " ".join(guidance_result.get("next_questions", [])),
                    "timestamp": datetime.utcnow().isoformat()
                }
                conversation_history.append(assistant_message)
            
            if progress_callback:
                await progress_callback("完成分析", 100, {})
            
            return {
                "success": True,
                "conversation_history": conversation_history,
                "analysis_result": analysis_result,
                "guidance_result": guidance_result,
                "is_complete": guidance_result.get("is_complete", False)
            }
            
        except Exception as e:
            logger.error(f"交互式研究方向确定失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def determine_research_direction_from_file(
        self,
        user: User,
        file_content: bytes,
        filename: str,
        progress_callback = None
    ) -> Dict:
        """
        基于文件确定研究方向
        
        Args:
            user: 用户对象
            file_content: 文件内容
            filename: 文件名
            progress_callback: 进度回调函数
            
        Returns:
            研究方向确定结果
        """
        try:
            logger.info(f"基于文件确定研究方向 - 文件: {filename}")
            
            if progress_callback:
                await progress_callback("上传文件", 10, {"filename": filename})
            
            # 使用文件上传服务分析文件
            file_analysis = await self.file_upload_service.upload_and_analyze_file(
                file_content, filename, user, "research_direction", progress_callback
            )
            
            if not file_analysis["success"]:
                return {"success": False, "error": file_analysis["error"]}
            
            if progress_callback:
                await progress_callback("深度分析研究方向", 70, {})
            
            # 基于文件分析结果进行深度研究方向分析
            research_direction = await self._deep_analyze_research_direction(
                file_analysis["analysis_result"]
            )
            
            if progress_callback:
                await progress_callback("生成项目建议", 90, {})
            
            # 生成项目创建建议
            project_suggestions = await self._generate_project_suggestions(research_direction)
            
            if progress_callback:
                await progress_callback("分析完成", 100, {})
            
            return {
                "success": True,
                "file_analysis": file_analysis,
                "research_direction": research_direction,
                "project_suggestions": project_suggestions,
                "confidence_score": research_direction.get("confidence_score", 0.0)
            }
            
        except Exception as e:
            logger.error(f"基于文件确定研究方向失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_discipline_menu_suggestions(
        self,
        user: User,
        selected_path: List[str] = None
    ) -> Dict:
        """
        获取学科菜单建议
        
        Args:
            user: 用户对象
            selected_path: 已选择的路径（如["化学", "有机化学"]）
            
        Returns:
            菜单建议结果
        """
        try:
            if selected_path is None:
                selected_path = []
            
            # 根据选择路径获取当前级别的选项
            current_level = self.discipline_hierarchy
            for path_item in selected_path:
                if path_item in current_level:
                    current_level = current_level[path_item]
                else:
                    return {"success": False, "error": f"无效的路径: {path_item}"}
            
            # 构建当前级别的选项
            if isinstance(current_level, dict):
                options = []
                for key, value in current_level.items():
                    option = {"name": key, "path": selected_path + [key]}
                    
                    if isinstance(value, dict):
                        # 还有子级别
                        option["has_children"] = True
                        option["children_count"] = len(value)
                        
                        # 添加描述（基于子项目）
                        if len(value) > 0:
                            first_child = list(value.keys())[0]
                            option["description"] = f"包含{first_child}等{len(value)}个子领域"
                    elif isinstance(value, list):
                        # 叶子节点
                        option["has_children"] = False
                        option["keywords"] = value
                        option["description"] = f"包含{len(value)}个研究方向"
                    
                    options.append(option)
                
                return {
                    "success": True,
                    "current_path": selected_path,
                    "options": options,
                    "is_leaf": False
                }
            elif isinstance(current_level, list):
                # 叶子节点
                return {
                    "success": True,
                    "current_path": selected_path,
                    "keywords": current_level,
                    "is_leaf": True,
                    "ready_for_project": True
                }
            else:
                return {"success": False, "error": "无效的层级结构"}
                
        except Exception as e:
            logger.error(f"获取学科菜单建议失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def finalize_research_direction(
        self,
        user: User,
        research_data: Dict,
        source_type: str = "interactive"  # interactive, file, menu
    ) -> Dict:
        """
        最终确定研究方向并生成项目配置
        
        Args:
            user: 用户对象
            research_data: 研究数据
            source_type: 来源类型
            
        Returns:
            最终确定结果
        """
        try:
            logger.info(f"最终确定研究方向 - 用户: {user.username}, 来源: {source_type}")
            
            # 整合和优化研究方向信息
            optimized_direction = await self._optimize_research_direction(
                research_data, source_type
            )
            
            # 生成详细的项目配置
            project_config = await self._generate_detailed_project_config(
                optimized_direction, user
            )
            
            # 预估文献采集配置
            literature_config = await self._estimate_literature_collection(
                optimized_direction
            )
            
            # 生成轻结构化模板建议
            structure_template = await self._suggest_structure_template(
                optimized_direction
            )
            
            return {
                "success": True,
                "research_direction": optimized_direction,
                "project_config": project_config,
                "literature_config": literature_config,
                "structure_template": structure_template,
                "ready_to_create": True
            }
            
        except Exception as e:
            logger.error(f"最终确定研究方向失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _analyze_conversation_content(self, conversation_history: List[Dict]) -> Dict:
        """分析对话内容"""
        try:
            if not conversation_history:
                return {"completeness": 0.0, "missing_info": ["研究主题", "研究目标", "研究方法"]}
            
            # 提取所有用户输入
            user_inputs = [
                msg["content"] for msg in conversation_history 
                if msg.get("role") == "user"
            ]
            
            if not user_inputs:
                return {"completeness": 0.0, "missing_info": ["研究主题", "研究目标", "研究方法"]}
            
            combined_input = "\n".join(user_inputs)
            
            # 使用AI分析对话内容
            analysis_prompt = f"""
请分析以下用户对话内容，评估研究方向信息的完整性：

对话内容:
{combined_input}

请分析并以JSON格式返回：
{{
    "completeness": 0.75,
    "extracted_info": {{
        "research_topic": "研究主题",
        "research_objectives": ["目标1", "目标2"],
        "methodology": ["方法1", "方法2"],
        "keywords": ["关键词1", "关键词2"],
        "application_areas": ["应用1", "应用2"],
        "research_field": "学科领域"
    }},
    "missing_info": ["缺失的信息类型"],
    "confidence_score": 8.0,
    "suggestions": ["建议1", "建议2"]
}}

评估标准：
- 完整性：0-1之间，1表示信息完整
- 提取的信息要准确
- 缺失信息要明确指出
- 置信度评分1-10分
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
            
            # 默认返回
            return {
                "completeness": 0.3,
                "extracted_info": {"research_topic": "待确定"},
                "missing_info": ["研究目标", "研究方法"],
                "confidence_score": 5.0
            }
            
        except Exception as e:
            logger.error(f"分析对话内容失败: {e}")
            return {"completeness": 0.0, "missing_info": ["所有信息"]}
    
    async def _generate_guidance_or_conclusion(
        self, 
        conversation_history: List[Dict], 
        analysis_result: Dict
    ) -> Dict:
        """生成引导问题或结论"""
        try:
            completeness = analysis_result.get("completeness", 0.0)
            
            # 如果信息足够完整，生成结论
            if completeness >= 0.8:
                return await self._generate_conclusion(analysis_result)
            
            # 否则生成引导问题
            return await self._generate_guidance_questions(analysis_result)
            
        except Exception as e:
            logger.error(f"生成引导或结论失败: {e}")
            return {"is_complete": False, "next_questions": ["请描述您的研究主题"]}
    
    async def _generate_conclusion(self, analysis_result: Dict) -> Dict:
        """生成研究方向确定结论"""
        try:
            extracted_info = analysis_result.get("extracted_info", {})
            
            conclusion_prompt = f"""
基于以下分析结果，生成研究方向确定的最终结论：

分析结果:
{json.dumps(extracted_info, ensure_ascii=False, indent=2)}

请生成结论并以JSON格式返回：
{{
    "is_complete": true,
    "research_direction": "明确的研究方向描述",
    "keywords": ["精确的关键词列表"],
    "research_categories": ["学科", "子领域", "具体方向"],
    "project_name_suggestions": ["项目名称建议1", "项目名称建议2"],
    "next_steps": ["下一步操作建议"],
    "confidence_score": 9.0
}}

要求：
- 研究方向要具体明确
- 关键词要准确相关
- 项目名称要专业且吸引人
"""
            
            response = await self.ai_service.generate_completion(
                conclusion_prompt,
                model="gpt-4",
                max_tokens=600,
                temperature=0.3
            )
            
            if response.get("success"):
                try:
                    conclusion = json.loads(response["content"])
                    return conclusion
                except json.JSONDecodeError:
                    pass
            
            # 默认结论
            return {
                "is_complete": True,
                "research_direction": extracted_info.get("research_topic", "研究方向"),
                "keywords": extracted_info.get("keywords", []),
                "confidence_score": 7.0
            }
            
        except Exception as e:
            logger.error(f"生成结论失败: {e}")
            return {"is_complete": True, "error": str(e)}
    
    async def _generate_guidance_questions(self, analysis_result: Dict) -> Dict:
        """生成引导问题"""
        try:
            missing_info = analysis_result.get("missing_info", [])
            extracted_info = analysis_result.get("extracted_info", {})
            
            guidance_prompt = f"""
基于当前分析结果，生成引导用户完善研究方向的问题：

已有信息:
{json.dumps(extracted_info, ensure_ascii=False, indent=2)}

缺失信息:
{missing_info}

请生成引导问题并以JSON格式返回：
{{
    "is_complete": false,
    "next_questions": [
        "具体的引导问题1",
        "具体的引导问题2"
    ],
    "question_type": "research_topic/objectives/methodology/application",
    "suggestions": ["建议或提示"],
    "progress_percentage": 45
}}

要求：
- 问题要具体且有针对性
- 基于已有信息提出相关问题
- 帮助用户逐步完善研究方向
"""
            
            response = await self.ai_service.generate_completion(
                guidance_prompt,
                model="gpt-4",
                max_tokens=400,
                temperature=0.4
            )
            
            if response.get("success"):
                try:
                    guidance = json.loads(response["content"])
                    return guidance
                except json.JSONDecodeError:
                    pass
            
            # 默认引导问题
            if "研究主题" in missing_info:
                return {
                    "is_complete": False,
                    "next_questions": ["请详细描述您的研究主题或研究对象"],
                    "question_type": "research_topic"
                }
            elif "研究目标" in missing_info:
                return {
                    "is_complete": False,
                    "next_questions": ["您希望通过这项研究解决什么问题或达到什么目标？"],
                    "question_type": "objectives"
                }
            else:
                return {
                    "is_complete": False,
                    "next_questions": ["请提供更多关于您研究的详细信息"],
                    "question_type": "general"
                }
                
        except Exception as e:
            logger.error(f"生成引导问题失败: {e}")
            return {"is_complete": False, "next_questions": ["请描述您的研究方向"]}
    
    async def _deep_analyze_research_direction(self, file_analysis_result: Dict) -> Dict:
        """深度分析研究方向"""
        try:
            analysis_prompt = f"""
基于文件分析结果，进行深度研究方向分析：

文件分析结果:
{json.dumps(file_analysis_result, ensure_ascii=False, indent=2)}

请进行深度分析并以JSON格式返回：
{{
    "research_direction": "具体的研究方向",
    "research_field": "所属学科领域",
    "keywords": ["关键词1", "关键词2", ...],
    "research_objectives": ["目标1", "目标2", ...],
    "methodology": ["方法1", "方法2", ...],
    "innovation_points": ["创新点1", "创新点2", ...],
    "application_prospects": ["应用前景1", "应用前景2", ...],
    "research_challenges": ["挑战1", "挑战2", ...],
    "literature_keywords": ["文献检索关键词1", "文献检索关键词2", ...],
    "confidence_score": 8.5,
    "completeness": 0.9
}}

要求：
- 分析要深入且专业
- 关键词要准确且具体
- 考虑创新性和应用价值
- 识别研究挑战和难点
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
            
            # 从原始分析结果中提取基本信息
            return {
                "research_direction": file_analysis_result.get("research_direction", "研究方向"),
                "keywords": file_analysis_result.get("keywords", []),
                "research_field": file_analysis_result.get("research_field", "综合"),
                "confidence_score": file_analysis_result.get("confidence_score", 5.0),
                "completeness": 0.7
            }
            
        except Exception as e:
            logger.error(f"深度分析研究方向失败: {e}")
            return {"research_direction": "分析失败", "confidence_score": 0.0}
    
    async def _generate_project_suggestions(self, research_direction: Dict) -> Dict:
        """生成项目建议"""
        try:
            suggestion_prompt = f"""
基于研究方向分析，生成项目创建建议：

研究方向分析:
{json.dumps(research_direction, ensure_ascii=False, indent=2)}

请生成项目建议并以JSON格式返回：
{{
    "project_names": ["项目名称建议1", "项目名称建议2", "项目名称建议3"],
    "literature_search_strategy": {{
        "primary_keywords": ["主要关键词"],
        "secondary_keywords": ["次要关键词"],
        "search_databases": ["推荐数据库"],
        "estimated_literature_count": 1500
    }},
    "project_structure": {{
        "main_sections": ["主要部分1", "主要部分2"],
        "research_phases": ["阶段1", "阶段2"],
        "deliverables": ["交付物1", "交付物2"]
    }},
    "resource_requirements": {{
        "time_estimate": "预估时间",
        "expertise_needed": ["需要的专业知识"],
        "tools_software": ["推荐工具"]
    }},
    "success_metrics": ["成功指标1", "成功指标2"]
}}

要求：
- 项目名称要专业且吸引人
- 文献检索策略要具体可行
- 考虑项目的可行性和实用性
"""
            
            response = await self.ai_service.generate_completion(
                suggestion_prompt,
                model="gpt-4",
                max_tokens=1000,
                temperature=0.4
            )
            
            if response.get("success"):
                try:
                    return json.loads(response["content"])
                except json.JSONDecodeError:
                    pass
            
            # 默认建议
            return {
                "project_names": [f"{research_direction.get('research_direction', '研究')}项目"],
                "literature_search_strategy": {
                    "primary_keywords": research_direction.get("keywords", [])[:5],
                    "estimated_literature_count": 1000
                }
            }
            
        except Exception as e:
            logger.error(f"生成项目建议失败: {e}")
            return {"project_names": ["新研究项目"]}
    
    async def _optimize_research_direction(self, research_data: Dict, source_type: str) -> Dict:
        """优化研究方向"""
        try:
            optimization_prompt = f"""
请优化以下研究方向信息，使其更准确和完整：

原始数据:
{json.dumps(research_data, ensure_ascii=False, indent=2)}

来源类型: {source_type}

请优化并以JSON格式返回：
{{
    "research_direction": "优化后的研究方向描述",
    "keywords": ["优化后的关键词列表"],
    "research_categories": ["学科", "子领域", "具体方向"],
    "objectives": ["明确的研究目标"],
    "methodology": ["具体的研究方法"],
    "innovation_aspects": ["创新点"],
    "practical_value": ["实用价值"],
    "literature_keywords": ["文献检索关键词"],
    "quality_score": 9.0
}}

优化要求：
- 确保研究方向具体明确
- 关键词要准确且具有检索价值
- 目标要可实现且有意义
- 方法要可行且适当
"""
            
            response = await self.ai_service.generate_completion(
                optimization_prompt,
                model="gpt-4",
                max_tokens=800,
                temperature=0.2
            )
            
            if response.get("success"):
                try:
                    return json.loads(response["content"])
                except json.JSONDecodeError:
                    pass
            
            # 如果优化失败，返回原始数据的清理版本
            return {
                "research_direction": research_data.get("research_direction", "研究方向"),
                "keywords": research_data.get("keywords", []),
                "quality_score": 7.0
            }
            
        except Exception as e:
            logger.error(f"优化研究方向失败: {e}")
            return research_data
    
    async def _generate_detailed_project_config(self, research_direction: Dict, user: User) -> Dict:
        """生成详细的项目配置"""
        try:
            # 基于研究方向和用户信息生成项目配置
            config = {
                "name": research_direction.get("research_direction", "新研究项目"),
                "description": f"基于{research_direction.get('research_direction', '研究方向')}的智能文献分析项目",
                "keywords": research_direction.get("keywords", []),
                "research_categories": research_direction.get("research_categories", []),
                "owner_id": user.id,
                "literature_sources": ["semantic_scholar", "pubmed", "google_scholar"],
                "max_literature_count": 1000,  # 根据用户会员级别调整
                "status": "planning"
            }
            
            return config
            
        except Exception as e:
            logger.error(f"生成项目配置失败: {e}")
            return {"name": "新项目", "keywords": []}
    
    async def _estimate_literature_collection(self, research_direction: Dict) -> Dict:
        """预估文献采集配置"""
        try:
            keywords = research_direction.get("keywords", [])
            
            # 估算每个关键词的文献数量
            estimated_counts = {}
            total_estimated = 0
            
            for keyword in keywords[:5]:  # 限制关键词数量
                # 简单的估算逻辑（实际应该基于历史数据）
                estimated_count = len(keyword) * 100 + 500  # 简化估算
                estimated_counts[keyword] = estimated_count
                total_estimated += estimated_count
            
            return {
                "keywords": keywords,
                "estimated_counts": estimated_counts,
                "total_estimated": min(total_estimated, 5000),  # 限制最大值
                "recommended_sources": ["semantic_scholar", "pubmed", "google_scholar"],
                "collection_strategy": "parallel_collection_with_ai_screening"
            }
            
        except Exception as e:
            logger.error(f"预估文献采集失败: {e}")
            return {"total_estimated": 1000}
    
    async def _suggest_structure_template(self, research_direction: Dict) -> Dict:
        """建议轻结构化模板"""
        try:
            research_field = research_direction.get("research_field", "综合")
            
            # 基于研究领域选择模板
            if "化学" in research_field or "材料" in research_field:
                template = {
                    "name": "材料化学研究模板",
                    "structure": {
                        "制备与表征": {
                            "制备方法": ["制备工艺", "反应条件", "设备参数"],
                            "材料表征": ["结构分析", "性能测试", "表征方法"]
                        },
                        "性能与应用": {
                            "性能评估": ["关键性能", "测试条件", "对比分析"],
                            "应用研究": ["应用领域", "实际效果", "优化方向"]
                        }
                    }
                }
            elif "能源" in research_field:
                template = {
                    "name": "能源科学研究模板",
                    "structure": {
                        "能源转换": {
                            "转换机理": ["转换原理", "效率分析", "影响因素"],
                            "器件设计": ["结构设计", "材料选择", "工艺优化"]
                        },
                        "性能与应用": {
                            "性能测试": ["关键指标", "测试方法", "稳定性"],
                            "应用前景": ["应用场景", "市场潜力", "发展趋势"]
                        }
                    }
                }
            else:
                template = {
                    "name": "通用研究模板",
                    "structure": {
                        "理论与方法": {
                            "理论基础": ["基础理论", "模型建立", "机理分析"],
                            "研究方法": ["实验方法", "分析方法", "评估方法"]
                        },
                        "结果与应用": {
                            "研究结果": ["主要结果", "数据分析", "结果讨论"],
                            "应用价值": ["应用领域", "实用价值", "推广前景"]
                        }
                    }
                }
            
            return template
            
        except Exception as e:
            logger.error(f"建议结构化模板失败: {e}")
            return {"name": "基础模板", "structure": {}}