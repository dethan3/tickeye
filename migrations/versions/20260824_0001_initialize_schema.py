"""Initialize the V2 migration history.

Revision ID: 20260824_0001
Revises:
Create Date: 2026-08-24
"""

from collections.abc import Sequence

revision: str = "20260824_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the Alembic version baseline; domain tables begin in PR 1."""


def downgrade() -> None:
    """Return to an unversioned database."""
