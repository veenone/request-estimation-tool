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

    # ── State ────────────────────────────────────────────────────
    all_rows: list[dict] = []
    state: dict = {"filter_priority": "All"}

    # Check if Jira integration is configured (do this before building UI so
    # we can show a clean info card instead of an empty table)
    jira_ok = False
    try:
        jira_config = await api_get("/integrations/JIRA")
        jira_ok = bool(jira_config.get("enabled"))
    except Exception:
        pass

    with ui.column().classes("w-full q-pa-md").style("gap: 0;"):

        # ── Sticky toolbar ──────────────────────────────────────
        with ui.element("div").classes("ed-toolbar"):
            if jira_ok:
                ui.button("Refresh", icon="refresh",
                          on_click=lambda: _refresh()) \
                    .props("flat dense color=secondary")
            ui.element("div").classes("ed-toolbar-grow")
            with ui.element("div").classes("ed-status-now"):
                ui.element("span").classes("ed-status-dot")
                _total_label = ui.label("TOTAL · 0").classes("ed-mono")

        with ui.element("div").classes("ed-shell"):

            ui.label("PR Registry").classes("text-h4 q-mb-md")
            ui.label(
                "Problem Reports fetched from Jira using the PR JQL filter "
                "configured in Settings > Integrations > JIRA."
            ).classes("ed-eyebrow").style("margin-bottom: 18px;")

            if not jira_ok:
                with ui.element("div").classes("ed-card") \
                        .style("border-color: var(--q-info);"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("info", color="info")
                        ui.label(
                            "Jira integration is not configured or not enabled. "
                            "Please configure it under Settings > Integrations > JIRA "
                            "and add a PR JQL Filter."
                        )
                return

            kpi_container = ui.element("div").classes("ed-strip")
            seg_container = ui.element("div").classes("ed-segmented")

            with ui.element("div").classes("ed-filter-row"):
                ui.label("Filter").classes("ed-filter-label")
                search_input = ui.input(
                    placeholder="Search by key or summary…"
                ).props('dense outlined clearable').style("min-width: 320px;")

            # ── KPI / segments / filter ────────────────────────
            def _count_by_pri(rows: list[dict], v: str) -> int:
                return sum(1 for r in rows if (r.get("priority") or "").upper() == v)

            def _set_pri(v: str) -> None:
                state["filter_priority"] = v
                _render_kpis()
                _render_segments()
                _filter_table()

            def _render_kpis() -> None:
                kpi_container.clear()
                with kpi_container:
                    rows = all_rows
                    _total_label.set_text(f"TOTAL · {len(rows)}")
                    open_n = sum(1 for r in rows
                                 if (r.get("status") or "").lower()
                                 not in ("done", "closed", "resolved"))
                    n_high = _count_by_pri(rows, "HIGH") + _count_by_pri(rows, "CRITICAL")
                    n_med = _count_by_pri(rows, "MEDIUM")
                    n_low = _count_by_pri(rows, "LOW")

                    def _tile(label: str, value: str, sub: str, key: str | None = None) -> None:
                        cls = "ed-strip-cell ed-stat-tile"
                        if key and state["filter_priority"] == key:
                            cls += " active"
                        el = ui.element("div").classes(cls)
                        if key is not None:
                            el.on("click", lambda _, k=key: _set_pri(k))
                        with el:
                            ui.label(label).classes("ed-eyebrow")
                            ui.label(value).classes("ed-strip-num")
                            if sub:
                                ui.label(sub).classes("ed-stat-tile-sub")

                    _tile("Total PRs", str(len(rows)),
                          f"{open_n} open" if rows else "click Refresh to load",
                          key="All")
                    if n_high:
                        _tile("High / Critical", str(n_high),
                              "filter to high priority", key="HIGH")
                    if n_med:
                        _tile("Medium", str(n_med),
                              "filter to medium", key="MEDIUM")
                    if n_low:
                        _tile("Low", str(n_low),
                              "filter to low", key="LOW")

            def _render_segments() -> None:
                seg_container.clear()
                with seg_container:
                    rows = all_rows

                    def _seg(label: str, key: str, count: int) -> None:
                        cls = "ed-segmented-item" + (
                            " active" if state["filter_priority"] == key else "")
                        btn = ui.element("button").classes(cls)
                        btn.on("click", lambda _, k=key: _set_pri(k))
                        with btn:
                            ui.label(label)
                            ui.label(f"· {count}").classes("seg-count")

                    _seg("All", "All", len(rows))
                    for v in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
                        n = _count_by_pri(rows, v)
                        if n or v == state["filter_priority"]:
                            _seg(v.title(), v, n)

            def _filter_table() -> None:
                query = (search_input.value or "").strip().lower()
                pri = state["filter_priority"]
                rows = list(all_rows)
                if pri == "HIGH":
                    rows = [r for r in rows
                            if (r.get("priority") or "").upper() in ("HIGH", "CRITICAL")]
                elif pri != "All":
                    rows = [r for r in rows if (r.get("priority") or "").upper() == pri]
                if query:
                    rows = [
                        r for r in rows
                        if query in (r.get("key", "") or "").lower()
                        or query in (r.get("summary", "") or "").lower()
                    ]
                table.rows = rows
                table.update()

            search_input.on("update:model-value", lambda _: _filter_table())

            # ── Table ──────────────────────────────────────────
            with ui.element("div").classes("ed-card"):
                table = ui.table(
                    columns=_COLUMNS,
                    rows=[],
                    row_key="key",
                    pagination={"rowsPerPage": 25},
                ).classes("w-full").props("flat")

                table.add_slot("body-cell-priority", r"""
                    <q-td :props="props">
                        <q-badge outline :color="
                            (props.value || '').toUpperCase() === 'CRITICAL' ||
                            (props.value || '').toUpperCase() === 'HIGH' ? 'negative' :
                            (props.value || '').toUpperCase() === 'MEDIUM' ? 'warning' :
                            'positive'
                        ">{{ props.value }}</q-badge>
                    </q-td>
                """)

            async def _refresh() -> None:
                nonlocal all_rows
                try:
                    items = await api_get("/integrations/JIRA/pr-items")
                    all_rows = items if isinstance(items, list) else []
                    _render_kpis()
                    _render_segments()
                    _filter_table()
                    ui.notify(f"Loaded {len(all_rows)} PR item(s).", type="positive")
                except Exception as exc:
                    ui.notify(f"Failed to load PR items: {exc}", type="negative")

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
                        ui.label(f"Created: {row.get('created', '')}").classes(
                            "text-body2 text-grey"
                        )
                    ui.button("Close", on_click=dlg.close).props("flat q-mt-md")
                dlg.open()

            table.on("rowClick", _show_detail)

            # Initial KPI / segments render with empty data
            _render_kpis()
            _render_segments()
