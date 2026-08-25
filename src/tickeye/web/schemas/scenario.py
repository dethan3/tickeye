"""Public Scenario experiment contracts."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from tickeye.application.scenario_service import (
    ScenarioOperationDraft,
    ScenarioSummary,
    StoredScenarioComparison,
)
from tickeye.domain.enums import AssetClass
from tickeye.domain.policy import RiskState
from tickeye.domain.scenario import (
    ScenarioOperationType,
    StressAssumption,
)
from tickeye.web.schemas.risk import (
    PolicyFindingSchema,
    RiskAnalysisSchema,
    RiskCoverageSchema,
)


class StressAssumptionInput(BaseModel):
    asset_class: AssetClass
    shock: Decimal = Field(gt=-1, le=0, decimal_places=8)

    def to_domain(self) -> StressAssumption:
        return StressAssumption(
            asset_class=self.asset_class,
            shock=self.shock,
        )


class CreateScenarioRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    candidate_instrument_id: int | None = Field(default=None, gt=0)
    stress_assumptions: list[StressAssumptionInput] = Field(default_factory=list, max_length=6)


class AddScenarioOperationRequest(BaseModel):
    operation_type: ScenarioOperationType
    instrument_id: int | None = Field(default=None, gt=0)
    amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    target_weight: Decimal | None = Field(default=None, ge=0, le=1, decimal_places=8)
    estimated_cost: Decimal = Field(default=Decimal(0), ge=0, decimal_places=2)

    def to_domain(self) -> ScenarioOperationDraft:
        return ScenarioOperationDraft(
            operation_type=self.operation_type,
            instrument_id=self.instrument_id,
            amount=self.amount,
            target_weight=self.target_weight,
            estimated_cost=self.estimated_cost,
        )


class ScenarioSummarySchema(BaseModel):
    scenario_id: int
    name: str
    status: str
    base_portfolio_revision: int
    candidate_instrument_id: int | None
    operation_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, value: ScenarioSummary) -> "ScenarioSummarySchema":
        return cls.model_validate(value, from_attributes=True)


class ScenarioListData(BaseModel):
    items: list[ScenarioSummarySchema]


class ScenarioListCoverage(BaseModel):
    scenario_count: int


class ScenarioListResponse(BaseModel):
    data: ScenarioListData
    as_of: date | None = None
    calculated_at: datetime
    coverage: ScenarioListCoverage
    warnings: list[str]
    methodology_version: Literal["scenario-comparison-v1"] = "scenario-comparison-v1"

    @classmethod
    def from_domain(cls, items: tuple[ScenarioSummary, ...]) -> "ScenarioListResponse":
        return cls(
            data=ScenarioListData(
                items=[ScenarioSummarySchema.from_domain(item) for item in items]
            ),
            calculated_at=datetime.now(UTC),
            coverage=ScenarioListCoverage(scenario_count=len(items)),
            warnings=[],
        )


class ScenarioOperationSchema(BaseModel):
    sequence: int
    operation_type: ScenarioOperationType
    instrument_id: int | None
    amount: Decimal | None
    target_weight: Decimal | None
    estimated_cost: Decimal


class StressAssumptionSchema(BaseModel):
    asset_class: AssetClass
    shock: Decimal


class ComparisonWindowSchema(BaseModel):
    start: date | None
    end: date | None
    observations: int


class ScenarioPolicySchema(BaseModel):
    state: RiskState
    findings: list[PolicyFindingSchema]
    methodology_version: str


class ScenarioSideSchema(BaseModel):
    analysis: RiskAnalysisSchema
    policy: ScenarioPolicySchema
    stressed_value: Decimal | None


class ScenarioJudgmentSchema(BaseModel):
    confidence: Literal["low", "medium", "high"]
    improvements: list[str]
    worsenings: list[str]
    objections: list[str]


class ScenarioComparisonPayload(BaseModel):
    scenario_id: int
    name: str
    base_portfolio_revision: int
    candidate_instrument_id: int | None
    policy_revision: int
    operation_count: int
    operations: list[ScenarioOperationSchema]
    comparison_window: ComparisonWindowSchema
    before: ScenarioSideSchema
    after: ScenarioSideSchema
    stress_assumptions: list[StressAssumptionSchema]
    total_estimated_cost: Decimal
    summary: ScenarioJudgmentSchema
    warnings: list[str]
    methodology_version: Literal["scenario-comparison-v1"]


class ScenarioComparisonData(ScenarioComparisonPayload):
    comparison_id: int


class ScenarioComparisonCoverage(BaseModel):
    before: RiskCoverageSchema
    after: RiskCoverageSchema


class ScenarioComparisonResponse(BaseModel):
    data: ScenarioComparisonData
    as_of: date | None
    calculated_at: datetime
    coverage: ScenarioComparisonCoverage
    warnings: list[str]
    methodology_version: Literal["scenario-comparison-v1"] = "scenario-comparison-v1"

    @classmethod
    def from_domain(
        cls, value: StoredScenarioComparison
    ) -> "ScenarioComparisonResponse":
        payload = ScenarioComparisonPayload.model_validate_json(value.payload_json)
        return cls(
            data=ScenarioComparisonData(
                comparison_id=value.comparison_id,
                **payload.model_dump(),
            ),
            as_of=(
                payload.after.analysis.market_data_as_of
                or payload.after.analysis.portfolio_as_of
            ),
            calculated_at=value.calculated_at,
            coverage=ScenarioComparisonCoverage(
                before=payload.before.analysis.coverage,
                after=payload.after.analysis.coverage,
            ),
            warnings=payload.warnings,
        )
