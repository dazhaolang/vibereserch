"""
轻结构化数据处理服务 - 商业化完整版本
实现自动模板生成、并行提取、版权合规处理
"""

import asyncio
import json
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.core.config import settings
from app.services.ai_service import AIService
from app.services.pdf_processor import PDFProcessor
from app.models.literature import Literature, LiteratureSegment
from app.models.project import Project


class LightweightStructuringService:
    """轻结构化数据处理服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.ai_service = AIService()
        self.pdf_processor = PDFProcessor()
        
        # 预设基础模板 - 按学科分类
        self.base_templates = {
            "材料科学": {
                "name": "材料科学研究模板",
                "structure": {
                    "制备与表征": {
                        "原料制备": ["制备方法", "工艺参数", "设备条件", "质量控制"],
                        "材料表征": ["表征方法", "测试条件", "关键指标", "结果分析"],
                        "性能测试": ["测试方法", "测试条件", "性能指标", "对比分析"]
                    },
                    "复合物与应用": {
                        "复合物制备": ["复合策略", "制备工艺", "界面处理", "结构控制"],
                        "应用研究": ["应用领域", "性能评估", "实际效果", "优化方向"]
                    },
                    "计算与机理": {
                        "理论计算": ["计算方法", "计算参数", "软件工具", "计算结果"],
                        "反应机理": ["机理分析", "反应路径", "关键步骤", "影响因素"]
                    }
                }
            },
            "有机化学": {
                "name": "有机化学研究模板", 
                "structure": {
                    "合成与制备": {
                        "合成路线": ["反应类型", "反应条件", "催化剂", "产率优化"],
                        "产物分析": ["结构确认", "纯度检测", "光谱数据", "理化性质"],
                        "工艺优化": ["条件筛选", "副反应控制", "放大工艺", "成本分析"]
                    },
                    "结构与性质": {
                        "分子结构": ["分子设计", "构效关系", "立体化学", "电子效应"],
                        "物理性质": ["溶解性", "稳定性", "熔沸点", "光学性质"],
                        "化学性质": ["反应活性", "选择性", "机理研究", "动力学"]
                    }
                }
            },
            "电化学": {
                "name": "电化学研究模板",
                "structure": {
                    "电极材料": {
                        "材料制备": ["制备方法", "结构设计", "形貌控制", "掺杂改性"],
                        "电化学性能": ["循环伏安", "充放电", "阻抗谱", "稳定性"],
                        "机理分析": ["反应机理", "动力学", "热力学", "界面行为"]
                    },
                    "器件与应用": {
                        "器件组装": ["电池结构", "电解液", "隔膜", "集流体"],
                        "性能测试": ["容量", "倍率", "循环", "安全性"],
                        "实际应用": ["应用场景", "工程化", "成本分析", "市场前景"]
                    }
                }
            }
        }
    
    async def auto_generate_structure_template(
        self, 
        project: Project, 
        sample_literature: List[Literature],
        progress_callback = None
    ) -> Dict:
        """
        自动生成轻结构化模板
        
        Args:
            project: 项目对象
            sample_literature: 样本文献列表
            progress_callback: 进度回调函数
        
        Returns:
            生成的模板结构
        """
        logger.info(f"开始为项目 {project.id} 自动生成轻结构化模板")
        
        if progress_callback:
            await progress_callback("分析研究领域", 10, {"sample_count": len(sample_literature)})
        
        # 第一步：识别研究领域
        research_field = await self._identify_research_field(project.keywords, sample_literature)
        logger.info(f"识别研究领域: {research_field}")
        
        # 第二步：获取基础模板
        base_template = self._get_base_template(research_field)
        
        if progress_callback:
            await progress_callback("分析文献特征", 30, {"field": research_field})
        
        # 第三步：分析样本文献特征
        literature_features = await self._analyze_literature_features(sample_literature)
        
        if progress_callback:
            await progress_callback("生成定制模板", 60, {"features_count": len(literature_features)})
        
        # 第四步：基于文献特征定制模板
        customized_template = await self._customize_template(
            base_template, literature_features, project.keywords
        )
        
        if progress_callback:
            await progress_callback("生成提取提示词", 80, {})
        
        # 第五步：生成对应的提取提示词
        extraction_prompts = await self._generate_extraction_prompts(customized_template)
        
        # 第六步：保存到项目配置
        project.structure_template = customized_template
        project.extraction_prompts = extraction_prompts
        self.db.commit()
        
        if progress_callback:
            await progress_callback("模板生成完成", 100, {"template_ready": True})
        
        return {
            "success": True,
            "template": customized_template,
            "prompts": extraction_prompts,
            "research_field": research_field,
            "features": literature_features
        }
    
    async def parallel_extract_literature(
        self,
        project: Project,
        literature_list: List[Literature],
        progress_callback = None
    ) -> Dict:
        """
        并行提取文献的轻结构化内容
        
        Args:
            project: 项目对象
            literature_list: 文献列表
            progress_callback: 进度回调函数
        
        Returns:
            提取结果统计
        """
        logger.info(f"开始并行提取 {len(literature_list)} 篇文献的轻结构化内容")
        
        if not project.structure_template or not project.extraction_prompts:
            raise ValueError("项目缺少轻结构化模板或提取提示词")
        
        # 统计变量
        total_count = len(literature_list)
        processed_count = 0
        success_count = 0
        failed_count = 0
        
        if progress_callback:
            await progress_callback("开始并行提取", 0, {"total": total_count})
        
        # 并行处理配置
        max_workers = min(10, total_count)  # 最多10个并发
        batch_size = 5  # 每批处理5篇文献
        
        # 分批并行处理
        for batch_start in range(0, total_count, batch_size):
            batch_end = min(batch_start + batch_size, total_count)
            batch_literature = literature_list[batch_start:batch_end]
            
            # 创建并行任务
            tasks = []
            for literature in batch_literature:
                task = self._extract_single_literature(project, literature)
                tasks.append(task)
            
            # 执行并行任务
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 统计结果
            for i, result in enumerate(batch_results):
                processed_count += 1
                
                if isinstance(result, Exception):
                    failed_count += 1
                    logger.error(f"文献提取失败 - {batch_literature[i].title}: {result}")
                else:
                    if result.get("success", False):
                        success_count += 1
                    else:
                        failed_count += 1
                
                # 更新进度
                if progress_callback:
                    progress = (processed_count / total_count) * 100
                    await progress_callback(
                        f"处理中 ({processed_count}/{total_count})", 
                        progress,
                        {
                            "processed": processed_count,
                            "success": success_count,
                            "failed": failed_count
                        }
                    )
        
        logger.info(f"并行提取完成 - 成功: {success_count}, 失败: {failed_count}")
        
        return {
            "success": True,
            "statistics": {
                "total_count": total_count,
                "processed_count": processed_count,
                "success_count": success_count,
                "failed_count": failed_count,
                "success_rate": (success_count / total_count) * 100 if total_count > 0 else 0
            }
        }
    
    async def _extract_single_literature(self, project: Project, literature: Literature) -> Dict:
        """提取单篇文献的轻结构化内容"""
        try:
            # 获取文献内容
            content = await self._get_literature_content(literature)
            if not content:
                return {"success": False, "error": "无法获取文献内容"}
            
            # 按模板结构逐部分提取
            structured_data = {}
            template = project.structure_template
            prompts = project.extraction_prompts
            
            for section_name, section_structure in template.get("structure", {}).items():
                section_data = {}
                
                for subsection_name, subsection_fields in section_structure.items():
                    # 获取对应的提取提示词
                    prompt_key = f"{section_name}_{subsection_name}"
                    extraction_prompt = prompts.get(prompt_key, "")
                    
                    if extraction_prompt:
                        # 使用AI提取内容
                        extracted_content = await self._extract_with_ai(
                            content, extraction_prompt, subsection_fields
                        )
                        
                        if extracted_content:
                            section_data[subsection_name] = extracted_content
                
                if section_data:
                    structured_data[section_name] = section_data
            
            # 保存提取结果
            await self._save_structured_data(literature, structured_data, project)
            
            return {"success": True, "structured_data": structured_data}
            
        except Exception as e:
            logger.error(f"提取文献 {literature.id} 失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _extract_with_ai(
        self, 
        content: str, 
        extraction_prompt: str, 
        fields: List[str]
    ) -> Optional[Dict]:
        """使用AI提取特定内容"""
        try:
            # 构建完整提示词
            full_prompt = f"""
{extraction_prompt}

