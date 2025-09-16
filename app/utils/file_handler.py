"""
文件处理工具
"""

import os
import shutil
import hashlib
from pathlib import Path
from typing import Optional
from fastapi import UploadFile, HTTPException
import aiofiles

from app.core.config import settings

class FileHandler:
    """文件处理工具类"""
    
    def __init__(self):
        self.upload_dir = Path(settings.upload_path)
        self.upload_dir.mkdir(exist_ok=True)
    
    async def save_uploaded_file(self, file: UploadFile, project_id: int) -> str:
        """
        保存上传的文件
        
        Args:
            file: 上传的文件
            project_id: 项目ID
            
        Returns:
            保存的文件路径
        """
        # 验证文件类型
        if not self._is_allowed_file_type(file.filename):
            raise HTTPException(
                status_code=400, 
                detail=f"不支持的文件类型。支持的类型: {settings.allowed_file_types}"
            )
        
        # 验证文件大小
        if file.size > settings.max_file_size:
            raise HTTPException(
                status_code=400,
                detail=f"文件过大。最大支持: {settings.max_file_size / (1024*1024):.1f}MB"
            )
        
        # 创建项目目录
        project_dir = self.upload_dir / f"project_{project_id}"
        project_dir.mkdir(exist_ok=True)
        
        # 生成安全的文件名
        safe_filename = self._generate_safe_filename(file.filename)
        file_path = project_dir / safe_filename
        
        # 保存文件
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        return str(file_path)
    
    def _is_allowed_file_type(self, filename: str) -> bool:
        """检查文件类型是否允许"""
        if not filename:
            return False
        
        file_ext = Path(filename).suffix.lower()
        return file_ext in settings.allowed_file_types
    
    def _generate_safe_filename(self, filename: str) -> str:
        """生成安全的文件名"""
        # 移除危险字符
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        
        name = Path(filename).stem
        ext = Path(filename).suffix
        
        safe_name = "".join(c for c in name if c in safe_chars)
        if not safe_name:
            safe_name = "uploaded_file"
        
        # 添加时间戳避免重名
        import time
        timestamp = str(int(time.time()))
        
        return f"{safe_name}_{timestamp}{ext}"
    
    def calculate_file_hash(self, file_path: str) -> str:
        """计算文件哈希值"""
        hash_md5 = hashlib.md5()
        
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        
        return hash_md5.hexdigest()
    
    def delete_file(self, file_path: str) -> bool:
        """删除文件"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception:
            return False
    
    def get_file_info(self, file_path: str) -> Optional[dict]:
        """获取文件信息"""
        try:
            if not os.path.exists(file_path):
                return None
            
            stat = os.stat(file_path)
            
            return {
                "size": stat.st_size,
                "created_at": stat.st_ctime,
                "modified_at": stat.st_mtime,
                "extension": Path(file_path).suffix,
                "hash": self.calculate_file_hash(file_path)
            }
        except Exception:
            return None