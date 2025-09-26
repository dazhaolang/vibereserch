# 科研文献智能分析平台 API 文档

## 概述

这是一个基于FastAPI的科研文献智能分析平台后端API文档，版本2.2.0。该平台集成了Claude Code + MCP，提供智能文献处理、分析、协作工作空间等功能。

**基础URL**: `http://localhost:8000` 或 `https://your-domain.com`
**API文档**: `/api/docs` (Swagger UI)
**ReDoc**: `/api/redoc`

## 认证机制

所有API（除了登录、注册、健康检查）都需要Bearer Token认证。

```javascript
// 请求头设置
headers: {
  'Authorization': 'Bearer your_access_token_here',
  'Content-Type': 'application/json'
}
```

## 核心API模块

### 1. 认证模块 (/api/auth)

#### 1.1 用户注册

**POST** `/api/auth/register`

注册新用户账户并自动分配免费会员权限。

**请求体**:
```javascript
{
  "email": "user@example.com",
  "username": "john_doe",
  "password": "password123",
  "full_name": "John Doe",
  "institution": "University of Science",
  "research_field": "Computer Science"
}
```

**响应**:
```javascript
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in": 43200,
  "user_info": {
    "id": 1,
    "email": "user@example.com",
    "username": "john_doe",
    "full_name": "John Doe",
    "institution": "University of Science",
    "research_field": "Computer Science",
    "is_active": true,
    "is_verified": false,
    "created_at": "2024-01-01T00:00:00",
    "updated_at": null,
    "last_login": null,
    "membership": {
      "id": 1,
      "user_id": 1,
      "membership_type": "FREE",
      "monthly_literature_used": 0,
      "monthly_queries_used": 0,
      "total_projects": 0,
      "subscription_start": null,
      "subscription_end": null,
      "auto_renewal": false,
      "created_at": "2024-01-01T00:00:00",
      "updated_at": null
    }
  }
}
```

#### 1.2 用户登录

**POST** `/api/auth/login`

用户登录获取访问令牌。

**请求体**:
```javascript
{
  "email": "user@example.com",
  "password": "password123"
}
```

**响应**: 同注册响应格式

#### 1.3 获取当前用户信息

**GET** `/api/auth/me`

**认证**: 需要Bearer Token

**响应**:
```javascript
{
  "id": 1,
  "email": "user@example.com",
  "username": "john_doe",
  "full_name": "John Doe",
  "institution": "University of Science",
  "research_field": "Computer Science",
  "is_active": true,
  "is_verified": false,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": null,
  "last_login": "2024-01-01T12:00:00",
  "membership": {
    // 会员信息...
  }
}
```

#### 1.4 用户登出

**POST** `/api/auth/logout`

**认证**: 需要Bearer Token

**响应**:
```javascript
{
  "message": "登出成功"
}
```

### 2. 项目管理模块 (/api/project)

#### 2.1 创建空项目

**POST** `/api/project/create-empty`

创建一个空项目，不需要预先定义研究方向。

**认证**: 需要Bearer Token

**请求体**:
```javascript
{
  "name": "我的研究项目",
  "description": "项目描述",
  "category": "机器学习"
}
```

**响应**:
```javascript
{
  "id": 1,
  "name": "我的研究项目",
  "description": "项目描述",
  "research_direction": null,
  "keywords": [],
  "research_categories": null,
  "status": "empty",
  "literature_sources": null,
  "max_literature_count": 200,
  "structure_template": null,
  "extraction_prompts": null,
  "owner_id": 1,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": null,
  "literature_count": 0,
  "progress_percentage": null
}
```

#### 2.2 创建完整项目

**POST** `/api/project/create`

创建有明确研究方向的项目。

**认证**: 需要Bearer Token

**请求体**:
```javascript
{
  "name": "深度学习研究",
  "description": "深度学习在图像识别中的应用",
  "research_direction": "计算机视觉",
  "keywords": ["深度学习", "图像识别", "神经网络"],
  "research_categories": ["人工智能", "计算机视觉"],
  "max_literature_count": 500
}
```

#### 2.3 获取项目列表

**GET** `/api/project/list`

获取当前用户的所有项目。

