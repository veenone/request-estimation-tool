"""Main Streamlit application entry point.

Run with: streamlit run frontend_web/app.py
"""

__version__ = "2.0.0"

import sys
from pathlib import Path

import requests as http
import streamlit as st

# Add backend to path — use the backend dir (not backend/src) so that
# relative imports inside src.database, src.auth etc. resolve correctly.
backend_path = str(Path(__file__).resolve().parent.parent / "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Initialize database on first run
from src.database.migrations import init_database
init_database()

st.set_page_config(
    page_title="Test Effort Estimation Tool",
    page_icon=":material/assignment:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_BASE = "http://localhost:8501/api"

ROLE_LABELS = {
    "ADMIN": "Administrator",
    "APPROVER": "Approver",
    "ESTIMATOR": "Estimator",
    "VIEWER": "Viewer",
}

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def _do_logout() -> None:
    """Call POST /api/auth/logout then wipe session state."""
    refresh_token = st.session_state.get("refresh_token", "")
    token = st.session_state.get("token", "")
    if refresh_token:
        try:
            http.post(
                f"{API_BASE}/auth/logout",
                json={"refresh_token": refresh_token},
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
        except Exception:
            # Best-effort: always clear client state even if the server call fails.
            pass

    for key in ("token", "refresh_token", "user"):
        st.session_state.pop(key, None)


# ---------------------------------------------------------------------------
# Sidebar — user info + logout (rendered on every page)
# ---------------------------------------------------------------------------

user = st.session_state.get("user")
token = st.session_state.get("token")

if token and user:
    display_name = user.get("display_name", user.get("username", "Unknown"))
    role = user.get("role", "")
    role_label = ROLE_LABELS.get(role, role)

    with st.sidebar:
        st.divider()
        st.markdown(f"**{display_name}**")
        st.caption(f"Role: {role_label}")
        if st.button("Logout", key="sidebar_logout_btn", use_container_width=True):
            _do_logout()
            st.rerun()
else:
    role = None
    with st.sidebar:
        st.divider()
        st.caption("Not logged in. Go to the Login page.")

# ---------------------------------------------------------------------------
# Auth guard — show a prompt for unauthenticated visitors on non-login pages
# ---------------------------------------------------------------------------

if not token:
    st.info(
        "You are not logged in. Please go to the **Login** page using the sidebar "
        "to sign in before accessing the tool."
    )

# ---------------------------------------------------------------------------
# Role-aware navigation
# ---------------------------------------------------------------------------

# Always-visible pages
overview_pages = [
    st.Page("pages/01_dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
    st.Page("pages/10_request_inbox.py", title="Request Inbox", icon=":material/inbox:"),
]

estimation_pages = [
    st.Page("pages/02_new_estimation.py", title="New Estimation", icon=":material/add_circle:"),
    st.Page("pages/09_estimation_detail.py", title="Estimation Detail", icon=":material/description:"),
]

data_pages = [
    st.Page("pages/03_feature_catalog.py", title="Feature Catalog", icon=":material/category:"),
    st.Page("pages/04_dut_registry.py", title="DUT Registry", icon=":material/devices:"),
    st.Page("pages/05_profiles.py", title="Test Profiles", icon=":material/tune:"),
    st.Page("pages/06_history.py", title="Historical Projects", icon=":material/history:"),
    st.Page("pages/07_team.py", title="Team Members", icon=":material/group:"),
]

admin_pages = [
    st.Page("pages/08_settings.py", title="Settings", icon=":material/settings:"),
    st.Page("pages/11_integrations.py", title="Integrations", icon=":material/sync:"),
]

# User Management page is only shown in the sidebar for ADMINs, but the page
# itself also enforces the ADMIN check so it is safe to access directly.
if role == "ADMIN":
    admin_pages.append(
        st.Page("pages/12_users.py", title="User Management", icon=":material/manage_accounts:")
    )

# Auth pages — always available so unauthenticated users can reach Login.
auth_pages = [
    st.Page("pages/00_login.py", title="Login", icon=":material/login:"),
]

pages = {
    "🔐 Account": auth_pages,
    "📊 Overview": overview_pages,
    "📋 Estimation": estimation_pages,
    "🗄️ Data Management": data_pages,
    "⚙️ Administration": admin_pages,
}

pg = st.navigation(pages)
pg.run()
