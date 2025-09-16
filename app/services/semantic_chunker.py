"""
语义分块器 - 基于轻量级结构化模板的完整字段分块策略
解决问题：替代当前按段落和长度分块的方式，实现基于语义的完整字段分块
"""

import re
import json
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from loguru import logger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.ai_service import AIService


class ChunkType(Enum):
    """分块类型"""
    METHODOLOGY = "methodology"        # 方法学
    RESULTS = "results"               # 结果
    PREPARATION = "preparation"       # 制备工艺
    CHARACTERIZATION = "characterization"  # 表征分析
    PERFORMANCE = "performance"       # 性能评估
    MECHANISM = "mechanism"          # 机理分析
    APPLICATION = "application"      # 应用
    INTRODUCTION = "introduction"    # 引言
    CONCLUSION = "conclusion"        # 结论
    DISCUSSION = "discussion"        # 讨论
    EXPERIMENTAL = "experimental"    # 实验


@dataclass
class SemanticChunk:
    """语义分块"""
    chunk_id: str
    chunk_type: ChunkType
    content: str
    structured_data: Dict[str, Any]
    confidence: float
    start_position: int
    end_position: int
    page_numbers: List[int]
    section_title: Optional[str] = None
    subsections: List[str] = None

    def __post_init__(self):
        if self.subsections is None:
            self.subsections = []


class LightweightStructuredTemplate:
    """轻量级结构化模板"""

    def __init__(self):
        # 标准字段模板
        self.field_templates = {
            "methodology": {
                "patterns": [
                    r"方法|method|procedure|protocol|approach|technique",
                    r"工艺|process|synthesis|fabrication|preparation",
                    r"步骤|step|stage|phase",
                    r"条件|condition|parameter|setting"
                ],
                "structured_fields": [
                    "materials_used",
                    "equipment_required",
                    "process_parameters",
                    "synthesis_conditions",
                    "characterization_methods"
                ],
                "required_sections": ["materials", "procedures", "characterization"]
            },

            "results": {
                "patterns": [
                    r"结果|result|finding|observation|data",
                    r"性能|performance|property|characteristic",
                    r"测试|test|measurement|analysis|evaluation",
                    r"数据|data|value|measurement|outcome"
                ],
                "structured_fields": [
                    "performance_metrics",
                    "measurement_results",
                    "test_conditions",
                    "data_analysis",
                    "statistical_significance"
                ],
                "required_sections": ["measurements", "performance", "analysis"]
            },

            "preparation": {
                "patterns": [
                    r"制备|preparation|synthesis|fabrication",
                    r"合成|synthesis|preparation|formation",
                    r"工艺|process|method|technique|procedure",
                    r"参数|parameter|condition|setting|variable"
                ],
                "structured_fields": [
                    "precursor_materials",
                    "synthesis_method",
                    "process_conditions",
                    "reaction_parameters",
                    "purification_steps"
                ],
                "required_sections": ["materials", "synthesis", "conditions"]
            },

            "characterization": {
                "patterns": [
                    r"表征|characterization|analysis|examination",
                    r"测试|test|measurement|evaluation|assessment",
                    r"分析|analysis|investigation|study|inspection",
                    r"仪器|instrument|equipment|apparatus|device"
                ],
                "structured_fields": [
                    "characterization_techniques",
                    "instrument_specifications",
                    "measurement_conditions",
                    "sample_preparation",
                    "data_processing"
                ],
                "required_sections": ["techniques", "instruments", "conditions"]
            },

            "performance": {
                "patterns": [
                    r"性能|performance|property|behavior|response",
                    r"效果|effect|efficiency|effectiveness|improvement",
                    r"优化|optimization|enhancement|improvement",
                    r"评估|evaluation|assessment|testing|validation"
                ],
                "structured_fields": [
                    "performance_metrics",
                    "optimization_parameters",
                    "comparative_analysis",
                    "improvement_factors",
                    "validation_methods"
                ],
                "required_sections": ["metrics", "optimization", "validation"]
            },

            "mechanism": {
                "patterns": [
                    r"机理|mechanism|principle|theory|explanation",
                    r"原理|principle|basis|foundation|rationale",
                    r"模型|model|simulation|theoretical|computational",
                    r"分析|analysis|investigation|interpretation|discussion"
                ],
                "structured_fields": [
                    "theoretical_framework",
                    "mechanistic_insights",
                    "computational_models",
                    "physical_principles",
                    "interpretation_analysis"
                ],
                "required_sections": ["theory", "mechanisms", "models"]
            }
        }


