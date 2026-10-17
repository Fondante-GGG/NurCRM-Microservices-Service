from typing import Any, Dict, Optional


class CRMException(Exception):
    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None,
    ):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details or {}


class ValidationError(CRMException):
    status_code = 400
    code = "validation_error"


class UnauthorizedError(CRMException):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(CRMException):
    status_code = 403
    code = "forbidden"


class NotFoundError(CRMException):
    status_code = 404
    code = "not_found"


class ConflictError(CRMException):
    status_code = 409
    code = "conflict"


class VersionConflictError(ConflictError):
    code = "version_conflict"

    def __init__(self, message: str = "Entity version conflict. Please reload and try again.", current_version: Optional[int] = None):
        details = {"current_version": current_version} if current_version is not None else {}
        super().__init__(message=message, code=self.code, details=details)


class SlotBusyError(ConflictError):
    code = "slot_busy"

    def __init__(self, message: str = "Selected time slot is already booked for this master."):
        super().__init__(message=message, code=self.code)


class AlreadyProcessedError(ConflictError):
    code = "already_processed"


class ShiftAlreadyOpenError(ConflictError):
    code = "shift_already_open"


class ClientExistsError(ConflictError):
    code = "client_exists"


class RateLimitExceededError(CRMException):
    status_code = 429
    code = "rate_limit_exceeded"


def crm_exception_handler(exc, context):
    try:
        from rest_framework.views import exception_handler
        from rest_framework.response import Response
        response = exception_handler(exc, context)
    except ImportError:
        response = None

    if isinstance(exc, CRMException):
        from libs.common.response import error_response
        from rest_framework.response import Response
        return Response(
            error_response(code=exc.code, message=exc.message, details=exc.details),
            status=exc.status_code,
        )
    return response
