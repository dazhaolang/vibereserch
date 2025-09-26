"""
数据库连接和会话管理
"""

import os
from pathlib import Path

import pymysql

pymysql.install_as_MySQLdb()

from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
import redis

from app.core.config import settings


def _allow_sqlite() -> bool:
    """Determine whether SQLite may be used in the current environment."""
    lightweight_env = os.getenv("LIGHTWEIGHT_MODE", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return settings.allow_sqlite_fallback or lightweight_env


def _create_engine_from_settings():
    """Construct the SQLAlchemy engine for the configured database."""
    db_url = settings.database_url
    url = make_url(db_url)
    backend = url.get_backend_name()

    if backend.startswith("sqlite"):
        if not _allow_sqlite():
            raise ValueError(
                "SQLite 仅允许在轻量模式或允许配置下使用，请配置 MySQL DATABASE_URL。"
            )

        connect_args = {"check_same_thread": False}

        if url.database and url.database not in {":memory:", ""}:
            db_path = Path(url.database)
            if not db_path.is_absolute():
                db_path = Path.cwd() / db_path
            db_path.parent.mkdir(parents=True, exist_ok=True)

        return create_engine(
            db_url,
            connect_args=connect_args,
            echo=settings.debug,
        )

    if not backend.startswith("mysql"):
        raise ValueError(
            f"Unsupported database backend '{backend}'. Only MySQL is supported in production."
        )

    mysql_url = db_url.replace("mysql://", "mysql+pymysql://")
    connect_args = {
        "charset": "utf8mb4",
        "connect_timeout": 30,
        "read_timeout": 30,
        "write_timeout": 30,
        "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
    }

    return create_engine(
        mysql_url,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        connect_args=connect_args,
        echo=settings.debug,
    )


# 数据库引擎实例
engine = _create_engine_from_settings()

# 会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 基础模型类
Base = declarative_base()

# Redis连接 - 添加连接池配置
redis_client = redis.from_url(
    settings.redis_url,
    decode_responses=True,
    max_connections=20,     # 最大连接数
    retry_on_timeout=True,  # 超时重试
    socket_connect_timeout=5,  # 连接超时
    socket_timeout=5,       # 读写超时
    health_check_interval=30  # 健康检查间隔
)

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def init_database():
    """初始化数据库，创建所有表"""
    try:
        # 先测试数据库连接
        await test_database_connection()
        # 创建所有表
        Base.metadata.create_all(bind=engine)
        print("✅ 数据库初始化成功")
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        raise

async def test_database_connection():
    """测试数据库连接"""
    try:
        db = SessionLocal()
        # 执行简单查询测试连接
        db.execute(text("SELECT 1"))
        db.close()
        print("✅ 数据库连接测试成功")
        return True
    except Exception as e:
        print(f"❌ 数据库连接测试失败: {e}")
        raise

def get_db_health():
    """获取数据库健康状态"""
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        backend = engine.url.get_backend_name()
        return {"status": "healthy", "database": backend}
    except Exception as e:
        backend = engine.url.get_backend_name()
        return {"status": "unhealthy", "database": backend, "error": str(e)}
