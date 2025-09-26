"""
文献相关的Pydantic模型
确保文献数据的类型安全和一致性
"""

from pydantic import BaseModel, Field, HttpUrl, model_validator, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import re

# ============================================
# 枚举类型
# ============================================

class LiteratureSourceEnum(str, Enum):
    RESEARCHRABBIT = "researchrabbit"
    GOOGLE_SCHOLAR = "google_scholar"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    PUBMED = "pubmed"
    ARXIV = "arxiv"
    CROSSREF = "crossref"
    MANUAL_UPLOAD = "manual_upload"

class LiteratureStatusEnum(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ParsingStatusEnum(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class SegmentTypeEnum(str, Enum):
    INTRODUCTION = "introduction"
    METHODOLOGY = "methodology"
    RESULTS = "results"
    DISCUSSION = "discussion"
    CONCLUSION = "conclusion"
    ABSTRACT = "abstract"
    REFERENCES = "references"
    CUSTOM = "custom"

# ============================================
# 请求模型
# ============================================

class LiteratureCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=1000, description="文献标题")
    authors: List[str] = Field(..., min_length=1, max_length=20, description="作者列表")
    abstract: Optional[str] = Field(None, max_length=5000, description="摘要")
    keywords: Optional[List[str]] = Field(None, max_length=20, description="关键词")
    
    # 发表信息
    journal: Optional[str] = Field(None, max_length=500, description="期刊名称")
    publication_year: Optional[int] = Field(None, ge=1900, le=2030, description="发表年份")
    volume: Optional[str] = Field(None, max_length=50)
    issue: Optional[str] = Field(None, max_length=50)
    pages: Optional[str] = Field(None, max_length=100)
    doi: Optional[str] = Field(None, max_length=200)
    
    # 来源信息
    source_platform: Optional[LiteratureSourceEnum] = LiteratureSourceEnum.MANUAL_UPLOAD
    source_url: Optional[HttpUrl] = None
    pdf_url: Optional[HttpUrl] = None
    
    # 项目关联
    project_id: int = Field(..., description="项目ID")
    
    @field_validator("authors", mode="before")
    def validate_authors(cls, value):
        if not value or len(value) == 0:
            raise ValueError("至少需要一个作者")
        cleaned_authors: List[str] = []
        for author in value:
            author_str = str(author).strip()
            if author_str:
                cleaned_authors.append(author_str)
        return cleaned_authors

    @field_validator("keywords", mode="before")
    def validate_keywords(cls, value):
        if value:
            cleaned_keywords: List[str] = []
            for keyword in value:
                keyword_str = str(keyword).strip()
                if keyword_str:
                    cleaned_keywords.append(keyword_str.lower())
            return cleaned_keywords
        return value

class LiteratureUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=1000)
    authors: Optional[List[str]] = Field(None, min_length=1, max_length=20)
    abstract: Optional[str] = Field(None, max_length=5000)
    keywords: Optional[List[str]] = Field(None, max_length=20)
    journal: Optional[str] = Field(None, max_length=500)
    publication_year: Optional[int] = Field(None, ge=1900, le=2030)
    tags: Optional[List[str]] = Field(None, max_length=10)
    category: Optional[str] = Field(None, max_length=100)

class LiteratureSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500, description="搜索查询")
    project_id: Optional[int] = None
    filters: Optional[Dict[str, Any]] = None
    sort_by: Optional[str] = Field("relevance", description="排序字段")
    sort_order: Optional[str] = Field("desc", pattern="^(asc|desc)$")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    search_mode: Optional[str] = Field("hybrid", pattern="^(keyword|semantic|hybrid)$")

class AILiteratureSearchRequest(BaseModel):
    """AI文献搜索请求模型"""
    project_id: int = Field(..., description="项目ID")
    query: str = Field(..., min_length=2, max_length=500, description="搜索查询")
    max_results: Optional[int] = Field(20, ge=1, le=100, description="最大结果数量")

