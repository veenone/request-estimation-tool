"""Main Streamlit application entry point.

Run with: streamlit run frontend_web/app.py
"""

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
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.sidebar.title("Estimation Tool")
st.sidebar.markdown("---")

st.title("Test Effort Estimation Tool")
st.markdown("### Welcome to the Test Effort Estimation Tool")
st.markdown(
    """
    Use the sidebar to navigate between pages:

    - **Dashboard** — View all estimations and requests
    - **New Estimation** — Create a new estimation using the 7-step wizard
    - **Feature Catalog** — Manage testable features and task templates
    - **DUT Registry** — Manage device types and complexity multipliers
    - **Profiles** — Manage test configuration profiles
    - **History** — Browse historical projects for calibration
    - **Team** — Manage team members and availability
    - **Settings** — Configure global parameters
    """
)
