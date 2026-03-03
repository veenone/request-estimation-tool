"""Team Management page — full CRUD for team members.

Supports: list, add, edit, delete with confirmation dialog.

Route: /team
API:
  GET    /team-members
  POST   /team-members
  PUT    /team-members/{id}
  DELETE /team-members/{id}
"""

import json as _json

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
_DEFAULT_SKILLS = ["Test Execution", "Test Design", "Automation", "Performance", "Security", "API Testing", "Mobile Testing", "Regression"]


def _parse_skills(raw: str) -> list[str]:
    """Parse a skills_json string into a list of strings."""
    try:
        result = _json.loads(raw) if raw else []
        return result if isinstance(result, list) else []
    except (_json.JSONDecodeError, TypeError):
        return []


@ui.page("/team")
async def team_page() -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    # Fetch available skills from config
    try:
        available_skills: list[str] = await api_get("/configuration/team_skills")
    except Exception:
        available_skills = _DEFAULT_SKILLS

    # Fetch users for linked user select
    try:
        all_users: list[dict] = await api_get("/users/assignable")
    except Exception:
        all_users = []

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
            f_skills = ui.select(
                label="Skills",
                options=available_skills,
                value=[],
                multiple=True,
            ).classes("w-full").props("use-chips")

            # Linked user select
            user_options = {0: "(None)"} | {
                u["id"]: f"{u.get('display_name', u.get('username', ''))}"
                for u in all_users
            }
            f_linked_user = ui.select(
                label="Linked User (optional)",
                options=user_options,
                value=0,
            ).classes("w-full")

            async def submit() -> None:
                if not f_name.value or not f_name.value.strip():
                    ui.notify("Name is required.", type="warning")
                    return

                selected_skills = f_skills.value if f_skills.value else []
                payload = {
                    "name": f_name.value.strip(),
                    "role": f_role.value,
                    "available_hours_per_day": f_hours.value or 7.0,
                    "skills_json": _json.dumps(selected_skills),
                }
                try:
                    new_member = await api_post("/team-members", json=payload)
                    # Link user if selected
                    linked_uid = f_linked_user.value
                    if linked_uid and linked_uid != 0 and new_member:
                        try:
                            from frontend_nicegui.app import api_put as _api_put
                            await _api_put(f"/users/{linked_uid}", json={"team_member_id": new_member["id"]})
                        except Exception:
                            pass
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
        existing_skills = _parse_skills(member.get("skills_json", "[]"))

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
            f_skills = ui.select(
                label="Skills",
                options=available_skills,
                value=existing_skills,
                multiple=True,
            ).classes("w-full").props("use-chips")

            # Linked user select
            user_options = {0: "(None)"} | {
                u["id"]: f"{u.get('display_name', u.get('username', ''))}"
                for u in all_users
            }
            current_linked = member.get("linked_user_id") or 0
            f_linked_user = ui.select(
                label="Linked User (optional)",
                options=user_options,
                value=current_linked,
            ).classes("w-full")

            async def submit() -> None:
                if not f_name.value or not f_name.value.strip():
                    ui.notify("Name is required.", type="warning")
                    return

                selected_skills = f_skills.value if f_skills.value else []
                payload = {
                    "name": f_name.value.strip(),
                    "role": f_role.value,
                    "available_hours_per_day": f_hours.value or 7.0,
                    "skills_json": _json.dumps(selected_skills),
                }
                try:
                    await api_put(f"/team-members/{member['id']}", json=payload)
                    # Update linked user
                    new_linked = f_linked_user.value if f_linked_user.value != 0 else None
                    old_linked = member.get("linked_user_id")
                    if new_linked != old_linked:
                        # Unlink old user
                        if old_linked:
                            try:
                                await api_put(f"/users/{old_linked}", json={"team_member_id": None})
                            except Exception:
                                pass
                        # Link new user
                        if new_linked:
                            try:
                                await api_put(f"/users/{new_linked}", json={"team_member_id": member["id"]})
                            except Exception:
                                pass
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
    # Team CRUD
    # ---------------------------------------------------------------------------
    teams: list[dict] = []

    async def load_teams() -> list[dict]:
        nonlocal teams
        try:
            teams = await api_get("/teams")
        except Exception:
            teams = []
        return teams

    async def open_create_team_dialog() -> None:
        with ui.dialog() as dialog, ui.card().classes("w-[420px]"):
            ui.label("Create Team").classes("text-h6")
            ui.separator()
            f_name = ui.input("Team Name *").classes("w-full")
            f_desc = ui.textarea("Description").classes("w-full")

            async def submit() -> None:
                if not f_name.value or not f_name.value.strip():
                    ui.notify("Team name is required.", type="warning")
                    return
                try:
                    await api_post("/teams", json={"name": f_name.value.strip(), "description": (f_desc.value or "").strip() or None})
                    ui.notify("Team created.", type="positive")
                    dialog.close()
                    ui.navigate.to("/team")
                except Exception as exc:
                    ui.notify(f"Error: {exc}", type="negative")

            with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Create", on_click=submit).props("color=primary")
        dialog.open()

    async def open_manage_team_dialog(team: dict) -> None:
        with ui.dialog() as dialog, ui.card().classes("w-[520px]"):
            ui.label(f"Manage Team: {team.get('name', '')}").classes("text-h6")
            ui.separator()

            # Show current members and allow add/remove
            all_members = members or []
            current_team_members = [m for m in all_members if m.get("team_id") == team["id"]]
            available_members = [m for m in all_members if m.get("team_id") is None or m.get("team_id") == team["id"]]

            member_options = {m["id"]: m["name"] for m in available_members}
            pre_selected = [m["id"] for m in current_team_members]
            f_members = ui.select(
                label="Team Members",
                options=member_options,
                value=pre_selected,
                multiple=True,
            ).classes("w-full").props("use-chips")

            async def save_members() -> None:
                try:
                    await api_put(f"/teams/{team['id']}/members", json={"member_ids": f_members.value or []})
                    ui.notify("Team members updated.", type="positive")
                    dialog.close()
                    ui.navigate.to("/team")
                except Exception as exc:
                    ui.notify(f"Error: {exc}", type="negative")

            with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Save", on_click=save_members).props("color=primary")
        dialog.open()

    async def delete_team(team: dict) -> None:
        try:
            await api_delete(f"/teams/{team['id']}")
            ui.notify("Team deleted.", type="positive")
            ui.navigate.to("/team")
        except Exception as exc:
            ui.notify(f"Error: {exc}", type="negative")

    # ---------------------------------------------------------------------------
    # Page layout
    # ---------------------------------------------------------------------------
    with ui.column().classes("q-pa-lg w-full"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Team Management").classes("text-h4")
            with ui.row().classes("gap-2"):
                ui.button(
                    "Create Team", icon="group_add", on_click=open_create_team_dialog
                ).props("color=secondary outline")
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
            {"name": "linked_user_name", "label": "Linked User", "field": "linked_user_name", "sortable": True, "align": "left"},
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

        # Parse skills JSON and show as chips
        table_ref.add_slot(
            "body-cell-skills_json",
            r"""
            <q-td :props="props">
                <template v-if="props.value">
                    <q-chip v-for="skill in (() => { try { const s = JSON.parse(props.value); return Array.isArray(s) ? s : []; } catch(e) { return []; } })()"
                            :key="skill" dense size="sm" color="teal" text-color="white" class="q-mr-xs">
                        {{ skill }}
                    </q-chip>
                </template>
                <span v-else class="text-caption text-grey">—</span>
            </q-td>
            """,
        )

        # Linked user column
        table_ref.add_slot(
            "body-cell-linked_user_name",
            r"""
            <q-td :props="props">
                <span :class="props.value ? '' : 'text-grey'">{{ props.value || '—' }}</span>
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

        # ----- Teams section -----
        ui.separator().classes("q-my-lg")
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Teams").classes("text-h5")

        await load_teams()
        if teams:
            with ui.row().classes("flex-wrap q-gutter-md q-mt-sm"):
                for team in teams:
                    with ui.card().classes("q-pa-md w-64"):
                        ui.label(team.get("name", "")).classes("text-h6")
                        if team.get("description"):
                            ui.label(team["description"]).classes("text-caption text-grey")
                        ui.label(f"{team.get('member_count', 0)} member(s)").classes("text-body2 q-mt-xs")
                        with ui.row().classes("q-mt-sm gap-1"):
                            ui.button("Manage", icon="settings", on_click=lambda t=team: open_manage_team_dialog(t)).props("flat dense color=primary size=sm")
                            ui.button("Delete", icon="delete", on_click=lambda t=team: delete_team(t)).props("flat dense color=negative size=sm")
        else:
            ui.label("No teams created yet.").classes("text-grey q-mt-md")