class LiteratureCollectionRequest(BaseModel):
    project_id: int = Field(..., description="项目ID")
    keywords: List[str] = Field(..., min_length=1, max_length=10, description="搜索关键词")
    max_count: Optional[int] = Field(100, ge=1, le=5000, description="最大采集数量")
    sources: Optional[List[LiteratureSourceEnum]] = None
    enable_ai_screening: bool = Field(True, description="是否启用AI初筛")
    quality_threshold: Optional[float] = Field(6.0, ge=0, le=10, description="质量阈值")

# ============================================
# 响应模型
# ============================================

class LiteratureSegmentResponse(BaseModel):
    id: int
    literature_id: int
    segment_type: SegmentTypeEnum
    section_title: Optional[str]
    content: str
    original_text: Optional[str]
    page_number: Optional[int]
    paragraph_index: Optional[int]
    structured_data: Optional[Dict[str, Any]]
    extraction_confidence: float
    created_at: datetime
    
    class Config:
        from_attributes = True

class LiteratureResponse(BaseModel):
    id: int
    # 基础信息
    title: str
    authors: List[str]
    abstract: Optional[str]
    keywords: Optional[List[str]]
    
    # 发表信息
    journal: Optional[str]
    publication_year: Optional[int]
    volume: Optional[str]
    issue: Optional[str]
    pages: Optional[str]
    doi: Optional[str]
    
    # 来源信息
    source_platform: Optional[str]
    source_url: Optional[str]
    pdf_url: Optional[str]
    pdf_path: Optional[str] = None  # 前端需要的字段
    
    # 处理状态  
    status: Optional[str] = None  # 前端需要的字段
    parsing_status: ParsingStatusEnum
    parsed_content: Optional[str] = None  # 前端需要的字段
    
    # 文献质量评估
    citation_count: int
    impact_factor: Optional[float]
    quality_score: Optional[float]
    
    # 文件处理状态
    is_downloaded: bool
    is_parsed: bool
    
    # 文件信息
    file_path: Optional[str]
    file_size: Optional[int]
    file_hash: Optional[str]
    
    # 时间戳
    created_at: datetime
    updated_at: Optional[datetime]
    
    # 关联数据
    segments: Optional[List[LiteratureSegmentResponse]] = None
    projects: Optional[List[Dict]] = None  # 前端需要的关联项目
    
    # 项目特定字段 - 前端扩展字段
    relevance_score: Optional[float] = None
    is_selected: Optional[bool] = None  # 前端需要的批量操作字段
    is_starred: Optional[bool] = None
    tags: Optional[List[str]] = None
    category: Optional[str] = None
    
    class Config:
        from_attributes = True

class LiteratureListResponse(BaseModel):
    id: int
    title: str
    authors: List[str]
    journal: Optional[str]
    publication_year: Optional[int]
    citation_count: int
    quality_score: Optional[float]
    relevance_score: Optional[float]
    parsing_status: ParsingStatusEnum
    tags: Optional[List[str]]
    category: Optional[str]
    created_at: datetime
    is_starred: Optional[bool] = None

    class Config:
        from_attributes = True


