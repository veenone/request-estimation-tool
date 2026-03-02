"""DUT Registry page — full CRUD.

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
    is_authenticated,
    sidebar,
)

_DEFAULT_CATEGORIES = ["SIM", "eSIM", "UICC", "IoT Device", "Mobile Device", "Other"]

_COLUMNS = [
    {"name": "id",                    "label": "ID",          "field": "id",                    "align": "left", "sortable": True},
    {"name": "name",                  "label": "Name",         "field": "name",                  "align": "left", "sortable": True},
    {"name": "category",              "label": "Category",     "field": "category",              "align": "left", "sortable": True},
    {"name": "complexity_multiplier", "label": "Multiplier",   "field": "complexity_multiplier", "align": "left", "sortable": True},
    {"name": "actions",               "label": "Actions",      "field": "actions",               "align": "left"},
]


@ui.page("/duts")
async def duts_page() -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    with ui.column().classes("q-pa-lg w-full"):
        ui.label("DUT Registry").classes("text-h4 q-mb-md")

        # ------------------------------------------------------------------ #
        # Table                                                                #
        # ------------------------------------------------------------------ #
        table = ui.table(
            columns=_COLUMNS,
            rows=[],
            row_key="id",
            pagination={"rowsPerPage": 20},
        ).classes("w-full shadow-1")

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
        # Fetch configurable categories                                          #
        # ------------------------------------------------------------------ #
        try:
            categories: list[str] = await api_get("/dut-categories")
        except Exception:
            categories = _DEFAULT_CATEGORIES

        # ------------------------------------------------------------------ #
        # Refresh helper                                                        #
        # ------------------------------------------------------------------ #
        async def refresh() -> None:
            try:
                rows: list = await api_get("/dut-types")
                table.rows = rows
                table.update()
            except Exception as exc:
                ui.notify(f"Failed to load DUT types: {exc}", type="negative")

        # ------------------------------------------------------------------ #
        # Add dialog                                                            #
        # ------------------------------------------------------------------ #
        async def show_add_dialog() -> None:
            with ui.dialog() as dialog, ui.card().classes("w-96"):
                ui.label("Add DUT Type").classes("text-h6 q-mb-sm")

                name_input = ui.input("Name *").classes("w-full")
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
                    options=["", "Payment", "Telco"],
                    label="Product Type (optional)",
                    value="",
                    with_input=True,
                    clearable=True,
                ).classes("w-full")

                async def save() -> None:
                    if not name_input.value or not str(name_input.value).strip():
                        ui.notify("Name is required.", type="warning")
                        return
                    try:
                        payload: dict = {
                            "name": str(name_input.value).strip(),
                            "category": category_select.value,
                            "complexity_multiplier": float(multiplier_input.value or 1.0),
                        }
                        if product_type_input.value:
                            payload["product_type"] = product_type_input.value
                        await api_post(
                            "/dut-types",
                            json=payload,
                        )
                        dialog.close()
                        ui.notify("DUT type created.", type="positive")
                        await refresh()
                    except Exception as exc:
                        ui.notify(f"Error creating DUT type: {exc}", type="negative")

                with ui.row().classes("q-mt-md justify-end w-full"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    ui.button("Save", on_click=save).props("color=primary")

            dialog.open()

        # ------------------------------------------------------------------ #
        # Edit dialog                                                           #
        # ------------------------------------------------------------------ #
        async def show_edit_dialog(row: dict) -> None:
            with ui.dialog() as dialog, ui.card().classes("w-96"):
                ui.label("Edit DUT Type").classes("text-h6 q-mb-sm")

                name_input = ui.input("Name *", value=row.get("name", "")).classes("w-full")
                category_select = ui.select(
                    categories,
                    label="Category",
                    value=row.get("category", categories[0] if categories else "Other"),
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
                    options=["", "Payment", "Telco"],
                    label="Product Type (optional)",
                    value=row.get("product_type") or "",
                    with_input=True,
                    clearable=True,
                ).classes("w-full")

                async def save() -> None:
                    if not name_input.value or not str(name_input.value).strip():
                        ui.notify("Name is required.", type="warning")
                        return
                    try:
                        payload: dict = {
                            "name": str(name_input.value).strip(),
                            "category": category_select.value,
                            "complexity_multiplier": float(multiplier_input.value or 1.0),
                            "product_type": product_type_input.value if product_type_input.value else None,
                        }
                        await api_put(
                            f"/dut-types/{row['id']}",
                            json=payload,
                        )
                        dialog.close()
                        ui.notify("DUT type updated.", type="positive")
                        await refresh()
                    except Exception as exc:
                        ui.notify(f"Error updating DUT type: {exc}", type="negative")

                with ui.row().classes("q-mt-md justify-end w-full"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    ui.button("Save", on_click=save).props("color=primary")

            dialog.open()

        # ------------------------------------------------------------------ #
        # Delete confirmation dialog                                            #
        # ------------------------------------------------------------------ #
        async def show_delete_dialog(row: dict) -> None:
            with ui.dialog() as dialog, ui.card().classes("w-80"):
                ui.label("Delete DUT Type").classes("text-h6")
                ui.label(
                    f"Delete '{row.get('name', '')}' (ID {row.get('id')})? "
                    "This cannot be undone."
                ).classes("text-body2 q-mt-sm")

                async def confirm() -> None:
                    try:
                        await api_delete(f"/dut-types/{row['id']}")
                        dialog.close()
                        ui.notify("DUT type deleted.", type="positive")
                        await refresh()
                    except Exception as exc:
                        ui.notify(f"Error deleting DUT type: {exc}", type="negative")

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
        # Toolbar: Add button                                                   #
        # ------------------------------------------------------------------ #
        with ui.row().classes("justify-end q-mb-md"):
            ui.button(
                "Add DUT Type",
                icon="add",
                on_click=show_add_dialog,
            ).props("color=primary")

        # ------------------------------------------------------------------ #
        # Initial data load                                                     #
        # ------------------------------------------------------------------ #
        await refresh()
