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
    extract_error_detail,
    is_authenticated,
    sidebar,
)

_DEFAULT_CATEGORIES = ["Telecom", "Security", "Platform", "Other"]

_COLUMNS = [
    {"name": "id",                 "label": "ID",          "field": "id",                 "align": "left", "sortable": True},
    {"name": "name",               "label": "Name",         "field": "name",               "align": "left", "sortable": True},
    {"name": "category",           "label": "Category",     "field": "category",           "align": "left", "sortable": True},
    {"name": "product_type",       "label": "Product Type", "field": "product_type",       "align": "left", "sortable": True},
    {"name": "complexity_weight",    "label": "Complexity",       "field": "complexity_weight",  "align": "left", "sortable": True},
    {"name": "study_effort_hours",  "label": "Study Effort (h)", "field": "study_effort_hours", "align": "left", "sortable": True},
    {"name": "has_existing_tests",  "label": "Has Tests",        "field": "has_existing_tests", "align": "left"},
    {"name": "actions",             "label": "Actions",          "field": "actions",            "align": "left"},
]


@ui.page("/features")
async def features_page() -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    # Fetch categories and product types from config
    try:
        categories: list[str] = await api_get("/feature-categories")
    except Exception:
        categories = list(_DEFAULT_CATEGORIES)
    try:
        product_types: list[str] = await api_get("/configuration/product_types")
    except Exception:
        product_types = ["Payment", "Telco"]

    with ui.column().classes("q-pa-lg w-full"):
        ui.label("Feature Catalog").classes("text-h4 q-mb-md")

        # ------------------------------------------------------------------ #
        # Mutable state — a plain list so closures always see the latest ref  #
        # ------------------------------------------------------------------ #
        state: dict = {"rows": [], "filter_category": "All", "filter_product_type": "All"}

        # ------------------------------------------------------------------ #
        # Table                                                                #
        # ------------------------------------------------------------------ #
        table = ui.table(
            columns=_COLUMNS,
            rows=[],
            row_key="id",
            pagination={"rowsPerPage": 15},
        ).classes("w-full shadow-1")

        # Render category as a badge
        table.add_slot(
            "body-cell-category",
            r"""
            <q-td :props="props">
                <q-badge outline color="primary" :label="props.value || '—'" />
            </q-td>
            """,
        )

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

        # Render study effort — show "Default" when null
        table.add_slot(
            "body-cell-study_effort_hours",
            r"""
            <q-td :props="props">
                <span v-if="props.value != null">{{ props.value }}h</span>
                <span v-else class="text-grey-6 text-italic">Default</span>
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
                    @click="() => $parent.$emit('edit-row', props.row)"
                    class="q-mr-xs"
                />
                <q-btn
                    dense flat round icon="delete" color="negative" size="sm"
                    @click="() => $parent.$emit('delete-row', props.row)"
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
                state["rows"] = all_rows
                cat = state.get("filter_category") or "All"
                pt = state.get("filter_product_type") or "All"
                filtered = list(all_rows)
                if cat != "All":
                    filtered = [r for r in filtered if r.get("category") == cat]
                if pt != "All":
                    filtered = [r for r in filtered if (r.get("product_type") or "") == pt]
                table.rows = filtered
                table.update()
            except Exception as exc:
                ui.notify(
                    f"Failed to load features: {extract_error_detail(exc)}",
                    type="negative",
                    timeout=6000,
                    multi_line=True,
                    close_button="OK",
                )

        # ------------------------------------------------------------------ #
        # Add dialog                                                            #
        # ------------------------------------------------------------------ #
        async def show_add_dialog() -> None:
            with ui.dialog() as dialog, ui.card().classes("w-96"):
                ui.label("Add Feature").classes("text-h6 q-mb-sm")

                name_input = ui.input("Name *").classes("w-full")
                category_select = ui.select(
                    categories,
                    label="Category",
                    value=categories[0] if categories else "",
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
                study_effort_input = ui.number(
                    "Study Effort Hours (blank = use global default)",
                    value=None,
                    min=0,
                    max=200,
                    step=1,
                    format="%.1f",
                ).classes("w-full")
                ui.label(
                    "Hours of study effort when this feature is new. "
                    "Leave blank to use global 'new_feature_study_hours' setting."
                ).classes("text-caption text-grey")

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
                            "study_effort_hours": float(study_effort_input.value) if study_effort_input.value is not None else None,
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
                        ui.notify(
                            extract_error_detail(exc),
                            type="negative",
                            timeout=6000,
                            multi_line=True,
                            close_button="OK",
                        )

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
                row_cat = row.get("category", "")
                edit_cat_options = list(categories)
                if row_cat and row_cat not in edit_cat_options:
                    edit_cat_options.append(row_cat)
                category_select = ui.select(
                    edit_cat_options,
                    label="Category",
                    value=row_cat or (edit_cat_options[0] if edit_cat_options else ""),
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
                study_effort_input = ui.number(
                    "Study Effort Hours (blank = use global default)",
                    value=row.get("study_effort_hours"),
                    min=0,
                    max=200,
                    step=1,
                    format="%.1f",
                ).classes("w-full")
                ui.label(
                    "Hours of study effort when this feature is new. "
                    "Leave blank to use global 'new_feature_study_hours' setting."
                ).classes("text-caption text-grey")

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
                            "study_effort_hours": float(study_effort_input.value) if study_effort_input.value is not None else None,
                        }
                        await api_put(
                            f"/features/{row['id']}",
                            json=payload,
                        )
                        dialog.close()
                        ui.notify("Feature updated.", type="positive")
                        await refresh()
                    except Exception as exc:
                        ui.notify(
                            extract_error_detail(exc),
                            type="negative",
                            timeout=6000,
                            multi_line=True,
                            close_button="OK",
                        )

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
                        ui.notify(
                            extract_error_detail(exc),
                            type="negative",
                            timeout=6000,
                            multi_line=True,
                            close_button="OK",
                        )

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
        # Manage Categories dialog                                             #
        # ------------------------------------------------------------------ #
        async def show_manage_categories_dialog() -> None:
            with ui.dialog() as cat_dialog, ui.card().classes("w-96"):
                ui.label("Manage Feature Categories").classes("text-h6 q-mb-sm")

                cat_list_container = ui.column().classes("w-full q-gutter-y-xs")

                def _rebuild_list_sync() -> None:
                    cat_list_container.clear()
                    with cat_list_container:
                        if not categories:
                            ui.label("No categories defined.").classes("text-grey text-italic")
                        for cat_name in list(categories):
                            with ui.row().classes("items-center w-full"):
                                ui.label(cat_name).classes("text-body1 q-mr-auto")
                                ui.button(
                                    icon="delete", on_click=lambda _, c=cat_name: _remove(c)
                                ).props("flat dense round color=negative size=sm")

                async def _save_categories() -> None:
                    try:
                        await api_put(
                            "/configuration/feature_categories",
                            json={"value": ",".join(categories)},
                        )
                    except Exception as exc:
                        ui.notify(f"Failed to save categories: {exc}", type="negative")

                async def _remove(name: str) -> None:
                    categories.remove(name)
                    await _save_categories()
                    _rebuild_list_sync()
                    category_filter_select.set_options(["All"] + categories)
                    ui.notify(f"Removed '{name}'.", type="info")

                async def _add() -> None:
                    val = str(new_cat_input.value or "").strip()
                    if not val:
                        ui.notify("Enter a category name.", type="warning")
                        return
                    if val in categories:
                        ui.notify(f"'{val}' already exists.", type="warning")
                        return
                    categories.append(val)
                    await _save_categories()
                    new_cat_input.value = ""
                    _rebuild_list_sync()
                    category_filter_select.set_options(["All"] + categories)
                    ui.notify(f"Added '{val}'.", type="positive")

                _rebuild_list_sync()

                ui.separator().classes("q-my-sm")
                with ui.row().classes("items-center w-full q-gutter-sm"):
                    new_cat_input = ui.input("New category").classes("q-mr-auto")
                    ui.button("Add", icon="add", on_click=_add).props("color=primary dense")

                with ui.row().classes("q-mt-md justify-end w-full"):
                    ui.button("Close", on_click=cat_dialog.close).props("flat")

            cat_dialog.open()

        # ------------------------------------------------------------------ #
        # Toolbar: category filter + Add button                                #
        # ------------------------------------------------------------------ #
        with ui.row().classes("items-center q-gutter-sm q-mb-md"):
            ui.label("Filter:").classes("text-body2")

            async def on_category_change(e) -> None:
                state["filter_category"] = e.value if e.value else "All"
                await refresh()

            category_filter_select = ui.select(
                ["All"] + categories,
                label="Category",
                value="All",
                on_change=on_category_change,
            ).classes("w-40")

            async def on_product_type_change(e) -> None:
                state["filter_product_type"] = e.value if e.value else "All"
                await refresh()

            ui.select(
                ["All"] + product_types,
                label="Product Type",
                value="All",
                on_change=on_product_type_change,
            ).classes("w-48")

            ui.button(
                "Manage Categories",
                icon="settings",
                on_click=show_manage_categories_dialog,
            ).props("flat dense")

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
