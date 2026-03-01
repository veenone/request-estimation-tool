"""Audit Log page — read-only view with filter controls.

Accessible to APPROVER and ADMIN roles (enforced server-side by the API).
The frontend shows an access-denied message for VIEWER/ESTIMATOR roles before
even calling the API, avoiding a misleading 403 error in the notification area.

Route: /audit
API:
  GET /audit-log?limit=50&offset=0&action=...&resource_type=...
"""

from nicegui import ui

from frontend_nicegui.app import (
    api_get,
    current_user,
    is_authenticated,
    sidebar,
)

_ALLOWED_ROLES = {"APPROVER", "ADMIN"}


@ui.page("/audit")
async def audit_page() -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    # ---------------------------------------------------------------------------
    # Role check — show informative message rather than a raw API 403
    # ---------------------------------------------------------------------------
    user = current_user()
    role = user.get("role", "VIEWER") if user else "VIEWER"

    with ui.column().classes("q-pa-lg w-full"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Audit Log").classes("text-h4")

        if role not in _ALLOWED_ROLES:
            ui.separator()
            with ui.row().classes("items-center gap-2 q-mt-md"):
                ui.icon("lock", size="lg").classes("text-warning")
                ui.label(
                    "Access restricted. APPROVER or ADMIN role required to view the audit log."
                ).classes("text-subtitle1 text-warning")
            return

        # ---------------------------------------------------------------------------
        # Filter bar
        # ---------------------------------------------------------------------------
        ui.label("Filters").classes("text-subtitle1 q-mt-sm")
        with ui.row().classes("w-full items-end gap-4 q-mb-md"):
            f_action = ui.input(
                "Action filter", placeholder="e.g. CREATE, DELETE"
            ).classes("flex-1")
            f_resource = ui.input(
                "Resource type filter", placeholder="e.g. user, estimation"
            ).classes("flex-1")
            f_limit = ui.number(
                "Limit", value=50, min=1, max=500, step=10, format="%.0f"
            ).classes("w-32")
            refresh_btn = ui.button("Refresh", icon="refresh").props("color=primary")

        ui.separator()

        # ---------------------------------------------------------------------------
        # Page-level state
        # ---------------------------------------------------------------------------
        logs: list[dict] = []
        table_container = ui.column().classes("w-full")

        # ---------------------------------------------------------------------------
        # Data helpers
        # ---------------------------------------------------------------------------
        async def load_logs() -> None:
            nonlocal logs
            params: dict = {"limit": int(f_limit.value or 50), "offset": 0}
            action_val = (f_action.value or "").strip()
            resource_val = (f_resource.value or "").strip()
            if action_val:
                params["action"] = action_val
            if resource_val:
                params["resource_type"] = resource_val
            try:
                data = await api_get("/audit-log", params=params)
                logs = data if isinstance(data, list) else []
            except Exception as exc:
                ui.notify(f"Failed to load audit log: {exc}", type="negative")
                logs = []

        def render_table() -> None:
            table_container.clear()
            with table_container:
                if not logs:
                    ui.label("No audit entries match the current filters.").classes(
                        "text-grey q-mt-md"
                    )
                    return

                columns = [
                    {"name": "id", "label": "ID", "field": "id", "sortable": True, "align": "left"},
                    {"name": "username", "label": "User", "field": "username", "sortable": True, "align": "left"},
                    {"name": "action", "label": "Action", "field": "action", "sortable": True, "align": "left"},
                    {"name": "resource_type", "label": "Resource Type", "field": "resource_type", "sortable": True, "align": "left"},
                    {"name": "resource_id", "label": "Res ID", "field": "resource_id", "sortable": True, "align": "right"},
                    {"name": "ip_address", "label": "IP Address", "field": "ip_address", "align": "left"},
                    {"name": "created_at", "label": "Timestamp", "field": "created_at", "sortable": True, "align": "left"},
                ]

                t = ui.table(
                    columns=columns,
                    rows=logs,
                    row_key="id",
                    pagination={"rowsPerPage": 25},
                ).classes("w-full")

                # Color-code action column
                t.add_slot(
                    "body-cell-action",
                    r"""
                    <q-td :props="props">
                        <q-badge
                            :color="props.value === 'DELETE' ? 'negative'
                                   : props.value === 'CREATE' ? 'positive'
                                   : props.value === 'UPDATE' ? 'warning'
                                   : 'grey'"
                            :label="props.value"
                        />
                    </q-td>
                    """,
                )

                # Truncate timestamps for readability
                t.add_slot(
                    "body-cell-created_at",
                    r"""
                    <q-td :props="props">
                        <span class="text-caption">
                            {{ props.value ? props.value.substring(0, 19).replace('T', ' ') : '—' }}
                        </span>
                    </q-td>
                    """,
                )

                # Show dash for null values in resource columns
                t.add_slot(
                    "body-cell-resource_id",
                    r"""
                    <q-td :props="props">
                        {{ props.value !== null && props.value !== undefined ? props.value : '—' }}
                    </q-td>
                    """,
                )

                t.add_slot(
                    "body-cell-ip_address",
                    r"""
                    <q-td :props="props">
                        <span class="text-caption text-grey">
                            {{ props.value || '—' }}
                        </span>
                    </q-td>
                    """,
                )

                ui.label(f"Showing {len(logs)} entries.").classes(
                    "text-caption text-grey q-mt-sm"
                )

        async def do_refresh() -> None:
            await load_logs()
            render_table()

        refresh_btn.on("click", lambda: do_refresh())

        # Initial load
        await load_logs()
        render_table()
