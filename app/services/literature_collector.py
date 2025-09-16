"""
文献采集服务 - 完整商业化版本
支持多渠道采集、智能初筛、会员服务差异化
集成ResearchRabbit API
"""

import asyncio
import aiohttp
import os
import tempfile
import hashlib
from typing import List, Dict, Optional, Tuple, Any
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup
import json
import re
import time
from datetime import datetime, timedelta
from loguru import logger
import xml.etree.ElementTree as ET

from app.core.config import settings
from app.models.literature import Literature
from app.models.user import User, MembershipType
from app.services.ai_service import AIService
from app.services.research_rabbit_client import ResearchRabbitClient, ResearchRabbitConfig
from app.services.pdf_processor import PDFProcessor
from app.utils.rate_limiter import RateLimiter, global_rate_limiter
from app.schemas.user_schemas import MembershipLimits

class EnhancedLiteratureCollector:
    """增强版文献采集器 - 商业化版本"""
    
    def __init__(self, ai_service: Optional[AIService] = None):
        # 使用全局限流器管理不同来源
        self.rate_limiter = global_rate_limiter
        
        # 依赖注入AI服务（便于测试和解耦）
        self.ai_service = ai_service or AIService()
        
        # PDF处理器
        self.pdf_processor = PDFProcessor()
        
        # ResearchRabbit客户端（懒加载）
        self._rr_client = None
        
        # 使用统一的会员限制配置
        self._membership_limits_cache = {}
    
    def _get_membership_limits(self, membership_type: MembershipType) -> Dict[str, Any]:
        """获取会员限制配置"""
        if membership_type not in self._membership_limits_cache:
            limits = MembershipLimits.get_limits(membership_type)
            self._membership_limits_cache[membership_type] = {
                "max_literature": limits.max_literature,
                "sources": limits.available_sources
            }
        
        return self._membership_limits_cache[membership_type]
        
    async def collect_literature_with_screening(
        self, 
        keywords: List[str], 
        user: User,
        max_count: int = None,
        sources: List[str] = None,
        enable_ai_screening: bool = True,
        progress_callback = None
    ) -> Dict:
        """
        智能文献采集与初筛 - 商业化版本
        
        Args:
            keywords: 关键词列表
            user: 用户对象（用于会员限制）
            max_count: 最大采集数量（会被会员限制覆盖）
            sources: 采集源列表（会被会员限制覆盖）
            enable_ai_screening: 是否启用AI初筛
            progress_callback: 进度回调函数
        
        Returns:
            采集结果字典
        """
        # 获取用户会员限制
        membership_type = user.membership.membership_type if user.membership else MembershipType.FREE
        limits = self._get_membership_limits(membership_type)
        
        # 应用会员限制
        effective_max_count = min(max_count or limits["max_literature"], limits["max_literature"])
        effective_sources = sources or limits["sources"]
        
        logger.info(f"开始文献采集 - 用户: {user.username}, 会员类型: {membership_type.value}, 限制: {effective_max_count}篇")
        
        if progress_callback:
            await progress_callback("开始文献采集", 0, {"total_sources": len(effective_sources)})
        
        # 第一阶段：多渠道采集原始文献
        all_literature = []
        per_source_count = min(effective_max_count * 2, 5000) // len(effective_sources)  # 采集更多用于初筛
        
        collection_tasks = []
        for source in effective_sources:
            if source == "researchrabbit":
                collection_tasks.append(self._collect_from_researchrabbit(keywords, per_source_count))
            elif source == "semantic_scholar":
                collection_tasks.append(self._collect_from_semantic_scholar(keywords, per_source_count))
            elif source == "google_scholar":
                collection_tasks.append(self._collect_from_google_scholar(keywords, per_source_count))
            elif source == "pubmed":
                collection_tasks.append(self._collect_from_pubmed(keywords, per_source_count))
            elif source == "arxiv":
                collection_tasks.append(self._collect_from_arxiv(keywords, per_source_count))
            elif source == "crossref":
                collection_tasks.append(self._collect_from_crossref(keywords, per_source_count))
        
        # 并行采集
        collection_results = await asyncio.gather(*collection_tasks, return_exceptions=True)
        
        for i, result in enumerate(collection_results):
            if isinstance(result, Exception):
                logger.error(f"文献采集错误 - 来源 {effective_sources[i]}: {result}")
                continue
            all_literature.extend(result)
        
        if progress_callback:
            await progress_callback("文献采集完成", 30, {"collected_count": len(all_literature)})
        
        # 第二阶段：去重和基础过滤
        unique_literature = self._deduplicate_literature(all_literature)
        logger.info(f"去重后文献数量: {len(unique_literature)}")
        
        if progress_callback:
            await progress_callback("文献去重完成", 40, {"unique_count": len(unique_literature)})
        
        # 第三阶段：AI智能初筛
        screened_literature = unique_literature
        if enable_ai_screening and len(unique_literature) > effective_max_count:
            logger.info("开始AI智能初筛")
            screened_literature = await self._ai_screen_literature(
                unique_literature, keywords, effective_max_count, progress_callback
            )
        
        # 第四阶段：最终排序和截取
        final_literature = self._sort_literature_by_relevance(screened_literature, keywords)
        final_literature = final_literature[:effective_max_count]
        
        if progress_callback:
            await progress_callback("文献采集完成", 100, {"final_count": len(final_literature)})
        
        return {
            "literature": final_literature,
            "statistics": {
                "total_collected": len(all_literature),
                "after_deduplication": len(unique_literature),
                "after_screening": len(screened_literature),
                "final_count": len(final_literature),
                "sources_used": effective_sources,
                "membership_type": membership_type.value,
                "ai_screening_enabled": enable_ai_screening
            }
        }
    
    async def _collect_from_semantic_scholar(self, keywords: List[str], max_count: int) -> List[Dict]:
        """从Semantic Scholar采集文献"""
        literature_list = []
        
        async with aiohttp.ClientSession() as session:
            for keyword in keywords:
                await self.semantic_scholar_limiter.acquire()
                
                url = "https://api.semanticscholar.org/graph/v1/paper/search"
                params = {
                    "query": keyword,
                    "limit": min(max_count // len(keywords), 100),
                    "fields": "paperId,title,authors,abstract,year,journal,citationCount,url,openAccessPdf"
                }
                
                headers = {}
                if settings.semantic_scholar_api_key:
                    headers["x-api-key"] = settings.semantic_scholar_api_key
                
                try:
                    async with session.get(url, params=params, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            papers = data.get("data", [])
                            
                            for paper in papers:
                                literature_data = self._parse_semantic_scholar_paper(paper)
                                if literature_data:
                                    literature_list.append(literature_data)
                        else:
                            logger.warning(f"Semantic Scholar API错误: {response.status}")
                            
                except Exception as e:
                    logger.error(f"Semantic Scholar请求失败: {e}")
        
        return literature_list
    
    async def _collect_from_pubmed(self, keywords: List[str], max_count: int) -> List[Dict]:
        """从PubMed采集文献"""
        literature_list = []
        
        async with aiohttp.ClientSession() as session:
            for keyword in keywords:
                await self.pubmed_limiter.acquire()
                
                # 第一步：搜索获取ID列表
                search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
                search_params = {
                    "db": "pubmed",
                    "term": keyword,
                    "retmax": min(max_count // len(keywords), 200),
                    "retmode": "json",
                    "sort": "relevance"
                }
                
                try:
                    async with session.get(search_url, params=search_params) as response:
                        if response.status == 200:
                            search_data = await response.json()
                            pmids = search_data.get("esearchresult", {}).get("idlist", [])
                            
                            if pmids:
                                # 第二步：获取详细信息
                                await self.pubmed_limiter.acquire()
                                
                                fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
                                fetch_params = {
                                    "db": "pubmed",
                                    "id": ",".join(pmids[:50]),  # 每次最多50篇
                                    "retmode": "xml"
                                }
                                
                                async with session.get(fetch_url, params=fetch_params) as fetch_response:
                                    if fetch_response.status == 200:
                                        xml_content = await fetch_response.text()
                                        papers = self._parse_pubmed_xml(xml_content)
                                        literature_list.extend(papers)
                                        
                        else:
                            logger.warning(f"PubMed搜索失败: {response.status}")
                            
                except Exception as e:
                    logger.error(f"PubMed请求失败: {e}")
        
        return literature_list
    
    async def _collect_from_arxiv(self, keywords: List[str], max_count: int) -> List[Dict]:
        """从arXiv采集文献"""
        literature_list = []
        
        async with aiohttp.ClientSession() as session:
            for keyword in keywords:
                await self.arxiv_limiter.acquire()
                
                url = "http://export.arxiv.org/api/query"
                params = {
                    "search_query": f"all:{keyword}",
                    "start": 0,
                    "max_results": min(max_count // len(keywords), 100),
                    "sortBy": "relevance",
                    "sortOrder": "descending"
                }
                
                try:
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            xml_content = await response.text()
                            papers = self._parse_arxiv_xml(xml_content)
                            literature_list.extend(papers)
                        else:
                            logger.warning(f"arXiv API错误: {response.status}")
                            
                except Exception as e:
                    logger.error(f"arXiv请求失败: {e}")
        
        return literature_list
    
    async def _collect_from_crossref(self, keywords: List[str], max_count: int) -> List[Dict]:
        """从Crossref采集文献"""
        literature_list = []
        
        async with aiohttp.ClientSession() as session:
            for keyword in keywords:
                await self.crossref_limiter.acquire()
                
                url = "https://api.crossref.org/works"
                params = {
                    "query": keyword,
                    "rows": min(max_count // len(keywords), 100),
                    "sort": "relevance",
                    "order": "desc"
                }
                
                headers = {
                    "User-Agent": "ResearchPlatform/1.0 (mailto:admin@research-platform.com)"
                }
                
                try:
                    async with session.get(url, params=params, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            works = data.get("message", {}).get("items", [])
                            
                            for work in works:
                                literature_data = self._parse_crossref_work(work)
                                if literature_data:
                                    literature_list.append(literature_data)
                        else:
                            logger.warning(f"Crossref API错误: {response.status}")
                            
                except Exception as e:
                    logger.error(f"Crossref请求失败: {e}")
        
        return literature_list
    
    async def _ai_screen_literature(
        self, 
        literature_list: List[Dict], 
        keywords: List[str], 
        target_count: int,
        progress_callback = None
    ) -> List[Dict]:
        """AI智能初筛文献"""
        if len(literature_list) <= target_count:
            return literature_list
        
        logger.info(f"开始AI初筛，从{len(literature_list)}篇筛选到{target_count}篇")
        
        # 分批进行AI评估，避免token限制
        batch_size = 20
        screened_literature = []
        
        for i in range(0, len(literature_list), batch_size):
            batch = literature_list[i:i + batch_size]
            
            # 构建筛选提示
            screening_prompt = f"""
你是一个文献相关性评估专家。请评估以下文献与研究关键词的相关性。

研究关键词: {', '.join(keywords)}

请为每篇文献打分（1-10分），10分表示高度相关，1分表示不相关。
只返回JSON格式的评分结果，格式如下：
{{"scores": [8, 6, 9, 3, 7, ...]}}

文献列表：
"""
            
            for j, lit in enumerate(batch):
                screening_prompt += f"\n{j+1}. 标题: {lit.get('title', 'N/A')}\n"
                screening_prompt += f"   摘要: {(lit.get('abstract', '') or '')[:300]}...\n"
            
            try:
                # 调用AI服务进行评估
                response = await self.ai_service.generate_completion(
                    screening_prompt,
                    model="gpt-3.5-turbo",  # 使用较便宜的模型进行初筛
                    max_tokens=200,
                    temperature=0.1
                )
                
                if response.get("success"):
                    scores_text = response["content"].strip()
                    # 尝试解析JSON
                    try:
                        scores_data = json.loads(scores_text)
                        scores = scores_data.get("scores", [])
                        
                        # 为每篇文献添加相关性评分
                        for j, score in enumerate(scores):
                            if j < len(batch):
                                batch[j]["ai_relevance_score"] = score
                                
                    except json.JSONDecodeError:
                        # 如果JSON解析失败，给所有文献中等评分
                        for lit in batch:
                            lit["ai_relevance_score"] = 5
                            
                else:
                    # AI评估失败，给所有文献中等评分
                    for lit in batch:
                        lit["ai_relevance_score"] = 5
                        
            except Exception as e:
                logger.error(f"AI初筛失败: {e}")
                # 失败时给所有文献中等评分
                for lit in batch:
                    lit["ai_relevance_score"] = 5
            
            screened_literature.extend(batch)
            
            # 更新进度
            if progress_callback:
                progress = 40 + (i / len(literature_list)) * 40  # 40-80%
                await progress_callback(
                    f"AI初筛进行中 ({i + len(batch)}/{len(literature_list)})", 
                    progress,
                    {"screened_count": len(screened_literature)}
                )
        
        # 按AI评分排序并选择前N篇
        screened_literature.sort(key=lambda x: x.get("ai_relevance_score", 0), reverse=True)
        final_screened = screened_literature[:target_count]
        
        logger.info(f"AI初筛完成，选择了{len(final_screened)}篇高相关性文献")
        return final_screened
    
    async def _collect_from_google_scholar(self, keywords: List[str], max_count: int) -> List[Dict]:
        """从Google Scholar采集文献（通过网页抓取）"""
        literature_list = []
        
        async with aiohttp.ClientSession() as session:
            for keyword in keywords:
                await self.google_scholar_limiter.acquire()
                
                # Google Scholar搜索URL
                query = quote(" ".join(keywords) if len(keywords) > 1 else keyword)
                url = f"https://scholar.google.com/scholar?q={query}&hl=en&num=100"
                
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                
                try:
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            html = await response.text()
                            papers = self._parse_google_scholar_results(html)
                            literature_list.extend(papers)
                        else:
                            logger.warning(f"Google Scholar请求失败: {response.status}")
                            
                except Exception as e:
                    logger.error(f"Google Scholar抓取失败: {e}")
                
                # 避免被封IP
                await asyncio.sleep(2)
        
        return literature_list[:max_count]
    
    def _parse_semantic_scholar_paper(self, paper: Dict) -> Optional[Dict]:
        """解析Semantic Scholar论文数据"""
        try:
            authors = []
            if paper.get("authors"):
                authors = [author.get("name", "") for author in paper["authors"]]
            
            pdf_url = None
            if paper.get("openAccessPdf"):
                pdf_url = paper["openAccessPdf"].get("url")
            
            return {
                "title": paper.get("title", ""),
                "authors": authors,
                "abstract": paper.get("abstract", ""),
                "publication_year": paper.get("year"),
                "journal": paper.get("journal", {}).get("name") if paper.get("journal") else None,
                "citation_count": paper.get("citationCount", 0),
                "doi": paper.get("externalIds", {}).get("DOI") if paper.get("externalIds") else None,
                "source_platform": "semantic_scholar",
                "source_url": paper.get("url"),
                "pdf_url": pdf_url,
                "quality_score": self._calculate_quality_score(paper)
            }
        except Exception as e:
            logger.error(f"解析Semantic Scholar论文失败: {e}")
            return None
    
    def _parse_google_scholar_results(self, html: str) -> List[Dict]:
        """解析Google Scholar搜索结果"""
        papers = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            results = soup.find_all('div', class_='gs_r gs_or gs_scl')
            
            for result in results:
                try:
                    # 提取标题
                    title_elem = result.find('h3', class_='gs_rt')
                    if not title_elem:
                        continue
                    
                    title_link = title_elem.find('a')
                    title = title_link.text if title_link else title_elem.text
                    source_url = title_link.get('href') if title_link else None
                    
                    # 提取作者和期刊信息
                    authors_elem = result.find('div', class_='gs_a')
                    authors_text = authors_elem.text if authors_elem else ""
                    
                    # 提取摘要
                    abstract_elem = result.find('div', class_='gs_rs')
                    abstract = abstract_elem.text if abstract_elem else ""
                    
                    # 提取引用数
                    citation_elem = result.find('div', class_='gs_fl')
                    citation_count = 0
                    if citation_elem:
                        citation_links = citation_elem.find_all('a')
                        for link in citation_links:
                            if 'Cited by' in link.text:
                                citation_count = int(link.text.split('Cited by ')[1]) if 'Cited by ' in link.text else 0
                                break
                    
                    paper_data = {
                        "title": title.strip(),
                        "authors": self._parse_authors_from_text(authors_text),
                        "abstract": abstract.strip(),
                        "publication_year": self._extract_year_from_text(authors_text),
                        "journal": self._extract_journal_from_text(authors_text),
                        "citation_count": citation_count,
                        "source_platform": "google_scholar",
                        "source_url": source_url,
                        "quality_score": self._calculate_quality_score_from_text(citation_count, authors_text)
                    }
                    
                    papers.append(paper_data)
                    
                except Exception as e:
                    logger.error(f"解析Google Scholar单个结果失败: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"解析Google Scholar结果失败: {e}")
        
        return papers
    
    def _calculate_quality_score(self, paper: Dict) -> float:
        """计算论文质量评分"""
        score = 0.0
        
        # 引用数评分 (0-40分)
        citation_count = paper.get("citationCount", 0)
        if citation_count > 100:
            score += 40
        elif citation_count > 50:
            score += 30
        elif citation_count > 10:
            score += 20
        elif citation_count > 0:
            score += 10
        
        # 年份评分 (0-20分)
        year = paper.get("year")
        if year:
            current_year = datetime.now().year
            if year >= current_year - 2:
                score += 20
            elif year >= current_year - 5:
                score += 15
            elif year >= current_year - 10:
                score += 10
            else:
                score += 5
        
        # 期刊评分 (0-20分)
        journal = paper.get("journal", {})
        if isinstance(journal, dict) and journal.get("name"):
            score += 15  # 有期刊信息
        
        # 摘要完整性 (0-20分)
        abstract = paper.get("abstract", "")
        if len(abstract) > 500:
            score += 20
        elif len(abstract) > 200:
            score += 15
        elif len(abstract) > 50:
            score += 10
        
        return min(score, 100.0)
    
    def _calculate_quality_score_from_text(self, citation_count: int, authors_text: str) -> float:
        """从文本信息计算质量评分"""
        score = 0.0
        
        # 引用数评分
        if citation_count > 100:
            score += 40
        elif citation_count > 50:
            score += 30
        elif citation_count > 10:
            score += 20
        elif citation_count > 0:
            score += 10
        
        # 作者和期刊信息完整性
        if authors_text and len(authors_text) > 20:
            score += 30
        
        return min(score, 100.0)
    
    def _parse_authors_from_text(self, authors_text: str) -> List[str]:
        """从文本中解析作者列表"""
        if not authors_text:
            return []
        
        # 简单的作者解析逻辑
        authors = []
        parts = authors_text.split('-')[0].split(',')
        for part in parts[:5]:  # 最多取前5个作者
            author = part.strip()
            if author and len(author) > 2:
                authors.append(author)
        
        return authors
    
    def _extract_year_from_text(self, text: str) -> Optional[int]:
        """从文本中提取年份"""
        import re
        if not text:
            return None
        
        # 查找4位数年份
        year_match = re.search(r'\b(19|20)\d{2}\b', text)
        if year_match:
            return int(year_match.group())
        
        return None
    
    def _extract_journal_from_text(self, text: str) -> Optional[str]:
        """从文本中提取期刊名称"""
        if not text:
            return None
        
        # 简单的期刊名提取逻辑
        parts = text.split('-')
        if len(parts) > 1:
            journal_part = parts[-1].strip()
            if len(journal_part) > 5 and len(journal_part) < 100:
                return journal_part
        
        return None
    
    def _deduplicate_literature(self, literature_list: List[Dict]) -> List[Dict]:
        """文献去重"""
        seen_titles = set()
        seen_dois = set()
        unique_literature = []
        
        for lit in literature_list:
            title = lit.get("title", "").lower().strip()
            doi = lit.get("doi", "")
            
            # 基于DOI去重（优先）
            if doi and doi in seen_dois:
                continue
            
            # 基于标题去重
            if title in seen_titles:
                continue
            
            if doi:
                seen_dois.add(doi)
            seen_titles.add(title)
            unique_literature.append(lit)
        
        return unique_literature
    
    def _sort_literature_by_relevance(self, literature_list: List[Dict], keywords: List[str]) -> List[Dict]:
        """按相关性排序文献"""
        keyword_text = " ".join(keywords).lower()
        
        def calculate_relevance(lit: Dict) -> float:
            relevance = 0.0
            
            title = lit.get("title", "").lower()
            abstract = lit.get("abstract", "").lower()
            
            # 标题关键词匹配 (权重: 40%)
            for keyword in keywords:
                if keyword.lower() in title:
                    relevance += 40
            
            # 摘要关键词匹配 (权重: 30%)
            for keyword in keywords:
                if keyword.lower() in abstract:
                    relevance += 30
            
            # 质量评分 (权重: 30%)
            quality_score = lit.get("quality_score", 0)
            relevance += quality_score * 0.3
            
            return relevance
        
        # 按相关性排序
        literature_list.sort(key=calculate_relevance, reverse=True)
        return literature_list
    
    def _parse_pubmed_xml(self, xml_content: str) -> List[Dict]:
        """解析PubMed XML响应"""
        papers = []
        try:
            root = ET.fromstring(xml_content)
            
            for article in root.findall('.//PubmedArticle'):
                try:
                    # 提取基本信息
                    medline_citation = article.find('.//MedlineCitation')
                    pmid = medline_citation.find('.//PMID').text if medline_citation.find('.//PMID') is not None else None
                    
                    # 标题
                    title_elem = article.find('.//ArticleTitle')
                    title = title_elem.text if title_elem is not None else ""
                    
                    # 摘要
                    abstract_elem = article.find('.//Abstract/AbstractText')
                    abstract = abstract_elem.text if abstract_elem is not None else ""
                    
                    # 作者
                    authors = []
                    for author in article.findall('.//Author'):
                        last_name = author.find('.//LastName')
                        first_name = author.find('.//ForeName')
                        if last_name is not None:
                            name = last_name.text
                            if first_name is not None:
                                name = f"{first_name.text} {name}"
                            authors.append({"name": name})
                    
                    # 期刊信息
                    journal_elem = article.find('.//Journal/Title')
                    journal = journal_elem.text if journal_elem is not None else ""
                    
                    # 发表年份
                    year_elem = article.find('.//PubDate/Year')
                    year = int(year_elem.text) if year_elem is not None else None
                    
                    # DOI
                    doi_elem = article.find('.//ArticleId[@IdType="doi"]')
                    doi = doi_elem.text if doi_elem is not None else None
                    
                    paper_data = {
                        "title": title,
                        "abstract": abstract,
                        "authors": authors,
                        "journal": journal,
                        "year": year,
                        "doi": doi,
                        "pmid": pmid,
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
                        "source": "pubmed",
                        "citation_count": 0  # PubMed不直接提供引用数
                    }
                    
                    if title:  # 只有标题不为空才添加
                        papers.append(paper_data)
                        
                except Exception as e:
                    logger.warning(f"解析PubMed文献失败: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"解析PubMed XML失败: {e}")
        
        return papers
    
    def _parse_arxiv_xml(self, xml_content: str) -> List[Dict]:
        """解析arXiv XML响应"""
        papers = []
        try:
            # 处理命名空间
            root = ET.fromstring(xml_content)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            
            for entry in root.findall('.//atom:entry', ns):
                try:
                    # 标题
                    title_elem = entry.find('atom:title', ns)
                    title = title_elem.text.strip() if title_elem is not None else ""
                    
                    # 摘要
                    summary_elem = entry.find('atom:summary', ns)
                    abstract = summary_elem.text.strip() if summary_elem is not None else ""
                    
                    # 作者
                    authors = []
                    for author in entry.findall('atom:author', ns):
                        name_elem = author.find('atom:name', ns)
                        if name_elem is not None:
                            authors.append({"name": name_elem.text})
                    
                    # arXiv ID和URL
                    id_elem = entry.find('atom:id', ns)
                    arxiv_url = id_elem.text if id_elem is not None else ""
                    arxiv_id = arxiv_url.split('/')[-1] if arxiv_url else ""
                    
                    # 发表日期
                    published_elem = entry.find('atom:published', ns)
                    year = None
                    if published_elem is not None:
                        try:
                            date_str = published_elem.text[:4]  # 取前4位作为年份
                            year = int(date_str)
                        except:
                            pass
                    
                    # 分类
                    categories = []
                    for category in entry.findall('atom:category', ns):
                        term = category.get('term', '')
                        if term:
                            categories.append(term)
                    
                    paper_data = {
                        "title": title,
                        "abstract": abstract,
                        "authors": authors,
                        "journal": f"arXiv:{arxiv_id}",
                        "year": year,
                        "doi": None,
                        "arxiv_id": arxiv_id,
                        "url": arxiv_url,
                        "source": "arxiv",
                        "categories": categories,
                        "citation_count": 0  # arXiv不提供引用数
                    }
                    
                    if title:
                        papers.append(paper_data)
                        
                except Exception as e:
                    logger.warning(f"解析arXiv文献失败: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"解析arXiv XML失败: {e}")
        
        return papers
    
    def _parse_crossref_work(self, work: Dict) -> Optional[Dict]:
        """解析Crossref工作记录"""
        try:
            # 标题
            title_list = work.get('title', [])
            title = title_list[0] if title_list else ""
            
            # 摘要 (Crossref通常不提供摘要)
            abstract = work.get('abstract', '')
            
            # 作者
            authors = []
            for author in work.get('author', []):
                given = author.get('given', '')
                family = author.get('family', '')
                name = f"{given} {family}".strip()
                if name:
                    authors.append({"name": name})
            
            # 期刊信息
            container_title = work.get('container-title', [])
            journal = container_title[0] if container_title else ""
            
            # 发表年份
            published = work.get('published-print') or work.get('published-online')
            year = None
            if published and 'date-parts' in published:
                date_parts = published['date-parts'][0]
                if date_parts:
                    year = date_parts[0]
            
            # DOI
            doi = work.get('DOI', '')
            
            # URL
            url = work.get('URL', '')
            if not url and doi:
                url = f"https://doi.org/{doi}"
            
            # 引用数 (如果有)
            citation_count = work.get('is-referenced-by-count', 0)
            
            paper_data = {
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "journal": journal,
                "year": year,
                "doi": doi,
                "url": url,
                "source": "crossref",
                "citation_count": citation_count
            }
            
            return paper_data if title else None
            
        except Exception as e:
            logger.warning(f"解析Crossref工作记录失败: {e}")
            return None
    
    async def _get_rr_client(self) -> ResearchRabbitClient:
        """获取ResearchRabbit客户端（懒加载）"""
        if self._rr_client is None:
            config = ResearchRabbitConfig()
            self._rr_client = ResearchRabbitClient(config)
            await self._rr_client.__aenter__()
        return self._rr_client
    
    async def _collect_from_researchrabbit(self, keywords: List[str], max_count: int) -> List[Dict]:
        """从ResearchRabbit采集文献"""
        try:
            logger.info(f"开始从ResearchRabbit采集文献，关键词: {keywords}, 数量: {max_count}")
            
            # 获取客户端
            rr_client = await self._get_rr_client()
            
            # 搜索文献
            query = " ".join(keywords)
            papers = await rr_client.search_all_papers(query, max_count)
            
            literature_list = []
            for paper in papers:
                try:
                    # 转换为统一格式
                    literature_data = await self._convert_rr_paper_to_literature(paper, rr_client)
                    if literature_data:
                        literature_list.append(literature_data)
                except Exception as e:
                    logger.warning(f"处理ResearchRabbit文献失败: {e}")
                    continue
            
            logger.info(f"从ResearchRabbit采集到 {len(literature_list)} 篇文献")
            return literature_list
            
        except Exception as e:
            logger.error(f"ResearchRabbit采集失败: {e}")
            return []
    
    async def _convert_rr_paper_to_literature(
        self, 
        paper: Dict, 
        rr_client: ResearchRabbitClient
    ) -> Optional[Dict]:
        """将ResearchRabbit论文数据转换为统一的文献格式"""
        try:
            # 基本信息
            title = paper.get("title", "").strip()
            if not title:
                return None
            
            # 作者信息
            authors = []
            for author in paper.get("authors", []):
                name = author.get("name", "").strip()
                if name:
                    authors.append({"name": name})
            
            # DOI
            doi = paper.get("externalIds", {}).get("DOI")
            
            # 摘要
            abstract = paper.get("abstract", "")
            
            # 期刊
            journal = paper.get("venue", "")
            
            # 年份
            year = paper.get("year")
            
            # 引用数
            citation_count = paper.get("citationCount", 0)
            
            # 参考文献数
            reference_count = paper.get("referenceCount", 0)
            
            # 开放获取状态
            is_open_access = paper.get("isOpenAccess", False)
            
            # 研究领域
            fields_of_study = paper.get("fieldsOfStudy") or []
            
            # URL
            url = paper.get("url", "")
            
            # 尝试获取PDF信息
            pdf_url = None
            if doi and is_open_access:
                try:
                    pdf_info = await rr_client.get_pdf_info(doi)
                    if pdf_info and pdf_info.get("url_for_pdf"):
                        pdf_url = pdf_info["url_for_pdf"]
                except Exception as e:
                    logger.debug(f"获取PDF信息失败: {e}")
            
            # 计算质量评分
            quality_score = self._calculate_rr_quality_score(paper)
            
            literature_data = {
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "journal": journal,
                "year": year,
                "doi": doi,
                "url": url,
                "pdf_url": pdf_url,
                "source": "researchrabbit",
                "citation_count": citation_count,
                "reference_count": reference_count,
                "is_open_access": is_open_access,
                "fields_of_study": fields_of_study,
                "quality_score": quality_score,
                "raw_data": paper
            }
            
            return literature_data
            
        except Exception as e:
            logger.warning(f"转换ResearchRabbit文献失败: {e}")
            return None
    
    def _calculate_rr_quality_score(self, paper: Dict) -> float:
        """计算ResearchRabbit文献的质量评分"""
        score = 5.0  # 基础分
        
        # 引用数加分
        citations = paper.get("citationCount", 0)
        if citations > 100:
            score += 2.0
        elif citations > 50:
            score += 1.5
        elif citations > 10:
            score += 1.0
        elif citations > 0:
            score += 0.5
        
        # 发表年份加分（越新越好）
        year = paper.get("year")
        if year:
            current_year = datetime.now().year
            if year >= current_year - 2:
                score += 1.0
            elif year >= current_year - 5:
                score += 0.5
        
        # 开放获取加分
        if paper.get("isOpenAccess"):
            score += 0.5
        
        # 有摘要加分
        if paper.get("abstract"):
            score += 0.5
        
        # 参考文献数加分
        ref_count = paper.get("referenceCount", 0)
        if ref_count > 50:
            score += 0.5
        elif ref_count > 20:
            score += 0.3
        
        return min(10.0, score)
    
    async def close(self):
        """关闭资源"""
        if self._rr_client:
            await self._rr_client.__aexit__(None, None, None)
            self._rr_client = None