**认证**: 需要Bearer Token

**响应**:
```javascript
[
  {
    "id": 1,
    "name": "项目1",
    "description": "描述",
    "research_direction": "研究方向",
    "keywords": ["关键词1", "关键词2"],
    "research_categories": ["分类1"],
    "status": "active",
    "literature_sources": null,
    "max_literature_count": 200,
    "structure_template": null,
    "extraction_prompts": null,
    "owner_id": 1,
    "created_at": "2024-01-01T00:00:00",
    "updated_at": null,
    "literature_count": 5,
    "progress_percentage": 25.0
  }
]
```

#### 2.4 获取项目详情

**GET** `/api/project/{project_id}`

获取指定项目的详细信息。

**认证**: 需要Bearer Token

**路径参数**:
- `project_id`: 项目ID

#### 2.5 智能确定研究方向

**POST** `/api/project/determine-direction`

使用AI分析用户输入，智能确定研究方向。

**认证**: 需要Bearer Token

**请求体**:
```javascript
{
  "user_input": "我想研究机器学习在医疗诊断中的应用",
  "conversation_history": [
    {
      "role": "user",
      "content": "我对AI很感兴趣"
    },
    {
      "role": "assistant",
      "content": "你具体对AI的哪个方向感兴趣？"
    }
  ]
}
```

**响应**:
```javascript
{
  "suggested_direction": "机器学习在医疗诊断中的应用研究",
  "keywords": ["机器学习", "医疗诊断", "人工智能", "深度学习"],
  "research_categories": ["人工智能", "医疗信息学", "机器学习"],
  "confidence": 0.85,
  "follow_up_questions": [
    "您主要关注哪种疾病的诊断？",
    "您希望使用哪种类型的医疗数据？"
  ]
}
```

#### 2.6 上传项目文件

**POST** `/api/project/{project_id}/upload-files`

上传项目相关文件（项目书、申请书等），系统会自动提取研究方向信息。

**认证**: 需要Bearer Token

**请求体**: `multipart/form-data`
- `files`: 文件列表

**响应**:
```javascript
{
  "message": "文件上传成功",
  "uploaded_files": [
    {
      "filename": "project_proposal.pdf",
      "file_path": "/uploads/project_1/project_proposal.pdf",
      "size": 1024000
    }
  ],
  "extracted_info": {
    "project_proposal.pdf": {
      "research_direction": "深度学习在医疗影像诊断中的应用",
      "keywords": ["深度学习", "医疗影像", "诊断"],
      "methods": ["卷积神经网络", "数据增强"],
      "objectives": ["提高诊断准确率", "减少误诊率"]
    }
  },
  "project_updated": true
}
```

#### 2.7 启动文献索引构建

**POST** `/api/project/{project_id}/start-indexing`

手动触发项目文献库的索引构建过程。

**认证**: 需要Bearer Token

**响应**:
```javascript
{
  "message": "索引构建已启动",
  "task_id": "indexing_1_abc12345",
  "estimated_time": "10-25 秒",
  "literature_count": 5
}
```

#### 2.8 获取索引构建状态

**GET** `/api/project/{project_id}/indexing-status/{task_id}`

查询索引构建任务的进度。

**认证**: 需要Bearer Token

**响应**:
```javascript
{
  "task_id": "indexing_1_abc12345",
  "status": "running",
  "progress": 60,
  "message": "正在处理第3篇文献...",
  "result": null,
  "error": null
}
```

#### 2.9 获取项目统计信息

**GET** `/api/project/{project_id}/statistics`

获取项目的详细统计数据。

**认证**: 需要Bearer Token

**响应**:
```javascript
{
  "literature_count": 15,
  "experience_books_count": 3,
  "analysis_count": 8,
  "progress_percentage": 75.5,
  "task_count": 12,
  "active_tasks": 2
}
```

### 3. 文献管理模块 (/api/literature)

#### 3.1 搜索建库 (核心功能)

**POST** `/api/literature/search-and-build-library`

启动完整的文献搜索、筛选、处理、入库流水线。支持200-500篇文献的大规模处理。

**认证**: 需要Bearer Token

