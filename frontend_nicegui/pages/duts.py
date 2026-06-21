"""DUT Registry page — full CRUD with bulk edit.

Route: /duts
API:
  GET    /dut-types
  POST   /dut-types
  PUT    /dut-types/{id}
  DELETE /dut-types/{id}
"""

from nicegui import ui
from frontend_nicegui.app import (
    api_delete,
    api_get,
    api_post,
    api_put,
    empty_state,
    has_permission,
    is_authenticated,
    loading_state,
    run_async,
    sidebar,
)

_DEFAULT_CATEGORIES = ["SIM", "eSIM", "UICC", "IoT Device", "Mobile Device", "Other"]

_COLUMNS = [
    {"name": "id",                    "label": "ID",          "field": "id",                    "align": "left", "sortable": True},
    {"name": "name",                  "label": "Name",         "field": "name",                  "align": "left", "sortable": True},
    {"name": "category",              "label": "Category",     "field": "category",              "align": "left", "sortable": True},
    {"name": "complexity_multiplier", "label": "Multiplier",   "field": "complexity_multiplier", "align": "left", "sortable": True},
    {"name": "product_type",          "label": "Product Type", "field": "product_type",          "align": "left", "sortable": True},
    {"name": "actions",               "label": "Actions",      "field": "actions",               "align": "left"},
]


