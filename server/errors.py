class AppError(Exception):
    status = 500
    code = "internal_error"

    def __init__(self, message, details=None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_payload(self):
        return {"error": self.code, "message": self.message, "details": self.details}


class ValidationError(AppError):
    status = 400
    code = "validation_error"


class AuthError(AppError):
    status = 401
    code = "auth_error"


class ForbiddenError(AppError):
    status = 403
    code = "forbidden"


class NotFoundError(AppError):
    status = 404
    code = "not_found"


class ConflictError(AppError):
    status = 409
    code = "conflict"
