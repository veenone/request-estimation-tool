"""User management page — ADMIN only.

Lists all user accounts and provides create / edit / delete operations.
All mutating actions go through the REST API so that the AuthService
keeps audit logs and enforces constraints (e.g. cannot delete yourself).

Required session_state keys (set by 00_login.py):
  token  -- str : Bearer access token
  user   -- dict: UserOut fields (role must be "ADMIN" to use this page)
"""

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import requests as http
import streamlit as st

# ---------------------------------------------------------------------------
# Path bootstrap — consistent with every other page
# ---------------------------------------------------------------------------

backend_path = str(Path(__file__).resolve().parent.parent.parent / "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

API_BASE = "http://localhost:8501/api"

ROLES = ["VIEWER", "ESTIMATOR", "APPROVER", "ADMIN"]
AUTH_PROVIDERS = ["local", "ldap"]

ROLE_LABELS = {
    "ADMIN": "Administrator",
    "APPROVER": "Approver",
    "ESTIMATOR": "Estimator",
    "VIEWER": "Viewer",
}


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def _auth_headers() -> dict[str, str]:
    token = st.session_state.get("token", "")
    return {"Authorization": f"Bearer {token}"}


def _current_user() -> dict[str, Any]:
    return st.session_state.get("user") or {}


# ---------------------------------------------------------------------------
# API calls — each returns (data_or_None, error_message_or_None)
# ---------------------------------------------------------------------------


def _api_get_users() -> tuple[list[dict], str | None]:
    try:
        resp = http.get(
            f"{API_BASE}/users",
            headers=_auth_headers(),
            timeout=10,
        )
    except http.exceptions.ConnectionError:
        return [], "Cannot reach the API server. Make sure the backend is running on localhost:8501."
    except http.exceptions.Timeout:
        return [], "Request timed out."

    if resp.status_code == 200:
        return resp.json(), None
    if resp.status_code == 401:
        return [], "Session expired. Please log in again."
    if resp.status_code == 403:
        return [], "Access denied. Administrator role is required."
    try:
        detail = resp.json().get("detail", resp.text)
    except Exception:
        detail = resp.text
    return [], f"Error {resp.status_code}: {detail}"


def _api_create_user(payload: dict) -> tuple[dict | None, str | None]:
    try:
        resp = http.post(
            f"{API_BASE}/users",
            json=payload,
            headers=_auth_headers(),
            timeout=10,
        )
    except http.exceptions.ConnectionError:
        return None, "Cannot reach the API server."
    except http.exceptions.Timeout:
        return None, "Request timed out."

    if resp.status_code == 201:
        return resp.json(), None
    try:
        detail = resp.json().get("detail", resp.text)
    except Exception:
        detail = resp.text
    return None, f"Error {resp.status_code}: {detail}"


def _api_update_user(user_id: int, payload: dict) -> tuple[dict | None, str | None]:
    try:
        resp = http.put(
            f"{API_BASE}/users/{user_id}",
            json=payload,
            headers=_auth_headers(),
            timeout=10,
        )
    except http.exceptions.ConnectionError:
        return None, "Cannot reach the API server."
    except http.exceptions.Timeout:
        return None, "Request timed out."

    if resp.status_code == 200:
        return resp.json(), None
    try:
        detail = resp.json().get("detail", resp.text)
    except Exception:
        detail = resp.text
    return None, f"Error {resp.status_code}: {detail}"


def _api_delete_user(user_id: int) -> tuple[bool, str | None]:
    try:
        resp = http.delete(
            f"{API_BASE}/users/{user_id}",
            headers=_auth_headers(),
            timeout=10,
        )
    except http.exceptions.ConnectionError:
        return False, "Cannot reach the API server."
    except http.exceptions.Timeout:
        return False, "Request timed out."

    if resp.status_code == 204:
        return True, None
    try:
        detail = resp.json().get("detail", resp.text)
    except Exception:
        detail = resp.text
    return False, f"Error {resp.status_code}: {detail}"


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------


def _role_badge(role: str) -> str:
    icons = {"ADMIN": "🔴", "APPROVER": "🟠", "ESTIMATOR": "🟡", "VIEWER": "🟢"}
    return f"{icons.get(role, '•')} {ROLE_LABELS.get(role, role)}"


def _active_badge(is_active: bool) -> str:
    return "Active" if is_active else "Inactive"


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.title("User Management")
st.markdown("Create, edit and deactivate user accounts.")

# ── Access guard ────────────────────────────────────────────────────────────
current_user = _current_user()
token = st.session_state.get("token")

if not token or not current_user:
    st.warning("You must be logged in to view this page. Go to the Login page.")
    st.stop()

if current_user.get("role") != "ADMIN":
    st.error(
        "Access denied. This page is restricted to Administrators. "
        f"Your current role is: **{ROLE_LABELS.get(current_user.get('role', ''), current_user.get('role', 'Unknown'))}**"
    )
    st.stop()

# ── Load user list ───────────────────────────────────────────────────────────
if "users_refresh" not in st.session_state:
    st.session_state["users_refresh"] = 0

users_list, load_error = _api_get_users()

if load_error:
    st.error(load_error)
    st.stop()

# ── Summary metrics ─────────────────────────────────────────────────────────
total_users = len(users_list)
active_users = sum(1 for u in users_list if u.get("is_active"))
admin_count = sum(1 for u in users_list if u.get("role") == "ADMIN")

metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
with metric_col1:
    st.metric("Total Users", total_users)
with metric_col2:
    st.metric("Active", active_users)
with metric_col3:
    st.metric("Inactive", total_users - active_users)
with metric_col4:
    st.metric("Administrators", admin_count)

st.divider()

# ── User table ───────────────────────────────────────────────────────────────
st.subheader("All Users")

col_search, col_role_filter, col_status_filter, col_refresh = st.columns([3, 2, 2, 1])

with col_search:
    search_query = st.text_input(
        "Search",
        placeholder="Username, display name or email...",
        label_visibility="collapsed",
    )

with col_role_filter:
    role_filter = st.multiselect(
        "Role",
        ROLES,
        placeholder="Filter by role",
        label_visibility="collapsed",
    )

with col_status_filter:
    status_filter = st.selectbox(
        "Status",
        ["All", "Active only", "Inactive only"],
        label_visibility="collapsed",
    )

with col_refresh:
    if st.button("Refresh", use_container_width=True):
        st.session_state["users_refresh"] += 1
        st.rerun()

# Apply filters
filtered_users = users_list

if search_query:
    q = search_query.lower()
    filtered_users = [
        u for u in filtered_users
        if q in u.get("username", "").lower()
        or q in u.get("display_name", "").lower()
        or q in (u.get("email") or "").lower()
    ]

if role_filter:
    filtered_users = [u for u in filtered_users if u.get("role") in role_filter]

if status_filter == "Active only":
    filtered_users = [u for u in filtered_users if u.get("is_active")]
elif status_filter == "Inactive only":
    filtered_users = [u for u in filtered_users if not u.get("is_active")]

st.markdown(f"**Showing {len(filtered_users)} of {total_users} users**")

if filtered_users:
    display_rows = []
    for u in filtered_users:
        display_rows.append({
            "ID": u["id"],
            "Username": u.get("username", ""),
            "Display Name": u.get("display_name", ""),
            "Email": u.get("email") or "—",
            "Role": _role_badge(u.get("role", "")),
            "Provider": u.get("auth_provider", "local"),
            "Status": _active_badge(u.get("is_active", True)),
            "Last Login": (
                u["last_login_at"][:10]
                if u.get("last_login_at") else "Never"
            ),
        })

    df = pd.DataFrame(display_rows)
    st.dataframe(
        df.drop("ID", axis=1),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Username": st.column_config.TextColumn(width="small"),
            "Display Name": st.column_config.TextColumn(width="medium"),
            "Email": st.column_config.TextColumn(width="medium"),
            "Role": st.column_config.TextColumn(width="small"),
            "Provider": st.column_config.TextColumn(width="small"),
            "Status": st.column_config.TextColumn(width="small"),
            "Last Login": st.column_config.TextColumn(width="small"),
        },
    )
