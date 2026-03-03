"""Feature Catalog page — full CRUD with category filter.

Route: /features
API:
  GET    /features
  POST   /features
  PUT    /features/{id}
  DELETE /features/{id}
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

CATEGORIES = ["Telecom", "Security", "Platform", "Other"]

_COLUMNS = [
    {"name": "id",                 "label": "ID",          "field": "id",                 "align": "left", "sortable": True},
    {"name": "name",               "label": "Name",         "field": "name",               "align": "left", "sortable": True},
    {"name": "category",           "label": "Category",     "field": "category",           "align": "left", "sortable": True},
    {"name": "complexity_weight",  "label": "Complexity",   "field": "complexity_weight",  "align": "left", "sortable": True},
    {"name": "has_existing_tests", "label": "Has Tests",    "field": "has_existing_tests", "align": "left"},
    {"name": "actions",            "label": "Actions",      "field": "actions",            "align": "left"},
]


@ui.page("/features")
async def features_page() -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    # Fetch product types from config
    try:
        product_types: list[str] = await api_get("/configuration/product_types")
    except Exception:
        product_types = ["Payment", "Telco"]

    with ui.column().classes("q-pa-lg w-full"):
        ui.label("Feature Catalog").classes("text-h4 q-mb-md")

        # ------------------------------------------------------------------ #
        # Mutable state — a plain list so closures always see the latest ref  #
        # ------------------------------------------------------------------ #
        state: dict = {"rows": [], "filter_category": "All"}

        # ------------------------------------------------------------------ #
        # Table                                                                #
        # ------------------------------------------------------------------ #
        table = ui.table(
            columns=_COLUMNS,
            rows=[],
            row_key="id",
            pagination={"rowsPerPage": 20},
        ).classes("w-full shadow-1")

        # Render boolean as readable text
        table.add_slot(
            "body-cell-has_existing_tests",
            r"""
            <q-td :props="props">
                <q-badge
                    :color="props.value ? 'positive' : 'grey'"
                    :label="props.value ? 'Yes' : 'No'"
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
        # Refresh helper                                                        #
        # ------------------------------------------------------------------ #
        async def refresh() -> None:
            try:
                all_rows: list = await api_get("/features")
                cat = state["filter_category"]
                state["rows"] = all_rows
                if cat and cat != "All":
                    table.rows = [r for r in all_rows if r.get("category") == cat]
                else:
                    table.rows = list(all_rows)
                table.update()
            except Exception as exc:
                ui.notify(f"Failed to load features: {exc}", type="negative")

        # ------------------------------------------------------------------ #
        # Add dialog                                                            #
        # ------------------------------------------------------------------ #
        async def show_add_dialog() -> None:
            with ui.dialog() as dialog, ui.card().classes("w-96"):
                ui.label("Add Feature").classes("text-h6 q-mb-sm")

                name_input = ui.input("Name *").classes("w-full")
                category_select = ui.select(
                    CATEGORIES,
                    label="Category",
                    value=CATEGORIES[0],
                ).classes("w-full")
                complexity_input = ui.number(
                    "Complexity Weight",
                    value=1.0,
                    min=0.1,
                    max=10.0,
                    step=0.5,
                    format="%.1f",
                ).classes("w-full")
                has_tests_toggle = ui.switch("Has Existing Tests", value=False)
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
                    try:
                        payload: dict = {
                            "name": str(name_input.value).strip(),
                            "category": category_select.value,
                            "complexity_weight": float(complexity_input.value or 1.0),
                            "has_existing_tests": bool(has_tests_toggle.value),
                        }
                        if product_type_input.value:
                            payload["product_type"] = product_type_input.value
                        await api_post(
                            "/features",
                            json=payload,
                        )
                        dialog.close()
                        ui.notify("Feature created.", type="positive")
                        await refresh()
                    except Exception as exc:
                        ui.notify(f"Error creating feature: {exc}", type="negative")

                with ui.row().classes("q-mt-md justify-end w-full"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    ui.button("Save", on_click=save).props("color=primary")

            dialog.open()

        # ------------------------------------------------------------------ #
        # Edit dialog                                                           #
        # ------------------------------------------------------------------ #
        async def show_edit_dialog(row: dict) -> None:
            with ui.dialog() as dialog, ui.card().classes("w-96"):
                ui.label("Edit Feature").classes("text-h6 q-mb-sm")

                name_input = ui.input("Name *", value=row.get("name", "")).classes("w-full")
                category_select = ui.select(
                    CATEGORIES,
                    label="Category",
                    value=row.get("category", CATEGORIES[0]),
                ).classes("w-full")
                complexity_input = ui.number(
                    "Complexity Weight",
                    value=float(row.get("complexity_weight", 1.0)),
                    min=0.1,
                    max=10.0,
                    step=0.5,
                    format="%.1f",
                ).classes("w-full")
                has_tests_toggle = ui.switch(
                    "Has Existing Tests",
                    value=bool(row.get("has_existing_tests", False)),
                )
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
                    try:
                        payload: dict = {
                            "name": str(name_input.value).strip(),
                            "category": category_select.value,
                            "complexity_weight": float(complexity_input.value or 1.0),
                            "has_existing_tests": bool(has_tests_toggle.value),
                            "product_type": product_type_input.value if product_type_input.value else None,
                        }
                        await api_put(
                            f"/features/{row['id']}",
                            json=payload,
                        )
                        dialog.close()
                        ui.notify("Feature updated.", type="positive")
                        await refresh()
                    except Exception as exc:
                        ui.notify(f"Error updating feature: {exc}", type="negative")

                with ui.row().classes("q-mt-md justify-end w-full"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    ui.button("Save", on_click=save).props("color=primary")

            dialog.open()

        # ------------------------------------------------------------------ #
        # Delete confirmation dialog                                            #
        # ------------------------------------------------------------------ #
        async def show_delete_dialog(row: dict) -> None:
            with ui.dialog() as dialog, ui.card().classes("w-80"):
                ui.label("Delete Feature").classes("text-h6")
                ui.label(
                    f"Delete '{row.get('name', '')}' (ID {row.get('id')})? "
                    "This cannot be undone."
                ).classes("text-body2 q-mt-sm")

                async def confirm() -> None:
                    try:
                        await api_delete(f"/features/{row['id']}")
                        dialog.close()
                        ui.notify("Feature deleted.", type="positive")
                        await refresh()
                    except Exception as exc:
                        ui.notify(f"Error deleting feature: {exc}", type="negative")

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
        # Toolbar: category filter + Add button                                #
        # ------------------------------------------------------------------ #
        with ui.row().classes("items-center q-gutter-sm q-mb-md"):
            ui.label("Filter by category:").classes("text-body2")

            async def on_category_change(e) -> None:
                state["filter_category"] = e.value
                await refresh()

            ui.select(
                ["All"] + CATEGORIES,
                label="Category",
                value="All",
                on_change=on_category_change,
            ).classes("w-40")

            ui.space()

            ui.button(
                "Add Feature",
                icon="add",
                on_click=show_add_dialog,
            ).props("color=primary")

        # ------------------------------------------------------------------ #
        # Initial data load                                                     #
        # ------------------------------------------------------------------ #
        await refresh()