请从以下文献内容中提取相关信息，以JSON格式返回：

目标字段: {', '.join(fields)}

文献内容:
{content[:4000]}...  # 限制内容长度避免token超限

要求：
1. 以总结式话术呈现核心信息，避免直接复制原文
2. 如果某个字段没有相关信息，设为null
3. 返回格式：{{"字段名": "总结内容", ...}}
4. 确保内容简洁且包含关键信息
"""
            
            # 调用AI服务
            response = await self.ai_service.generate_completion(
                full_prompt,
                model="gpt-3.5-turbo",
                max_tokens=800,
                temperature=0.2
            )
            
            if response.get("success"):
                try:
                    extracted_data = json.loads(response["content"])
                    return extracted_data
                except json.JSONDecodeError:
                    # 如果JSON解析失败，尝试提取文本内容
                    return {"summary": response["content"][:500]}
            
            return None
            
        except Exception as e:
            logger.error(f"AI提取失败: {e}")
            return None
    
    async def _get_literature_content(self, literature: Literature) -> Optional[str]:
        """获取文献内容"""
        try:
            # 如果有PDF文件，使用PDF处理器提取
            if literature.pdf_path:
                content = await self.pdf_processor.extract_text(literature.pdf_path)
                if content:
                    return content
            
            # 否则使用摘要和标题
            content_parts = []
            if literature.title:
                content_parts.append(f"标题: {literature.title}")
            if literature.abstract:
                content_parts.append(f"摘要: {literature.abstract}")
            
            return "\n\n".join(content_parts) if content_parts else None
            
        except Exception as e:
            logger.error(f"获取文献内容失败: {e}")
            return None
    
    async def _save_structured_data(
        self, 
        literature: Literature, 
        structured_data: Dict, 
        project: Project
    ):
        """保存结构化数据"""
        try:
            # 为每个结构化部分创建文献段落
            for section_name, section_data in structured_data.items():
                for subsection_name, subsection_content in section_data.items():
                    # 创建文献段落记录
                    segment = LiteratureSegment(
                        literature_id=literature.id,
                        project_id=project.id,
                        segment_type=f"{section_name}_{subsection_name}",
                        content=json.dumps(subsection_content, ensure_ascii=False),
                        structured_data=subsection_content,
                        extraction_method="ai_structured",
                        quality_score=self._calculate_quality_score(subsection_content)
                    )
                    
                    self.db.add(segment)
            
            self.db.commit()
            logger.info(f"保存文献 {literature.id} 的结构化数据完成")
            
        except Exception as e:
            logger.error(f"保存结构化数据失败: {e}")
            self.db.rollback()
    
    def _calculate_quality_score(self, content: Dict) -> float:
        """计算内容质量评分"""
        try:
            score = 0.0
            total_fields = 0
            
            for key, value in content.items():
                total_fields += 1
                if value and str(value).strip() and str(value).lower() != "null":
                    score += 1.0
                    # 内容长度奖励
                    if len(str(value)) > 50:
                        score += 0.5
                    if len(str(value)) > 200:
                        score += 0.5
            
            return (score / max(total_fields, 1)) * 10  # 转换为10分制
            
        except Exception:
            return 5.0  # 默认中等评分
    
    async def _identify_research_field(
        self, 
        keywords: List[str], 
        sample_literature: List[Literature]
    ) -> str:
        """识别研究领域"""
        try:
            # 构建分析提示
            titles = [lit.title for lit in sample_literature[:10] if lit.title]
            abstracts = [lit.abstract[:200] for lit in sample_literature[:5] if lit.abstract]
            
            analysis_prompt = f"""