else:
    st.info("No users match the current filters.")

st.divider()

# ── Tabbed CRUD section ──────────────────────────────────────────────────────
tab_create, tab_edit, tab_delete = st.tabs(
    ["Create New User", "Edit Existing User", "Delete User"]
)

# ── Tab 1: Create ────────────────────────────────────────────────────────────
with tab_create:
    st.subheader("Create New User")

    with st.form("create_user_form", clear_on_submit=True):
        form_col1, form_col2 = st.columns(2)

        with form_col1:
            new_username = st.text_input(
                "Username *",
                placeholder="e.g. jsmith",
                help="Unique login identifier. Cannot be changed after creation.",
            )
            new_display_name = st.text_input(
                "Display Name *",
                placeholder="e.g. John Smith",
            )
            new_email = st.text_input(
                "Email",
                placeholder="e.g. jsmith@company.com",
            )

        with form_col2:
            new_role = st.selectbox(
                "Role *",
                ROLES,
                index=0,
                help=(
                    "VIEWER — read-only access. "
                    "ESTIMATOR — can create estimations. "
                    "APPROVER — can approve/reject. "
                    "ADMIN — full access including user management."
                ),
            )
            new_auth_provider = st.selectbox(
                "Authentication Provider",
                AUTH_PROVIDERS,
                index=0,
                help="Use 'local' for password-based login, 'ldap' for LDAP/AD.",
            )
            new_password = st.text_input(
                "Password",
                type="password",
                placeholder="Leave blank to auto-generate",
                help="Required for local accounts. Leave blank to set later.",
            )

        st.write("")

        create_submitted = st.form_submit_button(
            "Create User",
            type="primary",
            use_container_width=False,
        )

    if create_submitted:
        errors = []
        if not new_username.strip():
            errors.append("Username is required.")
        if not new_display_name.strip():
            errors.append("Display Name is required.")
        if new_auth_provider == "local" and not new_password:
            errors.append("Password is required for local accounts.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            payload: dict = {
                "username": new_username.strip(),
                "display_name": new_display_name.strip(),
                "role": new_role,
                "auth_provider": new_auth_provider,
            }
            if new_email.strip():
                payload["email"] = new_email.strip()
            if new_password:
                payload["password"] = new_password

            with st.spinner("Creating user..."):
                created, create_error = _api_create_user(payload)

            if created:
                st.success(
                    f"User **{created['display_name']}** (`{created['username']}`) "
                    f"created successfully with role **{created['role']}**."
                )
                st.session_state["users_refresh"] += 1
                st.rerun()
            else:
                st.error(create_error)

