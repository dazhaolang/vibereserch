-- MySQL 初始化脚本
-- 仅负责创建数据库与基础账户，实际表结构请通过 Alembic 迁移或 ORM 自动创建

-- 创建数据库（若不存在）
CREATE DATABASE IF NOT EXISTS research_platform
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- 创建具备读写权限的业务账号（如已存在则忽略）
CREATE USER IF NOT EXISTS 'raggar'@'%' IDENTIFIED BY 'raggar123';
GRANT ALL PRIVILEGES ON research_platform.* TO 'raggar'@'%';
FLUSH PRIVILEGES;

-- 切换到目标数据库
USE research_platform;

-- 建议步骤：
-- 1. 执行 `alembic upgrade head` 以创建最新表结构与索引。
-- 2. 如需导入初始化数据，请使用专门的数据脚本或 ORM 种子逻辑。
