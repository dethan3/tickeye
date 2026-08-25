"""Pure evaluation of explicit user-owned portfolio risk boundaries."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from tickeye.domain.risk import RiskAnalysis, RiskCalculationStatus


class PolicyRuleType(StrEnum):
    INSTRUMENT_MAX_WEIGHT = "instrument_max_weight"
    ASSET_CLASS_MAX_WEIGHT = "asset_class_max_weight"
    CASH_MIN_WEIGHT = "cash_min_weight"
    ASSET_CLASS_TARGET_WEIGHT = "asset_class_target_weight"


class RiskState(StrEnum):
    UNKNOWN = "unknown"
    WITHIN = "within"
    WATCH = "watch"
    BREACHED = "breached"


@dataclass(frozen=True, slots=True)
class PolicyRule:
    rule_id: int
    rule_type: PolicyRuleType
    subject_key: str
    subject_label: str
    threshold: Decimal
    tolerance: Decimal | None
    warning_ratio: Decimal

    @property
    def finding_key(self) -> str:
        return f"policy:{self.rule_id}"


@dataclass(frozen=True, slots=True)
class RiskFinding:
    finding_key: str
    dimension: str
    state: RiskState
    title: str
    message: str
    current_value: Decimal | None
    boundary_low: Decimal | None
    boundary_high: Decimal | None
    contributor_key: str | None
    contributor_label: str | None
    policy_rule_id: int | None


@dataclass(frozen=True, slots=True)
class RiskEvaluation:
    state: RiskState
    findings: tuple[RiskFinding, ...]
    methodology_version: str = "policy-evaluation-v1"


def _max_state(findings: tuple[RiskFinding, ...]) -> RiskState:
    priority = {
        RiskState.WITHIN: 0,
        RiskState.WATCH: 1,
        RiskState.UNKNOWN: 2,
        RiskState.BREACHED: 3,
    }
    return max((item.state for item in findings), key=priority.__getitem__)


def _max_rule_state(current: Decimal, limit: Decimal, warning: Decimal) -> RiskState:
    if current > limit:
        return RiskState.BREACHED
    if current >= limit * (Decimal(1) - warning):
        return RiskState.WATCH
    return RiskState.WITHIN


def _min_rule_state(current: Decimal, limit: Decimal, warning: Decimal) -> RiskState:
    if current < limit:
        return RiskState.BREACHED
    if current <= limit * (Decimal(1) + warning):
        return RiskState.WATCH
    return RiskState.WITHIN


def _target_rule_state(
    current: Decimal,
    target: Decimal,
    tolerance: Decimal,
    warning: Decimal,
) -> RiskState:
    distance = abs(current - target)
    if distance > tolerance:
        return RiskState.BREACHED
    if distance >= tolerance * (Decimal(1) - warning):
        return RiskState.WATCH
    return RiskState.WITHIN


def _finding_for_rule(analysis: RiskAnalysis, rule: PolicyRule) -> RiskFinding:
    instrument = {item.key: item for item in analysis.instrument_exposures}
    asset_class = {item.key: item for item in analysis.asset_class_exposures}
    current: Decimal | None
    contributor_label = rule.subject_label
    if rule.rule_type == PolicyRuleType.INSTRUMENT_MAX_WEIGHT:
        exposure = instrument.get(rule.subject_key)
        current = exposure.weight if exposure is not None else Decimal(0)
        state = _max_rule_state(current, rule.threshold, rule.warning_ratio)
        low, high = None, rule.threshold
        dimension = "instrument_concentration"
        title = f"{rule.subject_label} 单一标的上限"
    elif rule.rule_type == PolicyRuleType.ASSET_CLASS_MAX_WEIGHT:
        exposure = asset_class.get(rule.subject_key)
        current = exposure.weight if exposure is not None else Decimal(0)
        state = _max_rule_state(current, rule.threshold, rule.warning_ratio)
        low, high = None, rule.threshold
        dimension = "asset_class_concentration"
        title = f"{rule.subject_label} 资产类别上限"
    elif rule.rule_type == PolicyRuleType.CASH_MIN_WEIGHT:
        exposure = asset_class.get("cash")
        current = exposure.weight if exposure is not None else Decimal(0)
        state = _min_rule_state(current, rule.threshold, rule.warning_ratio)
        low, high = rule.threshold, None
        dimension = "cash_liquidity"
        title = "现金最低比例"
        contributor_label = "现金"
    else:
        exposure = asset_class.get(rule.subject_key)
        current = exposure.weight if exposure is not None else Decimal(0)
        tolerance = rule.tolerance or Decimal(0)
        state = _target_rule_state(
            current, rule.threshold, tolerance, rule.warning_ratio
        )
        low = max(Decimal(0), rule.threshold - tolerance)
        high = min(Decimal(1), rule.threshold + tolerance)
        dimension = "target_allocation"
        title = f"{rule.subject_label} 目标配置"

    messages = {
        RiskState.WITHIN: "当前值位于用户设定边界内。",
        RiskState.WATCH: "当前值已进入用户设定边界前的关注区。",
        RiskState.BREACHED: "当前值已经越过用户设定边界。",
        RiskState.UNKNOWN: "当前数据不足，无法检查这条规则。",
    }
    return RiskFinding(
        finding_key=rule.finding_key,
        dimension=dimension,
        state=state,
        title=title,
        message=messages[state],
        current_value=current,
        boundary_low=low,
        boundary_high=high,
        contributor_key=rule.subject_key,
        contributor_label=contributor_label,
        policy_rule_id=rule.rule_id,
    )


def evaluate_policy(
    analysis: RiskAnalysis,
    rules: tuple[PolicyRule, ...],
) -> RiskEvaluation:
    data_state = (
        RiskState.UNKNOWN
        if analysis.status == RiskCalculationStatus.UNKNOWN
        else RiskState.WITHIN
    )
    findings: list[RiskFinding] = [
        RiskFinding(
            finding_key="system:data_reliability",
            dimension="data_reliability",
            state=data_state,
            title="风险计算数据可信度",
            message=(
                "数据不足或陈旧，历史市场风险无法可靠计算。"
                if data_state == RiskState.UNKNOWN
                else "数据满足当前历史风险计算的最低要求。"
            ),
            current_value=analysis.coverage.historical_value_ratio,
            boundary_low=None,
            boundary_high=None,
            contributor_key=None,
            contributor_label=None,
            policy_rule_id=None,
        )
    ]
    if not rules:
        findings.append(
            RiskFinding(
                finding_key="system:policy_coverage",
                dimension="policy_coverage",
                state=RiskState.UNKNOWN,
                title="用户风险边界",
                message="尚未设置风险规则，系统不能判断组合是否处于可接受边界内。",
                current_value=None,
                boundary_low=None,
                boundary_high=None,
                contributor_key=None,
                contributor_label=None,
                policy_rule_id=None,
            )
        )
    elif analysis.coverage.valued_positions < analysis.coverage.total_positions:
        findings.extend(
            RiskFinding(
                finding_key=rule.finding_key,
                dimension="policy_rule",
                state=RiskState.UNKNOWN,
                title=rule.subject_label,
                message="组合估值不完整，无法可靠检查这条权重规则。",
                current_value=None,
                boundary_low=None,
                boundary_high=None,
                contributor_key=rule.subject_key,
                contributor_label=rule.subject_label,
                policy_rule_id=rule.rule_id,
            )
            for rule in rules
        )
    else:
        findings.extend(_finding_for_rule(analysis, rule) for rule in rules)
    frozen = tuple(findings)
    return RiskEvaluation(state=_max_state(frozen), findings=frozen)
