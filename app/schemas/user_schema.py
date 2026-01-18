from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    view_mode: str
    is_master_admin: bool = False
    profile_pic: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

class NotificationCount(BaseModel):
    unread_count: int

class ModeSwitchRequestSchema(BaseModel):
    requested_mode: str
    reason: str