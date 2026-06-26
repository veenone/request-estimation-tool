"""Integrations page — configure and test REDMINE, JIRA, EMAIL, OUTLINE.

API used:
    GET  /integrations                          -> list[IntegrationConfigOut]
    PUT  /integrations/{system_name}            -> IntegrationConfigOut
    POST /integrations/{system_name}/test       -> {success, message, details}
    POST /integrations/{system_name}/sync       -> SyncResultOut

The ``additional_config_json`` field in the API payload is a JSON string.
Each per-system panel assembles that string from individual labeled fields
and parses it back when loading saved configuration.
"""

from __future__ import annotations

import json

from nicegui import ui
from frontend_nicegui.app import (
    api_get,
    api_post,
    api_put,
    format_age,
    format_datetime,
    is_authenticated,
    loading_state,
    run_async,
    show_error_page,
    sidebar,
)

SYSTEMS: list[str] = ["REDMINE", "JIRA", "EMAIL", "OUTLINE", "SNIPE_IT"]

SYSTEM_ICONS: dict[str, str] = {
    "REDMINE":  "bug_report",
    "JIRA":     "view_kanban",
    "EMAIL":    "email",
    "OUTLINE":  "article",
    "SNIPE_IT": "inventory_2",
}


# ---------------------------------------------------------------------------
# Shared action buttons (Test Connection / Sync)
# ---------------------------------------------------------------------------

def _render_action_buttons(
    system: str,
    last_sync: str | None,
    required_check=None,
) -> None:
    """Render Test Connection and Sync buttons plus last-sync info.

    ``required_check`` is an optional no-arg callable returning a string with a
    warning message when a required field (e.g. host/url) is missing, or
    ``None`` / "" when the pre-check passes.  It short-circuits the API call so
    we never fire a doomed request.
    """
    with ui.row().classes("items-center gap-2 flex-wrap q-mt-sm"):

        async def test_connection(_sys: str = system) -> None:
            result: dict = await api_post(f"/integrations/{_sys}/test")
            if result.get("success"):
                ui.notify(
                    f"Connection OK: {result.get('message', '')}",
                    type="positive",
                    timeout=5000,
                )
            else:
                ui.notify(
                    f"Connection failed: {result.get('message', '')}",
                    type="warning",
                    timeout=6000,
                )

        async def run_sync(_sys: str = system) -> None:
            result: dict = await api_post(f"/integrations/{_sys}/sync")
            status     = result.get("status", "unknown")
            processed  = result.get("items_processed", 0)
            created    = result.get("items_created", 0)
            updated    = result.get("items_updated", 0)
            failed     = result.get("items_failed", 0)
            errors     = result.get("errors", [])

            summary = (
                f"Sync {status} — "
                f"{processed} processed, "
                f"{created} created, "
                f"{updated} updated, "
                f"{failed} failed."
            )
            if errors:
                summary += f" Errors: {'; '.join(errors[:3])}"

            notify_type = (
                "positive" if status in ("SUCCESS", "success") else
                "warning"  if failed > 0 else
                "info"
            )
            ui.notify(summary, type=notify_type, timeout=7000)

        test_btn = ui.button(
            "Test Connection",
            icon="wifi_tethering",
        ).props("flat color=secondary")

        sync_btn = ui.button(
            "Sync",
            icon="sync",
        ).props("flat color=accent")

        def _guard(handler):
            async def _on_click(*_):
                if required_check is not None:
                    msg = required_check()
                    if msg:
                        ui.notify(msg, type="warning")
                        return
                await handler()
            return _on_click

        test_btn.on(
            "click",
            _guard(run_async(test_btn, test_connection, error_prefix="Test error")),
        )
        sync_btn.on(
            "click",
            _guard(run_async(sync_btn, run_sync, error_prefix="Sync error")),
        )

        if last_sync:
            ui.label(f"Last synced: {format_age(last_sync)}") \
                .classes("text-caption text-grey q-ml-sm") \
                .tooltip(format_datetime(last_sync))
        else:
            ui.label("Never synced.").classes("text-caption text-grey q-ml-sm")


# ---------------------------------------------------------------------------
# REDMINE panel
# ---------------------------------------------------------------------------

