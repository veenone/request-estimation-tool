"""Test Profiles page — full CRUD.

Route: /profiles
API:
  GET    /profiles
  POST   /profiles
  PUT    /profiles/{id}
  DELETE /profiles/{id}
"""

from nicegui import ui
from frontend_nicegui.app import (
    api_delete,
    api_get,
    api_post,
    api_put,
    empty_state,
    is_authenticated,
    loading_state,
    run_async,
    sidebar,
)

_COLUMNS = [
    {"name": "id",               "label": "ID",          "field": "id",               "align": "left", "sortable": True},
    {"name": "name",             "label": "Name",         "field": "name",             "align": "left", "sortable": True},
    {"name": "description",      "label": "Description",  "field": "description",      "align": "left"},
    {"name": "effort_multiplier","label": "Multiplier",   "field": "effort_multiplier","align": "left", "sortable": True},
    {"name": "product_type",     "label": "Product Type", "field": "product_type",     "align": "left", "sortable": True},
    {"name": "is_active",        "label": "Active",       "field": "is_active",        "align": "center", "sortable": True},
    {"name": "actions",          "label": "Actions",      "field": "actions",          "align": "left"},
]


@ui.page("/profiles")
async def profiles_page() -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    # Fetch product types from config
    try:
        product_types: list[str] = await api_get("/configuration/product_types")
    except Exception:
        product_types = ["Payment", "Telco"]

    # ── State ────────────────────────────────────────────────────
    all_rows_ref: dict = {"data": []}
    state: dict = {"filter_status": "All"}

    with ui.column().classes("w-full q-pa-md").style("gap: 0;"):

        # ── Sticky toolbar ──────────────────────────────────────
        with ui.element("div").classes("ed-toolbar"):
            ui.button("Add Profile", icon="add",
                      on_click=lambda: show_add_dialog()) \
                .props("flat dense color=primary")
            ui.element("div").classes("ed-toolbar-grow")
            with ui.element("div").classes("ed-status-now"):
                ui.element("span").classes("ed-status-dot")
                _total_label = ui.label("TOTAL · 0").classes("ed-mono")

        with ui.element("div").classes("ed-shell"):

            ui.label("Test Profiles").classes("text-h4 q-mb-md")

            kpi_container = ui.element("div").classes("ed-strip")
            seg_container = ui.element("div").classes("ed-segmented")

            with ui.element("div").classes("ed-filter-row"):
                ui.label("Filter").classes("ed-filter-label")
                search_input = ui.input(
                    placeholder="Search by name, description, product type…",
                ).props('dense outlined clearable').style("min-width: 320px;")

            # ── Table ──────────────────────────────────────────
            with ui.element("div").classes("ed-card"):
                table = ui.table(
                    columns=_COLUMNS,
                    rows=[],
                    row_key="id",
                    pagination={"rowsPerPage": 25},
                ).classes("w-full").props("flat")
                empty_holder = ui.element("div").classes("w-full")
                empty_holder.set_visibility(False)

        # Truncate long descriptions in the table cell
        table.add_slot(
            "body-cell-description",
            r"""
            <q-td :props="props">
                <span :title="props.value">
                    {{ props.value ? (props.value.length > 60 ? props.value.slice(0, 60) + '…' : props.value) : '—' }}
                </span>
            </q-td>
            """,
        )

        # Active status column
        table.add_slot(
            "body-cell-is_active",
            r"""
            <q-td :props="props">
                <q-icon :name="props.value === false ? 'cancel' : 'check_circle'"
                        :color="props.value === false ? 'negative' : 'positive'" size="sm" />
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
                ><q-tooltip>Edit</q-tooltip></q-btn>
                <q-btn
                    dense flat round icon="delete" color="negative" size="sm"
                    @click="$parent.$emit('delete-row', props.row)"
                ><q-tooltip>Delete</q-tooltip></q-btn>
            </q-td>
            """,
        )

        # ------------------------------------------------------------------ #
        # KPI / segments / filter                                              #
        # ------------------------------------------------------------------ #
        def _set_status(s: str) -> None:
            state["filter_status"] = s
            _render_kpis()
            _render_segments()
            _apply_search()

        def _render_kpis() -> None:
            kpi_container.clear()
            with kpi_container:
                rows = all_rows_ref["data"]
                _total_label.set_text(f"TOTAL · {len(rows)}")
                n_active = sum(1 for r in rows if r.get("is_active") is not False)
                n_inactive = len(rows) - n_active
                with_pt = sum(1 for r in rows if r.get("product_type"))
                avg_mult = (sum(float(r.get("effort_multiplier", 1.0)) for r in rows) / len(rows)) if rows else 0.0

                def _tile(label: str, count: str, sub: str, key: str | None = None) -> None:
                    cls = "ed-strip-cell ed-stat-tile"
                    if key and state["filter_status"] == key:
                        cls += " active"
                    el = ui.element("div").classes(cls)
                    if key is not None:
                        el.on("click", lambda _, k=key: _set_status(k))
                    with el:
                        ui.label(label).classes("ed-eyebrow")
                        ui.label(count).classes("ed-strip-num")
                        if sub:
                            ui.label(sub).classes("ed-stat-tile-sub")

                _tile("Total Profiles", str(len(rows)),
                      f"{with_pt} have product type set", key="All")
                _tile("Active", str(n_active),
                      f"{n_inactive} inactive", key="active")
                if n_inactive:
                    _tile("Inactive", str(n_inactive),
                          "filter to inactive", key="inactive")
                _tile("Avg Multiplier", f"{avg_mult:.2f}×",
                      "across all profiles", key=None)

        def _render_segments() -> None:
            seg_container.clear()
            with seg_container:
                rows = all_rows_ref["data"]
                n_active = sum(1 for r in rows if r.get("is_active") is not False)
                n_inactive = len(rows) - n_active

                def _seg(label: str, key: str, count: int) -> None:
                    cls = "ed-segmented-item" + (
                        " active" if state["filter_status"] == key else "")
                    btn = ui.element("button").classes(cls)
                    btn.on("click", lambda _, k=key: _set_status(k))
                    with btn:
                        ui.label(label)
                        ui.label(f"· {count}").classes("seg-count")
                _seg("All", "All", len(rows))
                _seg("Active", "active", n_active)
                if n_inactive or state["filter_status"] == "inactive":
                    _seg("Inactive", "inactive", n_inactive)

        def _apply_search() -> None:
            query = (search_input.value or "").strip().lower()
            stat = state["filter_status"]
            rows = list(all_rows_ref["data"])
            if stat == "active":
                rows = [r for r in rows if r.get("is_active") is not False]
            elif stat == "inactive":
                rows = [r for r in rows if r.get("is_active") is False]
            if query:
                rows = [
                    r for r in rows
                    if query in (r.get("name") or "").lower()
                    or query in (r.get("description") or "").lower()
                    or query in (r.get("product_type") or "").lower()
                    or query in str(r.get("effort_multiplier", ""))
                    or query in str(r.get("id", ""))
                ]
            table.rows = rows
            table.update()
            no_rows = not rows
            empty_holder.clear()
            if no_rows:
                with empty_holder:
                    empty_state("No results match your filters.")
            empty_holder.set_visibility(no_rows)
            table.set_visibility(not no_rows)

        search_input.on("update:model-value", lambda _: _apply_search())

        # ------------------------------------------------------------------ #
        # Refresh helper                                                        #
        # ------------------------------------------------------------------ #
        async def refresh() -> None:
            try:
                async with loading_state():
                    rows: list = await api_get("/profiles")
                all_rows_ref["data"] = rows
                _render_kpis()
                _render_segments()
                _apply_search()
            except Exception as exc:
                ui.notify(f"Failed to load profiles: {exc}", type="negative")

        # ------------------------------------------------------------------ #
        # Add dialog                                                            #
        # ------------------------------------------------------------------ #
        async def show_add_dialog() -> None:
            with ui.dialog() as dialog, ui.card().classes("w-[480px]"):
                ui.label("Add Test Profile").classes("text-h6 q-mb-sm")

                name_input = ui.input("Name *").props("autofocus").classes("w-full")
                description_input = ui.textarea("Description").classes("w-full")
                multiplier_input = ui.number(
                    "Effort Multiplier",
                    value=1.0,
                    min=0.1,
                    max=10.0,
                    step=0.1,
                    format="%.1f",
                ).classes("w-full")
                product_type_input = ui.select(
                    options=[""] + product_types,
                    label="Product Type (optional)",
                    value="",
                    with_input=True,
                    clearable=True,
                ).classes("w-full")

                async def save() -> None:
                    if not name_input.value or not str(name_input.value).strip():
                        ui.notify("Name is required.", type="warning")
                        return
                    payload: dict = {
                        "name": str(name_input.value).strip(),
                        "description": str(description_input.value or "").strip(),
                        "effort_multiplier": float(multiplier_input.value or 1.0),
                    }
                    if product_type_input.value:
                        payload["product_type"] = product_type_input.value
                    await api_post(
                        "/profiles",
                        json=payload,
                    )
                    dialog.close()
                    await refresh()

                with ui.row().classes("q-mt-md justify-end w-full"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    save_btn = ui.button("Save").props("color=primary")
                    save_btn.on("click", run_async(save_btn, save, success="Profile created.", error_prefix="Save failed"))

            dialog.open()

        # ------------------------------------------------------------------ #
        # Edit dialog                                                           #
        # ------------------------------------------------------------------ #
        async def show_edit_dialog(row: dict) -> None:
            with ui.dialog() as dialog, ui.card().classes("w-[480px]"):
                ui.label("Edit Test Profile").classes("text-h6 q-mb-sm")

                name_input = ui.input("Name *", value=row.get("name", "")).props("autofocus").classes("w-full")
                description_input = ui.textarea(
                    "Description",
                    value=row.get("description", "") or "",
                ).classes("w-full")
                multiplier_input = ui.number(
                    "Effort Multiplier",
                    value=float(row.get("effort_multiplier", 1.0)),
                    min=0.1,
                    max=10.0,
                    step=0.1,
                    format="%.1f",
                ).classes("w-full")
                product_type_input = ui.select(
                    options=[""] + product_types,
                    label="Product Type (optional)",
                    value=row.get("product_type") or "",
                    with_input=True,
                    clearable=True,
                ).classes("w-full")
                is_active_input = ui.switch(
                    "Active",
                    value=row.get("is_active", True) is not False,
                )

                async def save() -> None:
                    if not name_input.value or not str(name_input.value).strip():
                        ui.notify("Name is required.", type="warning")
                        return
                    payload: dict = {
                        "name": str(name_input.value).strip(),
                        "description": str(description_input.value or "").strip(),
                        "effort_multiplier": float(multiplier_input.value or 1.0),
                        "product_type": product_type_input.value if product_type_input.value else None,
                        "is_active": is_active_input.value,
                    }
                    await api_put(
                        f"/profiles/{row['id']}",
                        json=payload,
                    )
                    dialog.close()
                    await refresh()

                with ui.row().classes("q-mt-md justify-end w-full"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    save_btn = ui.button("Save").props("color=primary")
                    save_btn.on("click", run_async(save_btn, save, success="Profile updated.", error_prefix="Save failed"))

            dialog.open()

        # ------------------------------------------------------------------ #
        # Delete confirmation dialog                                            #
        # ------------------------------------------------------------------ #
        async def show_delete_dialog(row: dict) -> None:
            with ui.dialog() as dialog, ui.card().classes("w-80"):
                ui.label("Delete Profile").classes("text-h6")
                ui.label(
                    f"Delete '{row.get('name', '')}' (ID {row.get('id')})? "
                    "This cannot be undone."
                ).classes("text-body2 q-mt-sm")

                async def confirm() -> None:
                    await api_delete(f"/profiles/{row['id']}")
                    dialog.close()
                    await refresh()

                with ui.row().classes("q-mt-md justify-end w-full"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    del_btn = ui.button("Delete").props("color=negative")
                    del_btn.on("click", run_async(del_btn, confirm, success="Profile deleted.", error_prefix="Delete failed"))

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