# ── Tab 2: Edit ──────────────────────────────────────────────────────────────
with tab_edit:
    st.subheader("Edit Existing User")

    if not users_list:
        st.info("No users available to edit.")
    else:
        user_options = {
            f"{u['display_name']} ({u['username']})": u
            for u in users_list
        }
        selected_label = st.selectbox(
            "Select user to edit",
            list(user_options.keys()),
            key="edit_user_select",
        )
        selected_user = user_options[selected_label]
        selected_id = selected_user["id"]

        st.markdown(
            f"Editing user ID **{selected_id}** — "
            f"username: `{selected_user['username']}` — "
            f"provider: `{selected_user.get('auth_provider', 'local')}`"
        )

        with st.form("edit_user_form"):
            edit_col1, edit_col2 = st.columns(2)

            with edit_col1:
                edit_display_name = st.text_input(
                    "Display Name",
                    value=selected_user.get("display_name", ""),
                )
                edit_email = st.text_input(
                    "Email",
                    value=selected_user.get("email") or "",
                    placeholder="e.g. jsmith@company.com",
                )

            with edit_col2:
                current_role = selected_user.get("role", "VIEWER")
                role_index = ROLES.index(current_role) if current_role in ROLES else 0
                edit_role = st.selectbox(
                    "Role",
                    ROLES,
                    index=role_index,
                )
                edit_is_active = st.checkbox(
                    "Account is active",
                    value=selected_user.get("is_active", True),
                    help="Uncheck to deactivate the account without deleting it.",
                )

            st.write("")

            # Guard: warn if editing own account
            if selected_id == current_user.get("id"):
                st.warning(
                    "You are editing your own account. "
                    "Changing your role or deactivating yourself may lock you out."
                )

            edit_submitted = st.form_submit_button(
                "Save Changes",
                type="primary",
            )

        if edit_submitted:
            update_payload: dict = {}

            if edit_display_name.strip() != selected_user.get("display_name", ""):
                update_payload["display_name"] = edit_display_name.strip()
            if (edit_email.strip() or None) != selected_user.get("email"):
                update_payload["email"] = edit_email.strip() or None
            if edit_role != selected_user.get("role"):
                update_payload["role"] = edit_role
            if edit_is_active != selected_user.get("is_active", True):
                update_payload["is_active"] = edit_is_active

            if not update_payload:
                st.info("No changes detected.")
            else:
                with st.spinner("Saving changes..."):
                    updated, update_error = _api_update_user(selected_id, update_payload)

                if updated:
                    changed_fields = ", ".join(update_payload.keys())
                    st.success(
                        f"User **{updated['display_name']}** updated successfully. "
                        f"Changed fields: {changed_fields}."
                    )
                    st.session_state["users_refresh"] += 1
                    st.rerun()
                else:
                    st.error(update_error)

