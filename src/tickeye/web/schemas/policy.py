"""Policy management and insight event API contracts."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from tickeye.application.policy_service import (
    PolicyRuleDraft,
    PolicySet,
    StoredInsightEvent,
)
from tickeye.domain.policy import PolicyRuleType, RiskFinding


class PolicyRuleInput(BaseModel):
    id: int | None = None
    rule_type: PolicyRuleType
    subject_key: str = Field(min_length=1, max_length=64)
    threshold: Decimal = Field(ge=0, le=1, decimal_places=8)
    tolerance: Decimal | None = Field(default=None, gt=0, le=1, decimal_places=8)
    warning_ratio: Decimal = Field(gt=0, lt=1, decimal_places=8)
    enabled: bool = True

    def to_draft(self) -> PolicyRuleDraft:
        return PolicyRuleDraft(
            rule_id=self.id,
            rule_type=self.rule_type,
            subject_key=self.subject_key,
            threshold=self.threshold,
            tolerance=self.tolerance,
            warning_ratio=self.warning_ratio,
            enabled=self.enabled,
        )


class ReplacePoliciesRequest(BaseModel):
    expected_revision: int = Field(ge=0)
    rules: list[PolicyRuleInput] = Field(max_length=100)


class PolicyRuleSchema(BaseModel):
    id: int
    rule_type: PolicyRuleType
    subject_key: str
    subject_label: str
    threshold: Decimal
    tolerance: Decimal | None
    warning_ratio: Decimal
    enabled: bool


class PolicyData(BaseModel):
    revision: int
    rules: list[PolicyRuleSchema]


class PolicyResponse(BaseModel):
    data: PolicyData
    calculated_at: datetime
    warnings: list[str]
    methodology_version: Literal["policy-rules-v1"] = "policy-rules-v1"

    @classmethod
    def from_domain(cls, policy: PolicySet) -> "PolicyResponse":
        return cls(
            data=PolicyData(
                revision=policy.revision,
                rules=[
                    PolicyRuleSchema(
                        id=item.id,
                        rule_type=PolicyRuleType(item.rule_type),
                        subject_key=item.subject_key,
                        subject_label=item.subject_label,
                        threshold=item.threshold,
                        tolerance=item.tolerance,
                        warning_ratio=item.warning_ratio,
                        enabled=item.enabled,
                    )
                    for item in policy.rules
                ],
            ),
            calculated_at=datetime.now(UTC),
            warnings=(
                ["尚未设置用户风险边界；系统不会将当前组合解释为安全。"]
                if not policy.rules
                else []
            ),
        )


class InsightEventSchema(BaseModel):
    event_id: int
    event_type: str
    finding_key: str
    from_state: str | None
    to_state: str
    severity: str
    occurred_at: datetime
    finding: "RiskFindingEventSchema"


class RiskFindingEventSchema(BaseModel):
    finding_key: str
    dimension: str
    state: str
    title: str
    message: str
    current_value: Decimal | None
    boundary_low: Decimal | None
    boundary_high: Decimal | None
    contributor_key: str | None
    contributor_label: str | None
    policy_rule_id: int | None

    @classmethod
    def from_domain(cls, finding: RiskFinding) -> "RiskFindingEventSchema":
        return cls.model_validate(finding, from_attributes=True)


class EventData(BaseModel):
    items: list[InsightEventSchema]


class EventResponse(BaseModel):
    data: EventData
    calculated_at: datetime
    warnings: list[str]
    methodology_version: Literal["insight-events-v1"] = "insight-events-v1"

    @classmethod
    def from_domain(cls, events: tuple[StoredInsightEvent, ...]) -> "EventResponse":
        return cls(
            data=EventData(
                items=[
                    InsightEventSchema(
                        event_id=item.event_id,
                        event_type=item.event_type,
                        finding_key=item.finding_key,
                        from_state=item.from_state,
                        to_state=item.to_state,
                        severity=item.severity,
                        occurred_at=item.occurred_at,
                        finding=RiskFindingEventSchema.model_validate_json(
                            item.payload_json
                        ),
                    )
                    for item in events
                ]
            ),
            calculated_at=datetime.now(UTC),
            warnings=[],
        )