基于以下信息，判断这个研究项目属于哪个主要学科领域：

关键词: {', '.join(keywords)}

文献标题示例:
{chr(10).join([f"- {title}" for title in titles[:5]])}

文献摘要示例:
{chr(10).join([f"- {abstract}..." for abstract in abstracts[:3]])}

可选领域: 材料科学, 有机化学, 无机化学, 物理化学, 电化学, 生物化学, 环境科学, 能源科学

请只返回最匹配的一个领域名称。
"""
            
            response = await self.ai_service.generate_completion(
                analysis_prompt,
                model="gpt-3.5-turbo",
                max_tokens=50,
                temperature=0.1
            )
            
            if response.get("success"):
                field = response["content"].strip()
                # 验证返回的领域是否在预设列表中
                if field in self.base_templates:
                    return field
            
            # 默认返回材料科学
            return "材料科学"
            
        except Exception as e:
            logger.error(f"识别研究领域失败: {e}")
            return "材料科学"
    
    def _get_base_template(self, research_field: str) -> Dict:
        """获取基础模板"""
        return self.base_templates.get(research_field, self.base_templates["材料科学"])
    
    async def _analyze_literature_features(self, sample_literature: List[Literature]) -> Dict:
        """分析文献特征"""
        features = {
            "common_keywords": [],
            "research_methods": [],
            "application_areas": [],
            "material_types": []
        }
        
        try:
            # 收集样本文本
            sample_texts = []
            for lit in sample_literature[:10]:
                text_parts = []
                if lit.title:
                    text_parts.append(lit.title)
                if lit.abstract:
                    text_parts.append(lit.abstract[:300])
                if text_parts:
                    sample_texts.append(" ".join(text_parts))
            
            if not sample_texts:
                return features
            
            # 使用AI分析特征
            analysis_prompt = f"""
