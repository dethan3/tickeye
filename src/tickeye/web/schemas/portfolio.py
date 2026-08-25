"""Public portfolio API contract."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from tickeye.application.errors import ValidationIssue
from tickeye.application.portfolio_service import ImportPreview
from tickeye.domain.enums import AssetClass, InstrumentType
from tickeye.domain.models import PortfolioFacts, PositionFact, PositionInput


class PositionInputSchema(BaseModel):
    id: int | None = Field(default=None, gt=0)
    account_name: str = Field(min_length=1, max_length=100)
    institution: str | None = Field(default=None, max_length=100)
    account_currency: str = Field(default="CNY", min_length=3, max_length=3)
    code: str = Field(min_length=1, max_length=32)
    name: str | None = Field(default=None, max_length=200)
    instrument_type: InstrumentType | None = None
    market: str = Field(min_length=1, max_length=32)
    instrument_currency: str | None = Field(default=None, min_length=3, max_length=3)
    asset_class: AssetClass | None = None
    region: str | None = Field(default=None, max_length=64)
    quantity: Decimal | None = None
    manual_value: Decimal | None = None
    cost: Decimal | None = None
    as_of: date

    def to_domain(self) -> PositionInput:
        return PositionInput(**self.model_dump())

    @classmethod
    def from_domain(cls, value: PositionInput) -> "PositionInputSchema":
        return cls.model_validate(value, from_attributes=True)


class ReplacePositionsRequest(BaseModel):
    expected_revision: int = Field(ge=0)
    positions: list[PositionInputSchema] = Field(max_length=500)


class PositionSchema(BaseModel):
    id: int
    account_id: int
    account_name: str
    institution: str | None
    account_currency: str
    instrument_id: int
    code: str
    name: str
    instrument_type: InstrumentType
    market: str
    instrument_currency: str
    asset_class: AssetClass
    region: str
    quantity: Decimal | None
    manual_value: Decimal | None
    cost: Decimal | None
    as_of: date

    @classmethod
    def from_domain(cls, value: PositionFact) -> "PositionSchema":
        return cls.model_validate(value, from_attributes=True)


class PortfolioData(BaseModel):
    profile_id: int
    profile_name: str
    base_currency: str
    revision: int
    positions: list[PositionSchema]
    latest_snapshot_at: datetime | None


class PortfolioCoverage(BaseModel):
    account_count: int
    position_count: int


class PortfolioResponse(BaseModel):
    data: PortfolioData
    as_of: date | None
    calculated_at: datetime
    coverage: PortfolioCoverage
    warnings: list[str]
    methodology_version: Literal["portfolio-facts-v1"] = "portfolio-facts-v1"

    @classmethod
    def from_domain(cls, value: PortfolioFacts, *, calculated_at: datetime) -> "PortfolioResponse":
        return cls(
            data=PortfolioData(
                profile_id=value.profile_id,
                profile_name=value.profile_name,
                base_currency=value.base_currency,
                revision=value.revision,
                positions=[PositionSchema.from_domain(item) for item in value.positions],
                latest_snapshot_at=value.latest_snapshot_at,
            ),
            as_of=max((item.as_of for item in value.positions), default=None),
            calculated_at=calculated_at,
            coverage=PortfolioCoverage(
                account_count=len({item.account_id for item in value.positions}),
                position_count=len(value.positions),
            ),
            warnings=[],
        )


class ValidationIssueSchema(BaseModel):
    code: str
    message: str
    field: str | None
    row: int | None

    @classmethod
    def from_domain(cls, value: ValidationIssue) -> "ValidationIssueSchema":
        return cls.model_validate(value, from_attributes=True)


class PortfolioImportRequest(BaseModel):
    mode: Literal["preview", "confirm"] = "preview"
    csv_content: str = Field(min_length=1, max_length=2_000_000)
    preview_token: str | None = Field(default=None, min_length=64, max_length=64)
    expected_revision: int | None = Field(default=None, ge=0)


class ImportPreviewData(BaseModel):
    preview_token: str
    valid: bool
    duplicate_import: bool
    positions: list[PositionInputSchema]
    issues: list[ValidationIssueSchema]


class ImportPreviewResponse(BaseModel):
    mode: Literal["preview"] = "preview"
    data: ImportPreviewData

    @classmethod
    def from_domain(cls, value: ImportPreview) -> "ImportPreviewResponse":
        return cls(
            data=ImportPreviewData(
                preview_token=value.preview_token,
                valid=value.valid,
                duplicate_import=value.duplicate_import,
                positions=[PositionInputSchema.from_domain(item) for item in value.positions],
                issues=[ValidationIssueSchema.from_domain(item) for item in value.issues],
            )
        )


class ImportConfirmedResponse(BaseModel):
    mode: Literal["confirm"] = "confirm"
    portfolio: PortfolioResponse
