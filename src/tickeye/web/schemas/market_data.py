"""Public market refresh and data-quality contracts."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from tickeye.application.market_data_provider import MarketValueType
from tickeye.application.market_data_service import (
    DataQualityItem,
    DataQualityReport,
    DataQualityStatus,
    RefreshReport,
    RefreshResult,
    RefreshStatus,
)
from tickeye.domain.enums import InstrumentType


class DataQualityItemSchema(BaseModel):
    instrument_id: int
    code: str
    name: str
    instrument_type: InstrumentType
    status: DataQualityStatus
    last_observation_date: date | None
    latest_value: Decimal | None
    value_type: MarketValueType | None
    source: str | None
    sample_count: int
    freshness_days: int | None
    freshness_limit_days: int | None
    rejected_rate: Decimal | None
    last_refresh_at: datetime | None
    last_refresh_status: RefreshStatus | None
    failure_code: str | None
    failure_message: str | None
    limitations: list[str]

    @classmethod
    def from_domain(cls, value: DataQualityItem) -> "DataQualityItemSchema":
        return cls.model_validate(value, from_attributes=True)


class DataQualityCoverage(BaseModel):
    tracked_count: int
    available_count: int
    problem_count: int


class DataQualityData(BaseModel):
    items: list[DataQualityItemSchema]


class DataQualityResponse(BaseModel):
    data: DataQualityData
    as_of: date | None
    calculated_at: datetime
    coverage: DataQualityCoverage
    warnings: list[str]
    methodology_version: Literal["data-quality-v1"] = "data-quality-v1"

    @classmethod
    def from_domain(cls, report: DataQualityReport) -> "DataQualityResponse":
        failed_count = sum(
            item.status == DataQualityStatus.REFRESH_FAILED for item in report.items
        )
        warnings = (
            [f"{failed_count} 个标的最近一次刷新失败，已保留之前的数据。"]
            if failed_count
            else []
        )
        return cls(
            data=DataQualityData(
                items=[DataQualityItemSchema.from_domain(item) for item in report.items]
            ),
            as_of=max(
                (
                    item.last_observation_date
                    for item in report.items
                    if item.last_observation_date is not None
                ),
                default=None,
            ),
            calculated_at=report.calculated_at,
            coverage=DataQualityCoverage(
                tracked_count=report.tracked_count,
                available_count=report.available_count,
                problem_count=report.problem_count,
            ),
            warnings=warnings,
        )


class MarketRefreshRequest(BaseModel):
    instrument_ids: set[int] | None = Field(default=None, max_length=500)


class RefreshResultSchema(BaseModel):
    instrument_id: int
    code: str
    status: RefreshStatus
    accepted_rows: int
    written_rows: int
    error_code: str | None
    error_message: str | None

    @classmethod
    def from_domain(cls, value: RefreshResult) -> "RefreshResultSchema":
        return cls.model_validate(value, from_attributes=True)


class MarketRefreshData(BaseModel):
    results: list[RefreshResultSchema]
    quality: DataQualityResponse


class MarketRefreshResponse(BaseModel):
    data: MarketRefreshData

    @classmethod
    def from_domain(cls, report: RefreshReport) -> "MarketRefreshResponse":
        return cls(
            data=MarketRefreshData(
                results=[RefreshResultSchema.from_domain(item) for item in report.results],
                quality=DataQualityResponse.from_domain(report.quality),
            )
        )
