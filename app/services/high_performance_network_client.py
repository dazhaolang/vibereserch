"""
高性能网络客户端 - 优化Research Rabbit和PDF下载性能
"""

import asyncio
import aiohttp
import aiofiles
import time
from typing import Optional, List, Dict, Union
from dataclasses import dataclass
from urllib.parse import urlparse
import ssl
from concurrent.futures import ThreadPoolExecutor

@dataclass
class NetworkConfig:
    """网络配置优化"""
    # 连接池设置
    max_connections: int = 100          # 最大连接数
    max_connections_per_host: int = 30  # 单主机最大连接数
    
    # 超时设置 (优化后)
    total_timeout: float = 60.0         # 总超时
    connect_timeout: float = 10.0       # 连接超时
    read_timeout: float = 30.0          # 读取超时
    
    # 重试设置
    max_retries: int = 3
    retry_delay_base: float = 1.0       # 指数退避基数
    
    # 并发控制
    max_concurrent_downloads: int = 20  # 最大并发下载数
    chunk_size: int = 8192             # 下载块大小
    
    # HTTP/2优化
    enable_http2: bool = True          # 启用HTTP/2
    http2_max_streams: int = 100       # HTTP/2最大流数
    
    # 缓存设置
    enable_dns_cache: bool = True      # DNS缓存
    dns_cache_ttl: int = 300          # DNS缓存TTL(秒)

