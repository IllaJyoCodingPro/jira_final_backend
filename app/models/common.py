from sqlalchemy import Column, Integer, ForeignKey, Table, DateTime
from sqlalchemy.sql import func
from app.database.base import Base

# Association Table for Team Members
class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))

    created_at = Column(DateTime, server_default=func.now())

team_members = TeamMember.__table__