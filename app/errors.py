class AppError(Exception):
    status_code = 400
    error = "bad_request"

    def __init__(self, message, *, status_code=None, error=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if error is not None:
            self.error = error


class AuthenticationError(AppError):
    status_code = 401
    error = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    error = "forbidden"


class NotFoundError(AppError):
    status_code = 404
    error = "not_found"


class ConflictError(AppError):
    status_code = 409
    error = "conflict"


class ValidationError(AppError):
    status_code = 422
    error = "validation_error"

