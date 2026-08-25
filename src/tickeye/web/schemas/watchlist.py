"""Public watchlist contracts."""

from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from tickeye.application.watchlist_service import (
    WatchlistItemDraft,
    WatchlistItemView,
    WatchlistView,
)
from tickeye.domain.enums import AssetClass, InstrumentType


class CreateWatchlistRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class WatchlistItemInput(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=200)
    instrument_type: InstrumentType
    market: str = Field(min_length=1, max_length=32)
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    asset_class: AssetClass
    region: str = Field(min_length=1, max_length=64)
    reason: str | None = Field(default=None, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=10)

    def to_domain(self) -> WatchlistItemDraft:
        return WatchlistItemDraft(
            code=self.code,
            name=self.name,
            instrument_type=self.instrument_type,
            market=self.market,
            currency=self.currency,
            asset_class=self.asset_class,
            region=self.region,
            reason=self.reason,
            tags=tuple(self.tags),
        )


class UpdateWatchlistItemRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=10)


class WatchlistItemSchema(BaseModel):
    item_id: int
    instrument_id: int
    code: str
    name: str
    instrument_type: InstrumentType
    market: str
    currency: str
    asset_class: AssetClass
    region: str
    reason: str | None
    tags: list[str]
    held: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, value: WatchlistItemView) -> "WatchlistItemSchema":
        return cls.model_validate(value, from_attributes=True)


class WatchlistSchema(BaseModel):
    watchlist_id: int
    name: str
    items: list[WatchlistItemSchema]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, value: WatchlistView) -> "WatchlistSchema":
        return cls(
            watchlist_id=value.watchlist_id,
            name=value.name,
            items=[WatchlistItemSchema.from_domain(item) for item in value.items],
            created_at=value.created_at,
            updated_at=value.updated_at,
        )


class WatchlistData(BaseModel):
    items: list[WatchlistSchema]


class WatchlistCoverage(BaseModel):
    watchlist_count: int
    item_count: int
    held_item_count: int


class WatchlistResponse(BaseModel):
    data: WatchlistData
    as_of: date | None = None
    calculated_at: datetime
    coverage: WatchlistCoverage
    warnings: list[str]
    methodology_version: Literal["user-watchlists-v1"] = "user-watchlists-v1"

    @classmethod
    def from_domain(cls, values: tuple[WatchlistView, ...]) -> "WatchlistResponse":
        all_items = [item for watchlist in values for item in watchlist.items]
        return cls(
            data=WatchlistData(
                items=[WatchlistSchema.from_domain(value) for value in values]
            ),
            calculated_at=datetime.now(UTC),
            coverage=WatchlistCoverage(
                watchlist_count=len(values),
                item_count=len(all_items),
                held_item_count=sum(item.held for item in all_items),
            ),
            warnings=[
                "观察列表来自用户主动录入，不代表推荐、排名或适合买入。"
            ],
        )
