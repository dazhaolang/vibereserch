"""
数据生命周期管理服务
提供数据备份、迁移、清理、归档等功能
"""

import asyncio
import aiofiles
import shutil
import gzip
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from loguru import logger
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_
import boto3
from botocore.exceptions import NoCredentialsError

from app.core.database import get_db, engine
from app.core.config import settings
from app.models.literature import Literature
from app.models.project import Project
from app.models.user import User
from app.models.task import Task

class BackupStrategy:
    """备份策略"""
    
    def __init__(self):
        self.backup_config = {
            'daily': {
                'retention_days': 7,
                'tables': ['users', 'projects', 'literature', 'tasks'],
                'compression': True
            },
            'weekly': {
                'retention_weeks': 4,
                'tables': 'all',
                'compression': True,
                'include_files': True
            },
            'monthly': {
                'retention_months': 12,
                'tables': 'all',
                'compression': True,
                'include_files': True,
                'cloud_backup': True
            }
        }
        
        self.backup_dir = Path("./backups")
        self.backup_dir.mkdir(exist_ok=True)
    
    async def create_database_backup(
        self, 
        backup_type: str = 'daily',
        tables: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """创建数据库备份"""
        
        try:
            config = self.backup_config[backup_type]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"{backup_type}_backup_{timestamp}"
            backup_path = self.backup_dir / backup_name
            backup_path.mkdir(exist_ok=True)
            
            logger.info(f"开始创建{backup_type}备份: {backup_name}")
            
            # 确定要备份的表
            if tables:
                target_tables = tables
            elif config['tables'] == 'all':
                target_tables = await self._get_all_tables()
            else:
                target_tables = config['tables']
            
            backup_info = {
                'backup_name': backup_name,
                'backup_type': backup_type,
                'timestamp': timestamp,
                'tables': [],
                'total_rows': 0,
                'total_size_mb': 0,
                'duration_seconds': 0
            }
            
            start_time = datetime.now()
            
            # 备份每个表
            for table_name in target_tables:
                table_info = await self._backup_table(
                    table_name, 
                    backup_path, 
                    config['compression']
                )
                backup_info['tables'].append(table_info)
                backup_info['total_rows'] += table_info['row_count']
                backup_info['total_size_mb'] += table_info['size_mb']
            
            # 备份文件（如果配置了）
            if config.get('include_files'):
                file_info = await self._backup_files(backup_path)
                backup_info['files'] = file_info
            
            # 创建备份元数据
            backup_info['duration_seconds'] = (datetime.now() - start_time).total_seconds()
            
            metadata_file = backup_path / 'backup_metadata.json'
            async with aiofiles.open(metadata_file, 'w') as f:
                await f.write(json.dumps(backup_info, indent=2, default=str))
            
            # 云备份（如果配置了）
            if config.get('cloud_backup'):
                await self._upload_to_cloud(backup_path, backup_name)
            
            # 清理旧备份
            await self._cleanup_old_backups(backup_type)
            
            logger.info(f"备份完成: {backup_name}, 总行数: {backup_info['total_rows']}, 大小: {backup_info['total_size_mb']:.2f}MB")
            
            return backup_info
            
        except Exception as e:
            logger.error(f"创建备份失败: {e}")
            raise
    
    async def _get_all_tables(self) -> List[str]:
        """获取所有表名"""
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
            """))
            return [row[0] for row in result]
    
    async def _backup_table(
        self, 
        table_name: str, 
        backup_path: Path, 
        compress: bool = True
    ) -> Dict[str, Any]:
        """备份单个表"""
        
        try:
            # 查询表数据
            async with engine.begin() as conn:
                result = await conn.execute(text(f"SELECT * FROM {table_name}"))
                rows = result.fetchall()
                columns = result.keys()
            
            # 转换为DataFrame
            df = pd.DataFrame(rows, columns=columns)
            
            # 保存为CSV
            csv_filename = f"{table_name}.csv"
            if compress:
                csv_filename += ".gz"
            
            csv_path = backup_path / csv_filename
            
            if compress:
                df.to_csv(csv_path, index=False, compression='gzip')
            else:
                df.to_csv(csv_path, index=False)
            
            # 计算文件大小
            file_size_mb = os.path.getsize(csv_path) / 1024 / 1024
            
            return {
                'table_name': table_name,
                'row_count': len(rows),
                'column_count': len(columns),
                'file_name': csv_filename,
                'size_mb': file_size_mb,
                'compressed': compress
            }
            
        except Exception as e:
            logger.error(f"备份表 {table_name} 失败: {e}")
            return {
                'table_name': table_name,
                'error': str(e),
                'row_count': 0,
                'size_mb': 0
            }
    
    async def _backup_files(self, backup_path: Path) -> Dict[str, Any]:
        """备份上传的文件"""
        try:
            uploads_dir = Path("./uploads")
            if not uploads_dir.exists():
                return {'status': 'no_files', 'size_mb': 0}
            
            files_backup_path = backup_path / "files"
            
            # 复制文件目录
            await asyncio.get_event_loop().run_in_executor(
                None, 
                shutil.copytree, 
                uploads_dir, 
                files_backup_path
            )
            
            # 计算总大小
            total_size = sum(
                os.path.getsize(os.path.join(dirpath, filename))
                for dirpath, dirnames, filenames in os.walk(files_backup_path)
                for filename in filenames
            )
            
            return {
                'status': 'success',
                'file_count': len(list(files_backup_path.rglob('*'))),
                'size_mb': total_size / 1024 / 1024
            }
            
        except Exception as e:
            logger.error(f"备份文件失败: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'size_mb': 0
            }
    
    async def _upload_to_cloud(self, backup_path: Path, backup_name: str):
        """上传备份到云存储"""
        try:
            # 压缩备份目录
            archive_path = f"{backup_path}.tar.gz"
            await asyncio.get_event_loop().run_in_executor(
                None,
                shutil.make_archive,
                str(backup_path),
                'gztar',
                str(backup_path.parent),
                backup_path.name
            )
            
            # 上传到S3（示例）
            if hasattr(settings, 'aws_access_key_id'):
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=settings.aws_access_key_id,
                    aws_secret_access_key=settings.aws_secret_access_key,
                    region_name=settings.aws_region
                )
                
                bucket_name = settings.backup_bucket_name
                s3_key = f"backups/{backup_name}.tar.gz"
                
                s3_client.upload_file(archive_path, bucket_name, s3_key)
                logger.info(f"备份已上传到云存储: s3://{bucket_name}/{s3_key}")
            
            # 删除本地压缩文件
            os.remove(archive_path)
            
        except NoCredentialsError:
            logger.warning("AWS凭证未配置，跳过云备份")
        except Exception as e:
            logger.error(f"云备份失败: {e}")
    
    async def _cleanup_old_backups(self, backup_type: str):
        """清理过期备份"""
        try:
            config = self.backup_config[backup_type]
            
            if backup_type == 'daily':
                cutoff_date = datetime.now() - timedelta(days=config['retention_days'])
            elif backup_type == 'weekly':
                cutoff_date = datetime.now() - timedelta(weeks=config['retention_weeks'])
            elif backup_type == 'monthly':
                cutoff_date = datetime.now() - timedelta(days=config['retention_months'] * 30)
            else:
                return
            
            # 查找过期备份
            for backup_dir in self.backup_dir.glob(f"{backup_type}_backup_*"):
                try:
                    # 从目录名提取时间戳
                    timestamp_str = backup_dir.name.split('_')[-2] + '_' + backup_dir.name.split('_')[-1]
                    backup_date = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                    
                    if backup_date < cutoff_date:
                        shutil.rmtree(backup_dir)
                        logger.info(f"已删除过期备份: {backup_dir.name}")
                        
                except Exception as e:
                    logger.warning(f"清理备份 {backup_dir.name} 失败: {e}")
                    
        except Exception as e:
            logger.error(f"清理过期备份失败: {e}")

class DataMigrationManager:
    """数据迁移管理器"""
    
    def __init__(self):
        self.migration_scripts_dir = Path("./migrations/data")
        self.migration_scripts_dir.mkdir(parents=True, exist_ok=True)
    
    async def migrate_user_data(
        self, 
        source_user_id: int, 
        target_user_id: int,
        include_projects: bool = True,
        include_literature: bool = True
    ) -> Dict[str, Any]:
        """迁移用户数据"""
        
        migration_log = {
            'source_user_id': source_user_id,
            'target_user_id': target_user_id,
            'started_at': datetime.now(),
            'migrated_items': {},
            'errors': []
        }
        
        try:
            async with engine.begin() as conn:
                # 迁移项目
                if include_projects:
                    projects_result = await conn.execute(text("""
                        UPDATE projects 
                        SET owner_id = :target_id 
                        WHERE owner_id = :source_id
                        RETURNING id, name
                    """), {"source_id": source_user_id, "target_id": target_user_id})
                    
                    migrated_projects = projects_result.fetchall()
                    migration_log['migrated_items']['projects'] = [
                        {'id': p[0], 'name': p[1]} for p in migrated_projects
                    ]
                
                # 迁移文献（通过项目关联）
                if include_literature:
                    literature_result = await conn.execute(text("""
                        SELECT COUNT(*) FROM literature l
                        JOIN projects p ON l.project_id = p.id
                        WHERE p.owner_id = :target_id
                    """), {"target_id": target_user_id})
                    
                    literature_count = literature_result.scalar()
                    migration_log['migrated_items']['literature_count'] = literature_count
                
                migration_log['completed_at'] = datetime.now()
                migration_log['success'] = True
                
                logger.info(f"用户数据迁移完成: {source_user_id} -> {target_user_id}")
                
        except Exception as e:
            migration_log['errors'].append(str(e))
            migration_log['success'] = False
            logger.error(f"用户数据迁移失败: {e}")
            raise
        
        return migration_log
    
    async def export_user_data(
        self, 
        user_id: int, 
        export_format: str = 'json',
        include_files: bool = False
    ) -> Dict[str, Any]:
        """导出用户数据（GDPR合规）"""
        
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'format': export_format
        }
        
        try:
            async with engine.begin() as conn:
                # 用户基本信息
                user_result = await conn.execute(text("""
                    SELECT u.*, um.membership_type, um.subscription_start, um.subscription_end
                    FROM users u
                    LEFT JOIN user_memberships um ON u.id = um.user_id
                    WHERE u.id = :user_id
                """), {"user_id": user_id})
                
                user_data = user_result.fetchone()
                if user_data:
                    export_data['user_info'] = dict(user_data._mapping)
                
                # 项目数据
                projects_result = await conn.execute(text("""
                    SELECT * FROM projects WHERE owner_id = :user_id
                """), {"user_id": user_id})
                
                export_data['projects'] = [dict(p._mapping) for p in projects_result.fetchall()]
                
                # 文献数据
                literature_result = await conn.execute(text("""
                    SELECT l.* FROM literature l
                    JOIN projects p ON l.project_id = p.id
                    WHERE p.owner_id = :user_id
                """), {"user_id": user_id})
                
                export_data['literature'] = [dict(l._mapping) for l in literature_result.fetchall()]
                
                # 任务历史
                tasks_result = await conn.execute(text("""
                    SELECT t.* FROM tasks t
                    JOIN projects p ON t.project_id = p.id
                    WHERE p.owner_id = :user_id
                """), {"user_id": user_id})
                
                export_data['task_history'] = [dict(t._mapping) for t in tasks_result.fetchall()]
            
            # 保存导出文件
            export_filename = f"user_data_export_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            if export_format == 'json':
                export_path = self.backup_dir / f"{export_filename}.json"
                async with aiofiles.open(export_path, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(export_data, indent=2, default=str, ensure_ascii=False))
            
            elif export_format == 'excel':
                export_path = self.backup_dir / f"{export_filename}.xlsx"
                with pd.ExcelWriter(export_path, engine='openpyxl') as writer:
                    # 用户信息
                    if export_data.get('user_info'):
                        pd.DataFrame([export_data['user_info']]).to_excel(
                            writer, sheet_name='用户信息', index=False
                        )
                    
                    # 项目信息
                    if export_data.get('projects'):
                        pd.DataFrame(export_data['projects']).to_excel(
                            writer, sheet_name='项目', index=False
                        )
                    
                    # 文献信息
                    if export_data.get('literature'):
                        pd.DataFrame(export_data['literature']).to_excel(
                            writer, sheet_name='文献', index=False
                        )
            
            return {
                'success': True,
                'export_file': str(export_path),
                'file_size_mb': os.path.getsize(export_path) / 1024 / 1024,
                'records_exported': {
                    'projects': len(export_data.get('projects', [])),
                    'literature': len(export_data.get('literature', [])),
                    'tasks': len(export_data.get('task_history', []))
                }
            }
            
        except Exception as e:
            logger.error(f"导出用户数据失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }

class DataCleanupManager:
    """数据清理管理器"""
    
    def __init__(self):
        self.cleanup_policies = {
            'inactive_users': {
                'threshold_days': 365,  # 1年未活跃
                'action': 'archive'     # 归档而非删除
            },
            'failed_tasks': {
                'threshold_days': 30,   # 30天前的失败任务
                'action': 'delete'
            },
            'temporary_files': {
                'threshold_days': 7,    # 7天前的临时文件
                'action': 'delete'
            },
            'cache_data': {
                'threshold_days': 30,   # 30天前的缓存
                'action': 'delete'
            },
            'log_data': {
                'threshold_days': 90,   # 90天前的日志
                'action': 'compress'
            }
        }
    
    async def cleanup_inactive_data(self, dry_run: bool = True) -> Dict[str, Any]:
        """清理不活跃数据"""
        
        cleanup_report = {
            'started_at': datetime.now(),
            'dry_run': dry_run,
            'actions': []
        }
        
        try:
            # 清理不活跃用户
            inactive_users = await self._find_inactive_users()
            if inactive_users:
                action = {
                    'type': 'archive_inactive_users',
                    'count': len(inactive_users),
                    'user_ids': [u['id'] for u in inactive_users]
                }
                
                if not dry_run:
                    await self._archive_inactive_users(inactive_users)
                    action['status'] = 'completed'
                else:
                    action['status'] = 'simulated'
                
                cleanup_report['actions'].append(action)
            
            # 清理失败任务
            failed_tasks = await self._find_failed_tasks()
            if failed_tasks:
                action = {
                    'type': 'delete_failed_tasks',
                    'count': len(failed_tasks),
                    'task_ids': failed_tasks
                }
                
                if not dry_run:
                    await self._delete_failed_tasks(failed_tasks)
                    action['status'] = 'completed'
                else:
                    action['status'] = 'simulated'
                
                cleanup_report['actions'].append(action)
            
            # 清理临时文件
            temp_files = await self._find_temporary_files()
            if temp_files:
                action = {
                    'type': 'delete_temporary_files',
                    'count': len(temp_files),
                    'size_mb': sum(os.path.getsize(f) for f in temp_files if os.path.exists(f)) / 1024 / 1024
                }
                
                if not dry_run:
                    await self._delete_temporary_files(temp_files)
                    action['status'] = 'completed'
                else:
                    action['status'] = 'simulated'
                
                cleanup_report['actions'].append(action)
            
            cleanup_report['completed_at'] = datetime.now()
            cleanup_report['success'] = True
            
            logger.info(f"数据清理{'模拟' if dry_run else ''}完成，共{len(cleanup_report['actions'])}个操作")
            
        except Exception as e:
            cleanup_report['error'] = str(e)
            cleanup_report['success'] = False
            logger.error(f"数据清理失败: {e}")
        
        return cleanup_report
    
    async def _find_inactive_users(self) -> List[Dict]:
        """查找不活跃用户"""
        cutoff_date = datetime.now() - timedelta(days=365)
        
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT u.id, u.username, u.email, u.last_login,
                       COUNT(p.id) as project_count,
                       MAX(p.updated_at) as last_project_update
                FROM users u
                LEFT JOIN projects p ON u.id = p.owner_id
                WHERE (u.last_login IS NULL OR u.last_login < :cutoff_date)
                AND (p.updated_at IS NULL OR p.updated_at < :cutoff_date)
                GROUP BY u.id, u.username, u.email, u.last_login
                HAVING COUNT(p.id) = 0 OR MAX(p.updated_at) < :cutoff_date
            """), {"cutoff_date": cutoff_date})
            
            return [dict(row._mapping) for row in result.fetchall()]
    
    async def _find_failed_tasks(self) -> List[int]:
        """查找失败的任务"""
        cutoff_date = datetime.now() - timedelta(days=30)
        
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT id FROM tasks 
                WHERE status = 'failed' 
                AND created_at < :cutoff_date
            """), {"cutoff_date": cutoff_date})
            
            return [row[0] for row in result.fetchall()]
    
    async def _find_temporary_files(self) -> List[str]:
        """查找临时文件"""
        temp_dirs = ["./temp", "./cache", "./uploads/temp"]
        temp_files = []
        cutoff_date = datetime.now() - timedelta(days=7)
        
        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                            if file_mtime < cutoff_date:
                                temp_files.append(file_path)
                        except:
                            continue
        
        return temp_files
    
    async def _archive_inactive_users(self, users: List[Dict]):
        """归档不活跃用户"""
        for user in users:
            try:
                async with engine.begin() as conn:
                    # 标记用户为不活跃
                    await conn.execute(text("""
                        UPDATE users 
                        SET is_active = false, 
                            archived_at = NOW(),
                            archive_reason = 'inactive_cleanup'
                        WHERE id = :user_id
                    """), {"user_id": user['id']})
                    
                logger.info(f"已归档不活跃用户: {user['username']}")
                
            except Exception as e:
                logger.error(f"归档用户 {user['id']} 失败: {e}")
    
    async def _delete_failed_tasks(self, task_ids: List[int]):
        """删除失败任务"""
        try:
            async with engine.begin() as conn:
                # 先删除任务进度记录
                await conn.execute(text("""
                    DELETE FROM task_progress 
                    WHERE task_id = ANY(:task_ids)
                """), {"task_ids": task_ids})
                
                # 删除任务记录
                await conn.execute(text("""
                    DELETE FROM tasks 
                    WHERE id = ANY(:task_ids)
                """), {"task_ids": task_ids})
                
                logger.info(f"已删除{len(task_ids)}个失败任务")
                
        except Exception as e:
            logger.error(f"删除失败任务失败: {e}")
    
    async def _delete_temporary_files(self, file_paths: List[str]):
        """删除临时文件"""
        deleted_count = 0
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_count += 1
            except Exception as e:
                logger.warning(f"删除临时文件 {file_path} 失败: {e}")
        
        logger.info(f"已删除{deleted_count}个临时文件")

class DataIntegrityChecker:
    """数据完整性检查器"""
    
    async def check_data_integrity(self) -> Dict[str, Any]:
        """检查数据完整性"""
        
        integrity_report = {
            'checked_at': datetime.now(),
            'checks': [],
            'issues_found': 0,
            'critical_issues': 0
        }
        
        try:
            # 检查外键约束
            fk_issues = await self._check_foreign_key_integrity()
            integrity_report['checks'].append({
                'name': 'foreign_key_integrity',
                'status': 'passed' if not fk_issues else 'failed',
                'issues': fk_issues,
                'critical': True
            })
            
            if fk_issues:
                integrity_report['critical_issues'] += len(fk_issues)
            
            # 检查数据一致性
            consistency_issues = await self._check_data_consistency()
            integrity_report['checks'].append({
                'name': 'data_consistency',
                'status': 'passed' if not consistency_issues else 'failed',
                'issues': consistency_issues,
                'critical': False
            })
            
            integrity_report['issues_found'] += len(consistency_issues)
            
            # 检查重复数据
            duplicate_issues = await self._check_duplicate_data()
            integrity_report['checks'].append({
                'name': 'duplicate_data',
                'status': 'passed' if not duplicate_issues else 'warning',
                'issues': duplicate_issues,
                'critical': False
            })
            
            integrity_report['issues_found'] += len(duplicate_issues)
            
            # 检查孤立数据
            orphan_issues = await self._check_orphaned_data()
            integrity_report['checks'].append({
                'name': 'orphaned_data',
                'status': 'passed' if not orphan_issues else 'warning',
                'issues': orphan_issues,
                'critical': False
            })
            
            integrity_report['issues_found'] += len(orphan_issues)
            
        except Exception as e:
            integrity_report['error'] = str(e)
            logger.error(f"数据完整性检查失败: {e}")
        
        return integrity_report
    
    async def _check_foreign_key_integrity(self) -> List[Dict]:
        """检查外键完整性"""
        issues = []
        
        try:
            async with engine.begin() as conn:
                # 检查项目-用户关联
                result = await conn.execute(text("""
                    SELECT p.id, p.name, p.owner_id
                    FROM projects p
                    LEFT JOIN users u ON p.owner_id = u.id
                    WHERE u.id IS NULL
                """))
                
                for row in result.fetchall():
                    issues.append({
                        'type': 'missing_user',
                        'table': 'projects',
                        'record_id': row[0],
                        'details': f"项目 '{row[1]}' 引用不存在的用户ID: {row[2]}"
                    })
                
                # 检查文献-项目关联
                result = await conn.execute(text("""
                    SELECT l.id, l.title, l.project_id
                    FROM literature l
                    LEFT JOIN projects p ON l.project_id = p.id
                    WHERE p.id IS NULL
                """))
                
                for row in result.fetchall():
                    issues.append({
                        'type': 'missing_project',
                        'table': 'literature',
                        'record_id': row[0],
                        'details': f"文献 '{row[1][:50]}...' 引用不存在的项目ID: {row[2]}"
                    })
                    
        except Exception as e:
            logger.error(f"外键完整性检查失败: {e}")
        
        return issues
    
    async def _check_data_consistency(self) -> List[Dict]:
        """检查数据一致性"""
        issues = []
        
        try:
            async with engine.begin() as conn:
                # 检查用户会员信息一致性
                result = await conn.execute(text("""
                    SELECT u.id, u.username
                    FROM users u
                    LEFT JOIN user_memberships um ON u.id = um.user_id
                    WHERE u.is_active = true AND um.user_id IS NULL
                """))
                
                for row in result.fetchall():
                    issues.append({
                        'type': 'missing_membership',
                        'table': 'users',
                        'record_id': row[0],
                        'details': f"活跃用户 '{row[1]}' 缺少会员信息"
                    })
                
                # 检查项目统计一致性
                result = await conn.execute(text("""
                    SELECT p.id, p.name, p.literature_count, COUNT(l.id) as actual_count
                    FROM projects p
                    LEFT JOIN literature l ON p.id = l.project_id
                    GROUP BY p.id, p.name, p.literature_count
                    HAVING p.literature_count != COUNT(l.id)
                """))
                
                for row in result.fetchall():
                    issues.append({
                        'type': 'count_mismatch',
                        'table': 'projects',
                        'record_id': row[0],
                        'details': f"项目 '{row[1]}' 文献计数不匹配: 记录{row[2]} vs 实际{row[3]}"
                    })
                    
        except Exception as e:
            logger.error(f"数据一致性检查失败: {e}")
        
        return issues
    
    async def _check_duplicate_data(self) -> List[Dict]:
        """检查重复数据"""
        issues = []
        
        try:
            async with engine.begin() as conn:
                # 检查重复DOI
                result = await conn.execute(text("""
                    SELECT doi, COUNT(*) as count, array_agg(id) as ids
                    FROM literature
                    WHERE doi IS NOT NULL AND doi != ''
                    GROUP BY doi
                    HAVING COUNT(*) > 1
                """))
                
                for row in result.fetchall():
                    issues.append({
                        'type': 'duplicate_doi',
                        'table': 'literature',
                        'details': f"重复DOI: {row[0]}, 影响{row[1]}条记录: {row[2]}"
                    })
                
                # 检查重复邮箱
                result = await conn.execute(text("""
                    SELECT email, COUNT(*) as count, array_agg(id) as ids
                    FROM users
                    GROUP BY email
                    HAVING COUNT(*) > 1
                """))
                
                for row in result.fetchall():
                    issues.append({
                        'type': 'duplicate_email',
                        'table': 'users',
                        'details': f"重复邮箱: {row[0]}, 影响{row[1]}条记录: {row[2]}"
                    })
                    
        except Exception as e:
            logger.error(f"重复数据检查失败: {e}")
        
        return issues
    
    async def _check_orphaned_data(self) -> List[Dict]:
        """检查孤立数据"""
        issues = []
        
        try:
            async with engine.begin() as conn:
                # 检查孤立的文献段落
                result = await conn.execute(text("""
                    SELECT ls.id, ls.literature_id
                    FROM literature_segments ls
                    LEFT JOIN literature l ON ls.literature_id = l.id
                    WHERE l.id IS NULL
                """))
                
                orphaned_segments = result.fetchall()
                if orphaned_segments:
                    issues.append({
                        'type': 'orphaned_segments',
                        'table': 'literature_segments',
                        'count': len(orphaned_segments),
                        'details': f"发现{len(orphaned_segments)}个孤立的文献段落"
                    })
                
                # 检查孤立的任务进度
                result = await conn.execute(text("""
                    SELECT tp.id, tp.task_id
                    FROM task_progress tp
                    LEFT JOIN tasks t ON tp.task_id = t.id
                    WHERE t.id IS NULL
                """))
                
                orphaned_progress = result.fetchall()
                if orphaned_progress:
                    issues.append({
                        'type': 'orphaned_progress',
                        'table': 'task_progress',
                        'count': len(orphaned_progress),
                        'details': f"发现{len(orphaned_progress)}个孤立的任务进度记录"
                    })
                    
        except Exception as e:
            logger.error(f"孤立数据检查失败: {e}")
        
        return issues

# 全局实例
backup_strategy = BackupStrategy()
migration_manager = DataMigrationManager()
cleanup_manager = DataCleanupManager()
integrity_checker = DataIntegrityChecker()