def _build_redmine_panel(data: dict, assignable_users: list[dict] | None = None, current_watchers: list[int] | None = None) -> None:
    """Per-system form for REDMINE with individual labeled fields."""

    has_api_key: bool = bool(data.get("has_api_key", False))
    last_sync: str | None = data.get("last_sync_at")

    extra: dict = {}
    raw_json = data.get("additional_config_json") or "{}"
    try:
        extra = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        extra = {}

    with ui.column().classes("q-pa-md w-full gap-3"):

        # -- Connection Settings -------------------------------------------------
        ui.label("Connection Settings").classes("text-subtitle1 text-weight-medium")

        base_url_input = ui.input(
            label="Base URL",
            value=data.get("base_url") or "",
            placeholder="https://redmine.example.com",
        ).classes("w-full")

        api_key_input = ui.input(
            label="API Key",
            value="",
            password=True,
            password_toggle_button=True,
            placeholder="(unchanged)" if has_api_key else "Your Redmine API key",
        ).classes("w-full")
        if has_api_key:
            ui.label(
                "An API key is already stored on the server. "
                "Leave this field empty to keep it unchanged."
            ).classes("text-caption text-grey")

        ui.separator()

        # -- Additional Settings ------------------------------------------------
        ui.label("Additional Settings").classes("text-subtitle1 text-weight-medium")

        with ui.row().classes("w-full gap-3 flex-wrap"):
            project_id_input = ui.input(
                label="Project ID",
                value=extra.get("project_id", ""),
                placeholder="e.g., 1",
            ).classes("flex-1")

            tracker_id_input = ui.input(
                label="Tracker ID",
                value=extra.get("tracker_id", ""),
                placeholder="e.g., 1",
            ).classes("flex-1")

        ui.separator()

        # -- Auto-sync Settings ------------------------------------------------
        ui.label("Auto-sync Settings").classes("text-subtitle1 text-weight-medium")

        with ui.row().classes("w-full gap-3 flex-wrap items-end"):
            poll_interval_input = ui.number(
                label="Polling Interval (minutes)",
                value=int(extra.get("poll_interval_minutes", 0) or 0),
                min=0,
                step=5,
                format="%.0f",
            ).classes("flex-1")
            ui.label(
                "Set to 0 to disable auto-polling. Requires app restart to take effect."
            ).classes("text-caption text-grey")

        with ui.row().classes("w-full items-end gap-2"):
            webhook_secret_input = ui.input(
                label="Webhook Secret",
                value=extra.get("webhook_secret", ""),
                placeholder="Shared secret for webhook validation",
            ).classes("flex-1")

            def _generate_secret() -> None:
                import secrets
                webhook_secret_input.value = secrets.token_urlsafe(32)

            ui.button(
                "Generate", icon="casino", on_click=_generate_secret,
            ).props("outline dense").tooltip("Generate a random secure secret")

        with ui.column().classes("q-mt-xs gap-1"):
            ui.label("Webhook URL (configure in Redmine):").classes("text-caption text-grey")
            ui.label("/api/webhooks/redmine").classes("text-body2 text-primary")
            ui.label(
                "Complete URL example: "
                "https://<your-server>:8000/api/webhooks/redmine?token=<webhook_secret>"
            ).classes("text-caption text-grey")
            ui.label(
                "Replace <your-server> with your hostname or IP, and <webhook_secret> "
                "with the secret configured above. Port 8000 is the dedicated API port "
                "exposed via HTTPS through the nginx reverse proxy."
            ).classes("text-caption text-grey")

        ui.separator()

        # -- Webhook Notification Watchers -------------------------------------
        ui.label("Webhook Notification Watchers").classes("text-subtitle1 text-weight-medium")
        ui.label(
            "Select users who should be notified when new requests are imported via webhook."
        ).classes("text-caption text-grey")

        user_options = {u["id"]: u.get("display_name") or u.get("username", f"User {u['id']}") for u in (assignable_users or [])}
        watcher_select = ui.select(
            label="Watchers",
            options=user_options,
            value=current_watchers or [],
            multiple=True,
        ).props("use-chips clearable").classes("w-full")

        ui.separator()

        # -- Field Mappings -----------------------------------------------------
        ui.label("Field Mappings").classes("text-subtitle1 text-weight-medium")

        with ui.row().classes("w-full gap-3 flex-wrap"):
            effort_field_input = ui.input(
                label="Effort Hours Field ID",
                value=extra.get("effort_hours_field_id", ""),
                placeholder="Custom field ID or 'estimated_hours'",
            ).classes("flex-1")

            feasibility_field_input = ui.input(
                label="Feasibility Field ID",
                value=extra.get("feasibility_field_id", ""),
                placeholder="Custom field ID",
            ).classes("flex-1")

            estimation_field_input = ui.input(
                label="Estimation Number Field ID",
                value=extra.get("estimation_number_field_id", ""),
                placeholder="Custom field ID",
            ).classes("flex-1")

        # -- Task Breakdown Export -----------------------------------------------
        ui.label("Task Breakdown Export").classes("text-subtitle1 text-weight-medium")
        ui.label(
            "Configure sub-task creation when exporting estimation task breakdown to Redmine."
        ).classes("text-caption text-grey q-mb-sm")

        subtask_tracker_input = ui.input(
            label="Sub-task Tracker ID",
            value=extra.get("subtask_tracker_id", ""),
            placeholder="(uses parent issue tracker if empty)",
        ).classes("w-full")
        ui.label(
            "Redmine tracker ID for sub-tasks. Leave empty to use the same tracker as the parent issue."
        ).classes("text-caption text-grey")

        with ui.row().classes("items-center gap-2"):
            ssl_verify_toggle = ui.switch(
                "Verify SSL",
                value=bool(extra.get("ssl_verify", True)),
            )
            ui.label(
                "Turn off only for self-signed / internal-CA certificates."
            ).classes("text-caption text-grey")

        ui.separator()

        # -- Enabled toggle -----------------------------------------------------
        enabled_toggle = ui.switch(
            "Enable Redmine Integration",
            value=bool(data.get("enabled", False)),
        )

        # -- Action buttons (Test / Sync) ---------------------------------------
        _render_action_buttons(
            "REDMINE", last_sync,
            required_check=lambda: "Base URL is required before testing/syncing."
            if not (base_url_input.value or "").strip() else None,
        )

        # -- Save ---------------------------------------------------------------
        async def save_redmine(
            _tog=enabled_toggle,
            _url=base_url_input,
            _key=api_key_input,
            _pid=project_id_input,
            _tid=tracker_id_input,
            _eff=effort_field_input,
            _fea=feasibility_field_input,
            _est=estimation_field_input,
            _poll=poll_interval_input,
            _ws=webhook_secret_input,
            _watchers=watcher_select,
            _stid=subtask_tracker_input,
            _ssl=ssl_verify_toggle,
        ) -> None:
            additional: dict = {
                "project_id":               (_pid.value or "").strip(),
                "tracker_id":               (_tid.value or "").strip(),
                "effort_hours_field_id":    (_eff.value or "").strip(),
                "feasibility_field_id":     (_fea.value or "").strip(),
                "estimation_number_field_id": (_est.value or "").strip(),
                "poll_interval_minutes":    int(_poll.value or 0),
                "webhook_secret":           (_ws.value or "").strip(),
                "subtask_tracker_id":       (_stid.value or "").strip(),
                "ssl_verify":               _ssl.value,
            }
            payload: dict = {
                "enabled":                _tog.value,
                "base_url":               (_url.value or "").strip() or None,
                "username":               None,
                "additional_config_json": json.dumps(additional),
            }
            raw_key = (_key.value or "").strip()
            if raw_key:
                payload["api_key"] = raw_key

            await api_put("/integrations/REDMINE", json=payload)
            # Save webhook watchers config
            selected_ids = _watchers.value if _watchers.value else []
            await api_put("/configuration/webhook_watchers", json={"value": json.dumps(selected_ids)})

        def _on_redmine_saved(_result, _key=api_key_input) -> None:
            # Keep the credential field populated on success; just mark it as
            # stored so the user knows the secret persisted.
            if (_key.value or "").strip():
                _key.props('placeholder="(unchanged)"')

        save_btn = ui.button("Save", icon="save").props("color=primary")
        save_btn.on("click", run_async(
            save_btn, save_redmine,
            success="Credentials saved securely.",
            on_success=_on_redmine_saved,
            error_prefix="Save failed",
        ))


