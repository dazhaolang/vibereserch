"""
应用配置管理
"""

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Optional, List
import os

class Settings(BaseSettings):
    # 应用基础配置
    app_name: str = "科研文献智能分析平台"
    debug: bool = True
    log_level: str = "INFO"
    environment: str = Field(
        default=os.getenv("APP_ENV", "development"),
        description="Runtime environment identifier (development/staging/production)"
    )
    
    # 数据库配置
    database_url: str = Field(
        default=os.getenv("DATABASE_URL", "mysql://user:password@localhost:3306/research_platform"),
        description="MySQL数据库连接URL，建议通过环境变量 DATABASE_URL 配置"
    )
    redis_url: str = Field(
        default=os.getenv("REDIS_URL", "redis://localhost:6379"),
        description="Redis连接URL"
    )

    # Elasticsearch配置
    elasticsearch_url: str = Field(
        default=os.getenv("ELASTICSEARCH_URL", "http://localhost:9200"),
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
    jwt_secret_key_fallbacks: list[str] = Field(
        default_factory=list,
        description=(
            "Legacy JWT 密钥列表，用于热更新或迁移阶段验证旧令牌"
        )
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

    # MCP服务器配置
    mcp_server_url: str = "stdio"
    
    # Semantic Scholar API
    semantic_scholar_api_key: Optional[str] = None

    # ResearchRabbit API
    researchrabbit_base_url: str = "https://www.researchrabbitapp.com"
    researchrabbit_username: Optional[str] = None
    researchrabbit_password: Optional[str] = None
    researchrabbit_requests_per_minute: int = 30
    researchrabbit_max_retries: int = 3

    # CodeX调度配置
    codex_api_url: Optional[str] = None
    codex_api_route: str = "/orchestrate"
    codex_api_key: Optional[str] = None
    codex_timeout: int = 60

    # Gemini CLI调度配置
    gemini_cli_command: Optional[str] = None
    gemini_cli_timeout: int = 90

    # 文件上传配置
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    upload_path: str = "./uploads"
    allowed_file_types: list = [".pdf", ".doc", ".docx", ".txt", ".md"]
    
    # 文献采集配置
    max_literature_per_query: int = 5000
    literature_batch_size: int = 50
    literature_processing_concurrency: int = 3

    # 通知配置
    smtp_host: Optional[str] = Field(default=None, description="SMTP server host")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_username: Optional[str] = Field(default=None, description="SMTP account username")
    smtp_password: Optional[str] = Field(default=None, description="SMTP account password")
    smtp_use_tls: bool = Field(default=True, description="Whether to enable STARTTLS when sending email")
    smtp_timeout_seconds: int = Field(default=30, description="Timeout for SMTP operations in seconds")
    notifications_from_email: Optional[str] = Field(default=None, description="Default sender email address for notifications")
    notifications_enabled: bool = Field(default=True, description="Toggle for outbound notification delivery")

    # 经验增强配置
    max_iteration_rounds: int = 50
    stop_threshold: float = 0.05  # 5%新增信息阈值
    consecutive_low_rounds: int = 3

    # 会员配置
    free_literature_limit: int = 1000
    premium_literature_limit: int = 2000

    # 开发/测试配置
    allow_sqlite_fallback: bool = Field(
        default=False,
        description="允许在轻量模式下使用 SQLite 数据库，仅用于本地开发或测试"
    )
    
    @field_validator("jwt_secret_key_fallbacks", mode="before")
    @classmethod
    def _split_jwt_fallbacks(cls, value):
        """支持逗号分隔或JSON列表形式的配置"""
        if value in (None, ""):
            return []
        if isinstance(value, (list, tuple)):
            return [item for item in value if item]
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",")]
            return [part for part in parts if part]
        return value

    @property
    def jwt_decode_keys(self) -> List[str]:
        """返回用于验证JWT的密钥列表，包含主密钥和备用密钥"""
        keys: List[str] = []
        for candidate in [self.jwt_secret_key, *self.jwt_secret_key_fallbacks]:
            if candidate and candidate not in keys:
                keys.append(candidate)
        return keys

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"

# 创建全局设置实例
settings = Settings()
