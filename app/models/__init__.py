"""
统一模型管理
确保所有模型正确导入和关系定义
"""

from app.models.user import User, UserMembership, MembershipType
from app.models.project import Project, project_literature_association
from app.models.literature import Literature, LiteratureSegment
from app.models.shared_literature import SharedLiterature, UserLiteratureReference
from app.models.task import Task, TaskProgress, TaskType, TaskStatus
from app.models.experience import ExperienceBook, MainExperience
from app.models.collaboration import (
    Team, TeamMember, ProjectCollaboration, CollaborationInvitation,
    CollaborationComment, ActivityLog, CollaborationRole, InvitationStatus
)
from app.models.intelligent_template import TemplateDiscovery, PromptTemplate
from app.models.interaction import InteractionSession, ClarificationCard, InteractionAnalytics

# 导出所有模型
__all__ = [
    # 用户模型
    'User',
    'UserMembership', 
    'MembershipType',
    
    # 项目模型
    'Project',
    'project_literature_association',
    
    # 文献模型
    'Literature',
    'LiteratureSegment',
    
    # 共享文献模型
    'SharedLiterature',
    'UserLiteratureReference',
    
    # 任务模型
    'Task',
    'TaskProgress',
    'TaskType',
    'TaskStatus',
    
    # 经验模型
    'ExperienceBook',
    'MainExperience',
    
    # 协作模型
    'Team',
    'TeamMember',
    'ProjectCollaboration',
    'CollaborationInvitation',
    'CollaborationComment',
    'ActivityLog',
    'CollaborationRole',
    'InvitationStatus',

    # 智能模板模型
    'TemplateDiscovery',
    'PromptTemplate',

    # 智能交互模型
    'InteractionSession',
    'ClarificationCard',
    'InteractionAnalytics'
]

# 模型关系验证
def validate_model_relationships():
    """验证模型关系的正确性"""
    
    validation_errors = []
    
    try:
        # 验证User模型关系
        user_relationships = ['membership', 'projects']
        for rel in user_relationships:
            if not hasattr(User, rel):
                validation_errors.append(f"User模型缺少关系: {rel}")
        
        # 验证Project模型关系
        project_relationships = ['owner', 'literature']
        for rel in project_relationships:
            if not hasattr(Project, rel):
                validation_errors.append(f"Project模型缺少关系: {rel}")
        
        # 验证Literature模型关系
        literature_relationships = ['segments', 'projects']
        for rel in literature_relationships:
            if not hasattr(Literature, rel):
                validation_errors.append(f"Literature模型缺少关系: {rel}")
        
        # 验证外键约束
        foreign_key_checks = [
            (UserMembership, 'user_id', User, 'id'),
            (Project, 'owner_id', User, 'id'),
            (LiteratureSegment, 'literature_id', Literature, 'id'),
        ]
        
        for child_model, fk_column, parent_model, pk_column in foreign_key_checks:
            child_table = child_model.__tablename__
            parent_table = parent_model.__tablename__
            
            if not hasattr(child_model, fk_column):
                validation_errors.append(
                    f"{child_table}模型缺少外键列: {fk_column} -> {parent_table}.{pk_column}"
                )
        
        if validation_errors:
            raise ValueError(f"模型关系验证失败: {validation_errors}")
        
        return True
        
    except Exception as e:
        raise ValueError(f"模型关系验证异常: {e}")

# 模型初始化检查
try:
    validate_model_relationships()
    print("✅ 模型关系验证通过")
except Exception as e:
    print(f"❌ 模型关系验证失败: {e}")
    raise