"""User Management page — ADMIN-only full CRUD.

Guards:
  - Must be authenticated (redirects to /login otherwise).
  - Must have role == ADMIN (redirects to / otherwise).

Route: /users
API:
  GET    /users
  POST   /users
  PUT    /users/{id}
  DELETE /users/{id}
"""

from nicegui import ui

from frontend_nicegui.app import (
    api_delete,
    api_get,
    api_post,
    api_put,
    current_user,
    empty_state,
    is_authenticated,
    loading_state,
    run_async,
    sidebar,
)

_ROLES = ["VIEWER", "ESTIMATOR", "APPROVER", "ADMIN"]
_PROVIDERS = ["local", "ldap", "oidc"]


@ui.page("/users")
async def users_page() -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    user = current_user()
    if not user or user.get("role") != "ADMIN":
        ui.notify("Access denied — ADMIN role required.", type="negative")
        ui.navigate.to("/")
        return

    sidebar()

    # Fetch team members for linking
    try:
        async with loading_state("Loading users…"):
            team_members: list[dict] = await api_get("/team-members")
    except Exception:
        team_members = []

    # ---------------------------------------------------------------------------
    # Page-level state
    # ---------------------------------------------------------------------------
    users_list: list[dict] = []
    table_ref: ui.table | None = None
    current_user_id: int = user.get("id", -1)

    # ---------------------------------------------------------------------------
    # Data helpers
    # ---------------------------------------------------------------------------
    async def load_users() -> None:
        nonlocal users_list
        try:
            data = await api_get("/users")
            users_list = data if isinstance(data, list) else []
        except Exception as exc:
            ui.notify(f"Failed to load users: {exc}", type="negative")
            users_list = []

    search_ref: dict = {"input": None}

    async def refresh_table() -> None:
        await load_users()
        try:
            _total_label.set_text(f"TOTAL · {len(users_list)}")
            _render_kpis()
            _render_segments()
            _apply_filter()
        except NameError:
            if table_ref is not None:
                table_ref.rows = users_list
                table_ref.update()

    # ---------------------------------------------------------------------------
    # Add dialog
    # ---------------------------------------------------------------------------
    async def open_add_dialog() -> None:
        with ui.dialog() as dialog, ui.card().classes("w-[500px]"):
            ui.label("Add User").classes("text-h6")
            ui.separator()

            f_username = ui.input("Username *").classes("w-full").props("autofocus")
            f_display = ui.input("Display Name *").classes("w-full")
            f_email = ui.input("Email").classes("w-full")
            f_password = ui.input(
                "Password *", password=True, password_toggle_button=True
            ).classes("w-full")
            f_role = ui.select(
                label="Role", options=_ROLES, value="VIEWER"
            ).classes("w-full")
            f_provider = ui.select(
                label="Auth Provider", options=_PROVIDERS, value="local"
            ).classes("w-full")
            tm_options = {0: "(None)"} | {
                m["id"]: m.get("name", f"Member {m['id']}")
                for m in team_members
            }
            f_team_member = ui.select(
                label="Team Member (optional)",
                options=tm_options,
                value=0,
            ).classes("w-full")

            async def submit() -> None:
                if not f_username.value or not f_username.value.strip():
                    ui.notify("Username is required.", type="warning")
                    return
                if not f_display.value or not f_display.value.strip():
                    ui.notify("Display Name is required.", type="warning")
                    return
                if not f_password.value:
                    ui.notify("Password is required for new users.", type="warning")
                    return

                tm_id = f_team_member.value if f_team_member.value != 0 else None
                payload = {
                    "username": f_username.value.strip(),
                    "display_name": f_display.value.strip(),
                    "email": f_email.value.strip() or None,
                    "password": f_password.value,
                    "role": f_role.value,
                    "auth_provider": f_provider.value,
                    "team_member_id": tm_id,
                }

                async def _on_created(_):
                    dialog.close()
                    await refresh_table()

                await run_async(
                    create_btn,
                    lambda: api_post("/users", json=payload),
                    success="User created.",
                    on_success=_on_created,
                    error_prefix="Error creating user",
                )()

            with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                create_btn = ui.button("Create User", on_click=submit).props("color=primary")

        dialog.open()

    # ---------------------------------------------------------------------------
    # Edit dialog (no password field)
    # ---------------------------------------------------------------------------
    async def open_edit_dialog(target: dict) -> None:
        with ui.dialog() as dialog, ui.card().classes("w-[500px]"):
            ui.label(f"Edit User: {target.get('username', '')}").classes("text-h6")
            ui.separator()

            is_self = target.get("id") == current_user_id

            f_display = ui.input(
                "Display Name *", value=target.get("display_name", "")
            ).classes("w-full").props("autofocus")
            f_email = ui.input(
                "Email", value=target.get("email") or ""
            ).classes("w-full")
            f_role = ui.select(
                label="Role",
                options=_ROLES,
                value=target.get("role", "VIEWER"),
            ).classes("w-full")
            if is_self:
                # Self-lockout guard: prevent the logged-in admin from
                # downgrading their own role and locking themselves out.
                f_role.props("disable")
                f_role.tooltip(
                    "You cannot change your own role — this prevents locking "
                    "yourself out of admin access."
                )
            f_active = ui.checkbox(
                "Active", value=target.get("is_active", True)
            )
            tm_options_edit = {0: "(None)"} | {
                m["id"]: m.get("name", f"Member {m['id']}")
                for m in team_members
            }
            f_team_member = ui.select(
                label="Team Member (optional)",
                options=tm_options_edit,
                value=target.get("team_member_id") or 0,
            ).classes("w-full")

            async def submit() -> None:
                if not f_display.value or not f_display.value.strip():
                    ui.notify("Display Name is required.", type="warning")
                    return

                tm_id = f_team_member.value if f_team_member.value != 0 else None
                payload = {
                    "display_name": f_display.value.strip(),
                    "email": f_email.value.strip() or None,
                    # Keep self's role unchanged regardless of the (disabled) field.
                    "role": target.get("role", "VIEWER") if is_self else f_role.value,
                    "is_active": f_active.value,
                    "team_member_id": tm_id,
                }

                async def _on_saved(_):
                    dialog.close()
                    await refresh_table()

                await run_async(
                    save_btn,
                    lambda: api_put(f"/users/{target['id']}", json=payload),
                    success="User updated.",
                    on_success=_on_saved,
                    error_prefix="Error updating user",
                )()

            with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                save_btn = ui.button("Save Changes", on_click=submit).props("color=primary")

        dialog.open()

    # ---------------------------------------------------------------------------
    # Delete confirmation dialog
    # ---------------------------------------------------------------------------
    async def open_delete_dialog(target: dict) -> None:
        target_id = target.get("id")
        if target_id == current_user_id:
            ui.notify("You cannot delete your own account.", type="warning")
            return

        with ui.dialog() as dialog, ui.card().classes("w-[420px]"):
            ui.label("Confirm Delete").classes("text-h6")
            ui.separator()
            ui.label(
                f"Delete user '{target.get('username', '')}'? This permanently "
                "removes their account and unlinks any team member / assignments. "
                "This cannot be undone."
            ).classes("text-body2")

            async def _on_deleted(_):
                dialog.close()
                await refresh_table()

            with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                del_btn = ui.button("Delete").props("color=negative")
                del_btn.on_click(run_async(
                    del_btn,
                    lambda: api_delete(f"/users/{target_id}"),
                    success="User deleted.",
                    on_success=_on_deleted,
                    error_prefix="Error deleting user",
                ))

        dialog.open()

    # ---------------------------------------------------------------------------
    # Bulk role edit dialog
    # ---------------------------------------------------------------------------
    async def open_bulk_role_dialog() -> None:
        selected = table_ref.selected if table_ref else []
        if not selected:
            ui.notify("Select at least one user first.", type="warning")
            return

        # Self-lockout guard: if the logged-in admin is among the selected
        # users, changing their own role could remove their admin access.
        includes_self = any(row.get("id") == current_user_id for row in selected)
        names = [str(row.get("username") or row.get("display_name") or row.get("id"))
                 for row in selected]
        shown = names[:10]
        names_text = ", ".join(shown)
        if len(names) > len(shown):
            names_text += f", … (+{len(names) - len(shown)} more)"

        with ui.dialog() as dialog, ui.card().classes("w-[440px]"):
            ui.label("Bulk Set Role").classes("text-h6")
            ui.separator()
            ui.label(
                f"This will change {len(selected)} user(s): {names_text}"
            ).classes("text-body2 q-mb-sm")
            f_role = ui.select(
                label="New Role", options=_ROLES, value="VIEWER"
            ).classes("w-full")

            if includes_self:
                ui.label(
                    "Warning: your own account is in this selection. To avoid "
                    "locking yourself out, your role will not be changed."
                ).classes("text-warning text-caption q-mt-sm")

            confirm_cb = ui.checkbox(
                f"I understand this changes {len(selected)} users"
            ).classes("q-mt-sm")

            with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                apply_btn = ui.button("Apply").props("color=primary")

            async def _bulk_apply():
                new_role = f_role.value
                success = 0
                for row in selected:
                    # Skip self to honor the self-lockout guard.
                    if row.get("id") == current_user_id:
                        continue
                    try:
                        await api_put(f"/users/{row['id']}", json={"role": new_role})
                        success += 1
                    except Exception:
                        pass
                return success

            async def _on_bulk_done(success):
                ui.notify(
                    f"Role updated for {success}/{len(selected)} users.",
                    type="positive",
                )
                dialog.close()
                if table_ref:
                    table_ref.selected.clear()
                await refresh_table()

            apply_btn.on_click(run_async(
                apply_btn,
                _bulk_apply,
                on_success=_on_bulk_done,
                error_prefix="Bulk role update failed",
            ))

            def _gate() -> None:
                apply_btn.set_enabled(bool(confirm_cb.value))

            _gate()
            confirm_cb.on_value_change(lambda _: _gate())

        dialog.open()

    # ---------------------------------------------------------------------------
    # State + initial load
    # ---------------------------------------------------------------------------
    state: dict = {"filter_role": "All"}
    await load_users()

    # ---------------------------------------------------------------------------
    # Page layout
    # ---------------------------------------------------------------------------
    with ui.column().classes("w-full q-pa-md").style("gap: 0;"):

        # ── Sticky toolbar ──────────────────────────────────────
        with ui.element("div").classes("ed-toolbar"):
            ui.button("Add User", icon="person_add",
                      on_click=lambda: open_add_dialog()) \
                .props("flat dense color=primary")
            ui.element("div").classes("ed-toolbar-spacer")
            bulk_btn = ui.button("Bulk Set Role", icon="group",
                                 on_click=lambda: open_bulk_role_dialog()) \
                .props("flat dense color=secondary")
            bulk_btn.set_visibility(False)
            ui.element("div").classes("ed-toolbar-spacer")
            ui.button("Refresh", icon="refresh",
                      on_click=lambda: refresh_table()) \
                .props("flat dense")
            ui.element("div").classes("ed-toolbar-grow")
            with ui.element("div").classes("ed-status-now"):
                ui.element("span").classes("ed-status-dot")
                _total_label = ui.label(f"TOTAL · {len(users_list)}").classes("ed-mono")

        with ui.element("div").classes("ed-shell"):

            ui.label("User Management").classes("text-h4 q-mb-md")

            kpi_container = ui.element("div").classes("ed-strip")
            seg_container = ui.element("div").classes("ed-segmented")

            with ui.element("div").classes("ed-filter-row"):
                ui.label("Filter").classes("ed-filter-label")
                search_input = ui.input(
                    placeholder="Search by username, display name, email, role…",
                ).props("dense outlined clearable").style("min-width: 320px;")
            search_ref["input"] = search_input

            # ── KPI / segments / filter ────────────────────────
            def _count_by_role(rows: list[dict], r: str) -> int:
                return sum(1 for u in rows if (u.get("role") or "") == r)

            def _set_role(r: str) -> None:
                state["filter_role"] = r
                _render_kpis()
                _render_segments()
                _apply_filter()

            def _render_kpis() -> None:
                kpi_container.clear()
                with kpi_container:
                    rows = users_list
                    active_n = sum(1 for u in rows if u.get("is_active"))
                    inactive_n = len(rows) - active_n
                    ldap_n = sum(1 for u in rows if (u.get("auth_provider") or "") == "ldap")
                    oidc_n = sum(1 for u in rows if (u.get("auth_provider") or "") == "oidc")
                    local_n = sum(1 for u in rows if (u.get("auth_provider") or "local") == "local")

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

                    _tile("Total Users", str(len(rows)),
                          f"{active_n} active · {inactive_n} inactive",
                          key="All")
                    _tile("Admins", str(_count_by_role(rows, "ADMIN")),
                          "filter to admins", key="ADMIN")
                    _tile("Approvers", str(_count_by_role(rows, "APPROVER")),
                          "filter to approvers", key="APPROVER")
                    if ldap_n or oidc_n:
                        _tile("Federated", str(ldap_n + oidc_n),
                              f"{ldap_n} LDAP · {oidc_n} OIDC · {local_n} local",
                              key=None)

            def _render_segments() -> None:
                seg_container.clear()
                with seg_container:
                    rows = users_list

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

            def _apply_filter() -> None:
                query = (search_input.value or "").strip().lower()
                role_filter = state["filter_role"]
                rows = list(users_list)
                if role_filter != "All":
                    rows = [u for u in rows if (u.get("role") or "") == role_filter]
                if query:
                    rows = [
                        u for u in rows
                        if query in (u.get("username") or "").lower()
                        or query in (u.get("display_name") or "").lower()
                        or query in (u.get("email") or "").lower()
                        or query in (u.get("role") or "").lower()
                        or query in (u.get("auth_provider") or "").lower()
                        or query in str(u.get("id", ""))
                    ]
                if table_ref is not None:
                    table_ref.rows = rows
                    table_ref.update()

            search_input.on("update:model-value", lambda _: _apply_filter())

            columns = [
                {"name": "username", "label": "Username", "field": "username", "sortable": True, "align": "left"},
                {"name": "display_name", "label": "Display Name", "field": "display_name", "sortable": True, "align": "left"},
                {"name": "email", "label": "Email", "field": "email", "sortable": True, "align": "left"},
                {"name": "role", "label": "Role", "field": "role", "sortable": True, "align": "left"},
                {"name": "is_active", "label": "Active", "field": "is_active", "align": "center"},
                {"name": "auth_provider", "label": "Provider", "field": "auth_provider", "sortable": True, "align": "left"},
                {"name": "team_member_id", "label": "Team Member", "field": "team_member_id", "sortable": True, "align": "left"},
                {"name": "actions", "label": "Actions", "field": "actions", "align": "center"},
            ]

            with ui.element("div").classes("ed-card"):
                table_ref = ui.table(
                    columns=columns,
                    rows=users_list,
                    row_key="id",
                    pagination={"rowsPerPage": 25},
                    selection="multiple",
                ).classes("w-full").props("flat")
                table_ref.add_slot(
                    "no-data",
                    '<div class="ed-empty full-width column flex-center q-pa-md">'
                    'No users match the current filter.</div>',
                )

        def _on_selection_change() -> None:
            has_sel = bool(table_ref.selected) if table_ref else False
            bulk_btn.set_visibility(has_sel)

        table_ref.on("selection", lambda _: _on_selection_change())

        # Role badge with color per role
        table_ref.add_slot(
            "body-cell-role",
            r"""
            <q-td :props="props">
                <q-badge
                    :color="props.value === 'ADMIN' ? 'red'
                           : props.value === 'APPROVER' ? 'orange'
                           : props.value === 'ESTIMATOR' ? 'blue' : 'grey'"
                    :label="props.value"
                />
            </q-td>
            """,
        )

        # is_active colored badge
        table_ref.add_slot(
            "body-cell-is_active",
            r"""
            <q-td :props="props">
                <q-badge
                    :color="props.value ? 'positive' : 'negative'"
                    :label="props.value ? 'Active' : 'Inactive'"
                />
            </q-td>
            """,
        )

        # Team member name lookup
        import json as _json
        _tm_map = {m["id"]: m.get("name", f"Member {m['id']}") for m in team_members}
        _tm_map_json = _json.dumps(_tm_map)
        table_ref.add_slot(
            "body-cell-team_member_id",
            rf"""
            <q-td :props="props">
                <span v-if="props.value" class="text-caption">
                    {{{{ ({_tm_map_json})[props.value] || 'ID: ' + props.value }}}}
                </span>
                <span v-else class="text-grey">—</span>
            </q-td>
            """,
        )

        # Action buttons — edit and delete; delete is disabled for own account
        table_ref.add_slot(
            "body-cell-actions",
            rf"""
            <q-td :props="props">
                <q-btn flat round icon="edit" size="sm"
                       @click="$parent.$emit('edit', props.row)">
                    <q-tooltip>Edit user</q-tooltip>
                </q-btn>
                <q-btn flat round icon="delete" size="sm" color="negative"
                       :disable="props.row.id === {current_user_id}"
                       @click="$parent.$emit('delete', props.row)">
                    <q-tooltip>{{{{ props.row.id === {current_user_id} ? 'You cannot delete your own account' : 'Delete user' }}}}</q-tooltip>
                </q-btn>
            </q-td>
            """,
        )

        table_ref.on("edit", lambda e: open_edit_dialog(e.args))
        table_ref.on("delete", lambda e: open_delete_dialog(e.args))

        # Initial KPI / segments / filter render
        _render_kpis()
        _render_segments()
        _apply_filter()