class HighPerformanceNetworkClient:
    """高性能网络客户端"""
    
    def __init__(self, config: Optional[NetworkConfig] = None):
        self.config = config or NetworkConfig()
        self.session: Optional[aiohttp.ClientSession] = None
        self.download_semaphore = asyncio.Semaphore(self.config.max_concurrent_downloads)
        self.stats = {
            "requests_made": 0,
            "bytes_downloaded": 0,
            "cache_hits": 0,
            "retry_attempts": 0,
            "average_speed": 0.0
        }
        
    async def __aenter__(self):
        """异步上下文管理器 - 创建优化的session"""
        await self._create_optimized_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """清理资源"""
        if self.session:
            await self.session.close()
    
    async def _create_optimized_session(self):
        """创建优化的HTTP会话"""
        # SSL配置优化
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # 连接器配置 - 支持HTTP/2
        connector = aiohttp.TCPConnector(
            limit=self.config.max_connections,
            limit_per_host=self.config.max_connections_per_host,
            ssl=ssl_context,
            enable_cleanup_closed=True,  # 清理关闭的连接
            use_dns_cache=self.config.enable_dns_cache,
            ttl_dns_cache=self.config.dns_cache_ttl,
            keepalive_timeout=30        # 保持连接30秒
        )
        
        # 超时配置
        timeout = aiohttp.ClientTimeout(
            total=self.config.total_timeout,
            connect=self.config.connect_timeout,
            sock_read=self.config.read_timeout
        )
        
        # 创建会话
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
                "Connection": "keep-alive"
            },
            # 启用压缩
            auto_decompress=True,
            # 启用cookie支持
            cookie_jar=aiohttp.CookieJar()
        )
    
    async def download_with_retry(
        self, 
        url: str, 
        max_retries: Optional[int] = None,
        progress_callback=None
    ) -> Optional[bytes]:
        """带重试的下载方法"""
        max_retries = max_retries or self.config.max_retries
        
        async with self.download_semaphore:
            for attempt in range(max_retries + 1):
                try:
                    start_time = time.time()
                    
                    async with self.session.get(url) as response:
                        if response.status == 200:
                            content = await self._download_with_progress(
                                response, progress_callback
                            )
                            
                            # 更新统计
                            download_time = time.time() - start_time
                            self.stats["requests_made"] += 1
                            self.stats["bytes_downloaded"] += len(content)
                            
                            # 计算平均速度 (MB/s)
                            speed = len(content) / (1024 * 1024) / download_time if download_time > 0 else 0
                            self.stats["average_speed"] = (
                                self.stats["average_speed"] * (self.stats["requests_made"] - 1) + speed
                            ) / self.stats["requests_made"]
                            
                            return content
                            
                        elif response.status in [429, 503, 502, 504]:  # 可重试错误
                            if attempt < max_retries:
                                delay = self.config.retry_delay_base * (2 ** attempt)  # 指数退避
                                await asyncio.sleep(delay)
                                self.stats["retry_attempts"] += 1
                                continue
                            
                        return None
                        
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    if attempt < max_retries:
                        delay = self.config.retry_delay_base * (2 ** attempt)
                        await asyncio.sleep(delay)
                        self.stats["retry_attempts"] += 1
                        continue
                    
                    print(f"下载失败 {url}: {e}")
                    return None
            
            return None
    
    async def _download_with_progress(
        self, 
        response: aiohttp.ClientResponse, 
        progress_callback=None
    ) -> bytes:
        """带进度回调的下载"""
        content = bytearray()
        total_size = int(response.headers.get('Content-Length', 0))
        downloaded = 0
        
        async for chunk in response.content.iter_chunked(self.config.chunk_size):
            content.extend(chunk)
            downloaded += len(chunk)
            
            if progress_callback and total_size > 0:
                progress = downloaded / total_size
                await progress_callback(downloaded, total_size, progress)
        
        return bytes(content)
    
    async def batch_download(
        self, 
        urls: List[str],
        progress_callback=None
    ) -> List[Optional[bytes]]:
        """批量下载 - 并发优化"""
        
        # 创建下载任务
        tasks = []
        for i, url in enumerate(urls):
            task_progress_callback = None
            if progress_callback:
                task_progress_callback = lambda d, t, p, idx=i: progress_callback(idx, d, t, p)
            
            task = self.download_with_retry(url, progress_callback=task_progress_callback)
            tasks.append(task)
        
        # 并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        final_results = []
        for result in results:
            if isinstance(result, Exception):
                final_results.append(None)
            else:
                final_results.append(result)
        
        return final_results
    
    async def request_json(
        self, 
        method: str, 
        url: str, 
        **kwargs
    ) -> Optional[Dict]:
        """JSON请求 - 针对API调用优化"""
        try:
            async with self.session.request(method, url, **kwargs) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 429:  # 速率限制
                    retry_after = response.headers.get('Retry-After', '1')
                    await asyncio.sleep(int(retry_after))
                    # 递归重试一次
                    return await self.request_json(method, url, **kwargs)
                return None
        except Exception as e:
            print(f"JSON请求失败 {url}: {e}")
            return None
    
    async def save_to_file(
        self, 
        content: bytes, 
        file_path: str
    ) -> bool:
        """异步保存文件"""
        try:
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(content)
            return True
        except Exception as e:
            print(f"文件保存失败 {file_path}: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """获取性能统计"""
        return {
            **self.stats,
            "efficiency_rating": self._calculate_efficiency(),
            "recommended_optimization": self._get_optimization_suggestions()
        }
    
    def _calculate_efficiency(self) -> str:
        """计算效率评级"""
        avg_speed = self.stats["average_speed"]
        retry_rate = self.stats["retry_attempts"] / max(self.stats["requests_made"], 1)
        
        if avg_speed > 5.0 and retry_rate < 0.1:
            return "优秀"
        elif avg_speed > 2.0 and retry_rate < 0.2:
            return "良好"
        elif avg_speed > 0.5 and retry_rate < 0.3:
            return "一般"
        else:
            return "需要优化"
    
    def _get_optimization_suggestions(self) -> List[str]:
        """获取优化建议"""
        suggestions = []
        
        if self.stats["average_speed"] < 1.0:
            suggestions.append("考虑增加并发连接数")
            
        if self.stats["retry_attempts"] / max(self.stats["requests_made"], 1) > 0.2:
            suggestions.append("检查网络稳定性或增加重试延迟")
            
        if self.stats["requests_made"] > 100:
            suggestions.append("考虑使用连接池和DNS缓存")
            
        return suggestions or ["性能表现良好"]


class OptimizedResearchRabbitClient:
    """优化的Research Rabbit客户端"""
    
    def __init__(self):
        self.base_url = "https://www.researchrabbitapp.com"
        self.network_config = NetworkConfig(
            max_concurrent_downloads=15,  # Research Rabbit API限制
            max_connections_per_host=20,
            total_timeout=45.0
        )
    
    async def search_papers_fast(
        self, 
        query: str, 
        limit: int = 20
    ) -> Optional[Dict]:
        """优化的论文搜索"""
        
        async with HighPerformanceNetworkClient(self.network_config) as client:
            search_url = f"{self.base_url}/api/search"
            
            payload = {
                "query": query,
                "limit": limit,
                "include_metadata": True
            }
            
            result = await client.request_json("POST", search_url, json=payload)
            
            if result:
                print(f"🔍 搜索完成: {query}")
                print(f"📊 性能统计: {client.get_stats()}")
            
            return result
    
    async def batch_download_pdfs(
        self, 
        pdf_urls: List[str],
        save_directory: str = "/tmp"
    ) -> List[str]:
        """批量PDF下载 - 高性能版本"""
        
        async with HighPerformanceNetworkClient(self.network_config) as client:
            
            # 批量下载
            def progress_callback(task_idx, downloaded, total, progress):
                print(f"📥 任务{task_idx}: {downloaded/1024/1024:.1f}MB / {total/1024/1024:.1f}MB ({progress*100:.1f}%)")
            
            results = await client.batch_download(pdf_urls, progress_callback)
            
            # 保存文件
            saved_files = []
            for i, (url, content) in enumerate(zip(pdf_urls, results)):
                if content:
                    filename = f"{save_directory}/paper_{i}_{int(time.time())}.pdf"
                    if await client.save_to_file(content, filename):
                        saved_files.append(filename)
            
            print(f"💾 保存完成: {len(saved_files)}/{len(pdf_urls)} 个文件")
            print(f"📊 下载统计: {client.get_stats()}")
            
            return saved_files


# 使用示例和性能对比
async def performance_comparison_demo():
    """性能对比演示"""
    print("🚀 网络性能优化对比测试")
    print("=" * 50)
    
    # 测试URL
    test_urls = [
        "https://arxiv.org/pdf/1706.03762.pdf",  # Transformer
        "https://arxiv.org/pdf/1810.04805.pdf",  # BERT
        "https://arxiv.org/pdf/2005.14165.pdf",  # GPT-3
    ]
    
    # 1. 优化前 (传统aiohttp)
    print("📊 测试1: 传统aiohttp方法")
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for url in test_urls:
            task = session.get(url)
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        contents = []
        for resp in responses:
            if not isinstance(resp, Exception):
                content = await resp.read()
                contents.append(content)
                resp.close()
    
    traditional_time = time.time() - start_time
    print(f"⏱️ 传统方法耗时: {traditional_time:.2f}秒")
    
    # 2. 优化后 (高性能客户端)
    print("\\n📊 测试2: 高性能网络客户端")
    start_time = time.time()
    
    async with HighPerformanceNetworkClient() as client:
        optimized_results = await client.batch_download(test_urls)
    
    optimized_time = time.time() - start_time
    print(f"⏱️ 优化方法耗时: {optimized_time:.2f}秒")
    
    # 性能提升计算
    if optimized_time > 0:
        improvement = (traditional_time - optimized_time) / optimized_time * 100
        print(f"\\n🎯 性能提升: {improvement:.1f}%")
        print(f"📈 效率提升: {traditional_time/optimized_time:.1f}x")
    
    return {
        "traditional_time": traditional_time,
        "optimized_time": optimized_time,
        "improvement_percentage": improvement if optimized_time > 0 else 0
    }

if __name__ == "__main__":
    asyncio.run(performance_comparison_demo())