@ui.page("/duts")
async def duts_page() -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    # ------------------------------------------------------------------ #
    # Fetch configurable categories and product types                      #
    # ------------------------------------------------------------------ #
    try:
        categories: list[str] = await api_get("/dut-categories")
    except Exception:
        categories = _DEFAULT_CATEGORIES

    try:
        product_types: list[str] = await api_get("/configuration/product_types")
    except Exception:
        product_types = ["Payment", "Telco"]

    # ── State for filters ─────────────────────────────────────────
    state: dict = {"filter_category": "All"}
    all_rows_ref: dict = {"data": []}

    with ui.column().classes("w-full q-pa-md").style("gap: 0;"):

        # ── Sticky toolbar ──────────────────────────────────────
        with ui.element("div").classes("ed-toolbar"):
            ui.button("Add DUT", icon="add",
                      on_click=lambda: show_add_dialog()) \
                .props("flat dense color=primary")
            if has_permission("reinit_registries"):
                ui.element("div").classes("ed-toolbar-spacer")

                async def _reinit_duts() -> None:
                    with ui.dialog() as confirm_dlg, ui.card().classes("w-80"):
                        ui.label("Reinitialize DUT Registry").classes("text-h6")
                        ui.label(
                            "This will delete ALL DUT types and reset IDs to start from 1. "
                            "This cannot be undone."
                        ).classes("text-body2 q-mt-sm")

                        async def _confirm() -> None:
                            await api_post("/dut-types/reinit")
                            confirm_dlg.close()
                            await refresh()

                        with ui.row().classes("q-mt-md justify-end w-full"):
                            ui.button("Cancel", on_click=confirm_dlg.close).props("flat")
                            reinit_btn = ui.button("Delete All").props("color=negative")
                            reinit_btn.on("click", run_async(reinit_btn, _confirm, success="DUT registry reinitialized.", error_prefix="Reinit failed"))
                    confirm_dlg.open()

                ui.button("Reinit Registry", icon="restart_alt",
                          on_click=_reinit_duts) \
                    .props("flat dense color=negative")

            ui.element("div").classes("ed-toolbar-spacer")
            bulk_edit_btn = ui.button("Bulk Edit", icon="edit_note",
                                      on_click=lambda: show_bulk_edit_dialog()) \
                .props("flat dense color=secondary")
            bulk_edit_btn.set_visibility(False)

            bulk_delete_btn = ui.button("Bulk Delete", icon="delete_sweep",
                                        on_click=lambda: show_bulk_delete_dialog()) \
                .props("flat dense color=negative")
            bulk_delete_btn.set_visibility(False)

            ui.element("div").classes("ed-toolbar-grow")
            with ui.element("div").classes("ed-status-now"):
                ui.element("span").classes("ed-status-dot")
                _total_label = ui.label("TOTAL · 0").classes("ed-mono")

        with ui.element("div").classes("ed-shell"):

            ui.label("DUT Registry").classes("text-h4 q-mb-md")

            kpi_container = ui.element("div").classes("ed-strip")
            seg_container = ui.element("div").classes("ed-segmented")

            with ui.element("div").classes("ed-filter-row"):
                ui.label("Filter").classes("ed-filter-label")
                search_input = ui.input(
                    placeholder="Search by name, category, product type…",
                ).props('dense outlined clearable').style("min-width: 320px;")

            # ── Table ──────────────────────────────────────────
            with ui.element("div").classes("ed-card"):
                table = ui.table(
                    columns=_COLUMNS,
                    rows=[],
                    row_key="id",
                    pagination={"rowsPerPage": 25},
                    selection="multiple",
                ).classes("w-full").props("flat")
                empty_holder = ui.element("div").classes("w-full")
                empty_holder.set_visibility(False)

        # Show/hide bulk buttons based on selection
        def _on_selection_change() -> None:
            has_sel = bool(table.selected)
            bulk_edit_btn.set_visibility(has_sel)
            bulk_delete_btn.set_visibility(has_sel)

        table.on("selection", lambda _: _on_selection_change())

        # Action buttons column
        table.add_slot(
            "body-cell-actions",
            r"""
            <q-td :props="props">
                <q-btn
                    dense flat round icon="edit" color="primary" size="sm"
                    @click="() => $parent.$emit('edit-row', props.row)"
                    class="q-mr-xs"
                ><q-tooltip>Edit</q-tooltip></q-btn>
                <q-btn
                    dense flat round icon="delete" color="negative" size="sm"
                    @click="() => $parent.$emit('delete-row', props.row)"
                ><q-tooltip>Delete</q-tooltip></q-btn>
            </q-td>
            """,
        )

        # ------------------------------------------------------------------ #
        # KPI / segments / filter                                              #
        # ------------------------------------------------------------------ #
        def _count_by_cat(rows: list[dict], cat: str) -> int:
            return sum(1 for r in rows if (r.get("category") or "") == cat)

        def _set_category(c: str) -> None:
            state["filter_category"] = c
            _render_kpis()
            _render_segments()
            _apply_search()

        def _render_kpis() -> None:
            kpi_container.clear()
            with kpi_container:
                rows = all_rows_ref["data"]
                _total_label.set_text(f"TOTAL · {len(rows)}")
                top = sorted(categories, key=lambda c: -_count_by_cat(rows, c))[:3]

                def _tile(label: str, count: int, sub: str, key: str | None = None) -> None:
                    cls = "ed-strip-cell ed-stat-tile"
                    if key and state["filter_category"] == key:
                        cls += " active"
                    el = ui.element("div").classes(cls)
                    if key is not None:
                        el.on("click", lambda _, k=key: _set_category(k))
                    with el:
                        ui.label(label).classes("ed-eyebrow")
                        ui.label(str(count)).classes("ed-strip-num")
                        if sub:
                            ui.label(sub).classes("ed-stat-tile-sub")

                with_pt = sum(1 for r in rows if r.get("product_type"))
                _tile("Total DUTs", len(rows),
                      f"{with_pt} have product type set", key="All")
                for c in top:
                    n = _count_by_cat(rows, c)
                    if n:
                        _tile(c, n, "filter to category", key=c)

        def _render_segments() -> None:
            seg_container.clear()
            with seg_container:
                rows = all_rows_ref["data"]
                def _seg(label: str, key: str, count: int) -> None:
                    cls = "ed-segmented-item" + (
                        " active" if state["filter_category"] == key else "")
                    btn = ui.element("button").classes(cls)
                    btn.on("click", lambda _, k=key: _set_category(k))
                    with btn:
                        ui.label(label)
                        ui.label(f"· {count}").classes("seg-count")
                _seg("All", "All", len(rows))
                for c in categories:
                    n = _count_by_cat(rows, c)
                    if n or c == state["filter_category"]:
                        _seg(c, c, n)

        def _apply_search() -> None:
            query = (search_input.value or "").strip().lower()
            cat = state["filter_category"]
            rows = list(all_rows_ref["data"])
            if cat != "All":
                rows = [r for r in rows if (r.get("category") or "") == cat]
            if query:
                rows = [
                    r for r in rows
                    if query in (r.get("name") or "").lower()
                    or query in (r.get("category") or "").lower()
                    or query in (r.get("product_type") or "").lower()
                    or query in str(r.get("complexity_multiplier", ""))
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
        # Refresh helper                                                       #
        # ------------------------------------------------------------------ #
        async def refresh() -> None:
            try:
                async with loading_state():
                    rows: list = await api_get("/dut-types")
                all_rows_ref["data"] = rows
                _render_kpis()
                _render_segments()
                _apply_search()
                table.selected.clear()
                _on_selection_change()
            except Exception as exc:
                ui.notify(f"Failed to load DUT types: {exc}", type="negative")

        # ------------------------------------------------------------------ #
        # Add dialog                                                           #
        # ------------------------------------------------------------------ #
        async def show_add_dialog() -> None:
            with ui.dialog() as dialog, ui.card().classes("w-[480px]"):
                ui.label("Add DUT Type").classes("text-h6 q-mb-sm")

                name_input = ui.input("Name *").props("autofocus").classes("w-full")
                category_select = ui.select(
                    categories,
                    label="Category",
                    value=categories[0] if categories else "Other",
                ).classes("w-full")
                multiplier_input = ui.number(
                    "Complexity Multiplier",
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
                        "category": category_select.value,
                        "complexity_multiplier": float(multiplier_input.value or 1.0),
                    }
                    if product_type_input.value:
                        payload["product_type"] = product_type_input.value
                    await api_post("/dut-types", json=payload)
                    dialog.close()
                    await refresh()

                with ui.row().classes("q-mt-md justify-end w-full"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    save_btn = ui.button("Save").props("color=primary")
                    save_btn.on("click", run_async(save_btn, save, success="DUT type created.", error_prefix="Save failed"))

            dialog.open()

        # ------------------------------------------------------------------ #
        # Edit dialog                                                          #
        # ------------------------------------------------------------------ #
        async def show_edit_dialog(row: dict) -> None:
            with ui.dialog() as dialog, ui.card().classes("w-[480px]"):
                ui.label("Edit DUT Type").classes("text-h6 q-mb-sm")

                name_input = ui.input("Name *", value=row.get("name", "")).props("autofocus").classes("w-full")
                row_cat = row.get("category", categories[0] if categories else "Other")
                cat_options = categories if row_cat in categories else [row_cat] + categories
                category_select = ui.select(
                    cat_options,
                    label="Category",
                    value=row_cat,
                ).classes("w-full")
                multiplier_input = ui.number(
                    "Complexity Multiplier",
                    value=float(row.get("complexity_multiplier", 1.0)),
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

                async def save() -> None:
                    if not name_input.value or not str(name_input.value).strip():
                        ui.notify("Name is required.", type="warning")
                        return
                    payload: dict = {
                        "name": str(name_input.value).strip(),
                        "category": category_select.value,
                        "complexity_multiplier": float(multiplier_input.value or 1.0),
                        "product_type": product_type_input.value if product_type_input.value else None,
                    }
                    await api_put(f"/dut-types/{row['id']}", json=payload)
                    dialog.close()
                    await refresh()

                with ui.row().classes("q-mt-md justify-end w-full"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    save_btn = ui.button("Save").props("color=primary")
                    save_btn.on("click", run_async(save_btn, save, success="DUT type updated.", error_prefix="Save failed"))

            dialog.open()

        # ------------------------------------------------------------------ #
        # Bulk edit dialog                                                     #
        # ------------------------------------------------------------------ #
        async def show_bulk_edit_dialog() -> None:
            selected = list(table.selected)
            if not selected:
                ui.notify("Select at least one DUT type first.", type="warning")
                return

            with ui.dialog() as dialog, ui.card().classes("w-[480px]"):
                ui.label("Bulk Edit DUT Types").classes("text-h6")
                ui.separator()
                ui.label(
                    f"Update {len(selected)} selected DUT type(s). "
                    "Only checked fields will be changed."
                ).classes("text-body2 q-mb-md")

                # List selected names for reference
                with ui.expansion("Selected items", icon="list").classes("w-full q-mb-sm"):
                    for s in selected:
                        ui.label(f"  {s.get('id')} — {s.get('name', '')}").classes("text-caption")

                # Category field with enable checkbox
                with ui.row().classes("w-full items-center gap-2"):
                    cat_cb = ui.checkbox("Category").classes("w-28")
                    cat_select = ui.select(
                        categories,
                        label="New Category",
                        value=categories[0] if categories else "Other",
                    ).classes("flex-1")
                    cat_select.bind_enabled_from(cat_cb, "value")

                # Multiplier field with enable checkbox
                with ui.row().classes("w-full items-center gap-2"):
                    mult_cb = ui.checkbox("Multiplier").classes("w-28")
                    mult_input = ui.number(
                        "New Multiplier",
                        value=1.0,
                        min=0.1,
                        max=10.0,
                        step=0.1,
                        format="%.1f",
                    ).classes("flex-1")
                    mult_input.bind_enabled_from(mult_cb, "value")

                # Product type field with enable checkbox
                with ui.row().classes("w-full items-center gap-2"):
                    pt_cb = ui.checkbox("Product Type").classes("w-28")
                    pt_select = ui.select(
                        options=["(clear)"] + product_types,
                        label="New Product Type",
                        value=product_types[0] if product_types else "(clear)",
                        with_input=True,
                    ).classes("flex-1")
                    pt_select.bind_enabled_from(pt_cb, "value")

                async def apply() -> None:
                    if not cat_cb.value and not mult_cb.value and not pt_cb.value:
                        ui.notify("Check at least one field to update.", type="warning")
                        return

                    success = 0
                    errors = 0
                    for row in selected:
                        payload: dict = {}
                        if cat_cb.value:
                            payload["category"] = cat_select.value
                        if mult_cb.value:
                            payload["complexity_multiplier"] = float(mult_input.value or 1.0)
                        if pt_cb.value:
                            val = pt_select.value
                            payload["product_type"] = None if val == "(clear)" else val
                        try:
                            await api_put(f"/dut-types/{row['id']}", json=payload)
                            success += 1
                        except Exception:
                            errors += 1

                    msg = f"Updated {success}/{len(selected)} DUT types."
                    if errors:
                        msg += f" ({errors} failed)"
                    ui.notify(msg, type="positive" if not errors else "warning")
                    dialog.close()
                    await refresh()

                with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    apply_btn = ui.button("Apply", icon="check").props("color=primary")
                    apply_btn.on("click", run_async(apply_btn, apply, error_prefix="Bulk update failed"))

            dialog.open()

        # ------------------------------------------------------------------ #
        # Bulk delete dialog                                                   #
        # ------------------------------------------------------------------ #
        async def show_bulk_delete_dialog() -> None:
            selected = list(table.selected)
            if not selected:
                ui.notify("Select at least one DUT type first.", type="warning")
                return

            with ui.dialog() as dialog, ui.card().classes("w-[400px]"):
                ui.label("Bulk Delete DUT Types").classes("text-h6")
                ui.separator()
                ui.label(
                    f"Delete {len(selected)} selected DUT type(s)? This cannot be undone."
                ).classes("text-body2 q-mt-sm text-negative")

                with ui.expansion("Selected items", icon="list").classes("w-full q-mt-sm"):
                    for s in selected:
                        ui.label(f"  {s.get('id')} — {s.get('name', '')}").classes("text-caption")

                async def confirm() -> None:
                    success = 0
                    errors = 0
                    for row in selected:
                        try:
                            await api_delete(f"/dut-types/{row['id']}")
                            success += 1
                        except Exception:
                            errors += 1

                    msg = f"Deleted {success}/{len(selected)} DUT types."
                    if errors:
                        msg += f" ({errors} failed)"
                    ui.notify(msg, type="positive" if not errors else "warning")
                    dialog.close()
                    await refresh()

                with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    bulk_del_btn = ui.button("Delete", icon="delete").props("color=negative")
                    bulk_del_btn.on("click", run_async(bulk_del_btn, confirm, error_prefix="Bulk delete failed"))

            dialog.open()

        # ------------------------------------------------------------------ #
        # Delete confirmation dialog (single row)                              #
        # ------------------------------------------------------------------ #
        async def show_delete_dialog(row: dict) -> None:
            with ui.dialog() as dialog, ui.card().classes("w-80"):
                ui.label("Delete DUT Type").classes("text-h6")
                ui.label(
                    f"Delete '{row.get('name', '')}' (ID {row.get('id')})? "
                    "This cannot be undone."
                ).classes("text-body2 q-mt-sm")

                async def confirm() -> None:
                    await api_delete(f"/dut-types/{row['id']}")
                    dialog.close()
                    await refresh()

                with ui.row().classes("q-mt-md justify-end w-full"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    del_btn = ui.button("Delete").props("color=negative")
                    del_btn.on("click", run_async(del_btn, confirm, success="DUT type deleted.", error_prefix="Delete failed"))

            dialog.open()

        # ------------------------------------------------------------------ #
        # Wire table events to dialogs                                         #
        # ------------------------------------------------------------------ #
        table.on("edit-row",   lambda e: show_edit_dialog(e.args))
        table.on("delete-row", lambda e: show_delete_dialog(e.args))

        # ------------------------------------------------------------------ #
        # Initial data load                                                    #
        # ------------------------------------------------------------------ #
        await refresh()
