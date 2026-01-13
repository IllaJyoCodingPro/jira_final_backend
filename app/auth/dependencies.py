from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import User
from app.config.settings import settings
from app.exceptions import raise_unauthorized, raise_forbidden
from app.utils.logger import get_logger

logger = get_logger(__name__)

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    Dependency to get the current authenticated user from JWT token.
    
    Args:
        credentials: Bearer token credentials
        db: Database session
        
    Returns:
        User: The authenticated user instance
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int = payload.get("user_id")
        if not user_id:
            raise_unauthorized()
    except JWTError:
        raise_unauthorized()

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise_unauthorized()

    return user


def require_role(role: str):
    """
    Dependency factory to require a specific user role.
    
    Args:
        role: The role to require (e.g. 'ADMIN')
        
    Returns:
        function: Dependency function that checks user role
    """
    def checker(user: User = Depends(get_current_user)):
        if user.role != role:
            raise_forbidden("Insufficient permissions")
        return user
    return checker
