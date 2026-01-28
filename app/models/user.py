from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.hybrid import hybrid_property
from app.database.base import Base
from .team import team_members
from app.enums import UserRole

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    profile_pic = Column(String(255), nullable=True)
    _role = Column("role", String(20), default=UserRole.DEVELOPER.value)
    _view_mode = Column("view_mode", String(20), default=UserRole.DEVELOPER.value)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    @hybrid_property
    def role(self) -> str:
        if self.email == "admin@jira.local":
            return UserRole.MASTER_ADMIN.value
        return self._role or UserRole.DEVELOPER.value

    @role.setter
    def role(self, value: str):
        self._role = value

    @property
    def is_master_admin(self) -> bool:
        return self.email == "admin@jira.local"

    @hybrid_property
    def view_mode(self) -> str:
        if self.email == "admin@jira.local":
            return UserRole.ADMIN.value
        return self._view_mode or UserRole.DEVELOPER.value

    @view_mode.setter
    def view_mode(self, value: str):
        if self.email == "admin@jira.local":
            return
        self._view_mode = value

    reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user")
    
    # Relationships for Teams
    teams = relationship("Team", secondary=team_members, back_populates="members")
    led_teams = relationship("Team", back_populates="lead")
