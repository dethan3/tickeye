"""Manage user-curated watchlists without changing actual positions."""

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from tickeye.domain.enums import AssetClass, InstrumentType
from tickeye.infrastructure.db import (
    InstrumentRecord,
    WatchlistItemRecord,
    WatchlistRecord,
)
from tickeye.infrastructure.repositories import (
    PortfolioRepository,
    WatchlistRepository,
)

CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._:-]{0,31}$")


class WatchlistNotFoundError(Exception):
    pass


class WatchlistConflictError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class WatchlistValidationError(Exception):
    def __init__(self, code: str, message: str, field: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field


@dataclass(frozen=True, slots=True)
class WatchlistItemDraft:
    code: str
    name: str
    instrument_type: InstrumentType
    market: str
    currency: str
    asset_class: AssetClass
    region: str
    reason: str | None
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WatchlistItemView:
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
    tags: tuple[str, ...]
    held: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class WatchlistView:
    watchlist_id: int
    name: str
    items: tuple[WatchlistItemView, ...]
    created_at: datetime
    updated_at: datetime


def _aware_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _clean_text(value: str) -> str:
    return " ".join(value.strip().split())


def _tags(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        tag = _clean_text(raw)
        if not tag:
            continue
        if len(tag) > 30:
            raise WatchlistValidationError(
                "tag_too_long", "每个标签最多 30 个字符。", "tags"
            )
        folded = tag.casefold()
        if folded not in seen:
            normalized.append(tag)
            seen.add(folded)
    if len(normalized) > 10:
        raise WatchlistValidationError(
            "too_many_tags", "每个观察标的最多设置 10 个标签。", "tags"
        )
    return tuple(normalized)


class WatchlistService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def list(self) -> tuple[WatchlistView, ...]:
        with self.session_factory.begin() as session:
            profile = PortfolioRepository(session).get_or_create_profile()
            return self._views(session, profile.id)

    def create(self, name: str) -> tuple[WatchlistView, ...]:
        clean_name = _clean_text(name)
        if not clean_name:
            raise WatchlistValidationError(
                "invalid_name", "观察分组名称不能为空。", "name"
            )
        with self.session_factory.begin() as session:
            profile = PortfolioRepository(session).get_or_create_profile()
            repository = WatchlistRepository(session)
            if any(
                item.name.casefold() == clean_name.casefold()
                for item in repository.all(profile.id)
            ):
                raise WatchlistConflictError(
                    "duplicate_watchlist", "已经存在同名观察分组。"
                )
            now = datetime.now(UTC)
            repository.add(
                WatchlistRecord(
                    profile_id=profile.id,
                    name=clean_name,
                    created_at=now,
                    updated_at=now,
                )
            )
            return self._views(session, profile.id)

    def delete(self, watchlist_id: int) -> tuple[WatchlistView, ...]:
        with self.session_factory.begin() as session:
            profile = PortfolioRepository(session).get_or_create_profile()
            repository = WatchlistRepository(session)
            watchlist = repository.get(profile.id, watchlist_id)
            if watchlist is None:
                raise WatchlistNotFoundError
            session.delete(watchlist)
            session.flush()
            return self._views(session, profile.id)

    def add_item(
        self, watchlist_id: int, draft: WatchlistItemDraft
    ) -> tuple[WatchlistView, ...]:
        normalized = self._validate_draft(draft)
        with self.session_factory.begin() as session:
            portfolio_repository = PortfolioRepository(session)
            profile = portfolio_repository.get_or_create_profile()
            repository = WatchlistRepository(session)
            watchlist = repository.get(profile.id, watchlist_id)
            if watchlist is None:
                raise WatchlistNotFoundError
            instrument = portfolio_repository.get_instrument(
                normalized.code, normalized.market
            )
            if instrument is None:
                instrument = InstrumentRecord(
                    code=normalized.code,
                    name=normalized.name,
                    type=normalized.instrument_type.value,
                    market=normalized.market,
                    currency=normalized.currency,
                    asset_class=normalized.asset_class.value,
                    region=normalized.region,
                )
                session.add(instrument)
                session.flush()
            elif InstrumentType(instrument.type) == InstrumentType.CASH:
                raise WatchlistValidationError(
                    "unsupported_watch_type",
                    "现金不需要加入观察列表。",
                    "instrument_type",
                )
            if repository.item_for_instrument(watchlist.id, instrument.id) is not None:
                raise WatchlistConflictError(
                    "duplicate_watchlist_item", "这个标的已经在当前观察分组中。"
                )
            now = datetime.now(UTC)
            session.add(
                WatchlistItemRecord(
                    watchlist_id=watchlist.id,
                    instrument_id=instrument.id,
                    reason=normalized.reason,
                    tags_json=json.dumps(normalized.tags, ensure_ascii=False),
                    created_at=now,
                    updated_at=now,
                )
            )
            session.flush()
            return self._views(session, profile.id)

    def update_item(
        self,
        watchlist_id: int,
        item_id: int,
        reason: str | None,
        tags: tuple[str, ...],
    ) -> tuple[WatchlistView, ...]:
        clean_reason = self._reason(reason)
        clean_tags = _tags(tags)
        with self.session_factory.begin() as session:
            profile = PortfolioRepository(session).get_or_create_profile()
            repository = WatchlistRepository(session)
            watchlist = repository.get(profile.id, watchlist_id)
            if watchlist is None:
                raise WatchlistNotFoundError
            item = repository.get_item(watchlist.id, item_id)
            if item is None:
                raise WatchlistNotFoundError
            item.reason = clean_reason
            item.tags_json = json.dumps(clean_tags, ensure_ascii=False)
            item.updated_at = datetime.now(UTC)
            return self._views(session, profile.id)

    def remove_item(
        self, watchlist_id: int, item_id: int
    ) -> tuple[WatchlistView, ...]:
        with self.session_factory.begin() as session:
            profile = PortfolioRepository(session).get_or_create_profile()
            repository = WatchlistRepository(session)
            watchlist = repository.get(profile.id, watchlist_id)
            if watchlist is None:
                raise WatchlistNotFoundError
            item = repository.get_item(watchlist.id, item_id)
            if item is None:
                raise WatchlistNotFoundError
            session.delete(item)
            session.flush()
            return self._views(session, profile.id)

    @classmethod
    def _validate_draft(cls, draft: WatchlistItemDraft) -> WatchlistItemDraft:
        code = draft.code.strip().upper()
        market = draft.market.strip().upper()
        name = _clean_text(draft.name)
        region = _clean_text(draft.region)
        currency = draft.currency.strip().upper()
        if not CODE_PATTERN.fullmatch(code):
            raise WatchlistValidationError(
                "invalid_code", "标的代码格式无效。", "code"
            )
        if not name:
            raise WatchlistValidationError("invalid_name", "标的名称不能为空。", "name")
        if not market:
            raise WatchlistValidationError("invalid_market", "市场不能为空。", "market")
        if currency != "CNY":
            raise WatchlistValidationError(
                "unsupported_currency", "MVP 只支持人民币计价标的。", "currency"
            )
        if draft.instrument_type == InstrumentType.CASH:
            raise WatchlistValidationError(
                "unsupported_watch_type", "现金不需要加入观察列表。", "instrument_type"
            )
        if not region:
            raise WatchlistValidationError("invalid_region", "地区不能为空。", "region")
        return WatchlistItemDraft(
            code=code,
            name=name,
            instrument_type=draft.instrument_type,
            market=market,
            currency=currency,
            asset_class=draft.asset_class,
            region=region,
            reason=cls._reason(draft.reason),
            tags=_tags(draft.tags),
        )

    @staticmethod
    def _reason(value: str | None) -> str | None:
        if value is None:
            return None
        reason = value.strip()
        if len(reason) > 1000:
            raise WatchlistValidationError(
                "reason_too_long", "观察理由最多 1000 个字符。", "reason"
            )
        return reason or None

    @staticmethod
    def _views(session: Session, profile_id: int) -> tuple[WatchlistView, ...]:
        repository = WatchlistRepository(session)
        held_ids = {
            item.instrument_id
            for item in PortfolioRepository(session).load(profile_id).positions
        }
        return tuple(
            WatchlistView(
                watchlist_id=watchlist.id,
                name=watchlist.name,
                items=tuple(
                    WatchlistItemView(
                        item_id=item.id,
                        instrument_id=instrument.id,
                        code=instrument.code,
                        name=instrument.name,
                        instrument_type=InstrumentType(instrument.type),
                        market=instrument.market,
                        currency=instrument.currency,
                        asset_class=AssetClass(instrument.asset_class),
                        region=instrument.region,
                        reason=item.reason,
                        tags=tuple(json.loads(item.tags_json)),
                        held=instrument.id in held_ids,
                        created_at=_aware_utc(item.created_at),
                        updated_at=_aware_utc(item.updated_at),
                    )
                    for item, instrument in repository.items(watchlist.id)
                ),
                created_at=_aware_utc(watchlist.created_at),
                updated_at=_aware_utc(watchlist.updated_at),
            )
            for watchlist in repository.all(profile_id)
        )
