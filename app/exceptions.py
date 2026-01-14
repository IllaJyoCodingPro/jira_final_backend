from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.constants import ErrorMessages
from app.enums import ErrorCode


class BaseAPIException(HTTPException):
    """
    Base exception for all API errors.
    Enforces a consistent, frontend-friendly response structure.
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        error_code: ErrorCode,
        details: dict | None = None,
    ):
        super().__init__(status_code=status_code, detail=message)
        self.message = message
        self.error_code = error_code
        self.details = details


# --------------------------------------------------
# GLOBAL EXCEPTION HANDLER
# --------------------------------------------------

async def base_api_exception_handler(request: Request, exc: BaseAPIException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.message,
            "error_code": exc.error_code,
            "path": request.url.path,
            "details": exc.details,
        },
    )


# --------------------------------------------------
# CENTRAL ERROR FACTORY (ONLY PLACE TO RAISE ERRORS)
# --------------------------------------------------

def raise_api_error(
    status_code: int,
    message: str,
    error_code: ErrorCode,
    details: dict | None = None,
):
    raise BaseAPIException(
        status_code=status_code,
        message=message,
        error_code=error_code,
        details=details,
    )


# --------------------------------------------------
# GENERIC HTTP HELPERS
# --------------------------------------------------

def raise_bad_request(message: str):
    raise_api_error(400, message, ErrorCode.BAD_REQUEST)


def raise_unauthorized(
    message: str = ErrorMessages.INVALID_CREDENTIALS,
):
    raise_api_error(401, message, ErrorCode.UNAUTHORIZED)


def raise_forbidden(
    message: str = ErrorMessages.ACCESS_DENIED,
):
    raise_api_error(403, message, ErrorCode.FORBIDDEN)


def raise_not_found(
    message: str,
    error_code: ErrorCode,
):
    raise_api_error(404, message, error_code)


def raise_internal_error(
    message: str = "Internal server error",
):
    raise_api_error(
        500,
        message,
        ErrorCode.INTERNAL_SERVER_ERROR,
    )


# --------------------------------------------------
# DOMAIN-SPECIFIC HELPERS
# --------------------------------------------------

def raise_user_not_found():
    raise_not_found(
        ErrorMessages.USER_NOT_FOUND,
        ErrorCode.USER_NOT_FOUND,
    )


def raise_project_not_found():
    raise_not_found(
        ErrorMessages.PROJECT_NOT_FOUND,
        ErrorCode.PROJECT_NOT_FOUND,
    )


def raise_story_not_found():
    raise_not_found(
        ErrorMessages.STORY_NOT_FOUND,
        ErrorCode.STORY_NOT_FOUND,
    )


def raise_team_not_found():
    raise_not_found(
        ErrorMessages.TEAM_NOT_FOUND,
        ErrorCode.TEAM_NOT_FOUND,
    )


def raise_circular_dependency():
    raise_bad_request(ErrorMessages.CIRCULAR_DEPENDENCY)


def raise_no_permission_create():
    raise_api_error(
        403,
        ErrorMessages.NO_PERMISSION_CREATE,
        ErrorCode.PERMISSION_DENIED_CREATE,
    )


def raise_no_permission_edit():
    raise_api_error(
        403,
        ErrorMessages.NO_PERMISSION_EDIT,
        ErrorCode.PERMISSION_DENIED_EDIT,
    )
