"""Document Types registry page — manage document types for reporting tasks.

Route: /document-types
API:
  GET    /document-types/all
  POST   /document-types
  PUT    /document-types/{id}
  DELETE /document-types/{id}
"""

from nicegui import ui
from frontend_nicegui.app import api_get, api_post, api_put, is_authenticated, show_error_page, sidebar

_COLUMNS = [
    {"name": "name",             "label": "Name",           "field": "name",             "align": "left", "sortable": True},
    {"name": "category",         "label": "Category",       "field": "category",         "align": "left", "sortable": True},
    {"name": "base_effort_hours","label": "Base Hours",     "field": "base_effort_hours","align": "right","sortable": True},
    {"name": "task_template_name","label": "Linked Task",   "field": "task_template_name","align": "left","sortable": True},
    {"name": "description",      "label": "Description",    "field": "description",      "align": "left"},
    {"name": "is_active",        "label": "Active",         "field": "is_active",        "align": "center"},
]

_CATEGORIES = ["Planning", "Report", "Compliance", "Other"]


@ui.page("/document-types")
async def document_types_page() -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    with ui.column().classes("q-pa-lg w-full"):
        ui.label("Document Types").classes("text-h4 q-mb-md")
        ui.label(
            "Manage document types used in reporting and documentation tasks. "
            "Each type has a base effort (hours) for creating and submitting a document."
        ).classes("text-body2 text-grey q-mb-md")

        table = ui.table(
            columns=_COLUMNS,
            rows=[],
            row_key="id",
            pagination={"rowsPerPage": 20},
        ).classes("w-full shadow-1")

        # Cache task templates for selectors
        task_template_options: dict[int, str] = {}

        async def _load_task_templates() -> None:
            nonlocal task_template_options
            try:
                templates = await api_get("/task-templates")
                task_template_options = {t["id"]: t["name"] for t in templates}
            except Exception:
                task_template_options = {}

        async def refresh() -> None:
            await _load_task_templates()
            try:
                items = await api_get("/document-types/all")
                rows = []
                for item in items:
                    rows.append({
                        "id": item["id"],
                        "name": item.get("name", ""),
                        "category": item.get("category", ""),
                        "base_effort_hours": item.get("base_effort_hours", 0),
                        "task_template_id": item.get("task_template_id"),
                        "task_template_name": item.get("task_template_name") or "—",
                        "description": item.get("description") or "",
                        "is_active": "Yes" if item.get("is_active") else "No",
                    })
                table.rows = rows
                table.update()
            except Exception as exc:
                ui.notify(f"Failed to load: {exc}", type="negative")

        # Add dialog
        async def _open_add_dialog() -> None:
            tt_opts = {0: "— None —", **task_template_options}
            with ui.dialog() as dlg, ui.card().classes("w-[500px]"):
                ui.label("Add Document Type").classes("text-h6 q-mb-sm")
                name_inp = ui.input(label="Name", placeholder="e.g., Test Report").classes("w-full")
                cat_inp = ui.select(label="Category", options=_CATEGORIES, value="Report").classes("w-full")
                hours_inp = ui.number(label="Base Effort Hours", value=4.0, min=0.5, step=0.5).classes("w-full")
                tt_inp = ui.select(label="Linked Task Template", options=tt_opts, value=0).classes("w-full")
                ui.label("Links this document type's effort to a specific task template.").classes("text-caption text-grey")
                desc_inp = ui.textarea(label="Description", placeholder="Optional").classes("w-full").props("rows=2")

                async def _save() -> None:
                    name = (name_inp.value or "").strip()
                    if not name:
                        ui.notify("Name is required.", type="warning")
                        return
                    try:
                        payload = {
                            "name": name,
                            "category": cat_inp.value or "Report",
                            "base_effort_hours": float(hours_inp.value or 4.0),
                            "description": (desc_inp.value or "").strip() or None,
                            "task_template_id": tt_inp.value if tt_inp.value else None,
                        }
                        await api_post("/document-types", json=payload)
                        ui.notify(f"Document type '{name}' created.", type="positive")
                        dlg.close()
                        await refresh()
                    except Exception as exc:
                        ui.notify(f"Failed: {exc}", type="negative")

                with ui.row().classes("q-mt-md gap-2"):
                    ui.button("Save", on_click=_save).props("color=primary")
                    ui.button("Cancel", on_click=dlg.close).props("flat")
            dlg.open()

        # Edit dialog
        async def _open_edit_dialog(e) -> None:
            row = e.args[1] if isinstance(e.args, list) and len(e.args) > 1 else {}
            if not row or "id" not in row:
                return
            item_id = row["id"]
            tt_opts = {0: "— None —", **task_template_options}
            current_tt = row.get("task_template_id") or 0

            with ui.dialog() as dlg, ui.card().classes("w-[500px]"):
                ui.label("Edit Document Type").classes("text-h6 q-mb-sm")
                name_inp = ui.input(label="Name", value=row.get("name", "")).classes("w-full")
                cat_inp = ui.select(label="Category", options=_CATEGORIES, value=row.get("category", "Report")).classes("w-full")
                hours_inp = ui.number(label="Base Effort Hours", value=float(row.get("base_effort_hours", 4.0)), min=0.5, step=0.5).classes("w-full")
                tt_inp = ui.select(label="Linked Task Template", options=tt_opts, value=current_tt).classes("w-full")
                ui.label("Links this document type's effort to a specific task template.").classes("text-caption text-grey")
                desc_inp = ui.textarea(label="Description", value=row.get("description", "")).classes("w-full").props("rows=2")
                active_inp = ui.switch("Active", value=row.get("is_active") == "Yes")

                async def _update() -> None:
                    try:
                        await api_put(f"/document-types/{item_id}", json={
                            "name": (name_inp.value or "").strip() or None,
                            "category": cat_inp.value or None,
                            "base_effort_hours": float(hours_inp.value or 4.0),
                            "task_template_id": tt_inp.value if tt_inp.value else None,
                            "description": (desc_inp.value or "").strip() or None,
                            "is_active": active_inp.value,
                        })
                        ui.notify("Document type updated.", type="positive")
                        dlg.close()
                        await refresh()
                    except Exception as exc:
                        ui.notify(f"Failed: {exc}", type="negative")

                with ui.row().classes("q-mt-md gap-2"):
                    ui.button("Update", on_click=_update).props("color=primary")
                    ui.button("Cancel", on_click=dlg.close).props("flat")
            dlg.open()

        table.on("rowClick", _open_edit_dialog)

        ui.button("Add Document Type", icon="add", on_click=_open_add_dialog).props("color=primary")

        await refresh()
