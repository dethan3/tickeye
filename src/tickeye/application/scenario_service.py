"""Create frozen Scenario experiments and immutable before/after comparisons."""

import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from tickeye.application.risk_service import FrozenRiskInputs, RiskService
from tickeye.domain.enums import AssetClass, InstrumentType
from tickeye.domain.policy import (
    PolicyRule,
    PolicyRuleType,
    RiskEvaluation,
    RiskState,
    evaluate_policy,
)
from tickeye.domain.risk import (
    HistoricalValue,
    RiskAnalysis,
    RiskCalculationStatus,
    RiskPositionInput,
    analyze_portfolio_risk,
)
from tickeye.domain.scenario import (
    ScenarioOperation,
    ScenarioOperationError,
    ScenarioOperationType,
    StressAssumption,
    apply_scenario_operations,
    fixed_comparison_dates,
    stressed_portfolio_value,
)
from tickeye.infrastructure.db import (
    PolicyRuleRecord,
    ProfileRecord,
    ScenarioComparisonRecord,
    ScenarioOperationRecord,
    ScenarioRecord,
)
from tickeye.infrastructure.repositories import (
    PolicyRepository,
    PortfolioRepository,
    ScenarioRepository,
    WatchlistRepository,
)

SCENARIO_METHODOLOGY_VERSION = "scenario-comparison-v1"


class ScenarioNotFoundError(Exception):
    pass


class ScenarioValidationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class ScenarioOperationDraft:
    operation_type: ScenarioOperationType
    instrument_id: int | None
    amount: Decimal | None
    target_weight: Decimal | None
    estimated_cost: Decimal


@dataclass(frozen=True, slots=True)
class ScenarioSummary:
    scenario_id: int
    name: str
    status: str
    base_portfolio_revision: int
    candidate_instrument_id: int | None
    operation_count: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class StoredScenarioComparison:
    comparison_id: int
    scenario_id: int
    operation_count: int
    calculated_at: datetime
    payload_json: str


