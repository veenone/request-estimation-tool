"""Historical Projects page — read-only list with add-only CRUD.

The API supports GET and POST for /historical-projects but no edit or delete,
so this page provides a table view plus an Add dialog.

Route: /history
"""

from nicegui import ui

from frontend_nicegui.app import (
    api_get,
    api_post,
    current_user,
    empty_state,
    format_age,
    format_datetime,
    is_authenticated,
    loading_state,
    run_async,
    sidebar,
)


def _compute_accuracy(row: dict) -> str:
    """Return accuracy_ratio as a formatted string, handling divide-by-zero."""
    estimated = row.get("estimated_hours") or 0
    actual = row.get("actual_hours") or 0
    if estimated == 0:
        return "N/A"
    ratio = actual / estimated
    return f"{ratio:.2f}"


@ui.page("/history")
async def history_page() -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    # ---------------------------------------------------------------------------
    # Page-level state
    # ---------------------------------------------------------------------------
    projects: list[dict] = []
    table_ref: ui.table | None = None

    # ---------------------------------------------------------------------------
    # Data helpers
    # ---------------------------------------------------------------------------
    async def load_projects() -> None:
        nonlocal projects
        try:
            data = await api_get("/historical-projects")
            projects = data if isinstance(data, list) else []
            # Inject computed accuracy_ratio into each row for the table
            for row in projects:
                row["accuracy_ratio"] = _compute_accuracy(row)
                iso = row.get("completion_date") or ""
                row["completion_date_age"] = format_age(iso) if iso else "—"
                row["completion_date_full"] = format_datetime(iso) if iso else ""
        except Exception as exc:
            ui.notify(f"Failed to load projects: {exc}", type="negative")
            projects = []

    # ---------------------------------------------------------------------------
    # Add-project dialog
    # ---------------------------------------------------------------------------
    async def open_add_dialog() -> None:
        with ui.dialog() as dialog, ui.card().classes("w-[520px]"):
            ui.label("Add Historical Project").classes("text-h6")
            ui.separator()

            f_name = ui.input("Project Name *").classes("w-full").props("autofocus")
            f_type = ui.select(
                label="Project Type *",
                options=["NEW", "EVOLUTION", "SUPPORT"],
                value="EVOLUTION",
            ).classes("w-full")
            with ui.row().classes("w-full gap-4"):
                f_estimated = ui.number(
                    "Estimated Hours", value=None, min=0
                ).classes("flex-1")
                f_actual = ui.number(
                    "Actual Hours", value=None, min=0
                ).classes("flex-1")
            with ui.row().classes("w-full gap-4"):
                f_dut = ui.number(
                    "DUT Count", value=None, min=0, step=1, format="%.0f"
                ).classes("flex-1")
                f_profile = ui.number(
                    "Profile Count", value=None, min=0, step=1, format="%.0f"
                ).classes("flex-1")
                f_pr = ui.number(
                    "PR Count", value=None, min=0, step=1, format="%.0f"
                ).classes("flex-1")
            f_date = ui.input(
                "Completion Date (YYYY-MM-DD)"
            ).classes("w-full")
            f_features = ui.textarea(
                "Features JSON", value="[]"
            ).classes("w-full")
            f_notes = ui.textarea("Notes").classes("w-full")

            async def submit() -> None:
                payload: dict = {
                    "project_name": f_name.value.strip(),
                    "project_type": f_type.value,
                    "estimated_hours": f_estimated.value,
                    "actual_hours": f_actual.value,
                    "dut_count": int(f_dut.value) if f_dut.value is not None else None,
                    "profile_count": int(f_profile.value) if f_profile.value is not None else None,
                    "pr_count": int(f_pr.value) if f_pr.value is not None else None,
                    "completion_date": f_date.value.strip() if f_date.value else None,
                    "features_json": f_features.value or "[]",
                    "notes": f_notes.value or None,
                }
                await api_post("/historical-projects", json=payload)
                dialog.close()
                await refresh_table()

            with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                add_btn = ui.button("Add Project").props("color=primary")

                def _guarded_submit(*_):
                    if not f_name.value or not f_name.value.strip():
                        ui.notify("Project Name is required.", type="warning")
                        return
                    return run_async(
                        add_btn, submit,
                        success="Project added successfully.",
                        error_prefix="Error adding project",
                    )()

                add_btn.on("click", _guarded_submit)

        dialog.open()

    # ---------------------------------------------------------------------------
    # Table refresh
    # ---------------------------------------------------------------------------
    async def refresh_table() -> None:
        await load_projects()
        _total_label.set_text(f"TOTAL · {len(projects)}")
        _render_kpis()
        _render_segments()
        _apply_filters()

    # ---------------------------------------------------------------------------
    # State
    # ---------------------------------------------------------------------------
    state: dict = {"filter_type": "All"}
    user = current_user()
    role = user.get("role", "VIEWER") if user else "VIEWER"
    can_add = role in ("APPROVER", "ADMIN")

    # Load data first
    async with loading_state("Loading projects…"):
        await load_projects()

    # ---------------------------------------------------------------------------
    # Page layout
    # ---------------------------------------------------------------------------
    with ui.column().classes("w-full q-pa-md").style("gap: 0;"):

        # ── Sticky toolbar ──────────────────────────────────────
        with ui.element("div").classes("ed-toolbar"):
            if can_add:
                ui.button("Add Project", icon="add",
                          on_click=lambda: open_add_dialog()) \
                    .props("flat dense color=primary")
                ui.element("div").classes("ed-toolbar-spacer")
            ui.button("Refresh", icon="refresh",
                      on_click=lambda: refresh_table()) \
                .props("flat dense")
            ui.element("div").classes("ed-toolbar-grow")
            with ui.element("div").classes("ed-status-now"):
                ui.element("span").classes("ed-status-dot")
                _total_label = ui.label(f"TOTAL · {len(projects)}").classes("ed-mono")

        with ui.element("div").classes("ed-shell"):

            ui.label("Historical Projects").classes("text-h4 q-mb-md")

            kpi_container = ui.element("div").classes("ed-strip")
            seg_container = ui.element("div").classes("ed-segmented")

            # ── KPI / segment / refresh helpers ────────────────
            _PROJECT_TYPES = ["NEW", "EVOLUTION", "SUPPORT"]

            def _count_by_type(rows: list[dict], t: str) -> int:
                return sum(1 for r in rows if (r.get("project_type") or "") == t)

            def _avg_accuracy(rows: list[dict]) -> float:
                vals = []
                for r in rows:
                    a = r.get("accuracy_ratio")
                    if a and a != "N/A":
                        try:
                            vals.append(float(a))
                        except (ValueError, TypeError):
                            pass
                return sum(vals) / len(vals) if vals else 0.0

            def _set_type(t: str) -> None:
                state["filter_type"] = t
                _render_kpis()
                _render_segments()
                _apply_filters()

            def _render_kpis() -> None:
                kpi_container.clear()
                with kpi_container:
                    avg_acc = _avg_accuracy(projects)
                    over_n = sum(1 for r in projects
                                 if r.get("accuracy_ratio") and r["accuracy_ratio"] != "N/A"
                                 and float(r["accuracy_ratio"]) > 1.3)
                    total_h = sum((r.get("actual_hours") or 0) for r in projects)

                    def _tile(label: str, value: str, sub: str, key: str | None = None) -> None:
                        cls = "ed-strip-cell ed-stat-tile"
                        if key and state["filter_type"] == key:
                            cls += " active"
                        el = ui.element("div").classes(cls)
                        if key is not None:
                            el.on("click", lambda _, k=key: _set_type(k))
                        with el:
                            ui.label(label).classes("ed-eyebrow")
                            ui.label(value).classes("ed-strip-num")
                            if sub:
                                ui.label(sub).classes("ed-stat-tile-sub")

                    _tile("Total Projects", str(len(projects)),
                          f"{total_h:,.0f}h actual", key="All")
                    _tile("Avg Accuracy",
                          f"{avg_acc:.2f}×" if avg_acc else "—",
                          f"{over_n} over 1.3× ratio", key=None)
                    for t in _PROJECT_TYPES:
                        n = _count_by_type(projects, t)
                        if n:
                            _tile(t.title(), str(n), "filter to type", key=t)

            def _render_segments() -> None:
                seg_container.clear()
                with seg_container:
                    def _seg(label: str, key: str, count: int) -> None:
                        cls = "ed-segmented-item" + (
                            " active" if state["filter_type"] == key else "")
                        btn = ui.element("button").classes(cls)
                        btn.on("click", lambda _, k=key: _set_type(k))
                        with btn:
                            ui.label(label)
                            ui.label(f"· {count}").classes("seg-count")
                    _seg("All", "All", len(projects))
                    for t in _PROJECT_TYPES:
                        n = _count_by_type(projects, t)
                        if n or t == state["filter_type"]:
                            _seg(t.title(), t, n)

            def _apply_filters() -> None:
                rows = list(projects)
                if state["filter_type"] != "All":
                    rows = [r for r in rows if (r.get("project_type") or "") == state["filter_type"]]
                if table_ref is not None:
                    table_ref.rows = rows
                    table_ref.update()

            # ── Table ──────────────────────────────────────────
            with ui.element("div").classes("ed-card"):
                if not projects:
                    empty_state("No historical projects yet")
                else:
                    columns = [
                        {"name": "project_name", "label": "Project Name", "field": "project_name", "sortable": True, "align": "left"},
                        {"name": "project_type", "label": "Type", "field": "project_type", "sortable": True, "align": "left"},
                        {"name": "estimated_hours", "label": "Estimated h", "field": "estimated_hours", "sortable": True, "align": "right"},
                        {"name": "actual_hours", "label": "Actual h", "field": "actual_hours", "sortable": True, "align": "right"},
                        {"name": "accuracy_ratio", "label": "Accuracy Ratio", "field": "accuracy_ratio", "sortable": True, "align": "right"},
                        {"name": "completion_date", "label": "Completion Date", "field": "completion_date_age", "sortable": True, "align": "left"},
                    ]
                    table_ref = ui.table(
                        columns=columns,
                        rows=projects,
                        row_key="id",
                        pagination={"rowsPerPage": 25},
                    ).classes("w-full").props("flat")
                    table_ref.add_slot(
                        "body-cell-completion_date",
                        r"""
                        <q-td :props="props">
                            <span>{{ props.value }}</span>
                            <q-tooltip v-if="props.row.completion_date_full">
                                {{ props.row.completion_date_full }}
                            </q-tooltip>
                        </q-td>
                        """,
                    )
                    table_ref.add_slot(
                        "body-cell-accuracy_ratio",
                        r"""
                        <q-td :props="props">
                            <span
                                :class="props.value !== 'N/A' && parseFloat(props.value) > 1.3
                                    ? 'text-negative'
                                    : 'text-positive'"
                            >{{ props.value }}</span>
                        </q-td>
                        """,
                    )

            # Initial KPI/segment render
            _render_kpis()
            _render_segments()
