"""
多模型协同架构
协调不同AI模型的调用，实现任务分配和结果整合
"""

from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime
import asyncio
import json
import logging
from pydantic import BaseModel
from enum import Enum
from dataclasses import dataclass
import aiohttp
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class ModelType(Enum):
    """模型类型枚举"""
    LARGE_LANGUAGE_MODEL = "llm"  # 大语言模型
    SMALL_LANGUAGE_MODEL = "slm"  # 小语言模型
    EMBEDDING_MODEL = "embedding"  # 嵌入模型
    CLASSIFICATION_MODEL = "classification"  # 分类模型
    SUMMARIZATION_MODEL = "summarization"  # 摘要模型
    TRANSLATION_MODEL = "translation"  # 翻译模型


class TaskPriority(Enum):
    """任务优先级枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ModelCapability:
    """模型能力描述"""
    model_type: ModelType
    supported_tasks: List[str]
    max_tokens: int
    avg_response_time: float  # 秒
    cost_per_1k_tokens: float
    quality_score: float  # 0-1
    availability: float  # 0-1


@dataclass
class TaskRequest:
    """任务请求"""
    task_id: str
    task_type: str
    content: str
    context: Dict[str, Any] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    max_tokens: Optional[int] = None
    timeout: Optional[float] = None
    required_quality: Optional[float] = None


@dataclass
class ModelResponse:
    """模型响应"""
    task_id: str
    model_id: str
    response: str
    confidence: float
    processing_time: float
    tokens_used: int
    cost: float
    metadata: Dict[str, Any] = None


class BaseModelAdapter(ABC):
    """模型适配器基类"""
    
    def __init__(self, model_id: str, config: Dict[str, Any]):
        self.model_id = model_id
        self.config = config
        self.is_available = True
        self.current_load = 0.0
        self.max_concurrent = config.get("max_concurrent", 5)
    
    @abstractmethod
    async def process_request(self, request: TaskRequest) -> ModelResponse:
        """处理请求"""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> ModelCapability:
        """获取模型能力"""
        pass
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # 实现具体的健康检查逻辑
            return True
        except Exception as e:
            logger.error(f"Health check failed for {self.model_id}: {str(e)}")
            return False


class OpenAIAdapter(BaseModelAdapter):
    """OpenAI模型适配器"""
    
    def __init__(self, model_id: str, config: Dict[str, Any]):
        super().__init__(model_id, config)
        self.api_key = config.get("api_key")
        self.model_name = config.get("model_name", "gpt-3.5-turbo")
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
    
    async def process_request(self, request: TaskRequest) -> ModelResponse:
        """处理OpenAI请求"""
        start_time = datetime.now()
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model_name,
                "messages": [
                    {"role": "user", "content": request.content}
                ],
                "max_tokens": request.max_tokens or 1000,
                "temperature": 0.7
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=request.timeout or 30)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result["choices"][0]["message"]["content"]
                        tokens_used = result["usage"]["total_tokens"]
                        
                        processing_time = (datetime.now() - start_time).total_seconds()
                        cost = self._calculate_cost(tokens_used)
                        
                        return ModelResponse(
                            task_id=request.task_id,
                            model_id=self.model_id,
                            response=content,
                            confidence=0.85,  # 默认置信度
                            processing_time=processing_time,
                            tokens_used=tokens_used,
                            cost=cost,
                            metadata={"model_name": self.model_name}
                        )
                    else:
                        raise Exception(f"API request failed: {response.status}")
        
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"OpenAI request failed: {str(e)}")
            
            return ModelResponse(
                task_id=request.task_id,
                model_id=self.model_id,
                response=f"Error: {str(e)}",
                confidence=0.0,
                processing_time=processing_time,
                tokens_used=0,
                cost=0.0,
                metadata={"error": str(e)}
            )
    
    def get_capabilities(self) -> ModelCapability:
        """获取OpenAI模型能力"""
        return ModelCapability(
            model_type=ModelType.LARGE_LANGUAGE_MODEL,
            supported_tasks=[
                "text_generation", "summarization", "translation", 
                "question_answering", "analysis", "creative_writing"
            ],
            max_tokens=4000 if "gpt-3.5" in self.model_name else 8000,
            avg_response_time=2.5,
            cost_per_1k_tokens=0.002,
            quality_score=0.9,
            availability=0.99
        )
    
    def _calculate_cost(self, tokens: int) -> float:
        """计算成本"""
        return (tokens / 1000) * self.get_capabilities().cost_per_1k_tokens


class LocalModelAdapter(BaseModelAdapter):
    """本地模型适配器"""
    
    def __init__(self, model_id: str, config: Dict[str, Any]):
        super().__init__(model_id, config)
        self.model_path = config.get("model_path")
        self.model_type = ModelType(config.get("model_type", "slm"))
    
    async def process_request(self, request: TaskRequest) -> ModelResponse:
        """处理本地模型请求"""
        start_time = datetime.now()
        
        try:
            # 模拟本地模型处理
            await asyncio.sleep(0.5)  # 模拟处理时间
            
            # 根据任务类型生成不同的响应
            if request.task_type == "classification":
                response = self._classify_content(request.content)
            elif request.task_type == "summarization":
                response = self._summarize_content(request.content)
            elif request.task_type == "quality_assessment":
                response = self._assess_quality(request.content)
            else:
                response = f"本地模型处理结果: {request.content[:100]}..."
            
            processing_time = (datetime.now() - start_time).total_seconds()
            tokens_used = len(request.content.split()) + len(response.split())
            
            return ModelResponse(
                task_id=request.task_id,
                model_id=self.model_id,
                response=response,
                confidence=0.75,
                processing_time=processing_time,
                tokens_used=tokens_used,
                cost=0.0,  # 本地模型无成本
                metadata={"model_type": self.model_type.value}
            )
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Local model request failed: {str(e)}")
            
            return ModelResponse(
                task_id=request.task_id,
                model_id=self.model_id,
                response=f"Error: {str(e)}",
                confidence=0.0,
                processing_time=processing_time,
                tokens_used=0,
                cost=0.0,
                metadata={"error": str(e)}
            )
    
    def get_capabilities(self) -> ModelCapability:
        """获取本地模型能力"""
        return ModelCapability(
            model_type=self.model_type,
            supported_tasks=[
                "classification", "summarization", "quality_assessment", "simple_qa"
            ],
            max_tokens=2000,
            avg_response_time=0.8,
            cost_per_1k_tokens=0.0,
            quality_score=0.7,
            availability=0.95
        )
    
    def _classify_content(self, content: str) -> str:
        """分类内容"""
        # 简单的关键词分类
        if any(keyword in content.lower() for keyword in ["synthesis", "preparation", "制备"]):
            return "preparation"
        elif any(keyword in content.lower() for keyword in ["characterization", "analysis", "表征"]):
            return "characterization"
        elif any(keyword in content.lower() for keyword in ["application", "use", "应用"]):
            return "application"
        else:
            return "general"
    
    def _summarize_content(self, content: str) -> str:
        """摘要内容"""
        # 简单的摘要逻辑
        sentences = content.split('.')[:3]  # 取前3句
        return '. '.join(sentences) + '.'
    
    def _assess_quality(self, content: str) -> str:
        """评估质量"""
        word_count = len(content.split())
        if word_count > 500:
            return "high_quality"
        elif word_count > 200:
            return "medium_quality"
        else:
            return "low_quality"


class ModelLoadBalancer:
    """模型负载均衡器"""
    
    def __init__(self):
        self.models = {}  # model_id -> adapter
        self.load_history = {}  # model_id -> load_history
        self.performance_metrics = {}  # model_id -> metrics
    
    def register_model(self, adapter: BaseModelAdapter):
        """注册模型"""
        self.models[adapter.model_id] = adapter
        self.load_history[adapter.model_id] = []
        self.performance_metrics[adapter.model_id] = {
            "total_requests": 0,
            "successful_requests": 0,
            "avg_response_time": 0.0,
            "total_cost": 0.0
        }
        logger.info(f"Registered model: {adapter.model_id}")
    
    def unregister_model(self, model_id: str):
        """注销模型"""
        if model_id in self.models:
            del self.models[model_id]
            del self.load_history[model_id]
            del self.performance_metrics[model_id]
            logger.info(f"Unregistered model: {model_id}")
    
    async def select_best_model(self, request: TaskRequest) -> Optional[BaseModelAdapter]:
        """选择最佳模型"""
        
        # 筛选支持该任务的模型
        suitable_models = []
        for model_id, adapter in self.models.items():
            if not adapter.is_available:
                continue
            
            capabilities = adapter.get_capabilities()
            if request.task_type in capabilities.supported_tasks:
                suitable_models.append((model_id, adapter, capabilities))
        
        if not suitable_models:
            return None
        
        # 根据多个因素选择最佳模型
        best_model = None
        best_score = -1
        
        for model_id, adapter, capabilities in suitable_models:
            score = self._calculate_model_score(
                model_id, adapter, capabilities, request
            )
            
            if score > best_score:
                best_score = score
                best_model = adapter
        
        return best_model
    
    def _calculate_model_score(self, 
                              model_id: str, 
                              adapter: BaseModelAdapter, 
                              capabilities: ModelCapability,
                              request: TaskRequest) -> float:
        """计算模型评分"""
        
        score = 0.0
        
        # 质量权重 (40%)
        quality_weight = 0.4
        quality_score = capabilities.quality_score
        if request.required_quality and quality_score < request.required_quality:
            quality_score *= 0.5  # 惩罚不满足质量要求的模型
        score += quality_score * quality_weight
        
        # 响应时间权重 (25%)
        time_weight = 0.25
        time_score = 1.0 - min(capabilities.avg_response_time / 10.0, 1.0)  # 10秒为最差
        if request.priority == TaskPriority.CRITICAL:
            time_weight *= 1.5  # 关键任务更重视响应时间
        score += time_score * time_weight
        
        # 成本权重 (20%)
        cost_weight = 0.2
        cost_score = 1.0 - min(capabilities.cost_per_1k_tokens / 0.01, 1.0)  # 0.01为最贵
        score += cost_score * cost_weight
        
        # 可用性权重 (10%)
        availability_weight = 0.1
        availability_score = capabilities.availability
        score += availability_score * availability_weight
        
        # 当前负载权重 (5%)
        load_weight = 0.05
        load_score = 1.0 - (adapter.current_load / adapter.max_concurrent)
        score += load_score * load_weight
        
        return score
    
    async def update_model_metrics(self, model_id: str, response: ModelResponse):
        """更新模型指标"""
        if model_id not in self.performance_metrics:
            return
        
        metrics = self.performance_metrics[model_id]
        metrics["total_requests"] += 1
        
        if response.confidence > 0:  # 成功请求
            metrics["successful_requests"] += 1
        
        # 更新平均响应时间
        total_time = metrics["avg_response_time"] * (metrics["total_requests"] - 1)
        metrics["avg_response_time"] = (total_time + response.processing_time) / metrics["total_requests"]
        
        # 更新总成本
        metrics["total_cost"] += response.cost
        
        # 更新负载历史
        self.load_history[model_id].append({
            "timestamp": datetime.now(),
            "response_time": response.processing_time,
            "success": response.confidence > 0
        })
        
        # 保留最近100条记录
        if len(self.load_history[model_id]) > 100:
            self.load_history[model_id] = self.load_history[model_id][-100:]


class TaskQueue:
    """任务队列管理器"""
    
    def __init__(self):
        self.queues = {
            TaskPriority.CRITICAL: asyncio.Queue(),
            TaskPriority.HIGH: asyncio.Queue(),
            TaskPriority.MEDIUM: asyncio.Queue(),
            TaskPriority.LOW: asyncio.Queue()
        }
        self.processing_tasks = {}  # task_id -> task_info
    
    async def enqueue_task(self, request: TaskRequest):
        """加入任务队列"""
        await self.queues[request.priority].put(request)
        logger.debug(f"Enqueued task {request.task_id} with priority {request.priority.value}")
    
    async def dequeue_task(self) -> Optional[TaskRequest]:
        """从队列中取出任务（按优先级）"""
        
        # 按优先级顺序检查队列
        for priority in [TaskPriority.CRITICAL, TaskPriority.HIGH, TaskPriority.MEDIUM, TaskPriority.LOW]:
            queue = self.queues[priority]
            if not queue.empty():
                request = await queue.get()
                self.processing_tasks[request.task_id] = {
                    "request": request,
                    "start_time": datetime.now()
                }
                return request
        
        return None
    
    def complete_task(self, task_id: str):
        """完成任务"""
        if task_id in self.processing_tasks:
            del self.processing_tasks[task_id]
    
    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        return {
            "pending_tasks": {
                priority.value: self.queues[priority].qsize()
                for priority in TaskPriority
            },
            "processing_tasks": len(self.processing_tasks),
            "total_pending": sum(q.qsize() for q in self.queues.values())
        }


class MultiModelCoordinator:
    """多模型协调器主控制器"""
    
    def __init__(self):
        self.load_balancer = ModelLoadBalancer()
        self.task_queue = TaskQueue()
        self.response_cache = {}  # 简单的响应缓存
        self.is_running = False
        self.worker_tasks = []
    
    def initialize_models(self, model_configs: List[Dict[str, Any]]):
        """初始化模型"""
        
        for config in model_configs:
            model_type = config.get("type", "local")
            model_id = config.get("id")
            
            if model_type == "openai":
                adapter = OpenAIAdapter(model_id, config)
            elif model_type == "local":
                adapter = LocalModelAdapter(model_id, config)
            else:
                logger.warning(f"Unknown model type: {model_type}")
                continue
            
            self.load_balancer.register_model(adapter)
        
        logger.info(f"Initialized {len(self.load_balancer.models)} models")
    
    async def start_workers(self, num_workers: int = 3):
        """启动工作线程"""
        
        if self.is_running:
            return
        
        self.is_running = True
        
        for i in range(num_workers):
            worker_task = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self.worker_tasks.append(worker_task)
        
        logger.info(f"Started {num_workers} worker tasks")
    
    async def stop_workers(self):
        """停止工作线程"""
        
        self.is_running = False
        
        # 取消所有工作任务
        for task in self.worker_tasks:
            task.cancel()
        
        # 等待任务完成
        await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        self.worker_tasks.clear()
        
        logger.info("Stopped all worker tasks")
    
    async def _worker_loop(self, worker_id: str):
        """工作线程循环"""
        
        logger.info(f"Worker {worker_id} started")
        
        while self.is_running:
            try:
                # 从队列获取任务
                request = await self.task_queue.dequeue_task()
                
                if request is None:
                    await asyncio.sleep(0.1)  # 没有任务时短暂休眠
                    continue
                
                # 选择最佳模型
                model = await self.load_balancer.select_best_model(request)
                
                if model is None:
                    logger.error(f"No suitable model found for task {request.task_id}")
                    self.task_queue.complete_task(request.task_id)
                    continue
                
                # 处理请求
                response = await model.process_request(request)
                
                # 更新模型指标
                await self.load_balancer.update_model_metrics(model.model_id, response)
                
                # 缓存响应
                self.response_cache[request.task_id] = response
                
                # 完成任务
                self.task_queue.complete_task(request.task_id)
                
                logger.debug(f"Worker {worker_id} completed task {request.task_id}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {str(e)}")
                await asyncio.sleep(1)  # 错误后休眠
        
        logger.info(f"Worker {worker_id} stopped")
    
    async def submit_task(self, request: TaskRequest) -> str:
        """提交任务"""
        
        # 检查缓存
        cache_key = f"{request.task_type}:{hash(request.content)}"
        if cache_key in self.response_cache:
            cached_response = self.response_cache[cache_key]
            logger.debug(f"Task {request.task_id} served from cache")
            return cached_response.response
        
        # 加入队列
        await self.task_queue.enqueue_task(request)
        
        return request.task_id
    
    async def get_task_result(self, task_id: str, timeout: float = 30.0) -> Optional[ModelResponse]:
        """获取任务结果"""
        
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < timeout:
            if task_id in self.response_cache:
                return self.response_cache[task_id]
            
            await asyncio.sleep(0.1)
        
        return None  # 超时
    
    async def submit_and_wait(self, request: TaskRequest, timeout: float = 30.0) -> Optional[ModelResponse]:
        """提交任务并等待结果"""
        
        await self.submit_task(request)
        return await self.get_task_result(request.task_id, timeout)
    
    async def batch_process(self, requests: List[TaskRequest]) -> List[Optional[ModelResponse]]:
        """批量处理任务"""
        
        # 提交所有任务
        task_ids = []
        for request in requests:
            task_id = await self.submit_task(request)
            task_ids.append(task_id)
        
        # 等待所有结果
        results = []
        for task_id in task_ids:
            result = await self.get_task_result(task_id)
            results.append(result)
        
        return results
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        
        # 模型状态
        model_status = {}
        for model_id, adapter in self.load_balancer.models.items():
            capabilities = adapter.get_capabilities()
            metrics = self.load_balancer.performance_metrics.get(model_id, {})
            
            model_status[model_id] = {
                "available": adapter.is_available,
                "current_load": adapter.current_load,
                "max_concurrent": adapter.max_concurrent,
                "model_type": capabilities.model_type.value,
                "quality_score": capabilities.quality_score,
                "total_requests": metrics.get("total_requests", 0),
                "success_rate": (
                    metrics.get("successful_requests", 0) / max(metrics.get("total_requests", 1), 1)
                ),
                "avg_response_time": metrics.get("avg_response_time", 0.0),
                "total_cost": metrics.get("total_cost", 0.0)
            }
        
        return {
            "is_running": self.is_running,
            "worker_count": len(self.worker_tasks),
            "queue_status": self.task_queue.get_queue_status(),
            "model_status": model_status,
            "cache_size": len(self.response_cache)
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """系统健康检查"""
        
        health_status = {
            "overall_health": "healthy",
            "models": {},
            "issues": []
        }
        
        # 检查每个模型的健康状态
        for model_id, adapter in self.load_balancer.models.items():
            is_healthy = await adapter.health_check()
            health_status["models"][model_id] = {
                "healthy": is_healthy,
                "available": adapter.is_available
            }
            
            if not is_healthy:
                health_status["issues"].append(f"Model {model_id} is unhealthy")
                health_status["overall_health"] = "degraded"
        
        # 检查队列状态
        queue_status = self.task_queue.get_queue_status()
        total_pending = queue_status["total_pending"]
        
        if total_pending > 100:
            health_status["issues"].append(f"High queue load: {total_pending} pending tasks")
            health_status["overall_health"] = "degraded"
        
        if not self.is_running:
            health_status["issues"].append("Workers not running")
            health_status["overall_health"] = "unhealthy"
        
        return health_status


# 全局多模型协调器实例
multi_model_coordinator = MultiModelCoordinator()

# 默认模型配置
DEFAULT_MODEL_CONFIGS = [
    {
        "id": "gpt-3.5-turbo",
        "type": "openai",
        "model_name": "gpt-3.5-turbo",
        "api_key": "your-api-key-here",
        "max_concurrent": 3
    },
    {
        "id": "local-classifier",
        "type": "local",
        "model_type": "classification",
        "model_path": "/path/to/local/model",
        "max_concurrent": 10
    },
    {
        "id": "local-summarizer",
        "type": "local",
        "model_type": "summarization",
        "model_path": "/path/to/summarizer/model",
        "max_concurrent": 8
    }
]