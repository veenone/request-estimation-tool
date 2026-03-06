"""PR Registry page — view and browse Problem Reports from Jira.

Route: /pr-registry
API:
  GET  /integrations/JIRA/pr-items
  GET  /integrations/JIRA
"""

from nicegui import ui
from frontend_nicegui.app import api_get, is_authenticated, sidebar


_COLUMNS = [
    {"name": "key",        "label": "Key",       "field": "key",        "align": "left", "sortable": True},
    {"name": "summary",    "label": "Summary",   "field": "summary",    "align": "left", "sortable": True},
    {"name": "priority",   "label": "Priority",  "field": "priority",   "align": "left", "sortable": True},
    {"name": "status",     "label": "Status",    "field": "status",     "align": "left", "sortable": True},
    {"name": "issue_type", "label": "Type",       "field": "issue_type", "align": "left", "sortable": True},
    {"name": "created",    "label": "Created",   "field": "created",    "align": "left", "sortable": True},
]


@ui.page("/pr-registry")
async def pr_registry_page() -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    with ui.column().classes("q-pa-lg w-full"):
        ui.label("PR Registry").classes("text-h4 q-mb-md")
        ui.label(
            "Problem Reports fetched from Jira using the PR JQL filter configured in Settings > Integrations > JIRA."
        ).classes("text-body2 text-grey q-mb-md")

        # Check if Jira integration is configured
        jira_ok = False
        try:
            jira_config = await api_get("/integrations/JIRA")
            jira_ok = bool(jira_config.get("enabled"))
        except Exception:
            pass

        if not jira_ok:
            with ui.card().classes("w-full q-pa-md bg-blue-1"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("info", color="info")
                    ui.label(
                        "Jira integration is not configured or not enabled. "
                        "Please configure it under Settings > Integrations > JIRA and add a PR JQL Filter."
                    )
            return

        table = ui.table(
            columns=_COLUMNS,
            rows=[],
            row_key="key",
            pagination={"rowsPerPage": 25},
        ).classes("w-full shadow-1")

        # Add search/filter
        search_input = ui.input(label="Search", placeholder="Filter by key or summary...").classes("w-64 q-mb-sm")

        def _filter_table() -> None:
            query = (search_input.value or "").strip().lower()
            if not query:
                table.rows = list(all_rows)
            else:
                table.rows = [
                    r for r in all_rows
                    if query in (r.get("key", "") or "").lower()
                    or query in (r.get("summary", "") or "").lower()
                ]
            table.update()

        search_input.on("update:model-value", lambda _: _filter_table())

        all_rows: list[dict] = []

        async def _refresh() -> None:
            nonlocal all_rows
            try:
                items = await api_get("/integrations/JIRA/pr-items")
                all_rows = items if isinstance(items, list) else []
                table.rows = list(all_rows)
                table.update()
                ui.notify(f"Loaded {len(all_rows)} PR item(s).", type="positive")
            except Exception as exc:
                ui.notify(f"Failed to load PR items: {exc}", type="negative")

        ui.button("Refresh", icon="refresh", on_click=_refresh).props("color=secondary")

        # Detail dialog on row click
        async def _show_detail(e) -> None:
            row = e.args[1] if isinstance(e.args, list) and len(e.args) > 1 else {}
            if not row:
                return
            with ui.dialog() as dlg, ui.card().classes("w-[600px]"):
                ui.label(f"PR Detail: {row.get('key', '')}").classes("text-h6 q-mb-sm")
                with ui.column().classes("gap-1"):
                    ui.label(f"Summary: {row.get('summary', '')}").classes("text-body1")
                    ui.label(f"Priority: {row.get('priority', '')}").classes("text-body2")
                    ui.label(f"Status: {row.get('status', '')}").classes("text-body2")
                    ui.label(f"Type: {row.get('issue_type', '')}").classes("text-body2")
                    ui.label(f"Created: {row.get('created', '')}").classes("text-body2 text-grey")
                ui.button("Close", on_click=dlg.close).props("flat q-mt-md")
            dlg.open()

        table.on("rowClick", _show_detail)

        # Initial load
        await _refresh()
