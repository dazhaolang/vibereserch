"""
PDF处理服务 - 集成MinerU
"""

import os
import asyncio
import subprocess
from typing import Dict, List, Optional
from pathlib import Path
import json
import tempfile
from loguru import logger

from app.core.config import settings

class PDFProcessor:
    """PDF处理器 - 使用MinerU"""

    def __init__(self):
        self.upload_dir = Path(settings.upload_path)
        self.upload_dir.mkdir(exist_ok=True)

    async def process_pdf(self, file_path: str) -> Dict:
        """
        处理PDF文件，提取结构化内容

        Args:
            file_path: PDF文件路径

        Returns:
            处理结果字典
        """
        try:
            # 验证文件存在
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"PDF文件不存在: {file_path}")

            # 创建临时输出目录
            with tempfile.TemporaryDirectory() as temp_dir:
                output_dir = Path(temp_dir) / "output"
                output_dir.mkdir(exist_ok=True)

                # 使用MinerU处理PDF
                result = await self._run_mineru(file_path, str(output_dir))

                if result["success"]:
                    # 解析MinerU输出
                    parsed_content = await self._parse_mineru_output(str(output_dir))

                    return {
                        "success": True,
                        "content": parsed_content,
                        "metadata": result.get("metadata", {}),
                        "file_info": {
                            "size": os.path.getsize(file_path),
                            "pages": parsed_content.get("total_pages", 0)
                        }
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("error", "PDF处理失败"),
                        "content": None
                    }

        except Exception as e:
            logger.error(f"PDF处理异常: {e}")
            return {
                "success": False,
                "error": str(e),
                "content": None
            }

    async def _run_mineru(self, pdf_path: str, output_dir: str) -> Dict:
        """运行MinerU处理PDF"""
        try:
            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)

            # 尝试不同的magic-pdf路径
            magic_pdf_paths = [
                "/root/raggar/raggar/backend/venv/bin/magic-pdf",  # 虚拟环境路径
                "magic-pdf",  # 系统路径
                "./venv/bin/magic-pdf"  # 相对路径
            ]

            magic_pdf_cmd = None
            for path in magic_pdf_paths:
                if os.path.exists(path) or path == "magic-pdf":
                    magic_pdf_cmd = path
                    break

            if not magic_pdf_cmd:
                return {
                    "success": False,
                    "error": "magic-pdf 命令未找到"
                }

            # MinerU命令 - 使用正确的调用方式
            cmd = [
                magic_pdf_cmd,
                "--path", pdf_path,
                "--output-dir", output_dir,
                "--method", "auto"
            ]

            # 异步执行命令
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=output_dir
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return {
                    "success": True,
                    "stdout": stdout.decode(),
                    "metadata": {
                        "processor": "mineru",
                        "version": "1.3.12",
                        "command": magic_pdf_cmd
                    }
                }
            else:
                logger.warning(f"MinerU处理警告: {stderr.decode()}")
                # 即使有警告，如果生成了输出文件也认为成功
                if os.listdir(output_dir):
                    return {
                        "success": True,
                        "stdout": stdout.decode(),
                        "stderr": stderr.decode(),
                        "metadata": {
                            "processor": "mineru",
                            "version": "1.3.12",
                            "command": magic_pdf_cmd
                        }
                    }
                else:
                    return {
                        "success": False,
                        "error": stderr.decode(),
                        "stdout": stdout.decode()
                    }

        except Exception as e:
            logger.error(f"MinerU执行失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _parse_mineru_output(self, output_dir: str) -> Dict:
        """解析MinerU输出结果"""
        try:
            output_path = Path(output_dir)

            # 查找MinerU生成的结果文件
            markdown_files = list(output_path.glob("**/*.md"))
            json_files = list(output_path.glob("**/*.json"))

            content = {
                "text_content": "",
                "structured_content": {},
                "images": [],
                "tables": [],
                "total_pages": 0
            }

            # 处理Markdown文件
            for md_file in markdown_files:
                with open(md_file, 'r', encoding='utf-8') as f:
                    md_content = f.read()
                    content["text_content"] += md_content + "\n\n"

            # 处理JSON元数据文件
            for json_file in json_files:
                with open(json_file, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)

                    # 提取结构化信息
                    if "pages" in json_data:
                        content["total_pages"] = len(json_data["pages"])

                    if "tables" in json_data:
                        content["tables"] = json_data["tables"]

                    if "images" in json_data:
                        content["images"] = json_data["images"]

                    content["structured_content"].update(json_data)

            return content

        except Exception as e:
            logger.error(f"解析MinerU输出失败: {e}")
            return {
                "text_content": "",
                "structured_content": {},
                "images": [],
                "tables": [],
                "total_pages": 0
            }

    async def process_pdf_async(self, file_path: str) -> Optional[str]:
        """
        异步处理PDF文件，返回文本内容

        Args:
            file_path: PDF文件路径

        Returns:
            提取的文本内容，失败时返回None
        """
        try:
            result = await self.process_pdf(file_path)
            if result["success"] and result["content"]:
                return result["content"].get("text_content", "")
            return None
        except Exception as e:
            logger.error(f"异步PDF处理失败: {e}")
            return None

    async def process_pdf_with_segments(self, file_path: str, structure_template: Optional[Dict] = None) -> Dict:
        """
        处理PDF并返回结构化段落 - 使用语义分块策略

        Args:
            file_path: PDF文件路径
            structure_template: 结构化模板

        Returns:
            包含文本内容和段落的结果字典
        """
        try:
            # 处理PDF获取内容
            result = await self.process_pdf(file_path)
            if not result["success"]:
                return result

            content = result["content"]
            segments = []

            # 使用语义分块策略
            if structure_template:
                segments = await self.extract_semantic_segments_with_template(content, structure_template)
            else:
                segments = await self.extract_semantic_segments_default(content)

            return {
                "success": True,
                "content": content,
                "segments": segments,
                "metadata": result.get("metadata", {}),
                "file_info": result.get("file_info", {})
            }

        except Exception as e:
            logger.error(f"PDF分段处理失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "content": None,
                "segments": []
            }

    async def extract_text_segments(self, content: Dict, structure_template: Dict) -> List[Dict]:
        """
        根据结构化模板提取文本段落

        Args:
            content: PDF解析内容
            structure_template: 轻结构化模板

        Returns:
            文本段落列表
        """
        segments = []
        text_content = content.get("text_content", "")

        if not text_content or not structure_template:
            return segments

        try:
            # 根据模板结构分段
            template_sections = structure_template.get("sections", [])

            for section in template_sections:
                section_name = section.get("name", "")
                keywords = section.get("keywords", [])

                # 基于关键词匹配提取相关段落
                relevant_paragraphs = self._extract_relevant_paragraphs(
                    text_content, keywords
                )

                for paragraph in relevant_paragraphs:
                    segments.append({
                        "segment_type": section_name,
                        "content": paragraph["text"],
                        "page_number": paragraph.get("page", 0),
                        "confidence": paragraph.get("confidence", 0.5)
                    })

            return segments

        except Exception as e:
            logger.error(f"文本分段失败: {e}")
            return []

    async def extract_semantic_segments_with_template(self, content: Dict, structure_template: Dict) -> List[Dict]:
        """
        基于结构化模板进行语义分块
        保持字段的语义完整性，不按长度截断
        """
        segments = []
        text_content = content.get("text_content", "")

        if not text_content or not structure_template:
            return segments

        try:
            # 根据模板结构进行语义分块
            template_sections = structure_template.get("sections", [])

            for section in template_sections:
                section_name = section.get("name", "")
                keywords = section.get("keywords", [])

                # 基于语义相关性提取完整字段
                semantic_segments = await self._extract_semantic_fields(
                    text_content, keywords, section_name
                )

                segments.extend(semantic_segments)

            logger.info(f"基于模板提取语义段落: {len(segments)} 个")
            return segments

        except Exception as e:
            logger.error(f"语义分块失败: {e}")
            return await self.extract_semantic_segments_default(content)

    async def extract_semantic_segments_default(self, content: Dict) -> List[Dict]:
        """
        默认语义分块策略
        基于文档结构识别，保持完整性
        """
        segments = []
        text_content = content.get("text_content", "")

        if not text_content:
            return segments

        try:
            # 使用语义分块器进行结构化分块
            from app.services.semantic_chunker import create_semantic_chunker

            semantic_chunker = create_semantic_chunker()
            semantic_chunks = await semantic_chunker.chunk_literature(
                content=text_content,
                preserve_semantic_integrity=True  # 保持语义完整性
            )

            # 转换为段落格式
            for chunk in semantic_chunks:
                segments.append({
                    "segment_type": chunk.chunk_type.value,
                    "content": chunk.content,
                    "page_number": chunk.page_numbers[0] if chunk.page_numbers else 1,
                    "confidence": chunk.confidence,
                    "structured_data": chunk.structured_data,
                    "section_title": chunk.section_title
                })

            logger.info(f"默认语义分块完成: {len(segments)} 个")
            return segments

        except Exception as e:
            logger.error(f"默认语义分块失败，使用降级策略: {e}")
            return self._fallback_paragraph_segments(text_content)

    async def _extract_semantic_fields(self, text: str, keywords: List[str], section_name: str) -> List[Dict]:
        """提取语义完整的字段，不按长度截断"""
        segments = []

        try:
            # 1. 基于关键词识别相关区域
            relevant_regions = self._identify_relevant_regions(text, keywords)

            # 2. 扩展到语义边界（完整句子、段落、章节）
            for region in relevant_regions:
                expanded_content = self._expand_to_semantic_boundary(
                    text, region["start"], region["end"]
                )

                if expanded_content and len(expanded_content.strip()) > 0:  # 移除长度限制
                    segments.append({
                        "segment_type": section_name,
                        "content": expanded_content.strip(),
                        "page_number": 1,  # 可以根据位置计算
                        "confidence": region["confidence"],
                        "semantic_complete": True  # 标记为语义完整
                    })

            return segments

        except Exception as e:
            logger.error(f"语义字段提取失败: {e}")
            return []

    def _identify_relevant_regions(self, text: str, keywords: List[str]) -> List[Dict]:
        """识别与关键词相关的文本区域"""
        regions = []

        for keyword in keywords:
            # 使用正则表达式匹配关键词及其上下文
            pattern = rf"(?i).{{0,200}}{re.escape(keyword)}.{{0,500}}"
            matches = list(re.finditer(pattern, text))

            for match in matches:
                confidence = 0.8 if len(matches) == 1 else 0.6  # 单独匹配置信度更高
                regions.append({
                    "start": match.start(),
                    "end": match.end(),
                    "confidence": confidence,
                    "keyword": keyword
                })

        # 合并重叠区域
        return self._merge_overlapping_regions(regions)

    def _expand_to_semantic_boundary(self, text: str, start: int, end: int) -> str:
        """扩展到语义边界，确保完整性"""
        # 向前扩展到句子开始
        expanded_start = start
        while expanded_start > 0 and text[expanded_start-1] not in '.!?。！？\n':
            expanded_start -= 1
            if start - expanded_start > 200:  # 防止过度扩展
                break

        # 向后扩展到句子结束
        expanded_end = end
        while expanded_end < len(text) and text[expanded_end] not in '.!?。！？\n':
            expanded_end += 1
            if expanded_end - end > 300:  # 防止过度扩展
                break

        return text[expanded_start:expanded_end]

    def _merge_overlapping_regions(self, regions: List[Dict]) -> List[Dict]:
        """合并重叠的区域"""
        if not regions:
            return []

        # 按开始位置排序
        sorted_regions = sorted(regions, key=lambda x: x["start"])
        merged = [sorted_regions[0]]

        for current in sorted_regions[1:]:
            last = merged[-1]

            # 如果重叠，合并区域
            if current["start"] <= last["end"] + 100:  # 允许100字符的间隔
                merged[-1] = {
                    "start": last["start"],
                    "end": max(last["end"], current["end"]),
                    "confidence": max(last["confidence"], current["confidence"]),
                    "keyword": f"{last['keyword']}, {current['keyword']}"
                }
            else:
                merged.append(current)

        return merged

    def _fallback_paragraph_segments(self, text: str) -> List[Dict]:
        """降级段落分块策略（保持向后兼容）"""
        segments = []
        paragraphs = text.split('\n\n')

        for i, paragraph in enumerate(paragraphs):
            # 移除硬编码的长度限制，改为检查是否有实际内容
            content = paragraph.strip()
            if content:  # 只要有内容就保留
                segments.append({
                    "segment_type": "paragraph",
                    "content": content,
                    "page_number": 1,
                    "confidence": 0.7,
                    "fallback_method": True
                })

        logger.warning(f"使用降级分块策略，生成 {len(segments)} 个段落")
        return segments