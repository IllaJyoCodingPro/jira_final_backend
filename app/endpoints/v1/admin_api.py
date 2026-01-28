from typing import List
from fastapi import APIRouter, Depends, Form
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import User
from app.auth.dependencies import get_current_user
from app.constants import ErrorMessages
from app.utils.common import get_object_or_404
from app.exceptions import raise_forbidden, raise_bad_request
from app.utils.logger import get_logger

logger = get_logger(__name__)

from app.constants import Roles
from app.enums import UserRole


from app.schemas.user_schema import UserResponse

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/users", response_model=List[UserResponse])
def admin_get_all_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves all users for the admin dashboard.
    Only accessible by Master Admin.
    """
    if not current_user.is_master_admin:
        raise_forbidden("Only Master Admin can view all users")
    
    users = db.query(User).all()
    return users

@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    new_role: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Updates a user's role.
    Only Master Admin can perform this action.
    """
    if not current_user.is_master_admin:
        raise_forbidden("Only Master Admin can change user roles")
    
    new_role = new_role.upper()


    if new_role not in Roles.ALL_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Allowed roles: {Roles.ALL_ROLES}")

    
    user = get_object_or_404(db, User, user_id, ErrorMessages.USER_NOT_FOUND)
    
    if user.id == current_user.id and new_role != Roles.ADMIN:
        raise_bad_request("Admin cannot remove their own ADMIN role")
    
    user.role = new_role
    
    return {
        "message": "User role updated successfully",
        "user_id": user.id,
        "new_role": user.role
    }