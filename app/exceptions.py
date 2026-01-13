from fastapi import HTTPException
from app.constants import ErrorMessages

def raise_not_found(detail: str = ErrorMessages.PROJECT_NOT_FOUND):
    raise HTTPException(status_code=404, detail=detail)

def raise_bad_request(detail: str):
    raise HTTPException(status_code=400, detail=detail)

def raise_unauthorized(detail: str = ErrorMessages.INVALID_CREDENTIALS):
    raise HTTPException(status_code=401, detail=detail)

def raise_forbidden(detail: str = ErrorMessages.ACCESS_DENIED):
    raise HTTPException(status_code=403, detail=detail)

def raise_internal_error(detail: str = "Internal server error"):
    raise HTTPException(status_code=500, detail=detail)

# Specific Domain Exceptions
def raise_user_not_found():
    raise_not_found(ErrorMessages.USER_NOT_FOUND)

def raise_project_not_found():
    raise_not_found(ErrorMessages.PROJECT_NOT_FOUND)

def raise_story_not_found():
    raise_not_found(ErrorMessages.STORY_NOT_FOUND)

def raise_team_not_found():
    raise_not_found(ErrorMessages.TEAM_NOT_FOUND)

def raise_circular_dependency():
    raise_bad_request(ErrorMessages.CIRCULAR_DEPENDENCY)

def raise_no_permission_create():
    raise_forbidden(ErrorMessages.NO_PERMISSION_CREATE)

def raise_no_permission_edit():
    raise_forbidden(ErrorMessages.NO_PERMISSION_EDIT)
