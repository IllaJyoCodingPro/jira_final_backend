import os
import shutil
from typing import Optional, List, Union
from datetime import datetime, date

from fastapi import APIRouter, Depends, Form, UploadFile, File
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models import User
from app.auth.dependencies import get_current_user
from app.auth.permissions import can_create_issue, can_update_issue, can_view_issue
from app.utils.activity_logger import log_activity
from app.utils.notification_service import create_notification, notify_issue_assigned
from app.utils.utils import story_to_dict, track_change
from app.config.settings import settings
from app.enums import IssueType, StoryAction, StoryStatus, Priority
from app.constants import ErrorMessages, SuccessMessages
from app.utils.common import get_object_or_404, check_project_active
from app.schemas.story_schema import UserStoryActivityResponse

from sqlalchemy.exc import SQLAlchemyError
from app.utils import story_service as story_utils

router = APIRouter(prefix="/user-stories", tags=["user-stories"])





@router.get("/types", response_model=List[str])
def get_issue_types(user: User = Depends(get_current_user)):
    return [t.value for t in IssueType]

@router.get("/search")
def search_stories(
    q: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    results = story_utils.search_stories(db, user, q)
    return [story_to_dict(s) for s in results]

@router.get("/available-parents")
def get_available_parents(
    project_id: int,
    issue_type: str,
    exclude_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    results = story_utils.get_available_parents(db, user, project_id, issue_type, exclude_id)
    return [{"id": s.id, "title": s.title, "story_code": s.story_pointer} for s in results]

@router.get("/epics/all", response_model=List[dict])
def get_all_epics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    epics = story_utils.get_epics(db, user)
    return [{
        "id": e.id, 
        "title": e.title, 
        "story_code": e.story_pointer, 
        "project_id": e.project_id,
        "project_name": e.project_name
    } for e in epics]

@router.post("")
def create_user_story(
    project_id: int = Form(...),
    release_number: Optional[str] = Form(None),
    sprint_number: Optional[str] = Form(None),
    assignee: str = Form(...),
    assignee_id: Optional[str] = Form(None),
    assigned_to: Optional[str] = Form(None),
    reviewer: Optional[str] = Form(None),
    title: str = Form(...),
    description: str = Form(...),
    issue_type: Optional[IssueType] = Form(None),
    priority: Optional[str] = Form(None),
    status: str = Form(...),
    support_doc: Optional[Union[UploadFile, str]] = File(None), 
    start_date: Optional[date] = Form(None),
    end_date: Optional[date] = Form(None),
    team_id: Optional[str] = Form(None),
    parent_issue_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    def parse_optional_int(val):
        if val is None: return None
        if not val or (isinstance(val, str) and not val.strip()): return None
        try: return int(val)
        except: return None

    p_assignee_id = parse_optional_int(assigned_to) if assigned_to is not None else parse_optional_int(assignee_id)
    p_team_id = parse_optional_int(team_id)
    p_parent_id = parse_optional_int(parent_issue_id)
    
    file_path = None
    if isinstance(support_doc, UploadFile):
        UPLOAD_DIR = "uploads"
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        file_path = f"{UPLOAD_DIR}/{support_doc.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(support_doc.file, buffer)

    data = {
        "project_id": project_id,
        "release_number": release_number,
        "sprint_number": sprint_number,
        "assignee_id": p_assignee_id,
        "assignee_name": assignee,
        "reviewer": reviewer,
        "title": title,
        "description": description,
        "issue_type": issue_type.value if issue_type else None,
        "priority": priority,
        "status": status,
        "start_date": start_date,
        "end_date": end_date,
        "team_id": p_team_id,
        "parent_issue_id": p_parent_id
    }

    new_story = story_utils.create_story(db, user, data, file_path)
    return story_to_dict(new_story)

@router.get("/{id}/history", response_model=List[UserStoryActivityResponse])
def get_story_history(id: int, db: Session = Depends(get_db)):
    """
    Retrieves the activity history of a story.
    """
    from app.models.user_story_activity import UserStoryActivity
    return db.query(UserStoryActivity).filter(UserStoryActivity.story_id == id).order_by(UserStoryActivity.created_at.desc()).all()


@router.get("/{id}")
def get_story_by_id(
    id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    story = story_utils.get_story_by_id(db, id)
    if not story:
        raise_story_not_found()
    
    if not can_view_issue(user, story, db):
        raise_forbidden()
        
    return story_to_dict(story)

@router.put("/{id}")
def update_story(
    id: int,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    sprint_number: Optional[str] = Form(None),
    assignee: Optional[str] = Form(None),
    assignee_id: Optional[str] = Form(None),
    reviewer: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    parent_issue_id: Optional[str] = Form(None),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    priority: Optional[str] = Form(None),
    issue_type: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    def clean_str(val):
        if val == "" or val == "null" or val == "undefined": return None
        return val
        
    def clean_int(val):
        if not val: return None
        try: return int(val)
        except: return None
    
    def parse_date_str(dstr):
        if not dstr: return None
        return dstr[:10]

    updates = {}
    if title is not None: updates['title'] = title
    if description is not None: updates['description'] = description
    if sprint_number is not None: updates['sprint_number'] = clean_str(sprint_number)
    if assignee is not None: updates['assignee'] = assignee
    if assignee_id is not None: updates['assignee_id'] = clean_int(assignee_id)
    if reviewer is not None: updates['reviewer'] = clean_str(reviewer)
    if status is not None: updates['status'] = status
    if parent_issue_id is not None: updates['parent_issue_id'] = clean_int(parent_issue_id)
    if priority is not None: updates['priority'] = priority
    if issue_type is not None: updates['issue_type'] = issue_type
    
    if start_date is not None:
         dval = parse_date_str(start_date)
         updates['start_date'] = datetime.strptime(dval, "%Y-%m-%d").date() if dval else None
    if end_date is not None:
         dval = parse_date_str(end_date)
         updates['end_date'] = datetime.strptime(dval, "%Y-%m-%d").date() if dval else None

    updated_story = story_utils.update_story(db, user, id, updates)
    return story_to_dict(updated_story)

@router.get("/{id}/activity")
def get_story_activity(
    id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    story = story_utils.get_story_by_id(db, id)
    if not story: raise_story_not_found()
    
    if not can_view_issue(user, story, db):
        raise_forbidden()
    
    from app.models.user_story_activity import UserStoryActivity
    activities = db.query(UserStoryActivity).filter(UserStoryActivity.story_id == id).order_by(UserStoryActivity.created_at.desc()).all()
    
    result = []
    for act in activities:
        u = db.query(User).filter(User.id == act.user_id).first() if act.user_id else None
        result.append({
            "id": act.id,
            "story_id": act.story_id,
            "user_id": act.user_id,
            "username": u.username if u else "System", 
            "action": act.action,
            "changes": act.changes,
            "created_at": act.created_at
        })
    return result

@router.get("/assigned/me")
def get_my_assigned_stories(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    stories = story_utils.get_my_assigned_stories(db, user)
    return [story_to_dict(s) for s in stories]

@router.delete("/{id}")
def delete_user_story(
    id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    story = story_utils.get_story_by_id(db, id)
    if not story: raise_story_not_found()
    
    check_project_active(story.project.is_active)
    
    story_utils.delete_story(db, story)
    return {"message": SuccessMessages.STORY_DELETED}

@router.get("/project/{project_id}")
def get_stories_by_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    stories = story_utils.get_stories_by_project(db, project_id)
    return [story_to_dict(s) for s in stories]
