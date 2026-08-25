"""Pure Scenario operations applied to a frozen portfolio copy."""

from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from tickeye.domain.enums import AssetClass, InstrumentType
from tickeye.domain.risk import (
    DEFAULT_WINDOW_OBSERVATIONS,
    RiskPositionInput,
)

MONEY_QUANTUM = Decimal("0.01")
QUANTITY_QUANTUM = Decimal("0.00000001")


class ScenarioOperationType(StrEnum):
    NO_ACTION = "no_action"
    BUY = "buy"
    SELL = "sell"
    SET_AMOUNT = "set_amount"
    SET_TARGET_WEIGHT = "set_target_weight"


@dataclass(frozen=True, slots=True)
class ScenarioOperation:
    sequence: int
    operation_type: ScenarioOperationType
    instrument_id: int | None
    amount: Decimal | None
    target_weight: Decimal | None
    estimated_cost: Decimal


@dataclass(frozen=True, slots=True)
class StressAssumption:
    asset_class: AssetClass
    shock: Decimal


@dataclass(frozen=True, slots=True)
class AppliedScenario:
    positions: tuple[RiskPositionInput, ...]
    total_estimated_cost: Decimal


class ScenarioOperationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _quantity(value: Decimal) -> Decimal:
    return value.quantize(QUANTITY_QUANTUM, rounding=ROUND_HALF_UP)


def _latest_price(position: RiskPositionInput) -> Decimal | None:
    if position.instrument_type == InstrumentType.CASH or not position.history:
        return None
    return position.history[-1].value


def _position_value(position: RiskPositionInput) -> Decimal | None:
    if position.instrument_type == InstrumentType.CASH:
        value = position.manual_value if position.manual_value is not None else position.quantity
        return _money(value) if value is not None else None
    price = _latest_price(position)
    if price is not None and position.quantity is not None:
        return _money(position.quantity * price)
    return _money(position.manual_value) if position.manual_value is not None else None


def _known_total(positions: list[RiskPositionInput]) -> Decimal:
    values = [_position_value(position) for position in positions]
    if any(value is None for value in values):
        raise ScenarioOperationError(
            "incomplete_valuation",
            "组合存在无法估值的持仓，不能可靠应用金额或目标权重操作。",
        )
    return _money(sum((value or Decimal(0) for value in values), Decimal(0)))


def _cash_value(positions: list[RiskPositionInput]) -> Decimal:
    values = [
        _position_value(position)
        for position in positions
        if position.instrument_type == InstrumentType.CASH
    ]
    if any(value is None for value in values):
        raise ScenarioOperationError("unknown_cash", "现金持仓缺少可用余额。")
    return _money(sum((value or Decimal(0) for value in values), Decimal(0)))


def _change_cash(positions: list[RiskPositionInput], delta: Decimal) -> None:
    current = _cash_value(positions)
    desired = _money(current + delta)
    if desired < 0:
        raise ScenarioOperationError(
            "negative_cash",
            f"该操作会使方案现金变为 {desired} 元。",
        )
    cash_indexes = [
        index
        for index, position in enumerate(positions)
        if position.instrument_type == InstrumentType.CASH
    ]
    if cash_indexes:
        first = cash_indexes[0]
        positions[first] = replace(
            positions[first],
            quantity=None,
            manual_value=desired,
        )
        for index in cash_indexes[1:]:
            positions[index] = replace(
                positions[index], quantity=None, manual_value=Decimal("0.00")
            )
        return
    if desired > 0:
        as_of = max((position.position_as_of for position in positions), default=date.today())
        positions.append(
            RiskPositionInput(
                position_id=-1,
                instrument_id=-1,
                account_name="Scenario 虚拟现金",
                code="SCENARIO-CASH-CNY",
                name="Scenario 虚拟现金",
                instrument_type=InstrumentType.CASH,
                asset_class=AssetClass.CASH,
                quantity=None,
                manual_value=desired,
                position_as_of=as_of,
                history=(),
                freshness_limit_days=None,
            )
        )


def _instrument_indexes(
    positions: list[RiskPositionInput], instrument_id: int
) -> list[int]:
    indexes = [
        index
        for index, position in enumerate(positions)
        if position.instrument_id == instrument_id
        and position.instrument_type != InstrumentType.CASH
    ]
    if not indexes:
        raise ScenarioOperationError(
            "unknown_instrument",
            "Scenario 首版只能调整当前实际组合中已有的非现金标的。",
        )
    return indexes


def _instrument_value(
    positions: list[RiskPositionInput], indexes: list[int]
) -> Decimal:
    values = [_position_value(positions[index]) for index in indexes]
    if any(value is None for value in values):
        raise ScenarioOperationError(
            "unknown_price",
            "目标标的缺少可用价格，不能把交易金额换算为份额。",
        )
    return _money(sum((value or Decimal(0) for value in values), Decimal(0)))


def _set_instrument_value(
    positions: list[RiskPositionInput], indexes: list[int], desired: Decimal
) -> None:
    if desired < 0:
        raise ScenarioOperationError("oversell", "卖出金额超过当前持仓市值。")
    current = _instrument_value(positions, indexes)
    prices = {_latest_price(positions[index]) for index in indexes}
    if None in prices or len(prices) != 1:
        raise ScenarioOperationError(
            "unknown_price",
            "目标标的缺少一致的最新价格，不能换算方案份额。",
        )
    price = next(iter(prices))
    assert price is not None
    if current == 0:
        first = indexes[0]
        positions[first] = replace(
            positions[first], quantity=_quantity(desired / price), manual_value=None
        )
        return
    ratio = desired / current
    for index in indexes:
        quantity = positions[index].quantity
        if quantity is None:
            raise ScenarioOperationError(
                "unknown_price",
                "只有手工市值而没有份额的标的不能模拟交易。",
            )
        positions[index] = replace(
            positions[index],
            quantity=_quantity(quantity * ratio),
            manual_value=None,
        )


