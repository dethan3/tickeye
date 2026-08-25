"""Manage explicit policies and evaluate immutable risk snapshots."""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import delete, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session, sessionmaker

from tickeye.application.risk_service import StoredRiskSnapshot
from tickeye.domain.enums import AssetClass
from tickeye.domain.policy import (
    PolicyRule,
    PolicyRuleType,
    RiskEvaluation,
    RiskFinding,
    RiskState,
    evaluate_policy,
)
from tickeye.infrastructure.db import (
    InsightEventRecord,
    PolicyRuleRecord,
    ProfileRecord,
    RiskEvaluationRecord,
)
from tickeye.infrastructure.repositories import PolicyRepository, PortfolioRepository


class PolicyRevisionConflictError(Exception):
    pass


class PolicyValidationError(Exception):
    def __init__(self, messages: tuple[str, ...]) -> None:
        super().__init__("Invalid policy rules.")
        self.messages = messages


@dataclass(frozen=True, slots=True)
class PolicyRuleDraft:
    rule_id: int | None
    rule_type: PolicyRuleType
    subject_key: str
    threshold: Decimal
    tolerance: Decimal | None
    warning_ratio: Decimal
    enabled: bool


@dataclass(frozen=True, slots=True)
class PolicySet:
    revision: int
    rules: tuple[PolicyRuleRecord, ...]


@dataclass(frozen=True, slots=True)
class StoredRiskEvaluation:
    evaluation_id: int
    risk_snapshot_id: int
    policy_revision: int
    state: RiskState
    calculated_at: datetime
    findings_json: str


@dataclass(frozen=True, slots=True)
class StoredInsightEvent:
    event_id: int
    event_type: str
    finding_key: str
    from_state: str | None
    to_state: str
    severity: str
    occurred_at: datetime
    payload_json: str


def _json_default(value: object) -> str:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return str(value.value)
    raise TypeError(f"Unsupported policy value: {type(value).__name__}")


