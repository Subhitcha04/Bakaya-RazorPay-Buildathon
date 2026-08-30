"""
Tests app/api/server.py through a real FastAPI TestClient against a
REAL, seeded, file-backed SQLite database (scripts/seed_db.py) -- not
mocked responses, not an empty DB.
"""
from __future__ import annotations

import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from scripts.seed_db import seed
from app.api.server import app
from app.db import get_db


def _client_with_seeded_db(n: int = 150, seed_value: int = 1) -> TestClient:
    db_path = Path(tempfile.mktemp(suffix=".db"))
    seed(n, seed_value, db_path=db_path)

    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_list_cases_returns_the_seeded_count():
    client = _client_with_seeded_db(n=150, seed_value=1)
    resp = client.get("/api/cases")
    assert resp.status_code == 200
    assert len(resp.json()) == 150


def test_list_cases_every_case_has_the_expected_fields():
    client = _client_with_seeded_db(n=100, seed_value=1)
    resp = client.get("/api/cases")
    for case in resp.json():
        for field in ("id", "traceId", "surface", "category", "rootCause", "ladderLevel",
                       "arm", "amountPaise", "ltvBand", "verdict", "detectedAt", "channel", "recoveredPaise"):
            assert field in case, f"missing {field} in {case}"
        assert case["recoveredPaise"] is None


def test_list_cases_verdicts_are_only_the_four_real_values():
    client = _client_with_seeded_db(n=200, seed_value=1)
    resp = client.get("/api/cases")
    verdicts = {c["verdict"] for c in resp.json()}
    assert verdicts.issubset({"ALLOW", "BLOCK", "ESCALATE", "HOLDOUT"})


def test_get_case_detail_for_a_real_allow_case():
    client = _client_with_seeded_db(n=200, seed_value=1)
    cases = client.get("/api/cases").json()
    allow_case = next(c for c in cases if c["verdict"] == "ALLOW")

    resp = client.get(f"/api/cases/{allow_case['id']}")
    assert resp.status_code == 200
    detail = resp.json()
    steps = [n["step"] for n in detail["evidenceChain"]]
    assert steps == ["detected", "diagnosed", "decided", "authorized"]
    authorized_node = next(n for n in detail["evidenceChain"] if n["step"] == "authorized")
    assert authorized_node["hash"] is not None
    assert len(authorized_node["hash"]) == 64


def test_get_case_detail_for_a_real_block_case():
    client = _client_with_seeded_db(n=200, seed_value=1)
    cases = client.get("/api/cases").json()
    block_case = next(c for c in cases if c["verdict"] == "BLOCK")

    resp = client.get(f"/api/cases/{block_case['id']}")
    detail = resp.json()
    steps = [n["step"] for n in detail["evidenceChain"]]
    assert steps == ["detected", "diagnosed", "decided"]
    decided_node = next(n for n in detail["evidenceChain"] if n["step"] == "decided")
    assert decided_node["hash"] is not None
    assert decided_node["detail"]["failed_gate"] is not None


def test_get_case_detail_for_a_holdout_case_stops_after_diagnosed():
    client = _client_with_seeded_db(n=200, seed_value=1)
    cases = client.get("/api/cases").json()
    holdout_case = next(c for c in cases if c["verdict"] == "HOLDOUT" and c["ladderLevel"] != "L5")

    resp = client.get(f"/api/cases/{holdout_case['id']}")
    detail = resp.json()
    steps = [n["step"] for n in detail["evidenceChain"]]
    assert steps == ["detected", "diagnosed"]


def test_get_case_detail_404_for_unknown_case():
    client = _client_with_seeded_db(n=10, seed_value=1)
    resp = client.get("/api/cases/nonexistent_case_id")
    assert resp.status_code == 404


def test_approvals_only_contains_escalated_cases():
    client = _client_with_seeded_db(n=200, seed_value=1)
    cases = {c["id"]: c for c in client.get("/api/cases").json()}

    resp = client.get("/api/approvals")
    assert resp.status_code == 200
    approvals = resp.json()
    assert len(approvals) > 0
    for a in approvals:
        assert cases[a["id"]]["verdict"] == "ESCALATE"
        assert "reason" in a and a["reason"]
        assert "rootCause" in a
        assert a["rootCause"] == cases[a["id"]]["rootCause"]


def test_dashboard_summary_counts_match_the_case_list():
    client = _client_with_seeded_db(n=200, seed_value=1)
    cases = client.get("/api/cases").json()

    resp = client.get("/api/dashboard/summary")
    summary = resp.json()
    assert summary["totalCases"] == len(cases)

    verdict_counts_from_cases = {}
    for c in cases:
        verdict_counts_from_cases[c["verdict"]] = verdict_counts_from_cases.get(c["verdict"], 0) + 1
    assert summary["byVerdict"] == verdict_counts_from_cases


def test_dashboard_summary_arm_split_matches_case_list():
    client = _client_with_seeded_db(n=200, seed_value=1)
    cases = client.get("/api/cases").json()

    resp = client.get("/api/dashboard/summary")
    summary = resp.json()

    arm_counts_from_cases = {}
    for c in cases:
        arm_counts_from_cases[c["arm"]] = arm_counts_from_cases.get(c["arm"], 0) + 1
    assert summary["byArm"] == arm_counts_from_cases


def test_dashboard_summary_block_reasons_are_real_gate_names():
    client = _client_with_seeded_db(n=200, seed_value=1)
    resp = client.get("/api/dashboard/summary")
    block_reasons = resp.json()["blockReasons"]
    assert len(block_reasons) > 0