**请求体**:
```javascript
{
  "project_id": 1,
  "query": "深度学习医疗诊断",
  "keywords": ["deep learning", "medical diagnosis"],
  "max_results": 100,
  "enable_ai_filtering": true,
  "enable_pdf_processing": true,
  "enable_structured_extraction": true,
  "quality_threshold": 0.7,
  "batch_size": 10,
  "max_concurrent_downloads": 5,
  "processing_method": "standard"
}
```

**响应**:
```javascript
{
  "task_id": 123,
  "message": "搜索建库任务已启动，正在执行完整的文献处理流水线",
  "estimated_duration": 800,
  "config": {
    "keywords": ["deep learning", "medical diagnosis"],
    "max_results": 100,
    "processing_stages": [
      "搜索文献",
      "AI智能筛选",
      "PDF下载",
      "内容提取",
      "结构化处理",
      "数据库入库"
    ]
  }
}
```

#### 3.2 文献收集

**POST** `/api/literature/collect`

启动文献收集任务，从多个学术数据源搜索和收集文献。

**认证**: 需要Bearer Token

**请求体**:
```javascript
{
  "project_id": 1,
  "keywords": ["machine learning", "healthcare"],
  "sources": ["semantic_scholar", "pubmed", "arxiv"],
  "max_results": 50,
  "filter_criteria": {
    "min_citation_count": 10,
    "publication_year_start": 2020,
    "publication_year_end": 2024
  }
}
```

### 4. 任务管理模块 (/api/task)

#### 4.1 获取任务详情

**GET** `/api/task/{task_id}`

获取指定任务的详细信息和状态。

**认证**: 需要Bearer Token

**响应**:
```javascript
{
  "id": 123,
  "project_id": 1,
  "task_type": "search_and_build_library",
  "title": "搜索建库 - 深度学习, 医疗诊断",
  "description": "搜索→筛选→PDF处理→结构化→入库完整流水线",
  "config": {
    "keywords": ["深度学习", "医疗诊断"],
    "max_results": 100,
    "enable_ai_filtering": true
  },
  "input_data": null,
  "status": "running",
  "progress_percentage": 45,
  "current_step": "PDF下载中",
  "result": null,
  "error_message": null,
  "estimated_duration": 800,
  "actual_duration": null,
  "started_at": "2024-01-01T10:00:00",
  "completed_at": null,
  "created_at": "2024-01-01T10:00:00",
  "updated_at": "2024-01-01T10:05:00"
}
```

#### 4.2 获取任务进度历史

**GET** `/api/task/{task_id}/progress`

获取任务的详细进度历史记录。

**认证**: 需要Bearer Token

**响应**:
```javascript
{
  "task_id": 123,
  "current_status": "running",
  "current_progress": 45,
  "current_step": "PDF下载中",
  "progress_history": [
    {
      "id": 1,
      "step_name": "文献搜索",
      "progress_percentage": 20,
      "step_result": "找到150篇候选文献",
      "started_at": "2024-01-01T10:00:00",
      "completed_at": "2024-01-01T10:02:00"
    },
    {
      "id": 2,
      "step_name": "AI智能筛选",
      "progress_percentage": 40,
      "step_result": "筛选出85篇高质量文献",
      "started_at": "2024-01-01T10:02:00",
      "completed_at": "2024-01-01T10:04:00"
    }
  ]
}
```

### 5. 研究模式 (/api/research)

#### 5.1 研究查询

**POST** `/api/research/query`

执行不同模式的研究查询，包括RAG、深度分析、自动模式。

**认证**: 需要Bearer Token

**请求体**:
```javascript
{
  "mode": "rag",  // "rag" | "deep" | "auto"
  "project_id": 1,
  "query": "深度学习在医疗诊断中的最新进展",
  "max_literature_count": 10,
  "context_literature_ids": [1, 2, 3],
  "processing_method": "deep",
  "keywords": ["deep learning", "medical diagnosis"],
  "auto_config": {
    "analysis_depth": "comprehensive",
    "include_trends": true
  },
  "agent": "research_assistant"
}
```

