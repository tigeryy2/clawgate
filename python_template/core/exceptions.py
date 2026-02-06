from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorPayload:
    code: str
    message: str


class APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.payload = ErrorPayload(code=code, message=message)


class NotFoundError(APIError):
    def __init__(self, message: str):
        super().__init__(status_code=404, code="NOT_FOUND", message=message)


class ValidationError(APIError):
    def __init__(self, message: str, code: str = "VALIDATION_ERROR"):
        super().__init__(status_code=400, code=code, message=message)


class PolicyBlockedError(APIError):
    def __init__(self, message: str = "blocked by policy"):
        super().__init__(status_code=403, code="POLICY_BLOCKED", message=message)


class UnauthorizedError(APIError):
    def __init__(self, message: str = "missing or invalid credentials"):
        super().__init__(status_code=401, code="UNAUTHORIZED", message=message)


class RateLimitError(APIError):
    def __init__(self, message: str = "rate limit exceeded"):
        super().__init__(status_code=429, code="RATE_LIMITED", message=message)
