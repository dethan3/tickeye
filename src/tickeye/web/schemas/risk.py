"""Public contracts for immutable historical risk simulations."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from tickeye.application.policy_service import StoredRiskEvaluation
from tickeye.application.risk_service import StoredRiskSnapshot
from tickeye.domain.enums import AssetClass, InstrumentType
from tickeye.domain.policy import RiskState
from tickeye.domain.risk import (
    RiskCalculationStatus,
    RiskEvidenceCode,
    ValuationSource,
)


class PositionValuationSchema(BaseModel):
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


class ExposureSchema(BaseModel):
    key: str
    label: str
    value: Decimal
    weight: Decimal


class RiskCoverageSchema(BaseModel):
    total_positions: int
    valued_positions: int
    historical_positions: int
    known_portfolio_value: Decimal
    valued_position_ratio: Decimal
    historical_value_ratio: Decimal | None


class HistoricalMetricsSchema(BaseModel):
    aligned_observations: int
    return_samples: int
    window_start: date | None
    window_end: date | None
    annualized_volatility: Decimal | None
    downside_volatility: Decimal | None
    max_drawdown: Decimal | None
    current_drawdown: Decimal | None


class CorrelationEntrySchema(BaseModel):
    left_code: str
    right_code: str
    value: Decimal | None


class RiskEvidenceSchema(BaseModel):
    code: RiskEvidenceCode
    message: str
    instrument_id: int | None = None
    instrument_code: str | None = None


class PolicyFindingSchema(BaseModel):
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


class PolicyEvaluationPayload(BaseModel):
    state: RiskState
    findings: list[PolicyFindingSchema]


class PolicyEvaluationSchema(BaseModel):
    evaluation_id: int
    policy_revision: int
    state: RiskState
    calculated_at: datetime
    findings: list[PolicyFindingSchema]

    @classmethod
    def from_stored(cls, value: StoredRiskEvaluation) -> "PolicyEvaluationSchema":
        payload = PolicyEvaluationPayload.model_validate_json(value.findings_json)
        return cls(
            evaluation_id=value.evaluation_id,
            policy_revision=value.policy_revision,
            state=payload.state,
            calculated_at=value.calculated_at,
            findings=payload.findings,
        )


class RiskAnalysisSchema(BaseModel):
    status: RiskCalculationStatus
    portfolio_as_of: date | None
    market_data_as_of: date | None
    positions: list[PositionValuationSchema]
    instrument_exposures: list[ExposureSchema]
    asset_class_exposures: list[ExposureSchema]
    coverage: RiskCoverageSchema
    metrics: HistoricalMetricsSchema
    correlations: list[CorrelationEntrySchema]
    evidence: list[RiskEvidenceSchema]
    assumptions: list[str]
    limitations: list[str]
    methodology_version: Literal["historical-risk-v1"]


class RiskSnapshotData(BaseModel):
    snapshot_id: int
    portfolio_revision: int
    is_current: bool
    stale_reasons: list[str]
    analysis: RiskAnalysisSchema
    evaluation: PolicyEvaluationSchema | None = None


class RiskResponse(BaseModel):
    data: RiskSnapshotData | None
    as_of: date | None
    calculated_at: datetime
    coverage: RiskCoverageSchema | None
    warnings: list[str]
    methodology_version: Literal["historical-risk-v1"] = "historical-risk-v1"

    @classmethod
    def empty(cls) -> "RiskResponse":
        return cls(
            data=None,
            as_of=None,
            calculated_at=datetime.now(UTC),
            coverage=None,
            warnings=["尚未生成风险快照。"],
        )

    @classmethod
    def from_stored(
        cls,
        snapshot: StoredRiskSnapshot,
        evaluation: StoredRiskEvaluation | None = None,
    ) -> "RiskResponse":
        analysis = RiskAnalysisSchema.model_validate_json(snapshot.payload_json)
        stale_labels = {
            "portfolio_changed": "持仓已在快照生成后发生变化，请重新计算。",
            "market_data_changed": "市场数据已在快照生成后刷新，请重新计算。",
        }
        warnings = [stale_labels.get(reason, reason) for reason in snapshot.stale_reasons]
        return cls(
            data=RiskSnapshotData(
                snapshot_id=snapshot.snapshot_id,
                portfolio_revision=snapshot.portfolio_revision,
                is_current=snapshot.is_current,
                stale_reasons=list(snapshot.stale_reasons),
                analysis=analysis,
                evaluation=(
                    PolicyEvaluationSchema.from_stored(evaluation)
                    if evaluation is not None
                    else None
                ),
            ),
            as_of=analysis.market_data_as_of or analysis.portfolio_as_of,
            calculated_at=snapshot.calculated_at,
            coverage=analysis.coverage,
            warnings=warnings,
        )
