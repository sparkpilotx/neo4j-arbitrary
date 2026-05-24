"""Shared error infrastructure."""

from enum import StrEnum


class ErrorCode(StrEnum):
    NOT_FOUND = "NOT_FOUND"
    VALIDATION = "VALIDATION"
    PERMISSION = "PERMISSION"
    EXTERNAL = "EXTERNAL"


class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        context: dict[str, object] | None = None,
        suggestion: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.context: dict[str, object] = context or {}
        self.suggestion = suggestion

    def to_dict(self) -> dict[str, object]:
        return {
            "error": str(self.code),
            "message": self.message,
            "context": self.context,
            **({"suggestion": self.suggestion} if self.suggestion else {}),
        }
