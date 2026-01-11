from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models import User, UserStory, Team, Project

def check_issue_permission(user: User, resource, action: str, db: Session = None):
    """
    Centralized permission check logic for issues.
    
    Args:
        user: The user requesting access
        resource: instance of UserStory (or None for creation checks)
        action: "create", "read", "update", "delete"
        db: Optional database session
        
    Returns:
        bool: True if permitted, otherwise raises HTTPException
        
    Raises:
        HTTPException: If permission denied
    """
    if user.role == "ADMIN":
        return True # Admin has all permissions (except maybe super specific ones, but here All)

    # Context Mapping
    # Resource is usually a UserStory or Project. 
    
    if isinstance(resource, UserStory):
        return check_issue_permission(user, resource, action, db)
    
    # Check for Creation (resource might be a dict/object with target context)
    if action == "create_issue":
        # We need project_id and team_id from the request to validate
        # This is harder to genericize without context.
        # We will handle create logic in the route or specific helper.
        pass

    raise HTTPException(status_code=403, detail="Permission denied")

def can_create_issue(user: User, project_id: int, team_id: int, db: Session):
    """
    Checks if a user can create an issue in a project/team.
    
    Args:
        user: The user
        project_id: Target project ID
        team_id: Target team ID
        db: Database session
        
    Returns:
        bool: True if allowed
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project or not project.is_active:
        return False

    # Master admin can always create issues
    if user.is_master_admin:
        return True
    
    # Check ownership
    is_owner = project.owner_id == user.id

    # ADMIN View Mode: Only Owner can create
    if user.view_mode == "ADMIN":
        return is_owner
    
    # DEVELOPER View Mode:
    # 1. Owner cannot create in Developer mode (must switch to Admin? Or allow? 
    #    Strict view mode implies isolation. Let's enforce switching to Admin for Owners).
    if is_owner:
        return False
        
    # 2. Team Leads/Members can create if they belong to the project
    # Check if user is in any team of this project
    is_member = (
        db.query(Team)
        .filter(Team.project_id == project_id)
        .filter(or_(Team.lead_id == user.id, Team.id.in_([t.id for t in user.teams])))
        .count() > 0
    )
    
    if is_member:
        return True
        
    return False

def can_update_issue(user: User, story: UserStory, db: Session):
    """
    Checks if a user can update a specific issue.
    Respects view_mode: Users can only update in ADMIN mode if they own the project.
    Team leads can update issues assigned to their team members within their project.
    
    Args:
        user: The user
        story: The user story to update
        db: Database session
        
    Returns:
        bool: True if allowed
    """
    if not story.project.is_active:
        return False

    # Master admin can always update
    if user.is_master_admin:
        return True
    
    # Check project ownership
    is_owner = story.project.owner_id == user.id
    
    # In ADMIN mode: can only update issues in projects you own
    if user.view_mode == "ADMIN":
        return is_owner
    
    # In DEVELOPER mode: cannot update issues in projects you own
    if is_owner:
        return False
    
    # ✅ Team lead can update issues for their team members in their project (regardless of role)
    if story.team_id:
        team = db.query(Team).filter(Team.id == story.team_id).first()
        if team and team.lead_id == user.id and team.project_id == story.project_id:
            # User is the team lead for this issue's team in the same project
            return True
        
    # Developer mode: Can update if you're the assignee
    if story.assignee_id == user.id:
        return True
        
    return False

def can_delete_issue(user: User, story: UserStory, db: Session):
    """
    Checks if a user can delete a specific issue.
    Project owners in ADMIN mode, team leads for their team's issues, or master admin can delete.
    
    Args:
        user: The user
        story: The user story to delete
        db: Database session
        
    Returns:
        bool: True if allowed
    """
    if not story.project.is_active:
        return False

    # Master admin can always delete
    if user.is_master_admin:
        return True
    
    # Only project owners in ADMIN mode can delete issues
    is_owner = story.project.owner_id == user.id
    if user.view_mode == "ADMIN" and is_owner:
        return True
    
    # ✅ Team lead can delete issues for their team members in their project (regardless of role)
    if story.team_id:
        team = db.query(Team).filter(Team.id == story.team_id).first()
        if team and team.lead_id == user.id and team.project_id == story.project_id:
            # User is the team lead for this issue's team in the same project
            return True
            
    return False

def can_view_issue(user: User, story: UserStory, db: Session):
    """
    Checks if a user can view a specific issue.
    Respects view_mode: Admin mode shows owned projects, Developer mode shows assigned work.
    
    Args:
        user: The user
        story: The user story to view
        db: Database session
        
    Returns:
        bool: True if allowed
    """
    # Master admin sees everything
    if user.is_master_admin:
        return True
    
    is_owner = story.project.owner_id == user.id
    
    # ADMIN view mode: Only see issues in projects you own
    if user.view_mode == "ADMIN":
        return is_owner
    
    # DEVELOPER view mode: Don't see issues from projects you own
    if is_owner:
        return False
        
    # Check if user leads ANY team in this project
    is_team_lead_in_project = (
        db.query(Team)
        .filter(Team.project_id == story.project_id, Team.lead_id == user.id)
        .count() > 0
    )
    if is_team_lead_in_project:
        return True
        
    # Team Member - view issues assigned to their team
    if story.team_id:
        team = db.query(Team).filter(Team.id == story.team_id).first()
        if team and user in team.members:
            return True
    
    # Directly assigned
    if story.assignee_id == user.id:
        return True

    # Assigned to ANY issue in the project
    is_assigned_in_project = (
        db.query(UserStory)
        .filter(UserStory.project_id == story.project_id, UserStory.assignee_id == user.id)
        .count() > 0
    )
    if is_assigned_in_project:
        return True
        
    return False

def is_admin(user: User):
    """
    Simple check if user is an ADMIN role.
    """
    return user.role == "ADMIN"

def is_project_lead(user: User, project_id: int, db: Session):
    """
    Checks if user is a lead in a specific project.
    ✅ UPDATED: No longer checks role - only checks actual team leadership or project ownership.
    """
    # Check if user owns the project
    project = db.query(Project).filter(Project.id == project_id).first()
    if project and project.owner_id == user.id:
        return True
        
    # Check if user leads at least ONE team in this project (regardless of role)
    return db.query(Team).filter(Team.project_id == project_id, Team.lead_id == user.id).count() > 0

def can_manage_team_members(user: User, team: Team, db: Session):
    """
    Checks if user can manage members of a team.
    ✅ UPDATED: Allows team leads to manage their team regardless of role.
    """
    # Master admin can always manage
    if user.is_master_admin:
        return True
    
    # ADMIN role users can manage any team
    if user.role == "ADMIN":
        return True
    
    # Team lead can manage their own team (regardless of role)
    if team.lead_id == user.id:
        return True
    
    # Project leaders can manage teams in their project
    return is_project_lead(user, team.project_id, db)