# ---------------------------------------------------------------------------
# JIRA panel
# ---------------------------------------------------------------------------

def _build_jira_panel(data: dict) -> None:
    """Per-system form for JIRA with individual labeled fields."""

    has_api_key: bool = bool(data.get("has_api_key", False))
    last_sync: str | None = data.get("last_sync_at")

    extra: dict = {}
    raw_json = data.get("additional_config_json") or "{}"
    try:
        extra = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        extra = {}

    with ui.column().classes("q-pa-md w-full gap-3"):

        # -- Connection Settings -------------------------------------------------
        ui.label("Connection Settings").classes("text-subtitle1 text-weight-medium")

        base_url_input = ui.input(
            label="Base URL",
            value=data.get("base_url") or "",
            placeholder="https://jira.example.com",
        ).classes("w-full")

        api_key_input = ui.input(
            label="API Key",
            value="",
            password=True,
            password_toggle_button=True,
            placeholder="(unchanged)" if has_api_key else "Your Jira API key",
        ).classes("w-full")
        if has_api_key:
            ui.label(
                "An API key is already stored on the server. "
                "Leave this field empty to keep it unchanged."
            ).classes("text-caption text-grey")

        username_input = ui.input(
            label="Username",
            value=data.get("username") or "",
            placeholder="Jira account username",
        ).classes("w-full")

        ui.separator()

        # -- Additional Settings ------------------------------------------------
        ui.label("Additional Settings").classes("text-subtitle1 text-weight-medium")

        jql_filter_input = ui.textarea(
            label="JQL Filter",
            value=extra.get("jql_filter", ""),
            placeholder='e.g., type = "Feature Request" AND status = "Open"',
        ).classes("w-full").props("rows=3")

        project_key_input = ui.input(
            label="Project Key",
            value=extra.get("project_key", ""),
            placeholder="e.g., PROJ",
        ).classes("w-full")

        ui.separator()

        # -- Deployment Settings ------------------------------------------------
        ui.label("Deployment Settings").classes("text-subtitle1 text-weight-medium")

        with ui.row().classes("w-full gap-4 flex-wrap items-start"):

            with ui.column().classes("gap-1"):
                is_cloud_toggle = ui.switch(
                    "Jira Cloud",
                    value=bool(extra.get("is_cloud", False)),
                )
                ui.label("Check if using Jira Cloud").classes("text-caption text-grey")

            auth_mode_select = ui.select(
                label="Auth Mode",
                options=["auto", "basic", "pat"],
                value=extra.get("auth_mode", "auto")
                      if extra.get("auth_mode", "auto") in ("auto", "basic", "pat")
                      else "auto",
            ).classes("flex-1")

            issue_type_input = ui.input(
                label="Issue Type",
                value=extra.get("issue_type", ""),
                placeholder="e.g., Story",
            ).classes("flex-1")

            with ui.column().classes("gap-1"):
                ssl_verify_toggle = ui.switch(
                    "Verify SSL",
                    value=bool(extra.get("ssl_verify", True)),
                )
                ui.label("Uncheck for self-signed certs").classes("text-caption text-grey")

            with ui.column().classes("gap-1"):
                bypass_proxy_toggle = ui.switch(
                    "Bypass proxy",
                    value=bool(extra.get("bypass_proxy", False)),
                )
                ui.label(
                    "Enable for internal Jira behind a corporate proxy (502 errors)."
                ).classes("text-caption text-grey")

        ui.separator()

        # -- Field Mappings -----------------------------------------------------
        ui.label("Field Mappings").classes("text-subtitle1 text-weight-medium")

        with ui.row().classes("w-full gap-3 flex-wrap"):
            effort_field_input = ui.input(
                label="Effort Hours Custom Field",
                value=extra.get("effort_hours_field", ""),
                placeholder="customfield_10000 or 'originalEstimate'",
            ).classes("flex-1")

            feasibility_field_input = ui.input(
                label="Feasibility Custom Field",
                value=extra.get("feasibility_field", ""),
                placeholder="customfield_10001",
            ).classes("flex-1")

            estimation_field_input = ui.input(
                label="Estimation Number Custom Field",
                value=extra.get("estimation_number_field", ""),
                placeholder="customfield_10002",
            ).classes("flex-1")

        ui.separator()

        # -- X-Ray Integration --------------------------------------------------
        ui.label("X-Ray Integration").classes("text-subtitle1 text-weight-medium")

        with ui.row().classes("w-full gap-4 flex-wrap items-start"):
            with ui.column().classes("gap-1"):
                xray_enabled_toggle = ui.switch(
                    "Enable X-Ray Integration",
                    value=bool(extra.get("xray_enabled", False)),
                )
                ui.label("Enable test result sync with X-Ray").classes("text-caption text-grey")

            xray_project_key_input = ui.input(
                label="X-Ray Project Key",
                value=extra.get("xray_project_key", ""),
                placeholder="e.g., XRAY",
            ).classes("flex-1")

        # -- Task Breakdown Export -----------------------------------------------
        ui.label("Task Breakdown Export").classes("text-subtitle1 text-weight-medium")
        ui.label(
            "Configure sub-task creation when exporting estimation task breakdown to Jira."
        ).classes("text-caption text-grey q-mb-sm")

        task_export_type_input = ui.input(
            label="Standalone Task Issue Type",
            value=extra.get("task_export_type", ""),
            placeholder="e.g. Todo, Task (auto-detect if empty)",
        ).classes("w-full")
        ui.label(
            "Issue type for standalone tasks (no parent). Auto-detected from project if empty."
        ).classes("text-caption text-grey")

        subtask_type_input = ui.input(
            label="Sub-task Issue Type",
            value=extra.get("subtask_type", "Sub-task"),
            placeholder="Sub-task",
        ).classes("w-full")
        ui.label(
            "Issue type when creating sub-tasks under a parent issue (default: Sub-task)."
        ).classes("text-caption text-grey")

        ui.separator()

        # -- Problem Reports (PR) Integration -----------------------------------
        ui.label("Problem Reports (PR)").classes("text-subtitle1 text-weight-medium")
        ui.label(
            "Configure a separate JQL query to import Problem Reports / Defects from Jira. "
            "These can be used as PR fix items in estimations."
        ).classes("text-caption text-grey q-mb-sm")

        pr_api_key_input = ui.input(
            label="PR API Key / Token",
            value="",
            password=True,
            password_toggle_button=True,
            placeholder="(uses connection API key if empty)",
        ).classes("w-full")
        ui.label(
            "Optional separate API key for PR queries. Leave empty to use the connection API key."
        ).classes("text-caption text-grey")

        with ui.row().classes("items-center gap-2"):
            pr_bypass_proxy_toggle = ui.switch(
                "PR bypass proxy",
                value=bool(extra.get("pr_bypass_proxy", False)),
            )
            ui.label(
                "Bypass the corporate proxy for PR queries (internal hosts / 502 errors)."
            ).classes("text-caption text-grey")

        pr_jql_input = ui.textarea(
            label="PR JQL Filter",
            value=extra.get("pr_jql_filter", ""),
            placeholder='e.g., type = "Bug" AND status = "Open" AND project = PROJ',
        ).classes("w-full").props("rows=3")

        pr_fields_input = ui.input(
            label="PR Additional Fields (comma-separated)",
            value=extra.get("pr_fields", ""),
            placeholder="e.g., customfield_10100,priority,components",
        ).classes("w-full")
        ui.label(
            "Optional Jira fields to fetch alongside summary, status, and priority. "
            "These will be available as extra columns when importing PRs."
        ).classes("text-caption text-grey")

        # -- Sync PR items button --
        pr_result_label = ui.label("").classes("text-caption q-mt-xs")

        async def _sync_pr_items(
            _pr_jql=pr_jql_input,
        ) -> None:
            items = await api_get(
                "/integrations/JIRA/pr-items",
                params={"jql": (_pr_jql.value or "").strip()},
            )
            count = len(items) if isinstance(items, list) else 0
            pr_result_label.set_text(f"Fetched {count} PR item(s)")
            if count:
                ui.notify(f"Found {count} PR item(s).", type="positive")
            else:
                ui.notify("No items found matching the filter.", type="info")

        pr_fetch_btn = ui.button(
            "Fetch PR Items", icon="bug_report",
        ).props("flat color=secondary")

        def _on_pr_fetch_click(*_):
            if not (pr_jql_input.value or "").strip():
                ui.notify("PR JQL Filter is empty.", type="warning")
                return
            return run_async(
                pr_fetch_btn, _sync_pr_items, error_prefix="PR fetch failed",
            )()

        pr_fetch_btn.on("click", _on_pr_fetch_click)

        async def _test_pr_conn() -> None:
            result = await api_post("/integrations/JIRA/pr-test-connection")
            if result.get("success"):
                ui.notify(
                    f"PR connection OK: {result.get('message', '')}",
                    type="positive", timeout=7000,
                )
            else:
                ui.notify(
                    f"PR connection failed: {result.get('message', '')}",
                    type="warning", timeout=9000,
                )

        pr_test_btn = ui.button(
            "Test PR Connection", icon="link",
        ).props("flat color=secondary")
        pr_test_btn.on("click", run_async(
            pr_test_btn, _test_pr_conn, error_prefix="PR test failed",
        ))
        ui.label(
            "Tests the saved PR token (or main token if none) — save changes first."
        ).classes("text-caption text-grey")

        ui.separator()

        # -- Enabled toggle -----------------------------------------------------
        enabled_toggle = ui.switch(
            "Enable Jira Integration",
            value=bool(data.get("enabled", False)),
        )

        # -- Action buttons (Test / Sync) ---------------------------------------
        _render_action_buttons(
            "JIRA", last_sync,
            required_check=lambda: "Base URL is required before testing/syncing."
            if not (base_url_input.value or "").strip() else None,
        )

        # -- Save ---------------------------------------------------------------
        async def save_jira(
            _tog=enabled_toggle,
            _url=base_url_input,
            _key=api_key_input,
            _usr=username_input,
            _jql=jql_filter_input,
            _pk=project_key_input,
            _cld=is_cloud_toggle,
            _auth=auth_mode_select,
            _it=issue_type_input,
            _ssl=ssl_verify_toggle,
            _bp=bypass_proxy_toggle,
            _eff=effort_field_input,
            _fea=feasibility_field_input,
            _est=estimation_field_input,
            _xe=xray_enabled_toggle,
            _xk=xray_project_key_input,
            _pr_jql=pr_jql_input,
            _pr_fields=pr_fields_input,
            _pr_key=pr_api_key_input,
            _pr_bp=pr_bypass_proxy_toggle,
            _st=subtask_type_input,
            _tet=task_export_type_input,
        ) -> None:
            additional: dict = {
                "jql_filter":             (_jql.value or "").strip(),
                "project_key":            (_pk.value or "").strip(),
                "is_cloud":               _cld.value,
                "auth_mode":              _auth.value or "auto",
                "issue_type":             (_it.value or "").strip(),
                "ssl_verify":             _ssl.value,
                "bypass_proxy":           _bp.value,
                "effort_hours_field":     (_eff.value or "").strip(),
                "feasibility_field":      (_fea.value or "").strip(),
                "estimation_number_field": (_est.value or "").strip(),
                "xray_enabled":           _xe.value,
                "xray_project_key":       (_xk.value or "").strip(),
                "pr_jql_filter":          (_pr_jql.value or "").strip(),
                "pr_fields":              (_pr_fields.value or "").strip(),
                "pr_bypass_proxy":        _pr_bp.value,
                "subtask_type":           (_st.value or "Sub-task").strip(),
                "task_export_type":       (_tet.value or "").strip(),
            }
            # Save PR API key separately if provided
            pr_key_raw = (_pr_key.value or "").strip()
            if pr_key_raw:
                additional["pr_api_key"] = pr_key_raw
            payload: dict = {
                "enabled":                _tog.value,
                "base_url":               (_url.value or "").strip() or None,
                "username":               (_usr.value or "").strip() or None,
                "additional_config_json": json.dumps(additional),
            }
            raw_key = (_key.value or "").strip()
            if raw_key:
                payload["api_key"] = raw_key

            await api_put("/integrations/JIRA", json=payload)

        def _on_jira_saved(_result, _key=api_key_input, _pr_key=pr_api_key_input) -> None:
            if (_key.value or "").strip():
                _key.props('placeholder="(unchanged)"')
            if (_pr_key.value or "").strip():
                _pr_key.props('placeholder="(unchanged)"')

        save_btn = ui.button("Save", icon="save").props("color=primary")
        save_btn.on("click", run_async(
            save_btn, save_jira,
            success="Credentials saved securely.",
            on_success=_on_jira_saved,
            error_prefix="Save failed",
        ))


