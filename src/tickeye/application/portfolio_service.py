"""Current portfolio use cases, validation, snapshots, and CSV confirmation."""

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from tickeye.application.errors import (
    DuplicateImportError,
    PortfolioConflictError,
    PortfolioValidationError,
    ValidationIssue,
)
from tickeye.application.portfolio_csv import parse_portfolio_csv
from tickeye.domain.enums import AssetClass, InstrumentType
from tickeye.domain.models import PortfolioFacts, PositionInput
from tickeye.infrastructure.db import (
    AccountRecord,
    InstrumentRecord,
    PositionRecord,
    PositionSnapshotRecord,
)
from tickeye.infrastructure.repositories import PortfolioRepository

CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._:-]{0,31}$")


@dataclass(frozen=True, slots=True)
class ImportPreview:
    """Validated rows and immutable token shown before any CSV mutation."""

    preview_token: str
    positions: tuple[PositionInput, ...]
    issues: tuple[ValidationIssue, ...]
    duplicate_import: bool

    @property
    def valid(self) -> bool:
        return not self.issues and not self.duplicate_import


def csv_fingerprint(content: str) -> str:
    payload = f"tickeye-portfolio-csv-v1\0{content}".encode()
    return hashlib.sha256(payload).hexdigest()


def _normal_text(value: str) -> str:
    return " ".join(value.strip().split())


def _normal_currency(value: str) -> str:
    return value.strip().upper()


def _decimal_fits(value: Decimal, *, integer_digits: int, decimal_places: int) -> bool:
    if not value.is_finite():
        return False
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int):
        return False
    fraction_digits = max(-exponent, 0)
    whole_digits = 1 if value.is_zero() else max(value.adjusted() + 1, 1)
    return fraction_digits <= decimal_places and whole_digits <= integer_digits


