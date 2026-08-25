"""Persistence operations for frozen Scenario experiments."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from tickeye.infrastructure.db import (
    ScenarioComparisonRecord,
    ScenarioOperationRecord,
    ScenarioRecord,
)


class ScenarioRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, scenario: ScenarioRecord) -> ScenarioRecord:
        self.session.add(scenario)
        self.session.flush()
        return scenario

    def get(self, profile_id: int, scenario_id: int) -> ScenarioRecord | None:
        return self.session.scalar(
            select(ScenarioRecord).where(
                ScenarioRecord.id == scenario_id,
                ScenarioRecord.profile_id == profile_id,
            )
        )

    def all(self, profile_id: int) -> list[ScenarioRecord]:
        return list(
            self.session.scalars(
                select(ScenarioRecord)
                .where(ScenarioRecord.profile_id == profile_id)
                .order_by(ScenarioRecord.id.desc())
            )
        )

    def operations(self, scenario_id: int) -> list[ScenarioOperationRecord]:
        return list(
            self.session.scalars(
                select(ScenarioOperationRecord)
                .where(ScenarioOperationRecord.scenario_id == scenario_id)
                .order_by(ScenarioOperationRecord.sequence)
            )
        )

    def add_operation(
        self, operation: ScenarioOperationRecord
    ) -> ScenarioOperationRecord:
        self.session.add(operation)
        self.session.flush()
        return operation

    def add_comparison(
        self, comparison: ScenarioComparisonRecord
    ) -> ScenarioComparisonRecord:
        self.session.add(comparison)
        self.session.flush()
        return comparison

    def latest_comparison(self, scenario_id: int) -> ScenarioComparisonRecord | None:
        return self.session.scalar(
            select(ScenarioComparisonRecord)
            .where(ScenarioComparisonRecord.scenario_id == scenario_id)
            .order_by(ScenarioComparisonRecord.operation_count.desc())
            .limit(1)
        )
