"""Tests for integration adapters, service, and API endpoints."""

import json
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.integrations.base import (
    ConnectionTestResult,
    ExternalRequest,
    SyncResult,
    SyncStatus,
)
from src.integrations.email_adapter import EmailAdapter
from src.integrations.jira_adapter import JiraAdapter
from src.integrations.redmine_adapter import RedmineAdapter


# ── Adapter construction helpers ─────────────────────────


def _redmine_config(**overrides):
    base = {
        "base_url": "https://redmine.example.com",
        "api_key": "test-key-123",
        "username": "",
        "additional_config": {"project_id": "myproject", "timeout": 5},
    }
    base.update(overrides)
    return base


def _jira_config(**overrides):
    base = {
        "base_url": "https://jira.example.com",
        "api_key": "test-token",
        "username": "user@example.com",
        "additional_config": {
            "jql_filter": "project = TEST",
            "project_key": "TEST",
            "is_cloud": True,
            "timeout": 5,
        },
    }
    base.update(overrides)
    return base


def _email_config(**overrides):
    base = {
        "base_url": "",
        "api_key": "smtp-password",
        "username": "noreply@example.com",
        "additional_config": {
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_use_tls": True,
            "sender_email": "noreply@example.com",
            "sender_name": "Test Tool",
        },
    }
    base.update(overrides)
    return base


# ── RedmineAdapter tests ────────────────────────────────


class TestRedmineAdapter:
    def test_system_name(self):
        adapter = RedmineAdapter(_redmine_config())
        assert adapter.system_name == "REDMINE"

    def test_headers(self):
        adapter = RedmineAdapter(_redmine_config())
        headers = adapter._headers()
        assert headers["X-Redmine-API-Key"] == "test-key-123"
        assert headers["Content-Type"] == "application/json"

    def test_url_construction(self):
        adapter = RedmineAdapter(_redmine_config())
        assert adapter._url("/issues.json") == "https://redmine.example.com/issues.json"

    def test_test_connection_no_url(self):
        adapter = RedmineAdapter(_redmine_config(base_url=""))
        result = adapter.test_connection()
        assert result.success is False
        assert "not configured" in result.message

    def test_test_connection_no_key(self):
        adapter = RedmineAdapter(_redmine_config(api_key=""))
        result = adapter.test_connection()
        assert result.success is False

    @patch("src.integrations.redmine_adapter.http_requests.get")
    def test_test_connection_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "user": {"id": 1, "login": "admin", "firstname": "John", "lastname": "Doe"}
        }
        mock_get.return_value = mock_resp

        adapter = RedmineAdapter(_redmine_config())
        result = adapter.test_connection()
        assert result.success is True
        assert "John Doe" in result.message

    @patch("src.integrations.redmine_adapter.http_requests.get")
    def test_test_connection_failure(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        mock_get.return_value = mock_resp

        adapter = RedmineAdapter(_redmine_config())
        result = adapter.test_connection()
        assert result.success is False
        assert "401" in result.message

    def test_import_no_project_id(self):
        config = _redmine_config()
        config["additional_config"]["project_id"] = ""
        adapter = RedmineAdapter(config)
        result = adapter.import_requests()
        assert result.status == SyncStatus.FAILED

    @patch("src.integrations.redmine_adapter.http_requests.get")
    def test_import_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "issues": [
                {
                    "id": 101,
                    "subject": "Test Issue",
                    "description": "A test",
                    "author": {"name": "Alice"},
                    "priority": {"name": "High"},
                    "due_date": "2026-03-15",
                }
            ]
        }
        mock_get.return_value = mock_resp

        adapter = RedmineAdapter(_redmine_config())
        result = adapter.import_requests()
        assert result.status == SyncStatus.SUCCESS
        assert result.items_processed == 1
        assert result.items_created == 1

    def test_export_no_external_id(self):
        adapter = RedmineAdapter(_redmine_config())
        result = adapter.export_estimation({"grand_total_hours": 100})
        assert result.status == SyncStatus.SKIPPED

    @patch("src.integrations.redmine_adapter.http_requests.put")
    def test_export_success(self, mock_put):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_put.return_value = mock_resp

        adapter = RedmineAdapter(_redmine_config())
        result = adapter.export_estimation({
            "external_id": "101",
            "grand_total_hours": 100,
            "feasibility_status": "FEASIBLE",
            "estimation_number": "EST-2026-001",
        })
        assert result.status == SyncStatus.SUCCESS
        assert result.items_updated == 1


