from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database.session import get_db
from app.schemas import TeamCreate, TeamUpdate
from app.utils import team_service
from app.auth.dependencies import get_current_user
from app.models import User, Team
from app.auth.permissions import (
    is_admin,
    is_project_lead,
    can_manage_team_members
)

from app.constants import ErrorMessages, SuccessMessages
from app.utils.common import get_object_or_404
from app.exceptions import raise_forbidden
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/teams", tags=["Teams"])

@router.post("", status_code=201)
def create_team(
    team_data: TeamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new team.
    Restricted to Admins and Project Leads.
    """
    if not is_project_lead(current_user, team_data.project_id, db):
        raise_forbidden(ErrorMessages.ONLY_ADMINS_PROJECT_LEADS)

    new_team = team_service.create_team(db, team_data)

    return new_team

@router.get("")
def get_all_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves all teams in the system.
    """
    return team_service.get_all_teams(db)

@router.get("/project/{project_id}")
def get_project_teams(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves all teams for a specific project.
    """
    return team_service.get_teams_by_project(db, project_id)

@router.get("/{team_id}")
def get_team(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves details of a specific team.
    """
    return team_service.get_team(db, team_id)

@router.put("/{team_id}")
def update_team(
    team_id: int,
    team_update: TeamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Updates an existing team.
    Restricted to Admins and Project Leads.
    """
    team_model = get_object_or_404(db, Team, team_id, ErrorMessages.TEAM_NOT_FOUND)



    if not can_manage_team_members(current_user, team_model, db):
        raise_forbidden("Only Admins or Project Leads can manage team members")

    updated_team = team_service.update_team(db, team_id, team_update)

    return updated_team

@router.delete("/{team_id}")
def delete_team(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Deletes a team.
    Restricted to Admins.
    """
    if not is_admin(current_user):
        raise_forbidden("Only Admins can delete teams")

    team_service.delete_team(db, team_id)
    return {"message": SuccessMessages.TEAM_DELETED}