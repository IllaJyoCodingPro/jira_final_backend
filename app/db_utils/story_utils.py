from datetime import datetime
from typing import Optional, List, Any, Dict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.models import UserStory, Project, User, Team
from app.constants import ErrorMessages, ADMIN, DEVELOPER
from app.enums import IssueType, StoryAction, StoryStatus
from app.exceptions import (
    raise_bad_request, raise_forbidden, raise_internal_error, 
    raise_not_found, raise_story_not_found, raise_circular_dependency
)
from app.utils.common import get_object_or_404, check_project_active
from app.utils.notification_service import create_notification, notify_issue_assigned
from app.auth.permissions import can_create_issue, can_update_issue, can_view_issue

# --- Validation Helpers ---
def validate_hierarchy(db: Session, parent_id: Optional[int], issue_type: str, current_issue_id: Optional[int] = None):
    if not parent_id:
        if issue_type == IssueType.SUBTASK.value:
            raise_bad_request("Subtask must belong to a Task (parent_issue_id required).")
        return

    parent_story = db.query(UserStory).filter(UserStory.id == parent_id).first()
    if not parent_story:
        raise_bad_request("Parent issue not found")
    
    if current_issue_id:
        if parent_id == current_issue_id:
            raise_bad_request("Cannot set issue as its own parent.")
        
        ancestor = parent_story
        depth = 0
        while ancestor.parent_issue_id and depth < 50:
            if ancestor.parent_issue_id == current_issue_id:
                raise_circular_dependency()
            ancestor = ancestor.parent 
            if not ancestor:
                break
            depth += 1
            
    ptype = parent_story.issue_type
    
    if issue_type == IssueType.EPIC.value:
        raise_bad_request("Epics cannot have a parent issue.")
    
    if issue_type == IssueType.STORY.value and ptype != IssueType.EPIC.value:
        raise_bad_request(f"Story must be a child of an Epic, not {ptype}.")
        
    if issue_type == IssueType.TASK.value and ptype != IssueType.STORY.value:
        raise_bad_request(f"Task must be a child of a Story, not {ptype}.")
        
    if issue_type == IssueType.SUBTASK.value and ptype != IssueType.TASK.value:
        raise_bad_request(f"Subtask must be a child of a Task, not {ptype}.")
        
    if issue_type == IssueType.BUG.value and ptype not in [IssueType.STORY.value, IssueType.TASK.value]:
        raise_bad_request(f"Bug must be a child of a Story or Task, not {ptype}.")

def validate_status_transition(story: UserStory, new_status: str):
    if not new_status or new_status == story.status:
        return

    if new_status.lower() == StoryStatus.DONE.value.lower():
         pending_children = [
             child for child in story.children 
             if (child.status or "").lower() != StoryStatus.DONE.value.lower()
         ]
         if pending_children:
             raise_bad_request(f"Cannot mark as Done: Child issues are not Done ({len(pending_children)} pending).")

# --- Log Helpers ---
def _log_activity(db: Session, story_id: int, user_id: Optional[int], action: str, changes_dict: dict):
    if not changes_dict and action == StoryAction.UPDATED.value:
        return

    change_lines = []
    if action == StoryAction.CREATED.value:
        change_lines.append("Issue Created")
    
    for field, vals in changes_dict.items():
        change_lines.append(f"{field}: {vals['old']} → {vals['new']}")
        
    changes_text = "\n".join(change_lines)
    
    from app.models import UserStoryActivity
    
    activity = UserStoryActivity(
        story_id=story_id,
        user_id=user_id,
        action=action,
        changes=changes_text,
        change_count=len(changes_dict)
    )
    db.add(activity)

def _generate_story_code(db: Session, project_id: int) -> str:
    project = get_object_or_404(db, Project, project_id, ErrorMessages.PROJECT_NOT_FOUND)
    prefix_val = project.project_prefix if project.project_prefix else (project.name[:2].upper() if project.name else "XX")
    
    # Get Max
    stories = db.query(UserStory).filter(UserStory.story_pointer.like(f"{prefix_val}-%")).all()
    max_num = 0
    for s in stories:
        val = s.story_pointer
        if val:
            try:
                num = int(val.split('-')[-1])
                if num > max_num:
                    max_num = num
            except (ValueError, IndexError):
                continue
    next_num = max_num + 1
    return f"{prefix_val}-{next_num:04d}"

# --- DB/Service Functions ---

def get_story_by_id(db: Session, story_id: int) -> Optional[UserStory]:
    return db.query(UserStory).filter(UserStory.id == story_id).first()

def get_user_story_activities(db: Session, story_id: int) -> List[Any]:
    from app.models import UserStoryActivity
    return db.query(UserStoryActivity).filter(UserStoryActivity.story_id == story_id).order_by(UserStoryActivity.created_at.desc()).all()

