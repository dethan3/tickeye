"""Strict CSV parsing for preview-before-confirm portfolio imports."""

import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import TypeVar

from tickeye.application.errors import ValidationIssue
from tickeye.domain.enums import AssetClass, InstrumentType
from tickeye.domain.models import PositionInput

REQUIRED_COLUMNS = {"account", "code", "market", "as_of"}
EnumType = TypeVar("EnumType", InstrumentType, AssetClass)


@dataclass(frozen=True, slots=True)
class ParsedPortfolioCsv:
    positions: tuple[PositionInput, ...]
    issues: tuple[ValidationIssue, ...]


def _optional_decimal(
    value: str,
    *,
    row: int,
    field: str,
    issues: list[ValidationIssue],
) -> Decimal | None:
    if not value:
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        issues.append(
            ValidationIssue("invalid_number", "必须是有效数字。", field=field, row=row)
        )
        return None
    if not parsed.is_finite():
        issues.append(
            ValidationIssue("invalid_number", "数字不能是 NaN 或无穷值。", field=field, row=row)
        )
        return None
    return parsed


def _optional_enum(
    value: str,
    enum_type: type[EnumType],
    *,
    row: int,
    field: str,
    issues: list[ValidationIssue],
) -> EnumType | None:
    if not value:
        return None
    try:
        return enum_type(value)
    except ValueError:
        choices = ", ".join(choice.value for choice in enum_type)
        issues.append(
            ValidationIssue(
                "invalid_choice",
                f"必须是以下值之一：{choices}。",
                field=field,
                row=row,
            )
        )
        return None


def parse_portfolio_csv(content: str) -> ParsedPortfolioCsv:
    """Parse rows without mutating any portfolio facts."""

    issues: list[ValidationIssue] = []
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
    raw_headers = reader.fieldnames or []
    headers = [header.strip().lower() for header in raw_headers]
    if len(set(headers)) != len(headers):
        issues.append(ValidationIssue("duplicate_column", "CSV 包含重复列名。"))
    missing = sorted(REQUIRED_COLUMNS - set(headers))
    if missing:
        issues.append(
            ValidationIssue(
                "missing_columns",
                f"CSV 缺少必需列：{', '.join(missing)}。",
            )
        )
        return ParsedPortfolioCsv(positions=(), issues=tuple(issues))

    positions: list[PositionInput] = []
    for row_number, raw_row in enumerate(reader, start=2):
        row = {
            (key or "").strip().lower(): (value or "").strip()
            for key, value in raw_row.items()
        }
        if not any(row.values()):
            continue

        try:
            as_of = date.fromisoformat(row.get("as_of", ""))
        except ValueError:
            issues.append(
                ValidationIssue(
                    "invalid_date",
                    "日期必须使用 YYYY-MM-DD 格式。",
                    field="as_of",
                    row=row_number,
                )
            )
            continue

        position = PositionInput(
            id=None,
            account_name=row.get("account", ""),
            institution=row.get("institution") or None,
            account_currency=row.get("account_currency", "CNY") or "CNY",
            code=row.get("code", ""),
            name=row.get("name") or None,
            instrument_type=_optional_enum(
                row.get("type", ""),
                InstrumentType,
                row=row_number,
                field="type",
                issues=issues,
            ),
            market=row.get("market", ""),
            instrument_currency=row.get("currency") or None,
            asset_class=_optional_enum(
                row.get("asset_class", ""),
                AssetClass,
                row=row_number,
                field="asset_class",
                issues=issues,
            ),
            region=row.get("region") or None,
            quantity=_optional_decimal(
                row.get("quantity", ""),
                row=row_number,
                field="quantity",
                issues=issues,
            ),
            manual_value=_optional_decimal(
                row.get("manual_value", ""),
                row=row_number,
                field="manual_value",
                issues=issues,
            ),
            cost=_optional_decimal(
                row.get("cost", ""),
                row=row_number,
                field="cost",
                issues=issues,
            ),
            as_of=as_of,
        )
        positions.append(position)

    if not positions and not issues:
        issues.append(ValidationIssue("empty_csv", "CSV 中没有可导入的持仓行。"))
    return ParsedPortfolioCsv(positions=tuple(positions), issues=tuple(issues))
