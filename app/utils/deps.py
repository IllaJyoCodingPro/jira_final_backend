from fastapi import Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models import User
from app.auth.dependencies import get_current_user
from typing import Optional

class APIContext:
    def __init__(
        self,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user)
    ):
        self.db = db
        self.user = user

class AvailableParentsParams:
    def __init__(
        self,
        project_id: int,
        issue_type: str,
        exclude_id: Optional[int] = None
    ):
        self.project_id = project_id
        self.issue_type = issue_type
        self.exclude_id = exclude_id

class SearchParams:
    def __init__(self, q: str):
        self.q = q
