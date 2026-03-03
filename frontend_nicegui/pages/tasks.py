"""Task Templates CRUD page for the NiceGUI frontend."""

from nicegui import ui

from frontend_nicegui.app import (
    api_delete,
    api_get,
    api_post,
    api_put,
    is_authenticated,
    show_error_page,
    sidebar,
)


@ui.page("/tasks")
async def tasks_page():
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    with ui.column().classes("q-pa-lg w-full"):
        ui.label("Task Templates").classes("text-h4 q-mb-md")

        try:
            templates = await api_get("/task-templates")
            features = await api_get("/features")
        except Exception as exc:
            show_error_page(exc)
            return

        # Fetch product types from config
        try:
            product_types: list[str] = await api_get("/configuration/product_types")
        except Exception:
            product_types = ["Payment", "Telco"]

        feature_map = {f["id"]: f["name"] for f in features}
        feature_options = {0: "(Global - no feature)"} | {f["id"]: f["name"] for f in features}

        # ------------------------------------------------------------------ #
        # Table                                                                #
        # ------------------------------------------------------------------ #
        cols = [
            {"name": "id", "label": "ID", "field": "id", "align": "left", "sortable": True},
            {"name": "name", "label": "Name", "field": "name", "align": "left", "sortable": True},
            {"name": "task_type", "label": "Type", "field": "task_type", "align": "left", "sortable": True},
            {"name": "feature", "label": "Feature", "field": "feature", "align": "left"},
            {"name": "base_effort_hours", "label": "Base Hours", "field": "base_effort_hours", "align": "right", "sortable": True},
            {"name": "scales_with_dut", "label": "Scales DUT", "field": "scales_with_dut", "align": "center"},
            {"name": "scales_with_profile", "label": "Scales Profile", "field": "scales_with_profile", "align": "center"},
            {"name": "product_type", "label": "Product Type", "field": "product_type", "align": "left", "sortable": True},
            {"name": "actions", "label": "Actions", "field": "actions", "align": "center"},
        ]

        table = ui.table(
            columns=cols,
            rows=[],
            row_key="id",
            pagination={"rowsPerPage": 20},
        ).classes("w-full shadow-1")

        table.add_slot(
            "body-cell-actions",
            r"""
            <q-td :props="props">
                <q-btn dense flat round icon="edit" color="primary" size="sm"
                    @click="$parent.$emit('edit-row', props.row)" class="q-mr-xs" />
                <q-btn dense flat round icon="delete" color="negative" size="sm"
                    @click="$parent.$emit('delete-row', props.row)" />
            </q-td>
            """,
        )

        # ------------------------------------------------------------------ #
        # Refresh helper                                                       #
        # ------------------------------------------------------------------ #
        def _build_rows() -> list[dict]:
            rows = []
            for t in templates:
                rows.append({
                    "id": t["id"],
                    "name": t["name"],
                    "task_type": t["task_type"],
                    "feature": feature_map.get(t.get("feature_id"), "Global"),
                    "feature_id": t.get("feature_id"),
                    "base_effort_hours": t["base_effort_hours"],
                    "scales_with_dut": "Yes" if t.get("scales_with_dut") else "No",
                    "scales_with_profile": "Yes" if t.get("scales_with_profile") else "No",
                    "is_parallelizable": t.get("is_parallelizable", False),
                    "description": t.get("description") or "",
                    "product_type": t.get("product_type") or "",
                })
            return rows

        def _refresh_table():
            table.rows = _build_rows()
            table.update()

        # ------------------------------------------------------------------ #
        # Add dialog                                                           #
        # ------------------------------------------------------------------ #
        async def _show_add_dialog():
            with ui.dialog() as dlg, ui.card().classes("w-96"):
                ui.label("Add Task Template").classes("text-h6 q-mb-md")
                name_input = ui.input("Name *").classes("w-full")
                type_select = ui.select(
                    options=["SETUP", "EXECUTION", "ANALYSIS", "REPORTING", "STUDY"],
                    label="Task Type",
                    value="EXECUTION",
                ).classes("w-full")
                feat_select = ui.select(
                    options=feature_options,
                    label="Feature (optional)",
                    value=0,
                    with_input=True,
                ).classes("w-full")
                hours_input = ui.number("Base Effort Hours", value=8, min=0.1, step=0.5).classes("w-full")
                dut_switch = ui.switch("Scales with DUT", value=False)
                prof_switch = ui.switch("Scales with Profile", value=False)
                para_switch = ui.switch("Is Parallelizable", value=False)
                pt_select = ui.select(
                    options=[""] + product_types,
                    label="Product Type (optional)",
                    value="",
                    with_input=True,
                    clearable=True,
                ).classes("w-full")
                desc_input = ui.textarea("Description").classes("w-full")

                async def _save():
                    if not name_input.value:
                        ui.notify("Name is required.", type="warning")
                        return
                    payload = {
                        "name": name_input.value,
                        "task_type": type_select.value,
                        "feature_id": feat_select.value if feat_select.value != 0 else None,
                        "base_effort_hours": float(hours_input.value or 8),
                        "scales_with_dut": dut_switch.value,
                        "scales_with_profile": prof_switch.value,
                        "is_parallelizable": para_switch.value,
                        "description": desc_input.value or None,
                        "product_type": pt_select.value if pt_select.value else None,
                    }
                    try:
                        new_tmpl = await api_post("/task-templates", json=payload)
                        templates.append(new_tmpl)
                        ui.notify("Task template created.", type="positive")
                        dlg.close()
                        _refresh_table()
                    except Exception as exc:
                        ui.notify(f"Failed: {exc}", type="negative")

                with ui.row().classes("w-full justify-end q-mt-md"):
                    ui.button("Cancel", on_click=dlg.close).props("flat")
                    ui.button("Save", on_click=_save).props("color=primary")

            dlg.open()

        # ------------------------------------------------------------------ #
        # Edit dialog                                                          #
        # ------------------------------------------------------------------ #
        async def _show_edit_dialog(row: dict):
            # Find original template by id
            tmpl = next((t for t in templates if t["id"] == row["id"]), None)
            if not tmpl:
                ui.notify("Template not found.", type="warning")
                return

            with ui.dialog() as dlg, ui.card().classes("w-96"):
                ui.label("Edit Task Template").classes("text-h6 q-mb-md")
                name_input = ui.input("Name *", value=tmpl["name"]).classes("w-full")
                type_select = ui.select(
                    options=["SETUP", "EXECUTION", "ANALYSIS", "REPORTING", "STUDY"],
                    label="Task Type",
                    value=tmpl["task_type"],
                ).classes("w-full")
                feat_select = ui.select(
                    options=feature_options,
                    label="Feature (optional)",
                    value=tmpl.get("feature_id") or 0,
                    with_input=True,
                ).classes("w-full")
                hours_input = ui.number(
                    "Base Effort Hours",
                    value=tmpl["base_effort_hours"],
                    min=0.1,
                    step=0.5,
                ).classes("w-full")
                dut_switch = ui.switch("Scales with DUT", value=bool(tmpl.get("scales_with_dut")))
                prof_switch = ui.switch("Scales with Profile", value=bool(tmpl.get("scales_with_profile")))
                para_switch = ui.switch("Is Parallelizable", value=bool(tmpl.get("is_parallelizable")))
                pt_select = ui.select(
                    options=[""] + product_types,
                    label="Product Type (optional)",
                    value=tmpl.get("product_type") or "",
                    with_input=True,
                    clearable=True,
                ).classes("w-full")
                desc_input = ui.textarea("Description", value=tmpl.get("description") or "").classes("w-full")

                async def _save():
                    if not name_input.value:
                        ui.notify("Name is required.", type="warning")
                        return
                    payload = {
                        "name": name_input.value,
                        "task_type": type_select.value,
                        "feature_id": feat_select.value if feat_select.value != 0 else None,
                        "base_effort_hours": float(hours_input.value or 8),
                        "scales_with_dut": dut_switch.value,
                        "scales_with_profile": prof_switch.value,
                        "is_parallelizable": para_switch.value,
                        "description": desc_input.value or None,
                        "product_type": pt_select.value if pt_select.value else None,
                    }
                    try:
                        updated = await api_put(f"/task-templates/{tmpl['id']}", json=payload)
                        # Update in-memory list
                        for i, t in enumerate(templates):
                            if t["id"] == tmpl["id"]:
                                templates[i] = updated
                                break
                        ui.notify("Task template updated.", type="positive")
                        dlg.close()
                        _refresh_table()
                    except Exception as exc:
                        ui.notify(f"Failed: {exc}", type="negative")

                with ui.row().classes("w-full justify-end q-mt-md"):
                    ui.button("Cancel", on_click=dlg.close).props("flat")
                    ui.button("Save", on_click=_save).props("color=primary")

            dlg.open()

        # ------------------------------------------------------------------ #
        # Delete dialog                                                        #
        # ------------------------------------------------------------------ #
        async def _show_delete_dialog(row: dict):
            with ui.dialog() as dlg, ui.card().classes("w-80"):
                ui.label("Delete Task Template").classes("text-h6")
                ui.label(
                    f"Delete '{row.get('name', '')}' (ID {row.get('id')})? "
                    "This cannot be undone."
                ).classes("text-body2 q-mt-sm")

                async def _confirm():
                    try:
                        await api_delete(f"/task-templates/{row['id']}")
                        templates[:] = [t for t in templates if t["id"] != row["id"]]
                        dlg.close()
                        ui.notify("Task template deleted.", type="positive")
                        _refresh_table()
                    except Exception as exc:
                        ui.notify(f"Failed: {exc}", type="negative")

                with ui.row().classes("q-mt-md justify-end w-full"):
                    ui.button("Cancel", on_click=dlg.close).props("flat")
                    ui.button("Delete", on_click=_confirm).props("color=negative")

            dlg.open()

        # ------------------------------------------------------------------ #
        # Wire events                                                          #
        # ------------------------------------------------------------------ #
        table.on("edit-row", lambda e: _show_edit_dialog(e.args))
        table.on("delete-row", lambda e: _show_delete_dialog(e.args))

        # ------------------------------------------------------------------ #
        # Toolbar                                                              #
        # ------------------------------------------------------------------ #
        with ui.row().classes("q-mb-md"):
            ui.button("Add Template", icon="add", on_click=_show_add_dialog).props("color=primary")

        _refresh_table()