def _position_payload(portfolio: PortfolioFacts) -> str:
    payload = {
        "profile_id": portfolio.profile_id,
        "revision": portfolio.revision,
        "positions": [
            {
                "id": item.id,
                "account_id": item.account_id,
                "account_name": item.account_name,
                "institution": item.institution,
                "account_currency": item.account_currency,
                "instrument_id": item.instrument_id,
                "code": item.code,
                "name": item.name,
                "instrument_type": item.instrument_type.value,
                "market": item.market,
                "instrument_currency": item.instrument_currency,
                "asset_class": item.asset_class.value,
                "region": item.region,
                "quantity": str(item.quantity) if item.quantity is not None else None,
                "manual_value": (
                    str(item.manual_value) if item.manual_value is not None else None
                ),
                "cost": str(item.cost) if item.cost is not None else None,
                "as_of": item.as_of.isoformat(),
            }
            for item in portfolio.positions
        ],
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


class PortfolioService:
    """Transaction boundary for all current-position changes."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def get_portfolio(self) -> PortfolioFacts:
        with self.session_factory.begin() as session:
            repository = PortfolioRepository(session)
            profile = repository.get_or_create_profile()
            return repository.load(profile.id)

    def preview_csv(self, content: str) -> ImportPreview:
        fingerprint = csv_fingerprint(content)
        parsed = parse_portfolio_csv(content)
        issues = list(parsed.issues)
        duplicate = False
        positions = parsed.positions
        with self.session_factory.begin() as session:
            repository = PortfolioRepository(session)
            profile = repository.get_or_create_profile()
            if not issues:
                positions, validation_issues = self._normalize_positions(
                    repository,
                    profile.id,
                    positions,
                )
                issues.extend(validation_issues)
            duplicate = repository.has_import(fingerprint)
        return ImportPreview(
            preview_token=fingerprint,
            positions=positions,
            issues=tuple(issues),
            duplicate_import=duplicate,
        )

    def confirm_csv(
        self,
        *,
        content: str,
        preview_token: str,
        expected_revision: int,
    ) -> PortfolioFacts:
        expected_token = csv_fingerprint(content)
        if preview_token != expected_token:
            raise PortfolioValidationError(
                [
                    ValidationIssue(
                        "preview_changed",
                        "CSV 内容已在预览后改变，请重新预览。",
                        field="preview_token",
                    )
                ]
            )
        preview = self.preview_csv(content)
        if preview.duplicate_import:
            raise DuplicateImportError("This CSV batch was already imported.")
        if preview.issues:
            raise PortfolioValidationError(list(preview.issues))
        return self.replace_positions(
            expected_revision=expected_revision,
            positions=preview.positions,
            source="csv",
            import_fingerprint=expected_token,
        )

    def replace_positions(
        self,
        *,
        expected_revision: int,
        positions: tuple[PositionInput, ...],
        source: str = "manual",
        import_fingerprint: str | None = None,
    ) -> PortfolioFacts:
        with self.session_factory.begin() as session:
            repository = PortfolioRepository(session)
            profile = repository.get_or_create_profile()
            if import_fingerprint is not None and repository.has_import(import_fingerprint):
                raise DuplicateImportError("This CSV batch was already imported.")

            normalized, issues = self._normalize_positions(
                repository,
                profile.id,
                positions,
            )
            if issues:
                raise PortfolioValidationError(issues)
            new_revision = repository.advance_revision(profile.id, expected_revision)
            if new_revision is None:
                raise PortfolioConflictError(
                    "Portfolio changed after it was loaded; reload before saving."
                )

            self._persist_replacement(session, repository, profile.id, normalized)
            session.flush()
            portfolio = repository.load(profile.id)
            payload_json = _position_payload(portfolio)
            session.add(
                PositionSnapshotRecord(
                    profile_id=profile.id,
                    source=source,
                    payload_hash=hashlib.sha256(payload_json.encode()).hexdigest(),
                    payload_json=payload_json,
                    import_fingerprint=import_fingerprint,
                )
            )
            session.flush()
            return repository.load(profile.id)

    def _normalize_positions(
        self,
        repository: PortfolioRepository,
        profile_id: int,
        positions: tuple[PositionInput, ...],
    ) -> tuple[tuple[PositionInput, ...], list[ValidationIssue]]:
        issues: list[ValidationIssue] = []
        normalized: list[PositionInput] = []
        identities: set[tuple[str, str, str]] = set()
        position_ids: set[int] = set()
        account_facts: dict[str, tuple[str | None, str]] = {}
        instrument_facts: dict[
            tuple[str, str],
            tuple[str | None, InstrumentType | None, str | None, AssetClass | None, str | None],
        ] = {}
        existing_ids = {row.id for row, _, _ in repository.position_rows(profile_id)}

        for index, raw in enumerate(positions):
            row = index + 1
            account_name = _normal_text(raw.account_name)
            institution = _normal_text(raw.institution) if raw.institution else None
            account_currency = _normal_currency(raw.account_currency)
            code = raw.code.strip().upper()
            market = raw.market.strip().upper()
            name = _normal_text(raw.name) if raw.name else None
            instrument_currency = (
                _normal_currency(raw.instrument_currency) if raw.instrument_currency else None
            )
            region = _normal_text(raw.region) if raw.region else None
            existing_account = (
                repository.get_account(profile_id, account_name) if account_name else None
            )
            if institution is None and existing_account is not None:
                institution = existing_account.institution

            self._validate_basic_fields(
                raw,
                row=row,
                account_name=account_name,
                account_currency=account_currency,
                code=code,
                market=market,
                issues=issues,
            )
            if raw.id is not None:
                if raw.id in position_ids:
                    issues.append(
                        ValidationIssue(
                            "duplicate_position_id",
                            "同一持仓 ID 不能出现多次。",
                            field="id",
                            row=row,
                        )
                    )
                elif raw.id not in existing_ids:
                    issues.append(
                        ValidationIssue(
                            "unknown_position",
                            "持仓不存在或已经被删除。",
                            field="id",
                            row=row,
                        )
                    )
                position_ids.add(raw.id)

            identity = (account_name.casefold(), code, market)
            if identity in identities:
                issues.append(
                    ValidationIssue(
                        "duplicate_position",
                        "同一账户中不能重复出现相同标的。",
                        field="code",
                        row=row,
                    )
                )
            identities.add(identity)

            instrument = repository.get_instrument(code, market) if code and market else None
            if instrument is None and (
                name is None
                or raw.instrument_type is None
                or instrument_currency is None
                or raw.asset_class is None
                or region is None
            ):
                issues.append(
                    ValidationIssue(
                        "unknown_instrument",
                        "未知标的首次录入时必须提供名称、类型、币种、资产类别和地区。",
                        field="code",
                        row=row,
                    )
                )
            elif instrument is not None:
                name = name or instrument.name
                instrument_currency = instrument_currency or instrument.currency
                region = region or instrument.region
            if instrument_currency is not None and instrument_currency != "CNY":
                issues.append(
                    ValidationIssue(
                        "unsupported_currency",
                        "当前版本仅支持人民币账户和人民币计价资产。",
                        field="instrument_currency",
                        row=row,
                    )
                )

            account_key = account_name.casefold()
            account_fact = (institution, account_currency)
            previous_account_fact = account_facts.get(account_key)
            if previous_account_fact is not None and previous_account_fact != account_fact:
                issues.append(
                    ValidationIssue(
                        "inconsistent_account",
                        "同一账户的机构和币种必须保持一致。",
                        field="account_name",
                        row=row,
                    )
                )
            account_facts[account_key] = account_fact

            instrument_key = (code, market)
            instrument_fact = (
                name,
                raw.instrument_type or (InstrumentType(instrument.type) if instrument else None),
                instrument_currency,
                raw.asset_class or (AssetClass(instrument.asset_class) if instrument else None),
                region,
            )
            previous_instrument_fact = instrument_facts.get(instrument_key)
            if previous_instrument_fact is not None and previous_instrument_fact != instrument_fact:
                issues.append(
                    ValidationIssue(
                        "inconsistent_instrument",
                        "相同代码和市场的标的元数据必须保持一致。",
                        field="code",
                        row=row,
                    )
                )
            instrument_facts[instrument_key] = instrument_fact

            normalized.append(
                replace(
                    raw,
                    account_name=account_name,
                    institution=institution,
                    account_currency=account_currency,
                    code=code,
                    name=name,
                    market=market,
                    instrument_currency=instrument_currency,
                    instrument_type=instrument_fact[1],
                    asset_class=instrument_fact[3],
                    region=region,
                )
            )
        return tuple(normalized), issues

    @staticmethod
    def _validate_basic_fields(
        raw: PositionInput,
        *,
        row: int,
        account_name: str,
        account_currency: str,
        code: str,
        market: str,
        issues: list[ValidationIssue],
    ) -> None:
        required = {
            "account_name": account_name,
            "code": code,
            "market": market,
        }
        for field, value in required.items():
            if not value:
                issues.append(
                    ValidationIssue("required", "此字段不能为空。", field=field, row=row)
                )
        if not CODE_PATTERN.fullmatch(code):
            issues.append(
                ValidationIssue("invalid_code", "标的代码格式无效。", field="code", row=row)
            )
        if len(account_currency) != 3 or not account_currency.isalpha():
            issues.append(
                ValidationIssue(
                    "invalid_currency",
                    "币种必须是三个字母的代码。",
                    field="account_currency",
                    row=row,
                )
            )
        elif account_currency != "CNY":
            issues.append(
                ValidationIssue(
                    "unsupported_currency",
                    "当前版本仅支持人民币账户和人民币计价资产。",
                    field="account_currency",
                    row=row,
                )
            )
        for amount_field, amount in (
            ("quantity", raw.quantity),
            ("manual_value", raw.manual_value),
            ("cost", raw.cost),
        ):
            if amount is not None and (not amount.is_finite() or amount < Decimal(0)):
                issues.append(
                    ValidationIssue(
                        "nonnegative_number",
                        "必须是大于或等于零的有限数字。",
                        field=amount_field,
                        row=row,
                    )
                )
        precision_rules = (
            ("quantity", raw.quantity, 16, 8),
            ("manual_value", raw.manual_value, 22, 2),
            ("cost", raw.cost, 22, 2),
        )
        for amount_field, amount, integer_digits, decimal_places in precision_rules:
            if (
                amount is not None
                and amount.is_finite()
                and amount >= Decimal(0)
                and not _decimal_fits(
                amount,
                integer_digits=integer_digits,
                decimal_places=decimal_places,
                )
            ):
                issues.append(
                    ValidationIssue(
                        "numeric_precision",
                        f"最多允许 {integer_digits} 位整数和 {decimal_places} 位小数。",
                        field=amount_field,
                        row=row,
                    )
                )
        if raw.quantity is None and raw.manual_value is None:
            issues.append(
                ValidationIssue(
                    "missing_value",
                    "数量和手工市值至少填写一项。",
                    field="quantity",
                    row=row,
                )
            )
        if raw.as_of > date.today():
            issues.append(
                ValidationIssue(
                    "future_date",
                    "持仓日期不能晚于今天。",
                    field="as_of",
                    row=row,
                )
            )

    @staticmethod
    def _persist_replacement(
        session: Session,
        repository: PortfolioRepository,
        profile_id: int,
        positions: tuple[PositionInput, ...],
    ) -> None:
        existing_rows = repository.position_rows(profile_id)
        requested_ids = {item.id for item in positions if item.id is not None}
        requested_identities = {
            (item.account_name.casefold(), item.code, item.market) for item in positions
        }
        requested_identity_by_id = {
            item.id: (item.account_name.casefold(), item.code, item.market)
            for item in positions
            if item.id is not None
        }
        deleted_ids: set[int] = set()

        for position, account, instrument in existing_rows:
            identity = (account.name.casefold(), instrument.code, instrument.market)
            identity_changed = (
                position.id in requested_identity_by_id
                and requested_identity_by_id[position.id] != identity
            )
            omitted = position.id not in requested_ids and identity not in requested_identities
            if identity_changed or omitted:
                session.delete(position)
                deleted_ids.add(position.id)
        session.flush()
        existing_by_id = {
            position.id: position
            for position, _, _ in existing_rows
            if position.id not in deleted_ids
        }
        existing_identity = {
            (account.name.casefold(), instrument.code, instrument.market): position
            for position, account, instrument in existing_rows
            if position.id not in deleted_ids
        }

        account_cache: dict[str, AccountRecord] = {}
        instrument_cache: dict[tuple[str, str], InstrumentRecord] = {}
        for item in positions:
            account_key = item.account_name.casefold()
            account_candidate = account_cache.get(account_key) or repository.get_account(
                profile_id, item.account_name
            )
            if account_candidate is None:
                account = AccountRecord(
                    profile_id=profile_id,
                    name=item.account_name,
                    institution=item.institution,
                    currency=item.account_currency,
                )
                session.add(account)
                session.flush()
            else:
                account = account_candidate
                account.institution = item.institution
                account.currency = item.account_currency
            account_cache[account_key] = account

            instrument_key = (item.code, item.market)
            instrument_candidate = instrument_cache.get(
                instrument_key
            ) or repository.get_instrument(
                *instrument_key
            )
            if instrument_candidate is None:
                name = item.name
                instrument_type = item.instrument_type
                currency = item.instrument_currency
                asset_class = item.asset_class
                region = item.region
                if (
                    name is None
                    or instrument_type is None
                    or currency is None
                    or asset_class is None
                    or region is None
                ):
                    raise RuntimeError("Validated instrument metadata unexpectedly missing.")
                instrument = InstrumentRecord(
                    code=item.code,
                    name=name,
                    type=instrument_type.value,
                    market=item.market,
                    currency=currency,
                    asset_class=asset_class.value,
                    region=region,
                )
                session.add(instrument)
                session.flush()
            else:
                instrument = instrument_candidate
                instrument.name = item.name or instrument.name
                instrument.type = (
                    item.instrument_type.value if item.instrument_type else instrument.type
                )
                instrument.currency = item.instrument_currency or instrument.currency
                instrument.asset_class = (
                    item.asset_class.value if item.asset_class else instrument.asset_class
                )
                instrument.region = item.region or instrument.region
            instrument_cache[instrument_key] = instrument

            identity = (account_key, item.code, item.market)
            position_candidate = existing_by_id.get(item.id) if item.id is not None else None
            if position_candidate is None:
                position_candidate = existing_identity.get(identity)
            if position_candidate is None:
                position = PositionRecord(account_id=account.id, instrument_id=instrument.id)
                session.add(position)
            else:
                position = position_candidate
            position.account_id = account.id
            position.instrument_id = instrument.id
            position.quantity = item.quantity
            position.manual_value = item.manual_value
            position.cost = item.cost
            position.as_of = item.as_of
