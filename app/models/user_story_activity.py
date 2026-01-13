from sqlalchemy import Column, Integer, String, Text, ForeignKey, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.base import Base
from app.enums import StoryAction

class UserStoryActivity(Base):
    """ 
    Aggregated activity log for user story changes.
    Each record represents ONE save action with multiple field changes.
    """
    __tablename__ = "user_story_activity"

    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey("user_story.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    action = Column(String(50), nullable=False, default=StoryAction.UPDATED.value)  # UPDATED, CREATED, STATUS_CHANGED, etc.
    changes = Column(Text, nullable=False)  # Human-readable text description of changes
    change_count = Column(Integer, nullable=False, default=0)  # Number of fields changed
    
    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)
    
    # Relationships
    story = relationship("UserStory", back_populates="activities")
    user = relationship("User")
