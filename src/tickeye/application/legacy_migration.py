"""Preview and atomically migrate TickEye v1 watch configuration."""

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from tickeye.domain.enums import AssetClass, InstrumentType
from tickeye.infrastructure.db import (
    InstrumentRecord,
    ProfileRecord,
    WatchlistItemRecord,
    WatchlistRecord,
)
from tickeye.infrastructure.repositories import PortfolioRepository, WatchlistRepository


class LegacyMigrationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class LegacyMigrationIssue:
    code: str
    message: str
    row: int | None = None


@dataclass(frozen=True, slots=True)
class DeferredLegacyItem:
    code: str
    name: str
    reason: str


@dataclass(frozen=True, slots=True)
class LegacyWatchCandidate:
    code: str
    name: str
    instrument_type: InstrumentType
    market: str
    currency: str
    asset_class: AssetClass
    region: str
    already_present: bool = False


@dataclass(frozen=True, slots=True)
class LegacyMigrationPreview:
    preview_token: str
    target_watchlist: str
    candidates: tuple[LegacyWatchCandidate, ...]
    deferred_items: tuple[DeferredLegacyItem, ...]
    issues: tuple[LegacyMigrationIssue, ...]

    @property
    def can_confirm(self) -> bool:
        return bool(self.candidates) and not self.issues


@dataclass(frozen=True, slots=True)
class LegacyMigrationResult:
    target_watchlist: str
    watchlist_id: int
    imported_count: int
    skipped_existing_count: int
    deferred_count: int


def _decode_json(content: str, label: str) -> object:
    try:
        return json.loads(content)
    except json.JSONDecodeError as error:
        raise LegacyMigrationError(
            "invalid_json",
            f"{label} 不是有效 JSON：第 {error.lineno} 行第 {error.colno} 列。",
        ) from error


def _index_aliases(content: str) -> set[str]:
    decoded = _decode_json(content, "indices_config.json")
    if not isinstance(decoded, dict) or not isinstance(decoded.get("aliases"), dict):
        raise LegacyMigrationError(
            "invalid_indices_config",
            "indices_config.json 必须包含 aliases 对象。",
        )
    return {str(code).strip().upper() for code in decoded["aliases"]}


def _legacy_items(content: str) -> list[object]:
    decoded = _decode_json(content, "funds_config.json")
    if isinstance(decoded, list):
        return cast(list[object], decoded)
    if isinstance(decoded, dict) and isinstance(decoded.get("items"), list):
        return cast(list[object], decoded["items"])
    raise LegacyMigrationError(
        "invalid_funds_config",
        "funds_config.json 必须是数组，或包含 items 数组的对象。",
    )


def _item_facts(raw: object) -> tuple[str, str] | None:
    if isinstance(raw, dict):
        code = str(raw.get("code", "")).strip().upper()
        name = str(raw.get("name", "")).strip()
        return code, name
    if isinstance(raw, str):
        value = raw.strip()
        if "|" in value:
            code, name = value.split("|", 1)
            return code.strip().upper(), name.strip()
        return value.upper(), ""
    return None


def _instrument_type(name: str) -> InstrumentType:
    upper_name = name.upper()
    if "QDII" in upper_name:
        return InstrumentType.QDII_FUND
    if "ETF" in upper_name and "ETF联接" not in upper_name:
        return InstrumentType.ETF
    return InstrumentType.FUND


def _asset_class(name: str) -> AssetClass:
    if any(token in name for token in ("债", "固收", "货币", "同业存单")):
        return AssetClass.FIXED_INCOME
    if "混合" in name:
        return AssetClass.MIXED
    if any(token in name for token in ("黄金", "原油", "商品")):
        return AssetClass.COMMODITY
    return AssetClass.EQUITY


def _region(name: str) -> str:
    if any(token in name for token in ("港股", "恒生")):
        return "中国香港"
    if "全球" in name or "QDII" in name.upper():
        return "全球"
    return "中国"


