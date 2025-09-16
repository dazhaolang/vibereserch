"""
团队协作API路由
"""

from typing import List, Optional, Dict
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.models.project import Project
from app.models.collaboration import (
    Team, TeamMember, ProjectCollaboration, CollaborationInvitation,
    CollaborationComment, ActivityLog, CollaborationRole, InvitationStatus
)
from app.services.notification_service import NotificationService

router = APIRouter()

class TeamCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_public: bool = False
    max_members: int = 50

class TeamInvite(BaseModel):
    team_id: Optional[int] = None
    project_id: Optional[int] = None
    invitee_email: EmailStr
    role: CollaborationRole
    message: Optional[str] = None
    permissions: Optional[Dict] = None

class CommentCreate(BaseModel):
    content: str
    comment_type: str = "general"
    parent_comment_id: Optional[int] = None

class TeamResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_public: bool
    member_count: int
    created_at: str
    user_role: str

@router.post("/teams", response_model=TeamResponse)
async def create_team(
    team_data: TeamCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """创建团队"""
    
    # 创建团队
    team = Team(
        name=team_data.name,
        description=team_data.description,
        is_public=team_data.is_public,
        max_members=team_data.max_members,
        created_by=current_user.id
    )
    
    db.add(team)
    db.flush()
    
    # 添加创建者为团队所有者
    team_member = TeamMember(
        team_id=team.id,
        user_id=current_user.id,
        role=CollaborationRole.OWNER,
        permissions={
            "can_manage_members": True,
            "can_manage_projects": True,
            "can_delete_team": True,
            "can_modify_settings": True
        }
    )
    
    db.add(team_member)
    db.commit()
    db.refresh(team)
    
    # 记录活动日志
    activity = ActivityLog(
        user_id=current_user.id,
        team_id=team.id,
        action="created",
        target_type="team",
        target_id=team.id,
        description=f"创建了团队: {team.name}"
    )
    db.add(activity)
    db.commit()
    
    return TeamResponse(
        id=team.id,
        name=team.name,
        description=team.description,
        is_public=team.is_public,
        member_count=1,
        created_at=team.created_at.isoformat(),
        user_role="owner"
    )

@router.get("/teams", response_model=List[TeamResponse])
async def get_user_teams(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取用户所在的团队列表"""
    
    # 查询用户参与的团队
    team_members = db.query(TeamMember).filter(
        TeamMember.user_id == current_user.id,
        TeamMember.is_active == True
    ).all()
    
    teams = []
    for member in team_members:
        team = member.team
        member_count = db.query(TeamMember).filter(
            TeamMember.team_id == team.id,
            TeamMember.is_active == True
        ).count()
        
        teams.append(TeamResponse(
            id=team.id,
            name=team.name,
            description=team.description,
            is_public=team.is_public,
            member_count=member_count,
            created_at=team.created_at.isoformat(),
            user_role=member.role.value
        ))
    
    return teams

@router.post("/invitations")
async def send_invitation(
    invitation_data: TeamInvite,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """发送协作邀请"""
    
    # 验证权限
    if invitation_data.team_id:
        team_member = db.query(TeamMember).filter(
            TeamMember.team_id == invitation_data.team_id,
            TeamMember.user_id == current_user.id,
            TeamMember.is_active == True
        ).first()
        
        if not team_member or team_member.role not in [CollaborationRole.OWNER, CollaborationRole.ADMIN]:
            raise HTTPException(status_code=403, detail="无权限邀请成员")
    
    if invitation_data.project_id:
        project = db.query(Project).filter(
            Project.id == invitation_data.project_id,
            Project.owner_id == current_user.id
        ).first()
        
        if not project:
            raise HTTPException(status_code=403, detail="无权限邀请协作者")
    
    # 检查用户是否已存在
    invitee_user = db.query(User).filter(User.email == invitation_data.invitee_email).first()
    
    # 创建邀请
    invitation = CollaborationInvitation(
        inviter_id=current_user.id,
        invitee_email=invitation_data.invitee_email,
        invitee_id=invitee_user.id if invitee_user else None,
        project_id=invitation_data.project_id,
        team_id=invitation_data.team_id,
        role=invitation_data.role,
        message=invitation_data.message,
        permissions=invitation_data.permissions or {},
        expires_at=datetime.utcnow() + timedelta(days=7)  # 7天过期
    )
    
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    
    # 发送邀请邮件（后台任务）
    background_tasks.add_task(
        send_invitation_email,
        invitation.id,
        current_user.username,
        invitation_data.invitee_email
    )
    
    return {
        "invitation_id": invitation.id,
        "message": "邀请已发送",
        "expires_at": invitation.expires_at.isoformat()
    }

@router.get("/invitations")
async def get_user_invitations(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取用户的邀请列表"""
    
    invitations = db.query(CollaborationInvitation).filter(
        CollaborationInvitation.invitee_email == current_user.email,
        CollaborationInvitation.status == InvitationStatus.PENDING,
        CollaborationInvitation.expires_at > datetime.utcnow()
    ).order_by(CollaborationInvitation.created_at.desc()).all()
    
    invitation_list = []
    for inv in invitations:
        invitation_list.append({
            "id": inv.id,
            "inviter_name": inv.inviter.username,
            "inviter_email": inv.inviter.email,
            "project_name": inv.project.name if inv.project else None,
            "team_name": inv.team.name if inv.team else None,
            "role": inv.role.value,
            "message": inv.message,
            "created_at": inv.created_at.isoformat(),
            "expires_at": inv.expires_at.isoformat()
        })
    
    return {"invitations": invitation_list}

@router.post("/invitations/{invitation_id}/respond")
async def respond_to_invitation(
    invitation_id: int,
    accept: bool,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """响应协作邀请"""
    
    invitation = db.query(CollaborationInvitation).filter(
        CollaborationInvitation.id == invitation_id,
        CollaborationInvitation.invitee_email == current_user.email,
        CollaborationInvitation.status == InvitationStatus.PENDING
    ).first()
    
    if not invitation:
        raise HTTPException(status_code=404, detail="邀请不存在或已失效")
    
    if invitation.expires_at < datetime.utcnow():
        invitation.status = InvitationStatus.EXPIRED
        db.commit()
        raise HTTPException(status_code=400, detail="邀请已过期")
    
    if accept:
        # 接受邀请
        invitation.status = InvitationStatus.ACCEPTED
        invitation.invitee_id = current_user.id
        
        # 添加到团队或项目协作
        if invitation.team_id:
            team_member = TeamMember(
                team_id=invitation.team_id,
                user_id=current_user.id,
                role=invitation.role,
                permissions=invitation.permissions,
                invited_by=invitation.inviter_id
            )
            db.add(team_member)
        
        if invitation.project_id:
            project_collab = ProjectCollaboration(
                project_id=invitation.project_id,
                user_id=current_user.id,
                role=invitation.role,
                permissions=invitation.permissions
            )
            db.add(project_collab)
        
        message = "邀请已接受"
    else:
        # 拒绝邀请
        invitation.status = InvitationStatus.DECLINED
        message = "邀请已拒绝"
    
    invitation.responded_at = datetime.utcnow()
    db.commit()
    
    return {"message": message}

@router.post("/projects/{project_id}/comments")
async def add_project_comment(
    project_id: int,
    comment_data: CommentCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """添加项目评论"""
    
    # 验证项目访问权限
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 检查协作权限
    has_access = (
        project.owner_id == current_user.id or
        db.query(ProjectCollaboration).filter(
            ProjectCollaboration.project_id == project_id,
            ProjectCollaboration.user_id == current_user.id
        ).first() is not None
    )
    
    if not has_access:
        raise HTTPException(status_code=403, detail="无权限访问此项目")
    
    # 创建评论
    comment = CollaborationComment(
        project_id=project_id,
        content=comment_data.content,
        comment_type=comment_data.comment_type,
        author_id=current_user.id,
        parent_comment_id=comment_data.parent_comment_id
    )
    
    db.add(comment)
    db.commit()
    db.refresh(comment)
    
    # 记录活动
    activity = ActivityLog(
        user_id=current_user.id,
        project_id=project_id,
        action="commented",
        target_type="project",
        target_id=project_id,
        description=f"在项目中添加了评论"
    )
    db.add(activity)
    db.commit()
    
    return {
        "comment_id": comment.id,
        "message": "评论已添加"
    }

@router.get("/projects/{project_id}/comments")
async def get_project_comments(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取项目评论"""
    
    # 验证访问权限
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    has_access = (
        project.owner_id == current_user.id or
        db.query(ProjectCollaboration).filter(
            ProjectCollaboration.project_id == project_id,
            ProjectCollaboration.user_id == current_user.id
        ).first() is not None
    )
    
    if not has_access:
        raise HTTPException(status_code=403, detail="无权限访问此项目")
    
    # 获取评论列表
    comments = db.query(CollaborationComment).filter(
        CollaborationComment.project_id == project_id
    ).order_by(CollaborationComment.created_at.desc()).all()
    
    comment_list = []
    for comment in comments:
        comment_list.append({
            "id": comment.id,
            "content": comment.content,
            "comment_type": comment.comment_type,
            "author": {
                "id": comment.author.id,
                "username": comment.author.username,
                "full_name": comment.author.full_name
            },
            "parent_comment_id": comment.parent_comment_id,
            "is_resolved": comment.is_resolved,
            "is_pinned": comment.is_pinned,
            "created_at": comment.created_at.isoformat(),
            "updated_at": comment.updated_at.isoformat() if comment.updated_at else None
        })
    
    return {"comments": comment_list}

@router.get("/projects/{project_id}/collaborators")
async def get_project_collaborators(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取项目协作者列表"""
    
    # 验证项目所有权
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限")
    
    # 获取协作者
    collaborations = db.query(ProjectCollaboration).filter(
        ProjectCollaboration.project_id == project_id
    ).all()
    
    collaborator_list = []
    for collab in collaborations:
        collaborator_list.append({
            "user_id": collab.user.id,
            "username": collab.user.username,
            "full_name": collab.user.full_name,
            "email": collab.user.email,
            "role": collab.role.value,
            "permissions": collab.permissions,
            "joined_at": collab.created_at.isoformat()
        })
    
    return {"collaborators": collaborator_list}

@router.get("/projects/{project_id}/activity")
async def get_project_activity(
    project_id: int,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取项目活动日志"""
    
    # 验证访问权限
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    has_access = (
        project.owner_id == current_user.id or
        db.query(ProjectCollaboration).filter(
            ProjectCollaboration.project_id == project_id,
            ProjectCollaboration.user_id == current_user.id
        ).first() is not None
    )
    
    if not has_access:
        raise HTTPException(status_code=403, detail="无权限访问此项目")
    
    # 获取活动日志
    activities = db.query(ActivityLog).filter(
        ActivityLog.project_id == project_id
    ).order_by(ActivityLog.created_at.desc()).limit(limit).all()
    
    activity_list = []
    for activity in activities:
        activity_list.append({
            "id": activity.id,
            "user": {
                "username": activity.user.username,
                "full_name": activity.user.full_name
            },
            "action": activity.action,
            "target_type": activity.target_type,
            "target_id": activity.target_id,
            "description": activity.description,
            "metadata": activity.metadata,
            "created_at": activity.created_at.isoformat()
        })
    
    return {"activities": activity_list}

async def send_invitation_email(
    invitation_id: int,
    inviter_name: str,
    invitee_email: str
):
    """发送邀请邮件（后台任务）"""
    try:
        notification_service = NotificationService()
        
        # 构建邀请邮件内容
        subject = f"{inviter_name} 邀请您加入科研项目协作"
        content = f"""
您好！

{inviter_name} 邀请您加入科研文献智能分析平台的项目协作。

请点击以下链接接受邀请：
https://research-platform.com/invitations/{invitation_id}

如果您还没有账户，系统将引导您完成注册。

此邀请将在7天后过期。

科研文献智能分析平台团队
"""
        
        await notification_service.send_email(
            to_email=invitee_email,
            subject=subject,
            content=content
        )
        
        print(f"邀请邮件已发送到: {invitee_email}")
        
    except Exception as e:
        print(f"发送邀请邮件失败: {e}")

@router.delete("/teams/{team_id}/members/{user_id}")
async def remove_team_member(
    team_id: int,
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """移除团队成员"""
    
    # 验证权限
    team_member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == current_user.id,
        TeamMember.is_active == True
    ).first()
    
    if not team_member or team_member.role not in [CollaborationRole.OWNER, CollaborationRole.ADMIN]:
        raise HTTPException(status_code=403, detail="无权限移除成员")
    
    # 不能移除团队所有者
    target_member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == user_id,
        TeamMember.is_active == True
    ).first()
    
    if not target_member:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    if target_member.role == CollaborationRole.OWNER:
        raise HTTPException(status_code=400, detail="不能移除团队所有者")
    
    # 移除成员
    target_member.is_active = False
    db.commit()
    
    # 记录活动
    activity = ActivityLog(
        user_id=current_user.id,
        team_id=team_id,
        action="removed_member",
        target_type="team_member",
        target_id=user_id,
        description=f"移除了团队成员: {target_member.user.username}"
    )
    db.add(activity)
    db.commit()
    
    return {"message": "成员已移除"}