def _validate_operation(operation: ScenarioOperation) -> None:
    if operation.estimated_cost < 0:
        raise ScenarioOperationError("negative_cost", "交易成本不能为负数。")
    if operation.operation_type == ScenarioOperationType.NO_ACTION:
        if any(
            value is not None
            for value in (operation.instrument_id, operation.amount, operation.target_weight)
        ) or operation.estimated_cost != 0:
            raise ScenarioOperationError(
                "invalid_no_action", "NO_ACTION 不能携带标的、金额、权重或成本。"
            )
        return
    if operation.instrument_id is None:
        raise ScenarioOperationError("missing_instrument", "该操作必须选择一个标的。")
    if operation.operation_type == ScenarioOperationType.SET_TARGET_WEIGHT:
        if (
            operation.target_weight is None
            or not Decimal(0) <= operation.target_weight <= Decimal(1)
        ):
            raise ScenarioOperationError(
                "invalid_target_weight", "目标权重必须在 0% 到 100% 之间。"
            )
        if operation.amount is not None:
            raise ScenarioOperationError("unexpected_amount", "目标权重操作不能同时填写金额。")
    else:
        minimum = (
            Decimal(0)
            if operation.operation_type == ScenarioOperationType.SET_AMOUNT
            else Decimal("0.01")
        )
        if operation.amount is None or operation.amount < minimum:
            message = (
                "目标金额必须大于或等于 0。"
                if operation.operation_type == ScenarioOperationType.SET_AMOUNT
                else "买入或卖出金额必须大于 0。"
            )
            raise ScenarioOperationError("invalid_amount", message)
        if operation.target_weight is not None:
            raise ScenarioOperationError("unexpected_weight", "金额操作不能同时填写目标权重。")


def apply_scenario_operations(
    base_positions: tuple[RiskPositionInput, ...],
    operations: tuple[ScenarioOperation, ...],
) -> AppliedScenario:
    """Apply ordered operations without mutating the actual portfolio inputs."""

    if tuple(item.sequence for item in operations) != tuple(range(1, len(operations) + 1)):
        raise ScenarioOperationError("invalid_sequence", "Scenario 操作序号必须从 1 连续递增。")
    has_no_action = any(
        item.operation_type == ScenarioOperationType.NO_ACTION for item in operations
    )
    if has_no_action and len(operations) > 1:
        raise ScenarioOperationError("mixed_no_action", "NO_ACTION 必须是方案中的唯一操作。")

    positions = list(base_positions)
    total_cost = Decimal(0)
    for operation in operations:
        _validate_operation(operation)
        total_cost += operation.estimated_cost
        if operation.operation_type == ScenarioOperationType.NO_ACTION:
            continue
        assert operation.instrument_id is not None
        indexes = _instrument_indexes(positions, operation.instrument_id)
        current = _instrument_value(positions, indexes)
        if operation.operation_type == ScenarioOperationType.BUY:
            assert operation.amount is not None
            desired = current + operation.amount
            cash_delta = -(operation.amount + operation.estimated_cost)
        elif operation.operation_type == ScenarioOperationType.SELL:
            assert operation.amount is not None
            if operation.estimated_cost > operation.amount:
                raise ScenarioOperationError(
                    "cost_exceeds_proceeds", "交易成本不能超过卖出金额。"
                )
            desired = current - operation.amount
            cash_delta = operation.amount - operation.estimated_cost
        elif operation.operation_type == ScenarioOperationType.SET_AMOUNT:
            assert operation.amount is not None
            desired = operation.amount
            delta = desired - current
            if delta < 0 and operation.estimated_cost > -delta:
                raise ScenarioOperationError(
                    "cost_exceeds_proceeds", "交易成本不能超过调减产生的金额。"
                )
            cash_delta = -delta - operation.estimated_cost
        else:
            assert operation.target_weight is not None
            total_after_cost = _known_total(positions) - operation.estimated_cost
            if total_after_cost < 0:
                raise ScenarioOperationError("negative_total", "交易成本超过组合总值。")
            desired = total_after_cost * operation.target_weight
            delta = desired - current
            if delta < 0 and operation.estimated_cost > -delta:
                raise ScenarioOperationError(
                    "cost_exceeds_proceeds", "交易成本不能超过调减产生的金额。"
                )
            cash_delta = -delta - operation.estimated_cost
        _set_instrument_value(positions, indexes, _money(desired))
        _change_cash(positions, _money(cash_delta))

    return AppliedScenario(
        positions=tuple(positions),
        total_estimated_cost=_money(total_cost),
    )


def fixed_comparison_dates(
    positions: tuple[RiskPositionInput, ...],
    *,
    window_observations: int = DEFAULT_WINDOW_OBSERVATIONS,
) -> tuple[date, ...]:
    """Freeze one common historical window for both sides of a comparison."""

    histories = [
        {point.observed_on for point in position.history}
        for position in positions
        if position.instrument_type != InstrumentType.CASH
    ]
    if not histories:
        return ()
    return tuple(sorted(set.intersection(*histories))[-window_observations:])


def stressed_portfolio_value(
    positions: tuple[RiskPositionInput, ...],
    assumptions: tuple[StressAssumption, ...],
) -> Decimal | None:
    """Apply explicit asset-class shocks to current values; this is not a forecast."""

    shocks = {item.asset_class: item.shock for item in assumptions}
    total = Decimal(0)
    for position in positions:
        value = _position_value(position)
        if value is None:
            return None
        total += value * (Decimal(1) + shocks.get(position.asset_class, Decimal(0)))
    return _money(total)
