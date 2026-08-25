"""Export user-owned facts without treating derived caches as a ledger."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from tickeye.infrastructure.db import PolicyRuleRecord
from tickeye.infrastructure.repositories import (
    PortfolioRepository,
    ScenarioRepository,
    WatchlistRepository,
)


@dataclass(frozen=True, slots=True)
class UserDataExport:
    exported_at: datetime
    data: dict[str, Any]


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


class ExportService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def export(self) -> UserDataExport:
        exported_at = datetime.now(UTC)
        with self.session_factory.begin() as session:
            portfolio_repository = PortfolioRepository(session)
            profile = portfolio_repository.get_or_create_profile()
            portfolio = portfolio_repository.load(profile.id)
            watchlist_repository = WatchlistRepository(session)
            scenario_repository = ScenarioRepository(session)

            watchlists = []
            for watchlist in watchlist_repository.all(profile.id):
                watchlists.append(
                    {
                        "name": watchlist.name,
                        "items": [
                            {
                                "instrument": {
                                    "instrument_id": instrument.id,
                                    "code": instrument.code,
                                    "name": instrument.name,
                                    "instrument_type": instrument.type,
                                    "market": instrument.market,
                                    "currency": instrument.currency,
                                    "asset_class": instrument.asset_class,
                                    "region": instrument.region,
                                },
                                "reason": item.reason,
                                "tags": json.loads(item.tags_json),
                            }
                            for item, instrument in watchlist_repository.items(
                                watchlist.id
                            )
                        ],
                    }
                )

            scenarios = []
            for scenario in scenario_repository.all(profile.id):
                scenarios.append(
                    {
                        "name": scenario.name,
                        "status": scenario.status,
                        "base_portfolio_revision": scenario.base_portfolio_revision,
                        "candidate_instrument_id": scenario.candidate_instrument_id,
                        "base_inputs": json.loads(scenario.base_inputs_json),
                        "stress_assumptions": json.loads(scenario.assumptions_json),
                        "operations": [
                            {
                                "sequence": operation.sequence,
                                "operation_type": operation.operation_type,
                                "instrument_id": operation.instrument_id,
                                "amount": _decimal(operation.amount),
                                "target_weight": _decimal(operation.target_weight),
                                "estimated_cost": str(operation.estimated_cost),
                            }
                            for operation in scenario_repository.operations(scenario.id)
                        ],
                        "created_at": scenario.created_at.isoformat(),
                        "updated_at": scenario.updated_at.isoformat(),
                    }
                )

            policies = list(
                session.scalars(
                    select(PolicyRuleRecord)
                    .where(PolicyRuleRecord.profile_id == profile.id)
                    .order_by(PolicyRuleRecord.id)
                )
            )
            return UserDataExport(
                exported_at=exported_at,
                data={
                    "profile": {
                        "name": profile.name,
                        "base_currency": profile.base_currency,
                        "portfolio_revision": profile.revision,
                        "policy_revision": profile.policy_revision,
                    },
                    "positions": [
                        {
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
                            "quantity": _decimal(item.quantity),
                            "manual_value": _decimal(item.manual_value),
                            "cost": _decimal(item.cost),
                            "as_of": item.as_of.isoformat(),
                        }
                        for item in portfolio.positions
                    ],
                    "watchlists": watchlists,
                    "policies": [
                        {
                            "rule_type": item.rule_type,
                            "subject_key": item.subject_key,
                            "subject_label": item.subject_label,
                            "threshold": str(item.threshold),
                            "tolerance": _decimal(item.tolerance),
                            "warning_ratio": str(item.warning_ratio),
                            "enabled": item.enabled,
                        }
                        for item in policies
                    ],
                    "scenarios": scenarios,
                },
            )