# ---------------------------------------------------------------------------
# EMAIL panel
# ---------------------------------------------------------------------------

def _build_email_panel(data: dict) -> None:
    """Per-system form for EMAIL with individual labeled fields.

    username and api_key are stored as top-level fields (not inside
    additional_config_json).  SMTP-specific settings are stored inside
    additional_config_json.
    """

    has_api_key: bool = bool(data.get("has_api_key", False))
    last_sync: str | None = data.get("last_sync_at")

    extra: dict = {}
    raw_json = data.get("additional_config_json") or "{}"
    try:
        extra = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        extra = {}

    with ui.column().classes("q-pa-md w-full gap-3"):

        # -- SMTP Settings ------------------------------------------------------
        ui.label("SMTP Settings").classes("text-subtitle1 text-weight-medium")

        smtp_host_input = ui.input(
            label="SMTP Host",
            value=extra.get("smtp_host", ""),
            placeholder="smtp.gmail.com",
        ).classes("w-full")

        smtp_port_input = ui.number(
            label="SMTP Port",
            value=int(extra.get("smtp_port", 587)),
            min=1,
            max=65535,
            step=1,
            format="%.0f",
        ).classes("w-full")

        with ui.row().classes("items-center gap-2"):
            smtp_tls_toggle = ui.switch(
                "Use TLS",
                value=bool(extra.get("smtp_use_tls", True)),
            )
            ui.label("Enable TLS encryption for SMTP").classes("text-caption text-grey")

        ui.separator()

        # -- Authentication -----------------------------------------------------
        ui.label("Authentication").classes("text-subtitle1 text-weight-medium")

        username_input = ui.input(
            label="SMTP Username",
            value=data.get("username") or "",
            placeholder="your-email@example.com",
        ).classes("w-full")

        api_key_input = ui.input(
            label="SMTP Password",
            value="",
            password=True,
            password_toggle_button=True,
            placeholder="(unchanged)" if has_api_key else "Your email password or app password",
        ).classes("w-full")
        if has_api_key:
            ui.label(
                "A password is already stored on the server. "
                "Leave this field empty to keep it unchanged."
            ).classes("text-caption text-grey")

        ui.separator()

        # -- Sender Settings ----------------------------------------------------
        ui.label("Sender Settings").classes("text-subtitle1 text-weight-medium")

        with ui.row().classes("w-full gap-3 flex-wrap"):
            sender_email_input = ui.input(
                label="Sender Email",
                value=extra.get("sender_email", ""),
                placeholder="noreply@example.com",
            ).classes("flex-1")

            sender_name_input = ui.input(
                label="Sender Name",
                value=extra.get("sender_name", ""),
                placeholder="Estimation Tool",
            ).classes("flex-1")

        ui.separator()

        # -- Enabled toggle -----------------------------------------------------
        enabled_toggle = ui.switch(
            "Enable Email Integration",
            value=bool(data.get("enabled", False)),
        )

        # -- Action buttons (Test / Sync) ---------------------------------------
        def _email_precheck() -> str | None:
            if not (smtp_host_input.value or "").strip():
                return "SMTP Host is required before testing."
            if not (smtp_port_input.value or 0):
                return "SMTP Port is required before testing."
            return None

        _render_action_buttons("EMAIL", last_sync, required_check=_email_precheck)

        # -- Save ---------------------------------------------------------------
        async def save_email(
            _tog=enabled_toggle,
            _key=api_key_input,
            _usr=username_input,
            _host=smtp_host_input,
            _port=smtp_port_input,
            _tls=smtp_tls_toggle,
            _se=sender_email_input,
            _sn=sender_name_input,
        ) -> None:
            additional: dict = {
                "smtp_host":     (_host.value or "").strip(),
                "smtp_port":     int(_port.value or 587),
                "smtp_use_tls":  _tls.value,
                "sender_email":  (_se.value or "").strip(),
                "sender_name":   (_sn.value or "").strip(),
            }
            payload: dict = {
                "enabled":                _tog.value,
                "base_url":               None,
                "username":               (_usr.value or "").strip() or None,
                "additional_config_json": json.dumps(additional),
            }
            raw_key = (_key.value or "").strip()
            if raw_key:
                payload["api_key"] = raw_key

            await api_put("/integrations/EMAIL", json=payload)

        def _on_email_saved(_result, _key=api_key_input) -> None:
            if (_key.value or "").strip():
                _key.props('placeholder="(unchanged)"')

        save_btn = ui.button("Save", icon="save").props("color=primary")
        save_btn.on("click", run_async(
            save_btn, save_email,
            success="Credentials saved securely.",
            on_success=_on_email_saved,
            error_prefix="Save failed",
        ))


