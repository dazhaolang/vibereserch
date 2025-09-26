"""
ResearchRabbit API客户端
支持文献搜索、元数据获取、PDF下载等功能
"""

import asyncio
import aiohttp
import json
from typing import List, Dict, Optional, Any
from urllib.parse import quote
import time
from loguru import logger
from dataclasses import dataclass

from app.core.config import settings
from app.utils.async_limiter import AsyncLimiter


@dataclass
class ResearchRabbitConfig:
    """ResearchRabbit配置"""
    username: Optional[str] = settings.researchrabbit_username
    password: Optional[str] = settings.researchrabbit_password
    base_url: str = settings.researchrabbit_base_url
    requests_per_minute: int = settings.researchrabbit_requests_per_minute
    max_retries: int = settings.researchrabbit_max_retries


class ResearchRabbitClient:
    """ResearchRabbit API客户端"""
    
    def __init__(self, config: Optional[ResearchRabbitConfig] = None):
        self.config = config or ResearchRabbitConfig()
        self.session = None
        self.access_token = None
        self.refresh_token = None
        self.rate_limiter = AsyncLimiter(self.config.requests_per_minute, 60)
        
    async def __aenter__(self):
        """异步上下文管理器入口 - 优化版本"""
        # 创建优化的连接器
        connector = aiohttp.TCPConnector(
            limit=100,                    # 增加连接池大小
            limit_per_host=30,           # 单主机连接数
            enable_cleanup_closed=True,   # 自动清理连接
            use_dns_cache=True,          # 启用DNS缓存
            ttl_dns_cache=300,           # DNS缓存5分钟
            keepalive_timeout=30         # 保持连接30秒
        )
        
        # 优化超时设置
        timeout = aiohttp.ClientTimeout(
            total=45,                    # 总超时45秒
            connect=10,                  # 连接超时10秒
            sock_read=20                 # 读取超时20秒
        )
        
        # 创建会话时启用cookie jar以支持cookie认证
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Encoding": "gzip, deflate, br",  # 启用压缩
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
                "Connection": "keep-alive",
                "Cache-Control": "no-cache"
            },
            # 启用自动解压缩
            auto_decompress=True
        )
        await self.login()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        if self.session:
            await self.session.close()
    
    async def login(self) -> bool:
        """登录获取访问令牌"""
        if not self.config.username or not self.config.password:
            raise RuntimeError(
                "ResearchRabbit账号未配置。请在环境变量或设置中提供用户名和密码"
            )

        try:
            login_data = {
                "no_redirect": True,
                "username": self.config.username,
                "password": self.config.password
            }

            async with self.session.post(
                f"{self.config.base_url}/api/login",
                json=login_data
            ) as response:
                if response.status == 201:
                    data = await response.json()
                    self.access_token = data.get("access")
                    self.refresh_token = data.get("refresh")

                    logger.info("ResearchRabbit登录成功")
                    return True

                response_text = await response.text()
                raise RuntimeError(
                    f"ResearchRabbit登录失败: {response.status} - {response_text}"
                )

        except Exception as e:
            logger.error(f"ResearchRabbit登录异常: {e}")
            raise
    
    async def search_papers(
        self, 
        query: str, 
        limit: int = 50, 
        offset: int = 0
    ) -> Dict[str, Any]:
        """搜索文献"""
        try:
            async with self.rate_limiter:
                # 根据API文档构建正确的URL参数顺序：offset, limit, fields, query
                url = (f"{self.config.base_url}/s2"
                      f"?offset={offset}"
                      f"&limit={limit}"
                      f"&fields=title,authors,abstract,fieldsOfStudy,referenceCount,citationCount,year,externalIds,url,isOpenAccess,venue"
                      f"&query={quote(query)}")
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        response_text = await response.text()
                        logger.error(f"搜索失败: {response.status} - {response_text}")
                        return {"data": [], "total": 0}
                        
        except Exception as e:
            logger.error(f"搜索异常: {e}")
            return {"data": [], "total": 0}
    
    async def search_all_papers(
        self, 
        query: str, 
        max_count: int = 1000
    ) -> List[Dict[str, Any]]:
        """分页获取所有搜索结果"""
        all_papers = []
        offset = 0
        limit = 50  # ResearchRabbit单次最大限制
        
        logger.info(f"开始搜索文献: {query}, 最大数量: {max_count}")
        
        while len(all_papers) < max_count:
            # 计算本次获取数量
            current_limit = min(limit, max_count - len(all_papers))
            
            logger.info(f"获取第 {offset//limit + 1} 页，偏移量: {offset}")
            
            # 搜索当前页
            result = await self.search_papers(query, current_limit, offset)
            
            if not result.get("data"):
                logger.info("没有更多数据，搜索结束")
                break
            
            papers = result["data"]
            all_papers.extend(papers)
            
            logger.info(f"本页获取 {len(papers)} 篇文献，累计 {len(all_papers)} 篇")
            
            # 检查是否还有更多数据
            if len(papers) < current_limit:
                logger.info("已获取所有可用数据")
                break
            
            # 更新偏移量
            offset += len(papers)
            
            # 避免过快请求
            await asyncio.sleep(1)
        
        logger.info(f"搜索完成，总共获取 {len(all_papers)} 篇文献")
        return all_papers
    
    def create_metadata_identifier(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """从论文数据创建元数据标识符
        
        Args:
            paper: 从搜索API返回的论文数据
            
        Returns:
            符合元数据API要求的标识符格式
        """
        external_ids = paper.get("externalIds", {})
        
        return {
            "pmcid": external_ids.get("PMCID"),
            "doi": external_ids.get("DOI"),
            "rrid": external_ids.get("RRID"),
            "s2id": paper.get("paperId"),  # Semantic Scholar ID
            "arxiv_id": external_ids.get("ArXiv")
        }
    
    async def get_metadata_batch(
        self, 
        identifiers: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """批量获取文献元数据
        
        Args:
            identifiers: 标识符列表，格式应为：
            [
                {
                    "pmcid": null,
                    "doi": "10.1016/j.colsurfb.2022.112971",
                    "rrid": null,
                    "s2id": null,
                    "arxiv_id": null
                }
            ]
        """
        try:
            async with self.rate_limiter:
                # 确保identifiers格式符合API要求
                formatted_identifiers = []
                for identifier in identifiers:
                    # 标准化标识符格式，确保包含所有必需字段
                    formatted_id = {
                        "pmcid": identifier.get("pmcid"),
                        "doi": identifier.get("doi"),
                        "rrid": identifier.get("rrid"),
                        "s2id": identifier.get("s2id"),
                        "arxiv_id": identifier.get("arxiv_id")
                    }
                    formatted_identifiers.append(formatted_id)
                
                async with self.session.post(
                    f"{self.config.base_url}/api/v1/proxy/paper-metadata",
                    json=formatted_identifiers
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        response_text = await response.text()
                        logger.error(f"获取元数据失败: {response.status} - {response_text}")
                        return {}
                        
        except Exception as e:
            logger.error(f"获取元数据异常: {e}")
            return {}
    
    async def get_pdf_info(self, doi: str) -> Optional[Dict[str, Any]]:
        """获取PDF下载信息（通过Unpaywall）"""
        try:
            async with self.rate_limiter:
                # 根据API文档，使用指定的email参数
                url = f"{self.config.base_url}/unpaywall/{doi}?email=researchrabbittech@gmail.com"
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("is_oa") and data.get("best_oa_location"):
                            return data["best_oa_location"]
                    elif response.status != 404:  # 404是正常的（论文不开放获取）
                        response_text = await response.text()
                        logger.warning(f"获取PDF信息失败: {response.status} - {response_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"获取PDF信息异常: {e}")
            return None
    
    async def get_citations(
        self, 
        paper_id: int, 
        citation_type: str = "cited-by",
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """获取引用关系
        
        Args:
            paper_id: 论文内部ID
            citation_type: "cited-by" 或 "bibliography"
            limit: 返回数量限制
            offset: 偏移量
        """
        try:
            async with self.rate_limiter:
                endpoint = f"/api/calculations/v2/{citation_type}"
                # 根据API文档构建请求数据
                data = {
                    "paging": {
                        "offset": offset, 
                        "limit": limit
                    },
                    "paper_id": paper_id
                }
                
                async with self.session.post(
                    f"{self.config.base_url}{endpoint}",
                    json=data
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        response_text = await response.text()
                        logger.error(f"获取引用关系失败: {response.status} - {response_text}")
                        return {}
                        
        except Exception as e:
            logger.error(f"获取引用关系异常: {e}")
            return {}
    
    async def download_pdf(self, pdf_url: str, max_retries: int = 3) -> Optional[bytes]:
        """下载PDF文件 - 优化版本"""
        for attempt in range(max_retries + 1):
            try:
                async with self.rate_limiter:
                    async with self.session.get(
                        pdf_url,
                        headers={
                            "Accept": "application/pdf, */*",
                            "Referer": "https://www.researchrabbitapp.com/",
                        }
                    ) as response:
                        if response.status == 200:
                            # 分块读取大文件，避免内存溢出
                            chunks = []
                            async for chunk in response.content.iter_chunked(8192):
                                chunks.append(chunk)
                            return b''.join(chunks)
                        elif response.status in [429, 503, 502, 504] and attempt < max_retries:
                            # 可重试的错误，使用指数退避
                            wait_time = 2 ** attempt
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            logger.error(f"PDF下载失败: {response.status}")
                            return None
                        
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                    continue
                logger.error(f"PDF下载异常: {e}")
                return None
        
        return None
    
    async def batch_download_pdfs(self, pdf_urls: List[str], max_concurrent: int = 10) -> List[Optional[bytes]]:
        """批量下载PDF - 并发优化版本"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def download_single(url):
            async with semaphore:
                return await self.download_pdf(url)
        
        tasks = [download_single(url) for url in pdf_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        final_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"批量下载异常: {result}")
                final_results.append(None)
            else:
                final_results.append(result)
        
        return final_results
