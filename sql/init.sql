-- 科研文献智能分析平台数据库初始化脚本

-- 创建Elasticsearch扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 创建全文搜索扩展
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 创建索引函数
CREATE OR REPLACE FUNCTION create_indexes() RETURNS void AS $$
BEGIN
    -- 用户表索引
    CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
    CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
    CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);
    
    -- 项目表索引
    CREATE INDEX IF NOT EXISTS idx_projects_owner_id ON projects(owner_id);
    CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
    CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at);
    
    -- 文献表索引
    CREATE INDEX IF NOT EXISTS idx_literature_doi ON literature(doi);
    CREATE INDEX IF NOT EXISTS idx_literature_title ON literature USING gin(title gin_trgm_ops);
    CREATE INDEX IF NOT EXISTS idx_literature_publication_year ON literature(publication_year);
    CREATE INDEX IF NOT EXISTS idx_literature_quality_score ON literature(quality_score);
    CREATE INDEX IF NOT EXISTS idx_literature_citation_count ON literature(citation_count);
    
    -- 向量索引
    CREATE INDEX IF NOT EXISTS idx_literature_title_embedding ON literature USING ivfflat (title_embedding vector_cosine_ops);
    CREATE INDEX IF NOT EXISTS idx_literature_abstract_embedding ON literature USING ivfflat (abstract_embedding vector_cosine_ops);
    CREATE INDEX IF NOT EXISTS idx_segments_content_embedding ON literature_segments USING ivfflat (content_embedding vector_cosine_ops);
    
    -- 文献段落索引
    CREATE INDEX IF NOT EXISTS idx_segments_literature_id ON literature_segments(literature_id);
    CREATE INDEX IF NOT EXISTS idx_segments_segment_type ON literature_segments(segment_type);
    CREATE INDEX IF NOT EXISTS idx_segments_content ON literature_segments USING gin(content gin_trgm_ops);
    
    -- 全文搜索索引
    CREATE INDEX IF NOT EXISTS idx_segments_content_fts ON literature_segments USING gin(to_tsvector('english', content));
    
    -- 任务表索引
    CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks(project_id);
    CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
    CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
    
    -- 经验书索引
    CREATE INDEX IF NOT EXISTS idx_experience_books_project_id ON experience_books(project_id);
    CREATE INDEX IF NOT EXISTS idx_experience_books_iteration_round ON experience_books(iteration_round);
    CREATE INDEX IF NOT EXISTS idx_main_experiences_project_id ON main_experiences(project_id);
    CREATE INDEX IF NOT EXISTS idx_main_experiences_is_current ON main_experiences(is_current);
    
END;
$$ LANGUAGE plpgsql;

-- 创建触发器函数：自动更新updated_at字段
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建用户统计视图
CREATE OR REPLACE VIEW user_statistics AS
SELECT 
    u.id as user_id,
    u.username,
    u.email,
    um.membership_type,
    COUNT(DISTINCT p.id) as total_projects,
    COUNT(DISTINCT l.id) as total_literature,
    COUNT(DISTINCT t.id) as total_tasks,
    COUNT(DISTINCT CASE WHEN t.status = 'completed' THEN t.id END) as completed_tasks,
    MAX(p.created_at) as last_project_created,
    MAX(u.last_login) as last_login
FROM users u
LEFT JOIN user_memberships um ON u.id = um.user_id
LEFT JOIN projects p ON u.id = p.owner_id
LEFT JOIN project_literature_associations pla ON p.id = pla.project_id
LEFT JOIN literature l ON pla.literature_id = l.id
LEFT JOIN tasks t ON p.id = t.project_id
GROUP BY u.id, u.username, u.email, um.membership_type;

