from typing import Optional
from sqlalchemy.orm import Session
from app.models import UserStory
from app.enums import IssueType, StoryStatus
from app.exceptions import raise_bad_request, raise_circular_dependency

def validate_hierarchy(db: Session, parent_id: Optional[int], issue_type: str, current_issue_id: Optional[int] = None):
    try:
        current_type_enum = IssueType(issue_type)
    except ValueError:
        raise_bad_request(f"Invalid issue type: {issue_type}")

    if not parent_id:
        if current_type_enum == IssueType.SUBTASK:
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
            
    try:
        parent_type_enum = IssueType(parent_story.issue_type)
    except ValueError:
        raise_bad_request(f"Parent issue has invalid type: {parent_story.issue_type}")
    
    if current_type_enum == IssueType.EPIC:
        raise_bad_request("Epics cannot have a parent issue.")
    
    if current_type_enum == IssueType.STORY and parent_type_enum != IssueType.EPIC:
        raise_bad_request(f"Story must be a child of an Epic, not {parent_type_enum.value}.")
        
    if current_type_enum == IssueType.TASK and parent_type_enum != IssueType.STORY:
        raise_bad_request(f"Task must be a child of a Story, not {parent_type_enum.value}.")
        
    if current_type_enum == IssueType.SUBTASK and parent_type_enum != IssueType.TASK:
        raise_bad_request(f"Subtask must be a child of a Task, not {parent_type_enum.value}.")
        
    if current_type_enum == IssueType.BUG and parent_type_enum not in [IssueType.STORY, IssueType.TASK]:
        raise_bad_request(f"Bug must be a child of a Story or Task, not {parent_type_enum.value}.")

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
