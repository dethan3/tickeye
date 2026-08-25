from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from tickeye.application.legacy_migration import (
    LegacyMigrationError,
    LegacyMigrationService,
)
from tickeye.domain.enums import AssetClass, InstrumentType
from tickeye.infrastructure.db import (
    Base,
    PositionRecord,
    ProfileRecord,
    WatchlistItemRecord,
    WatchlistRecord,
    create_db_engine,
    create_session_factory,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LEGACY_ROOT = PROJECT_ROOT / "legacy" / "v1"
FUNDS_CONTENT = (LEGACY_ROOT / "funds_config.json").read_text(encoding="utf-8")
INDICES_CONTENT = (LEGACY_ROOT / "indices_config.json").read_text(encoding="utf-8")


def build_service(tmp_path: Path) -> tuple[LegacyMigrationService, Engine]:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    Base.metadata.create_all(engine)
    return LegacyMigrationService(create_session_factory(engine)), engine


def test_preview_classifies_mixed_v1_config_without_writing_database(
    tmp_path: Path,
) -> None:
    service, engine = build_service(tmp_path)

    preview = service.preview(FUNDS_CONTENT, INDICES_CONTENT)

    assert preview.can_confirm is True
    assert {item.code for item in preview.candidates} == {
        "015596",
        "019671",
        "021842",
        "520550",
    }
    assert {item.code for item in preview.deferred_items} == {
        "000001",
        "HSI",
        "NDX",
        "SPX",
    }
    by_code = {item.code: item for item in preview.candidates}
    assert by_code["015596"].instrument_type == InstrumentType.FUND
    assert by_code["015596"].asset_class == AssetClass.EQUITY
    assert by_code["019671"].instrument_type == InstrumentType.QDII_FUND
    assert by_code["019671"].region == "中国香港"
    assert by_code["021842"].asset_class == AssetClass.MIXED
    assert by_code["520550"].instrument_type == InstrumentType.ETF
    assert len(preview.preview_token) == 64

    session_factory = service.session_factory
    with session_factory() as session:
        profiles = session.scalar(select(func.count(ProfileRecord.id)))
    engine.dispose()
    assert profiles == 0


def test_confirm_is_atomic_idempotent_and_never_creates_positions(
    tmp_path: Path,
) -> None:
    service, engine = build_service(tmp_path)
    preview = service.preview(FUNDS_CONTENT, INDICES_CONTENT)

    result = service.confirm(
        FUNDS_CONTENT,
        INDICES_CONTENT,
        preview.preview_token,
    )
    repeated_preview = service.preview(FUNDS_CONTENT, INDICES_CONTENT)
    repeated = service.confirm(
        FUNDS_CONTENT,
        INDICES_CONTENT,
        repeated_preview.preview_token,
    )

    assert result.imported_count == 4
    assert result.skipped_existing_count == 0
    assert result.deferred_count == 4
    assert all(item.already_present for item in repeated_preview.candidates)
    assert repeated.imported_count == 0
    assert repeated.skipped_existing_count == 4
    with service.session_factory() as session:
        profile = session.scalar(select(ProfileRecord))
        watchlists = session.scalar(select(func.count(WatchlistRecord.id)))
        watch_items = list(
            session.scalars(
                select(WatchlistItemRecord).order_by(WatchlistItemRecord.id)
            )
        )
        positions = session.scalar(select(func.count(PositionRecord.id)))
    engine.dispose()
    assert profile is not None
    assert profile.revision == 0
    assert watchlists == 1
    assert len(watch_items) == 4
    assert all(item.tags_json == '["v1迁移", "待核对"]' for item in watch_items)
    assert positions == 0


def test_confirm_rejects_stale_token_and_source_issues(tmp_path: Path) -> None:
    service, engine = build_service(tmp_path)

    with pytest.raises(LegacyMigrationError, match="预览令牌不匹配"):
        service.confirm(FUNDS_CONTENT, INDICES_CONTENT, "0" * 64)

    invalid_content = (
        '{"items":[{"code":"015596","name":"A"},'
        '{"code":"015596","name":"B"}]}'
    )
    invalid = service.preview(invalid_content, INDICES_CONTENT)
    assert invalid.can_confirm is False
    assert invalid.issues[0].code == "duplicate_code"
    with pytest.raises(LegacyMigrationError, match="预览存在问题"):
        service.confirm(
            invalid_content,
            INDICES_CONTENT,
            invalid.preview_token,
        )
    with service.session_factory() as session:
        profiles = session.scalar(select(func.count(ProfileRecord.id)))
    engine.dispose()
    assert profiles == 0
