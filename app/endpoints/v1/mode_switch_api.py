from fastapi import APIRouter, Depends, Form
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.database.session import get_db
from app.models import User, ModeSwitchRequest, Notification
from app.auth.dependencies import get_current_user
from app.schemas.user_schema import UserResponse, ModeSwitchRequestSchema
from app.enums import ModeSwitchStatus
from app.constants import ErrorMessages, Roles
from app.utils.common import get_object_or_404
from app.exceptions import raise_bad_request, raise_forbidden
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/mode-switch", tags=["Mode Switch"])

@router.post("/request")
def create_switch_request(
    request_data: ModeSwitchRequestSchema,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submits a request to switch view mode (Admin <-> Developer).
    Notifies Master Admin.
    """ 
    requested_mode = request_data.requested_mode
    reason = request_data.reason
    if user.is_master_admin:
        raise_bad_request("Master Admin does not need to request mode switches")
    
    if requested_mode not in [Roles.ADMIN, Roles.DEVELOPER]:
        raise_bad_request("Invalid mode requested")
    
    # Check if there's already a pending request
    existing = db.query(ModeSwitchRequest).filter(
        ModeSwitchRequest.user_id == user.id,
        ModeSwitchRequest.status == ModeSwitchStatus.PENDING.value
    ).first()
    
    if existing:
        raise_bad_request("You already have a pending switch request")

    request = ModeSwitchRequest(
        user_id=user.id,
        requested_mode=requested_mode,
        reason=reason,
        status=ModeSwitchStatus.PENDING.value
    )
    db.add(request)
    # db.commit() removed as per request
    db.flush() # Ensure ID is generated for return
    db.refresh(request)

    # Notify Master Admin
    master_admin = db.query(User).filter(User.email == "admin@jira.local").first()
    if master_admin:
        notification = Notification(
            user_id=master_admin.id,
            title="New Mode Switch Request",
            message=f"User {user.username} has requested to switch to {requested_mode} mode."
        )
        db.add(notification)
        # db.commit() removed as per request

    return {"message": "Request submitted successfully", "request_id": request.id}

@router.get("/requests")
def get_all_requests(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Retrieves all pending mode switch requests.
    Only accessible by Master Admin.
    """
    if not user.is_master_admin:
        raise_forbidden("Only Master Admin can view requests")
    
    requests = db.query(ModeSwitchRequest).filter(ModeSwitchRequest.status == ModeSwitchStatus.PENDING.value).all()
    
    # Enrich with user info manually or use a schema
    result = []
    for r in requests:
        result.append({
            "id": r.id,
            "user_id": r.user_id,
            "username": r.user.username,
            "email": r.user.email,
            "role": r.user.role,
            "requested_mode": r.requested_mode,
            "reason": r.reason,
            "status": r.status,
            "created_at": r.created_at
        })
    return result

@router.post("/approve/{request_id}")
def approve_request(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Approves a mode switch request and updates user role/view mode.
    Only accessible by Master Admin.
    """
    if not user.is_master_admin:
        raise_forbidden("Only Master Admin can approve requests")
    
    request = get_object_or_404(db, ModeSwitchRequest, request_id, ErrorMessages.REQUEST_NOT_FOUND)
    
    if request.status != ModeSwitchStatus.PENDING.value:
        raise_bad_request(f"Request is already {request.status}")

    # Update User Mode and Role
    target_user = request.user
    target_user.role = request.requested_mode
    target_user.view_mode = request.requested_mode
    request.status = ModeSwitchStatus.APPROVED.value
    
    # Create Notification
    notification = Notification(
        user_id=target_user.id,
        title="Mode Switch Approved",
        message=f"Your request to switch to {request.requested_mode} mode has been approved by the Master Admin."
    )
    db.add(notification)
    
    # db.commit() removed as per request
    return {"message": "Request approved and user mode updated"}

@router.post("/reject/{request_id}")
def reject_request(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Rejects a mode switch request.
    Only accessible by Master Admin.
    """
    if not user.is_master_admin:
        raise_forbidden("Only Master Admin can reject requests")
    
    request = get_object_or_404(db, ModeSwitchRequest, request_id, ErrorMessages.REQUEST_NOT_FOUND)
    
    if request.status != ModeSwitchStatus.PENDING.value:
        raise_bad_request(f"Request is already {request.status}")

    request.status = ModeSwitchStatus.REJECTED.value
    
    # Create Notification
    notification = Notification(
        user_id=request.user_id,
        title="Mode Switch Rejected",
        message=f"Your request to switch to {request.requested_mode} mode was rejected."
    )
    db.add(notification)
    
    # db.commit() removed as per request
    return {"message": "Request rejected"}