# ── JiraAdapter tests ───────────────────────────────────


class TestJiraAdapter:
    def test_system_name(self):
        adapter = JiraAdapter(_jira_config())
        assert adapter.system_name == "JIRA"

    def test_cloud_auth_header(self):
        adapter = JiraAdapter(_jira_config())
        headers = adapter._headers()
        assert "Basic" in headers["Authorization"]

    def test_server_bearer_auth(self):
        config = _jira_config(username="")
        config["additional_config"]["is_cloud"] = False
        adapter = JiraAdapter(config)
        headers = adapter._headers()
        assert "Bearer" in headers["Authorization"]

    def test_url_construction(self):
        adapter = JiraAdapter(_jira_config())
        url = adapter._url("search")
        assert url == "https://jira.example.com/rest/api/2/search"

    def test_test_connection_no_url(self):
        adapter = JiraAdapter(_jira_config(base_url=""))
        result = adapter.test_connection()
        assert result.success is False

    @patch("src.integrations.jira_adapter.http_requests.get")
    def test_test_connection_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"displayName": "John", "accountId": "abc"}
        mock_get.return_value = mock_resp

        adapter = JiraAdapter(_jira_config())
        result = adapter.test_connection()
        assert result.success is True
        assert "John" in result.message

    def test_import_no_jql(self):
        config = _jira_config()
        config["additional_config"]["jql_filter"] = ""
        adapter = JiraAdapter(config)
        result = adapter.import_requests()
        assert result.status == SyncStatus.FAILED
        assert "JQL" in result.errors[0]

    @patch("src.integrations.jira_adapter.http_requests.get")
    def test_import_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "issues": [
                {
                    "key": "TEST-1",
                    "fields": {
                        "summary": "Jira Issue",
                        "description": "A test",
                        "reporter": {"displayName": "Bob", "emailAddress": "bob@test.com"},
                        "priority": {"name": "High"},
                        "duedate": "2026-04-01",
                        "status": {"name": "Open"},
                        "issuetype": {"name": "Task"},
                    },
                }
            ]
        }
        mock_get.return_value = mock_resp

        adapter = JiraAdapter(_jira_config())
        result = adapter.import_requests()
        assert result.status == SyncStatus.SUCCESS
        assert result.items_created == 1

    def test_export_no_external_id(self):
        adapter = JiraAdapter(_jira_config())
        result = adapter.export_estimation({})
        assert result.status == SyncStatus.SKIPPED

    @patch("src.integrations.jira_adapter.http_requests.post")
    @patch("src.integrations.jira_adapter.http_requests.put")
    def test_export_with_field_mappings(self, mock_put, mock_post):
        mock_put.return_value = MagicMock(status_code=204)
        mock_post.return_value = MagicMock(status_code=201)

        config = _jira_config()
        config["additional_config"]["field_mappings"] = {
            "effort_hours": "customfield_10001",
        }
        adapter = JiraAdapter(config)
        result = adapter.export_estimation({
            "external_id": "TEST-1",
            "grand_total_hours": 120,
            "feasibility_status": "FEASIBLE",
            "estimation_number": "EST-001",
        })
        assert result.status == SyncStatus.SUCCESS

    def test_xray_disabled(self):
        adapter = JiraAdapter(_jira_config())
        result = adapter.create_xray_test_plan({})
        assert result.status == SyncStatus.SKIPPED


# ── EmailAdapter tests ──────────────────────────────────


class TestEmailAdapter:
    def test_system_name(self):
        adapter = EmailAdapter(_email_config())
        assert adapter.system_name == "EMAIL"

    def test_test_connection_no_host(self):
        config = _email_config()
        config["additional_config"]["smtp_host"] = ""
        adapter = EmailAdapter(config)
        result = adapter.test_connection()
        assert result.success is False
        assert "not configured" in result.message

    def test_import_not_implemented(self):
        adapter = EmailAdapter(_email_config())
        result = adapter.import_requests()
        assert result.status == SyncStatus.SKIPPED
        assert "not yet implemented" in result.errors[0].lower()

    def test_export_no_email(self):
        adapter = EmailAdapter(_email_config())
        result = adapter.export_estimation({"grand_total_hours": 100})
        assert result.status == SyncStatus.SKIPPED

    def test_send_report_no_host(self):
        config = _email_config()
        config["additional_config"]["smtp_host"] = ""
        adapter = EmailAdapter(config)
        result = adapter.send_report("to@test.com", "Subject", "<p>Body</p>")
        assert result.status == SyncStatus.FAILED