def create_story(db: Session, user: User, data: dict, file_path: Optional[str] = None) -> UserStory:
    project_id = data.get('project_id')
    assignee_id = data.get('assignee_id')
    team_id = data.get('team_id')
    assignee_name = data.get('assignee_name')
    
    # Assignee Logic
    final_assignee_id = assignee_id
    final_assignee_name = assignee_name

    if user.role == DEVELOPER:
        is_team_lead = False
        if team_id:
             if any(t.id == team_id for t in user.led_teams):
                is_team_lead = True
        
        is_project_lead = any(t.project_id == project_id for t in user.led_teams)

        if is_team_lead or is_project_lead:
             if final_assignee_id:
                 target_user = get_object_or_404(db, User, final_assignee_id, ErrorMessages.USER_NOT_FOUND)
                 final_assignee_name = target_user.username
             else:
                 if not final_assignee_name or not final_assignee_name.strip():
                     final_assignee_name = "Unassigned"
        else:
             final_assignee_id = user.id
             final_assignee_name = user.username
    else:
        if final_assignee_id:
            target_user = get_object_or_404(db, User, final_assignee_id, ErrorMessages.USER_NOT_FOUND)
            final_assignee_name = target_user.username
        else:
            if not final_assignee_name or not final_assignee_name.strip():
                final_assignee_name = "Unassigned"

    project = get_object_or_404(db, Project, project_id, ErrorMessages.PROJECT_NOT_FOUND)
    check_project_active(project.is_active)

    if not can_create_issue(user, project_id, team_id, db):
        is_owner = project.owner_id == user.id
        if user.view_mode == DEVELOPER and is_owner:
            msg = "Project owners must switch to Admin mode to create issues in their own projects."
        elif user.view_mode == ADMIN and not is_owner:
            msg = "In Admin mode, you can only create issues in projects you own."
        else:
            msg = ErrorMessages.NO_PERMISSION_CREATE
        raise_forbidden(msg)

    validate_hierarchy(db, data.get('parent_issue_id'), data.get('issue_type'))
    
    try:
        story_code = _generate_story_code(db, project_id)
    except ValueError as e:
        raise_bad_request(str(e))

    if final_assignee_id and team_id:
        team = get_object_or_404(db, Team, team_id, ErrorMessages.TEAM_NOT_FOUND)
        member_ids = [m.id for m in (team.members or [])]
        if final_assignee_id not in member_ids:
            target_user = get_object_or_404(db, User, final_assignee_id, ErrorMessages.USER_NOT_FOUND)
            team.members.append(target_user)
            db.add(team)
            db.flush()

    new_story = UserStory(
        project_id=project_id,
        release_number=data.get('release_number'),
        sprint_number=data.get('sprint_number'),
        story_pointer=story_code,
        assignee=final_assignee_name,
        assignee_id=final_assignee_id,
        reviewer=data.get('reviewer'),
        title=data.get('title'),
        description=data.get('description'),
        issue_type=data.get('issue_type'),
        priority=data.get('priority'),
        status=data.get('status'),
        support_doc=file_path,
        start_date=data.get('start_date'),
        end_date=data.get('end_date'),
        team_id=team_id,
        parent_issue_id=data.get('parent_issue_id'),
        created_by=user.id,
        project_name=project.name
    )
    
    db.add(new_story)
    db.flush()
    db.refresh(new_story)
    
    _log_activity(db, new_story.id, user.id, StoryAction.CREATED.value, {"Status": {"old": "None", "new": data.get('status')}})
    
    if new_story.assignee_id:
        notify_issue_assigned(db, new_story.assignee_id, new_story.title)
        
    db.commit()
    db.refresh(new_story)
    return new_story

def update_story(db: Session, user: User, story_id: int, updates: dict) -> UserStory:
    story = get_object_or_404(db, UserStory, story_id, ErrorMessages.STORY_NOT_FOUND)
    check_project_active(story.project.is_active)
    
    if not can_update_issue(user, story, db):
        raise_forbidden(ErrorMessages.NO_PERMISSION_EDIT)

    if user.role == DEVELOPER:
        if 'assignee' in updates: del updates['assignee']
        if 'assignee_id' in updates: del updates['assignee_id']

    changes = {}
    
    if 'parent_issue_id' in updates:
        new_parent_id = updates['parent_issue_id']
        if new_parent_id != story.parent_issue_id:
            try:
                validate_hierarchy(db, new_parent_id, story.issue_type, current_issue_id=story.id)
            except Exception as e:
                raise_bad_request(f"{ErrorMessages.INVALID_PARENT}: {str(e)}")
            changes["parent_issue_id"] = {"old": str(story.parent_issue_id), "new": str(new_parent_id)}
            
    if 'status' in updates and updates['status'] != story.status:
        validate_status_transition(story, updates['status'])
        
    for field, new_val in updates.items():
        if field == "parent_issue_id" and field in changes: 
             setattr(story, field, new_val)
             continue
             
        old_val = getattr(story, field, None)
        str_old = str(old_val) if old_val is not None else ""
        str_new = str(new_val) if new_val is not None else ""
        
        if str_old != str_new:
            changes[field] = {"old": str_old, "new": str_new}
            setattr(story, field, new_val)
            
            if field == "assignee_id":
                 assignee_user = db.query(User).filter(User.id == new_val).first()
                 story.assignee = assignee_user.username if assignee_user else "Unknown"
                 if new_val:
                     notify_issue_assigned(db, new_val, story.title)
                     
            if field == "status" and story.assignee_id:
                create_notification(db, story.assignee_id, "Status Updated", f"Story '{story.title}' is now {new_val}")
            
            if field == "priority" and story.assignee_id:
                create_notification(db, story.assignee_id, "Priority Updated", f"Priority for '{story.title}' changed to {new_val}")

    db.add(story)
    
    _log_activity(db, story.id, user.id, StoryAction.UPDATED.value, changes)
    
    db.commit()
    db.refresh(story)
    return story