**响应**:
```javascript
{
  "mode": "rag",
  "payload": {
    "answer": "基于检索到的相关文献，深度学习在医疗诊断中的最新进展包括...",
    "confidence": 0.92,
    "sources": [
      {
        "literature_id": 1,
        "title": "Deep Learning for Medical Diagnosis",
        "relevance": 0.95,
        "citation": "Smith et al., 2024"
      }
    ],
    "metadata": {
      "processing_time": 2.5,
      "literature_used": 8,
      "model_version": "gpt-4"
    }
  }
}
```

### 6. 分析模块 (/api/analysis)

#### 6.1 智能问答

**POST** `/api/analysis/ask-question`

针对项目文献进行智能问答。

**认证**: 需要Bearer Token

**请求体**:
```javascript
{
  "project_id": 1,
  "question": "这些文献中提到的主要深度学习模型有哪些？",
  "use_main_experience": false,
  "context": {
    "focus_area": "methodology"
  }
}
```

**响应**:
```javascript
{
  "answer": "基于您项目中的文献分析，主要的深度学习模型包括：1. 卷积神经网络(CNN)...",
  "confidence": 0.85,
  "sources": [
    {
      "type": "literature",
      "content": "文献摘要片段"
    }
  ],
  "related_literature": [1, 3, 5],
  "processing_time": 1.2
}
```

#### 6.2 生成经验总结

**POST** `/api/analysis/generate-experience`

基于项目文献生成经验总结和知识提取。

**认证**: 需要Bearer Token

**请求体**:
```javascript
{
  "project_id": 1,
  "processing_method": "enhanced",
  "research_question": "深度学习模型在医疗诊断中的有效性"
}
```

### 7. WebSocket连接

#### 7.1 任务进度WebSocket

**WebSocket** `/ws/progress/{task_id}?token=your_token`

实时接收任务进度更新、文献元数据、AI输出流。

**连接参数**:
- `task_id`: 任务ID
- `token`: 认证令牌(查询参数)

**接收消息格式**:
```javascript
{
  "type": "progress_event",
  "event": {
    "task_id": "123",
    "step_name": "PDF处理",
    "progress_percentage": 60,
    "message": "正在处理第5篇文献",
    "timestamp": "2024-01-01T10:05:00",
    "metadata": {
      "current_literature": "Deep Learning for Medical Diagnosis",
      "processed_count": 5,
      "total_count": 10
    }
  }
}
```

**发送消息格式**:
```javascript
{
  "type": "request_status"  // 请求任务状态
}

{
  "type": "request_literature"  // 请求文献元数据
}

{
  "type": "ping",
  "timestamp": "2024-01-01T10:05:00"
}
```

#### 7.2 项目状态WebSocket

**WebSocket** `/ws/project/{project_id}/status?token=your_token`

接收项目级别的状态更新和通知。

#### 7.3 全局WebSocket

**WebSocket** `/ws/global?token=your_token`

接收系统级通知和管理信息。

### 8. 智能交互 (/api/intelligent-interaction)

#### 8.1 智能交互WebSocket

**WebSocket** `/ws/intelligent-interaction/{session_id}?token=your_token`

提供实时智能交互事件推送和状态同步。

## 系统状态与监控

### 健康检查

**GET** `/health`

检查系统健康状态，无需认证。

**响应**:
```javascript
{
  "status": "healthy",
  "version": "2.2.0",
  "features_status": {
    "multi_model_ai": "active",
    "smart_assistant": "active",
    "knowledge_graph": "active",
    "collaborative_workspace": "active",
    "vector_search": "active",
    "performance_optimization": "active",
    "cost_control": "active",
    "real_time_monitoring": "active",
    "claude_code_integration": "operational",
    "mcp_protocol": "operational"
  },
  "system_status": {
    // 详细系统状态
  },
  "performance_health": {
    "overall_score": 0.95,
    "cpu_score": 0.92,
    "memory_score": 0.98,
    "timestamp": "2024-01-01T10:00:00"
  }
}
```

### 系统状态详情

**GET** `/api/system/status`

获取详细的系统状态信息。

### 系统能力说明

**GET** `/api/system/capabilities`

获取系统功能和技术栈信息。

## 错误响应格式

所有API错误都遵循统一格式：