-- 创建项目统计视图
CREATE OR REPLACE VIEW project_statistics AS
SELECT 
    p.id as project_id,
    p.name as project_name,
    p.owner_id,
    COUNT(DISTINCT l.id) as literature_count,
    COUNT(DISTINCT ls.id) as segments_count,
    COUNT(DISTINCT eb.id) as experience_books_count,
    COUNT(DISTINCT me.id) as main_experiences_count,
    COUNT(DISTINCT t.id) as total_tasks,
    COUNT(DISTINCT CASE WHEN t.status = 'completed' THEN t.id END) as completed_tasks,
    AVG(l.quality_score) as avg_literature_quality,
    MAX(l.publication_year) as latest_publication_year,
    MIN(l.publication_year) as earliest_publication_year
FROM projects p
LEFT JOIN project_literature_associations pla ON p.id = pla.project_id
LEFT JOIN literature l ON pla.literature_id = l.id
LEFT JOIN literature_segments ls ON l.id = ls.literature_id
LEFT JOIN experience_books eb ON p.id = eb.project_id
LEFT JOIN main_experiences me ON p.id = me.project_id
LEFT JOIN tasks t ON p.id = t.project_id
GROUP BY p.id, p.name, p.owner_id;

-- 插入默认数据
INSERT INTO users (email, username, hashed_password, full_name, is_active, is_verified) 
VALUES 
    ('admin@research-platform.com', 'admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4f8n8QnXhG', '系统管理员', true, true),
    ('demo@research-platform.com', 'demo_user', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4f8n8QnXhG', '演示用户', true, true)
ON CONFLICT (email) DO NOTHING;

-- 为默认用户创建会员信息
INSERT INTO user_memberships (user_id, membership_type, monthly_literature_used, monthly_queries_used, total_projects)
SELECT 
    u.id, 
    'premium'::membership_type,
    0,
    0, 
    0
FROM users u 
WHERE u.email IN ('admin@research-platform.com', 'demo@research-platform.com')
ON CONFLICT (user_id) DO NOTHING;

-- 创建研究领域模板
CREATE TABLE IF NOT EXISTS research_templates (
    id SERIAL PRIMARY KEY,
    domain_name VARCHAR(200) NOT NULL,
    template_structure JSONB NOT NULL,
    description TEXT,
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 插入默认研究模板
INSERT INTO research_templates (domain_name, template_structure, description) VALUES
('材料科学', '{
    "sections": [
        {
            "name": "制备与合成",
            "subsections": [
                {"name": "原料制备", "keywords": ["制备", "合成", "原料"], "extraction_points": ["制备方法", "工艺参数", "设备要求"]},
                {"name": "工艺优化", "keywords": ["优化", "工艺", "参数"], "extraction_points": ["优化策略", "关键参数", "工艺条件"]}
            ]
        },
        {
            "name": "表征与分析", 
            "subsections": [
                {"name": "结构表征", "keywords": ["XRD", "SEM", "TEM", "表征"], "extraction_points": ["表征方法", "结果分析", "结构信息"]},
                {"name": "性能测试", "keywords": ["性能", "测试", "测量"], "extraction_points": ["测试方法", "性能指标", "测试条件"]}
            ]
        }
    ]
}', '材料科学通用模板'),

('化学工程', '{
    "sections": [
        {
            "name": "反应工程",
            "subsections": [
                {"name": "反应机理", "keywords": ["机理", "反应", "催化"], "extraction_points": ["反应路径", "催化剂", "反应条件"]},
                {"name": "工艺设计", "keywords": ["工艺", "设计", "反应器"], "extraction_points": ["工艺流程", "设备设计", "操作条件"]}
            ]
        },
        {
            "name": "分离纯化",
            "subsections": [
                {"name": "分离技术", "keywords": ["分离", "纯化", "提取"], "extraction_points": ["分离方法", "分离效率", "纯度要求"]},
                {"name": "工艺优化", "keywords": ["优化", "能耗", "成本"], "extraction_points": ["优化目标", "优化方法", "经济性分析"]}
            ]
        }
    ]
}', '化学工程通用模板')
ON CONFLICT DO NOTHING;

-- 执行索引创建
SELECT create_indexes();