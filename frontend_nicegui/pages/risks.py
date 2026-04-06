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

    with ui.column().classes("q-pa-lg w-full"):
        ui.label("Risk Registry").classes("text-h4 q-mb-md")

        # ------------------------------------------------------------------ #
        # Mutable state                                                       #
        # ------------------------------------------------------------------ #
        state: dict = {"rows": []}

        # ------------------------------------------------------------------ #
        # Search input                                                         #
        # ------------------------------------------------------------------ #
        search_input = ui.input(
            placeholder="Search by name, category, likelihood, impact...",
        ).classes("w-full q-mb-sm").props('outlined dense clearable')
        with search_input:
            ui.icon("search").classes("text-grey").props('slot="prepend"')

        # ------------------------------------------------------------------ #
        # Table                                                                #
        # ------------------------------------------------------------------ #
        table = ui.table(
            columns=_COLUMNS,
            rows=[],
            row_key="id",
            pagination={"rowsPerPage": 15},
        ).classes("w-full shadow-1")

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
        # Filter helper                                                        #
        # ------------------------------------------------------------------ #
        def _apply_search() -> None:
            query = (search_input.value or "").strip().lower()
            if not query:
                table.rows = list(state["rows"])
            else:
                table.rows = [
                    r for r in state["rows"]
                    if query in (r.get("name") or "").lower()
                    or query in (r.get("category") or "").lower()
                    or query in (r.get("likelihood") or "").lower()
                    or query in (r.get("impact") or "").lower()
                    or query in (r.get("description") or "").lower()
                    or query in str(r.get("id", ""))
                ]
            table.update()

        search_input.on("update:model-value", lambda _: _apply_search())

        # ------------------------------------------------------------------ #
        # Refresh helper                                                        #
        # ------------------------------------------------------------------ #
        async def refresh() -> None:
            try:
                all_rows: list = await api_get("/risk-items")
                state["rows"] = all_rows
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
        # Toolbar: Add button                                                   #
        # ------------------------------------------------------------------ #
        with ui.row().classes("items-center q-gutter-sm q-mb-md"):
            ui.space()

            ui.button(
                "Add Risk",
                icon="add",
                on_click=show_add_dialog,
            ).props("color=primary")

        # ------------------------------------------------------------------ #
        # Initial data load                                                     #
        # ------------------------------------------------------------------ #
        await refresh()
