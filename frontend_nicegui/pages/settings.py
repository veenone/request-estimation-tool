"""Settings page — view and edit all configuration key-value pairs.

API used:
    GET  /configuration          -> list[{key, value, description}]
    PUT  /configuration/{key}    -> {key, value, description}  (ADMIN only)
"""

from nicegui import ui
from frontend_nicegui.app import api_get, api_post, api_put, is_authenticated, sidebar

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
    for k in SECTION_KEYS["Estimation Parameters"]:
        if key == k:
            return "Estimation Parameters"
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

    with ui.column().classes("q-pa-lg w-full"):
        ui.label("Settings").classes("text-h4 q-mb-md")

        # ---- load ----------------------------------------------------------------
        try:
            config_list: list[dict] = await api_get("/configuration")
        except Exception as exc:
            ui.label(f"Error loading configuration: {exc}").classes("text-negative")
            return

        if not config_list:
            ui.label("No configuration entries found.").classes("text-grey")
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

        # ---- render sections -----------------------------------------------------
        for section_name, items in sections.items():
            if not items:
                continue

            with ui.expansion(section_name, icon="settings").classes(
                "w-full q-mb-sm border rounded"
            ).props("default-opened"):
                with ui.column().classes("q-pa-sm w-full gap-2"):
                    for item in items:
                        key: str = item["key"]
                        value: str = item.get("value") or ""
                        description: str = item.get("description") or ""

                        with ui.column().classes("w-full"):
                            inp = ui.input(
                                label=key,
                                value=value,
                            ).classes("w-full")
                            if description:
                                ui.label(description).classes(
                                    "text-caption text-grey q-mt-none q-mb-xs"
                                )
                        inputs[key] = inp

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
                ui.notify(
                    f"Saved {len(changed)} configuration key(s).",
                    type="positive",
                )
                status_label.set_text(f"Saved: {', '.join(changed)}")
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

        with ui.row().classes("q-mt-lg gap-2"):
            ui.button("Save Changes", icon="save", on_click=save_changes).props(
                "color=primary"
            )
            ui.button(
                "Reset to Defaults",
                icon="restart_alt",
                on_click=confirm_reset,
            ).props("flat color=warning")

        # ---- Connection test buttons -----------------------------------------
        ui.separator().classes("q-my-md")
        ui.label("Connection Tests").classes("text-h6")

        with ui.row().classes("gap-2 q-mt-sm flex-wrap"):

            async def test_smtp():
                ui.notify("Testing SMTP connection...", type="info", timeout=2000)
                try:
                    result = await api_post("/integrations/EMAIL/test")
                    if result.get("success"):
                        ui.notify(
                            f"SMTP OK: {result.get('message', '')}",
                            type="positive", timeout=5000,
                        )
                    else:
                        ui.notify(
                            f"SMTP failed: {result.get('message', '')}",
                            type="warning", timeout=6000,
                        )
                except Exception as exc:
                    ui.notify(f"SMTP test error: {exc}", type="negative")

            ui.button(
                "Test SMTP", icon="email", on_click=test_smtp,
            ).props("flat color=secondary")

            async def test_ldap():
                ui.notify("Testing LDAP connection...", type="info", timeout=2000)
                try:
                    result = await api_post("/integrations/LDAP/test")
                    if result.get("success"):
                        ui.notify(
                            f"LDAP OK: {result.get('message', '')}",
                            type="positive", timeout=5000,
                        )
                    else:
                        ui.notify(
                            f"LDAP failed: {result.get('message', '')}",
                            type="warning", timeout=6000,
                        )
                except Exception as exc:
                    ui.notify(f"LDAP test error: {exc}", type="negative")

            ui.button(
                "Test LDAP", icon="domain", on_click=test_ldap,
            ).props("flat color=secondary")

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

            ui.button(
                "Sync LDAP Users", icon="sync", on_click=sync_ldap_users,
            ).props("flat color=accent")