# ── Integration service tests ───────────────────────────


class TestIntegrationService:
    @patch("src.integrations.service.Session")
    def test_get_adapter_returns_none_when_disabled(self, mock_session_cls):
        from src.integrations.service import get_adapter

        mock_session = MagicMock()
        mock_config = MagicMock()
        mock_config.enabled = False
        mock_session.query.return_value.filter.return_value.first.return_value = mock_config

        result = get_adapter("REDMINE", mock_session)
        assert result is None

    @patch("src.integrations.service.Session")
    def test_get_adapter_returns_none_for_unknown(self, mock_session_cls):
        from src.integrations.service import get_adapter

        mock_session = MagicMock()
        mock_config = MagicMock()
        mock_config.enabled = True
        mock_session.query.return_value.filter.return_value.first.return_value = mock_config

        result = get_adapter("UNKNOWN_SYSTEM", mock_session)
        assert result is None

    @patch("src.integrations.service.Session")
    def test_test_integration_not_configured(self, mock_session_cls):
        from src.integrations.service import test_integration

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = test_integration("REDMINE", mock_session)
        assert result.success is False
        assert "not configured" in result.message

    @patch("src.integrations.service.Session")
    def test_get_integration_status(self, mock_session_cls):
        from src.integrations.service import get_integration_status

        mock_session = MagicMock()
        mock_cfg = MagicMock()
        mock_cfg.system_name = "REDMINE"
        mock_cfg.enabled = True
        mock_cfg.base_url = "https://redmine.example.com"
        mock_cfg.last_sync_at = None
        mock_cfg.api_key = "key"
        mock_session.query.return_value.all.return_value = [mock_cfg]

        statuses = get_integration_status(mock_session)
        assert len(statuses) == 1
        assert statuses[0]["system_name"] == "REDMINE"
        assert statuses[0]["has_api_key"] is True


# ── Integration API endpoint tests ──────────────────────


class TestIntegrationAPI:
    """Test integration API endpoints using the FastAPI test client."""

    @pytest.fixture
    def client(self, tmp_path):
        """Create a test client with a fresh database."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from fastapi.testclient import TestClient

        from src.api.app import app, get_db
        from src.database.migrations import init_database

        db_path = str(tmp_path / "test.db")
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
        client = TestClient(app)
        yield client
        app.dependency_overrides.clear()

    def _create_integration_config(self, client, system_name="REDMINE"):
        """Helper to create an integration config."""
        return client.put(
            f"/api/integrations/{system_name}",
            json={
                "base_url": "https://redmine.example.com",
                "api_key": "test-key",
                "enabled": True,
            },
        )

    def test_list_integrations_empty(self, client):
        resp = client.get("/api/integrations")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_and_get_integration(self, client):
        # Create via PUT (upsert)
        resp = self._create_integration_config(client)
        assert resp.status_code == 200
        data = resp.json()
        assert data["system_name"] == "REDMINE"
        assert data["enabled"] is True
        assert data["has_api_key"] is True

        # Get
        resp2 = client.get("/api/integrations/REDMINE")
        assert resp2.status_code == 200
        assert resp2.json()["system_name"] == "REDMINE"

    def test_get_integration_not_found(self, client):
        resp = client.get("/api/integrations/NONEXISTENT")
        assert resp.status_code == 404

    def test_update_integration(self, client):
        self._create_integration_config(client)
        resp = client.put(
            "/api/integrations/REDMINE",
            json={"enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_list_integrations_after_create(self, client):
        self._create_integration_config(client, "REDMINE")
        self._create_integration_config(client, "JIRA")
        resp = client.get("/api/integrations")
        assert resp.status_code == 200
        names = [i["system_name"] for i in resp.json()]
        assert "REDMINE" in names
        assert "JIRA" in names

    def test_integration_status(self, client):
        self._create_integration_config(client)
        resp = client.get("/api/integrations/REDMINE/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["system_name"] == "REDMINE"
        assert data["enabled"] is True
        assert data["configured"] is True

    def test_integration_status_not_found(self, client):
        resp = client.get("/api/integrations/NONEXISTENT/status")
        assert resp.status_code == 404

    def test_test_integration_not_configured(self, client):
        """Test connection for an unconfigured integration should fail gracefully."""
        resp = client.post("/api/integrations/REDMINE/test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False

    def test_sync_not_configured(self, client):
        """Sync for an unconfigured integration should fail gracefully."""
        resp = client.post("/api/integrations/REDMINE/sync")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "FAILED"
