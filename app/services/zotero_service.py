"""
Zotero集成服务
"""

import asyncio
import aiohttp
from typing import List, Dict, Optional
import json
from urllib.parse import quote
from loguru import logger

from app.core.config import settings
from app.models.literature import Literature

class ZoteroService:
    """Zotero集成服务"""
    
    def __init__(self):
        self.base_url = "https://api.zotero.org"
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_user_library(
        self, 
        user_id: str, 
        api_key: str,
        collection_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        获取用户的Zotero文献库
        
        Args:
            user_id: Zotero用户ID
            api_key: Zotero API密钥
            collection_id: 集合ID（可选）
            limit: 获取数量限制
            
        Returns:
            文献列表
        """
        try:
            headers = {
                "Zotero-API-Key": api_key,
                "Content-Type": "application/json"
            }
            
            # 构建API URL
            if collection_id:
                url = f"{self.base_url}/users/{user_id}/collections/{collection_id}/items"
            else:
                url = f"{self.base_url}/users/{user_id}/items"
            
            params = {
                "format": "json",
                "include": "data,meta",
                "limit": limit,
                "sort": "dateModified",
                "direction": "desc"
            }
            
            async with self.session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    items = await response.json()
                    logger.info(f"成功获取Zotero文献: {len(items)}篇")
                    
                    # 转换为标准格式
                    literature_list = []
                    for item in items:
                        literature_data = self._convert_zotero_item(item)
                        if literature_data:
                            literature_list.append(literature_data)
                    
                    return literature_list
                    
                elif response.status == 403:
                    logger.error("Zotero API密钥无效或无权限")
                    raise Exception("Zotero API密钥无效或无权限")
                else:
                    logger.error(f"Zotero API请求失败: {response.status}")
                    raise Exception(f"Zotero API请求失败: {response.status}")
                    
        except Exception as e:
            logger.error(f"获取Zotero文献库失败: {e}")
            raise
    
    async def get_user_collections(self, user_id: str, api_key: str) -> List[Dict]:
        """获取用户的Zotero集合列表"""
        try:
            headers = {
                "Zotero-API-Key": api_key,
                "Content-Type": "application/json"
            }
            
            url = f"{self.base_url}/users/{user_id}/collections"
            params = {
                "format": "json",
                "include": "data"
            }
            
            async with self.session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    collections = await response.json()
                    
                    collection_list = []
                    for collection in collections:
                        data = collection.get("data", {})
                        collection_list.append({
                            "id": collection.get("key"),
                            "name": data.get("name", ""),
                            "parent_collection": data.get("parentCollection"),
                            "item_count": collection.get("meta", {}).get("numItems", 0)
                        })
                    
                    return collection_list
                else:
                    logger.error(f"获取Zotero集合失败: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"获取Zotero集合失败: {e}")
            return []
    
    async def sync_to_zotero(
        self,
        user_id: str,
        api_key: str,
        literature_data: List[Dict],
        collection_id: Optional[str] = None
    ) -> Dict:
        """
        同步文献到Zotero
        
        Args:
            user_id: Zotero用户ID
            api_key: API密钥
            literature_data: 要同步的文献数据
            collection_id: 目标集合ID
            
        Returns:
            同步结果
        """
        try:
            headers = {
                "Zotero-API-Key": api_key,
                "Content-Type": "application/json"
            }
            
            # 转换为Zotero格式
            zotero_items = []
            for lit in literature_data:
                zotero_item = self._convert_to_zotero_format(lit)
                if zotero_item:
                    zotero_items.append(zotero_item)
            
            if not zotero_items:
                return {"success": False, "message": "没有可同步的文献"}
            
            # 批量上传到Zotero
            url = f"{self.base_url}/users/{user_id}/items"
            
            # Zotero API限制每次最多50个项目
            batch_size = 50
            uploaded_count = 0
            failed_count = 0
            
            for i in range(0, len(zotero_items), batch_size):
                batch = zotero_items[i:i + batch_size]
                
                async with self.session.post(url, headers=headers, json=batch) as response:
                    if response.status in [200, 201]:
                        result = await response.json()
                        uploaded_count += len(result.get("successful", {}))
                        failed_count += len(result.get("failed", {}))
                    else:
                        logger.error(f"Zotero同步批次失败: {response.status}")
                        failed_count += len(batch)
                
                # 避免API限制
                await asyncio.sleep(1)
            
            return {
                "success": True,
                "uploaded_count": uploaded_count,
                "failed_count": failed_count,
                "total_count": len(zotero_items)
            }
            
        except Exception as e:
            logger.error(f"同步到Zotero失败: {e}")
            return {
                "success": False,
                "message": str(e),
                "uploaded_count": 0,
                "failed_count": len(literature_data)
            }
    
    def _convert_zotero_item(self, zotero_item: Dict) -> Optional[Dict]:
        """将Zotero项目转换为标准文献格式"""
        try:
            data = zotero_item.get("data", {})
            
            # 提取基础信息
            title = data.get("title", "")
            if not title:
                return None
            
            # 提取作者信息
            authors = []
            creators = data.get("creators", [])
            for creator in creators:
                if creator.get("creatorType") in ["author", "editor"]:
                    first_name = creator.get("firstName", "")
                    last_name = creator.get("lastName", "")
                    name = f"{first_name} {last_name}".strip()
                    if name:
                        authors.append(name)
            
            # 提取发表信息
            publication_year = None
            date_str = data.get("date", "")
            if date_str:
                # 尝试提取年份
                import re
                year_match = re.search(r'\b(19|20)\d{2}\b', date_str)
                if year_match:
                    publication_year = int(year_match.group())
            
            # 提取DOI
            doi = data.get("DOI") or data.get("doi")
            
            # 提取URL
            url = data.get("url")
            
            # 提取摘要
            abstract = data.get("abstractNote", "")
            
            # 提取期刊信息
            journal = data.get("publicationTitle") or data.get("journalAbbreviation")
            
            # 提取标签作为关键词
            tags = data.get("tags", [])
            keywords = [tag.get("tag", "") for tag in tags if tag.get("tag")]
            
            return {
                "title": title,
                "authors": authors,
                "abstract": abstract,
                "keywords": keywords,
                "journal": journal,
                "publication_year": publication_year,
                "doi": doi,
                "source_platform": "zotero",
                "source_url": url,
                "zotero_key": zotero_item.get("key"),
                "zotero_version": zotero_item.get("version"),
                "quality_score": self._calculate_zotero_quality_score(data)
            }
            
        except Exception as e:
            logger.error(f"转换Zotero项目失败: {e}")
            return None
    
    def _convert_to_zotero_format(self, literature: Dict) -> Optional[Dict]:
        """将标准文献格式转换为Zotero格式"""
        try:
            # 基础Zotero项目结构
            zotero_item = {
                "itemType": "journalArticle",
                "title": literature.get("title", ""),
                "abstractNote": literature.get("abstract", ""),
                "publicationTitle": literature.get("journal", ""),
                "date": str(literature.get("publication_year", "")),
                "DOI": literature.get("doi", ""),
                "url": literature.get("source_url", ""),
                "creators": [],
                "tags": []
            }
            
            # 转换作者信息
            authors = literature.get("authors", [])
            for author in authors:
                # 简单的姓名分割逻辑
                name_parts = author.strip().split()
                if len(name_parts) >= 2:
                    zotero_item["creators"].append({
                        "creatorType": "author",
                        "firstName": " ".join(name_parts[:-1]),
                        "lastName": name_parts[-1]
                    })
                else:
                    zotero_item["creators"].append({
                        "creatorType": "author",
                        "name": author
                    })
            
            # 转换关键词为标签
            keywords = literature.get("keywords", [])
            for keyword in keywords:
                zotero_item["tags"].append({"tag": keyword})
            
            return zotero_item
            
        except Exception as e:
            logger.error(f"转换为Zotero格式失败: {e}")
            return None
    
    def _calculate_zotero_quality_score(self, zotero_data: Dict) -> float:
        """计算从Zotero导入文献的质量评分"""
        score = 0.0
        
        # 标题完整性 (20分)
        if zotero_data.get("title"):
            score += 20
        
        # 作者信息 (20分)
        creators = zotero_data.get("creators", [])
        if creators:
            score += min(20, len(creators) * 5)
        
        # 摘要完整性 (20分)
        abstract = zotero_data.get("abstractNote", "")
        if abstract:
            if len(abstract) > 500:
                score += 20
            elif len(abstract) > 200:
                score += 15
            else:
                score += 10
        
        # 期刊信息 (15分)
        if zotero_data.get("publicationTitle"):
            score += 15
        
        # DOI信息 (15分)
        if zotero_data.get("DOI"):
            score += 15
        
        # 发表年份 (10分)
        if zotero_data.get("date"):
            score += 10
        
        return min(score, 100.0)
    
    async def validate_api_key(self, user_id: str, api_key: str) -> bool:
        """验证Zotero API密钥有效性"""
        try:
            headers = {
                "Zotero-API-Key": api_key
            }
            
            url = f"{self.base_url}/users/{user_id}/items"
            params = {"limit": 1}
            
            async with self.session.get(url, headers=headers, params=params) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"验证Zotero API密钥失败: {e}")
            return False
    
    async def get_sync_status(
        self, 
        user_id: str, 
        api_key: str,
        last_sync_version: Optional[int] = None
    ) -> Dict:
        """获取同步状态信息"""
        try:
            headers = {
                "Zotero-API-Key": api_key
            }
            
            # 获取库的版本信息
            url = f"{self.base_url}/users/{user_id}/items"
            params = {"format": "versions", "limit": 1}
            
            async with self.session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    # 获取最新版本号
                    last_modified_version = response.headers.get("Last-Modified-Version")
                    
                    # 检查是否有更新
                    has_updates = (
                        last_sync_version is None or 
                        (last_modified_version and int(last_modified_version) > last_sync_version)
                    )
                    
                    return {
                        "success": True,
                        "has_updates": has_updates,
                        "last_modified_version": int(last_modified_version) if last_modified_version else 0,
                        "last_sync_version": last_sync_version or 0
                    }
                else:
                    return {
                        "success": False,
                        "error": f"获取同步状态失败: {response.status}"
                    }
                    
        except Exception as e:
            logger.error(f"获取Zotero同步状态失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

# Mendeley集成服务（基础实现）
class MendeleyService:
    """Mendeley集成服务"""
    
    def __init__(self):
        self.base_url = "https://api.mendeley.com"
    
    async def get_user_library(self, access_token: str, limit: int = 100) -> List[Dict]:
        """获取Mendeley文献库"""
        # 实现Mendeley API集成
        # 由于Mendeley API较复杂，这里提供基础框架
        return []
    
    def _convert_mendeley_item(self, mendeley_item: Dict) -> Optional[Dict]:
        """转换Mendeley项目格式"""
        # 实现Mendeley到标准格式的转换
        return None

# EndNote集成服务（基础实现）
class EndNoteService:
    """EndNote集成服务"""
    
    def __init__(self):
        pass
    
    def parse_enl_file(self, file_path: str) -> List[Dict]:
        """解析EndNote库文件"""
        # 实现EndNote .enl文件解析
        return []
    
    def parse_ris_file(self, file_content: str) -> List[Dict]:
        """解析RIS格式文件"""
        try:
            literature_list = []
            
            # 简单的RIS解析逻辑
            records = file_content.split('\n\nER  -')
            
            for record in records:
                if not record.strip():
                    continue
                
                lines = record.strip().split('\n')
                item_data = {}
                
                for line in lines:
                    if '  - ' in line:
                        tag, value = line.split('  - ', 1)
                        tag = tag.strip()
                        value = value.strip()
                        
                        if tag == 'TI':  # Title
                            item_data['title'] = value
                        elif tag == 'AU':  # Author
                            if 'authors' not in item_data:
                                item_data['authors'] = []
                            item_data['authors'].append(value)
                        elif tag == 'AB':  # Abstract
                            item_data['abstract'] = value
                        elif tag == 'JO' or tag == 'T2':  # Journal
                            item_data['journal'] = value
                        elif tag == 'PY':  # Publication Year
                            try:
                                item_data['publication_year'] = int(value[:4])
                            except:
                                pass
                        elif tag == 'DO':  # DOI
                            item_data['doi'] = value
                        elif tag == 'UR':  # URL
                            item_data['source_url'] = value
                        elif tag == 'KW':  # Keywords
                            if 'keywords' not in item_data:
                                item_data['keywords'] = []
                            item_data['keywords'].append(value)
                
                if item_data.get('title'):
                    item_data['source_platform'] = 'endnote'
                    literature_list.append(item_data)
            
            logger.info(f"解析RIS文件: {len(literature_list)}篇文献")
            return literature_list
            
        except Exception as e:
            logger.error(f"解析RIS文件失败: {e}")
            return []
    
    def parse_bibtex_file(self, file_content: str) -> List[Dict]:
        """解析BibTeX格式文件"""
        try:
            literature_list = []
            
            # 简单的BibTeX解析逻辑
            import re
            
            # 匹配BibTeX条目
            pattern = r'@(\w+)\s*\{\s*([^,]+)\s*,\s*(.*?)\s*\}(?=\s*@|\s*$)'
            matches = re.findall(pattern, file_content, re.DOTALL | re.IGNORECASE)
            
            for entry_type, cite_key, fields_str in matches:
                item_data = {
                    'source_platform': 'bibtex',
                    'cite_key': cite_key.strip()
                }
                
                # 解析字段
                field_pattern = r'(\w+)\s*=\s*\{([^}]+)\}'
                field_matches = re.findall(field_pattern, fields_str)
                
                for field, value in field_matches:
                    field = field.lower().strip()
                    value = value.strip()
                    
                    if field == 'title':
                        item_data['title'] = value
                    elif field == 'author':
                        # 分割多个作者
                        authors = [author.strip() for author in value.split(' and ')]
                        item_data['authors'] = authors
                    elif field == 'abstract':
                        item_data['abstract'] = value
                    elif field == 'journal':
                        item_data['journal'] = value
                    elif field == 'year':
                        try:
                            item_data['publication_year'] = int(value)
                        except:
                            pass
                    elif field == 'doi':
                        item_data['doi'] = value
                    elif field == 'url':
                        item_data['source_url'] = value
                
                if item_data.get('title'):
                    literature_list.append(item_data)
            
            logger.info(f"解析BibTeX文件: {len(literature_list)}篇文献")
            return literature_list
            
        except Exception as e:
            logger.error(f"解析BibTeX文件失败: {e}")
            return []

# 统一的第三方集成管理器
class ThirdPartyIntegrationManager:
    """第三方集成管理器"""
    
    def __init__(self):
        self.zotero_service = ZoteroService()
        self.mendeley_service = MendeleyService()
        self.endnote_service = EndNoteService()
    
    async def import_from_zotero(
        self,
        user_id: str,
        api_key: str,
        collection_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """从Zotero导入文献"""
        async with self.zotero_service as zotero:
            return await zotero.get_user_library(user_id, api_key, collection_id, limit)
    
    async def export_to_zotero(
        self,
        user_id: str,
        api_key: str,
        literature_data: List[Dict],
        collection_id: Optional[str] = None
    ) -> Dict:
        """导出文献到Zotero"""
        async with self.zotero_service as zotero:
            return await zotero.sync_to_zotero(user_id, api_key, literature_data, collection_id)
    
    def import_from_file(self, file_content: str, file_format: str) -> List[Dict]:
        """从文件导入文献"""
        if file_format.lower() == 'ris':
            return self.endnote_service.parse_ris_file(file_content)
        elif file_format.lower() == 'bibtex':
            return self.endnote_service.parse_bibtex_file(file_content)
        else:
            raise ValueError(f"不支持的文件格式: {file_format}")
    
    async def get_supported_platforms(self) -> List[Dict]:
        """获取支持的平台列表"""
        return [
            {
                "platform": "zotero",
                "name": "Zotero",
                "description": "开源文献管理工具",
                "features": ["双向同步", "集合管理", "标签支持"],
                "auth_type": "api_key",
                "status": "active"
            },
            {
                "platform": "mendeley",
                "name": "Mendeley",
                "description": "学术社交网络和文献管理",
                "features": ["文献导入", "社交功能"],
                "auth_type": "oauth",
                "status": "beta"
            },
            {
                "platform": "endnote",
                "name": "EndNote",
                "description": "专业文献管理软件",
                "features": ["文件导入", "多格式支持"],
                "auth_type": "file_upload",
                "status": "active"
            }
        ]