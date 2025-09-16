"""
数据导入导出服务
"""

import asyncio
import json
import csv
import io
import zipfile
from typing import List, Dict, Optional, Any
from datetime import datetime
import pandas as pd
from pathlib import Path
from loguru import logger

from app.core.config import settings
from app.models.literature import Literature, LiteratureSegment
from app.models.project import Project
from app.models.experience import ExperienceBook, MainExperience

class DataExportService:
    """数据导出服务"""
    
    def __init__(self):
        self.export_formats = ['json', 'csv', 'excel', 'pdf', 'markdown', 'bibtex', 'ris']
    
    async def export_project_data(
        self,
        project_id: int,
        export_format: str = 'json',
        include_options: Dict[str, bool] = None
    ) -> Dict[str, Any]:
        """
        导出项目完整数据
        
        Args:
            project_id: 项目ID
            export_format: 导出格式
            include_options: 包含选项
            
        Returns:
            导出结果
        """
        try:
            if include_options is None:
                include_options = {
                    'literature': True,
                    'segments': True,
                    'experience_books': True,
                    'main_experience': True,
                    'comments': False,
                    'activity_logs': False
                }
            
            # 收集项目数据
            project_data = await self._collect_project_data(project_id, include_options)
            
            # 根据格式导出
            if export_format == 'json':
                return await self._export_to_json(project_data)
            elif export_format == 'csv':
                return await self._export_to_csv(project_data)
            elif export_format == 'excel':
                return await self._export_to_excel(project_data)
            elif export_format == 'pdf':
                return await self._export_to_pdf(project_data)
            elif export_format == 'markdown':
                return await self._export_to_markdown(project_data)
            elif export_format == 'bibtex':
                return await self._export_to_bibtex(project_data)
            elif export_format == 'ris':
                return await self._export_to_ris(project_data)
            else:
                raise ValueError(f"不支持的导出格式: {export_format}")
                
        except Exception as e:
            logger.error(f"项目数据导出失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _collect_project_data(self, project_id: int, include_options: Dict[str, bool]) -> Dict:
        """收集项目数据"""
        # 这里应该从数据库查询真实数据
        # 为了测试，使用模拟数据
        
        project_data = {
            "project": {
                "id": project_id,
                "name": f"测试项目 {project_id}",
                "description": "这是一个测试项目的描述",
                "research_direction": "氮化硼纳米材料研究",
                "keywords": ["氮化硼", "纳米材料", "制备工艺"],
                "created_at": datetime.now().isoformat()
            }
        }
        
        if include_options.get('literature', False):
            project_data["literature"] = [
                {
                    "id": 1,
                    "title": "Advanced Synthesis of Boron Nitride Nanosheets",
                    "authors": ["John Smith", "Jane Doe"],
                    "abstract": "This study presents novel synthesis methods...",
                    "journal": "Nature Materials",
                    "publication_year": 2023,
                    "citation_count": 156,
                    "doi": "10.1038/s41563-023-1234-5"
                },
                {
                    "id": 2,
                    "title": "Thermal Properties of BN Nanocomposites",
                    "authors": ["Wei Zhang", "Ming Li"],
                    "abstract": "Investigation of thermal conductivity...",
                    "journal": "Advanced Materials", 
                    "publication_year": 2023,
                    "citation_count": 89,
                    "doi": "10.1002/adma.202301234"
                }
            ]
        
        if include_options.get('experience_books', False):
            project_data["experience_books"] = [
                {
                    "id": 1,
                    "title": "氮化硼制备经验书 - 第5轮",
                    "research_question": "如何优化球磨法制备氮化硼纳米片？",
                    "iteration_round": 5,
                    "content": "基于多篇文献的分析，球磨法制备氮化硼纳米片的最佳工艺参数为...",
                    "information_gain": 0.08,
                    "is_final": True
                }
            ]
        
        if include_options.get('main_experience', False):
            project_data["main_experience"] = {
                "id": 1,
                "title": "氮化硼纳米材料主经验库",
                "research_domain": "纳米材料",
                "content": "氮化硼纳米材料的制备、表征和应用综合经验...",
                "coverage_scope": ["球磨法", "超声法", "CVD法"],
                "source_literature_count": 150
            }
        
        return project_data
    
    async def _export_to_json(self, data: Dict) -> Dict[str, Any]:
        """导出为JSON格式"""
        try:
            json_content = json.dumps(data, ensure_ascii=False, indent=2)
            
            return {
                "success": True,
                "format": "json",
                "content": json_content,
                "filename": f"project_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                "size": len(json_content.encode('utf-8'))
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _export_to_csv(self, data: Dict) -> Dict[str, Any]:
        """导出为CSV格式"""
        try:
            csv_files = {}
            
            # 导出文献数据
            if 'literature' in data:
                literature_csv = io.StringIO()
                writer = csv.writer(literature_csv)
                
                # 写入头部
                headers = ['ID', 'Title', 'Authors', 'Journal', 'Year', 'Citations', 'DOI', 'Abstract']
                writer.writerow(headers)
                
                # 写入数据
                for lit in data['literature']:
                    row = [
                        lit.get('id', ''),
                        lit.get('title', ''),
                        '; '.join(lit.get('authors', [])),
                        lit.get('journal', ''),
                        lit.get('publication_year', ''),
                        lit.get('citation_count', 0),
                        lit.get('doi', ''),
                        lit.get('abstract', '')[:500] + '...' if len(lit.get('abstract', '')) > 500 else lit.get('abstract', '')
                    ]
                    writer.writerow(row)
                
                csv_files['literature.csv'] = literature_csv.getvalue()
            
            # 创建ZIP文件包含所有CSV
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for filename, content in csv_files.items():
                    zip_file.writestr(filename, content)
                
                # 添加项目信息
                project_info = json.dumps(data.get('project', {}), ensure_ascii=False, indent=2)
                zip_file.writestr('project_info.json', project_info)
            
            return {
                "success": True,
                "format": "csv",
                "content": zip_buffer.getvalue(),
                "filename": f"project_csv_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                "size": len(zip_buffer.getvalue())
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _export_to_markdown(self, data: Dict) -> Dict[str, Any]:
        """导出为Markdown格式"""
        try:
            md_content = []
            
            # 项目信息
            project = data.get('project', {})
            md_content.append(f"# {project.get('name', '项目导出')}")
            md_content.append(f"\n**项目描述**: {project.get('description', '')}")
            md_content.append(f"**研究方向**: {project.get('research_direction', '')}")
            md_content.append(f"**关键词**: {', '.join(project.get('keywords', []))}")
            md_content.append(f"**导出时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}")
            md_content.append("\n---\n")
            
            # 文献列表
            if 'literature' in data:
                md_content.append("## 📚 文献库\n")
                
                for i, lit in enumerate(data['literature'], 1):
                    md_content.append(f"### {i}. {lit.get('title', '')}")
                    md_content.append(f"**作者**: {', '.join(lit.get('authors', []))}")
                    md_content.append(f"**期刊**: {lit.get('journal', '')}")
                    md_content.append(f"**年份**: {lit.get('publication_year', '')}")
                    md_content.append(f"**引用数**: {lit.get('citation_count', 0)}")
                    
                    if lit.get('doi'):
                        md_content.append(f"**DOI**: {lit['doi']}")
                    
                    if lit.get('abstract'):
                        md_content.append(f"\n**摘要**: {lit['abstract']}")
                    
                    md_content.append("\n---\n")
            
            # 主经验
            if 'main_experience' in data:
                main_exp = data['main_experience']
                md_content.append("## 🧠 主经验库\n")
                md_content.append(f"**标题**: {main_exp.get('title', '')}")
                md_content.append(f"**研究领域**: {main_exp.get('research_domain', '')}")
                md_content.append(f"**覆盖范围**: {', '.join(main_exp.get('coverage_scope', []))}")
                md_content.append(f"**基于文献数**: {main_exp.get('source_literature_count', 0)}")
                md_content.append(f"\n{main_exp.get('content', '')}")
                md_content.append("\n---\n")
            
            # 经验书
            if 'experience_books' in data:
                md_content.append("## 📖 经验书\n")
                
                for book in data['experience_books']:
                    md_content.append(f"### {book.get('title', '')}")
                    md_content.append(f"**研究问题**: {book.get('research_question', '')}")
                    md_content.append(f"**迭代轮次**: 第{book.get('iteration_round', 0)}轮")
                    md_content.append(f"**信息增益**: {book.get('information_gain', 0):.2%}")
                    md_content.append(f"\n{book.get('content', '')}")
                    md_content.append("\n---\n")
            
            markdown_text = '\n'.join(md_content)
            
            return {
                "success": True,
                "format": "markdown",
                "content": markdown_text,
                "filename": f"project_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                "size": len(markdown_text.encode('utf-8'))
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _export_to_bibtex(self, data: Dict) -> Dict[str, Any]:
        """导出为BibTeX格式"""
        try:
            bibtex_entries = []
            
            if 'literature' in data:
                for lit in data['literature']:
                    # 生成引用键
                    first_author = lit.get('authors', ['Unknown'])[0].split()[-1] if lit.get('authors') else 'Unknown'
                    year = lit.get('publication_year', datetime.now().year)
                    cite_key = f"{first_author.lower()}{year}"
                    
                    # 构建BibTeX条目
                    entry = f"@article{{{cite_key},\n"
                    entry += f"  title={{{lit.get('title', '')}}},\n"
                    
                    if lit.get('authors'):
                        authors = ' and '.join(lit['authors'])
                        entry += f"  author={{{authors}}},\n"
                    
                    if lit.get('journal'):
                        entry += f"  journal={{{lit['journal']}}},\n"
                    
                    if lit.get('publication_year'):
                        entry += f"  year={{{lit['publication_year']}}},\n"
                    
                    if lit.get('doi'):
                        entry += f"  doi={{{lit['doi']}}},\n"
                    
                    if lit.get('abstract'):
                        entry += f"  abstract={{{lit['abstract']}}},\n"
                    
                    entry = entry.rstrip(',\n') + '\n}'
                    bibtex_entries.append(entry)
            
            bibtex_content = '\n\n'.join(bibtex_entries)
            
            return {
                "success": True,
                "format": "bibtex",
                "content": bibtex_content,
                "filename": f"literature_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bib",
                "size": len(bibtex_content.encode('utf-8'))
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def export_literature_list(
        self,
        literature_ids: List[int],
        export_format: str = 'json'
    ) -> Dict[str, Any]:
        """导出文献列表"""
        try:
            # 模拟从数据库获取文献数据
            literature_data = []
            for lit_id in literature_ids:
                literature_data.append({
                    "id": lit_id,
                    "title": f"Literature {lit_id}",
                    "authors": [f"Author {lit_id}A", f"Author {lit_id}B"],
                    "journal": f"Journal {lit_id % 3 + 1}",
                    "publication_year": 2020 + (lit_id % 4),
                    "citation_count": lit_id * 10,
                    "quality_score": 50 + (lit_id % 5) * 10
                })
            
            if export_format == 'json':
                content = json.dumps(literature_data, ensure_ascii=False, indent=2)
            elif export_format == 'csv':
                output = io.StringIO()
                writer = csv.writer(output)
                
                # 写入头部
                writer.writerow(['ID', 'Title', 'Authors', 'Journal', 'Year', 'Citations', 'Quality Score'])
                
                # 写入数据
                for lit in literature_data:
                    writer.writerow([
                        lit['id'],
                        lit['title'],
                        '; '.join(lit['authors']),
                        lit['journal'],
                        lit['publication_year'],
                        lit['citation_count'],
                        lit['quality_score']
                    ])
                
                content = output.getvalue()
            else:
                raise ValueError(f"不支持的格式: {export_format}")
            
            return {
                "success": True,
                "format": export_format,
                "content": content,
                "filename": f"literature_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{export_format}",
                "count": len(literature_data)
            }
            
        except Exception as e:
            logger.error(f"文献列表导出失败: {e}")
            return {"success": False, "error": str(e)}

class DataImportService:
    """数据导入服务"""
    
    def __init__(self):
        self.supported_formats = ['json', 'csv', 'excel', 'ris', 'bibtex']
    
    async def import_literature_data(
        self,
        file_content: str,
        file_format: str,
        project_id: int,
        import_options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        导入文献数据
        
        Args:
            file_content: 文件内容
            file_format: 文件格式
            project_id: 目标项目ID
            import_options: 导入选项
            
        Returns:
            导入结果
        """
        try:
            if import_options is None:
                import_options = {
                    'skip_duplicates': True,
                    'auto_process': True,
                    'quality_threshold': 30
                }
            
            # 根据格式解析数据
            if file_format == 'json':
                parsed_data = await self._parse_json_import(file_content)
            elif file_format == 'csv':
                parsed_data = await self._parse_csv_import(file_content)
            elif file_format == 'ris':
                parsed_data = await self._parse_ris_import(file_content)
            elif file_format == 'bibtex':
                parsed_data = await self._parse_bibtex_import(file_content)
            else:
                raise ValueError(f"不支持的导入格式: {file_format}")
            
            # 数据验证和清理
            validated_data = await self._validate_import_data(parsed_data, import_options)
            
            # 保存到数据库（模拟）
            import_result = await self._save_imported_data(validated_data, project_id)
            
            return {
                "success": True,
                "imported_count": import_result["saved_count"],
                "skipped_count": import_result["skipped_count"],
                "error_count": import_result["error_count"],
                "total_processed": len(parsed_data),
                "details": import_result["details"]
            }
            
        except Exception as e:
            logger.error(f"数据导入失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "imported_count": 0
            }
    
    async def _parse_json_import(self, content: str) -> List[Dict]:
        """解析JSON导入数据"""
        try:
            data = json.loads(content)
            
            # 支持多种JSON结构
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # 检查是否有文献列表
                if 'literature' in data:
                    return data['literature']
                elif 'items' in data:
                    return data['items']
                else:
                    return [data]  # 单个文献对象
            else:
                raise ValueError("无效的JSON格式")
                
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON解析失败: {e}")
    
    async def _parse_csv_import(self, content: str) -> List[Dict]:
        """解析CSV导入数据"""
        try:
            # 使用pandas解析CSV
            df = pd.read_csv(io.StringIO(content))
            
            # 标准化列名
            column_mapping = {
                'title': ['title', 'Title', '标题'],
                'authors': ['authors', 'Authors', 'Author', '作者'],
                'journal': ['journal', 'Journal', 'Publication', '期刊'],
                'year': ['year', 'Year', 'Publication Year', '年份'],
                'doi': ['doi', 'DOI'],
                'abstract': ['abstract', 'Abstract', '摘要']
            }
            
            # 重命名列
            for standard_name, possible_names in column_mapping.items():
                for col in df.columns:
                    if col in possible_names:
                        df = df.rename(columns={col: standard_name})
                        break
            
            # 转换为字典列表
            literature_list = []
            for _, row in df.iterrows():
                lit_data = {}
                
                for col in df.columns:
                    value = row[col]
                    if pd.notna(value):
                        if col == 'authors' and isinstance(value, str):
                            # 分割作者字符串
                            lit_data[col] = [author.strip() for author in value.split(';')]
                        else:
                            lit_data[col] = value
                
                if lit_data.get('title'):  # 必须有标题
                    literature_list.append(lit_data)
            
            return literature_list
            
        except Exception as e:
            raise ValueError(f"CSV解析失败: {e}")
    
    async def _validate_import_data(self, data: List[Dict], options: Dict) -> List[Dict]:
        """验证和清理导入数据"""
        validated_data = []
        
        for item in data:
            # 基础验证
            if not item.get('title'):
                continue
            
            # 质量检查
            quality_score = self._calculate_import_quality_score(item)
            if quality_score < options.get('quality_threshold', 30):
                continue
            
            # 标准化数据
            standardized_item = {
                'title': item.get('title', '').strip(),
                'authors': item.get('authors', []) if isinstance(item.get('authors'), list) else [item.get('authors', '')],
                'abstract': item.get('abstract', '').strip(),
                'journal': item.get('journal', '').strip(),
                'publication_year': self._parse_year(item.get('year') or item.get('publication_year')),
                'doi': item.get('doi', '').strip(),
                'source_url': item.get('url', '').strip(),
                'keywords': item.get('keywords', []) if isinstance(item.get('keywords'), list) else [],
                'quality_score': quality_score,
                'source_platform': 'import'
            }
            
            validated_data.append(standardized_item)
        
        return validated_data
    
    def _calculate_import_quality_score(self, item: Dict) -> float:
        """计算导入文献的质量评分"""
        score = 0.0
        
        # 标题 (20分)
        if item.get('title'):
            score += 20
        
        # 作者 (20分)
        authors = item.get('authors', [])
        if authors:
            score += min(20, len(authors) * 5)
        
        # 摘要 (20分)
        abstract = item.get('abstract', '')
        if abstract:
            if len(abstract) > 500:
                score += 20
            elif len(abstract) > 200:
                score += 15
            else:
                score += 10
        
        # 期刊 (15分)
        if item.get('journal'):
            score += 15
        
        # DOI (15分)
        if item.get('doi'):
            score += 15
        
        # 年份 (10分)
        if item.get('year') or item.get('publication_year'):
            score += 10
        
        return min(score, 100.0)
    
    def _parse_year(self, year_value: Any) -> Optional[int]:
        """解析年份值"""
        if not year_value:
            return None
        
        try:
            # 如果是字符串，提取数字
            if isinstance(year_value, str):
                import re
                year_match = re.search(r'\b(19|20)\d{2}\b', year_value)
                if year_match:
                    return int(year_match.group())
            else:
                return int(year_value)
        except:
            pass
        
        return None
    
    async def _save_imported_data(self, data: List[Dict], project_id: int) -> Dict:
        """保存导入的数据到数据库"""
        # 模拟保存过程
        saved_count = 0
        skipped_count = 0
        error_count = 0
        details = []
        
        for item in data:
            try:
                # 模拟重复检查
                is_duplicate = False  # 简化实现
                
                if is_duplicate:
                    skipped_count += 1
                    details.append(f"跳过重复文献: {item['title'][:50]}...")
                else:
                    # 模拟保存
                    saved_count += 1
                    details.append(f"导入成功: {item['title'][:50]}...")
                    
            except Exception as e:
                error_count += 1
                details.append(f"导入失败: {str(e)}")
        
        return {
            "saved_count": saved_count,
            "skipped_count": skipped_count,
            "error_count": error_count,
            "details": details[:10]  # 只返回前10条详情
        }