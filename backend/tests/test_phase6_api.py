"""Tests for Phase 6 API endpoints: estimation CRUD, status workflow,
attachments, calibration, and dashboard stats."""

import json
from datetime import date, datetime
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.app import app, get_db
from src.database.migrations import init_database


@pytest.fixture
def client(tmp_path):
    """Create a test client with a fresh database."""
    db_path = str(tmp_path / "test_phase6.db")
    init_database(db_path)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    SessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _create_estimation(client) -> dict:
    """Helper to create a minimal estimation for testing."""
    resp = client.post("/api/estimations", json={
        "project_name": "Test Project",
        "project_type": "NEW",
        "feature_ids": [],
        "team_size": 2,
        "has_leader": True,
        "working_days": 20,
        "pr_fixes": {"simple": 2, "medium": 1, "complex": 0},
    })
    assert resp.status_code == 201
    return resp.json()


def _create_request(client) -> dict:
    """Helper to create a request."""
    resp = client.post("/api/requests", json={
        "title": "Test Request",
        "requester_name": "John Doe",
        "requester_email": "john@example.com",
        "business_unit": "Testing",
        "priority": "HIGH",
        "received_date": "2026-02-27",
    })
    assert resp.status_code == 201
    return resp.json()


# ── Estimation Update (PUT) ──────────────────────────────


