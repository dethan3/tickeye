"""Pure valuation and fixed-weight historical risk simulation."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

import numpy as np

from tickeye.domain.enums import AssetClass, InstrumentType

MONEY_QUANTUM = Decimal("0.01")
RATIO_QUANTUM = Decimal("0.00000001")
TRADING_DAYS_PER_YEAR = 252
DEFAULT_WINDOW_OBSERVATIONS = 252
MINIMUM_ALIGNED_OBSERVATIONS = 120
METHODOLOGY_VERSION = "historical-risk-v1"


class RiskCalculationStatus(StrEnum):
    AVAILABLE = "available"
    UNKNOWN = "unknown"
    ALL_CASH = "all_cash"


class ValuationSource(StrEnum):
    MARKET_DATA = "market_data"
    MANUAL_VALUE = "manual_value"
    CASH_BALANCE = "cash_balance"
    ZERO_QUANTITY = "zero_quantity"
    UNAVAILABLE = "unavailable"


class RiskEvidenceCode(StrEnum):
    EMPTY_PORTFOLIO = "empty_portfolio"
    INCOMPLETE_VALUATION = "incomplete_valuation"
    MISSING_HISTORY = "missing_history"
    STALE_HISTORY = "stale_history"
    REFRESH_FAILED = "refresh_failed"
    INSUFFICIENT_ALIGNED_HISTORY = "insufficient_aligned_history"
    ZERO_VARIANCE_CORRELATION = "zero_variance_correlation"
    MIXED_VALUATION_DATES = "mixed_valuation_dates"


@dataclass(frozen=True, slots=True)
class HistoricalValue:
    observed_on: date
    value: Decimal


@dataclass(frozen=True, slots=True)
class RiskPositionInput:
    position_id: int
    instrument_id: int
    account_name: str
    code: str
    name: str
    instrument_type: InstrumentType
    asset_class: AssetClass
    quantity: Decimal | None
    manual_value: Decimal | None
    position_as_of: date
    history: tuple[HistoricalValue, ...]
    freshness_limit_days: int | None
    last_refresh_failed: bool = False
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PositionValuation:
    position_id: int
    instrument_id: int
    account_name: str
    code: str
    name: str
    instrument_type: InstrumentType
    asset_class: AssetClass
    value: Decimal | None
    weight: Decimal | None
    valuation_source: ValuationSource
    value_as_of: date | None


@dataclass(frozen=True, slots=True)
class Exposure:
    key: str
    label: str
    value: Decimal
    weight: Decimal


@dataclass(frozen=True, slots=True)
class RiskCoverage:
    total_positions: int
    valued_positions: int
    historical_positions: int
    known_portfolio_value: Decimal
    valued_position_ratio: Decimal
    historical_value_ratio: Decimal | None


@dataclass(frozen=True, slots=True)
class HistoricalMetrics:
    aligned_observations: int
    return_samples: int
    window_start: date | None
    window_end: date | None
    annualized_volatility: Decimal | None
    downside_volatility: Decimal | None
    max_drawdown: Decimal | None
    current_drawdown: Decimal | None


@dataclass(frozen=True, slots=True)
class CorrelationEntry:
    left_code: str
    right_code: str
    value: Decimal | None


@dataclass(frozen=True, slots=True)
class RiskEvidence:
    code: RiskEvidenceCode
    message: str
    instrument_id: int | None = None
    instrument_code: str | None = None


@dataclass(frozen=True, slots=True)
class RiskAnalysis:
    status: RiskCalculationStatus
    portfolio_as_of: date | None
    market_data_as_of: date | None
    positions: tuple[PositionValuation, ...]
    instrument_exposures: tuple[Exposure, ...]
    asset_class_exposures: tuple[Exposure, ...]
    coverage: RiskCoverage
    metrics: HistoricalMetrics
    correlations: tuple[CorrelationEntry, ...]
    evidence: tuple[RiskEvidence, ...]
    assumptions: tuple[str, ...]
    limitations: tuple[str, ...]
    methodology_version: str = METHODOLOGY_VERSION

    @property
    def max_instrument_weight(self) -> Decimal | None:
        if not self.instrument_exposures:
            return None
        return max(item.weight for item in self.instrument_exposures)

    @property
    def max_asset_class_weight(self) -> Decimal | None:
        if not self.asset_class_exposures:
            return None
        return max(item.weight for item in self.asset_class_exposures)


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _ratio(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(RATIO_QUANTUM, rounding=ROUND_HALF_UP)


def _position_value(
    position: RiskPositionInput,
) -> tuple[Decimal | None, ValuationSource, date | None]:
    if position.instrument_type == InstrumentType.CASH:
        if position.manual_value is not None:
            return (
                _money(position.manual_value),
                ValuationSource.CASH_BALANCE,
                position.position_as_of,
            )
        if position.quantity is not None:
            return _money(position.quantity), ValuationSource.CASH_BALANCE, position.position_as_of
        return None, ValuationSource.UNAVAILABLE, None

    if position.quantity == 0:
        return Decimal("0.00"), ValuationSource.ZERO_QUANTITY, position.position_as_of
    if position.quantity is not None and position.history:
        latest = position.history[-1]
        return (
            _money(position.quantity * latest.value),
            ValuationSource.MARKET_DATA,
            latest.observed_on,
        )
    if position.manual_value is not None:
        return _money(position.manual_value), ValuationSource.MANUAL_VALUE, position.position_as_of
    return None, ValuationSource.UNAVAILABLE, None


def _empty_metrics() -> HistoricalMetrics:
    return HistoricalMetrics(
        aligned_observations=0,
        return_samples=0,
        window_start=None,
        window_end=None,
        annualized_volatility=None,
        downside_volatility=None,
        max_drawdown=None,
        current_drawdown=None,
    )


def _exposures(
    positions: list[PositionValuation],
    total_value: Decimal,
    *,
    by_asset_class: bool,
) -> tuple[Exposure, ...]:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    labels: dict[str, str] = {}
    for position in positions:
        if position.value is None:
            continue
        key = position.asset_class.value if by_asset_class else str(position.instrument_id)
        label = (
            position.asset_class.value
            if by_asset_class
            else f"{position.name} ({position.code})"
        )
        totals[key] += position.value
        labels[key] = label
    if total_value <= 0:
        return ()
    return tuple(
        Exposure(
            key=key,
            label=labels[key],
            value=_money(value),
            weight=_ratio(value / total_value),
        )
        for key, value in sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    )


def _correlations(
    returns_by_instrument: dict[int, tuple[str, np.ndarray]],
) -> tuple[CorrelationEntry, ...]:
    entries: list[CorrelationEntry] = []
    instrument_ids = sorted(returns_by_instrument)
    for index, left_id in enumerate(instrument_ids):
        left_code, left_returns = returns_by_instrument[left_id]
        for right_id in instrument_ids[index + 1 :]:
            right_code, right_returns = returns_by_instrument[right_id]
            if np.isclose(np.std(left_returns), 0) or np.isclose(np.std(right_returns), 0):
                value = None
            else:
                value = _ratio(float(np.corrcoef(left_returns, right_returns)[0, 1]))
            entries.append(
                CorrelationEntry(
                    left_code=left_code,
                    right_code=right_code,
                    value=value,
                )
            )
    return tuple(entries)


def analyze_portfolio_risk(
    positions: tuple[RiskPositionInput, ...],
    *,
    calculated_on: date,
    window_observations: int = DEFAULT_WINDOW_OBSERVATIONS,
    minimum_observations: int = MINIMUM_ALIGNED_OBSERVATIONS,
    fixed_window_dates: tuple[date, ...] | None = None,
) -> RiskAnalysis:
    """Calculate valuation and a daily-rebalanced simulation without I/O."""

    provisional: list[PositionValuation] = []
    values: dict[int, Decimal | None] = {}
    for position in positions:
        value, source, value_as_of = _position_value(position)
        values[position.position_id] = value
        provisional.append(
            PositionValuation(
                position_id=position.position_id,
                instrument_id=position.instrument_id,
                account_name=position.account_name,
                code=position.code,
                name=position.name,
                instrument_type=position.instrument_type,
                asset_class=position.asset_class,
                value=value,
                weight=None,
                valuation_source=source,
                value_as_of=value_as_of,
            )
        )

    known_value = sum((value for value in values.values() if value is not None), Decimal(0))
    valuations = [
        PositionValuation(
            position_id=item.position_id,
            instrument_id=item.instrument_id,
            account_name=item.account_name,
            code=item.code,
            name=item.name,
            instrument_type=item.instrument_type,
            asset_class=item.asset_class,
            value=item.value,
            weight=(
                _ratio(item.value / known_value)
                if item.value is not None and known_value > 0
                else None
            ),
            valuation_source=item.valuation_source,
            value_as_of=item.value_as_of,
        )
        for item in provisional
    ]
    valued_count = sum(item.value is not None for item in valuations)
    valued_ratio = _ratio(valued_count / len(positions)) if positions else Decimal("1.00000000")
    portfolio_as_of = max((item.position_as_of for item in positions), default=None)
    market_dates = [item.history[-1].observed_on for item in positions if item.history]
    market_data_as_of = max(market_dates, default=None)
    instrument_exposures = _exposures(valuations, known_value, by_asset_class=False)
    asset_class_exposures = _exposures(valuations, known_value, by_asset_class=True)

    evidence: list[RiskEvidence] = []
    for item in valuations:
        if item.value is None:
            evidence.append(
                RiskEvidence(
                    code=RiskEvidenceCode.INCOMPLETE_VALUATION,
                    message=f"{item.name} 缺少可用行情和手工市值，组合总值与权重不完整。",
                    instrument_id=item.instrument_id,
                    instrument_code=item.code,
                )
            )

    material: list[RiskPositionInput] = []
    for position in positions:
        value = values[position.position_id]
        if (
            position.instrument_type != InstrumentType.CASH
            and value is not None
            and value > 0
        ):
            material.append(position)
    assumptions = (
        "使用当前估值权重回放历史，每个观测日按固定权重重新平衡。",
        "现金日收益假设为 0，不包含存款利息、费用、税费和交易滑点。",
        (
            f"最多使用最近 {window_observations} 个共同价格观测日，"
            f"至少需要 {minimum_observations} 个。"
        ),
        "结果是历史风险模拟，不是账户收益、未来预测或买卖建议。",
    )
    limitations = tuple(sorted({limit for item in positions for limit in item.limitations}))

    usable_historical = [
        item
        for item in material
        if item.history
        and not item.last_refresh_failed
        and (
            item.freshness_limit_days is None
            or (calculated_on - item.history[-1].observed_on).days
            <= item.freshness_limit_days
        )
    ]
    usable_historical_value = sum(
        (values[item.position_id] or Decimal(0) for item in usable_historical),
        Decimal(0),
    )
    coverage = RiskCoverage(
        total_positions=len(positions),
        valued_positions=valued_count,
        historical_positions=len(usable_historical),
        known_portfolio_value=_money(known_value),
        valued_position_ratio=valued_ratio,
        historical_value_ratio=(
            _ratio(usable_historical_value / known_value) if known_value > 0 else None
        ),
    )

    if not positions:
        return RiskAnalysis(
            status=RiskCalculationStatus.UNKNOWN,
            portfolio_as_of=None,
            market_data_as_of=None,
            positions=(),
            instrument_exposures=(),
            asset_class_exposures=(),
            coverage=coverage,
            metrics=_empty_metrics(),
            correlations=(),
            evidence=(
                RiskEvidence(
                    code=RiskEvidenceCode.EMPTY_PORTFOLIO,
                    message="当前没有持仓，无法建立组合风险模拟。",
                ),
            ),
            assumptions=assumptions,
            limitations=(),
        )

    valuation_dates = {
        item.value_as_of for item in valuations if item.value_as_of is not None
    }
    informational_evidence = (
        [
            RiskEvidence(
                code=RiskEvidenceCode.MIXED_VALUATION_DATES,
                message="持仓估值日期不完全一致，组合市值不是严格的同一时点快照。",
            )
        ]
        if len(valuation_dates) > 1
        else []
    )

    if evidence:
        return RiskAnalysis(
            status=RiskCalculationStatus.UNKNOWN,
            portfolio_as_of=portfolio_as_of,
            market_data_as_of=market_data_as_of,
            positions=tuple(valuations),
            instrument_exposures=instrument_exposures,
            asset_class_exposures=asset_class_exposures,
            coverage=coverage,
            metrics=_empty_metrics(),
            correlations=(),
            evidence=tuple(evidence + informational_evidence),
            assumptions=assumptions,
            limitations=limitations,
        )

    if not material:
        zero_metrics = HistoricalMetrics(
            aligned_observations=0,
            return_samples=0,
            window_start=None,
            window_end=None,
            annualized_volatility=Decimal("0.00000000"),
            downside_volatility=Decimal("0.00000000"),
            max_drawdown=Decimal("0.00000000"),
            current_drawdown=Decimal("0.00000000"),
        )
        return RiskAnalysis(
            status=RiskCalculationStatus.ALL_CASH,
            portfolio_as_of=portfolio_as_of,
            market_data_as_of=None,
            positions=tuple(valuations),
            instrument_exposures=instrument_exposures,
            asset_class_exposures=asset_class_exposures,
            coverage=coverage,
            metrics=zero_metrics,
            correlations=(),
            evidence=tuple(informational_evidence),
            assumptions=assumptions,
            limitations=limitations,
        )

    for position in material:
        if position.last_refresh_failed:
            evidence.append(
                RiskEvidence(
                    code=RiskEvidenceCode.REFRESH_FAILED,
                    message=f"{position.name} 最近一次行情刷新失败。",
                    instrument_id=position.instrument_id,
                    instrument_code=position.code,
                )
            )
        if not position.history:
            evidence.append(
                RiskEvidence(
                    code=RiskEvidenceCode.MISSING_HISTORY,
                    message=f"{position.name} 没有历史行情。",
                    instrument_id=position.instrument_id,
                    instrument_code=position.code,
                )
            )
        elif (
            position.freshness_limit_days is not None
            and (calculated_on - position.history[-1].observed_on).days
            > position.freshness_limit_days
        ):
            evidence.append(
                RiskEvidence(
                    code=RiskEvidenceCode.STALE_HISTORY,
                    message=f"{position.name} 的最后行情已经超过新鲜度阈值。",
                    instrument_id=position.instrument_id,
                    instrument_code=position.code,
                )
            )
    if evidence:
        return RiskAnalysis(
            status=RiskCalculationStatus.UNKNOWN,
            portfolio_as_of=portfolio_as_of,
            market_data_as_of=market_data_as_of,
            positions=tuple(valuations),
            instrument_exposures=instrument_exposures,
            asset_class_exposures=asset_class_exposures,
            coverage=coverage,
            metrics=_empty_metrics(),
            correlations=(),
            evidence=tuple(evidence + informational_evidence),
            assumptions=assumptions,
            limitations=limitations,
        )

    histories = [
        {point.observed_on: point.value for point in position.history}
        for position in material
    ]
    common_dates = (
        list(fixed_window_dates[-window_observations:])
        if fixed_window_dates is not None
        else sorted(set.intersection(*(set(history) for history in histories)))[
            -window_observations:
        ]
    )
    if fixed_window_dates is not None and any(
        not set(common_dates).issubset(history) for history in histories
    ):
        evidence.append(
            RiskEvidence(
                code=RiskEvidenceCode.INSUFFICIENT_ALIGNED_HISTORY,
                message="至少一个标的不能覆盖 Scenario 固定比较窗口。",
            )
        )
        common_dates = []
    if len(common_dates) < minimum_observations:
        evidence.append(
            RiskEvidence(
                code=RiskEvidenceCode.INSUFFICIENT_ALIGNED_HISTORY,
                message=(
                    f"共同价格观测日只有 {len(common_dates)} 个，"
                    f"至少需要 {minimum_observations} 个。"
                ),
            )
        )
        return RiskAnalysis(
            status=RiskCalculationStatus.UNKNOWN,
            portfolio_as_of=portfolio_as_of,
            market_data_as_of=market_data_as_of,
            positions=tuple(valuations),
            instrument_exposures=instrument_exposures,
            asset_class_exposures=asset_class_exposures,
            coverage=coverage,
            metrics=HistoricalMetrics(
                aligned_observations=len(common_dates),
                return_samples=max(0, len(common_dates) - 1),
                window_start=common_dates[0] if common_dates else None,
                window_end=common_dates[-1] if common_dates else None,
                annualized_volatility=None,
                downside_volatility=None,
                max_drawdown=None,
                current_drawdown=None,
            ),
            correlations=(),
            evidence=tuple(evidence + informational_evidence),
            assumptions=assumptions,
            limitations=limitations,
        )

    instrument_values: dict[int, Decimal] = defaultdict(Decimal)
    instrument_codes: dict[int, str] = {}
    instrument_history: dict[int, dict[date, Decimal]] = {}
    for position, history in zip(material, histories, strict=True):
        instrument_values[position.instrument_id] += values[position.position_id] or Decimal(0)
        instrument_codes[position.instrument_id] = position.code
        instrument_history[position.instrument_id] = history

    portfolio_returns = np.zeros(len(common_dates) - 1, dtype=float)
    returns_by_instrument: dict[int, tuple[str, np.ndarray]] = {}
    for instrument_id, value in instrument_values.items():
        history = instrument_history[instrument_id]
        prices = np.array([float(history[item]) for item in common_dates], dtype=float)
        returns = prices[1:] / prices[:-1] - 1.0
        portfolio_returns += returns * float(value / known_value)
        returns_by_instrument[instrument_id] = (instrument_codes[instrument_id], returns)

    annualized_volatility = float(np.std(portfolio_returns, ddof=1)) * np.sqrt(
        TRADING_DAYS_PER_YEAR
    )
    downside = np.minimum(portfolio_returns, 0.0)
    downside_volatility = float(np.sqrt(np.mean(np.square(downside)))) * np.sqrt(
        TRADING_DAYS_PER_YEAR
    )
    wealth = np.concatenate(([1.0], np.cumprod(1.0 + portfolio_returns)))
    drawdowns = 1.0 - wealth / np.maximum.accumulate(wealth)
    metrics = HistoricalMetrics(
        aligned_observations=len(common_dates),
        return_samples=len(portfolio_returns),
        window_start=common_dates[0],
        window_end=common_dates[-1],
        annualized_volatility=_ratio(annualized_volatility),
        downside_volatility=_ratio(downside_volatility),
        max_drawdown=_ratio(float(np.max(drawdowns))),
        current_drawdown=_ratio(float(drawdowns[-1])),
    )
    correlations = _correlations(returns_by_instrument)
    if any(item.value is None for item in correlations):
        evidence.append(
            RiskEvidence(
                code=RiskEvidenceCode.ZERO_VARIANCE_CORRELATION,
                message="至少一个标的在窗口内没有波动，因此相关系数不可定义。",
            )
        )
    return RiskAnalysis(
        status=RiskCalculationStatus.AVAILABLE,
        portfolio_as_of=portfolio_as_of,
        market_data_as_of=market_data_as_of,
        positions=tuple(valuations),
        instrument_exposures=instrument_exposures,
        asset_class_exposures=asset_class_exposures,
        coverage=coverage,
        metrics=metrics,
        correlations=correlations,
        evidence=tuple(evidence + informational_evidence),
        assumptions=assumptions,
        limitations=limitations,
    )
