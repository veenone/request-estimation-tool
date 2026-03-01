"""Jira / Xray integration adapter.

Links estimations to Jira issues and syncs test plans with Xray.
Supports Jira Cloud, Jira Server, and Jira Data Center (DC).

Authentication modes:
  - Cloud: email + API token (Basic Auth)
  - Server/DC: username + password (Basic Auth) OR Personal Access Token (Bearer)
"""

import base64
from typing import Any

import requests as http_requests

from .base import (
    BaseAdapter,
    ConnectionTestResult,
    ExternalRequest,
    SyncResult,
    SyncStatus,
)


class JiraAdapter(BaseAdapter):
    """Jira REST API adapter supporting Cloud, Server, and Data Center."""

    @property
    def system_name(self) -> str:
        return "JIRA"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.jql_filter = self.additional_config.get("jql_filter", "")
        self.issue_type = self.additional_config.get("issue_type", "Task")
        self.project_key = self.additional_config.get("project_key", "")
        self.xray_enabled = self.additional_config.get("xray_enabled", False)
        self.xray_project_key = self.additional_config.get("xray_project_key", "")
        self.is_cloud = self.additional_config.get("is_cloud", False)

        # SSL verification — DC instances often use self-signed certificates
        ssl_val = self.additional_config.get("ssl_verify", True)
        if isinstance(ssl_val, str):
            self.ssl_verify: bool | str = ssl_val.lower() not in ("false", "0", "no")
        else:
            self.ssl_verify = bool(ssl_val)

        self.timeout = int(self.additional_config.get("timeout", 30))

        # Auth mode: "pat" (Personal Access Token), "basic", or auto-detect
        self.auth_mode = self.additional_config.get("auth_mode", "").lower()

        # Field mappings — support both nested dict and flat UI keys
        field_mappings = self.additional_config.get("field_mappings", {})
        if not field_mappings:
            # Map flat UI keys to internal field_mappings dict
            for ui_key, fm_key in [
                ("effort_hours_field", "effort_hours"),
                ("feasibility_field", "feasibility"),
                ("estimation_number_field", "estimation_number"),
            ]:
                val = self.additional_config.get(ui_key)
                if val:
                    val_str = str(val).strip()
                    if val_str.lower() in ("originalestimate", "time_tracking", "0"):
                        field_mappings[fm_key] = "originalEstimate"
                    else:
                        field_mappings[fm_key] = val_str
        self.field_mappings = field_mappings

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.is_cloud:
            # Cloud: email + API token as Basic Auth
            creds = base64.b64encode(f"{self.username}:{self.api_key}".encode()).decode()
            headers["Authorization"] = f"Basic {creds}"
        elif self.auth_mode == "pat" or (self.api_key and not self.username):
            # DC/Server: Personal Access Token (Bearer)
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif self.username and self.api_key:
            # DC/Server: username + password (Basic Auth)
            creds = base64.b64encode(f"{self.username}:{self.api_key}".encode()).decode()
            headers["Authorization"] = f"Basic {creds}"
        return headers

    def _url(self, path: str) -> str:
        base = self.base_url.rstrip("/")
        return f"{base}/rest/api/2/{path.lstrip('/')}"

    def _request(self, method: str, url: str, **kwargs) -> http_requests.Response:
        """Centralised HTTP call with SSL and timeout defaults."""
        kwargs.setdefault("headers", self._headers())
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("verify", self.ssl_verify)
        return http_requests.request(method, url, **kwargs)

    def test_connection(self) -> ConnectionTestResult:
        """Test connection by fetching current user and server info."""
        if not self.base_url or not self.api_key:
            return ConnectionTestResult(False, "Jira URL or API key not configured.")
        try:
            resp = self._request("GET", self._url("myself"))
            if resp.status_code == 200:
                user = resp.json()
                display = user.get("displayName", user.get("name", "Unknown"))

                # Detect deployment type via serverInfo (DC/Server expose this)
                deploy_type = "Cloud" if self.is_cloud else "Server/DC"
                try:
                    info_resp = self._request(
                        "GET",
                        f"{self.base_url.rstrip('/')}/rest/api/2/serverInfo",
                    )
                    if info_resp.status_code == 200:
                        info = info_resp.json()
                        version = info.get("version", "")
                        dt = info.get("deploymentType", "")
                        if dt:
                            deploy_type = dt.replace("_", " ").title()
                        if version:
                            deploy_type += f" v{version}"
                except Exception:
                    pass

                return ConnectionTestResult(
                    True,
                    f"Connected as: {display} ({deploy_type})",
                    details={"account_id": user.get("accountId", user.get("key"))},
                )
            return ConnectionTestResult(False, f"HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            return ConnectionTestResult(False, f"Connection failed: {e}")

    def import_requests(self) -> SyncResult:
        """Import issues from Jira using JQL filter."""
        if not self.jql_filter:
            return SyncResult(
                system=self.system_name,
                direction="IMPORT",
                status=SyncStatus.FAILED,
                errors=["No JQL filter configured."],
            )

        try:
            resp = self._request(
                "GET",
                self._url("search"),
                params={
                    "jql": self.jql_filter,
                    "maxResults": 100,
                    "fields": "summary,description,reporter,priority,duedate,status,issuetype",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            issues = data.get("issues", [])

            imported: list[ExternalRequest] = []
            errors: list[str] = []

            for issue in issues:
                try:
                    fields = issue.get("fields", {})
                    priority_map = {
                        "Lowest": "LOW",
                        "Low": "LOW",
                        "Medium": "MEDIUM",
                        "High": "HIGH",
                        "Highest": "CRITICAL",
                    }
                    priority_name = (fields.get("priority") or {}).get("name", "Medium")
                    reporter = fields.get("reporter") or {}

                    ext_req = ExternalRequest(
                        external_id=issue["key"],
                        title=fields.get("summary", ""),
                        description=fields.get("description", "") or "",
                        requester_name=reporter.get("displayName", reporter.get("name", "")),
                        requester_email=reporter.get("emailAddress", ""),
                        priority=priority_map.get(priority_name, "MEDIUM"),
                        requested_delivery_date=fields.get("duedate"),
                        raw_data=issue,
                    )
                    imported.append(ext_req)
                except Exception as e:
                    errors.append(f"Issue {issue.get('key', '?')}: {e}")

            return SyncResult(
                system=self.system_name,
                direction="IMPORT",
                status=SyncStatus.SUCCESS if not errors else SyncStatus.PARTIAL,
                items_processed=len(issues),
                items_created=len(imported),
                items_failed=len(errors),
                errors=errors,
                imported_items=imported,
            )
        except Exception as e:
            return SyncResult(
                system=self.system_name,
                direction="IMPORT",
                status=SyncStatus.FAILED,
                errors=[str(e)],
            )

    def export_estimation(self, estimation_data: dict) -> SyncResult:
        """Push estimation results to a Jira issue via custom fields."""
        external_id = estimation_data.get("external_id")  # Jira issue key
        if not external_id:
            return SyncResult(
                system=self.system_name,
                direction="EXPORT",
                status=SyncStatus.SKIPPED,
                errors=["No external_id (Jira issue key) provided."],
            )

        try:
            update_fields: dict[str, Any] = {}

            fm = self.field_mappings
            effort_hours_val = estimation_data.get("grand_total_hours", 0)

            if "effort_hours" in fm:
                target = fm["effort_hours"]
                if target == "originalEstimate":
                    # Use Jira's built-in time tracking field
                    # originalEstimate expects a Jira duration string, e.g. "511h"
                    hours = float(effort_hours_val or 0)
                    update_fields["timetracking"] = {
                        "originalEstimate": f"{hours:.0f}h",
                    }
                else:
                    update_fields[target] = effort_hours_val
            if "feasibility" in fm:
                update_fields[fm["feasibility"]] = estimation_data.get("feasibility_status", "")
            if "estimation_number" in fm:
                update_fields[fm["estimation_number"]] = estimation_data.get("estimation_number", "")

            # Add comment with summary
            est_num = estimation_data.get("estimation_number", "N/A")
            total = float(effort_hours_val or 0)
            status = estimation_data.get("feasibility_status", "N/A")

            # Update fields
            if update_fields:
                resp = self._request(
                    "PUT",
                    self._url(f"issue/{external_id}"),
                    json={"fields": update_fields},
                )
                if resp.status_code not in (200, 204):
                    return SyncResult(
                        system=self.system_name,
                        direction="EXPORT",
                        status=SyncStatus.FAILED,
                        errors=[f"Field update failed: HTTP {resp.status_code}: {resp.text[:200]}"],
                    )

            # Add comment
            comment_body = (
                f"Estimation {est_num} completed.\n"
                f"Total effort: {total:.1f} hours\n"
                f"Feasibility: {status}"
            )
            self._request(
                "POST",
                self._url(f"issue/{external_id}/comment"),
                json={"body": comment_body},
            )

            return SyncResult(
                system=self.system_name,
                direction="EXPORT",
                status=SyncStatus.SUCCESS,
                items_processed=1,
                items_updated=1,
            )
        except Exception as e:
            return SyncResult(
                system=self.system_name,
                direction="EXPORT",
                status=SyncStatus.FAILED,
                errors=[str(e)],
            )

    def create_xray_test_plan(self, estimation_data: dict) -> SyncResult:
        """Create an Xray test plan from estimation task breakdown."""
        if not self.xray_enabled:
            return SyncResult(
                system="XRAY",
                direction="EXPORT",
                status=SyncStatus.SKIPPED,
                errors=["Xray integration not enabled."],
            )

        project_key = self.xray_project_key or self.project_key
        if not project_key:
            return SyncResult(
                system="XRAY",
                direction="EXPORT",
                status=SyncStatus.FAILED,
                errors=["No Xray project key configured."],
            )

        try:
            est_num = estimation_data.get("estimation_number", "")
            project_name = estimation_data.get("project_name", "")
            tasks = estimation_data.get("tasks", [])

            # Create a Test Plan issue
            plan_data = {
                "fields": {
                    "project": {"key": project_key},
                    "summary": f"Test Plan - {est_num}: {project_name}",
                    "description": (
                        f"Auto-generated test plan from estimation {est_num}.\n"
                        f"Total effort: {estimation_data.get('grand_total_hours', 0):.1f} hours\n"
                        f"Tasks: {len(tasks)}"
                    ),
                    "issuetype": {"name": "Test Plan"},
                }
            }

            resp = self._request(
                "POST",
                self._url("issue"),
                json=plan_data,
            )

            if resp.status_code == 201:
                plan_key = resp.json().get("key", "")
                return SyncResult(
                    system="XRAY",
                    direction="EXPORT",
                    status=SyncStatus.SUCCESS,
                    items_processed=1,
                    items_created=1,
                )
            return SyncResult(
                system="XRAY",
                direction="EXPORT",
                status=SyncStatus.FAILED,
                errors=[f"HTTP {resp.status_code}: {resp.text[:200]}"],
            )
        except Exception as e:
            return SyncResult(
                system="XRAY",
                direction="EXPORT",
                status=SyncStatus.FAILED,
                errors=[str(e)],
            )
