import os
from typing import List


from fastapi import APIRouter, Depends, UploadFile
from app.models import User
from app.auth.permissions import can_view_issue
from app.auth.permissions import can_view_issue
from app.utils.utils import story_to_dict

from app.enums import IssueType, StoryAction, StoryStatus, Priority
from app.constants import ErrorMessages, SuccessMessages
from app.utils.common import get_object_or_404, check_project_active, save_uploaded_file
from app.utils.deps import APIContext, AvailableParentsParams, SearchParams
from app.schemas.story_schema import UserStoryActivityResponse, StorySimpleResponse, EpicResponse, UserStoryCreateForm, UserStoryUpdateForm

from sqlalchemy.exc import SQLAlchemyError
from app.utils import story_service as story_utils

router = APIRouter(prefix="/user-stories", tags=["user-stories"])


@router.get("/types", response_model=List[str])
def get_issue_types(ctx: APIContext = Depends()):
    return [t.value for t in IssueType]

@router.get("/search")
def search_stories(
    params: SearchParams = Depends(),
    ctx: APIContext = Depends()
):
    results = story_utils.search_stories(ctx.db, ctx.user, params.q)
    return [story_to_dict(s) for s in results]

@router.get("/available-parents", response_model=List[StorySimpleResponse])
def get_available_parents(
    params: AvailableParentsParams = Depends(),
    ctx: APIContext = Depends()
):
    results = story_utils.get_available_parents(ctx.db, ctx.user, params.project_id, params.issue_type, params.exclude_id)
    return results

@router.get("/epics/all", response_model=List[EpicResponse])
def get_all_epics(
    ctx: APIContext = Depends()
):
    epics = story_utils.get_epics(ctx.db, ctx.user)
    return epics

@router.post("")
def create_user_story(
    form: UserStoryCreateForm = Depends(),
    ctx: APIContext = Depends()
):
    file_path = save_uploaded_file(form.support_doc)
    
    story_in = form.to_create_request()

    new_story = story_utils.create_story(ctx.db, ctx.user, story_in, file_path)
    return story_to_dict(new_story)

@router.get("/{id}/history", response_model=List[UserStoryActivityResponse])
def get_story_history(id: int, ctx: APIContext = Depends()):
    """
    Retrieves the activity history of a story.
    """
    from app.models.user_story_activity import UserStoryActivity
    return ctx.db.query(UserStoryActivity).filter(UserStoryActivity.story_id == id).order_by(UserStoryActivity.created_at.desc()).all()


@router.get("/{id}")
def get_story_by_id(
    id: int,
    ctx: APIContext = Depends()
):
    story = story_utils.get_story_by_id(ctx.db, id)
    if not story:
        raise_story_not_found()
    
    if not can_view_issue(ctx.user, story, ctx.db):
        raise_forbidden()
        
    return story_to_dict(story)

@router.put("/{id}")
def update_story(
    id: int,
    form: UserStoryUpdateForm = Depends(),
    ctx: APIContext = Depends()
):
    story_in = form.to_update_request()

    updated_story = story_utils.update_story(ctx.db, ctx.user, id, story_in)
    return story_to_dict(updated_story)

@router.get("/{id}/activity")
def get_story_activity(
    id: int,
    ctx: APIContext = Depends()
):
    story = story_utils.get_story_by_id(ctx.db, id)
    if not story: raise_story_not_found()
    
    if not can_view_issue(ctx.user, story, ctx.db):
        raise_forbidden()
    
    from app.models.user_story_activity import UserStoryActivity
    activities = ctx.db.query(UserStoryActivity).filter(UserStoryActivity.story_id == id).order_by(UserStoryActivity.created_at.desc()).all()
    
    result = []
    for act in activities:
        u = ctx.db.query(User).filter(User.id == act.user_id).first() if act.user_id else None
        
        # Calculate change count roughly from changes string if needed, or default to 0
        # The frontend likely expects this structure
        result.append(UserStoryActivityResponse(
            id=act.id,
            story_id=act.story_id,
            user_id=act.user_id,
            username=u.username if u else "System", 
            action=act.action,
            changes=act.changes,
            change_count=0, # Defaulting as it was missing in manual dict
            created_at=act.created_at
        ))
    return result

@router.get("/assigned/me")
def get_my_assigned_stories(
    ctx: APIContext = Depends()
):
    stories = story_utils.get_my_assigned_stories(ctx.db, ctx.user)
    return [story_to_dict(s) for s in stories]

@router.delete("/{id}")
def delete_user_story(
    id: int,
    ctx: APIContext = Depends()
):
    story = story_utils.get_story_by_id(ctx.db, id)
    if not story: raise_story_not_found()
    
    check_project_active(story.project.is_active)
    
    story_utils.delete_story(ctx.db, story)
    return {"message": SuccessMessages.STORY_DELETED}

@router.get("/project/{project_id}")
def get_stories_by_project(
    project_id: int,
    ctx: APIContext = Depends()
):
    stories = story_utils.get_stories_by_project(ctx.db, project_id)
    return [story_to_dict(s) for s in stories]
