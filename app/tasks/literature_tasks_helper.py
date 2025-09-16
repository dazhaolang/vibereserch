"""
文献处理任务的辅助函数
"""

from loguru import logger
from sqlalchemy.orm import Session

from app.models.literature import Literature, LiteratureSegment
from app.models.project import Project
from app.services.pdf_processor import PDFProcessor


async def create_basic_segments(literature: Literature, db: Session, project: Project):
    """基于摘要和标题创建基本文献段落"""
    try:
        # 基于摘要和标题生成结构化内容
        text_content = f"标题: {literature.title}\n\n摘要: {literature.abstract or ''}"
        
        if project.structure_template:
            pdf_processor = PDFProcessor()
            extraction_result = await pdf_processor.extract_text_segments(
                {"text_content": text_content},
                project.structure_template
            )
            
            # 保存文献段落
            for segment_data in extraction_result:
                segment = LiteratureSegment(
                    literature_id=literature.id,
                    segment_type=segment_data.get("segment_type", "general"),
                    content=segment_data.get("content", ""),
                    page_number=segment_data.get("page_number", 1),
                    extraction_confidence=segment_data.get("confidence", 0.5),
                    structured_data={"source": "abstract_title"}
                )
                db.add(segment)
        else:
            # 没有模板时，创建简单段落
            if literature.abstract:
                segment = LiteratureSegment(
                    literature_id=literature.id,
                    segment_type="abstract",
                    content=literature.abstract,
                    page_number=1,
                    extraction_confidence=0.9,
                    structured_data={"source": "abstract"}
                )
                db.add(segment)
        
        # 标记文献已处理
        literature.is_parsed = True
        literature.parsing_status = "completed"
        literature.parsed_content = text_content
        
    except Exception as e:
        logger.error(f"创建基本段落失败: {e}")
        literature.parsing_status = "failed"