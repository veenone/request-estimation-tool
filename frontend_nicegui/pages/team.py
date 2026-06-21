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
    empty_state,
    icon_action,
    is_authenticated,
    loading_state,
    run_async,
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

    search_ref: dict = {"input": None}

    async def refresh_table() -> None:
        await load_members()
        try:
            _total_label.set_text(f"TOTAL · {len(members)}")
            _render_kpis()
            _render_segments()
            _apply_team_filter()
        except NameError:
            # Helpers not yet defined on first run — table_ref still updates below
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

            f_name = ui.input("Name *").classes("w-full").props("autofocus")
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
                label="Skills (type to add new)",
                options=list(available_skills),
                value=[],
                multiple=True,
            ).classes("w-full").props('use-chips use-input new-value-mode="add-unique" input-debounce="0"')

            # Linked user select — sorted ascending, searchable
            sorted_users = sorted(all_users, key=lambda u: (u.get("display_name") or u.get("username", "")).lower())
            user_options = {0: "(None)"} | {
                u["id"]: f"{u.get('display_name', u.get('username', ''))}"
                for u in sorted_users
            }
            f_linked_user = ui.select(
                label="Linked User (optional)",
                options=user_options,
                value=0,
                with_input=True,
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
                new_member = await api_post("/team-members", json=payload)
                # Link user if selected
                linked_uid = f_linked_user.value
                if linked_uid and linked_uid != 0 and new_member:
                    try:
                        from frontend_nicegui.app import api_put as _api_put
                        await _api_put(f"/users/{linked_uid}", json={"team_member_id": new_member["id"]})
                    except Exception:
                        pass
                dialog.close()
                await refresh_table()

            with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                add_btn = ui.button("Add Member").props("color=primary")
                add_btn.on("click", run_async(add_btn, submit, success="Team member added.", error_prefix="Add member failed"))

        dialog.open()

    # ---------------------------------------------------------------------------
    # Edit dialog
    # ---------------------------------------------------------------------------
    async def open_edit_dialog(member: dict) -> None:
        existing_skills = _parse_skills(member.get("skills_json", "[]"))

        with ui.dialog() as dialog, ui.card().classes("w-[460px]"):
            ui.label(f"Edit: {member.get('name', '')}").classes("text-h6")
            ui.separator()

            f_name = ui.input("Name *", value=member.get("name", "")).classes("w-full").props("autofocus")
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
            # Merge existing skills into available options so they appear in the dropdown
            all_skill_options = sorted(set(available_skills) | set(existing_skills))
            f_skills = ui.select(
                label="Skills (type to add new)",
                options=all_skill_options,
                value=existing_skills,
                multiple=True,
            ).classes("w-full").props('use-chips use-input new-value-mode="add-unique" input-debounce="0"')

            # Linked user select — sorted ascending, searchable
            sorted_users = sorted(all_users, key=lambda u: (u.get("display_name") or u.get("username", "")).lower())
            user_options = {0: "(None)"} | {
                u["id"]: f"{u.get('display_name', u.get('username', ''))}"
                for u in sorted_users
            }
            current_linked = member.get("linked_user_id") or 0
            f_linked_user = ui.select(
                label="Linked User (optional)",
                options=user_options,
                value=current_linked,
                with_input=True,
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
                dialog.close()
                await refresh_table()

            with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                save_btn = ui.button("Save Changes").props("color=primary")
                save_btn.on("click", run_async(save_btn, submit, success="Team member updated.", error_prefix="Update failed"))

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
                await api_delete(f"/team-members/{member['id']}")
                dialog.close()
                await refresh_table()

            with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                del_btn = ui.button("Delete").props("color=negative")
                del_btn.on("click", run_async(del_btn, confirm, success="Team member deleted.", error_prefix="Delete failed"))

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
            f_name = ui.input("Team Name *").classes("w-full").props("autofocus")
            f_desc = ui.textarea("Description").classes("w-full")

            async def submit() -> None:
                if not f_name.value or not f_name.value.strip():
                    ui.notify("Team name is required.", type="warning")
                    return
                await api_post("/teams", json={"name": f_name.value.strip(), "description": (f_desc.value or "").strip() or None})
                dialog.close()
                ui.navigate.to("/team")

            with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                create_btn = ui.button("Create").props("color=primary")
                create_btn.on("click", run_async(create_btn, submit, success="Team created.", error_prefix="Create team failed"))
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
                await api_put(f"/teams/{team['id']}/members", json={"member_ids": f_members.value or []})
                dialog.close()
                ui.navigate.to("/team")

            with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                save_members_btn = ui.button("Save").props("color=primary")
                save_members_btn.on("click", run_async(save_members_btn, save_members, success="Team members updated.", error_prefix="Save failed"))
        dialog.open()

    async def delete_team(team: dict) -> None:
        await api_delete(f"/teams/{team['id']}")
        ui.navigate.to("/team")

    # ---------------------------------------------------------------------------
    # State + initial load
    # ---------------------------------------------------------------------------
    state: dict = {"filter_role": "All"}
    async with loading_state("Loading team…"):
        await load_members()

    # ---------------------------------------------------------------------------
    # Page layout
    # ---------------------------------------------------------------------------
    with ui.column().classes("w-full q-pa-md").style("gap: 0;"):

        # ── Sticky toolbar ──────────────────────────────────────
        with ui.element("div").classes("ed-toolbar"):
            ui.button("Add Member", icon="person_add",
                      on_click=lambda: open_add_dialog()) \
                .props("flat dense color=primary")
            ui.element("div").classes("ed-toolbar-spacer")
            ui.button("Create Team", icon="group_add",
                      on_click=lambda: open_create_team_dialog()) \
                .props("flat dense color=secondary")
            ui.element("div").classes("ed-toolbar-grow")
            with ui.element("div").classes("ed-status-now"):
                ui.element("span").classes("ed-status-dot")
                _total_label = ui.label(f"TOTAL · {len(members)}").classes("ed-mono")

        with ui.element("div").classes("ed-shell"):

            ui.label("Team Management").classes("text-h4 q-mb-md")

            kpi_container = ui.element("div").classes("ed-strip")
            seg_container = ui.element("div").classes("ed-segmented")

            with ui.element("div").classes("ed-filter-row"):
                ui.label("Filter").classes("ed-filter-label")
                search_input = ui.input(
                    placeholder="Search by name, role, skills, linked user…",
                ).props('dense outlined clearable').style("min-width: 320px;")
            search_ref["input"] = search_input

            # ── KPI / segments / filter ────────────────────────
            def _count_by_role(rows: list[dict], r: str) -> int:
                return sum(1 for m in rows if (m.get("role") or "") == r)

            def _set_role(r: str) -> None:
                state["filter_role"] = r
                _render_kpis()
                _render_segments()
                _apply_team_filter()

            def _render_kpis() -> None:
                kpi_container.clear()
                with kpi_container:
                    rows = members
                    total_h = sum((m.get("available_hours_per_day") or 0) for m in rows)
                    linked = sum(1 for m in rows if m.get("linked_user_name"))

                    def _tile(label: str, value: str, sub: str, key: str | None = None) -> None:
                        cls = "ed-strip-cell ed-stat-tile"
                        if key and state["filter_role"] == key:
                            cls += " active"
                        el = ui.element("div").classes(cls)
                        if key is not None:
                            el.on("click", lambda _, k=key: _set_role(k))
                        with el:
                            ui.label(label).classes("ed-eyebrow")
                            ui.label(value).classes("ed-strip-num")
                            if sub:
                                ui.label(sub).classes("ed-stat-tile-sub")

                    _tile("Total Members", str(len(rows)),
                          f"{linked} linked to a user · {total_h:.1f}h/day capacity",
                          key="All")
                    for r in _ROLES:
                        n = _count_by_role(rows, r)
                        if n:
                            _tile(r.title(), str(n), "filter to role", key=r)

            def _render_segments() -> None:
                seg_container.clear()
                with seg_container:
                    rows = members

                    def _seg(label: str, key: str, count: int) -> None:
                        cls = "ed-segmented-item" + (
                            " active" if state["filter_role"] == key else "")
                        btn = ui.element("button").classes(cls)
                        btn.on("click", lambda _, k=key: _set_role(k))
                        with btn:
                            ui.label(label)
                            ui.label(f"· {count}").classes("seg-count")

                    _seg("All", "All", len(rows))
                    for r in _ROLES:
                        n = _count_by_role(rows, r)
                        if n or r == state["filter_role"]:
                            _seg(r.title(), r, n)

            def _apply_team_filter() -> None:
                query = (search_input.value or "").strip().lower()
                role_filter = state["filter_role"]
                rows = list(members)
                if role_filter != "All":
                    rows = [m for m in rows if (m.get("role") or "") == role_filter]
                if query:
                    rows = [
                        m for m in rows
                        if query in (m.get("name") or "").lower()
                        or query in (m.get("role") or "").lower()
                        or query in (m.get("skills_json") or "").lower()
                        or query in (m.get("linked_user_name") or "").lower()
                        or query in str(m.get("id", ""))
                    ]
                if table_ref is not None:
                    table_ref.rows = rows
                    table_ref.update()

            search_input.on("update:model-value", lambda _: _apply_team_filter())

            columns = [
                {"name": "name", "label": "Name", "field": "name", "sortable": True, "align": "left"},
                {"name": "role", "label": "Role", "field": "role", "sortable": True, "align": "left"},
                {"name": "available_hours_per_day", "label": "Hrs/Day", "field": "available_hours_per_day", "sortable": True, "align": "right"},
                {"name": "skills_json", "label": "Skills", "field": "skills_json", "align": "left"},
                {"name": "linked_user_name", "label": "Linked User", "field": "linked_user_name", "sortable": True, "align": "left"},
                {"name": "actions", "label": "Actions", "field": "actions", "align": "center"},
            ]

            with ui.element("div").classes("ed-card"):
                table_ref = ui.table(
                    columns=columns,
                    rows=members,
                    row_key="id",
                    pagination={"rowsPerPage": 25},
                ).classes("w-full").props("flat")

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
                       @click="$parent.$emit('edit', props.row)">
                    <q-tooltip>Edit member</q-tooltip>
                </q-btn>
                <q-btn flat round icon="delete" size="sm" color="negative"
                       @click="$parent.$emit('delete', props.row)">
                    <q-tooltip>Delete member</q-tooltip>
                </q-btn>
            </q-td>
            """,
        )

        table_ref.on("edit", lambda e: open_edit_dialog(e.args))
        table_ref.on("delete", lambda e: open_delete_dialog(e.args))

        # Initial KPI / segments render (table is now ready)
        _render_kpis()
        _render_segments()
        _apply_team_filter()

        # ── Teams section ──────────────────────────────────────
        await load_teams()
        with ui.element("div").classes("ed-card").style("margin-top: 24px;"):
            with ui.element("div").classes("ed-card-head"):
                ui.label("Teams").classes("ed-cap")
                ui.label(f"{len(teams)} team{'s' if len(teams) != 1 else ''}") \
                    .classes("ed-card-head-meta")
            if teams:
                with ui.row().classes("flex-wrap q-gutter-md"):
                    for team in teams:
                        with ui.element("div").classes("ed-card") \
                                .style("width: 240px; margin-bottom: 0;"):
                            ui.label(team.get("name", "")).style(
                                "font-size: 16px; font-weight: 600; margin-bottom: 4px;"
                            )
                            if team.get("description"):
                                ui.label(team["description"]).classes(
                                    "text-caption text-grey"
                                ).style("margin-bottom: 6px;")
                            ui.label(
                                f"{team.get('member_count', 0)} member"
                                f"{'s' if team.get('member_count', 0) != 1 else ''}"
                            ).classes("ed-mono").style("font-size: 12px; opacity: 0.75;")
                            with ui.row().classes("q-mt-sm gap-1"):
                                ui.button("Manage", icon="settings",
                                          on_click=lambda t=team: open_manage_team_dialog(t)) \
                                    .props("flat dense color=primary size=sm")
                                _del_team_btn = ui.button("Delete", icon="delete") \
                                    .props("flat dense color=negative size=sm")
                                _del_team_btn.on("click", run_async(
                                    _del_team_btn, lambda t=team: delete_team(t),
                                    success="Team deleted.", error_prefix="Delete team failed"))
            else:
                empty_state("No teams created yet")
