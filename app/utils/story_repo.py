from typing import List, Optional, Any, Dict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.models import UserStory, Project, Team, UserStoryActivity
from app.enums import IssueType
from app.constants import ErrorMessages
from app.utils.common import get_object_or_404

def get_next_story_code(db: Session, project_id: int) -> str:
    project = get_object_or_404(db, Project, project_id, ErrorMessages.PROJECT_NOT_FOUND)
    prefix_val = project.project_prefix if project.project_prefix else (project.name[:2].upper() if project.name else "XX")
    
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

def get_story_by_id_db(db: Session, story_id: int) -> Optional[UserStory]:
    return db.query(UserStory).options(joinedload(UserStory.project)).filter(UserStory.id == story_id).first()

def get_user_story_activities_db(db: Session, story_id: int) -> List[UserStoryActivity]:
    return db.query(UserStoryActivity).filter(UserStoryActivity.story_id == story_id).order_by(UserStoryActivity.created_at.desc()).all()

def create_story_record(db: Session, story_data: Dict[str, Any]) -> UserStory:
    new_story = UserStory(**story_data)
    db.add(new_story)
    db.flush()
    db.refresh(new_story)
    return new_story

def update_story_record(db: Session, story: UserStory):
    db.add(story) 
    db.flush()
    db.refresh(story)
    return story

def delete_story_record(db: Session, story: UserStory):
    db.delete(story)

def search_stories_db(
    db: Session, 
    query_str: str, 
    filter_assignee_id: Optional[int] = None, 
    filter_team_ids: Optional[List[int]] = None, 
    filter_project_ids: Optional[List[int]] = None,
    apply_filters: bool = False
) -> List[UserStory]:
    base_query = db.query(UserStory).options(joinedload(UserStory.project)).filter(
        or_(
            UserStory.title.ilike(f"%{query_str}%"),
            UserStory.story_pointer.ilike(f"%{query_str}%"),
        )
    )
    
    if apply_filters:
        criteria = []
        if filter_assignee_id is not None:
             criteria.append(UserStory.assignee_id == filter_assignee_id)
        if filter_team_ids:
             criteria.append(UserStory.team_id.in_(filter_team_ids))
        if filter_project_ids:
             criteria.append(UserStory.project_id.in_(filter_project_ids))
        
        if criteria:
            base_query = base_query.filter(or_(*criteria))
        else:
            return[]

    return base_query.limit(50).all()

def find_potential_parents_db(db: Session, project_id: int, target_types: List[str], exclude_id: Optional[int] = None) -> List[UserStory]:
    query = db.query(UserStory).filter(
        UserStory.project_id == project_id,
        UserStory.issue_type.in_(target_types)
    )
    if exclude_id:
        query = query.filter(UserStory.id != exclude_id)
    return query.all()

def get_epics_db(db: Session, filter_owner_id: Optional[int] = None, filter_project_ids: Optional[List[int]] = None, restrict: bool = False) -> List[UserStory]:
    query = db.query(UserStory).join(Project).filter(UserStory.issue_type == IssueType.EPIC.value)
    
    if restrict:
        criteria = []
        if filter_owner_id:
             criteria.append(Project.owner_id == filter_owner_id)
        if filter_project_ids:
             criteria.append(Project.id.in_(filter_project_ids))
        
        if criteria:
             query = query.filter(or_(*criteria))
    
    return query.all()

def get_distinct_project_ids_for_assignee(db: Session, user_id: int) -> List[int]:
    return [pid[0] for pid in db.query(UserStory.project_id).filter(UserStory.assignee_id == user_id).distinct().all()]

def get_epics_accessible_by_user(db: Session, user_id: int, owned_project_ids: List[int]) -> List[UserStory]:
    member_project_ids = db.query(Team.project_id).filter(
        Team.members.any(id=user_id)
    ).subquery()
    
    return db.query(UserStory).join(Project).filter(
        UserStory.issue_type == IssueType.EPIC.value,
        or_(
            Project.owner_id == user_id,
            Project.id.in_(owned_project_ids),
            Project.id.in_(member_project_ids)
        )
    ).all()

def get_assigned_stories_db(db: Session, user_id: int, project_ids_in: Optional[List[int]] = None, project_ids_not_in: Optional[List[int]] = None) -> List[UserStory]:
    query = db.query(UserStory).options(joinedload(UserStory.team), joinedload(UserStory.project))\
            .filter(UserStory.assignee_id == user_id)
    
    if project_ids_in:
        query = query.filter(UserStory.project_id.in_(project_ids_in))
    
    if project_ids_not_in:
        query = query.filter(UserStory.project_id.notin_(project_ids_not_in))
        
    return query.all()

def get_stories_by_project_db(db: Session, project_id: int) -> List[UserStory]:
    return db.query(UserStory)\
        .options(joinedload(UserStory.team), joinedload(UserStory.project))\
        .filter(UserStory.project_id == project_id).all()