# ---------------------------------------------------------------------------
# OUTLINE panel
# ---------------------------------------------------------------------------

def _build_outline_panel(data: dict) -> None:
    """Per-system form for OUTLINE with individual labeled fields."""

    has_api_key: bool = bool(data.get("has_api_key", False))
    last_sync: str | None = data.get("last_sync_at")

    extra: dict = {}
    raw_json = data.get("additional_config_json") or "{}"
    try:
        extra = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        extra = {}

    with ui.column().classes("q-pa-md w-full gap-3"):

        # -- Connection Settings -------------------------------------------------
        ui.label("Connection Settings").classes("text-subtitle1 text-weight-medium")

        base_url_input = ui.input(
            label="Outline URL",
            value=data.get("base_url") or "",
            placeholder="https://wiki.example.com",
        ).classes("w-full")

        api_key_input = ui.input(
            label="API Key",
            value="",
            password=True,
            password_toggle_button=True,
            placeholder="(unchanged)" if has_api_key else "Your Outline API key",
        ).classes("w-full")
        if has_api_key:
            ui.label(
                "An API key is already stored on the server. "
                "Leave this field empty to keep it unchanged."
            ).classes("text-caption text-grey")

        ui.separator()

        # -- Publishing Settings ------------------------------------------------
        ui.label("Publishing Settings").classes("text-subtitle1 text-weight-medium")

        collection_id_input = ui.input(
            label="Collection ID",
            value=extra.get("collection_id", ""),
            placeholder="UUID of target collection",
        ).classes("w-full")

        with ui.row().classes("items-center gap-2"):
            auto_publish_toggle = ui.switch(
                "Auto-publish on approval",
                value=bool(extra.get("auto_publish", False)),
            )
            ui.label(
                "Automatically publish estimation to Outline when status changes to APPROVED"
            ).classes("text-caption text-grey")

        with ui.row().classes("items-center gap-2"):
            ssl_verify_toggle = ui.switch(
                "Verify SSL",
                value=bool(extra.get("ssl_verify", True)),
            )
            ui.label(
                "Turn off only for self-signed / internal-CA certificates."
            ).classes("text-caption text-grey")

        ui.separator()

        # -- Enabled toggle -----------------------------------------------------
        enabled_toggle = ui.switch(
            "Enable Outline Integration",
            value=bool(data.get("enabled", False)),
        )

        # -- Action buttons (Test / Sync) ---------------------------------------
        _render_action_buttons(
            "OUTLINE", last_sync,
            required_check=lambda: "Outline URL is required before testing/syncing."
            if not (base_url_input.value or "").strip() else None,
        )

        # -- Save ---------------------------------------------------------------
        async def save_outline(
            _tog=enabled_toggle,
            _url=base_url_input,
            _key=api_key_input,
            _cid=collection_id_input,
            _ap=auto_publish_toggle,
            _ssl=ssl_verify_toggle,
        ) -> None:
            additional: dict = {
                "collection_id": (_cid.value or "").strip(),
                "auto_publish":  _ap.value,
                "ssl_verify":    _ssl.value,
            }
            payload: dict = {
                "enabled":                _tog.value,
                "base_url":               (_url.value or "").strip() or None,
                "username":               None,
                "additional_config_json": json.dumps(additional),
            }
            raw_key = (_key.value or "").strip()
            if raw_key:
                payload["api_key"] = raw_key

            await api_put("/integrations/OUTLINE", json=payload)

        def _on_outline_saved(_result, _key=api_key_input) -> None:
            if (_key.value or "").strip():
                _key.props('placeholder="(unchanged)"')

        save_btn = ui.button("Save", icon="save").props("color=primary")
        save_btn.on("click", run_async(
            save_btn, save_outline,
            success="Credentials saved securely.",
            on_success=_on_outline_saved,
            error_prefix="Save failed",
        ))


