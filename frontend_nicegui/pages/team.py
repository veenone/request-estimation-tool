"""Team Management page — full CRUD for team members.

Supports: list, add, edit, delete with confirmation dialog.

Route: /team
API:
  GET    /team-members
  POST   /team-members
  PUT    /team-members/{id}
  DELETE /team-members/{id}
"""

from nicegui import ui

from frontend_nicegui.app import (
    api_delete,
    api_get,
    api_post,
    api_put,
    current_user,
    is_authenticated,
    sidebar,
)

_ROLES = ["TESTER", "LEADER", "MANAGER"]


@ui.page("/team")
async def team_page() -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    # ---------------------------------------------------------------------------
    # Page-level state
    # ---------------------------------------------------------------------------
    members: list[dict] = []
    table_ref: ui.table | None = None

    # ---------------------------------------------------------------------------
    # Data helpers
    # ---------------------------------------------------------------------------
    async def load_members() -> None:
        nonlocal members
        try:
            data = await api_get("/team-members")
            members = data if isinstance(data, list) else []
        except Exception as exc:
            ui.notify(f"Failed to load team members: {exc}", type="negative")
            members = []

    async def refresh_table() -> None:
        await load_members()
        if table_ref is not None:
            table_ref.rows = members
            table_ref.update()

    # ---------------------------------------------------------------------------
    # Add dialog
    # ---------------------------------------------------------------------------
    async def open_add_dialog() -> None:
        with ui.dialog() as dialog, ui.card().classes("w-[460px]"):
            ui.label("Add Team Member").classes("text-h6")
            ui.separator()

            f_name = ui.input("Name *").classes("w-full")
            f_role = ui.select(
                label="Role *", options=_ROLES, value="TESTER"
            ).classes("w-full")
            f_hours = ui.number(
                "Available Hours / Day",
                value=7.0,
                min=0.0,
                max=24.0,
                step=0.5,
                format="%.1f",
            ).classes("w-full")
            f_skills = ui.textarea(
                "Skills JSON (array of strings)", value="[]"
            ).classes("w-full")

            async def submit() -> None:
                if not f_name.value or not f_name.value.strip():
                    ui.notify("Name is required.", type="warning")
                    return

                payload = {
                    "name": f_name.value.strip(),
                    "role": f_role.value,
                    "available_hours_per_day": f_hours.value or 7.0,
                    "skills_json": f_skills.value or "[]",
                }
                try:
                    await api_post("/team-members", json=payload)
                    ui.notify("Team member added.", type="positive")
                    dialog.close()
                    await refresh_table()
                except Exception as exc:
                    ui.notify(f"Error adding member: {exc}", type="negative")

            with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Add Member", on_click=submit).props("color=primary")

        dialog.open()

    # ---------------------------------------------------------------------------
    # Edit dialog
    # ---------------------------------------------------------------------------
    async def open_edit_dialog(member: dict) -> None:
        with ui.dialog() as dialog, ui.card().classes("w-[460px]"):
            ui.label(f"Edit: {member.get('name', '')}").classes("text-h6")
            ui.separator()

            f_name = ui.input("Name *", value=member.get("name", "")).classes("w-full")
            f_role = ui.select(
                label="Role *",
                options=_ROLES,
                value=member.get("role", "TESTER"),
            ).classes("w-full")
            f_hours = ui.number(
                "Available Hours / Day",
                value=member.get("available_hours_per_day", 7.0),
                min=0.0,
                max=24.0,
                step=0.5,
                format="%.1f",
            ).classes("w-full")
            f_skills = ui.textarea(
                "Skills JSON (array of strings)",
                value=member.get("skills_json", "[]"),
            ).classes("w-full")

            async def submit() -> None:
                if not f_name.value or not f_name.value.strip():
                    ui.notify("Name is required.", type="warning")
                    return

                payload = {
                    "name": f_name.value.strip(),
                    "role": f_role.value,
                    "available_hours_per_day": f_hours.value or 7.0,
                    "skills_json": f_skills.value or "[]",
                }
                try:
                    await api_put(f"/team-members/{member['id']}", json=payload)
                    ui.notify("Team member updated.", type="positive")
                    dialog.close()
                    await refresh_table()
                except Exception as exc:
                    ui.notify(f"Error updating member: {exc}", type="negative")

            with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Save Changes", on_click=submit).props("color=primary")

        dialog.open()

    # ---------------------------------------------------------------------------
    # Delete confirmation dialog
    # ---------------------------------------------------------------------------
    async def open_delete_dialog(member: dict) -> None:
        with ui.dialog() as dialog, ui.card().classes("w-[400px]"):
            ui.label("Confirm Delete").classes("text-h6")
            ui.separator()
            ui.label(
                f"Delete team member '{member.get('name', '')}'? This cannot be undone."
            )

            async def confirm() -> None:
                try:
                    await api_delete(f"/team-members/{member['id']}")
                    ui.notify("Team member deleted.", type="positive")
                    dialog.close()
                    await refresh_table()
                except Exception as exc:
                    ui.notify(f"Error deleting member: {exc}", type="negative")

            with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Delete", on_click=confirm).props("color=negative")

        dialog.open()

    # ---------------------------------------------------------------------------
    # Page layout
    # ---------------------------------------------------------------------------
    with ui.column().classes("q-pa-lg w-full"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Team Management").classes("text-h4")
            ui.button(
                "Add Member", icon="person_add", on_click=open_add_dialog
            ).props("color=primary")

        await load_members()

        columns = [
            {"name": "id", "label": "ID", "field": "id", "sortable": True, "align": "left"},
            {"name": "name", "label": "Name", "field": "name", "sortable": True, "align": "left"},
            {"name": "role", "label": "Role", "field": "role", "sortable": True, "align": "left"},
            {"name": "available_hours_per_day", "label": "Hrs/Day", "field": "available_hours_per_day", "sortable": True, "align": "right"},
            {"name": "skills_json", "label": "Skills", "field": "skills_json", "align": "left"},
            {"name": "actions", "label": "Actions", "field": "actions", "align": "center"},
        ]

        table_ref = ui.table(
            columns=columns,
            rows=members,
            row_key="id",
            pagination={"rowsPerPage": 20},
        ).classes("w-full")

        # Render role with a colored chip
        table_ref.add_slot(
            "body-cell-role",
            r"""
            <q-td :props="props">
                <q-badge
                    :color="props.value === 'LEADER' ? 'purple'
                           : props.value === 'MANAGER' ? 'blue' : 'teal'"
                    :label="props.value"
                />
            </q-td>
            """,
        )

        # Truncate long skills JSON for display
        table_ref.add_slot(
            "body-cell-skills_json",
            r"""
            <q-td :props="props">
                <span class="text-caption text-grey">
                    {{ props.value && props.value.length > 60
                       ? props.value.substring(0, 60) + '…'
                       : props.value }}
                </span>
            </q-td>
            """,
        )

        # Action buttons — passed through a scoped slot so each row carries its data
        table_ref.add_slot(
            "body-cell-actions",
            r"""
            <q-td :props="props">
                <q-btn flat round icon="edit" size="sm"
                       @click="$parent.$emit('edit', props.row)" />
                <q-btn flat round icon="delete" size="sm" color="negative"
                       @click="$parent.$emit('delete', props.row)" />
            </q-td>
            """,
        )

        table_ref.on("edit", lambda e: open_edit_dialog(e.args))
        table_ref.on("delete", lambda e: open_delete_dialog(e.args))

        if not members:
            ui.label("No team members found.").classes("text-grey q-mt-md")
