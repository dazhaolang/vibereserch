"""
测试配置文件
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 测试数据库配置
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "mysql://test_user:test_pass@localhost:3306/test_vibereserch"
)

# Redis测试配置
TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/1")

# Elasticsearch测试配置
TEST_ES_URL = os.getenv("TEST_ES_URL", "http://localhost:9200")

# 测试用户凭据
TEST_USER = {
    "email": "test@example.com",
    "password": "Test@123456",
    "name": "Test User"
}

# 测试项目数据
TEST_PROJECT = {
    "name": "Test Research Project",
    "description": "This is a test project"
}

# 测试文献数据
TEST_LITERATURE = {
    "title": "Test Literature Title",
    "authors": ["Author One", "Author Two"],
    "abstract": "This is a test abstract",
    "doi": "10.1234/test.doi",
    "year": 2024
}
