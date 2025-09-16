"""
数据库连接和会话管理
"""

import pymysql
pymysql.install_as_MySQLdb()

from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import redis
from app.core.config import settings

# MySQL数据库引擎 - 使用pymysql驱动
mysql_url = settings.database_url.replace("mysql://", "mysql+pymysql://")
engine = create_engine(
    mysql_url,
    pool_pre_ping=True,  # 连接前检查连接是否有效
    pool_recycle=1800,   # 30分钟回收连接，避免连接过期
    pool_size=5,         # 连接池大小
    max_overflow=10,     # 最大溢出连接数
    pool_timeout=30,     # 获取连接的超时时间 (增加)
    connect_args={
        "charset": "utf8mb4",
        "connect_timeout": 30,  # 连接超时 (增加)
        "read_timeout": 30,     # 读取超时 (增加)
        "write_timeout": 30,    # 写入超时 (增加)
        "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
    },
    echo=settings.debug
)

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
        return {"status": "healthy", "database": "mysql"}
    except Exception as e:
        return {"status": "unhealthy", "database": "mysql", "error": str(e)}