def _token(
    target_watchlist: str,
    candidates: list[LegacyWatchCandidate],
    deferred: list[DeferredLegacyItem],
    issues: list[LegacyMigrationIssue],
) -> str:
    payload = {
        "target_watchlist": target_watchlist,
        "candidates": [
            {
                "code": item.code,
                "name": item.name,
                "instrument_type": item.instrument_type.value,
                "market": item.market,
                "currency": item.currency,
                "asset_class": item.asset_class.value,
                "region": item.region,
            }
            for item in candidates
        ],
        "deferred": [
            {"code": item.code, "name": item.name, "reason": item.reason}
            for item in deferred
        ],
        "issues": [
            {"code": item.code, "message": item.message, "row": item.row}
            for item in issues
        ],
    }
    canonical = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class LegacyMigrationService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def preview(
        self,
        funds_content: str,
        indices_content: str,
        target_watchlist: str = "v1 迁移观察列表",
    ) -> LegacyMigrationPreview:
        target = " ".join(target_watchlist.strip().split())
        if not target or len(target) > 100:
            raise LegacyMigrationError(
                "invalid_target_watchlist", "目标观察分组名称必须为 1 到 100 个字符。"
            )
        aliases = _index_aliases(indices_content)
        candidates: list[LegacyWatchCandidate] = []
        deferred: list[DeferredLegacyItem] = []
        issues: list[LegacyMigrationIssue] = []
        seen: set[str] = set()

        for row, raw in enumerate(_legacy_items(funds_content), 1):
            facts = _item_facts(raw)
            if facts is None:
                issues.append(
                    LegacyMigrationIssue(
                        "invalid_item", "配置项必须是对象或字符串。", row
                    )
                )
                continue
            code, name = facts
            if not code:
                issues.append(
                    LegacyMigrationIssue("missing_code", "标的代码不能为空。", row)
                )
                continue
            if code in seen:
                issues.append(
                    LegacyMigrationIssue(
                        "duplicate_code", f"标的代码 {code} 在源配置中重复。", row
                    )
                )
                continue
            seen.add(code)
            if not name:
                issues.append(
                    LegacyMigrationIssue(
                        "missing_name", f"标的 {code} 缺少名称，不能安全迁移。", row
                    )
                )
                continue
            if code in aliases:
                deferred.append(
                    DeferredLegacyItem(
                        code,
                        name,
                        "这是 indices_config.json 中的指数别名；V2 当前不把指数作为基金观察标的。",
                    )
                )
                continue
            if not (len(code) == 6 and code.isdigit()):
                deferred.append(
                    DeferredLegacyItem(
                        code,
                        name,
                        "无法确认它是六位基金代码，暂缓迁移并等待人工核对。",
                    )
                )
                continue
            candidates.append(
                LegacyWatchCandidate(
                    code=code,
                    name=name,
                    instrument_type=_instrument_type(name),
                    market="CN",
                    currency="CNY",
                    asset_class=_asset_class(name),
                    region=_region(name),
                )
            )

        preview_token = _token(target, candidates, deferred, issues)
        candidates = self._mark_existing(target, candidates, issues)
        return LegacyMigrationPreview(
            preview_token=preview_token,
            target_watchlist=target,
            candidates=tuple(candidates),
            deferred_items=tuple(deferred),
            issues=tuple(issues),
        )

    def _mark_existing(
        self,
        target: str,
        candidates: list[LegacyWatchCandidate],
        issues: list[LegacyMigrationIssue],
    ) -> list[LegacyWatchCandidate]:
        with self.session_factory.begin() as session:
            profile = session.scalar(select(ProfileRecord).order_by(ProfileRecord.id).limit(1))
            if profile is None:
                return candidates
            watchlist_repository = WatchlistRepository(session)
            watchlist = next(
                (
                    item
                    for item in watchlist_repository.all(profile.id)
                    if item.name.casefold() == target.casefold()
                ),
                None,
            )
            marked: list[LegacyWatchCandidate] = []
            portfolio_repository = PortfolioRepository(session)
            for candidate in candidates:
                instrument = portfolio_repository.get_instrument(
                    candidate.code, candidate.market
                )
                if instrument is not None and instrument.type == InstrumentType.CASH.value:
                    issues.append(
                        LegacyMigrationIssue(
                            "instrument_conflict",
                            f"{candidate.code} 已被保存为现金标的，不能迁移为基金。",
                        )
                    )
                already_present = (
                    watchlist is not None
                    and instrument is not None
                    and watchlist_repository.item_for_instrument(
                        watchlist.id, instrument.id
                    )
                    is not None
                )
                marked.append(replace(candidate, already_present=already_present))
            return marked

    def confirm(
        self,
        funds_content: str,
        indices_content: str,
        preview_token: str,
        target_watchlist: str = "v1 迁移观察列表",
    ) -> LegacyMigrationResult:
        preview = self.preview(funds_content, indices_content, target_watchlist)
        if preview.preview_token != preview_token:
            raise LegacyMigrationError(
                "preview_token_mismatch",
                "预览令牌不匹配；配置内容或目标分组可能已改变，请重新预览。",
            )
        if not preview.can_confirm:
            raise LegacyMigrationError(
                "preview_not_confirmable", "预览存在问题或没有可迁移标的，不能确认。"
            )

        now = datetime.now(UTC)
        imported = 0
        skipped = 0
        with self.session_factory.begin() as session:
            portfolio_repository = PortfolioRepository(session)
            profile = portfolio_repository.get_or_create_profile()
            watchlist_repository = WatchlistRepository(session)
            watchlist = next(
                (
                    item
                    for item in watchlist_repository.all(profile.id)
                    if item.name.casefold() == preview.target_watchlist.casefold()
                ),
                None,
            )
            if watchlist is None:
                watchlist = watchlist_repository.add(
                    WatchlistRecord(
                        profile_id=profile.id,
                        name=preview.target_watchlist,
                        created_at=now,
                        updated_at=now,
                    )
                )

            for candidate in preview.candidates:
                instrument = portfolio_repository.get_instrument(
                    candidate.code, candidate.market
                )
                if instrument is None:
                    instrument = InstrumentRecord(
                        code=candidate.code,
                        name=candidate.name,
                        type=candidate.instrument_type.value,
                        market=candidate.market,
                        currency=candidate.currency,
                        asset_class=candidate.asset_class.value,
                        region=candidate.region,
                    )
                    session.add(instrument)
                    session.flush()
                if (
                    watchlist_repository.item_for_instrument(
                        watchlist.id, instrument.id
                    )
                    is not None
                ):
                    skipped += 1
                    continue
                session.add(
                    WatchlistItemRecord(
                        watchlist_id=watchlist.id,
                        instrument_id=instrument.id,
                        reason=(
                            "从 TickEye v1 funds_config.json 迁移；"
                            "分类和地区由名称推断，请人工核对。"
                        ),
                        tags_json=json.dumps(
                            ["v1迁移", "待核对"], ensure_ascii=False
                        ),
                        created_at=now,
                        updated_at=now,
                    )
                )
                imported += 1
            session.flush()
            watchlist_id = watchlist.id

        return LegacyMigrationResult(
            target_watchlist=preview.target_watchlist,
            watchlist_id=watchlist_id,
            imported_count=imported,
            skipped_existing_count=skipped,
            deferred_count=len(preview.deferred_items),
        )
