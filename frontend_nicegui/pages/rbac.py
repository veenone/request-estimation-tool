"""RBAC (Role-Based Access Control) Management page — ADMIN only.

Displays a permission matrix where rows are named permissions/actions and
columns are the four application roles (VIEWER, ESTIMATOR, APPROVER, ADMIN).
Each cell contains a checkbox.  The matrix is persisted as a JSON string
under the configuration key ``rbac_matrix`` via the existing /configuration
API endpoints.

Guards:
  - Must be authenticated (redirects to /login otherwise).
  - Must have role == ADMIN; shows "Access denied" for all other roles.

Route: /rbac
API:
  GET /configuration              -> list[{key, value, description}]
  PUT /configuration/rbac_matrix  -> {key, value, description}
"""

from __future__ import annotations

import json
from typing import Any

from nicegui import ui

from frontend_nicegui.app import (
    _safe_storage,
    api_get,
    api_put,
    current_user,
    is_authenticated,
    loading_state,
    run_async,
    show_error_page,
    sidebar,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ROLES: list[str] = ["VIEWER", "ESTIMATOR", "APPROVER", "ADMIN"]

# Display label -> internal permission key
_PERMISSIONS: list[tuple[str, str]] = [
    ("View Estimations",     "view_estimations"),
    ("Create Estimations",   "create_estimations"),
    ("Approve Estimations",  "approve_estimations"),
    ("Manage Users",         "manage_users"),
    ("View Reports",         "view_reports"),
    ("Download Reports",     "download_reports"),
    ("Manage Features",      "manage_features"),
    ("Manage DUTs",          "manage_duts"),
    ("Manage Profiles",      "manage_profiles"),
    ("Manage Team",          "manage_team"),
    ("Manage Integrations",  "manage_integrations"),
    ("Manage Settings",      "manage_settings"),
    ("View Audit Log",       "view_audit_log"),
    ("View Requests",        "view_requests"),
    ("Manage Requests",      "manage_requests"),
    ("LDAP Sync",            "ldap_sync"),
    ("Reinit Registries",    "reinit_registries"),
]

# Short human descriptions of what each permission grants (for row tooltips).
_PERMISSION_DESCRIPTIONS: dict[str, str] = {
    "view_estimations":   "View existing estimations.",
    "create_estimations": "Create and edit estimations.",
    "approve_estimations": "Approve or reject submitted estimations.",
    "manage_users":       "Create, edit and delete user accounts.",
    "view_reports":       "View generated reports.",
    "download_reports":   "Download reports as PDF / Word / Excel.",
    "manage_features":    "Add, edit and remove catalog features.",
    "manage_duts":        "Manage the DUT (device) registry.",
    "manage_profiles":    "Manage test configuration profiles.",
    "manage_team":        "Manage team members and assignments.",
    "manage_integrations": "Configure Redmine / JIRA / Outline integrations.",
    "manage_settings":    "Change global application settings.",
    "view_audit_log":     "View the security / audit log.",
    "view_requests":      "View incoming test requests.",
    "manage_requests":    "Triage and manage test requests.",
    "ldap_sync":          "Trigger LDAP user synchronization.",
    "reinit_registries":  "Re-initialize seed registries.",
}

# Sensible built-in defaults (used when no rbac_matrix key exists in the DB)
_DEFAULT_MATRIX: dict[str, list[str]] = {
    "VIEWER": [
        "view_estimations",
        "view_reports",
    ],
    "ESTIMATOR": [
        "view_estimations",
        "create_estimations",
        "view_reports",
        "download_reports",
        "manage_features",
        "manage_duts",
        "manage_profiles",
        "view_requests",
    ],
    "APPROVER": [
        "view_estimations",
        "create_estimations",
        "approve_estimations",
        "view_reports",
        "download_reports",
        "manage_features",
        "manage_duts",
        "manage_profiles",
        "view_audit_log",
        "view_requests",
        "manage_requests",
    ],
    "ADMIN": [p for _, p in _PERMISSIONS],   # every permission
}

# Role badge colours (Quasar/Tailwind colour names used in q-badge)
_ROLE_COLOURS: dict[str, str] = {
    "VIEWER":    "grey",
    "ESTIMATOR": "blue",
    "APPROVER":  "orange",
    "ADMIN":     "red",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_matrix(raw_value: str | None) -> dict[str, list[str]]:
    """Parse the rbac_matrix JSON string from the configuration table.

    Returns the default matrix on any parse failure or when the value is
    absent, so the page always has a sensible starting state.
    """
    if not raw_value:
        return {role: list(perms) for role, perms in _DEFAULT_MATRIX.items()}
    try:
        parsed = json.loads(raw_value)
        if not isinstance(parsed, dict):
            return {role: list(perms) for role, perms in _DEFAULT_MATRIX.items()}
        # Normalise: ensure every role key is present and contains a list
        result: dict[str, list[str]] = {}
        for role in _ROLES:
            role_perms = parsed.get(role, [])
            result[role] = role_perms if isinstance(role_perms, list) else []
        return result
    except (json.JSONDecodeError, TypeError):
        return {role: list(perms) for role, perms in _DEFAULT_MATRIX.items()}


def _matrix_to_json(matrix: dict[str, list[str]]) -> str:
    """Serialise the matrix dict to a compact JSON string for storage."""
    return json.dumps(matrix, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

@ui.page("/rbac")
async def rbac_page() -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    user = current_user()
    role = user.get("role", "VIEWER") if user else "VIEWER"

    with ui.column().classes("w-full q-pa-md").style("gap: 0;"):

        # ── Sticky toolbar ──────────────────────────────────────
        # Button refs captured here; click handlers wired through run_async
        # once the async action functions are defined further below.
        save_btn = reset_btn = reload_btn = None
        with ui.element("div").classes("ed-toolbar"):
            if role == "ADMIN":
                save_btn = ui.button("Save Changes", icon="save") \
                    .props("flat dense color=primary")
                ui.element("div").classes("ed-toolbar-spacer")
                reset_btn = ui.button("Reset Defaults", icon="restart_alt",
                          on_click=lambda: reset_to_defaults()) \
                    .props("flat dense color=warning")
                ui.element("div").classes("ed-toolbar-spacer")
                reload_btn = ui.button("Reload", icon="refresh") \
                    .props("flat dense")
            ui.element("div").classes("ed-toolbar-grow")
            with ui.element("div").classes("ed-status-now"):
                ui.element("span").classes("ed-status-dot")
                ui.label("ADMIN ONLY").classes("ed-mono")

        with ui.element("div").classes("ed-shell"):

            ui.label("RBAC Management").classes("text-h4 q-mb-md")
            ui.label(
                "Configure which permissions each role grants across the application."
            ).classes("ed-eyebrow").style("margin-bottom: 14px;")

            # ---- prominent note (read before editing) --------------------------
            with ui.element("div").classes("ed-card") \
                    .style("border-color: var(--q-info); margin-bottom: 18px;"):
                with ui.row().classes("items-start gap-2"):
                    ui.icon("info", size="sm").classes("text-info q-mt-xs")
                    ui.label(
                        "ADMIN always has all permissions regardless of the "
                        "checkboxes below. Changes saved here update the "
                        "rbac_matrix configuration key used by the frontend for "
                        "UI-level access hints — backend endpoints enforce role "
                        "checks independently via the RequireRole dependency."
                    ).classes("text-caption")

            # ---- access guard --------------------------------------------------
            if role != "ADMIN":
                with ui.element("div").classes("ed-card") \
                        .style("border-color: var(--q-warning);"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("lock", size="lg").classes("text-warning")
                        ui.label(
                            "Access denied. ADMIN role is required to manage role permissions."
                        ).classes("text-subtitle1 text-warning")
                return

        # ---- load current matrix from /configuration ----------------------------
        raw_matrix_value: str | None = None
        try:
            async with loading_state("Loading permissions…"):
                config_list: list[dict[str, Any]] = await api_get("/configuration")
            for item in config_list:
                if item.get("key") == "rbac_matrix":
                    raw_matrix_value = item.get("value")
                    break
        except Exception as exc:
            show_error_page(exc)
            return

        # Active matrix state — dict[role -> set of permission keys]
        # Using a dict of sets internally; converted to list[str] for JSON.
        matrix: dict[str, set[str]] = {
            role_name: set(perms)
            for role_name, perms in _parse_matrix(raw_matrix_value).items()
        }

        # checkbox widget registry: (permission_key, role) -> ui.checkbox
        checkbox_refs: dict[tuple[str, str], ui.checkbox] = {}

        # ---- KPI strip showing permission summary per role ----------------
        with ui.element("div").classes("ed-strip"):
            for r in _ROLES:
                with ui.element("div").classes("ed-strip-cell"):
                    ui.label(r).classes("ed-eyebrow")
                    ui.label(str(len(matrix.get(r, set())))).classes("ed-strip-num")
                    total = len(_PERMISSIONS)
                    ui.label(f"of {total} permissions").classes("ed-stat-tile-sub")

        # ---- legend / role badges -----------------------------------------------
        with ui.row().classes("items-center gap-4 q-mt-md q-mb-md"):
            ui.label("Roles:").classes("ed-eyebrow")
            for r in _ROLES:
                colour = _ROLE_COLOURS.get(r, "grey")
                ui.badge(r, color=colour).classes("text-caption")

        # ---- matrix card --------------------------------------------------------
        is_dark = _safe_storage().get("dark_mode", True)
        header_bg = "bg-grey-10" if is_dark else "bg-grey-3"
        row_bg = "bg-grey-9" if is_dark else "bg-grey-2"

        with ui.element("div").classes("ed-card").style("padding: 0;"):

            # Column header row
            with ui.row().classes(
                f"w-full items-center q-px-md q-py-sm {header_bg}"
            ):
                # Permission label column — fixed width
                ui.label("Permission").classes(
                    "text-subtitle2 text-bold"
                ).style("min-width: 220px; flex: 1;")

                for r in _ROLES:
                    colour = _ROLE_COLOURS.get(r, "grey")
                    with ui.column().classes("items-center").style("min-width: 110px;"):
                        ui.badge(r, color=colour).classes("text-subtitle2")

            ui.separator()

            # Permission rows
            for idx, (label, perm_key) in enumerate(_PERMISSIONS):
                row_class = (
                    "w-full items-center q-px-md q-py-xs "
                    + (row_bg if idx % 2 == 0 else "")
                )
                with ui.row().classes(row_class):

                    # Permission label (with a help tooltip describing the grant)
                    perm_desc = _PERMISSION_DESCRIPTIONS.get(
                        perm_key, f"Controls the '{label}' capability."
                    )
                    ui.label(label).style("min-width: 220px; flex: 1;").classes(
                        "text-body2"
                    ).tooltip(perm_desc)

                    # One checkbox per role
                    for r in _ROLES:
                        is_checked = perm_key in matrix[r]

                        with ui.column().classes("items-center").style(
                            "min-width: 110px;"
                        ):
                            cb = ui.checkbox(
                                value=is_checked,
                                # ADMIN always has every permission — lock it
                                # so the matrix cannot accidentally omit ADMIN
                                # permissions, which would be misleading
                                # (the backend enforces ADMIN = superuser anyway).
                            )
                            # a11y: announce both the permission and the role.
                            cb.props(f'aria-label="{label} for {r}"')
                            if r == "ADMIN":
                                cb.props("disable")
                                cb.value = True  # always ticked

                            checkbox_refs[(perm_key, r)] = cb

            ui.separator()

        # ---- status label (updated after save / reset) ---------------------------
        status_label = ui.label("").classes("text-caption text-grey q-mt-xs")

        # ---- action helpers ------------------------------------------------------

        def _collect_matrix() -> dict[str, list[str]]:
            """Read all checkbox states and build the current matrix dict."""
            result: dict[str, list[str]] = {r: [] for r in _ROLES}
            for (perm_key, r), cb in checkbox_refs.items():
                if cb.value:
                    result[r].append(perm_key)
            # ADMIN always gets everything, regardless of checkbox state
            result["ADMIN"] = [p for _, p in _PERMISSIONS]
            return result

        async def save_matrix() -> None:
            """Persist the current checkbox state to the backend."""
            current_matrix = _collect_matrix()
            payload_value = _matrix_to_json(current_matrix)
            await api_put(
                "/configuration/rbac_matrix",
                json={"value": payload_value},
            )
            # Update the live matrix state
            for r in _ROLES:
                matrix[r] = set(current_matrix[r])
            status_label.set_text("Matrix saved.")

        async def reset_to_defaults() -> None:
            """Show a confirmation dialog then restore factory defaults."""
            with ui.dialog() as dialog, ui.card().classes("w-[440px] q-pa-md"):
                ui.label("Reset to Defaults?").classes("text-h6")
                ui.separator()
                ui.label(
                    "This will overwrite ALL custom permissions for every role "
                    "with the built-in defaults and save them to the server. "
                    "ADMIN always retains all permissions. This cannot be undone."
                ).classes("text-body2 text-grey q-mb-md")

                ack_cb = ui.checkbox(
                    "I understand this overwrites all custom permissions"
                ).classes("q-mb-sm")

                default_matrix = {
                    r: list(perms) for r, perms in _DEFAULT_MATRIX.items()
                }

                async def _do_reset():
                    payload_value = _matrix_to_json(default_matrix)
                    await api_put(
                        "/configuration/rbac_matrix",
                        json={"value": payload_value},
                    )
                    # Apply defaults to checkboxes + live state
                    for (perm_key, r), cb in checkbox_refs.items():
                        if r == "ADMIN":
                            continue  # always ticked, already disabled
                        cb.value = perm_key in default_matrix.get(r, [])
                    for r in _ROLES:
                        matrix[r] = set(default_matrix[r])
                    status_label.set_text("Reset to defaults.")

                async def _on_reset(_):
                    dialog.close()

                with ui.row().classes("w-full justify-end gap-2"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    confirm_btn = ui.button("Reset to Defaults").props("color=warning")
                    confirm_btn.on_click(run_async(
                        confirm_btn,
                        _do_reset,
                        success="RBAC matrix reset to defaults.",
                        on_success=_on_reset,
                        error_prefix="Failed to save default matrix",
                    ))

                def _gate() -> None:
                    confirm_btn.set_enabled(bool(ack_cb.value))

                _gate()
                ack_cb.on_value_change(lambda _: _gate())

            dialog.open()

        async def reload_from_server() -> None:
            """Fetch the current matrix from the server and refresh checkboxes."""
            try:
                fresh_config: list[dict[str, Any]] = await api_get("/configuration")
            except Exception as exc:
                ui.notify(f"Reload failed: {exc}", type="negative")
                return

            fresh_value: str | None = None
            for item in fresh_config:
                if item.get("key") == "rbac_matrix":
                    fresh_value = item.get("value")
                    break

            fresh_matrix = _parse_matrix(fresh_value)
            for (perm_key, r), cb in checkbox_refs.items():
                if r == "ADMIN":
                    continue
                cb.value = perm_key in fresh_matrix.get(r, [])
            for r in _ROLES:
                matrix[r] = set(fresh_matrix.get(r, []))

            ui.notify("RBAC matrix reloaded from server.", type="info")
            status_label.set_text("Reloaded from server.")

        # ---- wire toolbar buttons through run_async (defined above) --------------
        # (The prominent ADMIN-permissions note now lives at the TOP of the page.)
        if save_btn is not None:
            save_btn.on_click(run_async(
                save_btn,
                save_matrix,
                success="RBAC matrix saved successfully.",
                error_prefix="Failed to save RBAC matrix",
            ))
        if reload_btn is not None:
            reload_btn.on_click(run_async(
                reload_btn,
                reload_from_server,
                error_prefix="Reload failed",
            ))

        status_label  # silence linter — defined above and referenced inside actions
