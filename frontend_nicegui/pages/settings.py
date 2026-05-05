"""Settings page — view and edit all configuration key-value pairs.

API used:
    GET  /configuration          -> list[{key, value, description}]
    PUT  /configuration/{key}    -> {key, value, description}  (ADMIN only)
"""

import asyncio
import json

from nicegui import ui
from frontend_nicegui.app import API_URL, _safe_storage, api_get, api_post, api_put, auth_headers, is_authenticated, show_error_page, sidebar

# ---------------------------------------------------------------------------
# Role mapping constants
# ---------------------------------------------------------------------------

_APP_ROLES: list[str] = ["ADMIN", "APPROVER", "ESTIMATOR", "VIEWER"]

# Config keys that should be rendered as role-mapping matrix tables
# instead of plain text inputs.
_ROLE_MAPPING_KEYS: set[str] = {"ldap_group_mapping_json", "oidc_role_mapping_json"}

# ---------------------------------------------------------------------------
# Section grouping
# ---------------------------------------------------------------------------

SECTION_KEYS: dict[str, list[str]] = {
    "Estimation Parameters": [
        "leader_effort_ratio",
        "new_feature_study_hours",
        "working_hours_per_day",
        "buffer_percentage",
        "pr_fix_base_hours",
        "estimation_number_prefix",
        "pr_priority_list",
        "pr_hours_simple",
        "pr_hours_medium",
        "pr_hours_complex",
        "pr_no_test_hours",
        "pr_no_test_task_template_id",
        "release_effort_factor",
        "release_effort_task_types",
    ],
    "Workflow Automation": [
        "outline_auto_export_states",
        "auto_create_historical_project",
    ],
    "Branding": [
        "logo_url",
        "logo_height",
    ],
    "Appearance": [
        "table_header_bg_light",
        "table_header_bg_dark",
        "sidebar_bg_light",
        "sidebar_bg_dark",
        "content_bg_light",
        "content_bg_dark",
        "button_color_light",
        "button_color_dark",
        "calendar_today_bg_light",
        "calendar_today_bg_dark",
        "calendar_weekend_bg_light",
        "calendar_weekend_bg_dark",
    ],
    "Data Management": [
        "dut_categories",
        "feature_categories",
        "project_types",
    ],
    "Email / SMTP": [],   # dynamic: keys starting with "smtp_"
    "LDAP": [],           # dynamic: keys starting with "ldap_"
    "OIDC": [],           # dynamic: keys starting with "oidc_"
    "Other": [],          # everything that does not match any prefix
}

_PREFIX_MAP: dict[str, str] = {
    "smtp_": "Email / SMTP",
    "ldap_": "LDAP",
    "oidc_": "OIDC",
}


def _classify(key: str) -> str:
    """Return the section name for a configuration key."""
    for section_name, keys in SECTION_KEYS.items():
        if key in keys:
            return section_name
    for prefix, section in _PREFIX_MAP.items():
        if key.startswith(prefix):
            return section
    return "Other"


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