class SemanticChunker:
    """语义分块器"""

    def __init__(self, ai_service: AIService = None):
        self.ai_service = ai_service or AIService()
        self.template = LightweightStructuredTemplate()

        # 分块参数配置
        self.min_chunk_length = 200      # 最小分块长度 (字符)
        self.max_chunk_length = 3000     # 最大分块长度 (字符)
        self.overlap_ratio = 0.1         # 重叠比例
        self.confidence_threshold = 0.6   # 置信度阈值

    async def chunk_literature(
        self,
        content: str,
        structure_template: Optional[Dict] = None,
        preserve_semantic_integrity: bool = True
    ) -> List[SemanticChunk]:
        """
        对文献内容进行语义分块

        Args:
            content: 文献文本内容
            structure_template: 可选的结构化模板
            preserve_semantic_integrity: 是否保持语义完整性

        Returns:
            语义分块列表
        """
        try:
            logger.info(f"开始语义分块，内容长度: {len(content)} 字符")

            # 1. 预处理文本
            cleaned_content = self._preprocess_text(content)

            # 2. 识别文档结构
            document_structure = await self._identify_document_structure(cleaned_content)

            # 3. 基于语义进行分块
            if preserve_semantic_integrity:
                chunks = await self._semantic_chunking_with_integrity(
                    cleaned_content, document_structure, structure_template
                )
            else:
                chunks = await self._standard_semantic_chunking(
                    cleaned_content, document_structure, structure_template
                )

            # 4. 后处理和验证
            validated_chunks = await self._validate_and_enhance_chunks(chunks)

            logger.info(f"语义分块完成，生成 {len(validated_chunks)} 个分块")
            return validated_chunks

        except Exception as e:
            logger.error(f"语义分块失败: {e}")
            # 降级到简单分块
            return await self._fallback_chunking(content)

    def _preprocess_text(self, content: str) -> str:
        """预处理文本"""
        # 去除多余空白
        content = re.sub(r'\s+', ' ', content)

        # 规范化换行
        content = re.sub(r'\n\s*\n', '\n\n', content)

        # 去除特殊字符
        content = re.sub(r'[^\w\s\u4e00-\u9fff.,;:!?()[\]{}"\'=-]', ' ', content)

        return content.strip()

    async def _identify_document_structure(self, content: str) -> Dict[str, Any]:
        """识别文档结构"""
        try:
            # 使用AI识别文档结构
            structure_prompt = f"""
请分析以下学术论文文本，识别其结构组成：

文本内容（前2000字符）：
{content[:2000]}

请识别出以下结构组件的位置和内容：
1. Abstract/摘要
2. Introduction/引言
3. Methodology/方法
4. Results/结果
5. Discussion/讨论
6. Conclusion/结论
7. References/参考文献

对每个识别出的组件，请提供：
- start_position: 开始位置（字符索引）
- end_position: 结束位置（字符索引）
- confidence: 识别置信度（0-1）
- section_title: 章节标题

以JSON格式返回：
{{
    "sections": [
        {{
            "type": "methodology",
            "start_position": 100,
            "end_position": 500,
            "confidence": 0.9,
            "section_title": "实验方法"
        }}
    ],
    "document_type": "research_paper",
    "language": "zh/en"
}}
"""

            response = await self.ai_service.generate_completion(
                structure_prompt,
                model="gpt-3.5-turbo",
                max_tokens=1000,
                temperature=0.1
            )

            if response.get("success"):
                try:
                    structure = json.loads(response["content"])
                    return structure
                except json.JSONDecodeError:
                    logger.warning("文档结构识别返回格式错误，使用模式识别")

            # 降级到模式识别
            return self._pattern_based_structure_identification(content)

        except Exception as e:
            logger.error(f"文档结构识别失败: {e}")
            return self._pattern_based_structure_identification(content)

    def _pattern_based_structure_identification(self, content: str) -> Dict[str, Any]:
        """基于模式的结构识别"""
        sections = []

        # 常见章节标题模式
        section_patterns = {
            "methodology": [
                r"方法|method|methodology|experimental|procedure|材料.*方法",
                r"实验.*方法|experimental.*method|materials.*method"
            ],
            "results": [
                r"结果|results|findings|observations|数据.*分析",
                r"测试.*结果|performance.*results|characterization.*results"
            ],
            "preparation": [
                r"制备|preparation|synthesis|fabrication|样品.*制备",
                r"合成.*方法|synthesis.*method|preparation.*procedure"
            ],
            "characterization": [
                r"表征|characterization|analysis|测试.*表征",
                r"结构.*表征|morphology.*characterization|测试.*方法"
            ],
            "performance": [
                r"性能|performance|properties|效果.*评估",
                r"性能.*测试|performance.*evaluation|property.*assessment"
            ]
        }

        for section_type, patterns in section_patterns.items():
            for pattern in patterns:
                matches = list(re.finditer(pattern, content, re.IGNORECASE))
                for match in matches:
                    # 尝试找到章节内容的结束位置
                    start_pos = match.start()
                    end_pos = self._find_section_end(content, start_pos)

                    sections.append({
                        "type": section_type,
                        "start_position": start_pos,
                        "end_position": end_pos,
                        "confidence": 0.7,
                        "section_title": match.group()
                    })

        return {
            "sections": sections,
            "document_type": "research_paper",
            "language": "mixed"
        }

    def _find_section_end(self, content: str, start_pos: int) -> int:
        """查找章节结束位置"""
        # 查找下一个章节标题或文档结束
        next_section_patterns = [
            r"\n\s*\d+\.?\s*[A-Z]",  # 数字编号章节
            r"\n\s*[A-Z][A-Z\s]{10,}",  # 大写章节标题
            r"\n\s*参考文献|references|bibliography",  # 参考文献开始
            r"\n\s*致谢|acknowledgments?",  # 致谢部分
        ]

        search_start = start_pos + 100  # 从章节开始后100字符开始搜索
        min_end_pos = len(content)

        for pattern in next_section_patterns:
            match = re.search(pattern, content[search_start:], re.IGNORECASE)
            if match:
                end_pos = search_start + match.start()
                min_end_pos = min(min_end_pos, end_pos)

        # 确保章节至少有最小长度
        min_section_length = 300
        if min_end_pos - start_pos < min_section_length:
            min_end_pos = min(start_pos + min_section_length, len(content))

        return min_end_pos

    async def _semantic_chunking_with_integrity(
        self,
        content: str,
        document_structure: Dict[str, Any],
        structure_template: Optional[Dict] = None
    ) -> List[SemanticChunk]:
        """基于语义完整性的分块"""
        chunks = []

        # 按识别的章节进行分块
        sections = document_structure.get("sections", [])

        if not sections:
            # 如果没有识别出章节，使用模板驱动分块
            return await self._template_driven_chunking(content, structure_template)

        for i, section in enumerate(sections):
            section_content = content[section["start_position"]:section["end_position"]]

            if len(section_content) < self.min_chunk_length:
                continue

            # 如果章节过长，进行子分块（但保持语义完整性）
            if len(section_content) > self.max_chunk_length:
                sub_chunks = await self._split_section_semantically(
                    section_content, section, i
                )
                chunks.extend(sub_chunks)
            else:
                # 创建单个分块
                chunk = await self._create_semantic_chunk(
                    content=section_content,
                    chunk_type=ChunkType(section["type"]) if section["type"] in [e.value for e in ChunkType] else ChunkType.METHODOLOGY,
                    start_pos=section["start_position"],
                    end_pos=section["end_position"],
                    confidence=section.get("confidence", 0.7),
                    section_title=section.get("section_title"),
                    chunk_id=f"chunk_{i}"
                )
                chunks.append(chunk)

        return chunks

    async def _split_section_semantically(
        self,
        section_content: str,
        section_info: Dict,
        section_index: int
    ) -> List[SemanticChunk]:
        """语义分割长章节"""
        chunks = []

        # 识别子章节或段落边界
        paragraph_boundaries = self._find_paragraph_boundaries(section_content)

        current_chunk_start = 0
        current_chunk_content = ""

        for boundary in paragraph_boundaries:
            paragraph = section_content[current_chunk_start:boundary]

            # 检查添加这个段落是否会超过最大长度
            if len(current_chunk_content + paragraph) > self.max_chunk_length and current_chunk_content:
                # 创建当前分块
                chunk = await self._create_semantic_chunk(
                    content=current_chunk_content,
                    chunk_type=ChunkType(section_info["type"]) if section_info["type"] in [e.value for e in ChunkType] else ChunkType.METHODOLOGY,
                    start_pos=section_info["start_position"] + current_chunk_start - len(current_chunk_content),
                    end_pos=section_info["start_position"] + current_chunk_start,
                    confidence=section_info.get("confidence", 0.7),
                    section_title=section_info.get("section_title"),
                    chunk_id=f"chunk_{section_index}_{len(chunks)}"
                )
                chunks.append(chunk)

                # 重置当前分块（包含少量重叠）
                overlap_size = int(len(current_chunk_content) * self.overlap_ratio)
                current_chunk_content = current_chunk_content[-overlap_size:] + paragraph
                current_chunk_start = boundary
            else:
                current_chunk_content += paragraph

        # 创建最后一个分块
        if current_chunk_content:
            chunk = await self._create_semantic_chunk(
                content=current_chunk_content,
                chunk_type=ChunkType(section_info["type"]) if section_info["type"] in [e.value for e in ChunkType] else ChunkType.METHODOLOGY,
                start_pos=section_info["start_position"] + current_chunk_start - len(current_chunk_content),
                end_pos=section_info["end_position"],
                confidence=section_info.get("confidence", 0.7),
                section_title=section_info.get("section_title"),
                chunk_id=f"chunk_{section_index}_{len(chunks)}"
            )
            chunks.append(chunk)

        return chunks

    def _find_paragraph_boundaries(self, content: str) -> List[int]:
        """查找段落边界"""
        boundaries = []

        # 查找自然段落边界
        paragraph_patterns = [
            r'\n\s*\n',          # 双换行
            r'\.\s*\n\s*[A-Z]',  # 句号后的新行
            r'。\s*\n',          # 中文句号后换行
            r'\n\s*\d+\)',       # 编号列表
            r'\n\s*[A-Za-z]\)', # 字母列表
        ]

        for pattern in paragraph_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                boundaries.append(match.end())

        # 去重并排序
        boundaries = sorted(list(set(boundaries)))

        # 确保包含内容结束位置
        if boundaries[-1] != len(content):
            boundaries.append(len(content))

        return boundaries

    async def _template_driven_chunking(
        self,
        content: str,
        structure_template: Optional[Dict] = None
    ) -> List[SemanticChunk]:
        """基于模板的分块"""
        chunks = []

        # 如果没有提供模板，使用默认模板
        if not structure_template:
            structure_template = self.template.field_templates

        # 对每个模板字段类型进行分块
        for field_type, template_config in structure_template.items():
            relevant_content = self._extract_relevant_content(
                content, template_config.get("patterns", [])
            )

            if relevant_content and len(relevant_content) >= self.min_chunk_length:
                chunk = await self._create_template_based_chunk(
                    content=relevant_content,
                    field_type=field_type,
                    template_config=template_config,
                    chunk_id=f"template_{field_type}"
                )
                if chunk:
                    chunks.append(chunk)

        # 如果基于模板没有生成足够的分块，使用滑动窗口分块
        if len(chunks) < 2:
            chunks.extend(await self._sliding_window_chunking(content))

        return chunks

    def _extract_relevant_content(self, content: str, patterns: List[str]) -> str:
        """提取与模式相关的内容"""
        relevant_segments = []

        for pattern in patterns:
            matches = list(re.finditer(pattern, content, re.IGNORECASE))
            for match in matches:
                # 扩展匹配区域以获取完整语义
                start = max(0, match.start() - 200)
                end = min(len(content), match.end() + 800)
                segment = content[start:end]
                relevant_segments.append(segment)

        # 合并重叠的段落并去重
        merged_content = self._merge_overlapping_segments(relevant_segments)
        return merged_content

    def _merge_overlapping_segments(self, segments: List[str]) -> str:
        """合并重叠的文本段落"""
        if not segments:
            return ""

        # 简单合并（可以进一步优化）
        unique_segments = []
        for segment in segments:
            if not any(segment in existing for existing in unique_segments):
                unique_segments.append(segment)

        return "\n\n".join(unique_segments)

    async def _create_semantic_chunk(
        self,
        content: str,
        chunk_type: ChunkType,
        start_pos: int,
        end_pos: int,
        confidence: float,
        section_title: Optional[str] = None,
        chunk_id: str = ""
    ) -> SemanticChunk:
        """创建语义分块"""

        # 提取结构化数据
        structured_data = await self._extract_structured_data(content, chunk_type)

        # 计算页码（简化实现）
        page_numbers = self._estimate_page_numbers(start_pos, end_pos)

        chunk = SemanticChunk(
            chunk_id=chunk_id,
            chunk_type=chunk_type,
            content=content,
            structured_data=structured_data,
            confidence=confidence,
            start_position=start_pos,
            end_position=end_pos,
            page_numbers=page_numbers,
            section_title=section_title
        )

        return chunk

    async def _create_template_based_chunk(
        self,
        content: str,
        field_type: str,
        template_config: Dict,
        chunk_id: str
    ) -> Optional[SemanticChunk]:
        """创建基于模板的分块"""
        try:
            chunk_type = ChunkType(field_type) if field_type in [e.value for e in ChunkType] else ChunkType.METHODOLOGY

            # 提取结构化数据
            structured_data = await self._extract_template_structured_data(
                content, template_config
            )

            chunk = SemanticChunk(
                chunk_id=chunk_id,
                chunk_type=chunk_type,
                content=content,
                structured_data=structured_data,
                confidence=0.8,
                start_position=0,  # 模板分块的位置信息需要重新计算
                end_position=len(content),
                page_numbers=[1]  # 简化实现
            )

            return chunk

        except Exception as e:
            logger.error(f"创建模板分块失败 {field_type}: {e}")
            return None

    async def _extract_structured_data(
        self,
        content: str,
        chunk_type: ChunkType
    ) -> Dict[str, Any]:
        """提取分块的结构化数据"""
        try:
            # 根据分块类型选择合适的提取策略
            if chunk_type == ChunkType.METHODOLOGY:
                return await self._extract_methodology_data(content)
            elif chunk_type == ChunkType.RESULTS:
                return await self._extract_results_data(content)
            elif chunk_type == ChunkType.PREPARATION:
                return await self._extract_preparation_data(content)
            elif chunk_type == ChunkType.CHARACTERIZATION:
                return await self._extract_characterization_data(content)
            elif chunk_type == ChunkType.PERFORMANCE:
                return await self._extract_performance_data(content)
            else:
                return await self._extract_general_data(content)

        except Exception as e:
            logger.error(f"结构化数据提取失败: {e}")
            return {"raw_content": content[:500]}  # 降级返回原始内容摘要

    async def _extract_methodology_data(self, content: str) -> Dict[str, Any]:
        """提取方法学结构化数据"""
        extraction_prompt = f"""
请从以下方法学内容中提取结构化信息：

内容：
{content[:1500]}

请提取以下信息（如果存在）：
1. materials_used: 使用的材料列表
2. equipment_required: 所需设备
3. process_parameters: 工艺参数
4. synthesis_conditions: 合成条件
5. characterization_methods: 表征方法

以JSON格式返回：
{{
    "materials_used": ["材料1", "材料2"],
    "equipment_required": ["设备1", "设备2"],
    "process_parameters": {{"温度": "XXX", "压力": "XXX"}},
    "synthesis_conditions": {{"时间": "XXX", "气氛": "XXX"}},
    "characterization_methods": ["方法1", "方法2"]
}}

如果某些信息不存在，请返回空列表或空字典。
"""

        response = await self.ai_service.generate_completion(
            extraction_prompt,
            model="gpt-3.5-turbo",
            max_tokens=800,
            temperature=0.1
        )

        if response.get("success"):
            try:
                return json.loads(response["content"])
            except json.JSONDecodeError:
                pass

        # 降级到模式匹配
        return self._pattern_extract_methodology(content)

    def _pattern_extract_methodology(self, content: str) -> Dict[str, Any]:
        """使用模式匹配提取方法学数据"""
        data = {
            "materials_used": [],
            "equipment_required": [],
            "process_parameters": {},
            "synthesis_conditions": {},
            "characterization_methods": []
        }

        # 提取材料
        material_patterns = [
            r"([A-Za-z0-9]+(?:[A-Za-z0-9\-])*)\s*(?:powder|solution|precursor|化学试剂)",
            r"使用[了]?([^，。]+)(?:作为|作|做)[^，。]*材料"
        ]

        for pattern in material_patterns:
            matches = re.findall(pattern, content)
            data["materials_used"].extend([match.strip() for match in matches if match.strip()])

        # 提取设备
        equipment_patterns = [
            r"使用[了]?([^，。]*(?:仪器|设备|装置|系统))",
            r"([A-Za-z\-\s]+(?:spectrometer|microscope|diffractometer|analyzer))"
        ]

        for pattern in equipment_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            data["equipment_required"].extend([match.strip() for match in matches if match.strip()])

        # 提取参数
        parameter_patterns = [
            r"温度[为:]?\s*(\d+(?:\.\d+)?)\s*[°℃]?C",
            r"压力[为:]?\s*(\d+(?:\.\d+)?)\s*(?:MPa|Pa|bar)",
            r"时间[为:]?\s*(\d+(?:\.\d+)?)\s*(?:h|min|小时|分钟)"
        ]

        for pattern in parameter_patterns:
            matches = re.findall(pattern, content)
            if matches:
                if "温度" in pattern:
                    data["process_parameters"]["temperature"] = matches[0] + "°C"
                elif "压力" in pattern:
                    data["process_parameters"]["pressure"] = matches[0]
                elif "时间" in pattern:
                    data["synthesis_conditions"]["time"] = matches[0]

        return data

    async def _extract_results_data(self, content: str) -> Dict[str, Any]:
        """提取结果数据"""
        # 简化实现，实际应该更复杂
        return {
            "performance_metrics": [],
            "measurement_results": {},
            "test_conditions": {},
            "data_analysis": "",
            "statistical_significance": None
        }

    async def _extract_preparation_data(self, content: str) -> Dict[str, Any]:
        """提取制备数据"""
        return {
            "precursor_materials": [],
            "synthesis_method": "",
            "process_conditions": {},
            "reaction_parameters": {},
            "purification_steps": []
        }

    async def _extract_characterization_data(self, content: str) -> Dict[str, Any]:
        """提取表征数据"""
        return {
            "characterization_techniques": [],
            "instrument_specifications": {},
            "measurement_conditions": {},
            "sample_preparation": "",
            "data_processing": ""
        }

    async def _extract_performance_data(self, content: str) -> Dict[str, Any]:
        """提取性能数据"""
        return {
            "performance_metrics": [],
            "optimization_parameters": {},
            "comparative_analysis": "",
            "improvement_factors": [],
            "validation_methods": []
        }

    async def _extract_general_data(self, content: str) -> Dict[str, Any]:
        """提取通用数据"""
        return {
            "content_summary": content[:200],
            "key_entities": [],
            "technical_terms": [],
            "numerical_data": []
        }

    async def _extract_template_structured_data(
        self,
        content: str,
        template_config: Dict
    ) -> Dict[str, Any]:
        """基于模板配置提取结构化数据"""
        structured_fields = template_config.get("structured_fields", [])
        data = {}

        for field in structured_fields:
            # 简化实现：为每个字段创建空值
            if "parameters" in field or "conditions" in field:
                data[field] = {}
            else:
                data[field] = []

        return data

    def _estimate_page_numbers(self, start_pos: int, end_pos: int) -> List[int]:
        """估算页码（简化实现）"""
        # 假设平均每页3000字符
        chars_per_page = 3000
        start_page = max(1, start_pos // chars_per_page + 1)
        end_page = max(start_page, end_pos // chars_per_page + 1)
        return list(range(start_page, end_page + 1))

    async def _sliding_window_chunking(self, content: str) -> List[SemanticChunk]:
        """滑动窗口分块（降级策略）"""
        chunks = []
        window_size = self.max_chunk_length
        overlap = int(window_size * self.overlap_ratio)

        for i in range(0, len(content), window_size - overlap):
            end_pos = min(i + window_size, len(content))
            chunk_content = content[i:end_pos]

            if len(chunk_content) >= self.min_chunk_length:
                chunk = SemanticChunk(
                    chunk_id=f"sliding_{i}",
                    chunk_type=ChunkType.METHODOLOGY,  # 默认类型
                    content=chunk_content,
                    structured_data={"sliding_window": True},
                    confidence=0.5,  # 低置信度
                    start_position=i,
                    end_position=end_pos,
                    page_numbers=self._estimate_page_numbers(i, end_pos)
                )
                chunks.append(chunk)

        return chunks

    async def _validate_and_enhance_chunks(
        self,
        chunks: List[SemanticChunk]
    ) -> List[SemanticChunk]:
        """验证和增强分块"""
        validated_chunks = []

        for chunk in chunks:
            # 验证分块质量
            if await self._validate_chunk_quality(chunk):
                # 增强分块信息
                enhanced_chunk = await self._enhance_chunk(chunk)
                validated_chunks.append(enhanced_chunk)
            else:
                logger.warning(f"分块质量不达标，跳过: {chunk.chunk_id}")

        return validated_chunks

    async def _validate_chunk_quality(self, chunk: SemanticChunk) -> bool:
        """验证分块质量"""
        # 长度检查
        if len(chunk.content) < self.min_chunk_length:
            return False

        # 置信度检查
        if chunk.confidence < self.confidence_threshold:
            return False

        # 内容质量检查（简化）
        if not chunk.content.strip():
            return False

        return True

    async def _enhance_chunk(self, chunk: SemanticChunk) -> SemanticChunk:
        """增强分块信息"""
        # 简化实现：可以添加更多增强逻辑
        return chunk

    async def _fallback_chunking(self, content: str) -> List[SemanticChunk]:
        """降级分块策略"""
        logger.warning("使用降级分块策略")
        return await self._sliding_window_chunking(content)


# 工厂函数
def create_semantic_chunker(ai_service: Optional[AIService] = None) -> SemanticChunker:
    """创建语义分块器实例"""
    return SemanticChunker(ai_service)