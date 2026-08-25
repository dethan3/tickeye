from dataclasses import replace
from decimal import Decimal

from tests.unit.test_risk import TODAY, position
from tickeye.domain.policy import (
    PolicyRule,
    PolicyRuleType,
    RiskState,
    evaluate_policy,
)
from tickeye.domain.risk import (
    Exposure,
    RiskCalculationStatus,
    analyze_portfolio_risk,
)


def analysis_with_weight(weight: str = "0.50"):
    base = analyze_portfolio_risk(
        (position(),), calculated_on=TODAY, minimum_observations=4
    )
    exposure = Exposure(
        key="1",
        label="沪深300ETF",
        value=Decimal("100"),
        weight=Decimal(weight),
    )
    return replace(base, instrument_exposures=(exposure,))


def max_rule() -> PolicyRule:
    return PolicyRule(
        rule_id=1,
        rule_type=PolicyRuleType.INSTRUMENT_MAX_WEIGHT,
        subject_key="1",
        subject_label="沪深300ETF",
        threshold=Decimal("0.50"),
        tolerance=None,
        warning_ratio=Decimal("0.20"),
    )


def analysis_with_asset_weight(asset_class: str, weight: str):
    analysis = analysis_with_weight()
    exposure = Exposure(
        key=asset_class,
        label=asset_class,
        value=Decimal("100"),
        weight=Decimal(weight),
    )
    return replace(analysis, asset_class_exposures=(exposure,))


def test_max_boundary_equality_is_watch_not_breached() -> None:
    assert evaluate_policy(analysis_with_weight("0.39"), (max_rule(),)).state == RiskState.WITHIN
    assert evaluate_policy(analysis_with_weight("0.40"), (max_rule(),)).state == RiskState.WATCH
    assert evaluate_policy(analysis_with_weight("0.50"), (max_rule(),)).state == RiskState.WATCH
    assert evaluate_policy(analysis_with_weight("0.51"), (max_rule(),)).state == RiskState.BREACHED


def test_cash_minimum_equality_is_watch_not_breached() -> None:
    rule = PolicyRule(
        rule_id=2,
        rule_type=PolicyRuleType.CASH_MIN_WEIGHT,
        subject_key="cash",
        subject_label="现金",
        threshold=Decimal("0.10"),
        tolerance=None,
        warning_ratio=Decimal("0.20"),
    )

    assert (
        evaluate_policy(analysis_with_asset_weight("cash", "0.13"), (rule,)).state
        == RiskState.WITHIN
    )
    assert (
        evaluate_policy(analysis_with_asset_weight("cash", "0.12"), (rule,)).state
        == RiskState.WATCH
    )
    assert (
        evaluate_policy(analysis_with_asset_weight("cash", "0.10"), (rule,)).state
        == RiskState.WATCH
    )
    assert (
        evaluate_policy(analysis_with_asset_weight("cash", "0.09"), (rule,)).state
        == RiskState.BREACHED
    )


def test_target_tolerance_equality_is_watch_not_breached() -> None:
    rule = PolicyRule(
        rule_id=3,
        rule_type=PolicyRuleType.ASSET_CLASS_TARGET_WEIGHT,
        subject_key="equity",
        subject_label="权益",
        threshold=Decimal("0.50"),
        tolerance=Decimal("0.10"),
        warning_ratio=Decimal("0.20"),
    )

    assert (
        evaluate_policy(analysis_with_asset_weight("equity", "0.50"), (rule,)).state
        == RiskState.WITHIN
    )
    assert (
        evaluate_policy(analysis_with_asset_weight("equity", "0.58"), (rule,)).state
        == RiskState.WATCH
    )
    assert (
        evaluate_policy(analysis_with_asset_weight("equity", "0.60"), (rule,)).state
        == RiskState.WATCH
    )
    assert (
        evaluate_policy(analysis_with_asset_weight("equity", "0.61"), (rule,)).state
        == RiskState.BREACHED
    )


def test_confirmed_breach_takes_priority_over_unknown_data() -> None:
    analysis = replace(
        analysis_with_weight("0.60"), status=RiskCalculationStatus.UNKNOWN
    )

    evaluation = evaluate_policy(analysis, (max_rule(),))

    assert evaluation.state == RiskState.BREACHED
    assert {item.state for item in evaluation.findings} == {
        RiskState.UNKNOWN,
        RiskState.BREACHED,
    }


def test_no_user_rules_never_means_within() -> None:
    evaluation = evaluate_policy(analysis_with_weight(), ())

    assert evaluation.state == RiskState.UNKNOWN
    assert evaluation.findings[-1].finding_key == "system:policy_coverage"
