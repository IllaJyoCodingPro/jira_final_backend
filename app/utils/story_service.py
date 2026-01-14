from typing import List, Optional, Any, Dict
from sqlalchemy.orm import Session
from datetime import datetime

from app.models import User, UserStory, Project, Team
from app.enums import IssueType, StoryAction, StoryStatus
from app.constants import ErrorMessages, ADMIN, DEVELOPER
from app.exceptions import raise_forbidden, raise_bad_request
from app.utils.common import get_object_or_404, check_project_active
from app.utils.notification_service import create_notification, notify_issue_assigned
from app.auth.permissions import can_create_issue, can_update_issue, can_view_issue

# Internal modules
from app.utils import story_repo
from app.utils import story_validation

def get_story_by_id(db: Session, story_id: int) -> Optional[UserStory]:
    return story_repo.get_story_by_id(db, story_id)

def get_user_story_activities(db: Session, story_id: int) -> List[Any]:
    return story_repo.get_user_story_activities(db, story_id)

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

    story_validation.validate_hierarchy(db, data.get('parent_issue_id'), data.get('issue_type'))
    
    try:
        story_code = story_repo.get_next_story_code(db, project_id)
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

    # Prepare data for repo
    create_data = {
        "project_id": project_id,
        "release_number": data.get('release_number'),
        "sprint_number": data.get('sprint_number'),
        "story_pointer": story_code,
        "assignee": final_assignee_name,
        "assignee_id": final_assignee_id,
        "reviewer": data.get('reviewer'),
        "title": data.get('title'),
        "description": data.get('description'),
        "issue_type": data.get('issue_type'),
        "priority": data.get('priority'),
        "status": data.get('status'),
        "support_doc": file_path,
        "start_date": data.get('start_date'),
        "end_date": data.get('end_date'),
        "team_id": team_id,
        "parent_issue_id": data.get('parent_issue_id'),
        "created_by": user.id,

    }
    
    new_story = story_repo.create_story_record(db, create_data)
    
    # Activity & Notification
    story_repo.create_activity(db, new_story.id, user.id, StoryAction.CREATED.value, {"Status": {"old": "None", "new": data.get('status')}})
    
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
                story_validation.validate_hierarchy(db, new_parent_id, story.issue_type, current_issue_id=story.id)
            except Exception as e:
                raise_bad_request(f"{ErrorMessages.INVALID_PARENT}: {str(e)}")
            changes["parent_issue_id"] = {"old": str(story.parent_issue_id), "new": str(new_parent_id)}
            
    if 'status' in updates and updates['status'] != story.status:
        story_validation.validate_status_transition(story, updates['status'])
        
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

    updated_story = story_repo.update_story_record(db, story)
    
    story_repo.create_activity(db, story.id, user.id, StoryAction.UPDATED.value, changes)
    
    db.commit()
    db.refresh(story)
    return story

def delete_story(db: Session, story: UserStory):
    story_repo.delete_story_record(db, story)
    db.commit()

def search_stories(db: Session, user: User, query_str: str) -> List[UserStory]:
    if user.role == ADMIN:
        return story_repo.search_stories_db(db, query_str, apply_filters=False)
    
    # Logic for non-admin
    led_ids = [t.project_id for t in user.led_teams]
    member_team_ids = [t.id for t in user.teams]
    assigned_project_ids = story_repo.get_distinct_project_ids_for_assignee(db, user.id)
    
    # We need to construct the filter logic.
    # Original: OR(assignee_id==uid, team_id IN member_team_ids, project_id IN led_ids, project_id IN assigned_project_ids)
    # Repo search_stories_db has AND logic for filters? No, the filters in repo need to support OR.
    # Current repo `search_stories_db` implementation:
    # `if criteria: base_query = base_query.filter(or_(*criteria))`
    # So if we pass all criteria, they are OR'ed. Perfect.
    
    return story_repo.search_stories_db(
        db, 
        query_str, 
        filter_assignee_id=user.id,
        filter_team_ids=member_team_ids,
        filter_project_ids=led_ids + assigned_project_ids, # Combined list of allowed projects
        apply_filters=True
    )
    # Wait, `filter_project_ids` checks `project_id`. Original checked `project_id IN led_ids OR project_id IN assigned_project_ids`.
    # Merging them works.

def find_potential_parents(db: Session, project_id: int, target_types: List[str], exclude_id: Optional[int] = None) -> List[UserStory]:
    return story_repo.find_potential_parents_db(db, project_id, target_types, exclude_id)

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
    if user.is_master_admin:
        return story_repo.get_epics_db(db)
    
    # Logic: Owner OR Member
    owned_ids = [p.id for p in db.query(Project).filter(Project.owner_id == user.id).all()]
    
    # Repo function `get_epics_accessible_by_user` handles the complex logic
    return story_repo.get_epics_accessible_by_user(db, user.id, owned_ids)

def get_my_assigned_stories(db: Session, user: User) -> List[UserStory]:
    if user.is_master_admin:
         return story_repo.get_assigned_stories_db(db, user.id)
        
    owned_project_ids = [p.id for p in db.query(Project).filter(Project.owner_id == user.id).all()]
    
    if user.view_mode == ADMIN:
        if not owned_project_ids: return []
        return story_repo.get_assigned_stories_db(db, user.id, project_ids_in=owned_project_ids)
    else:
        if owned_project_ids:
             return story_repo.get_assigned_stories_db(db, user.id, project_ids_not_in=owned_project_ids)
        else:
             return story_repo.get_assigned_stories_db(db, user.id)

def get_stories_by_project(db: Session, project_id: int) -> List[UserStory]:
    return story_repo.get_stories_by_project_db(db, project_id)
