from dataclasses import replace
from decimal import Decimal

import pytest

from tests.unit.test_risk import TODAY, position
from tickeye.domain.enums import AssetClass, InstrumentType
from tickeye.domain.risk import analyze_portfolio_risk
from tickeye.domain.scenario import (
    ScenarioOperation,
    ScenarioOperationError,
    ScenarioOperationType,
    StressAssumption,
    apply_scenario_operations,
    fixed_comparison_dates,
    stressed_portfolio_value,
)


def portfolio_inputs():
    risky = position()
    cash = position(
        position_id=2,
        instrument_id=2,
        code="CASH-CNY",
        instrument_type=InstrumentType.CASH,
        asset_class=AssetClass.CASH,
        quantity=None,
        manual_value="1000",
        prices=(),
        freshness_limit_days=None,
    )
    return risky, cash


def operation(
    operation_type: ScenarioOperationType,
    *,
    amount: str | None = None,
    target_weight: str | None = None,
    cost: str = "0",
) -> ScenarioOperation:
    return ScenarioOperation(
        sequence=1,
        operation_type=operation_type,
        instrument_id=1,
        amount=Decimal(amount) if amount is not None else None,
        target_weight=Decimal(target_weight) if target_weight is not None else None,
        estimated_cost=Decimal(cost),
    )


def test_buy_uses_cash_and_never_mutates_actual_positions() -> None:
    base = portfolio_inputs()

    result = apply_scenario_operations(
        base,
        (operation(ScenarioOperationType.BUY, amount="100", cost="1"),),
    )
    analysis = analyze_portfolio_risk(
        result.positions,
        calculated_on=TODAY,
        minimum_observations=4,
        fixed_window_dates=fixed_comparison_dates(base),
    )

    assert base[0].quantity == Decimal("10")
    assert base[1].manual_value == Decimal("1000")
    assert result.positions[1].manual_value == Decimal("899.00")
    assert analysis.coverage.known_portfolio_value == Decimal("1989.00")
    assert result.total_estimated_cost == Decimal("1.00")


def test_ordered_sell_then_buy_can_reuse_sale_proceeds() -> None:
    base = portfolio_inputs()
    operations = (
        operation(ScenarioOperationType.SELL, amount="500"),
        ScenarioOperation(
            sequence=2,
            operation_type=ScenarioOperationType.BUY,
            instrument_id=1,
            amount=Decimal("1200"),
            target_weight=None,
            estimated_cost=Decimal("0"),
        ),
    )

    result = apply_scenario_operations(base, operations)

    assert result.positions[1].manual_value == Decimal("300.00")


def test_multiple_cash_accounts_are_treated_as_one_nonnegative_pool() -> None:
    risky, cash = portfolio_inputs()
    second_cash = position(
        position_id=3,
        instrument_id=3,
        code="CASH-SECOND",
        instrument_type=InstrumentType.CASH,
        asset_class=AssetClass.CASH,
        quantity=None,
        manual_value="500",
        prices=(),
        freshness_limit_days=None,
    )
    first_cash = replace(cash, manual_value=Decimal("500"))

    result = apply_scenario_operations(
        (risky, first_cash, second_cash),
        (operation(ScenarioOperationType.BUY, amount="800"),),
    )

    cash_values = [
        item.manual_value
        for item in result.positions
        if item.instrument_type == InstrumentType.CASH
    ]
    assert cash_values == [Decimal("200.00"), Decimal("0.00")]


def test_oversell_and_negative_cash_are_rejected() -> None:
    base = portfolio_inputs()

    with pytest.raises(ScenarioOperationError, match="超过当前持仓") as oversell:
        apply_scenario_operations(
            base,
            (operation(ScenarioOperationType.SELL, amount="1000"),),
        )
    with pytest.raises(ScenarioOperationError, match="现金") as negative_cash:
        apply_scenario_operations(
            base,
            (operation(ScenarioOperationType.BUY, amount="1001"),),
        )

    assert oversell.value.code == "oversell"
    assert negative_cash.value.code == "negative_cash"


def test_target_weight_closes_against_total_after_cost() -> None:
    base = portfolio_inputs()

    result = apply_scenario_operations(
        base,
        (
            operation(
                ScenarioOperationType.SET_TARGET_WEIGHT,
                target_weight="0.60",
                cost="10",
            ),
        ),
    )
    analysis = analyze_portfolio_risk(
        result.positions,
        calculated_on=TODAY,
        minimum_observations=4,
        fixed_window_dates=fixed_comparison_dates(base),
    )

    risky = next(item for item in analysis.instrument_exposures if item.key == "1")
    assert analysis.coverage.known_portfolio_value == Decimal("1980.00")
    assert risky.weight == Decimal("0.60000000")


def test_no_action_cannot_be_mixed_with_other_operations() -> None:
    no_action = ScenarioOperation(
        sequence=1,
        operation_type=ScenarioOperationType.NO_ACTION,
        instrument_id=None,
        amount=None,
        target_weight=None,
        estimated_cost=Decimal("0"),
    )
    buy = ScenarioOperation(
        sequence=2,
        operation_type=ScenarioOperationType.BUY,
        instrument_id=1,
        amount=Decimal("10"),
        target_weight=None,
        estimated_cost=Decimal("0"),
    )

    with pytest.raises(ScenarioOperationError, match="唯一操作"):
        apply_scenario_operations(portfolio_inputs(), (no_action, buy))


def test_manual_stress_is_an_assumption_and_uses_scenario_weights() -> None:
    base = portfolio_inputs()
    stressed = stressed_portfolio_value(
        base,
        (StressAssumption(asset_class=AssetClass.EQUITY, shock=Decimal("-0.20")),),
    )

    assert stressed == Decimal("1792.00")
    assert fixed_comparison_dates(base)[0] == TODAY.replace(day=21)