@ui.page("/settings")
async def settings_page():
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    # ---- Load configuration before building UI ----------------------------------
    try:
        config_list: list[dict] = await api_get("/configuration")
    except Exception as exc:
        show_error_page(exc)
        return

    with ui.column().classes("w-full q-pa-md").style("gap: 0;"):

        # ── Sticky toolbar ──────────────────────────────────────
        with ui.element("div").classes("ed-toolbar"):
            ui.button("Save Changes", icon="save",
                      on_click=lambda: save_changes()) \
                .props("flat dense color=primary")
            ui.element("div").classes("ed-toolbar-spacer")
            ui.button("Reset Defaults", icon="restart_alt",
                      on_click=lambda: confirm_reset()) \
                .props("flat dense color=warning")
            ui.element("div").classes("ed-toolbar-grow")
            with ui.element("div").classes("ed-status-now"):
                ui.element("span").classes("ed-status-dot")
                ui.label(f"{len(config_list)} CONFIG KEYS").classes("ed-mono")

        with ui.element("div").classes("ed-shell"):

            ui.label("Settings").classes("text-h4 q-mb-md")
            ui.label(
                "Configure application behavior, branding, integrations, "
                "and authentication. Changes apply immediately after saving."
            ).classes("ed-eyebrow").style("margin-bottom: 22px;")

            if not config_list:
                ui.label("No configuration entries found").classes("ed-empty")
                return

        # ---- state ---------------------------------------------------------------
        # original_values: key -> str  (server-side values at page load)
        original_values: dict[str, str] = {item["key"]: item["value"] for item in config_list}

        # inputs: key -> ui.input reference
        inputs: dict[str, ui.input] = {}

        # ---- group into sections -------------------------------------------------
        sections: dict[str, list[dict]] = {s: [] for s in SECTION_KEYS}
        for item in config_list:
            section = _classify(item["key"])
            sections[section].append(item)

        # ---- collect role mapping config items ------------------------------------
        role_mapping_items: dict[str, dict] = {}
        for item in config_list:
            if item["key"] in _ROLE_MAPPING_KEYS:
                role_mapping_items[item["key"]] = item

        # ---- render sections -----------------------------------------------------
        for section_name, items in sections.items():
            # Filter out role-mapping keys — they get a dedicated matrix UI below
            filtered = [i for i in items if i["key"] not in _ROLE_MAPPING_KEYS]
            if not filtered:
                continue

            with ui.expansion(section_name, icon="settings").classes(
                "w-full q-mb-sm border rounded"
            ).props("default-opened"):
                with ui.column().classes("q-pa-sm w-full gap-2"):
                    for item in filtered:
                        key: str = item["key"]
                        value: str = item.get("value") or ""
                        description: str = item.get("description") or ""

                        # Use color picker for color config keys
                        is_color_key = any(p in key for p in ("_bg_", "_color_"))
                        with ui.column().classes("w-full"):
                            if is_color_key:
                                inp = ui.color_input(
                                    label=key,
                                    value=value,
                                ).classes("w-full")
                            else:
                                inp = ui.input(
                                    label=key,
                                    value=value,
                                ).classes("w-full")
                            if description:
                                ui.label(description).classes(
                                    "text-caption text-grey q-mt-none q-mb-xs"
                                )
                            # Logo upload button alongside the URL input
                            if key == "logo_url":
                                _logo_inp = inp  # capture for closure
                                _logo_preview = None
                                with ui.row().classes("items-center gap-2 q-mt-xs"):
                                    if value:
                                        _logo_preview = ui.image(value).classes("q-mr-sm").style(
                                            "max-height: 40px; max-width: 120px;"
                                        )

                                    def _make_logo_handler(logo_input=_logo_inp, logo_preview=_logo_preview):
                                        async def _handle_logo_upload(e) -> None:
                                            import httpx
                                            # NiceGUI 3.8+: e is UploadEventArguments with .file (FileUpload)
                                            # FileUpload has .name, async .read(), async .save()
                                            upload_file = getattr(e, "file", None) or e
                                            fname = upload_file.name if hasattr(upload_file, "name") else "logo.png"
                                            # Read content: NiceGUI 3.8 uses async read()
                                            if hasattr(upload_file, "read") and asyncio.iscoroutinefunction(upload_file.read):
                                                content = await upload_file.read()
                                            elif hasattr(upload_file, "content"):
                                                # Legacy NiceGUI: content is a SpooledTemporaryFile
                                                upload_file.content.seek(0)
                                                content = upload_file.content.read()
                                            else:
                                                ui.notify("Could not read upload file.", type="warning")
                                                return
                                            if not content:
                                                ui.notify("Upload file is empty.", type="warning")
                                                return
                                            try:
                                                async with httpx.AsyncClient() as client:
                                                    resp = await client.post(
                                                        f"{API_URL}/configuration/logo/upload",
                                                        headers=auth_headers(),
                                                        files={"file": (fname, content)},
                                                        timeout=15,
                                                    )
                                                resp.raise_for_status()
                                                result = resp.json()
                                                new_url = result.get("logo_url", "")
                                                if logo_input and new_url:
                                                    logo_input.value = new_url
                                                # Invalidate the sidebar/theme cache so the next render
                                                # picks up the freshly-saved logo URL.
                                                _safe_storage().pop("_rbac_cache", None)
                                                ui.notify(
                                                    "Logo uploaded and saved. Reloading page...",
                                                    type="positive",
                                                )
                                                ui.timer(1.5, lambda: ui.navigate.to("/settings"), once=True)
                                            except Exception as exc:
                                                ui.notify(
                                                    f"Logo upload failed: {exc}",
                                                    type="negative",
                                                )
                                        return _handle_logo_upload

                                    ui.upload(
                                        label="Upload Logo",
                                        auto_upload=True,
                                        max_files=1,
                                        on_upload=_make_logo_handler(),
                                    ).props('accept=".png,.jpg,.jpeg,.gif,.svg,.webp" flat dense').classes(
                                        "w-48"
                                    )
                        inputs[key] = inp

        # ---- role mapping matrix tables ------------------------------------------
        mapping_inputs: dict[str, dict[str, ui.input]] = {}  # config_key -> {role -> input}

        _MAPPING_META: dict[str, tuple[str, str, str]] = {
            "ldap_group_mapping_json": (
                "LDAP Group Mapping",
                "domain",
                "Map application roles to Active Directory / LDAP group DNs. "
                "Example: CN=EstimationAdmins,OU=Groups,DC=example,DC=com",
            ),
            "oidc_role_mapping_json": (
                "OIDC Role Mapping",
                "vpn_key",
                "Map application roles to OIDC claim values. "
                "Enter the value from the configured role claim (e.g. estimation-admin).",
            ),
        }

        for cfg_key, (title, icon, help_text) in _MAPPING_META.items():
            item = role_mapping_items.get(cfg_key)
            raw_value = (item.get("value") or "{}") if item else "{}"

            try:
                mapping = json.loads(raw_value) if raw_value else {}
                if not isinstance(mapping, dict):
                    mapping = {}
            except (json.JSONDecodeError, TypeError):
                mapping = {}

            mapping_inputs[cfg_key] = {}

            with ui.expansion(title, icon=icon).classes(
                "w-full q-mb-sm border rounded"
            ).props("default-opened" if any(mapping.values()) else ""):
                ui.label(help_text).classes("text-caption text-grey q-mb-sm")

                _is_dark = _safe_storage().get("dark_mode", True)
                _s_header_bg = "bg-grey-10" if _is_dark else "bg-grey-3"
                _s_row_bg = "bg-grey-9" if _is_dark else "bg-grey-2"

                with ui.card().classes("w-full q-pa-none"):
                    # Header row
                    with ui.row().classes(
                        f"w-full items-center q-px-md q-py-sm {_s_header_bg}"
                    ):
                        ui.label("Application Role").classes(
                            "text-subtitle2 text-bold"
                        ).style("min-width: 160px; width: 160px;")
                        ui.label("External Group / Claim Value").classes(
                            "text-subtitle2 text-bold"
                        ).style("flex: 1;")

                    ui.separator()

                    for idx, app_role in enumerate(_APP_ROLES):
                        row_bg = _s_row_bg if idx % 2 == 0 else ""
                        with ui.row().classes(
                            f"w-full items-center q-px-md q-py-xs {row_bg}"
                        ):
                            ui.label(app_role).classes("text-body2 text-bold").style(
                                "min-width: 160px; width: 160px;"
                            )
                            role_input = ui.input(
                                value=mapping.get(app_role, ""),
                                placeholder=f"Enter value for {app_role}",
                            ).classes("flex-grow")
                            mapping_inputs[cfg_key][app_role] = role_input

        # ---- action buttons ------------------------------------------------------
        status_label = ui.label("").classes("text-caption q-mt-sm")

        async def save_changes():
            """Iterate all inputs, PUT only those whose value has changed."""
            changed: list[str] = []
            errors: list[str] = []

            for key, inp in inputs.items():
                new_val = (inp.value or "").strip()
                if new_val == original_values.get(key, ""):
                    continue  # unchanged — skip
                try:
                    await api_put(f"/configuration/{key}", json={"value": new_val})
                    original_values[key] = new_val   # update baseline
                    changed.append(key)
                except Exception as exc:
                    errors.append(f"{key}: {exc}")

            # Save role mapping matrices
            for cfg_key, role_inputs in mapping_inputs.items():
                new_mapping = {}
                for role, inp in role_inputs.items():
                    val = (inp.value or "").strip()
                    if val:
                        new_mapping[role] = val
                new_json = json.dumps(new_mapping, separators=(",", ":"))
                old_json = original_values.get(cfg_key, "{}")
                if new_json != old_json:
                    try:
                        await api_put(f"/configuration/{cfg_key}", json={"value": new_json})
                        original_values[cfg_key] = new_json
                        changed.append(cfg_key)
                    except Exception as exc:
                        errors.append(f"{cfg_key}: {exc}")

            if errors:
                ui.notify(
                    f"Saved {len(changed)} key(s). {len(errors)} error(s): "
                    + "; ".join(errors),
                    type="warning",
                    timeout=6000,
                )
                status_label.set_text(
                    f"Partial save — {len(errors)} error(s). See notification."
                )
            elif changed:
                # Invalidate cached config so sidebar/theme picks up new values
                _safe_storage().pop("_rbac_cache", None)
                ui.notify(
                    f"Saved {len(changed)} configuration key(s). Reloading...",
                    type="positive",
                )
                status_label.set_text(f"Saved: {', '.join(changed)}")
                # Reload page so appearance/theme changes take effect immediately
                ui.timer(1.0, lambda: ui.navigate.to("/settings"), once=True)
            else:
                ui.notify("No changes detected.", type="info")
                status_label.set_text("No changes to save.")

        async def confirm_reset():
            """Show a confirmation dialog then reload from the API."""
            with ui.dialog() as dlg, ui.card().classes("q-pa-md"):
                ui.label("Reset to server values?").classes("text-h6")
                ui.label(
                    "This will discard any unsaved edits and reload all values "
                    "from the server."
                ).classes("text-body2 text-grey q-mb-md")
                with ui.row().classes("gap-2"):
                    ui.button(
                        "Cancel",
                        on_click=dlg.close,
                    ).props("flat")
                    async def do_reset():
                        dlg.close()
                        await reload_from_api()
                    ui.button(
                        "Reset",
                        on_click=do_reset,
                        color="warning",
                    )
            dlg.open()

        async def reload_from_api():
            """Fetch fresh values from the API and update all input widgets."""
            try:
                fresh: list[dict] = await api_get("/configuration")
            except Exception as exc:
                ui.notify(f"Reload failed: {exc}", type="negative")
                return
            for item in fresh:
                key = item["key"]
                val = item.get("value") or ""
                original_values[key] = val
                if key in inputs:
                    inputs[key].value = val
            status_label.set_text("Reloaded from server.")
            ui.notify("Configuration reloaded from server.", type="info")

        # ---- Connection test functions ──────────────────────────────────────
        async def test_smtp():
            ui.notify("Testing SMTP connection...", type="info", timeout=2000)
            try:
                result = await api_post("/integrations/EMAIL/test")
                if result.get("success"):
                    ui.notify(f"SMTP OK: {result.get('message', '')}",
                              type="positive", timeout=5000)
                else:
                    ui.notify(f"SMTP failed: {result.get('message', '')}",
                              type="warning", timeout=6000)
            except Exception as exc:
                ui.notify(f"SMTP test error: {exc}", type="negative")

        async def test_ldap():
            ui.notify("Testing LDAP connection...", type="info", timeout=2000)
            try:
                result = await api_post("/integrations/LDAP/test")
                if result.get("success"):
                    ui.notify(f"LDAP OK: {result.get('message', '')}",
                              type="positive", timeout=5000)
                else:
                    ui.notify(f"LDAP failed: {result.get('message', '')}",
                              type="warning", timeout=6000)
            except Exception as exc:
                ui.notify(f"LDAP test error: {exc}", type="negative")

        async def sync_ldap_users():
            ui.notify("Syncing LDAP users...", type="info", timeout=2000)
            try:
                result = await api_post("/auth/ldap/sync")
                synced = result.get("synced", 0)
                created = result.get("created", 0)
                updated = result.get("updated", 0)
                ui.notify(
                    f"LDAP sync complete: {synced} synced, "
                    f"{created} created, {updated} updated",
                    type="positive", timeout=5000,
                )
            except Exception as exc:
                ui.notify(f"LDAP sync error: {exc}", type="negative")

        # ---- Connection test card ──────────────────────────────────────────
        with ui.element("div").classes("ed-card").style("margin-top: 22px;"):
            with ui.element("div").classes("ed-card-head"):
                ui.label("Connection Tests").classes("ed-cap")
                ui.label("validate integration credentials").classes("ed-card-head-meta")
            with ui.row().classes("gap-2 flex-wrap"):
                ui.button("Test SMTP", icon="email",
                          on_click=test_smtp).props("flat color=secondary")
                ui.button("Test LDAP", icon="domain",
                          on_click=test_ldap).props("flat color=secondary")
                ui.button("Sync LDAP Users", icon="sync",
                          on_click=sync_ldap_users).props("flat color=accent")
