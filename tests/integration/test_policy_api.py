from pathlib import Path

import httpx2
import pytest
from sqlalchemy import func, select

from tests.integration.test_risk_api import build_risk_app, positions_payload
from tickeye.infrastructure.db import (
    InsightEventRecord,
    RiskEvaluationRecord,
    RiskSnapshotRecord,
)

pytestmark = pytest.mark.anyio


async def test_policy_transitions_create_deduplicated_immutable_events(
    tmp_path: Path,
) -> None:
    app = build_risk_app(tmp_path)
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.put(
            "/api/v1/portfolio/positions", json=positions_payload()
        )
        instrument_id = next(
            item["instrument_id"]
            for item in created.json()["data"]["positions"]
            if item["code"] == "510300"
        )
        await client.post(
            "/api/v1/market-data/refresh", json={"instrument_ids": None}
        )
        initial = await client.post("/api/v1/risk/recalculate")
        empty_policies = await client.get("/api/v1/policies")
        breached_policy = await client.put(
            "/api/v1/policies",
            json={
                "expected_revision": 0,
                "rules": [
                    {
                        "id": None,
                        "rule_type": "instrument_max_weight",
                        "subject_key": str(instrument_id),
                        "threshold": "0.01",
                        "tolerance": None,
                        "warning_ratio": "0.20",
                        "enabled": True,
                    }
                ],
            },
        )
        current_breached = await client.get("/api/v1/risk/current")
        await client.post("/api/v1/risk/recalculate")
        events_after_repeat = await client.get("/api/v1/events")
        rule = breached_policy.json()["data"]["rules"][0]
        recovered_policy = await client.put(
            "/api/v1/policies",
            json={
                "expected_revision": 1,
                "rules": [
                    {
                        **rule,
                        "threshold": "0.50",
                    }
                ],
            },
        )
        current_recovered = await client.get("/api/v1/risk/current")
        final_events = await client.get("/api/v1/events")
        conflict = await client.put(
            "/api/v1/policies",
            json={"expected_revision": 1, "rules": []},
        )

    assert initial.json()["data"]["evaluation"]["state"] == "unknown"
    assert empty_policies.json()["data"] == {"revision": 0, "rules": []}
    assert breached_policy.status_code == 200
    assert breached_policy.json()["data"]["revision"] == 1
    assert current_breached.json()["data"]["evaluation"]["state"] == "breached"
    repeated_policy_events = [
        item
        for item in events_after_repeat.json()["data"]["items"]
        if item["finding_key"].startswith("policy:")
    ]
    assert len(repeated_policy_events) == 1
    assert recovered_policy.json()["data"]["revision"] == 2
    assert current_recovered.json()["data"]["evaluation"]["state"] == "within"
    policy_events = [
        item
        for item in final_events.json()["data"]["items"]
        if item["finding_key"].startswith("policy:")
    ]
    assert [item["event_type"] for item in policy_events] == ["recovered", "detected"]
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "policy_revision_conflict"

    with app.state.session_factory() as session:
        snapshots = session.scalar(select(func.count(RiskSnapshotRecord.id)))
        evaluations = session.scalar(select(func.count(RiskEvaluationRecord.id)))
        events = session.scalar(select(func.count(InsightEventRecord.id)))
    app.state.engine.dispose()
    assert snapshots == 4
    assert evaluations == 4
    assert events == 3


async def test_invalid_policy_does_not_create_snapshot(tmp_path: Path) -> None:
    app = build_risk_app(tmp_path)
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(
            "/api/v1/policies",
            json={
                "expected_revision": 0,
                "rules": [
                    {
                        "rule_type": "asset_class_target_weight",
                        "subject_key": "equity",
                        "threshold": "0.60",
                        "tolerance": None,
                        "warning_ratio": "0.20",
                        "enabled": True,
                    }
                ],
            },
        )

    with app.state.session_factory() as session:
        snapshots = session.scalar(select(func.count(RiskSnapshotRecord.id)))
    app.state.engine.dispose()
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "policy_validation_error"
    assert snapshots == 0