分析以下文献样本，提取关键特征信息：

文献样本:
{chr(10).join([f"{i+1}. {text}" for i, text in enumerate(sample_texts[:5])])}

请提取以下信息，以JSON格式返回：
{{
    "common_keywords": ["关键词1", "关键词2", ...],
    "research_methods": ["方法1", "方法2", ...],
    "application_areas": ["应用1", "应用2", ...],
    "material_types": ["材料1", "材料2", ...]
}}

每个列表最多5个项目。
"""
            
            response = await self.ai_service.generate_completion(
                analysis_prompt,
                model="gpt-3.5-turbo",
                max_tokens=400,
                temperature=0.3
            )
            
            if response.get("success"):
                try:
                    analyzed_features = json.loads(response["content"])
                    features.update(analyzed_features)
                except json.JSONDecodeError:
                    pass
            
        except Exception as e:
            logger.error(f"分析文献特征失败: {e}")
        
        return features
    
    async def _customize_template(
        self, 
        base_template: Dict, 
        literature_features: Dict, 
        project_keywords: List[str]
    ) -> Dict:
        """基于文献特征定制模板"""
        try:
            customization_prompt = f"""
基于以下信息，调整和优化轻结构化模板：

基础模板:
{json.dumps(base_template, ensure_ascii=False, indent=2)}

文献特征:
{json.dumps(literature_features, ensure_ascii=False, indent=2)}

项目关键词: {', '.join(project_keywords)}

请调整模板结构，使其更适合这个具体研究项目。保持JSON格式，可以：
1. 调整字段名称使其更具体
2. 添加特定的子字段
3. 重新组织结构层次

返回完整的优化后模板。
"""
            
            response = await self.ai_service.generate_completion(
                customization_prompt,
                model="gpt-4",  # 使用更强的模型进行模板定制
                max_tokens=1000,
                temperature=0.2
            )
            
            if response.get("success"):
                try:
                    customized_template = json.loads(response["content"])
                    return customized_template
                except json.JSONDecodeError:
                    pass
            
            # 如果定制失败，返回基础模板
            return base_template
            
        except Exception as e:
            logger.error(f"定制模板失败: {e}")
            return base_template
    
    async def _generate_extraction_prompts(self, template: Dict) -> Dict:
        """生成提取提示词"""
        prompts = {}
        
        try:
            structure = template.get("structure", {})
            
            for section_name, section_structure in structure.items():
                for subsection_name, fields in section_structure.items():
                    prompt_key = f"{section_name}_{subsection_name}"
                    
                    # 生成针对性的提取提示词
                    prompt = f"""
你是一个专业的文献信息提取专家。请从文献中提取关于"{subsection_name}"的相关信息。

提取目标：
- 重点关注: {section_name} -> {subsection_name}
- 具体字段: {', '.join(fields)}

提取要求：
1. 以总结式话术呈现，避免直接复制原文
2. 突出关键的技术参数、方法和结果
3. 保持信息的准确性和完整性
4. 如果没有相关信息，返回null
5. 避免版权风险，用自己的话总结

请仔细阅读文献内容，准确提取相关信息。
"""
                    
                    prompts[prompt_key] = prompt
            
        except Exception as e:
            logger.error(f"生成提取提示词失败: {e}")
        
        return prompts


class CopyrightComplianceChecker:
    """版权合规检查器"""
    
    def __init__(self):
        self.ai_service = AIService()
    
    async def check_content_compliance(self, original_text: str, extracted_text: str) -> Dict:
        """检查提取内容的版权合规性"""
        try:
            check_prompt = f"""
请评估以下提取内容是否存在版权风险：

原始文本（部分）:
{original_text[:500]}...

提取内容:
{extracted_text}

评估标准：
1. 是否直接复制了大段原文
2. 是否用总结性语言重新表述
3. 是否保留了原文的核心数据但避免了直接抄袭

请返回JSON格式结果：
{{
    "compliant": true/false,
    "risk_level": "low/medium/high", 
    "suggestions": ["建议1", "建议2", ...]
}}
"""
            
            response = await self.ai_service.generate_completion(
                check_prompt,
                model="gpt-3.5-turbo",
                max_tokens=300,
                temperature=0.1
            )
            
            if response.get("success"):
                try:
                    return json.loads(response["content"])
                except json.JSONDecodeError:
                    pass
            
            return {"compliant": True, "risk_level": "low", "suggestions": []}
            
        except Exception as e:
            logger.error(f"版权合规检查失败: {e}")
            return {"compliant": True, "risk_level": "low", "suggestions": []}