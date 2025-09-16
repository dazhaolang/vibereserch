# 科研文献智能分析平台 - 后端服务

## 项目概述

这是一个中文研究文献智能分析平台的后端服务，使用 AI 技术分析学术论文，生成结构化经验，并提供智能问答功能。系统从多个文献来源处理文献并创建研究辅助知识库。

## 技术栈

- **框架**: FastAPI (Python 3.12+)
- **数据库**: MySQL + Elasticsearch
- **缓存**: Redis
- **AI 服务**: OpenAI GPT 集成
- **PDF 处理**: MinerU 集成
- **异步任务**: Celery
- **部署**: Docker

## 环境要求

- Python 3.12+
- MySQL 8.0+
- Elasticsearch 7.x+
- Redis 6.0+
- Docker & Docker Compose (推荐)

## 快速开始

### 1. 环境变量配置

复制环境变量示例文件并配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置以下关键参数：

```env
# 数据库配置
DATABASE_URL=mysql://raggar:raggar123@localhost:3306/research_platform

# Redis 配置
REDIS_URL=redis://localhost:6379

# Elasticsearch 配置
ELASTICSEARCH_URL=http://localhost:9200

# AI 服务配置
OPENAI_API_KEY=your_openai_api_key
SEMANTIC_SCHOLAR_API_KEY=your_semantic_scholar_key

# JWT 密钥
JWT_SECRET_KEY=your_strong_secret_key
```

### 2. Docker 方式部署（推荐）

启动数据库服务：

```bash
# 启动 MySQL, Elasticsearch, Redis 容器
docker-compose up mysql elasticsearch redis -d
```

### 3. 手动安装

#### 3.1 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows
```

#### 3.2 安装依赖

```bash
pip install -r requirements.txt
```

#### 3.3 数据库初始化

```bash
# 创建数据库表
PYTHONPATH=/path/to/your/backend python -c "from app.core.database import engine, Base; Base.metadata.create_all(bind=engine)"
```

#### 3.4 启动服务

```bash
# 启动主应用
PYTHONPATH=/path/to/your/backend uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 启动 Celery 工作进程（新终端）
PYTHONPATH=/path/to/your/backend celery -A app.celery worker --loglevel=info
```

## API 文档

启动服务后访问：

- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc
- 健康检查: http://localhost:8000/health

## 主要功能模块

### 文献处理流程

1. **文献收集**: Google Scholar + Semantic Scholar APIs
2. **AI 过滤**: 基于 GPT 的相关性评估
3. **PDF 处理**: MinerU 集成高质量文本提取
4. **结构化**: 自动轻量级数据模板生成
5. **经验增强**: 动态停止的迭代学习

### API 端点

- `/api/auth/*` - 用户认证
- `/api/literature/*` - 文献管理
- `/api/analysis/*` - 智能分析
- `/api/research-direction/*` - 研究方向
- `/api/experiment-design/*` - 实验设计
- `/api/project/*` - 项目管理

### 多模型 AI 协调

- 位置: `app/services/multi_model_coordinator.py`
- 管理多个 AI 模型实例
- 负载均衡和故障转移策略
- 健康检查和系统状态监控

## 开发指南

### 添加新的 API 端点

1. 在 `app/api/` 中创建路由处理器
2. 在 `app/schemas/` 中定义 Pydantic 模式
3. 在 `app/services/` 中添加业务逻辑
4. 在 `app/main.py` 中注册路由

### 后台任务处理

- 在 `app/tasks/` 中定义任务
- 使用 Celery 装饰器进行异步处理
- 集成 WebSocket 进度更新
- 处理错误情况和重试逻辑

## 项目结构

```
backend/
├── app/
│   ├── main.py              # FastAPI 应用入口
│   ├── api/                 # API 路由处理器
│   ├── core/               # 核心配置和数据库
│   ├── models/             # SQLAlchemy 数据库模型
│   ├── schemas/            # Pydantic 请求/响应模式
│   ├── services/           # 业务逻辑服务
│   ├── tasks/              # Celery 后台任务
│   └── middleware/         # 自定义中间件
├── requirements.txt         # Python 依赖
├── alembic.ini             # 数据库迁移配置
├── docker-compose.yml      # Docker 编排
└── sql/                    # SQL 初始化脚本
```

## 测试

```bash
# 运行测试
python -m pytest

# 代码格式化
black .
isort .
```

## 性能考虑

- 多模型 AI 协调负载分布
- Elasticsearch 全文和语义搜索
- Redis 缓存频繁访问数据
- Celery 异步处理长时间运行任务
- WebSocket 实时更新减少轮询

## 故障排除

### 常见问题

1. **数据库连接错误**：检查 DATABASE_URL 配置
2. **Redis 连接错误**：确保 Redis 服务运行
3. **Elasticsearch 错误**：检查 ES 服务状态和索引配置
4. **API 密钥错误**：验证 OpenAI 和 Semantic Scholar API 密钥

### 日志查看

```bash
# 查看应用日志
tail -f app.log

# 查看 Celery 日志
tail -f celery.log
```

## 许可证

[根据项目实际情况添加许可证信息]

## 贡献

欢迎提交 Issue 和 Pull Request。

## 联系方式

- 邮箱: 1842156241@qq.com
- GitHub: [@dazhaolang](https://github.com/dazhaolang)