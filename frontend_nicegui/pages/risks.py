"""Risk Registry page — full CRUD with likelihood/impact filters.

Route: /risks
API:
  GET    /risk-items
  POST   /risk-items
  PUT    /risk-items/{id}
  DELETE /risk-items/{id}
"""

from nicegui import ui
from frontend_nicegui.app import (
    api_delete,
    api_get,
    api_post,
    api_put,
    is_authenticated,
    sidebar,
)

LIKELIHOOD_OPTIONS = ["LOW", "MEDIUM", "HIGH"]
IMPACT_OPTIONS = ["LOW", "MEDIUM", "HIGH"]

_COLUMNS = [
    {"name": "id",         "label": "ID",         "field": "id",         "align": "left", "sortable": True},
    {"name": "name",       "label": "Name",       "field": "name",       "align": "left", "sortable": True},
    {"name": "category",   "label": "Category",   "field": "category",   "align": "left", "sortable": True},
    {"name": "likelihood", "label": "Likelihood", "field": "likelihood", "align": "left", "sortable": True},
    {"name": "impact",     "label": "Impact",     "field": "impact",     "align": "left", "sortable": True},
    {"name": "actions",    "label": "Actions",    "field": "actions",    "align": "left"},
]


@ui.page("/risks")
async def risks_page() -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    # ── State ────────────────────────────────────────────────────
    state: dict = {"rows": [], "filter_likelihood": "All"}

    with ui.column().classes("w-full q-pa-md").style("gap: 0;"):

        # ── Sticky toolbar ──────────────────────────────────────
        with ui.element("div").classes("ed-toolbar"):
            ui.button("Add Risk", icon="add",
                      on_click=lambda: show_add_dialog()) \
                .props("flat dense color=primary")
            ui.element("div").classes("ed-toolbar-grow")
            with ui.element("div").classes("ed-status-now"):
                ui.element("span").classes("ed-status-dot")
                _total_label = ui.label("TOTAL · 0").classes("ed-mono")

        with ui.element("div").classes("ed-shell"):

            ui.label("Risk Registry").classes("text-h4 q-mb-md")

            kpi_container = ui.element("div").classes("ed-strip")
            seg_container = ui.element("div").classes("ed-segmented")

            with ui.element("div").classes("ed-filter-row"):
                ui.label("Filter").classes("ed-filter-label")
                search_input = ui.input(
                    placeholder="Search by name, category, likelihood, impact…",
                ).props('dense outlined clearable').style("min-width: 320px;")

            # ── Table ──────────────────────────────────────────
            with ui.element("div").classes("ed-card"):
                table = ui.table(
                    columns=_COLUMNS,
                    rows=[],
                    row_key="id",
                    pagination={"rowsPerPage": 25},
                ).classes("w-full").props("flat")

        # Color-coded badges for likelihood
        table.add_slot(
            "body-cell-likelihood",
            r"""
            <q-td :props="props">
                <q-badge
                    :color="props.value === 'HIGH' ? 'negative' : props.value === 'MEDIUM' ? 'warning' : 'positive'"
                    :label="props.value"
                />
            </q-td>
            """,
        )

        # Color-coded badges for impact
        table.add_slot(
            "body-cell-impact",
            r"""
            <q-td :props="props">
                <q-badge
                    :color="props.value === 'HIGH' ? 'negative' : props.value === 'MEDIUM' ? 'warning' : 'positive'"
                    :label="props.value"
                />
            </q-td>
            """,
        )

        # Action buttons column
        table.add_slot(
            "body-cell-actions",
            r"""
            <q-td :props="props">
                <q-btn
                    dense flat round icon="edit" color="primary" size="sm"
                    @click="$parent.$emit('edit-row', props.row)"
                    class="q-mr-xs"
                />
                <q-btn
                    dense flat round icon="delete" color="negative" size="sm"
                    @click="$parent.$emit('delete-row', props.row)"
                />
            </q-td>
            """,
        )

        # ------------------------------------------------------------------ #
        # KPI / segments / filter                                              #
        # ------------------------------------------------------------------ #
        def _count_by_lik(rows: list[dict], v: str) -> int:
            return sum(1 for r in rows if (r.get("likelihood") or "") == v)

        def _set_lik(v: str) -> None:
            state["filter_likelihood"] = v
            _render_kpis()
            _render_segments()
            _apply_search()

        def _render_kpis() -> None:
            kpi_container.clear()
            with kpi_container:
                rows = state["rows"]
                _total_label.set_text(f"TOTAL · {len(rows)}")
                high_n = _count_by_lik(rows, "HIGH")
                med_n = _count_by_lik(rows, "MEDIUM")
                low_n = _count_by_lik(rows, "LOW")
                high_impact = sum(1 for r in rows if (r.get("impact") or "") == "HIGH")
                cat_n = len({r.get("category") or "" for r in rows} - {""})

                def _tile(label: str, value: str, sub: str, key: str | None = None) -> None:
                    cls = "ed-strip-cell ed-stat-tile"
                    if key and state["filter_likelihood"] == key:
                        cls += " active"
                    el = ui.element("div").classes(cls)
                    if key is not None:
                        el.on("click", lambda _, k=key: _set_lik(k))
                    with el:
                        ui.label(label).classes("ed-eyebrow")
                        ui.label(value).classes("ed-strip-num")
                        if sub:
                            ui.label(sub).classes("ed-stat-tile-sub")

                _tile("Total Risks", str(len(rows)),
                      f"{cat_n} categor{'ies' if cat_n != 1 else 'y'} · {high_impact} high impact",
                      key="All")
                _tile("High Likelihood", str(high_n),
                      "filter to high", key="HIGH")
                _tile("Medium", str(med_n),
                      "filter to medium", key="MEDIUM")
                _tile("Low", str(low_n),
                      "filter to low", key="LOW")

        def _render_segments() -> None:
            seg_container.clear()
            with seg_container:
                rows = state["rows"]

                def _seg(label: str, key: str, count: int) -> None:
                    cls = "ed-segmented-item" + (
                        " active" if state["filter_likelihood"] == key else "")
                    btn = ui.element("button").classes(cls)
                    btn.on("click", lambda _, k=key: _set_lik(k))
                    with btn:
                        ui.label(label)
                        ui.label(f"· {count}").classes("seg-count")

                _seg("All", "All", len(rows))
                for v in LIKELIHOOD_OPTIONS:
                    n = _count_by_lik(rows, v)
                    if n or v == state["filter_likelihood"]:
                        _seg(v.title(), v, n)

        def _apply_search() -> None:
            query = (search_input.value or "").strip().lower()
            lik = state["filter_likelihood"]
            rows = list(state["rows"])
            if lik != "All":
                rows = [r for r in rows if (r.get("likelihood") or "") == lik]
            if query:
                rows = [
                    r for r in rows
                    if query in (r.get("name") or "").lower()
                    or query in (r.get("category") or "").lower()
                    or query in (r.get("likelihood") or "").lower()
                    or query in (r.get("impact") or "").lower()
                    or query in (r.get("description") or "").lower()
                    or query in str(r.get("id", ""))
                ]
            table.rows = rows
            table.update()

        search_input.on("update:model-value", lambda _: _apply_search())

        # ------------------------------------------------------------------ #
        # Refresh helper                                                        #
        # ------------------------------------------------------------------ #
        async def refresh() -> None:
            try:
                all_rows: list = await api_get("/risk-items")
                state["rows"] = all_rows
                _render_kpis()
                _render_segments()
                _apply_search()
            except Exception as exc:
                ui.notify(f"Failed to load risk items: {exc}", type="negative")

        # ------------------------------------------------------------------ #
        # Add dialog                                                            #
        # ------------------------------------------------------------------ #
        async def show_add_dialog() -> None:
            with ui.dialog() as dialog, ui.card().classes("w-96"):
                ui.label("Add Risk").classes("text-h6 q-mb-sm")

                name_input = ui.input("Name *").classes("w-full")
                category_input = ui.input("Category").classes("w-full")
                likelihood_select = ui.select(
                    LIKELIHOOD_OPTIONS,
                    label="Likelihood",
                    value="MEDIUM",
                ).classes("w-full")
                impact_select = ui.select(
                    IMPACT_OPTIONS,
                    label="Impact",
                    value="MEDIUM",
                ).classes("w-full")
                description_input = ui.textarea(
                    "Description",
                ).classes("w-full")
                mitigation_input = ui.textarea(
                    "Mitigation",
                ).classes("w-full")

                async def save() -> None:
                    if not name_input.value or not str(name_input.value).strip():
                        ui.notify("Name is required.", type="warning")
                        return
                    try:
                        payload: dict = {
                            "name": str(name_input.value).strip(),
                            "category": str(category_input.value or "").strip(),
                            "likelihood": likelihood_select.value,
                            "impact": impact_select.value,
                            "description": str(description_input.value or "").strip(),
                            "mitigation": str(mitigation_input.value or "").strip(),
                        }
                        await api_post(
                            "/risk-items",
                            json=payload,
                        )
                        dialog.close()
                        ui.notify("Risk item created.", type="positive")
                        await refresh()
                    except Exception as exc:
                        ui.notify(f"Error creating risk item: {exc}", type="negative")

                with ui.row().classes("q-mt-md justify-end w-full"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    ui.button("Save", on_click=save).props("color=primary")

            dialog.open()

        # ------------------------------------------------------------------ #
        # Edit dialog                                                           #
        # ------------------------------------------------------------------ #
        async def show_edit_dialog(row: dict) -> None:
            with ui.dialog() as dialog, ui.card().classes("w-96"):
                ui.label("Edit Risk").classes("text-h6 q-mb-sm")

                name_input = ui.input("Name *", value=row.get("name", "")).classes("w-full")
                category_input = ui.input("Category", value=row.get("category", "")).classes("w-full")
                likelihood_select = ui.select(
                    LIKELIHOOD_OPTIONS,
                    label="Likelihood",
                    value=row.get("likelihood", "MEDIUM"),
                ).classes("w-full")
                impact_select = ui.select(
                    IMPACT_OPTIONS,
                    label="Impact",
                    value=row.get("impact", "MEDIUM"),
                ).classes("w-full")
                description_input = ui.textarea(
                    "Description",
                    value=row.get("description", ""),
                ).classes("w-full")
                mitigation_input = ui.textarea(
                    "Mitigation",
                    value=row.get("mitigation", ""),
                ).classes("w-full")

                async def save() -> None:
                    if not name_input.value or not str(name_input.value).strip():
                        ui.notify("Name is required.", type="warning")
                        return
                    try:
                        payload: dict = {
                            "name": str(name_input.value).strip(),
                            "category": str(category_input.value or "").strip(),
                            "likelihood": likelihood_select.value,
                            "impact": impact_select.value,
                            "description": str(description_input.value or "").strip(),
                            "mitigation": str(mitigation_input.value or "").strip(),
                        }
                        await api_put(
                            f"/risk-items/{row['id']}",
                            json=payload,
                        )
                        dialog.close()
                        ui.notify("Risk item updated.", type="positive")
                        await refresh()
                    except Exception as exc:
                        ui.notify(f"Error updating risk item: {exc}", type="negative")

                with ui.row().classes("q-mt-md justify-end w-full"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    ui.button("Save", on_click=save).props("color=primary")

            dialog.open()

        # ------------------------------------------------------------------ #
        # Delete confirmation dialog                                            #
        # ------------------------------------------------------------------ #
        async def show_delete_dialog(row: dict) -> None:
            with ui.dialog() as dialog, ui.card().classes("w-80"):
                ui.label("Delete Risk").classes("text-h6")
                ui.label(
                    f"Delete '{row.get('name', '')}' (ID {row.get('id')})? "
                    "This cannot be undone."
                ).classes("text-body2 q-mt-sm")

                async def confirm() -> None:
                    try:
                        await api_delete(f"/risk-items/{row['id']}")
                        dialog.close()
                        ui.notify("Risk item deleted.", type="positive")
                        await refresh()
                    except Exception as exc:
                        ui.notify(f"Error deleting risk item: {exc}", type="negative")

                with ui.row().classes("q-mt-md justify-end w-full"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    ui.button("Delete", on_click=confirm).props("color=negative")

            dialog.open()

        # ------------------------------------------------------------------ #
        # Wire table events to dialogs                                          #
        # ------------------------------------------------------------------ #
        table.on("edit-row",   lambda e: show_edit_dialog(e.args))
        table.on("delete-row", lambda e: show_delete_dialog(e.args))

        # ------------------------------------------------------------------ #
        # Initial data load                                                     #
        # ------------------------------------------------------------------ #
        await refresh()