class TestEstimationUpdate:
    def test_update_project_name(self, client):
        est = _create_estimation(client)
        resp = client.put(f"/api/estimations/{est['id']}", json={
            "project_name": "Updated Project",
        })
        assert resp.status_code == 200
        assert resp.json()["project_name"] == "Updated Project"

    def test_update_expected_delivery(self, client):
        est = _create_estimation(client)
        resp = client.put(f"/api/estimations/{est['id']}", json={
            "expected_delivery": "2026-06-01",
        })
        assert resp.status_code == 200
        assert resp.json()["expected_delivery"] == "2026-06-01"

    def test_update_not_found(self, client):
        resp = client.put("/api/estimations/9999", json={"project_name": "X"})
        assert resp.status_code == 404

    def test_partial_update(self, client):
        est = _create_estimation(client)
        original_type = est["project_type"]
        resp = client.put(f"/api/estimations/{est['id']}", json={
            "project_name": "Only Name Changed",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_name"] == "Only Name Changed"
        assert data["project_type"] == original_type


# ── Estimation Delete ────────────────────────────────────


class TestEstimationDelete:
    def test_delete_estimation(self, client):
        est = _create_estimation(client)
        resp = client.delete(f"/api/estimations/{est['id']}")
        assert resp.status_code == 204

        # Verify it's gone
        resp2 = client.get(f"/api/estimations/{est['id']}")
        assert resp2.status_code == 404

    def test_delete_not_found(self, client):
        resp = client.delete("/api/estimations/9999")
        assert resp.status_code == 404


# ── Estimation Status Workflow ───────────────────────────


class TestEstimationStatusWorkflow:
    def test_draft_to_final(self, client):
        est = _create_estimation(client)
        assert est["status"] == "DRAFT"

        resp = client.post(f"/api/estimations/{est['id']}/status", json={
            "status": "FINAL",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "FINAL"

    def test_final_to_approved(self, client):
        est = _create_estimation(client)
        client.post(f"/api/estimations/{est['id']}/status", json={"status": "FINAL"})

        resp = client.post(f"/api/estimations/{est['id']}/status", json={
            "status": "APPROVED",
            "approved_by": "Manager Smith",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "APPROVED"
        assert data["approved_by"] == "Manager Smith"
        assert data["approved_at"] is not None

    def test_approved_to_revised(self, client):
        est = _create_estimation(client)
        client.post(f"/api/estimations/{est['id']}/status", json={"status": "FINAL"})
        client.post(f"/api/estimations/{est['id']}/status", json={
            "status": "APPROVED", "approved_by": "Boss",
        })

        resp = client.post(f"/api/estimations/{est['id']}/status", json={
            "status": "REVISED",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "REVISED"
        # Approval should be cleared on revision
        assert data["approved_by"] is None
        assert data["approved_at"] is None

    def test_invalid_transition(self, client):
        est = _create_estimation(client)
        # DRAFT -> APPROVED (skipping FINAL) should fail
        resp = client.post(f"/api/estimations/{est['id']}/status", json={
            "status": "APPROVED",
        })
        assert resp.status_code == 400
        assert "Invalid status transition" in resp.json()["detail"]

    def test_status_not_found(self, client):
        resp = client.post("/api/estimations/9999/status", json={"status": "FINAL"})
        assert resp.status_code == 404


# ── Request Detail with Estimations ──────────────────────


class TestRequestDetail:
    def test_request_detail_with_estimations(self, client):
        req = _create_request(client)
        # Create estimation linked to request
        client.post("/api/estimations", json={
            "request_id": req["id"],
            "project_name": "Linked Project",
            "project_type": "EVOLUTION",
            "feature_ids": [],
            "team_size": 1,
            "has_leader": False,
            "working_days": 10,
            "pr_fixes": {"simple": 0, "medium": 0, "complex": 0},
        })

        resp = client.get(f"/api/requests/{req['id']}/detail")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test Request"
        assert len(data["estimations"]) == 1
        assert data["estimations"][0]["project_name"] == "Linked Project"

    def test_request_detail_no_estimations(self, client):
        req = _create_request(client)
        resp = client.get(f"/api/requests/{req['id']}/detail")
        assert resp.status_code == 200
        assert len(resp.json()["estimations"]) == 0

    def test_request_detail_not_found(self, client):
        resp = client.get("/api/requests/9999/detail")
        assert resp.status_code == 404


# ── Attachment Upload ────────────────────────────────────


class TestAttachmentUpload:
    def test_upload_file(self, client, tmp_path):
        req = _create_request(client)
        file_content = b"Hello, this is a test file."
        resp = client.post(
            f"/api/requests/{req['id']}/attachments",
            files={"file": ("test.txt", BytesIO(file_content), "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "test.txt"
        assert data["size"] == len(file_content)

        # Verify attachments_json updated
        req_resp = client.get(f"/api/requests/{req['id']}")
        attachments = json.loads(req_resp.json()["attachments_json"])
        assert len(attachments) == 1
        assert attachments[0]["filename"] == "test.txt"

    def test_upload_to_nonexistent_request(self, client):
        resp = client.post(
            "/api/requests/9999/attachments",
            files={"file": ("test.txt", BytesIO(b"data"), "text/plain")},
        )
        assert resp.status_code == 404


# ── Calibration ─────────────────────────────────────────


class TestCalibration:
    def _create_historical_project(self, client, est_hours=100, act_hours=120):
        resp = client.post("/api/historical-projects", json={
            "project_name": "Past Project",
            "project_type": "EVOLUTION",
            "estimated_hours": est_hours,
            "actual_hours": act_hours,
            "dut_count": 2,
            "profile_count": 2,
        })
        return resp.json()

    def test_calibrate_with_reference(self, client):
        hist = self._create_historical_project(client, 100, 120)
        est = client.post("/api/estimations", json={
            "project_name": "Calibrated Project",
            "project_type": "EVOLUTION",
            "feature_ids": [],
            "reference_project_ids": [hist["id"]],
            "team_size": 2,
            "has_leader": True,
            "working_days": 20,
            "pr_fixes": {"simple": 5, "medium": 2, "complex": 1},
        }).json()

        resp = client.post(f"/api/estimations/{est['id']}/calibrate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["accuracy_ratio"] == 1.2  # 120/100
        assert data["adjusted_grand_total"] > 0
        assert len(data["reference_projects"]) == 1

    def test_calibrate_no_references(self, client):
        est = _create_estimation(client)
        resp = client.post(f"/api/estimations/{est['id']}/calibrate")
        assert resp.status_code == 400

    def test_calibrate_not_found(self, client):
        resp = client.post("/api/estimations/9999/calibrate")
        assert resp.status_code == 404


# ── Dashboard Stats ─────────────────────────────────────


class TestDashboardStats:
    def test_empty_dashboard(self, client):
        resp = client.get("/api/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_requests"] == 0
        assert data["total_estimations"] == 0

    def test_dashboard_with_data(self, client):
        _create_request(client)
        _create_request(client)
        _create_estimation(client)

        resp = client.get("/api/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_requests"] == 2
        assert data["requests_new"] == 2
        assert data["total_estimations"] == 1
        assert data["estimations_draft"] == 1
        assert data["avg_grand_total_hours"] >= 0

    def test_dashboard_request_counts(self, client):
        # Create requests with different statuses
        req1 = _create_request(client)
        req2 = _create_request(client)
        # Update one to completed
        client.put(f"/api/requests/{req2['id']}", json={"status": "COMPLETED"})

        resp = client.get("/api/dashboard/stats")
        data = resp.json()
        assert data["total_requests"] == 2
        assert data["requests_new"] == 1
        assert data["requests_completed"] == 1