```javascript
{
  "detail": "错误描述信息",
  "error_code": "SPECIFIC_ERROR_CODE",
  "timestamp": "2024-01-01T10:00:00"
}
```

常见HTTP状态码：
- `200`: 成功
- `400`: 请求参数错误
- `401`: 未认证或token无效
- `403`: 权限不足
- `404`: 资源不存在
- `422`: 数据验证失败
- `500`: 服务器内部错误

## 使用示例

### JavaScript/TypeScript示例

```javascript
// 1. 用户登录
const loginResponse = await fetch('/api/auth/login', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    email: 'user@example.com',
    password: 'password123'
  })
});

const { access_token } = await loginResponse.json();

// 2. 创建项目
const projectResponse = await fetch('/api/project/create-empty', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${access_token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    name: '我的研究项目',
    description: '深度学习研究'
  })
});

const project = await projectResponse.json();

// 3. 启动搜索建库
const searchResponse = await fetch('/api/literature/search-and-build-library', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${access_token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    project_id: project.id,
    query: '深度学习医疗诊断',
    max_results: 50,
    enable_ai_filtering: true,
    enable_pdf_processing: true
  })
});

const { task_id } = await searchResponse.json();

// 4. 连接WebSocket监听进度
const ws = new WebSocket(`ws://localhost:8000/ws/progress/${task_id}?token=${access_token}`);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('进度更新:', data);
};

// 5. 查询任务状态
const taskResponse = await fetch(`/api/task/${task_id}`, {
  headers: {
    'Authorization': `Bearer ${access_token}`
  }
});

const taskStatus = await taskResponse.json();
console.log('任务状态:', taskStatus);
```

### Python示例

```python
import requests
import websocket
import json

# 1. 登录获取token
login_response = requests.post('http://localhost:8000/api/auth/login', json={
    'email': 'user@example.com',
    'password': 'password123'
})

token = login_response.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# 2. 创建项目
project_response = requests.post(
    'http://localhost:8000/api/project/create-empty',
    headers=headers,
    json={
        'name': '我的研究项目',
        'description': '深度学习研究'
    }
)

project_id = project_response.json()['id']

# 3. 启动搜索建库
search_response = requests.post(
    'http://localhost:8000/api/literature/search-and-build-library',
    headers=headers,
    json={
        'project_id': project_id,
        'query': '深度学习医疗诊断',
        'max_results': 50,
        'enable_ai_filtering': True,
        'enable_pdf_processing': True
    }
)

task_id = search_response.json()['task_id']

# 4. WebSocket监听进度
def on_message(ws, message):
    data = json.loads(message)
    print(f"进度更新: {data}")

ws = websocket.WebSocketApp(
    f"ws://localhost:8000/ws/progress/{task_id}?token={token}",
    on_message=on_message
)

ws.run_forever()
```

## 会员权限限制

不同会员等级的功能限制：

| 功能 | 免费版 | 高级版 | 企业版 |
|------|--------|--------|--------|
| 最大文献数 | 500 | 2000 | 10000 |
| 最大项目数 | 3 | 10 | 50 |
| 月度查询数 | 100 | 500 | 2000 |
| API调用频率 | 30/分钟 | 120/分钟 | 300/分钟 |
| 并发请求数 | 3 | 10 | 50 |
| 数据源访问 | 基础 | 完整 | 完整+企业 |

## 费率和成本

文献处理成本（估算）：
- **轻量模式**: ~$0.05/篇
- **标准模式**: ~$0.15/篇
- **深度模式**: ~$0.35/篇

## 技术栈

- **后端**: FastAPI + Python
- **数据库**: MySQL + Elasticsearch
- **AI模型**: OpenAI GPT + 本地模型
- **实时通信**: WebSocket + 事件驱动
- **向量搜索**: Elasticsearch + 语义相似度
- **缓存**: Redis + 多级缓存
- **MCP协议**: Model Context Protocol
- **Claude Code**: Anthropic Claude Code集成

## 支持和联系

如有API使用问题，请通过以下方式联系：

- 技术文档: `/api/docs`
- 系统状态: `/health`
- 功能说明: `/api/system/capabilities`

---

*文档版本: 2.2.0*
*最后更新: 2024-01-01*