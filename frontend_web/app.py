"""Main Streamlit application entry point.

Run with: streamlit run frontend_web/app.py
"""

__version__ = "1.0.0"

import sys
from pathlib import Path

import streamlit as st

# Add backend to path
backend_path = str(Path(__file__).resolve().parent.parent / "backend" / "src")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Initialize database on first run
from database.migrations import init_database
init_database()

st.set_page_config(
    page_title="Test Effort Estimation Tool",
    page_icon=":material/assignment:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Grouped navigation using st.navigation with icons on section headers
pages = {
    "📊 Overview": [
        st.Page("pages/01_dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
        st.Page("pages/10_request_inbox.py", title="Request Inbox", icon=":material/inbox:"),
    ],
    "📋 Estimation": [
        st.Page("pages/02_new_estimation.py", title="New Estimation", icon=":material/add_circle:"),
        st.Page("pages/09_estimation_detail.py", title="Estimation Detail", icon=":material/description:"),
    ],
    "🗄️ Data Management": [
        st.Page("pages/03_feature_catalog.py", title="Feature Catalog", icon=":material/category:"),
        st.Page("pages/04_dut_registry.py", title="DUT Registry", icon=":material/devices:"),
        st.Page("pages/05_profiles.py", title="Test Profiles", icon=":material/tune:"),
        st.Page("pages/06_history.py", title="Historical Projects", icon=":material/history:"),
        st.Page("pages/07_team.py", title="Team Members", icon=":material/group:"),
    ],
    "⚙️ Administration": [
        st.Page("pages/08_settings.py", title="Settings", icon=":material/settings:"),
        st.Page("pages/11_integrations.py", title="Integrations", icon=":material/sync:"),
    ],
}

pg = st.navigation(pages)
pg.run()
