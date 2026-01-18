from enum import Enum

class IssueType(str, Enum):
    EPIC = "Epic"
    STORY = "Story"
    TASK = "Task"
    BUG = "Bug"
    SUBTASK = "Subtask"

    @property
    def valid_parents(self):
        if self == IssueType.EPIC:
            return []  # No parent
        if self == IssueType.STORY:
            return [IssueType.EPIC]
        if self == IssueType.TASK:
            return [IssueType.STORY]
        if self == IssueType.SUBTASK:
            return [IssueType.TASK]
        if self == IssueType.BUG:
            return [IssueType.STORY, IssueType.TASK]
        return []

class Priority(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

class StoryStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "In Progress"
    REVIEW = "Review"
    DONE = "Done"

class UserRole(str, Enum):
    ADMIN = "ADMIN"
    DEVELOPER = "DEVELOPER"
    TESTER = "TESTER"
    MASTER_ADMIN = "MASTER_ADMIN"

class ModeSwitchStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class StoryAction(str, Enum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    STATUS_CHANGED = "STATUS_CHANGED"
class ErrorCode(str, Enum):
    # Generic
    BAD_REQUEST = "BAD_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"

    # Auth / User
    USER_NOT_FOUND = "USER_NOT_FOUND"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"

    # Project / Domain
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    STORY_NOT_FOUND = "STORY_NOT_FOUND"
    TEAM_NOT_FOUND = "TEAM_NOT_FOUND"

    # Permission
    PERMISSION_DENIED_CREATE = "PERMISSION_DENIED_CREATE"
    PERMISSION_DENIED_EDIT = "PERMISSION_DENIED_EDIT"

    # Business rules
    CIRCULAR_DEPENDENCY = "CIRCULAR_DEPENDENCY"