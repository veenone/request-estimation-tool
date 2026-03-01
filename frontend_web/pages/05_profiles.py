"""Test Profiles management page.

CRUD operations for test profiles and their configurations.
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy.orm import Session

# Add backend to path
backend_path = str(Path(__file__).resolve().parent.parent.parent / "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from src.database.migrations import get_engine
from src.database.models import TestProfile

st.title("⚙️ Test Profiles")
st.markdown("Manage test profile configurations and effort multipliers")

engine = get_engine()


@st.cache_data(ttl=60)
def get_profiles_data():
    """Fetch all test profiles from the database."""
    with Session(engine) as session:
        profiles = session.query(TestProfile).all()
        return [
            {
                "ID": p.id,
                "Name": p.name,
                "Description": p.description or "",
                "Effort Multiplier": p.effort_multiplier,
            }
            for p in profiles
        ]


def get_profile_by_id(profile_id: int) -> TestProfile | None:
    """Fetch a single test profile by ID."""
    with Session(engine) as session:
        return session.query(TestProfile).filter(
            TestProfile.id == profile_id
        ).first()


def add_profile(name: str, description: str, effort_multiplier: float) -> bool:
    """Add a new test profile."""
    try:
        with Session(engine) as session:
            profile = TestProfile(
                name=name,
                description=description if description else None,
                effort_multiplier=effort_multiplier,
            )
            session.add(profile)
            session.commit()
            return True
    except Exception as e:
        st.error(f"Error adding profile: {str(e)}")
        return False


def update_profile(profile_id: int, name: str, description: str,
                   effort_multiplier: float) -> bool:
    """Update an existing test profile."""
    try:
        with Session(engine) as session:
            profile = session.query(TestProfile).filter(
                TestProfile.id == profile_id
            ).first()
            if not profile:
                st.error("Profile not found")
                return False
            profile.name = name
            profile.description = description if description else None
            profile.effort_multiplier = effort_multiplier
            session.commit()
            return True
    except Exception as e:
        st.error(f"Error updating profile: {str(e)}")
        return False


def delete_profile(profile_id: int) -> bool:
    """Delete a test profile."""
    try:
        with Session(engine) as session:
            profile = session.query(TestProfile).filter(
                TestProfile.id == profile_id
            ).first()
            if not profile:
                st.error("Profile not found")
                return False
            session.delete(profile)
            session.commit()
            return True
    except Exception as e:
        st.error(f"Error deleting profile: {str(e)}")
        return False


# Main UI
col1, col2 = st.columns([2, 1])

with col2:
    if st.button("+ Add Profile", use_container_width=True):
        st.session_state["show_add_profile"] = True

# Display profiles table
st.subheader("Test Profiles")

profiles_data = get_profiles_data()

if profiles_data:
    df = pd.DataFrame(profiles_data)

    # Sort by name
    df_sorted = df.sort_values("Name")

    # Display dataframe with nice formatting
    st.dataframe(
        df_sorted,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ID": st.column_config.NumberColumn(width="small"),
            "Name": st.column_config.TextColumn(width="medium"),
            "Description": st.column_config.TextColumn(width="large"),
            "Effort Multiplier": st.column_config.NumberColumn(
                width="small", format="%.2f"
            ),
        },
    )

    st.divider()

    # Profile management
    col1, col2 = st.columns(2)

    with col1:
        selected_id = st.selectbox(
            "Select profile to manage",
            df["ID"].tolist(),
            format_func=lambda x: df[df["ID"] == x]["Name"].values[0],
        )

        if selected_id:
            profile = get_profile_by_id(selected_id)
            if profile:
                action = st.radio(
                    "Action",
                    ["View", "Edit", "Delete"],
                    horizontal=True,
                )

                if action == "View":
                    st.info(f"**Name:** {profile.name}")
                    st.info(
                        f"**Description:** {profile.description or 'No description'}"
                    )
                    st.info(f"**Effort Multiplier:** {profile.effort_multiplier:.2f}x")
                    st.caption(
                        "This multiplier is applied to estimated effort hours "
                        "for projects using this profile."
                    )

                elif action == "Edit":
                    with st.form(f"edit_profile_{profile.id}"):
                        st.write("**Edit Test Profile**")
                        name = st.text_input("Profile Name *", value=profile.name)
                        description = st.text_area(
                            "Description",
                            value=profile.description or "",
                            height=100,
                        )
                        effort_multiplier = st.number_input(
                            "Effort Multiplier",
                            min_value=0.5,
                            max_value=5.0,
                            value=float(profile.effort_multiplier),
                            step=0.1,
                            help="Multiplier applied to base effort estimates",
                        )

                        if st.form_submit_button("Update Profile"):
                            if name:
                                if update_profile(
                                    profile.id, name, description, effort_multiplier
                                ):
                                    st.success("Profile updated!")
                                    st.cache_data.clear()
                                    st.rerun()
                            else:
                                st.error("Profile name is required")

                elif action == "Delete":
                    st.warning(
                        f"Are you sure you want to delete **{profile.name}**? "
                        "This action cannot be undone."
                    )
                    if st.button(
                        "Delete Profile",
                        type="primary",
                        key=f"delete_{profile.id}",
                    ):
                        if delete_profile(profile.id):
                            st.success("Profile deleted!")
                            st.cache_data.clear()
                            st.rerun()

    with col2:
        st.metric("Total Profiles", len(df))
        avg_multiplier = df["Effort Multiplier"].mean()
        st.metric("Avg Multiplier", f"{avg_multiplier:.2f}x")
        max_multiplier = df["Effort Multiplier"].max()
        st.metric("Max Multiplier", f"{max_multiplier:.2f}x")

else:
    st.info("No test profiles found. Add one using the button above.")

st.divider()

# Add profile form
if st.session_state.get("show_add_profile"):
    st.subheader("Add New Test Profile")

    with st.form("add_profile_form"):
        name = st.text_input(
            "Profile Name *",
            placeholder="e.g., Smoke Testing, Full Regression, Load Testing",
        )
        description = st.text_area(
            "Description",
            placeholder="Describe what this test profile covers...",
            height=100,
        )
        effort_multiplier = st.number_input(
            "Effort Multiplier *",
            min_value=0.5,
            max_value=5.0,
            value=1.0,
            step=0.1,
            help=(
                "Multiplier to apply to base effort estimates. "
                "For example:\n"
                "- 0.5x for smoke testing (reduced scope)\n"
                "- 1.0x for standard testing\n"
                "- 2.0x for comprehensive testing"
            ),
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Add Profile"):
                if name and effort_multiplier:
                    if add_profile(name, description, effort_multiplier):
                        st.success("Profile added successfully!")
                        st.cache_data.clear()
                        st.session_state["show_add_profile"] = False
                        st.rerun()
                else:
                    st.error("Profile name and effort multiplier are required")

        with col2:
            if st.form_submit_button("Cancel"):
                st.session_state["show_add_profile"] = False
                st.rerun()

# Profile templates
st.divider()
st.subheader("Profile Templates")

st.markdown(
    """
    Use these as templates when creating new profiles:

    | Profile | Multiplier | Use Case |
    |---------|-----------|----------|
    | **Smoke Test** | 0.5x | Quick validation, basic functionality |
    | **Standard** | 1.0x | Normal test coverage |
    | **Extended** | 1.5x | Enhanced coverage with edge cases |
    | **Comprehensive** | 2.0x | Full regression, all scenarios |
    | **Load Testing** | 2.5x | Performance, stress, stability testing |
    | **Security Testing** | 2.0x | Security analysis and penetration |
    """
)

# Statistics
st.divider()
st.subheader("Profile Statistics")

if profiles_data:
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Profiles", len(profiles_data))

    with col2:
        avg_multiplier = sum(
            p["Effort Multiplier"] for p in profiles_data
        ) / len(profiles_data)
        st.metric("Avg Multiplier", f"{avg_multiplier:.2f}x")

    with col3:
        max_multiplier = max(p["Effort Multiplier"] for p in profiles_data)
        st.metric("Max Multiplier", f"{max_multiplier:.2f}x")

    with col4:
        min_multiplier = min(p["Effort Multiplier"] for p in profiles_data)
        st.metric("Min Multiplier", f"{min_multiplier:.2f}x")

    # Multiplier distribution
    st.write("**Multiplier Distribution**")
    df_sorted = df.sort_values("Effort Multiplier")
    st.bar_chart(
        df_sorted.set_index("Name")["Effort Multiplier"],
        use_container_width=True,
    )
