"""Shared authentication helpers for Streamlit pages.

Provides session state management, role checking, and API call helpers.
"""

import requests
import streamlit as st

API_URL = "http://localhost:8501/api"


def get_token() -> str | None:
    """Return current JWT access token from session state."""
    return st.session_state.get("token")


def get_user() -> dict | None:
    """Return current user dict from session state."""
    return st.session_state.get("user")


def get_role() -> str:
    """Return current user's role, defaulting to VIEWER."""
    user = get_user()
    return user.get("role", "VIEWER") if user else "VIEWER"


def is_authenticated() -> bool:
    """Check if user is authenticated."""
    return get_token() is not None


def require_auth() -> bool:
    """Check authentication and show warning if not logged in.

    Returns True if authenticated, False otherwise.
    """
    if not is_authenticated():
        st.warning("Please log in to access this page. Go to the **Login** page.")
        st.stop()
        return False
    return True


def require_role(minimum_role: str) -> bool:
    """Check if the user has at least the specified role.

    Role hierarchy: VIEWER < ESTIMATOR < APPROVER < ADMIN
    Returns True if authorized, False otherwise.
    """
    require_auth()

    hierarchy = {"VIEWER": 0, "ESTIMATOR": 1, "APPROVER": 2, "ADMIN": 3}
    user_level = hierarchy.get(get_role(), 0)
    required_level = hierarchy.get(minimum_role, 0)

    if user_level < required_level:
        st.error(f"Access denied. This page requires **{minimum_role}** role or higher.")
        st.stop()
        return False
    return True


def auth_headers() -> dict[str, str]:
    """Return Authorization header dict for API calls."""
    token = get_token()
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def api_get(path: str, params: dict | None = None) -> requests.Response:
    """Make authenticated GET request to the API."""
    return requests.get(f"{API_URL}{path}", headers=auth_headers(), params=params)


def api_post(path: str, json: dict | None = None, **kwargs) -> requests.Response:
    """Make authenticated POST request to the API."""
    return requests.post(f"{API_URL}{path}", headers=auth_headers(), json=json, **kwargs)


def api_put(path: str, json: dict | None = None) -> requests.Response:
    """Make authenticated PUT request to the API."""
    return requests.put(f"{API_URL}{path}", headers=auth_headers(), json=json)


def api_delete(path: str) -> requests.Response:
    """Make authenticated DELETE request to the API."""
    return requests.delete(f"{API_URL}{path}", headers=auth_headers())


def show_user_sidebar():
    """Display current user info and logout button in sidebar."""
    user = get_user()
    if user:
        with st.sidebar:
            st.divider()
            st.caption(f"Logged in as **{user.get('display_name', user.get('username', '?'))}**")
            st.caption(f"Role: `{user.get('role', 'VIEWER')}`")
            if st.button("Logout", key="sidebar_logout"):
                try:
                    api_post("/auth/logout")
                except Exception:
                    pass
                for key in ["token", "refresh_token", "user"]:
                    st.session_state.pop(key, None)
                st.rerun()
    else:
        with st.sidebar:
            st.divider()
            st.caption("Not logged in")