# ---------------------------------------------------------------------------
# SNIPE_IT panel
# ---------------------------------------------------------------------------

def _build_snipe_it_panel(data: dict) -> None:
    """Per-system form for SNIPE_IT with individual labeled fields."""

    has_api_key: bool = bool(data.get("has_api_key", False))
    last_sync: str | None = data.get("last_sync_at")

    extra: dict = {}
    raw_json = data.get("additional_config_json") or "{}"
    try:
        extra = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        extra = {}

    with ui.column().classes("q-pa-md w-full gap-3"):

        ui.label("Connection Settings").classes("text-subtitle1 text-weight-medium")

        base_url_input = ui.input(
            label="Base URL",
            value=data.get("base_url") or "",
            placeholder="https://snipeit.example.com",
        ).classes("w-full")

        api_key_input = ui.input(
            label="API Key (Bearer Token)",
            value="",
            password=True,
            password_toggle_button=True,
            placeholder="(unchanged)" if has_api_key else "Your Snipe-IT API key",
        ).classes("w-full")
        if has_api_key:
            ui.label(
                "An API key is already stored on the server. "
                "Leave this field empty to keep it unchanged."
            ).classes("text-caption text-grey")

        ui.separator()

        ui.label("Asset Settings").classes("text-subtitle1 text-weight-medium")

        # Parse previously saved categories into a list
        _saved_cats_str = extra.get("categories", "")
        _saved_cats = [c.strip() for c in _saved_cats_str.split(",") if c.strip()] if _saved_cats_str else []

        categories_select = ui.select(
            options=_saved_cats or [],
            label="Categories (select from Snipe-IT)",
            value=_saved_cats,
            multiple=True,
            with_input=True,
            clearable=True,
        ).classes("w-full")
        ui.label(
            "Select categories to filter DUT assets. Click 'Fetch Categories' to load from Snipe-IT."
        ).classes("text-caption text-grey")

        async def _fetch_categories(_sel=categories_select) -> None:
            cats: list = await api_get("/integrations/SNIPE_IT/categories")
            names = sorted([c.get("name", "") for c in cats if c.get("name")])
            _sel.options = names
            _sel.update()
            if names:
                ui.notify(f"Loaded {len(names)} categories from Snipe-IT.", type="positive")
            else:
                ui.notify("No items found matching the filter.", type="info")

        fetch_cats_btn = ui.button(
            "Fetch Categories", icon="sync",
        ).props("flat color=secondary dense")

        def _on_fetch_cats_click(*_):
            if not (base_url_input.value or "").strip():
                ui.notify("Base URL is required before fetching categories.", type="warning")
                return
            return run_async(
                fetch_cats_btn, _fetch_categories,
                error_prefix="Failed to fetch categories",
            )()

        fetch_cats_btn.on("click", _on_fetch_cats_click)

        timeout_input = ui.number(
            label="Timeout (seconds)",
            value=int(extra.get("timeout", 30)),
            min=5,
            max=120,
            step=5,
            format="%.0f",
        ).classes("w-full")

        with ui.row().classes("items-center gap-2"):
            ssl_verify_toggle = ui.switch(
                "Verify SSL",
                value=bool(extra.get("ssl_verify", True)),
            )
            ui.label(
                "Turn off only for self-signed / internal-CA certificates."
            ).classes("text-caption text-grey")

        ui.separator()

        enabled_toggle = ui.switch(
            "Enable Snipe-IT Integration",
            value=bool(data.get("enabled", False)),
        )

        _render_action_buttons(
            "SNIPE_IT", last_sync,
            required_check=lambda: "Base URL is required before testing/syncing."
            if not (base_url_input.value or "").strip() else None,
        )

        async def save_snipeit(
            _tog=enabled_toggle,
            _url=base_url_input,
            _key=api_key_input,
            _cats=categories_select,
            _timeout=timeout_input,
            _ssl=ssl_verify_toggle,
        ) -> None:
            # categories_select.value is a list of selected names
            cats_val = _cats.value or []
            cats_str = ", ".join(cats_val) if isinstance(cats_val, list) else str(cats_val)
            additional: dict = {
                "categories": cats_str,
                "timeout": int(_timeout.value or 30),
                "ssl_verify": _ssl.value,
            }
            payload: dict = {
                "enabled": _tog.value,
                "base_url": (_url.value or "").strip() or None,
                "username": None,
                "additional_config_json": json.dumps(additional),
            }
            raw_key = (_key.value or "").strip()
            if raw_key:
                payload["api_key"] = raw_key

            await api_put("/integrations/SNIPE_IT", json=payload)

        def _on_snipeit_saved(_result, _key=api_key_input) -> None:
            if (_key.value or "").strip():
                _key.props('placeholder="(unchanged)"')

        save_btn = ui.button("Save", icon="save").props("color=primary")
        save_btn.on("click", run_async(
            save_btn, save_snipeit,
            success="Credentials saved securely.",
            on_success=_on_snipeit_saved,
            error_prefix="Save failed",
        ))


