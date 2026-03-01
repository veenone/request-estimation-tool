"""Login / logout page for the Test Effort Estimation Tool.

Authenticates against POST /api/auth/login and stores the returned JWT
token pair plus user info in st.session_state so that every other page
can include an Authorization header when calling the API.

State keys written by this page:
  st.session_state["token"]         -- str  : access_token (Bearer)
  st.session_state["refresh_token"] -- str  : opaque refresh token
  st.session_state["user"]          -- dict : UserOut fields
"""

import sys
from pathlib import Path

import requests as http
import streamlit as st

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Add backend to path (kept consistent with every other page so that the
# database migration bootstrap in app.py still works when this page is
# visited first).
backend_path = str(Path(__file__).resolve().parent.parent.parent / "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

API_BASE = "http://localhost:8501/api"

ROLE_LABELS = {
    "ADMIN": "Administrator",
    "APPROVER": "Approver",
    "ESTIMATOR": "Estimator",
    "VIEWER": "Viewer",
}


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _auth_headers() -> dict[str, str]:
    """Return the Authorization header dict for the active session."""
    token = st.session_state.get("token", "")
    return {"Authorization": f"Bearer {token}"}


def _do_login(username: str, password: str) -> tuple[bool, str]:
    """POST /api/auth/login.

    Returns (success, error_message).  On success the token pair and user
    info are written into session_state.
    """
    try:
        resp = http.post(
            f"{API_BASE}/auth/login",
            json={"username": username, "password": password},
            timeout=10,
        )
    except http.exceptions.ConnectionError:
        return False, "Cannot reach the API server. Make sure the backend is running on localhost:8501."
    except http.exceptions.Timeout:
        return False, "Login request timed out. The API server may be overloaded."

    if resp.status_code == 200:
        data = resp.json()
        st.session_state["token"] = data["access_token"]
        st.session_state["refresh_token"] = data["refresh_token"]
        st.session_state["user"] = data["user"]
        return True, ""

    if resp.status_code == 401:
        return False, "Invalid username or password. Please try again."

    # Unexpected error — surface the detail if available.
    try:
        detail = resp.json().get("detail", resp.text)
    except Exception:
        detail = resp.text
    return False, f"Login failed ({resp.status_code}): {detail}"


def _do_logout() -> None:
    """POST /api/auth/logout then wipe session_state."""
    refresh_token = st.session_state.get("refresh_token", "")
    if refresh_token:
        try:
            http.post(
                f"{API_BASE}/auth/logout",
                json={"refresh_token": refresh_token},
                headers=_auth_headers(),
                timeout=5,
            )
        except Exception:
            # Best-effort: always clear client-side state even if the server
            # call fails so the user is not stuck.
            pass

    for key in ("token", "refresh_token", "user"):
        st.session_state.pop(key, None)


# ---------------------------------------------------------------------------
# Page rendering
# ---------------------------------------------------------------------------

st.title("Login")

user = st.session_state.get("user")
token = st.session_state.get("token")

# ── Already logged in ────────────────────────────────────────────────────────
if token and user:
    display_name = user.get("display_name", user.get("username", "Unknown"))
    role = user.get("role", "")
    role_label = ROLE_LABELS.get(role, role)

    st.success(f"Welcome, **{display_name}**!")

    info_col, action_col = st.columns([3, 1])

    with info_col:
        st.markdown(
            f"""
            | Field | Value |
            |---|---|
            | Username | `{user.get('username', '—')}` |
            | Display Name | {display_name} |
            | Role | {role_label} |
            | Email | {user.get('email') or '—'} |
            | Account Active | {'Yes' if user.get('is_active') else 'No'} |
            """
        )

    with action_col:
        st.write("")  # vertical spacing
        st.write("")
        if st.button("Logout", type="primary", use_container_width=True):
            _do_logout()
            st.success("You have been logged out.")
            st.rerun()

    st.divider()
    st.info(
        "Use the sidebar on the left to navigate to other pages. "
        "Your session will remain active until you click Logout or close the browser tab."
    )

# ── Not logged in — show login form ──────────────────────────────────────────
else:
    # Center the form with empty columns on either side.
    _, center_col, _ = st.columns([1, 2, 1])

    with center_col:
        st.markdown("### Sign in to your account")
        st.markdown("Enter your credentials below to access the estimation tool.")
        st.write("")

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input(
                "Username",
                placeholder="Enter your username",
                autocomplete="username",
            )
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                autocomplete="current-password",
            )

            st.write("")  # spacer before button

            submitted = st.form_submit_button(
                "Sign In",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            if not username.strip():
                st.error("Username is required.")
            elif not password:
                st.error("Password is required.")
            else:
                with st.spinner("Signing in..."):
                    success, error_msg = _do_login(username.strip(), password)

                if success:
                    logged_in_user = st.session_state.get("user", {})
                    name = logged_in_user.get("display_name", username)
                    st.success(f"Welcome, {name}! Redirecting…")
                    st.rerun()
                else:
                    st.error(error_msg)

        st.divider()
        st.caption(
            "If you do not have an account, ask an Administrator to create one for you."
        )
