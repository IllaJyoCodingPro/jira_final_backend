from sqlalchemy.orm import Session
from typing import Type, TypeVar, Optional, Any
from app.exceptions import raise_not_found, raise_forbidden
from app.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

def get_object_or_404(db: Session, model: Type[T], obj_id: Any, msg: str = "Object not found") -> T:
    """
    Retrieves an object by ID or raises a 404 HTTPException.
    """
    obj = db.query(model).filter(model.id == obj_id).first()
    if not obj:
        raise_not_found(msg)
    return obj

def check_project_active(project_is_active: bool):
    """
    Checks if a project is active, otherwise raises a 403.
    """
    if not project_is_active:
        from app.constants import ErrorMessages
        raise_forbidden(ErrorMessages.PROJECT_INACTIVE)

def save_uploaded_file(upload_file: Any) -> Optional[str]:
    import shutil
    import os
    from app.config.settings import settings
    
    if not upload_file:
        return None
        
    try:
        # Check if it's an UploadFile (flexible check to avoid circular imports if needed, though Any works)
        if hasattr(upload_file, 'filename') and hasattr(upload_file, 'file'):
             file_path = os.path.join(settings.UPLOAD_DIR, upload_file.filename)
             with open(file_path, "wb") as buffer:
                 shutil.copyfileobj(upload_file.file, buffer)
             return file_path
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {str(e)}")
        return None
    return None