# ---------------------------------------------------------------------------
# Dispatch table: system name -> panel builder
# ---------------------------------------------------------------------------

_PANEL_BUILDERS = {
    "REDMINE":  _build_redmine_panel,
    "JIRA":     _build_jira_panel,
    "EMAIL":    _build_email_panel,
    "OUTLINE":  _build_outline_panel,
    "SNIPE_IT": _build_snipe_it_panel,
}


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

@ui.page("/integrations")
async def integrations_page() -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    # ---- load all integrations BEFORE building UI -----------------------
    try:
        async with loading_state("Loading integrations…"):
            raw_list: list[dict] = await api_get("/integrations")
    except Exception as exc:
        show_error_page(exc)
        return

    # Index by system_name for easy lookup; provide empty defaults if absent
    by_system: dict[str, dict] = {
        item["system_name"].upper(): item for item in raw_list
    }

    # Fetch assignable users and current watchers for Redmine panel
    assignable_users: list[dict] = []
    current_watchers: list[int] = []
    async with loading_state("Loading users & watchers…"):
        try:
            assignable_users = await api_get("/users/assignable")
        except Exception:
            pass
        try:
            configs = await api_get("/configuration")
            for cfg in configs:
                if cfg.get("key") == "webhook_watchers":
                    current_watchers = json.loads(cfg.get("value", "[]"))
                    break
        except Exception:
            pass

    enabled_n = sum(1 for s in SYSTEMS
                    if by_system.get(s, {}).get("enabled"))

    with ui.column().classes("w-full q-pa-md").style("gap: 0;"):

        # ── Sticky toolbar ──────────────────────────────────────
        with ui.element("div").classes("ed-toolbar"):
            ui.label("Integrations").classes("ed-eyebrow")
            ui.element("div").classes("ed-toolbar-grow")
            with ui.element("div").classes("ed-status-now"):
                ui.element("span").classes("ed-status-dot") \
                    .style("background: var(--q-positive);" if enabled_n else "")
                ui.label(f"{enabled_n} OF {len(SYSTEMS)} ENABLED") \
                    .classes("ed-mono")

        with ui.element("div").classes("ed-shell"):

            ui.label("Integrations").classes("text-h4 q-mb-md")
            ui.label(
                "Configure external systems used by the estimation pipeline. "
                "Each integration has its own credentials and connection settings."
            ).classes("ed-eyebrow").style("margin-bottom: 22px;")

            # ── KPI strip showing per-system status ─────────────
            with ui.element("div").classes("ed-strip").style("margin-bottom: 18px;"):
                for sys in SYSTEMS:
                    sys_data = by_system.get(sys, {})
                    is_enabled = bool(sys_data.get("enabled"))
                    last_sync = sys_data.get("last_sync_at")
                    sync_failed = bool(sys_data.get("last_sync_failed"))
                    icon = SYSTEM_ICONS.get(sys, "settings")
                    with ui.element("div").classes("ed-strip-cell"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon(icon).style(
                                "font-size: 14px; opacity: 0.7;"
                            )
                            ui.label(sys).classes("ed-eyebrow")
                        if not is_enabled:
                            ui.badge("OFF").props("color=grey")
                        elif sync_failed:
                            ui.badge("FAILED").props("color=negative")
                        else:
                            ui.badge("CONNECTED").props("color=positive")
                        if last_sync:
                            ui.label(format_age(last_sync)) \
                                .classes("ed-stat-tile-sub") \
                                .tooltip(format_datetime(last_sync))
                        else:
                            ui.label("Never synced").classes("ed-stat-tile-sub")

            # ── Tabs ────────────────────────────────────────────
            with ui.tabs().classes("ed-tabs w-full").props("inline-label align=left no-caps") as tabs:
                tab_refs: dict[str, ui.tab] = {}
                for sys in SYSTEMS:
                    icon = SYSTEM_ICONS.get(sys, "settings")
                    tab_refs[sys] = ui.tab(sys, label=sys, icon=icon)

            with ui.tab_panels(tabs, value=tab_refs[SYSTEMS[0]]).classes("ed-panels w-full"):
                for sys in SYSTEMS:
                    data = by_system.get(sys, {})
                    with ui.tab_panel(tab_refs[sys]):
                        if sys == "REDMINE":
                            _PANEL_BUILDERS[sys](data, assignable_users=assignable_users, current_watchers=current_watchers)
                        else:
                            _PANEL_BUILDERS[sys](data)
