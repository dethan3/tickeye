"""Add frozen scenarios, ordered operations, and immutable comparisons.

Revision ID: 20260825_0006
Revises: 20260824_0005
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260825_0006"
down_revision: str | None = "20260824_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scenarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("base_portfolio_revision", sa.Integer(), nullable=False),
        sa.Column("base_inputs_json", sa.Text(), nullable=False),
        sa.Column("assumptions_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "scenario_operations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scenario_id", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("operation_type", sa.String(length=32), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Numeric(24, 2), nullable=True),
        sa.Column("target_weight", sa.Numeric(12, 8), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(24, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount IS NULL OR amount >= 0", name="ck_scenario_amount"),
        sa.CheckConstraint(
            "target_weight IS NULL OR (target_weight >= 0 AND target_weight <= 1)",
            name="ck_scenario_target_weight",
        ),
        sa.CheckConstraint("estimated_cost >= 0", name="ck_scenario_estimated_cost"),
        sa.ForeignKeyConstraint(
            ["scenario_id"], ["scenarios.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scenario_id", "sequence", name="uq_scenario_operation_sequence"
        ),
    )
    op.create_table(
        "scenario_comparisons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scenario_id", sa.Integer(), nullable=False),
        sa.Column("operation_count", sa.Integer(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("methodology_version", sa.String(length=50), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["scenario_id"], ["scenarios.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scenario_id", "operation_count", name="uq_scenario_comparison_version"
        ),
    )


def downgrade() -> None:
    op.drop_table("scenario_comparisons")
    op.drop_table("scenario_operations")
    op.drop_table("scenarios")
