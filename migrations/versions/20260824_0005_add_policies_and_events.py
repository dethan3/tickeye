"""Add explicit policies, immutable evaluations, and insight events.

Revision ID: 20260824_0005
Revises: 20260824_0004
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260824_0005"
down_revision: str | None = "20260824_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("profiles") as batch:
        batch.add_column(
            sa.Column("policy_revision", sa.Integer(), server_default="0", nullable=False)
        )
    op.create_table(
        "policy_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("rule_type", sa.String(length=50), nullable=False),
        sa.Column("subject_key", sa.String(length=64), nullable=False),
        sa.Column("subject_label", sa.String(length=200), nullable=False),
        sa.Column("threshold", sa.Numeric(12, 8), nullable=False),
        sa.Column("tolerance", sa.Numeric(12, 8), nullable=True),
        sa.Column("warning_ratio", sa.Numeric(12, 8), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("threshold >= 0 AND threshold <= 1", name="ck_policy_threshold"),
        sa.CheckConstraint(
            "warning_ratio > 0 AND warning_ratio < 1", name="ck_policy_warning_ratio"
        ),
        sa.CheckConstraint(
            "tolerance IS NULL OR (tolerance > 0 AND tolerance <= 1)",
            name="ck_policy_tolerance",
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id", "rule_type", "subject_key", name="uq_policy_rule_subject"
        ),
    )
    op.create_table(
        "risk_evaluations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("risk_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("methodology_version", sa.String(length=50), nullable=False),
        sa.Column("findings_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["risk_snapshot_id"], ["risk_snapshots.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "insight_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("evaluation_id", sa.Integer(), nullable=False),
        sa.Column("finding_key", sa.String(length=100), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("from_state", sa.String(length=16), nullable=True),
        sa.Column("to_state", sa.String(length=16), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("dedupe_key", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["evaluation_id"], ["risk_evaluations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key"),
    )


def downgrade() -> None:
    op.drop_table("insight_events")
    op.drop_table("risk_evaluations")
    op.drop_table("policy_rules")
    with op.batch_alter_table("profiles") as batch:
        batch.drop_column("policy_revision")
