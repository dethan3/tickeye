"""Persistence operations for user-curated watchlists."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from tickeye.infrastructure.db import (
    InstrumentRecord,
    WatchlistItemRecord,
    WatchlistRecord,
)


class WatchlistRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def all(self, profile_id: int) -> list[WatchlistRecord]:
        return list(
            self.session.scalars(
                select(WatchlistRecord)
                .where(WatchlistRecord.profile_id == profile_id)
                .order_by(WatchlistRecord.id)
            )
        )

    def get(self, profile_id: int, watchlist_id: int) -> WatchlistRecord | None:
        return self.session.scalar(
            select(WatchlistRecord).where(
                WatchlistRecord.id == watchlist_id,
                WatchlistRecord.profile_id == profile_id,
            )
        )

    def add(self, watchlist: WatchlistRecord) -> WatchlistRecord:
        self.session.add(watchlist)
        self.session.flush()
        return watchlist

    def items(
        self, watchlist_id: int
    ) -> list[tuple[WatchlistItemRecord, InstrumentRecord]]:
        return list(
            self.session.execute(
                select(WatchlistItemRecord, InstrumentRecord)
                .join(
                    InstrumentRecord,
                    WatchlistItemRecord.instrument_id == InstrumentRecord.id,
                )
                .where(WatchlistItemRecord.watchlist_id == watchlist_id)
                .order_by(WatchlistItemRecord.id)
            ).tuples()
        )

    def get_item(
        self, watchlist_id: int, item_id: int
    ) -> WatchlistItemRecord | None:
        return self.session.scalar(
            select(WatchlistItemRecord).where(
                WatchlistItemRecord.id == item_id,
                WatchlistItemRecord.watchlist_id == watchlist_id,
            )
        )

    def item_for_instrument(
        self, watchlist_id: int, instrument_id: int
    ) -> WatchlistItemRecord | None:
        return self.session.scalar(
            select(WatchlistItemRecord).where(
                WatchlistItemRecord.watchlist_id == watchlist_id,
                WatchlistItemRecord.instrument_id == instrument_id,
            )
        )

    def is_watched(self, profile_id: int, instrument_id: int) -> bool:
        return self.session.scalar(
            select(WatchlistItemRecord.id)
            .join(WatchlistRecord, WatchlistItemRecord.watchlist_id == WatchlistRecord.id)
            .where(
                WatchlistRecord.profile_id == profile_id,
                WatchlistItemRecord.instrument_id == instrument_id,
            )
            .limit(1)
        ) is not None
