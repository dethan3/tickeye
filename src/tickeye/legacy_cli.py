"""One-time, explicit TickEye v1 configuration migration command."""

import argparse
import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from tickeye.application.legacy_migration import (
    LegacyMigrationError,
    LegacyMigrationPreview,
    LegacyMigrationResult,
    LegacyMigrationService,
)
from tickeye.config import PROJECT_ROOT, get_settings
from tickeye.infrastructure.db import create_db_engine, create_session_factory


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise LegacyMigrationError(
            "config_read_failed", f"无法读取 {path}：{error.strerror or error}。"
        ) from error


def _json_default(value: object) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    raise TypeError(f"Unsupported value: {type(value).__name__}")


def _print_json(value: Any) -> None:
    payload = asdict(value)
    if isinstance(value, LegacyMigrationPreview):
        payload["can_confirm"] = value.can_confirm
    print(json.dumps(payload, default=_json_default, ensure_ascii=False, indent=2))


def _print_preview(preview: LegacyMigrationPreview) -> None:
    print("TickEye v1 迁移预览")
    print(f"目标观察分组：{preview.target_watchlist}")
    print(f"可迁移基金/ETF：{len(preview.candidates)}")
    for candidate in preview.candidates:
        suffix = "（已存在，将跳过）" if candidate.already_present else ""
        print(
            f"  - {candidate.code} {candidate.name} [{candidate.instrument_type.value}/"
            f"{candidate.asset_class.value}/{candidate.region}]{suffix}"
        )
    print(f"暂缓指数或未识别标的：{len(preview.deferred_items)}")
    for deferred_item in preview.deferred_items:
        print(
            f"  - {deferred_item.code} {deferred_item.name}："
            f"{deferred_item.reason}"
        )
    print(f"配置问题：{len(preview.issues)}")
    for issue in preview.issues:
        prefix = f"第 {issue.row} 项" if issue.row is not None else "配置"
        print(f"  - {prefix} [{issue.code}] {issue.message}")
    print(f"可确认：{'是' if preview.can_confirm else '否'}")
    print(f"预览令牌：{preview.preview_token}")
    if preview.can_confirm:
        print("确认时重新运行并添加：--confirm --preview-token <上面的令牌>")


def _print_result(result: LegacyMigrationResult) -> None:
    print("TickEye v1 配置迁移完成")
    print(f"目标观察分组：{result.target_watchlist} (ID {result.watchlist_id})")
    print(f"新增观察标的：{result.imported_count}")
    print(f"已存在并跳过：{result.skipped_existing_count}")
    print(f"暂缓未迁移：{result.deferred_count}")
    print("迁移没有创建或修改任何真实持仓。")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preview or confirm migration of TickEye v1 funds_config.json"
    )
    parser.add_argument(
        "--funds-config",
        type=Path,
        default=PROJECT_ROOT / "legacy" / "v1" / "funds_config.json",
    )
    parser.add_argument(
        "--indices-config",
        type=Path,
        default=PROJECT_ROOT / "legacy" / "v1" / "indices_config.json",
    )
    parser.add_argument("--target-watchlist", default="v1 迁移观察列表")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--preview-token")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    if args.confirm and not args.preview_token:
        parser.error("--confirm 必须同时提供 --preview-token")

    settings = get_settings()
    engine = create_db_engine(settings.database_url, echo=settings.debug)
    service = LegacyMigrationService(create_session_factory(engine))
    try:
        funds_content = _read(args.funds_config)
        indices_content = _read(args.indices_config)
        if args.confirm:
            result = service.confirm(
                funds_content,
                indices_content,
                args.preview_token,
                args.target_watchlist,
            )
            _print_json(result) if args.as_json else _print_result(result)
        else:
            preview = service.preview(
                funds_content, indices_content, args.target_watchlist
            )
            _print_json(preview) if args.as_json else _print_preview(preview)
            if not preview.can_confirm:
                raise SystemExit(2)
    except LegacyMigrationError as error:
        if args.as_json:
            print(
                json.dumps(
                    {"error": {"code": error.code, "message": error.message}},
                    ensure_ascii=False,
                )
            )
        else:
            print(f"迁移失败 [{error.code}]：{error.message}")
        raise SystemExit(2) from error
    except SQLAlchemyError as error:
        message = "数据库不可用或迁移尚未完成，请先运行 alembic upgrade head。"
        if args.as_json:
            print(
                json.dumps(
                    {"error": {"code": "database_not_ready", "message": message}},
                    ensure_ascii=False,
                )
            )
        else:
            print(f"迁移失败 [database_not_ready]：{message}")
        raise SystemExit(2) from error
    finally:
        engine.dispose()
