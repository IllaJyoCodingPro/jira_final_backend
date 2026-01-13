from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models import User, UserStory, Team, Project
from app.exceptions import raise_forbidden
from app.utils.logger import get_logger

logger = get_logger(__name__)

def check_issue_permission(user: User, resource, action: str, db: Session = None):
    """
    Centralized permission check logic for issues.
    """
    if user.role == "ADMIN":
        return True

    # Resource is usually a UserStory or Project.
    if isinstance(resource, UserStory):
        return check_issue_permission(user, resource, action, db)

    if action == "create_issue":
        # Handled in route logic; keep for compatibility.
        pass

    raise_forbidden("Permission denied")


def can_create_issue(user: User, project_id: int, team_id: int, db: Session):
    """
    Checks if a user can create an issue in a project/team.
    (Unchanged)
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project or not project.is_active:
        return False

    if user.is_master_admin:
        return True

    is_owner = project.owner_id == user.id

    if user.view_mode == "ADMIN":
        return is_owner

    if is_owner:
        return False

    is_member = (
        db.query(Team)
        .filter(Team.project_id == project_id)
        .filter(or_(Team.lead_id == user.id, Team.id.in_([t.id for t in user.teams])))
        .count() > 0
    )

    if is_member:
        return True

    return False


def can_update_issue(user: User, story: UserStory, db: Session):
    """
    Checks if a user can update a specific issue.
    Rules:
      - master admin / ADMIN / OWNER => can update any issue
      - Team lead for the story's TEAM => can update any issue for that team
      - Project-scoped team lead (user leads ANY team in the project) => can update
      - Regular developer => only own assigned issues
    """
    if not story.project.is_active:
        return False

    # Master admin / Admin / Owner
    if user.is_master_admin or user.role in ["ADMIN", "OWNER"]:
        return True

    # Developer rules
    if user.role == "DEVELOPER":
        # 1) Team-lead of the specific team that the story belongs to
        if story.team_id:
            team = db.query(Team).filter(Team.id == story.team_id).first()
            if team and team.lead_id == user.id and team.project_id == story.project_id:
                return True

        # 2) Project-scoped lead (if user leads any team in the story's project)
        if any(t.project_id == story.project_id for t in getattr(user, 'led_teams', [])):
            return True

        # 3) Regular developer: only own issues
        return story.assignee_id == user.id

    return False


def can_delete_issue(user: User, story: UserStory, db: Session):
    """
    Checks if a user can delete a specific issue.
    (Unchanged; team lead deletion remains supported.)
    """
    if not story.project.is_active:
        return False

    if user.is_master_admin:
        return True

    is_owner = story.project.owner_id == user.id
    if user.view_mode == "ADMIN" and is_owner:
        return True

    if story.team_id:
        team = db.query(Team).filter(Team.id == story.team_id).first()
        if team and team.lead_id == user.id and team.project_id == story.project_id:
            return True

    return False


def can_view_issue(user: User, story: UserStory, db: Session):
    """
    Checks if a user can view a specific issue.

    Rules:
      - master admin / ADMIN / OWNER => view any issue
      - Team lead of the story's team => may view it
      - Project-scoped lead => view
      - Regular developer => only assigned issues
    """
    if user.is_master_admin or user.role in ["ADMIN", "OWNER"]:
        return True

    if user.role == "DEVELOPER":
        # 1) Team-lead of the specific team that the story belongs to
        if story.team_id:
            team = db.query(Team).filter(Team.id == story.team_id).first()
            if team and team.lead_id == user.id and team.project_id == story.project_id:
                return True

        # 2) Project-scoped lead
        if any(t.project_id == story.project_id for t in getattr(user, 'led_teams', [])):
            return True

        # 3) Regular developer: only own assigned
        return story.assignee_id == user.id

    return False


def is_admin(user: User):
    return user.role == "ADMIN"


def is_project_lead(user: User, project_id: int, db: Session):
    """
    Checks if user leads a team in a specific project or owns the project.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if project and project.owner_id == user.id:
        return True

    return db.query(Team).filter(Team.project_id == project_id, Team.lead_id == user.id).count() > 0


def can_manage_team_members(user: User, team: Team, db: Session):
    """
    Checks if user can manage members of a team (unchanged).
    """
    if user.is_master_admin:
        return True

    if user.role == "ADMIN":
        return True

    if team.lead_id == user.id:
        return True

    return is_project_lead(user, team.project_id, db)