class LiteraturePageResponse(BaseModel):
    items: List[LiteratureResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class LiteratureSearchResponse(BaseModel):
    items: List[LiteratureListResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    search_time_ms: float
    search_mode: str

class LiteratureCollectionResponse(BaseModel):
    task_id: int
    message: str
    estimated_duration: int
    collection_config: Dict[str, Any]

class LiteratureStatisticsResponse(BaseModel):
    total_literature: int
    processed_literature: int
    pending_literature: int
    failed_literature: int
    processing_progress: float
    total_segments: int
    avg_quality_score: float
    year_distribution: List[Dict[str, Any]]
    journal_distribution: List[Dict[str, Any]]
    source_distribution: List[Dict[str, Any]]
    category_distribution: List[Dict[str, Any]]

class LiteratureStatsResponse(BaseModel):
    """V2架构统计响应 - 用于共享文献库统计"""
    total_literature: int
    processed_literature: int
    processing_rate: float
    pending_tasks: int
    running_tasks: int
    storage_saved: Dict[str, Any]

# ============================================
# 批量操作模型
# ============================================

class BatchTagRequest(BaseModel):
    literature_ids: List[int] = Field(..., min_length=1, max_length=1000)
    tags: List[str] = Field(..., min_length=1, max_length=10)
    action: str = Field("add", pattern="^(add|remove|replace)$")

class BatchCategorizeRequest(BaseModel):
    literature_ids: List[int] = Field(..., min_length=1, max_length=1000)
    category: str = Field(..., min_length=1, max_length=100)

class BatchMoveRequest(BaseModel):
    literature_ids: List[int] = Field(..., min_length=1, max_length=1000)
    target_project_id: int = Field(..., description="目标项目ID")

class BatchExportRequest(BaseModel):
    literature_ids: List[int] = Field(..., min_length=1, max_length=1000)
    format: str = Field("json", pattern="^(json|csv|bibtex|ris|excel)$")
    include_options: Optional[Dict[str, bool]] = None

class BatchOperationResponse(BaseModel):
    success: bool
    message: str
    processed_count: int
    failed_count: int
    failed_items: Optional[List[Dict[str, Any]]] = None
    result: Optional[Any] = None
    operation_id: Optional[str] = None

# ============================================
# 文献分析模型
# ============================================

class LiteratureAnalysisRequest(BaseModel):
    literature_id: int = Field(..., description="文献ID")
    analysis_type: str = Field(..., pattern="^(summary|keywords|methodology|insights)$")
    custom_prompt: Optional[str] = Field(None, max_length=1000)

class LiteratureAnalysisResponse(BaseModel):
    literature_id: int
    analysis_type: str
    result: Dict[str, Any]
    confidence_score: float
    processing_time_ms: float
    model_used: str
    created_at: datetime

# ============================================
# 文献导入模型
# ============================================

class LiteratureImportRequest(BaseModel):
    format: str = Field(..., pattern="^(bibtex|ris|csv|json)$")
    project_id: int = Field(..., description="目标项目ID")
    file_content: str = Field(..., description="文件内容")
    import_options: Optional[Dict[str, bool]] = None

class LiteratureImportResponse(BaseModel):
    success: bool
    imported_count: int
    skipped_count: int
    error_count: int
    imported_literature: List[LiteratureListResponse]
    errors: Optional[List[Dict[str, str]]] = None
    warnings: Optional[List[str]] = None

# ============================================
# 验证函数
# ============================================

def validate_literature_data(data: dict) -> Dict[str, Any]:
    """验证文献数据的完整性和有效性"""
    errors = []
    warnings = []
    
    # 必需字段检查
    required_fields = ['title', 'authors']
    for field in required_fields:
        if not data.get(field):
            errors.append(f"缺少必需字段: {field}")
    
    # 数据质量检查
    if data.get('title') and len(data['title']) < 10:
        warnings.append("标题过短，可能影响搜索效果")
    
    if data.get('abstract') and len(data['abstract']) < 100:
        warnings.append("摘要过短，可能影响分析质量")
    
    if data.get('publication_year'):
        current_year = datetime.now().year
        if data['publication_year'] > current_year:
            errors.append("发表年份不能超过当前年份")
        elif data['publication_year'] < 1900:
            warnings.append("发表年份过早，请确认数据准确性")
    
    # DOI格式验证
    if data.get('doi'):
        doi_pattern = r'^10\.\d{4,}/[-._;()/:\w\[\]]+$'
        if not re.match(doi_pattern, data['doi']):
            warnings.append("DOI格式可能不正确")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'quality_score': calculate_data_quality_score(data, errors, warnings)
    }

def calculate_data_quality_score(data: dict, errors: list, warnings: list) -> float:
    """计算数据质量分数"""
    base_score = 10.0
    
    # 错误扣分
    base_score -= len(errors) * 2.0
    
    # 警告扣分
    base_score -= len(warnings) * 0.5
    
    # 完整性加分
    completeness_fields = ['abstract', 'journal', 'publication_year', 'doi', 'keywords']
    completeness_score = sum(1 for field in completeness_fields if data.get(field))
    base_score += (completeness_score / len(completeness_fields)) * 2.0
    
    return max(0.0, min(10.0, base_score))

# 新增：文献统计响应模型
class LiteratureProjectStatisticsResponse(BaseModel):
    """项目文献统计响应模型"""
    total_literature: int
    processed_literature: int
    processing_rate: float
    total_segments: int
    unprocessed_literature: int
    storage_saved: Dict[str, Any]

# 新增：文献段落响应模型
class LiteratureSegmentItem(BaseModel):
    """单个文献段落项"""
    id: int
    segment_type: str
    content: str
    order_index: int
    embedding_status: Optional[str] = None
    created_at: str

class LiteratureSegmentsResponse(BaseModel):
    """文献段落列表响应模型"""
    segments: List[LiteratureSegmentItem]

# ============================================
# 三模式API基础模型 (Base Models for Three-Mode API)
# ============================================

class ModeRequestBase(BaseModel):
    """三模式请求基类 - 包含args和kwargs字段以解决422错误"""
    query: str = Field(..., min_length=1, max_length=500, description="查询字符串")
    args: Optional[List[Any]] = Field(default_factory=list, description="位置参数列表")
    kwargs: Optional[Dict[str, Any]] = Field(default_factory=dict, description="关键字参数字典")

class SearchLibraryModeRequest(ModeRequestBase):
    """搜索建库模式请求 - 对应 POST /api/literature/search-and-build-library"""
    project_id: int = Field(..., description="项目ID")
    max_papers: Optional[int] = Field(50, ge=1, le=1000, description="最大文献数量")
    processing_method: Optional[str] = Field("standard", description="处理方式")
    keywords: Optional[List[str]] = Field(None, description="关键词列表")
    max_results: Optional[int] = Field(200, ge=1, le=5000, description="最大搜索结果")
    enable_ai_filtering: Optional[bool] = Field(True, description="启用AI筛选")
    enable_pdf_processing: Optional[bool] = Field(True, description="启用PDF处理")
    enable_structured_extraction: Optional[bool] = Field(True, description="启用结构化提取")
    quality_threshold: Optional[float] = Field(6.0, ge=0, le=10, description="质量阈值")
    batch_size: Optional[int] = Field(10, ge=1, le=50, description="批处理大小")
    max_concurrent_downloads: Optional[int] = Field(5, ge=1, le=20, description="最大并发下载数")

class AISearchModeRequest(ModeRequestBase):
    """AI搜索RAG模式请求 - 对应 POST /api/literature/ai-search"""
    project_id: Optional[int] = Field(None, description="项目ID（可选）")
    search_type: Optional[str] = Field("rag", description="搜索类型")
    similarity_threshold: Optional[float] = Field(0.7, ge=0.0, le=1.0, description="相似度阈值")
    max_results: Optional[int] = Field(20, ge=1, le=100, description="最大结果数量")

class AutoResearchModeRequest(ModeRequestBase):
    """自动研究工作流模式请求 - 对应 POST /api/workflow/auto-research"""
    project_id: int = Field(..., description="项目ID")
    research_scope: Optional[str] = Field("comprehensive", description="研究范围")
    max_iterations: Optional[int] = Field(3, ge=1, le=10, description="最大迭代次数")
    max_results: Optional[int] = Field(20, ge=1, le=100, description="最大结果数量")
