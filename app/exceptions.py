class DomainError(Exception):
    """Base for usecase-layer errors. Usecases raise these instead of FastAPI's
    HTTPException, so they stay framework-agnostic; main.py's exception
    handlers translate them into HTTP responses."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class NotFoundError(DomainError):
    pass


class UnauthorizedError(DomainError):
    pass


class ConflictError(DomainError):
    pass