def delete_story(db: Session, story: UserStory):
    db.delete(story)
    db.commit()

def search_stories(db: Session, user: User, query_str: str) -> List[UserStory]:
    base_query = db.query(UserStory).filter(
        or_(
            UserStory.title.ilike(f"%{query_str}%"),
            UserStory.story_pointer.ilike(f"%{query_str}%"),
        )
    )
    
    if user.role != ADMIN:
        led_ids = [t.project_id for t in user.led_teams]
        member_team_ids = [t.id for t in user.teams]
        assigned_project_ids = [pid[0] for pid in db.query(UserStory.project_id).filter(UserStory.assignee_id == user.id).distinct().all()]
        
        base_query = base_query.filter(
            or_(
                UserStory.assignee_id == user.id,
                UserStory.team_id.in_(member_team_ids),
                UserStory.project_id.in_(led_ids),
                UserStory.project_id.in_(assigned_project_ids)
            )
        )
    return base_query.limit(50).all()

def find_potential_parents(db: Session, project_id: int, target_types: List[str], exclude_id: Optional[int] = None) -> List[UserStory]:
    query = db.query(UserStory).filter(
        UserStory.project_id == project_id,
        UserStory.issue_type.in_(target_types)
    )
    if exclude_id:
        query = query.filter(UserStory.id != exclude_id)
    return query.all()

def get_available_parents(db: Session, user: User, project_id: int, issue_type: str, exclude_id: Optional[int]) -> List[UserStory]:
    project = get_object_or_404(db, Project, project_id, ErrorMessages.PROJECT_NOT_FOUND)
    is_owner = project.owner_id == user.id
    
    if not user.is_master_admin:
        if user.view_mode == ADMIN and not is_owner:
            raise_forbidden()
        elif user.view_mode == DEVELOPER and is_owner:
            raise_forbidden()
            
    target_type = None
    if issue_type == IssueType.STORY.value: target_type = IssueType.EPIC.value
    elif issue_type == IssueType.TASK.value: target_type = IssueType.STORY.value
    elif issue_type == IssueType.SUBTASK.value: target_type = IssueType.TASK.value
    elif issue_type == IssueType.BUG.value:
         return find_potential_parents(db, project_id, [IssueType.STORY.value, IssueType.TASK.value], exclude_id)
         
    if not target_type: return []
    
    return find_potential_parents(db, project_id, [target_type], exclude_id)

def get_epics(db: Session, user: User) -> List[UserStory]:
    query = db.query(UserStory).join(Project).filter(UserStory.issue_type == IssueType.EPIC.value)
    
    if not user.is_master_admin:
        member_project_ids = db.query(Team.project_id).filter(
            Team.members.any(id=user.id)
        ).subquery()
        
        query = query.filter(
            or_(
                Project.owner_id == user.id,
                Project.id.in_(member_project_ids)
            )
        )
    return query.all()

def get_my_assigned_stories(db: Session, user: User) -> List[UserStory]:
    if user.is_master_admin:
         return db.query(UserStory).options(joinedload(UserStory.team), joinedload(UserStory.project))\
            .filter(UserStory.assignee_id == user.id).all()
        
    owned_project_ids = [p.id for p in db.query(Project).filter(Project.owner_id == user.id).all()]
    
    if user.view_mode == ADMIN:
        if not owned_project_ids: return []
        return db.query(UserStory).options(joinedload(UserStory.team), joinedload(UserStory.project))\
               .filter(UserStory.assignee_id == user.id, UserStory.project_id.in_(owned_project_ids)).all()
    else:
        if owned_project_ids:
             return db.query(UserStory).options(joinedload(UserStory.team), joinedload(UserStory.project))\
               .filter(UserStory.assignee_id == user.id, UserStory.project_id.notin_(owned_project_ids)).all()
        else:
             return db.query(UserStory).options(joinedload(UserStory.team), joinedload(UserStory.project))\
               .filter(UserStory.assignee_id == user.id).all()

def get_stories_by_project(db: Session, project_id: int) -> List[UserStory]:
    return db.query(UserStory)\
        .options(joinedload(UserStory.team), joinedload(UserStory.project))\
        .filter(UserStory.project_id == project_id).all()
