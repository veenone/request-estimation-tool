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
    is_authenticated,
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

            f_name = ui.input("Project Name *").classes("w-full")
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
                if not f_name.value or not f_name.value.strip():
                    ui.notify("Project Name is required.", type="warning")
                    return

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
                try:
                    await api_post("/historical-projects", json=payload)
                    ui.notify("Project added successfully.", type="positive")
                    dialog.close()
                    await refresh_table()
                except Exception as exc:
                    ui.notify(f"Error adding project: {exc}", type="negative")

            with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Add Project", on_click=submit).props("color=primary")

        dialog.open()

    # ---------------------------------------------------------------------------
    # Table refresh
    # ---------------------------------------------------------------------------
    async def refresh_table() -> None:
        await load_projects()
        if table_ref is not None:
            table_ref.rows = projects
            table_ref.update()

    # ---------------------------------------------------------------------------
    # Page layout
    # ---------------------------------------------------------------------------
    with ui.column().classes("q-pa-lg w-full"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Historical Projects").classes("text-h4")
            with ui.row().classes("gap-2"):
                ui.button(
                    "Refresh", icon="refresh", on_click=refresh_table
                ).props("outline")
                user = current_user()
                role = user.get("role", "VIEWER") if user else "VIEWER"
                if role in ("APPROVER", "ADMIN"):
                    ui.button(
                        "Add Project", icon="add", on_click=open_add_dialog
                    ).props("color=primary")

        await load_projects()

        if not projects:
            ui.label("No historical projects found.").classes("text-grey q-mt-md")
        else:
            columns = [
                {"name": "id", "label": "ID", "field": "id", "sortable": True, "align": "left"},
                {"name": "project_name", "label": "Project Name", "field": "project_name", "sortable": True, "align": "left"},
                {"name": "project_type", "label": "Type", "field": "project_type", "sortable": True, "align": "left"},
                {"name": "estimated_hours", "label": "Estimated h", "field": "estimated_hours", "sortable": True, "align": "right"},
                {"name": "actual_hours", "label": "Actual h", "field": "actual_hours", "sortable": True, "align": "right"},
                {"name": "accuracy_ratio", "label": "Accuracy Ratio", "field": "accuracy_ratio", "sortable": True, "align": "right"},
                {"name": "completion_date", "label": "Completion Date", "field": "completion_date", "sortable": True, "align": "left"},
            ]
            table_ref = ui.table(
                columns=columns,
                rows=projects,
                row_key="id",
                pagination={"rowsPerPage": 20},
            ).classes("w-full")
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
