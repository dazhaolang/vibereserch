"""
应用配置管理
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os

class Settings(BaseSettings):
    # 应用基础配置
    app_name: str = "科研文献智能分析平台"
    debug: bool = True
    log_level: str = "INFO"
    
    # 数据库配置
    database_url: str = Field(
        default="mysql://raggar:raggar123@localhost:3306/research_platform",
        description="MySQL数据库连接URL，生产环境应从环境变量获取"
    )
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis连接URL"
    )

    # Elasticsearch配置
    elasticsearch_url: str = Field(
        default="http://localhost:9200",
        description="Elasticsearch连接URL"
    )
    elasticsearch_index_prefix: str = Field(
        default="raggar_",
        description="Elasticsearch索引名前缀"
    )
    
    # JWT配置
    jwt_secret_key: str = Field(
        default="CHANGE-THIS-IN-PRODUCTION-USE-STRONG-SECRET-KEY", 
        description="JWT密钥，生产环境必须修改为强密钥"
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480  # 8小时
    
    # OpenAI配置
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_model: str = "o1-mini"
    openai_embedding_model: str = "text-embedding-ada-002"
    
    # Claude Code配置
    claude_code_api_key: Optional[str] = None
    claude_code_base_url: Optional[str] = None
    
    # Semantic Scholar API
    semantic_scholar_api_key: Optional[str] = None
    
    # 文件上传配置
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    upload_path: str = "./uploads"
    allowed_file_types: list = [".pdf", ".doc", ".docx", ".txt", ".md"]
    
    # 文献采集配置
    max_literature_per_query: int = 5000
    literature_batch_size: int = 50
    
    # 经验增强配置
    max_iteration_rounds: int = 50
    stop_threshold: float = 0.05  # 5%新增信息阈值
    consecutive_low_rounds: int = 3
    
    # 会员配置
    free_literature_limit: int = 1000
    premium_literature_limit: int = 2000
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# 创建全局设置实例
settings = Settings()