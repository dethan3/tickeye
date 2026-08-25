"""Persistence operations for policies, evaluations, and insight events."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from tickeye.infrastructure.db import (
    InsightEventRecord,
    PolicyRuleRecord,
    RiskEvaluationRecord,
)


class PolicyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def rules(self, profile_id: int) -> list[PolicyRuleRecord]:
        return list(
            self.session.scalars(
                select(PolicyRuleRecord)
                .where(PolicyRuleRecord.profile_id == profile_id)
                .order_by(PolicyRuleRecord.id)
            )
        )

    def add_evaluation(
        self, evaluation: RiskEvaluationRecord
    ) -> RiskEvaluationRecord:
        self.session.add(evaluation)
        self.session.flush()
        return evaluation

    def latest_evaluation(self, profile_id: int) -> RiskEvaluationRecord | None:
        return self.session.scalar(
            select(RiskEvaluationRecord)
            .where(RiskEvaluationRecord.profile_id == profile_id)
            .order_by(RiskEvaluationRecord.id.desc())
            .limit(1)
        )

    def evaluation_for_snapshot(
        self, risk_snapshot_id: int
    ) -> RiskEvaluationRecord | None:
        return self.session.scalar(
            select(RiskEvaluationRecord)
            .where(RiskEvaluationRecord.risk_snapshot_id == risk_snapshot_id)
            .order_by(RiskEvaluationRecord.id.desc())
            .limit(1)
        )

    def add_event(self, event: InsightEventRecord) -> None:
        self.session.add(event)

    def events(self, profile_id: int, *, limit: int = 100) -> list[InsightEventRecord]:
        return list(
            self.session.scalars(
                select(InsightEventRecord)
                .where(InsightEventRecord.profile_id == profile_id)
                .order_by(InsightEventRecord.id.desc())
                .limit(limit)
            )
        )
