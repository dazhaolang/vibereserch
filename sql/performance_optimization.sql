-- 数据库性能优化SQL脚本
-- 为科研文献智能分析平台优化数据库性能

-- ============================================
-- 1. 索引优化
-- ============================================

-- 文献表核心索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_literature_project_status_created 
ON literature(project_id, status, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_literature_title_search 
ON literature USING gin(to_tsvector('english', title));

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_literature_abstract_search 
ON literature USING gin(to_tsvector('english', abstract));

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_literature_authors_search 
ON literature USING gin(authors);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_literature_tags_search 
ON literature USING gin(tags);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_literature_doi_unique 
ON literature(doi) WHERE doi IS NOT NULL;

-- 向量检索优化索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_literature_embedding_cosine 
ON literature_segments USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 1000);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_literature_embedding_ip 
ON literature_segments USING ivfflat (embedding vector_ip_ops) 
WITH (lists = 1000);

-- 用户和项目相关索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_email_active 
ON users(email, is_active) WHERE is_active = true;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_project_owner_created 
ON projects(owner_id, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_membership_type 
ON user_memberships(user_id, membership_type);

-- 任务和进度相关索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_project_status 
ON tasks(project_id, status, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_progress_task_updated 
ON task_progress(task_id, updated_at DESC);

-- ============================================
-- 2. 表分区策略
-- ============================================

-- 按时间分区文献表（如果数据量很大）
-- ALTER TABLE literature RENAME TO literature_old;

-- CREATE TABLE literature (
--     id SERIAL,
--     project_id INTEGER NOT NULL,
--     title TEXT NOT NULL,
--     authors TEXT[],
--     abstract TEXT,
--     created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
--     -- 其他字段...
--     PRIMARY KEY (id, created_at)
-- ) PARTITION BY RANGE (created_at);

-- 创建分区表
-- CREATE TABLE literature_2024 PARTITION OF literature 
-- FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');

-- CREATE TABLE literature_2025 PARTITION OF literature 
-- FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');

-- ============================================
-- 3. 视图优化
-- ============================================

-- 文献统计视图
CREATE OR REPLACE VIEW literature_stats AS
SELECT 
    p.id as project_id,
    p.name as project_name,
    COUNT(l.id) as total_literature,
    COUNT(CASE WHEN l.status = 'processed' THEN 1 END) as processed_count,
    COUNT(CASE WHEN l.status = 'pending' THEN 1 END) as pending_count,
    AVG(l.relevance_score) as avg_relevance_score,
    MAX(l.created_at) as last_added_at
FROM projects p
LEFT JOIN literature l ON p.id = l.project_id
GROUP BY p.id, p.name;

-- 用户活跃度视图
CREATE OR REPLACE VIEW user_activity_stats AS
SELECT 
    u.id as user_id,
    u.username,
    u.email,
    um.membership_type,
    COUNT(DISTINCT p.id) as project_count,
    COUNT(l.id) as literature_count,
    COUNT(DISTINCT DATE(l.created_at)) as active_days,
    MAX(l.created_at) as last_activity
FROM users u
LEFT JOIN user_memberships um ON u.id = um.user_id
LEFT JOIN projects p ON u.id = p.owner_id
LEFT JOIN literature l ON p.id = l.project_id
WHERE u.is_active = true
GROUP BY u.id, u.username, u.email, um.membership_type;

-- 系统性能视图
CREATE OR REPLACE VIEW system_performance_stats AS
SELECT 
    DATE(created_at) as date,
    COUNT(*) as daily_literature_processed,
    AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_processing_time,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_count,
    (COUNT(CASE WHEN status = 'completed' THEN 1 END)::float / COUNT(*) * 100) as success_rate
FROM tasks
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- ============================================
-- 4. 存储过程优化
-- ============================================

-- 批量文献处理存储过程
CREATE OR REPLACE FUNCTION batch_update_literature_status(
    p_literature_ids INTEGER[],
    p_new_status TEXT,
    p_user_id INTEGER
) RETURNS TABLE(
    updated_count INTEGER,
    failed_ids INTEGER[]
) AS $$
DECLARE
    v_updated_count INTEGER := 0;
    v_failed_ids INTEGER[] := ARRAY[]::INTEGER[];
    v_literature_id INTEGER;
BEGIN
    -- 验证用户权限并批量更新
    FOREACH v_literature_id IN ARRAY p_literature_ids
    LOOP
        BEGIN
            UPDATE literature 
            SET status = p_new_status, updated_at = NOW()
            WHERE id = v_literature_id 
            AND project_id IN (
                SELECT id FROM projects WHERE owner_id = p_user_id
            );
            
            IF FOUND THEN
                v_updated_count := v_updated_count + 1;
            ELSE
                v_failed_ids := array_append(v_failed_ids, v_literature_id);
            END IF;
        EXCEPTION WHEN OTHERS THEN
            v_failed_ids := array_append(v_failed_ids, v_literature_id);
        END;
    END LOOP;
    
    RETURN QUERY SELECT v_updated_count, v_failed_ids;
END;
$$ LANGUAGE plpgsql;

-- 智能文献去重存储过程
CREATE OR REPLACE FUNCTION intelligent_literature_dedup(
    p_project_id INTEGER
) RETURNS TABLE(
    duplicate_count INTEGER,
    duplicate_ids INTEGER[]
) AS $$
DECLARE
    v_duplicate_count INTEGER := 0;
    v_duplicate_ids INTEGER[] := ARRAY[]::INTEGER[];
BEGIN
    -- 基于DOI去重
    WITH doi_duplicates AS (
        SELECT doi, array_agg(id ORDER BY created_at) as ids
        FROM literature 
        WHERE project_id = p_project_id AND doi IS NOT NULL
        GROUP BY doi
        HAVING COUNT(*) > 1
    )
    INSERT INTO literature_duplicates (original_id, duplicate_ids, detection_method)
    SELECT 
        ids[1], 
        ids[2:], 
        'doi_match'
    FROM doi_duplicates;
    
    -- 基于标题相似度去重（使用编辑距离）
    WITH title_duplicates AS (
        SELECT 
            l1.id as id1,
            l2.id as id2,
            similarity(l1.title, l2.title) as sim_score
        FROM literature l1
        JOIN literature l2 ON l1.project_id = l2.project_id
        WHERE l1.id < l2.id 
        AND l1.project_id = p_project_id
        AND similarity(l1.title, l2.title) > 0.8
    )
    INSERT INTO literature_duplicates (original_id, duplicate_ids, detection_method, similarity_score)
    SELECT 
        id1, 
        ARRAY[id2], 
        'title_similarity',
        sim_score
    FROM title_duplicates;
    
    GET DIAGNOSTICS v_duplicate_count = ROW_COUNT;
    
    RETURN QUERY SELECT v_duplicate_count, v_duplicate_ids;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- 5. 数据库配置优化
-- ============================================

-- 连接和内存配置（需要数据库管理员权限）
-- ALTER SYSTEM SET shared_buffers = '256MB';
-- ALTER SYSTEM SET effective_cache_size = '1GB';
-- ALTER SYSTEM SET maintenance_work_mem = '64MB';
-- ALTER SYSTEM SET checkpoint_completion_target = 0.9;
-- ALTER SYSTEM SET wal_buffers = '16MB';
-- ALTER SYSTEM SET default_statistics_target = 100;
-- ALTER SYSTEM SET random_page_cost = 1.1;
-- ALTER SYSTEM SET effective_io_concurrency = 200;

-- ============================================
-- 6. 监控和统计
-- ============================================

-- 查询性能监控表
CREATE TABLE IF NOT EXISTS query_performance_log (
    id SERIAL PRIMARY KEY,
    query_hash TEXT NOT NULL,
    query_text TEXT NOT NULL,
    execution_time_ms FLOAT NOT NULL,
    rows_returned INTEGER,
    user_id INTEGER,
    endpoint TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_query_perf_hash_time ON query_performance_log(query_hash, created_at DESC);

-- 慢查询检测函数
CREATE OR REPLACE FUNCTION log_slow_query(
    p_query_text TEXT,
    p_execution_time_ms FLOAT,
    p_user_id INTEGER DEFAULT NULL,
    p_endpoint TEXT DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    IF p_execution_time_ms > 1000 THEN  -- 超过1秒的查询
        INSERT INTO query_performance_log (
            query_hash,
            query_text,
            execution_time_ms,
            user_id,
            endpoint
        ) VALUES (
            md5(p_query_text),
            p_query_text,
            p_execution_time_ms,
            p_user_id,
            p_endpoint
        );
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- 7. 定期维护任务
-- ============================================

-- 统计信息更新
-- 建议在cron中运行: 0 2 * * * psql -d research_platform -c "ANALYZE;"

-- 索引维护
-- 建议定期运行: REINDEX INDEX CONCURRENTLY idx_literature_embedding_cosine;

-- 清理过期数据
CREATE OR REPLACE FUNCTION cleanup_expired_data() RETURNS VOID AS $$
BEGIN
    -- 清理过期的任务进度记录（保留30天）
    DELETE FROM task_progress 
    WHERE updated_at < NOW() - INTERVAL '30 days';
    
    -- 清理过期的会话数据（保留7天）
    DELETE FROM user_sessions 
    WHERE created_at < NOW() - INTERVAL '7 days';
    
    -- 清理过期的缓存记录
    DELETE FROM cache_entries 
    WHERE expires_at < NOW();
    
    -- 记录清理日志
    INSERT INTO maintenance_log (operation, details, created_at)
    VALUES ('cleanup_expired_data', 'Cleaned up expired data', NOW());
END;
$$ LANGUAGE plpgsql;

-- 创建维护日志表
CREATE TABLE IF NOT EXISTS maintenance_log (
    id SERIAL PRIMARY KEY,
    operation TEXT NOT NULL,
    details TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);