def _aware_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _json_default(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return str(value.value)
    if is_dataclass(value):
        return asdict(value)  # type: ignore[arg-type]
    raise TypeError(f"Unsupported Scenario value: {type(value).__name__}")


def _json(value: object) -> str:
    return json.dumps(
        value,
        default=_json_default,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _serialize_inputs(inputs: FrozenRiskInputs) -> str:
    return _json(asdict(inputs)["positions"])


def _parse_inputs(payload: str) -> tuple[RiskPositionInput, ...]:
    raw: Any = json.loads(payload)
    if not isinstance(raw, list):
        raise RuntimeError("Stored Scenario inputs are invalid.")
    positions: list[RiskPositionInput] = []
    for item in raw:
        if not isinstance(item, dict):
            raise RuntimeError("Stored Scenario position is invalid.")
        history = tuple(
            HistoricalValue(
                observed_on=date.fromisoformat(point["observed_on"]),
                value=Decimal(point["value"]),
            )
            for point in item["history"]
        )
        positions.append(
            RiskPositionInput(
                position_id=int(item["position_id"]),
                instrument_id=int(item["instrument_id"]),
                account_name=str(item["account_name"]),
                code=str(item["code"]),
                name=str(item["name"]),
                instrument_type=InstrumentType(item["instrument_type"]),
                asset_class=AssetClass(item["asset_class"]),
                quantity=(
                    Decimal(item["quantity"]) if item["quantity"] is not None else None
                ),
                manual_value=(
                    Decimal(item["manual_value"])
                    if item["manual_value"] is not None
                    else None
                ),
                position_as_of=date.fromisoformat(item["position_as_of"]),
                history=history,
                freshness_limit_days=item["freshness_limit_days"],
                last_refresh_failed=bool(item["last_refresh_failed"]),
                limitations=tuple(item["limitations"]),
            )
        )
    return tuple(positions)


def _parse_assumptions(payload: str) -> tuple[StressAssumption, ...]:
    raw: Any = json.loads(payload)
    return tuple(
        StressAssumption(
            asset_class=AssetClass(item["asset_class"]),
            shock=Decimal(item["shock"]),
        )
        for item in raw
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


def _domain_operation(record: ScenarioOperationRecord) -> ScenarioOperation:
    return ScenarioOperation(
        sequence=record.sequence,
        operation_type=ScenarioOperationType(record.operation_type),
        instrument_id=record.instrument_id,
        amount=record.amount,
        target_weight=record.target_weight,
        estimated_cost=record.estimated_cost,
    )


def _metric_changes(before: RiskAnalysis, after: RiskAnalysis) -> tuple[list[str], list[str]]:
    improvements: list[str] = []
    worsenings: list[str] = []

    def compare(label: str, old: Decimal | None, new: Decimal | None) -> None:
        if old is None or new is None or old == new:
            return
        message = f"{label}从 {old * 100:.2f}% 变为 {new * 100:.2f}%。"
        (improvements if new < old else worsenings).append(message)

    compare("最大单一标的权重", before.max_instrument_weight, after.max_instrument_weight)
    compare("年化波动率", before.metrics.annualized_volatility, after.metrics.annualized_volatility)
    compare("下行波动率", before.metrics.downside_volatility, after.metrics.downside_volatility)
    compare("模拟最大回撤", before.metrics.max_drawdown, after.metrics.max_drawdown)
    return improvements, worsenings


def _policy_change(
    before: RiskEvaluation,
    after: RiskEvaluation,
    improvements: list[str],
    worsenings: list[str],
) -> None:
    comparable = {
        RiskState.WITHIN: 0,
        RiskState.WATCH: 1,
        RiskState.BREACHED: 2,
    }
    if before.state not in comparable or after.state not in comparable:
        return
    if comparable[after.state] < comparable[before.state]:
        improvements.append(
            f"用户规则汇总状态从 {before.state.value} 改善为 {after.state.value}。"
        )
    elif comparable[after.state] > comparable[before.state]:
        worsenings.append(
            f"用户规则汇总状态从 {before.state.value} 恶化为 {after.state.value}。"
        )


def _confidence(before: RiskAnalysis, after: RiskAnalysis) -> str:
    if RiskCalculationStatus.UNKNOWN in {before.status, after.status}:
        return "low"
    if (
        before.coverage.valued_position_ratio == Decimal(1)
        and after.coverage.valued_position_ratio == Decimal(1)
        and before.status == RiskCalculationStatus.AVAILABLE
        and after.status == RiskCalculationStatus.AVAILABLE
    ):
        return "high"
    return "medium"


def _comparison_payload(
    scenario: ScenarioRecord,
    operations: tuple[ScenarioOperation, ...],
    rules: tuple[PolicyRule, ...],
    policy_revision: int,
) -> dict[str, object]:
    base = _parse_inputs(scenario.base_inputs_json)
    assumptions = _parse_assumptions(scenario.assumptions_json)
    try:
        applied = apply_scenario_operations(base, operations)
    except ScenarioOperationError as error:
        raise ScenarioValidationError(error.code, error.message) from error
    fixed_dates = fixed_comparison_dates(base)
    calculated_on = _aware_utc(scenario.created_at).date()
    before = analyze_portfolio_risk(
        base,
        calculated_on=calculated_on,
        fixed_window_dates=fixed_dates,
    )
    after = analyze_portfolio_risk(
        applied.positions,
        calculated_on=calculated_on,
        fixed_window_dates=fixed_dates,
    )
    before_policy = evaluate_policy(before, rules)
    after_policy = evaluate_policy(after, rules)
    improvements, worsenings = _metric_changes(before, after)
    _policy_change(before_policy, after_policy, improvements, worsenings)
    objections: list[str] = []
    if after.status == RiskCalculationStatus.UNKNOWN:
        objections.append("操作后数据仍不足，历史风险指标不能可靠比较。")
    if after_policy.state == RiskState.BREACHED:
        objections.append("操作后的组合仍有用户规则处于 BREACHED。")
    if worsenings:
        objections.append(f"至少一项风险事实恶化：{worsenings[0]}")
    if applied.total_estimated_cost > 0:
        objections.append(f"方案需要支付用户估计的交易成本 {applied.total_estimated_cost} 元。")
    objections.append("历史风险回放和手工压力假设都不能预测未来收益。")
    warnings = [
        "这是未执行的方案比较，不会修改实际持仓。",
        "before/after 使用同一份冻结行情和相同历史窗口。",
    ]
    if assumptions:
        warnings.append("压力结果来自用户手工假设，不是市场预测。")
    return {
        "scenario_id": scenario.id,
        "name": scenario.name,
        "base_portfolio_revision": scenario.base_portfolio_revision,
        "candidate_instrument_id": scenario.candidate_instrument_id,
        "policy_revision": policy_revision,
        "operation_count": len(operations),
        "operations": operations,
        "comparison_window": {
            "start": fixed_dates[0] if fixed_dates else None,
            "end": fixed_dates[-1] if fixed_dates else None,
            "observations": len(fixed_dates),
        },
        "before": {
            "analysis": before,
            "policy": before_policy,
            "stressed_value": stressed_portfolio_value(base, assumptions),
        },
        "after": {
            "analysis": after,
            "policy": after_policy,
            "stressed_value": stressed_portfolio_value(applied.positions, assumptions),
        },
        "stress_assumptions": assumptions,
        "total_estimated_cost": applied.total_estimated_cost,
        "summary": {
            "confidence": _confidence(before, after),
            "improvements": improvements,
            "worsenings": worsenings,
            "objections": objections,
        },
        "warnings": warnings,
        "methodology_version": SCENARIO_METHODOLOGY_VERSION,
    }


class ScenarioService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        risk_service: RiskService,
    ) -> None:
        self.session_factory = session_factory
        self.risk_service = risk_service

    def create(
        self,
        name: str,
        assumptions: tuple[StressAssumption, ...],
        candidate_instrument_id: int | None = None,
    ) -> tuple[ScenarioSummary, StoredScenarioComparison]:
        clean_name = name.strip()
        if not clean_name:
            raise ScenarioValidationError("invalid_name", "方案名称不能为空。")
        self._validate_assumptions(assumptions)
        if candidate_instrument_id is not None:
            with self.session_factory.begin() as session:
                profile = PortfolioRepository(session).get_or_create_profile()
                if not WatchlistRepository(session).is_watched(
                    profile.id, candidate_instrument_id
                ):
                    raise ScenarioValidationError(
                        "candidate_not_watched",
                        "候选标的必须来自当前用户的观察列表。",
                    )
        frozen = self.risk_service.freeze_current_inputs(
            (candidate_instrument_id,) if candidate_instrument_id is not None else ()
        )
        now = datetime.now(UTC)
        with self.session_factory.begin() as session:
            repository = ScenarioRepository(session)
            scenario = repository.add(
                ScenarioRecord(
                    profile_id=frozen.profile_id,
                    name=clean_name,
                    status="evaluated",
                    base_portfolio_revision=frozen.portfolio_revision,
                    candidate_instrument_id=candidate_instrument_id,
                    base_inputs_json=_serialize_inputs(frozen),
                    assumptions_json=_json(assumptions),
                    created_at=now,
                    updated_at=now,
                )
            )
            comparison = self._save_comparison(session, scenario, ())
            return self._summary(repository, scenario), comparison

    def append_operation(
        self,
        scenario_id: int,
        draft: ScenarioOperationDraft,
    ) -> StoredScenarioComparison:
        with self.session_factory.begin() as session:
            profile = PortfolioRepository(session).get_or_create_profile()
            repository = ScenarioRepository(session)
            scenario = repository.get(profile.id, scenario_id)
            if scenario is None:
                raise ScenarioNotFoundError
            existing = tuple(
                _domain_operation(item) for item in repository.operations(scenario.id)
            )
            operation = ScenarioOperation(
                sequence=len(existing) + 1,
                operation_type=draft.operation_type,
                instrument_id=draft.instrument_id,
                amount=draft.amount,
                target_weight=draft.target_weight,
                estimated_cost=draft.estimated_cost,
            )
            operations = (*existing, operation)
            comparison_payload = self._build_comparison(session, scenario, operations)
            repository.add_operation(
                ScenarioOperationRecord(
                    scenario_id=scenario.id,
                    sequence=operation.sequence,
                    operation_type=operation.operation_type.value,
                    instrument_id=operation.instrument_id,
                    amount=operation.amount,
                    target_weight=operation.target_weight,
                    estimated_cost=operation.estimated_cost,
                    created_at=datetime.now(UTC),
                )
            )
            scenario.updated_at = datetime.now(UTC)
            return self._persist_comparison(
                repository,
                scenario,
                len(operations),
                comparison_payload,
            )

    def list(self) -> tuple[ScenarioSummary, ...]:
        with self.session_factory.begin() as session:
            profile = PortfolioRepository(session).get_or_create_profile()
            repository = ScenarioRepository(session)
            return tuple(
                self._summary(repository, scenario)
                for scenario in repository.all(profile.id)
            )

    def comparison(self, scenario_id: int) -> StoredScenarioComparison:
        with self.session_factory.begin() as session:
            profile = PortfolioRepository(session).get_or_create_profile()
            repository = ScenarioRepository(session)
            scenario = repository.get(profile.id, scenario_id)
            if scenario is None:
                raise ScenarioNotFoundError
            comparison = repository.latest_comparison(scenario.id)
            if comparison is None:
                raise RuntimeError("Scenario comparison disappeared.")
            return self._stored_comparison(comparison)

    @staticmethod
    def _validate_assumptions(assumptions: tuple[StressAssumption, ...]) -> None:
        classes: set[AssetClass] = set()
        for assumption in assumptions:
            if assumption.asset_class in classes:
                raise ScenarioValidationError(
                    "duplicate_stress", "同一资产类别只能设置一个压力假设。"
                )
            classes.add(assumption.asset_class)
            if not Decimal(-1) < assumption.shock <= Decimal(0):
                raise ScenarioValidationError(
                    "invalid_stress", "压力幅度必须大于 -100% 且不高于 0%。"
                )

    @staticmethod
    def _summary(
        repository: ScenarioRepository, scenario: ScenarioRecord
    ) -> ScenarioSummary:
        return ScenarioSummary(
            scenario_id=scenario.id,
            name=scenario.name,
            status=scenario.status,
            base_portfolio_revision=scenario.base_portfolio_revision,
            candidate_instrument_id=scenario.candidate_instrument_id,
            operation_count=len(repository.operations(scenario.id)),
            created_at=_aware_utc(scenario.created_at),
            updated_at=_aware_utc(scenario.updated_at),
        )

    @staticmethod
    def _build_comparison(
        session: Session,
        scenario: ScenarioRecord,
        operations: tuple[ScenarioOperation, ...],
    ) -> dict[str, object]:
        profile = session.get(ProfileRecord, scenario.profile_id)
        if profile is None:
            raise RuntimeError("Scenario profile disappeared.")
        rules = tuple(
            _domain_rule(record)
            for record in PolicyRepository(session).rules(scenario.profile_id)
            if record.enabled
        )
        return _comparison_payload(
            scenario,
            operations,
            rules,
            profile.policy_revision,
        )

    def _save_comparison(
        self,
        session: Session,
        scenario: ScenarioRecord,
        operations: tuple[ScenarioOperation, ...],
    ) -> StoredScenarioComparison:
        payload = self._build_comparison(session, scenario, operations)
        return self._persist_comparison(
            ScenarioRepository(session), scenario, len(operations), payload
        )

    @staticmethod
    def _persist_comparison(
        repository: ScenarioRepository,
        scenario: ScenarioRecord,
        operation_count: int,
        payload: dict[str, object],
    ) -> StoredScenarioComparison:
        calculated_at = datetime.now(UTC)
        record = repository.add_comparison(
            ScenarioComparisonRecord(
                scenario_id=scenario.id,
                operation_count=operation_count,
                calculated_at=calculated_at,
                methodology_version=SCENARIO_METHODOLOGY_VERSION,
                payload_json=_json(payload),
            )
        )
        return StoredScenarioComparison(
            comparison_id=record.id,
            scenario_id=scenario.id,
            operation_count=operation_count,
            calculated_at=calculated_at,
            payload_json=record.payload_json,
        )

    @staticmethod
    def _stored_comparison(
        record: ScenarioComparisonRecord,
    ) -> StoredScenarioComparison:
        return StoredScenarioComparison(
            comparison_id=record.id,
            scenario_id=record.scenario_id,
            operation_count=record.operation_count,
            calculated_at=_aware_utc(record.calculated_at),
            payload_json=record.payload_json,
        )
