"""Integration tests for FastAPI endpoints."""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.database.migrations import init_database, get_engine
from src.database.models import Base


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Use a temporary database for API tests."""
    db_path = tmp_path / "test_api.db"
    init_database(db_path)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    TestSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    from src.api.app import app, get_db
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    from src.api.app import app
    return TestClient(app)


def _get_auth_headers(client: TestClient) -> dict:
    """Log in as the default admin and return Bearer auth headers."""
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers(client):
    return _get_auth_headers(client)


class TestFeatureEndpoints:
    def test_list_features(self, client, auth_headers):
        resp = client.get("/api/features", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 5  # Seed data

    def test_create_feature(self, client, auth_headers):
        resp = client.post("/api/features", headers=auth_headers, json={
            "name": "API Test Feature",
            "category": "Test",
            "complexity_weight": 1.5,
            "has_existing_tests": False,
        })
        assert resp.status_code == 201
        assert resp.json()["name"] == "API Test Feature"

    def test_get_feature(self, client, auth_headers):
        resp = client.get("/api/features/1", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == 1

    def test_update_feature(self, client, auth_headers):
        resp = client.put("/api/features/1", headers=auth_headers, json={"complexity_weight": 2.0})
        assert resp.status_code == 200
        assert resp.json()["complexity_weight"] == 2.0

    def test_delete_feature(self, client, auth_headers):
        # Create then delete
        create_resp = client.post("/api/features", headers=auth_headers, json={
            "name": "To Delete",
            "category": "Test",
        })
        fid = create_resp.json()["id"]
        resp = client.delete(f"/api/features/{fid}", headers=auth_headers)
        assert resp.status_code == 204

    def test_feature_not_found(self, client, auth_headers):
        resp = client.get("/api/features/9999", headers=auth_headers)
        assert resp.status_code == 404


class TestDutTypeEndpoints:
    def test_list_dut_types(self, client, auth_headers):
        resp = client.get("/api/dut-types", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 3

    def test_create_dut_type(self, client, auth_headers):
        resp = client.post("/api/dut-types", headers=auth_headers, json={
            "name": "Test DUT",
            "category": "Test",
            "complexity_multiplier": 1.3,
        })
        assert resp.status_code == 201


class TestProfileEndpoints:
    def test_list_profiles(self, client, auth_headers):
        resp = client.get("/api/profiles", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 3


class TestRequestEndpoints:
    def test_create_request(self, client, auth_headers):
        resp = client.post("/api/requests", headers=auth_headers, json={
            "request_number": "REQ_26/0001",
            "title": "Test Request",
            "requester_name": "John Doe",
            "received_date": "2026-02-26",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "NEW"
        assert data["request_number"] == "REQ_26/0001"

    def test_list_requests(self, client, auth_headers):
        client.post("/api/requests", headers=auth_headers, json={
            "request_number": "REQ_26/0002",
            "title": "Test",
            "requester_name": "Jane",
            "received_date": "2026-02-26",
        })
        resp = client.get("/api/requests", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestConfigurationEndpoints:
    def test_list_config(self, client, auth_headers):
        resp = client.get("/api/configuration", headers=auth_headers)
        assert resp.status_code == 200
        keys = [c["key"] for c in resp.json()]
        assert "leader_effort_ratio" in keys

    def test_update_config(self, client, auth_headers):
        resp = client.put("/api/configuration/leader_effort_ratio", headers=auth_headers, json={"value": "0.6"})
        assert resp.status_code == 200
        assert resp.json()["value"] == "0.6"


class TestTeamMemberEndpoints:
    def test_create_and_list(self, client, auth_headers):
        client.post("/api/team-members", headers=auth_headers, json={
            "name": "Alice",
            "role": "TESTER",
            "available_hours_per_day": 7.0,
        })
        resp = client.get("/api/team-members", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestEstimationEndpoints:
    def test_create_estimation(self, client, auth_headers):
        # Get feature IDs from seed data
        features_resp = client.get("/api/features", headers=auth_headers)
        feature_ids = [f["id"] for f in features_resp.json()[:3]]

        resp = client.post("/api/estimations", headers=auth_headers, json={
            "project_name": "API Test Project",
            "project_type": "EVOLUTION",
            "feature_ids": feature_ids,
            "new_feature_ids": [],
            "dut_ids": [1, 2],
            "profile_ids": [1],
            "pr_fixes": {"simple": 1, "medium": 1, "complex": 0},
            "team_size": 2,
            "has_leader": True,
            "working_days": 20,
            "expected_delivery": "2026-04-01",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["project_name"] == "API Test Project"
        assert data["feasibility_status"] in ("FEASIBLE", "AT_RISK", "NOT_FEASIBLE")
        assert data["grand_total_hours"] > 0
        assert len(data["tasks"]) > 0
        assert data["estimation_number"].startswith("EST")

    def test_list_estimations(self, client, auth_headers):
        resp = client.get("/api/estimations", headers=auth_headers)
        assert resp.status_code == 200


class TestReportEndpoints:
    def _create_estimation(self, client, auth_headers) -> int:
        features_resp = client.get("/api/features", headers=auth_headers)
        feature_ids = [f["id"] for f in features_resp.json()[:2]]
        resp = client.post("/api/estimations", headers=auth_headers, json={
            "project_name": "Report Test",
            "project_type": "NEW",
            "feature_ids": feature_ids,
            "dut_ids": [1],
            "profile_ids": [1],
            "team_size": 2,
            "has_leader": False,
            "working_days": 15,
        })
        return resp.json()["id"]

    def test_xlsx_report(self, client, auth_headers):
        est_id = self._create_estimation(client, auth_headers)
        resp = client.get(f"/api/estimations/{est_id}/report/xlsx", headers=auth_headers)
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers["content-type"]
        assert len(resp.content) > 0

    def test_docx_report(self, client, auth_headers):
        est_id = self._create_estimation(client, auth_headers)
        resp = client.get(f"/api/estimations/{est_id}/report/docx", headers=auth_headers)
        assert resp.status_code == 200
        assert "wordprocessingml" in resp.headers["content-type"]
        assert len(resp.content) > 0

    def test_pdf_report(self, client, auth_headers):
        est_id = self._create_estimation(client, auth_headers)
        resp = client.get(f"/api/estimations/{est_id}/report/pdf", headers=auth_headers)
        assert resp.status_code == 200
        assert "pdf" in resp.headers["content-type"]
        assert resp.content[:4] == b"%PDF"
