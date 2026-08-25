"""Application-level failures that web and future agent adapters can translate."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """A stable field-level problem suitable for forms and CSV rows."""

    code: str
    message: str
    field: str | None = None
    row: int | None = None


class PortfolioValidationError(Exception):
    def __init__(self, issues: list[ValidationIssue]) -> None:
        super().__init__("Portfolio data is invalid.")
        self.issues = tuple(issues)


class PortfolioConflictError(Exception):
    """The caller attempted to replace a portfolio from an old revision."""


class DuplicateImportError(Exception):
    """The same confirmed CSV batch was already applied."""
