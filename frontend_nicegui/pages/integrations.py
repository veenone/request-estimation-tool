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
from frontend_nicegui.app import api_get, api_post, api_put, is_authenticated, show_error_page, sidebar

SYSTEMS: list[str] = ["REDMINE", "JIRA", "EMAIL", "OUTLINE"]

SYSTEM_ICONS: dict[str, str] = {
    "REDMINE": "bug_report",
    "JIRA":    "view_kanban",
    "EMAIL":   "email",
    "OUTLINE": "article",
}


# ---------------------------------------------------------------------------
# Shared action buttons (Test Connection / Sync)
# ---------------------------------------------------------------------------

def _render_action_buttons(system: str, last_sync: str | None) -> None:
    """Render Test Connection and Sync buttons plus last-sync info."""
    with ui.row().classes("items-center gap-2 flex-wrap q-mt-sm"):

        async def test_connection(_sys: str = system) -> None:
            try:
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
            except Exception as exc:
                ui.notify(f"Test error: {exc}", type="negative")

        async def run_sync(_sys: str = system) -> None:
            try:
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
            except Exception as exc:
                ui.notify(f"Sync error: {exc}", type="negative")

        ui.button(
            "Test Connection",
            icon="wifi_tethering",
            on_click=test_connection,
        ).props("flat color=secondary")

        ui.button(
            "Sync",
            icon="sync",
            on_click=run_sync,
        ).props("flat color=accent")

        if last_sync:
            ui.label(f"Last synced: {last_sync}").classes("text-caption text-grey q-ml-sm")
        else:
            ui.label("Never synced.").classes("text-caption text-grey q-ml-sm")


# ---------------------------------------------------------------------------
# REDMINE panel
# ---------------------------------------------------------------------------

def _build_redmine_panel(data: dict) -> None:
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

        ui.separator()

        # -- Enabled toggle -----------------------------------------------------
        enabled_toggle = ui.switch(
            "Enable Redmine Integration",
            value=bool(data.get("enabled", False)),
        )

        # -- Action buttons (Test / Sync) ---------------------------------------
        _render_action_buttons("REDMINE", last_sync)

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
        ) -> None:
            additional: dict = {
                "project_id":               (_pid.value or "").strip(),
                "tracker_id":               (_tid.value or "").strip(),
                "effort_hours_field_id":    (_eff.value or "").strip(),
                "feasibility_field_id":     (_fea.value or "").strip(),
                "estimation_number_field_id": (_est.value or "").strip(),
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

            try:
                await api_put("/integrations/REDMINE", json=payload)
                ui.notify("Redmine configuration saved.", type="positive")
                _key.value = ""
            except Exception as exc:
                ui.notify(f"Save failed: {exc}", type="negative")

        ui.button("Save", icon="save", on_click=save_redmine).props("color=primary")


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

        ui.separator()

        # -- Enabled toggle -----------------------------------------------------
        enabled_toggle = ui.switch(
            "Enable Jira Integration",
            value=bool(data.get("enabled", False)),
        )

        # -- Action buttons (Test / Sync) ---------------------------------------
        _render_action_buttons("JIRA", last_sync)

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
            _eff=effort_field_input,
            _fea=feasibility_field_input,
            _est=estimation_field_input,
            _xe=xray_enabled_toggle,
            _xk=xray_project_key_input,
        ) -> None:
            additional: dict = {
                "jql_filter":             (_jql.value or "").strip(),
                "project_key":            (_pk.value or "").strip(),
                "is_cloud":               _cld.value,
                "auth_mode":              _auth.value or "auto",
                "issue_type":             (_it.value or "").strip(),
                "ssl_verify":             _ssl.value,
                "effort_hours_field":     (_eff.value or "").strip(),
                "feasibility_field":      (_fea.value or "").strip(),
                "estimation_number_field": (_est.value or "").strip(),
                "xray_enabled":           _xe.value,
                "xray_project_key":       (_xk.value or "").strip(),
            }
            payload: dict = {
                "enabled":                _tog.value,
                "base_url":               (_url.value or "").strip() or None,
                "username":               (_usr.value or "").strip() or None,
                "additional_config_json": json.dumps(additional),
            }
            raw_key = (_key.value or "").strip()
            if raw_key:
                payload["api_key"] = raw_key

            try:
                await api_put("/integrations/JIRA", json=payload)
                ui.notify("Jira configuration saved.", type="positive")
                _key.value = ""
            except Exception as exc:
                ui.notify(f"Save failed: {exc}", type="negative")

        ui.button("Save", icon="save", on_click=save_jira).props("color=primary")


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
        _render_action_buttons("EMAIL", last_sync)

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

            try:
                await api_put("/integrations/EMAIL", json=payload)
                ui.notify("Email configuration saved.", type="positive")
                _key.value = ""
            except Exception as exc:
                ui.notify(f"Save failed: {exc}", type="negative")

        ui.button("Save", icon="save", on_click=save_email).props("color=primary")


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

        ui.separator()

        # -- Enabled toggle -----------------------------------------------------
        enabled_toggle = ui.switch(
            "Enable Outline Integration",
            value=bool(data.get("enabled", False)),
        )

        # -- Action buttons (Test / Sync) ---------------------------------------
        _render_action_buttons("OUTLINE", last_sync)

        # -- Save ---------------------------------------------------------------
        async def save_outline(
            _tog=enabled_toggle,
            _url=base_url_input,
            _key=api_key_input,
            _cid=collection_id_input,
            _ap=auto_publish_toggle,
        ) -> None:
            additional: dict = {
                "collection_id": (_cid.value or "").strip(),
                "auto_publish":  _ap.value,
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

            try:
                await api_put("/integrations/OUTLINE", json=payload)
                ui.notify("Outline configuration saved.", type="positive")
                _key.value = ""
            except Exception as exc:
                ui.notify(f"Save failed: {exc}", type="negative")

        ui.button("Save", icon="save", on_click=save_outline).props("color=primary")


# ---------------------------------------------------------------------------
# Dispatch table: system name -> panel builder
# ---------------------------------------------------------------------------

_PANEL_BUILDERS = {
    "REDMINE": _build_redmine_panel,
    "JIRA":    _build_jira_panel,
    "EMAIL":   _build_email_panel,
    "OUTLINE": _build_outline_panel,
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

    with ui.column().classes("q-pa-lg w-full"):
        ui.label("Integrations").classes("text-h4 q-mb-md")

        # ---- load all integrations -----------------------------------------
        try:
            raw_list: list[dict] = await api_get("/integrations")
        except Exception as exc:
            show_error_page(exc)
            return

        # Index by system_name for easy lookup; provide empty defaults if absent
        by_system: dict[str, dict] = {
            item["system_name"].upper(): item for item in raw_list
        }

        # ---- tabs ----------------------------------------------------------
        with ui.tabs().classes("w-full") as tabs:
            tab_refs: dict[str, ui.tab] = {}
            for sys in SYSTEMS:
                icon = SYSTEM_ICONS.get(sys, "settings")
                tab_refs[sys] = ui.tab(sys, label=sys, icon=icon)

        with ui.tab_panels(tabs, value=tab_refs[SYSTEMS[0]]).classes("w-full"):
            for sys in SYSTEMS:
                data = by_system.get(sys, {})
                with ui.tab_panel(tab_refs[sys]):
                    _PANEL_BUILDERS[sys](data)
