from datetime import date, timedelta
from decimal import Decimal

from tickeye.domain.enums import AssetClass, InstrumentType
from tickeye.domain.risk import (
    HistoricalValue,
    RiskCalculationStatus,
    RiskEvidenceCode,
    RiskPositionInput,
    ValuationSource,
    analyze_portfolio_risk,
)

TODAY = date(2026, 8, 24)


def position(
    *,
    position_id: int = 1,
    instrument_id: int = 1,
    code: str = "510300",
    instrument_type: InstrumentType = InstrumentType.ETF,
    asset_class: AssetClass = AssetClass.EQUITY,
    quantity: str | None = "10",
    manual_value: str | None = None,
    prices: tuple[str, ...] = ("100", "110", "99", "99"),
    last_date: date = TODAY,
    freshness_limit_days: int | None = 3,
    refresh_failed: bool = False,
) -> RiskPositionInput:
    start = last_date - timedelta(days=len(prices) - 1)
    return RiskPositionInput(
        position_id=position_id,
        instrument_id=instrument_id,
        account_name="测试账户",
        code=code,
        name=code,
        instrument_type=instrument_type,
        asset_class=asset_class,
        quantity=Decimal(quantity) if quantity is not None else None,
        manual_value=Decimal(manual_value) if manual_value is not None else None,
        position_as_of=TODAY,
        history=tuple(
            HistoricalValue(start + timedelta(days=index), Decimal(value))
            for index, value in enumerate(prices)
        ),
        freshness_limit_days=freshness_limit_days,
        last_refresh_failed=refresh_failed,
    )


def test_fixed_weight_metrics_match_hand_calculation() -> None:
    risky = position()
    cash = position(
        position_id=2,
        instrument_id=2,
        code="CASH-CNY",
        instrument_type=InstrumentType.CASH,
        asset_class=AssetClass.CASH,
        quantity=None,
        manual_value="990",
        prices=(),
        freshness_limit_days=None,
    )

    result = analyze_portfolio_risk(
        (risky, cash), calculated_on=TODAY, minimum_observations=4
    )

    assert result.status == RiskCalculationStatus.AVAILABLE
    assert result.coverage.known_portfolio_value == Decimal("1980.00")
    assert result.positions[0].value == Decimal("990.00")
    assert result.positions[0].weight == Decimal("0.50000000")
    assert result.positions[0].valuation_source == ValuationSource.MARKET_DATA
    assert result.metrics.aligned_observations == 4
    assert result.metrics.return_samples == 3
    assert result.metrics.annualized_volatility == Decimal("0.79372539")
    assert result.metrics.downside_volatility == Decimal("0.45825757")
    assert result.metrics.max_drawdown == Decimal("0.05000000")
    assert result.metrics.current_drawdown == Decimal("0.05000000")


def test_manual_value_supports_valuation_but_not_missing_history() -> None:
    missing = position(manual_value="1000", prices=())

    result = analyze_portfolio_risk((missing,), calculated_on=TODAY)

    assert result.positions[0].value == Decimal("1000.00")
    assert result.positions[0].valuation_source == ValuationSource.MANUAL_VALUE
    assert result.status == RiskCalculationStatus.UNKNOWN
    assert result.coverage.historical_positions == 0
    assert result.coverage.historical_value_ratio == Decimal("0.00000000")
    assert result.evidence[0].code == RiskEvidenceCode.MISSING_HISTORY


def test_stale_or_failed_history_makes_market_risk_unknown() -> None:
    stale = position(last_date=TODAY - timedelta(days=4))
    failed = position(position_id=2, instrument_id=2, code="007360", refresh_failed=True)

    result = analyze_portfolio_risk((stale, failed), calculated_on=TODAY)

    assert result.status == RiskCalculationStatus.UNKNOWN
    assert {
        RiskEvidenceCode.STALE_HISTORY,
        RiskEvidenceCode.REFRESH_FAILED,
    } <= {item.code for item in result.evidence}


def test_short_aligned_history_is_unknown_without_filling_dates() -> None:
    first = position(prices=("1", "2", "3", "4"))
    second = position(
        position_id=2,
        instrument_id=2,
        code="007360",
        prices=("1", "2"),
    )

    result = analyze_portfolio_risk(
        (first, second), calculated_on=TODAY, minimum_observations=3
    )

    assert result.status == RiskCalculationStatus.UNKNOWN
    assert result.metrics.aligned_observations == 2
    assert result.evidence[0].code == RiskEvidenceCode.INSUFFICIENT_ALIGNED_HISTORY


def test_incomplete_valuation_is_unknown_and_not_silently_zero() -> None:
    unavailable = position(quantity="10", manual_value=None, prices=())

    result = analyze_portfolio_risk((unavailable,), calculated_on=TODAY)

    assert result.coverage.valued_positions == 0
    assert result.positions[0].value is None
    assert result.positions[0].valuation_source == ValuationSource.UNAVAILABLE
    assert result.status == RiskCalculationStatus.UNKNOWN
    assert result.evidence[0].code == RiskEvidenceCode.INCOMPLETE_VALUATION


def test_all_cash_has_explicit_zero_market_simulation() -> None:
    cash = position(
        instrument_type=InstrumentType.CASH,
        asset_class=AssetClass.CASH,
        quantity="10000",
        prices=(),
        freshness_limit_days=None,
    )

    result = analyze_portfolio_risk((cash,), calculated_on=TODAY)

    assert result.status == RiskCalculationStatus.ALL_CASH
    assert result.metrics.annualized_volatility == Decimal("0.00000000")
    assert result.metrics.max_drawdown == Decimal("0.00000000")
    assert result.correlations == ()


def test_empty_portfolio_is_unknown_instead_of_all_cash() -> None:
    result = analyze_portfolio_risk((), calculated_on=TODAY)

    assert result.status == RiskCalculationStatus.UNKNOWN
    assert result.evidence[0].code == RiskEvidenceCode.EMPTY_PORTFOLIO
    assert result.coverage.total_positions == 0


def test_correlation_is_pairwise_and_zero_variance_is_undefined() -> None:
    rising = position(prices=("100", "110", "121", "133.1"))
    falling = position(
        position_id=2,
        instrument_id=2,
        code="007360",
        prices=("100", "90", "81", "72.9"),
    )

    result = analyze_portfolio_risk(
        (rising, falling), calculated_on=TODAY, minimum_observations=4
    )

    assert len(result.correlations) == 1
    assert result.correlations[0].value is None
    assert RiskEvidenceCode.ZERO_VARIANCE_CORRELATION in {
        item.code for item in result.evidence
    }