def _findings_json(evaluation: RiskEvaluation) -> str:
    return json.dumps(
        {"state": evaluation.state, "findings": asdict(evaluation)["findings"]},
        default=_json_default,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _domain_rule(record: PolicyRuleRecord) -> PolicyRule:
    return PolicyRule(
        rule_id=record.id,
        rule_type=PolicyRuleType(record.rule_type),
        subject_key=record.subject_key,
        subject_label=record.subject_label,
        threshold=record.threshold,
        tolerance=record.tolerance,
        warning_ratio=record.warning_ratio,
    )


class PolicyService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def get(self) -> PolicySet:
        with self.session_factory.begin() as session:
            profile = PortfolioRepository(session).get_or_create_profile()
            return PolicySet(
                revision=profile.policy_revision,
                rules=tuple(PolicyRepository(session).rules(profile.id)),
            )

    def replace(
        self,
        expected_revision: int,
        drafts: tuple[PolicyRuleDraft, ...],
    ) -> PolicySet:
        with self.session_factory.begin() as session:
            portfolio_repository = PortfolioRepository(session)
            profile = portfolio_repository.get_or_create_profile()
            messages = self._validate(session, profile.id, drafts)
            if messages:
                raise PolicyValidationError(tuple(messages))
            result = session.execute(
                update(ProfileRecord)
                .where(
                    ProfileRecord.id == profile.id,
                    ProfileRecord.policy_revision == expected_revision,
                )
                .values(policy_revision=ProfileRecord.policy_revision + 1)
            )
            assert isinstance(result, CursorResult)
            if result.rowcount != 1:
                raise PolicyRevisionConflictError

            existing = {item.id: item for item in PolicyRepository(session).rules(profile.id)}
            retained: set[int] = set()
            for draft in drafts:
                record = existing.get(draft.rule_id) if draft.rule_id is not None else None
                if draft.rule_id is not None and record is None:
                    raise PolicyValidationError(("规则不存在或不属于当前用户。",))
                if record is None:
                    record = PolicyRuleRecord(profile_id=profile.id)
                    session.add(record)
                elif record.profile_id != profile.id:
                    raise PolicyValidationError(("规则不属于当前用户。",))
                record.rule_type = draft.rule_type.value
                record.subject_key = self._subject_key(draft)
                record.subject_label = self._subject_label(session, draft)
                record.threshold = draft.threshold
                record.tolerance = draft.tolerance
                record.warning_ratio = draft.warning_ratio
                record.enabled = draft.enabled
                session.flush()
                retained.add(record.id)
            for rule_id in set(existing) - retained:
                session.execute(delete(PolicyRuleRecord).where(PolicyRuleRecord.id == rule_id))
            refreshed_profile = session.get(
                ProfileRecord, profile.id, populate_existing=True
            )
            assert refreshed_profile is not None
            return PolicySet(
                revision=refreshed_profile.policy_revision,
                rules=tuple(PolicyRepository(session).rules(profile.id)),
            )

    @staticmethod
    def _subject_key(draft: PolicyRuleDraft) -> str:
        if draft.rule_type == PolicyRuleType.CASH_MIN_WEIGHT:
            return "cash"
        return draft.subject_key

    @staticmethod
    def _subject_label(session: Session, draft: PolicyRuleDraft) -> str:
        if draft.rule_type == PolicyRuleType.CASH_MIN_WEIGHT:
            return "现金"
        if draft.rule_type == PolicyRuleType.INSTRUMENT_MAX_WEIGHT:
            profile = PortfolioRepository(session).get_or_create_profile()
            facts = PortfolioRepository(session).load(profile.id)
            instrument = next(
                item for item in facts.positions if str(item.instrument_id) == draft.subject_key
            )
            return f"{instrument.name} ({instrument.code})"
        labels = {
            AssetClass.EQUITY: "权益",
            AssetClass.FIXED_INCOME: "固收",
            AssetClass.MIXED: "混合",
            AssetClass.CASH: "现金",
            AssetClass.COMMODITY: "商品",
            AssetClass.OTHER: "其他",
        }
        return labels[AssetClass(draft.subject_key)]

    @staticmethod
    def _validate(
        session: Session,
        profile_id: int,
        drafts: tuple[PolicyRuleDraft, ...],
    ) -> list[str]:
        messages: list[str] = []
        keys: set[tuple[PolicyRuleType, str]] = set()
        held_ids = {
            str(item.instrument_id)
            for item in PortfolioRepository(session).load(profile_id).positions
        }
        for draft in drafts:
            subject_key = PolicyService._subject_key(draft)
            key = (draft.rule_type, subject_key)
            if key in keys:
                messages.append("同一对象不能重复设置同类规则。")
            keys.add(key)
            if not Decimal(0) <= draft.threshold <= Decimal(1):
                messages.append("边界必须在 0% 到 100% 之间。")
            if not Decimal(0) < draft.warning_ratio < Decimal(1):
                messages.append("关注缓冲比例必须大于 0% 且小于 100%。")
            is_target = draft.rule_type == PolicyRuleType.ASSET_CLASS_TARGET_WEIGHT
            if is_target and (
                draft.tolerance is None
                or not Decimal(0) < draft.tolerance <= Decimal(1)
            ):
                messages.append("目标配置规则必须设置有效容差。")
            if not is_target and draft.tolerance is not None:
                messages.append("只有目标配置规则可以设置容差。")
            if (
                draft.rule_type == PolicyRuleType.INSTRUMENT_MAX_WEIGHT
                and draft.subject_key not in held_ids
            ):
                messages.append("单一标的规则只能选择当前持仓标的。")
            if draft.rule_type in {
                PolicyRuleType.ASSET_CLASS_MAX_WEIGHT,
                PolicyRuleType.ASSET_CLASS_TARGET_WEIGHT,
            }:
                try:
                    AssetClass(draft.subject_key)
                except ValueError:
                    messages.append("未知的资产类别。")
        return messages


class RiskEvaluationService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def evaluate(self, snapshot: StoredRiskSnapshot) -> StoredRiskEvaluation:
        if snapshot.analysis is None:
            raise ValueError("A fresh in-memory risk analysis is required.")
        calculated_at = datetime.now(UTC)
        with self.session_factory.begin() as session:
            repository = PolicyRepository(session)
            profile = session.get(ProfileRecord, snapshot.profile_id)
            if profile is None:
                raise RuntimeError("Risk snapshot profile no longer exists.")
            rules = tuple(
                _domain_rule(item)
                for item in repository.rules(profile.id)
                if item.enabled
            )
            evaluation = evaluate_policy(snapshot.analysis, rules)
            previous = repository.latest_evaluation(profile.id)
            record = repository.add_evaluation(
                RiskEvaluationRecord(
                    profile_id=profile.id,
                    risk_snapshot_id=snapshot.snapshot_id,
                    policy_revision=profile.policy_revision,
                    state=evaluation.state.value,
                    calculated_at=calculated_at,
                    methodology_version=evaluation.methodology_version,
                    findings_json=_findings_json(evaluation),
                )
            )
            self._create_events(repository, record, evaluation.findings, previous)
            return StoredRiskEvaluation(
                evaluation_id=record.id,
                risk_snapshot_id=record.risk_snapshot_id,
                policy_revision=record.policy_revision,
                state=RiskState(record.state),
                calculated_at=calculated_at,
                findings_json=record.findings_json,
            )

    def current_for_snapshot(self, snapshot_id: int) -> StoredRiskEvaluation | None:
        with self.session_factory() as session:
            record = PolicyRepository(session).evaluation_for_snapshot(snapshot_id)
            if record is None:
                return None
            calculated_at = record.calculated_at
            if calculated_at.tzinfo is None:
                calculated_at = calculated_at.replace(tzinfo=UTC)
            return StoredRiskEvaluation(
                evaluation_id=record.id,
                risk_snapshot_id=record.risk_snapshot_id,
                policy_revision=record.policy_revision,
                state=RiskState(record.state),
                calculated_at=calculated_at,
                findings_json=record.findings_json,
            )

    @staticmethod
    def _create_events(
        repository: PolicyRepository,
        evaluation: RiskEvaluationRecord,
        findings: tuple[RiskFinding, ...],
        previous: RiskEvaluationRecord | None,
    ) -> None:
        previous_states: dict[str, str] = {}
        if previous is not None:
            raw: Any = json.loads(previous.findings_json)
            previous_states = {
                item["finding_key"]: item["state"] for item in raw.get("findings", [])
            }
        for finding in findings:
            old_state = previous_states.get(finding.finding_key)
            new_state = finding.state.value
            if old_state == new_state or (old_state is None and finding.state == RiskState.WITHIN):
                continue
            if old_state is None:
                event_type = "detected"
            elif finding.state == RiskState.WITHIN:
                event_type = "recovered"
            else:
                event_type = "state_changed"
            dedupe_key = hashlib.sha256(
                f"{evaluation.id}:{finding.finding_key}:{new_state}".encode()
            ).hexdigest()
            repository.add_event(
                InsightEventRecord(
                    profile_id=evaluation.profile_id,
                    evaluation_id=evaluation.id,
                    finding_key=finding.finding_key,
                    event_type=event_type,
                    from_state=old_state,
                    to_state=new_state,
                    severity=new_state,
                    dedupe_key=dedupe_key,
                    occurred_at=evaluation.calculated_at,
                    payload_json=json.dumps(
                        asdict(finding),
                        default=_json_default,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                )
            )

    def events(self) -> tuple[StoredInsightEvent, ...]:
        with self.session_factory.begin() as session:
            profile = PortfolioRepository(session).get_or_create_profile()
            return tuple(
                StoredInsightEvent(
                    event_id=item.id,
                    event_type=item.event_type,
                    finding_key=item.finding_key,
                    from_state=item.from_state,
                    to_state=item.to_state,
                    severity=item.severity,
                    occurred_at=(
                        item.occurred_at
                        if item.occurred_at.tzinfo is not None
                        else item.occurred_at.replace(tzinfo=UTC)
                    ),
                    payload_json=item.payload_json,
                )
                for item in PolicyRepository(session).events(profile.id)
            )
