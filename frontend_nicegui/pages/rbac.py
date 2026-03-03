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
]

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

    with ui.column().classes("q-pa-lg w-full"):

        # ---- page header ---------------------------------------------------------
        with ui.row().classes("w-full items-center justify-between q-mb-md"):
            ui.label("RBAC Management").classes("text-h4")
            ui.label(
                "Configure which permissions each role grants across the application."
            ).classes("text-subtitle2 text-grey")

        # ---- access guard --------------------------------------------------------
        if role != "ADMIN":
            ui.separator()
            with ui.row().classes("items-center gap-2 q-mt-md"):
                ui.icon("lock", size="lg").classes("text-warning")
                ui.label(
                    "Access denied. ADMIN role is required to manage role permissions."
                ).classes("text-subtitle1 text-warning")
            return

        # ---- load current matrix from /configuration ----------------------------
        raw_matrix_value: str | None = None
        try:
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

        # ---- legend / role badges -----------------------------------------------
        with ui.row().classes("items-center gap-4 q-mb-md"):
            ui.label("Roles:").classes("text-caption text-grey")
            for r in _ROLES:
                colour = _ROLE_COLOURS.get(r, "grey")
                ui.badge(r, color=colour).classes("text-caption")

        # ---- matrix card --------------------------------------------------------
        is_dark = _safe_storage().get("dark_mode", True)
        header_bg = "bg-grey-10" if is_dark else "bg-grey-3"
        row_bg = "bg-grey-9" if is_dark else "bg-grey-2"

        with ui.card().classes("w-full q-pa-none"):

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

                    # Permission label
                    ui.label(label).style("min-width: 220px; flex: 1;").classes(
                        "text-body2"
                    )

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
            try:
                await api_put(
                    "/configuration/rbac_matrix",
                    json={"value": payload_value},
                )
                # Update the live matrix state
                for r in _ROLES:
                    matrix[r] = set(current_matrix[r])
                ui.notify("RBAC matrix saved successfully.", type="positive")
                status_label.set_text("Matrix saved.")
            except Exception as exc:
                ui.notify(f"Failed to save RBAC matrix: {exc}", type="negative")
                status_label.set_text(f"Save error: {exc}")

        async def reset_to_defaults() -> None:
            """Show a confirmation dialog then restore factory defaults."""
            with ui.dialog() as dialog, ui.card().classes("w-[420px] q-pa-md"):
                ui.label("Reset to Defaults?").classes("text-h6")
                ui.separator()
                ui.label(
                    "This will restore the built-in default permissions for every "
                    "role and save them to the server. Any custom changes will be "
                    "overwritten."
                ).classes("text-body2 text-grey q-mb-md")

                async def confirm_reset() -> None:
                    dialog.close()
                    default_matrix = {
                        r: list(perms) for r, perms in _DEFAULT_MATRIX.items()
                    }
                    # Apply defaults to checkboxes
                    for (perm_key, r), cb in checkbox_refs.items():
                        if r == "ADMIN":
                            continue  # always ticked, already disabled
                        cb.value = perm_key in default_matrix.get(r, [])
                    # Persist to server
                    payload_value = _matrix_to_json(default_matrix)
                    try:
                        await api_put(
                            "/configuration/rbac_matrix",
                            json={"value": payload_value},
                        )
                        for r in _ROLES:
                            matrix[r] = set(default_matrix[r])
                        ui.notify("RBAC matrix reset to defaults.", type="positive")
                        status_label.set_text("Reset to defaults.")
                    except Exception as exc:
                        ui.notify(
                            f"Failed to save default matrix: {exc}",
                            type="negative",
                        )
                        status_label.set_text(f"Reset error: {exc}")

                with ui.row().classes("w-full justify-end gap-2"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    ui.button(
                        "Reset to Defaults",
                        on_click=confirm_reset,
                    ).props("color=warning")

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

        # ---- action buttons row --------------------------------------------------
        with ui.row().classes("q-mt-lg gap-2 items-center"):
            ui.button("Save Changes", icon="save", on_click=save_matrix).props(
                "color=primary"
            )
            ui.button(
                "Reset to Defaults",
                icon="restart_alt",
                on_click=reset_to_defaults,
            ).props("flat color=warning")
            ui.button(
                "Reload from Server",
                icon="refresh",
                on_click=reload_from_server,
            ).props("flat")

        # ---- info note -----------------------------------------------------------
        with ui.row().classes("items-start gap-2 q-mt-md"):
            ui.icon("info", size="xs").classes("text-grey q-mt-xs")
            ui.label(
                "Note: ADMIN always has all permissions regardless of the checkboxes "
                "shown above. Changes saved here update the rbac_matrix configuration "
                "key used by the frontend for UI-level access hints. Backend endpoints "
                "enforce role checks independently via the RequireRole dependency."
            ).classes("text-caption text-grey")
