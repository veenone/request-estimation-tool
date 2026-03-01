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
    is_authenticated,
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

    async def refresh_table() -> None:
        await load_users()
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

            f_username = ui.input("Username *").classes("w-full")
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

                payload = {
                    "username": f_username.value.strip(),
                    "display_name": f_display.value.strip(),
                    "email": f_email.value.strip() or None,
                    "password": f_password.value,
                    "role": f_role.value,
                    "auth_provider": f_provider.value,
                }
                try:
                    await api_post("/users", json=payload)
                    ui.notify("User created.", type="positive")
                    dialog.close()
                    await refresh_table()
                except Exception as exc:
                    ui.notify(f"Error creating user: {exc}", type="negative")

            with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Create User", on_click=submit).props("color=primary")

        dialog.open()

    # ---------------------------------------------------------------------------
    # Edit dialog (no password field)
    # ---------------------------------------------------------------------------
    async def open_edit_dialog(target: dict) -> None:
        with ui.dialog() as dialog, ui.card().classes("w-[500px]"):
            ui.label(f"Edit User: {target.get('username', '')}").classes("text-h6")
            ui.separator()

            f_display = ui.input(
                "Display Name *", value=target.get("display_name", "")
            ).classes("w-full")
            f_email = ui.input(
                "Email", value=target.get("email") or ""
            ).classes("w-full")
            f_role = ui.select(
                label="Role",
                options=_ROLES,
                value=target.get("role", "VIEWER"),
            ).classes("w-full")
            f_active = ui.checkbox(
                "Active", value=target.get("is_active", True)
            )

            async def submit() -> None:
                if not f_display.value or not f_display.value.strip():
                    ui.notify("Display Name is required.", type="warning")
                    return

                payload = {
                    "display_name": f_display.value.strip(),
                    "email": f_email.value.strip() or None,
                    "role": f_role.value,
                    "is_active": f_active.value,
                }
                try:
                    await api_put(f"/users/{target['id']}", json=payload)
                    ui.notify("User updated.", type="positive")
                    dialog.close()
                    await refresh_table()
                except Exception as exc:
                    ui.notify(f"Error updating user: {exc}", type="negative")

            with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Save Changes", on_click=submit).props("color=primary")

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
                f"Delete user '{target.get('username', '')}'? This cannot be undone."
            )

            async def confirm() -> None:
                try:
                    await api_delete(f"/users/{target_id}")
                    ui.notify("User deleted.", type="positive")
                    dialog.close()
                    await refresh_table()
                except Exception as exc:
                    ui.notify(f"Error deleting user: {exc}", type="negative")

            with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Delete", on_click=confirm).props("color=negative")

        dialog.open()

    # ---------------------------------------------------------------------------
    # Page layout
    # ---------------------------------------------------------------------------
    with ui.column().classes("q-pa-lg w-full"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("User Management").classes("text-h4")
            with ui.row().classes("gap-2"):
                ui.button(
                    "Refresh", icon="refresh", on_click=refresh_table
                ).props("outline")
                ui.button(
                    "Add User", icon="person_add", on_click=open_add_dialog
                ).props("color=primary")

        await load_users()

        columns = [
            {"name": "id", "label": "ID", "field": "id", "sortable": True, "align": "left"},
            {"name": "username", "label": "Username", "field": "username", "sortable": True, "align": "left"},
            {"name": "display_name", "label": "Display Name", "field": "display_name", "sortable": True, "align": "left"},
            {"name": "email", "label": "Email", "field": "email", "sortable": True, "align": "left"},
            {"name": "role", "label": "Role", "field": "role", "sortable": True, "align": "left"},
            {"name": "is_active", "label": "Active", "field": "is_active", "align": "center"},
            {"name": "auth_provider", "label": "Provider", "field": "auth_provider", "sortable": True, "align": "left"},
            {"name": "actions", "label": "Actions", "field": "actions", "align": "center"},
        ]

        table_ref = ui.table(
            columns=columns,
            rows=users_list,
            row_key="id",
            pagination={"rowsPerPage": 20},
        ).classes("w-full")

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

        # Action buttons — edit and delete; delete is disabled for own account
        table_ref.add_slot(
            "body-cell-actions",
            rf"""
            <q-td :props="props">
                <q-btn flat round icon="edit" size="sm"
                       @click="$parent.$emit('edit', props.row)" />
                <q-btn flat round icon="delete" size="sm" color="negative"
                       :disable="props.row.id === {current_user_id}"
                       @click="$parent.$emit('delete', props.row)" />
            </q-td>
            """,
        )

        table_ref.on("edit", lambda e: open_edit_dialog(e.args))
        table_ref.on("delete", lambda e: open_delete_dialog(e.args))

        if not users_list:
            ui.label("No users found.").classes("text-grey q-mt-md")