# ── Tab 3: Delete ────────────────────────────────────────────────────────────
with tab_delete:
    st.subheader("Delete User")
    st.warning(
        "Deleting a user is permanent. Consider deactivating the account instead "
        "(via the Edit tab) to preserve audit history."
    )

    if not users_list:
        st.info("No users available.")
    else:
        # Exclude the current admin's own account from the delete list to match
        # the API constraint (cannot delete yourself).
        deletable_users = [
            u for u in users_list if u["id"] != current_user.get("id")
        ]

        if not deletable_users:
            st.info("No other users to delete.")
        else:
            delete_options = {
                f"{u['display_name']} ({u['username']}) — {u.get('role', '')}": u
                for u in deletable_users
            }

            delete_label = st.selectbox(
                "Select user to delete",
                list(delete_options.keys()),
                key="delete_user_select",
            )
            delete_target = delete_options[delete_label]
            delete_id = delete_target["id"]

            st.markdown(
                f"Selected: **{delete_target['display_name']}** "
                f"(username: `{delete_target['username']}`, "
                f"role: `{delete_target.get('role', 'VIEWER')}`)"
            )

            # Two-step confirmation — checkbox must be checked first, then
            # the button becomes the actual destructive action.
            confirm_check = st.checkbox(
                f"I confirm I want to permanently delete user "
                f"**{delete_target['display_name']}**",
                key="delete_confirm_check",
            )

            delete_btn_disabled = not confirm_check

            if st.button(
                "Delete User",
                type="primary",
                disabled=delete_btn_disabled,
                key="delete_user_btn",
            ):
                with st.spinner("Deleting user..."):
                    success, delete_error = _api_delete_user(delete_id)

                if success:
                    st.success(
                        f"User **{delete_target['display_name']}** "
                        f"(`{delete_target['username']}`) has been deleted."
                    )
                    st.session_state["users_refresh"] += 1
                    st.rerun()
                else:
                    st.error(delete_error)
