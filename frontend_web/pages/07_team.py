"""Team member management page.

CRUD operations for team members and capacity planning.
"""

import json
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
from src.database.models import TeamMember

st.title("👥 Team Management")
st.markdown("Manage team members and track capacity")

engine = get_engine()

# Constants
TEAM_ROLES = ["TESTER", "TEST_LEADER"]
SKILL_OPTIONS = [
    "Android",
    "iOS",
    "Web",
    "Automation",
    "Performance Testing",
    "Security Testing",
    "API Testing",
    "Database Testing",
    "Integration Testing",
    "Regression Testing",
]


@st.cache_data(ttl=60)
def get_team_data():
    """Fetch all team members from the database."""
    with Session(engine) as session:
        members = session.query(TeamMember).all()
        data = []
        for m in members:
            # Parse skills
            skills = []
            try:
                skills = json.loads(m.skills_json or "[]")
            except (json.JSONDecodeError, TypeError):
                skills = []

            data.append({
                "ID": m.id,
                "Name": m.name,
                "Role": m.role,
                "Available Hours/Day": m.available_hours_per_day,
                "Skills": len(skills),
                "Skill List": skills,
            })
        return data


def get_member_by_id(member_id: int) -> TeamMember | None:
    """Fetch a single team member by ID."""
    with Session(engine) as session:
        return session.query(TeamMember).filter(TeamMember.id == member_id).first()


def add_member(
    name: str,
    role: str,
    available_hours_per_day: float,
    skills: list[str],
) -> bool:
    """Add a new team member."""
    try:
        with Session(engine) as session:
            member = TeamMember(
                name=name,
                role=role,
                available_hours_per_day=available_hours_per_day,
                skills_json=json.dumps(skills),
            )
            session.add(member)
            session.commit()
            return True
    except Exception as e:
        st.error(f"Error adding team member: {str(e)}")
        return False


def update_member(
    member_id: int,
    name: str,
    role: str,
    available_hours_per_day: float,
    skills: list[str],
) -> bool:
    """Update an existing team member."""
    try:
        with Session(engine) as session:
            member = session.query(TeamMember).filter(TeamMember.id == member_id).first()
            if not member:
                st.error("Team member not found")
                return False
            member.name = name
            member.role = role
            member.available_hours_per_day = available_hours_per_day
            member.skills_json = json.dumps(skills)
            session.commit()
            return True
    except Exception as e:
        st.error(f"Error updating team member: {str(e)}")
        return False


def delete_member(member_id: int) -> bool:
    """Delete a team member."""
    try:
        with Session(engine) as session:
            member = session.query(TeamMember).filter(TeamMember.id == member_id).first()
            if not member:
                st.error("Team member not found")
                return False
            session.delete(member)
            session.commit()
            return True
    except Exception as e:
        st.error(f"Error deleting team member: {str(e)}")
        return False


# Main UI
col1, col2 = st.columns([2, 1])

with col2:
    if st.button("+ Add Member", use_container_width=True):
        st.session_state["show_add_member"] = True

# Display team table
st.subheader("Team Members")

team_data = get_team_data()

if team_data:
    df = pd.DataFrame(team_data)

    # Sort by role and name
    df_sorted = df.sort_values(["Role", "Name"])

    # Display table
    st.dataframe(
        df_sorted[["ID", "Name", "Role", "Available Hours/Day", "Skills"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "ID": st.column_config.NumberColumn(width="small"),
            "Name": st.column_config.TextColumn(width="medium"),
            "Role": st.column_config.TextColumn(width="small"),
            "Available Hours/Day": st.column_config.NumberColumn(
                width="small", format="%.1f"
            ),
            "Skills": st.column_config.NumberColumn(width="small"),
        },
    )

    st.divider()

    # Team member management
    col1, col2 = st.columns(2)

    with col1:
        selected_id = st.selectbox(
            "Select team member to manage",
            df_sorted["ID"].tolist(),
            format_func=lambda x: df_sorted[df_sorted["ID"] == x]["Name"].values[0],
        )

        if selected_id:
            member = get_member_by_id(selected_id)
            if member:
                action = st.radio(
                    "Action",
                    ["View", "Edit", "Delete"],
                    horizontal=True,
                )

                if action == "View":
                    skills = []
                    try:
                        skills = json.loads(member.skills_json or "[]")
                    except (json.JSONDecodeError, TypeError):
                        skills = []

                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.info(f"**Name:** {member.name}")
                        st.info(f"**Role:** {member.role}")
                    with col_b:
                        st.info(
                            f"**Available Hours/Day:** {member.available_hours_per_day}"
                        )
                        st.info(f"**Skills:** {len(skills)}")

                    if skills:
                        st.markdown("**Skill Set:**")
                        skill_cols = st.columns(min(3, len(skills)))
                        for idx, skill in enumerate(skills):
                            with skill_cols[idx % len(skill_cols)]:
                                st.caption(f"✓ {skill}")

                elif action == "Edit":
                    skills = []
                    try:
                        skills = json.loads(member.skills_json or "[]")
                    except (json.JSONDecodeError, TypeError):
                        skills = []

                    with st.form(f"edit_member_{member.id}"):
                        st.write("**Edit Team Member**")

                        col_a, col_b = st.columns(2)
                        with col_a:
                            name = st.text_input("Name *", value=member.name)
                            role = st.selectbox(
                                "Role *",
                                TEAM_ROLES,
                                index=TEAM_ROLES.index(member.role)
                                if member.role in TEAM_ROLES
                                else 0,
                            )
                        with col_b:
                            available_hours = st.number_input(
                                "Available Hours per Day",
                                min_value=0.0,
                                max_value=24.0,
                                value=float(member.available_hours_per_day),
                                step=0.5,
                            )

                        selected_skills = st.multiselect(
                            "Skills",
                            SKILL_OPTIONS,
                            default=skills,
                            help="Select the skills this team member has",
                        )

                        if st.form_submit_button("Update Member"):
                            if name and role:
                                if update_member(
                                    member.id,
                                    name,
                                    role,
                                    available_hours,
                                    selected_skills,
                                ):
                                    st.success("Team member updated!")
                                    st.cache_data.clear()
                                    st.rerun()
                            else:
                                st.error("Name and Role are required")

                elif action == "Delete":
                    st.warning(
                        f"Are you sure you want to delete **{member.name}**? "
                        "This action cannot be undone."
                    )
                    if st.button(
                        "Delete Member",
                        type="primary",
                        key=f"delete_{member.id}",
                    ):
                        if delete_member(member.id):
                            st.success("Team member deleted!")
                            st.cache_data.clear()
                            st.rerun()

    with col2:
        st.metric("Total Members", len(df))

        testers = len(df[df["Role"] == "TESTER"])
        leaders = len(df[df["Role"] == "TEST_LEADER"])
        st.metric("Testers", testers)
        st.metric("Test Leaders", leaders)

        total_hours = df["Available Hours/Day"].sum()
        st.metric("Total Capacity (hours/day)", f"{total_hours:.1f}")

else:
    st.info("No team members found. Add one using the button above.")

st.divider()

# Add member form
if st.session_state.get("show_add_member"):
    st.subheader("Add New Team Member")

    with st.form("add_member_form"):
        col_a, col_b = st.columns(2)
        with col_a:
            name = st.text_input(
                "Member Name *",
                placeholder="e.g., John Smith",
            )
            role = st.selectbox("Role *", TEAM_ROLES)
        with col_b:
            available_hours = st.number_input(
                "Available Hours per Day",
                min_value=0.0,
                max_value=24.0,
                value=7.0,
                step=0.5,
                help="Working hours available per day",
            )

        selected_skills = st.multiselect(
            "Skills",
            SKILL_OPTIONS,
            help="Select the skills this team member possesses",
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Add Member"):
                if name and role:
                    if add_member(name, role, available_hours, selected_skills):
                        st.success("Team member added successfully!")
                        st.cache_data.clear()
                        st.session_state["show_add_member"] = False
                        st.rerun()
                else:
                    st.error("Name and Role are required")

        with col2:
            if st.form_submit_button("Cancel"):
                st.session_state["show_add_member"] = False
                st.rerun()

# Capacity Planning
if team_data:
    st.divider()
    st.subheader("Team Capacity Planning")

    df = pd.DataFrame(team_data)

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Capacity by Role**")
        capacity_by_role = (
            df.groupby("Role")["Available Hours/Day"]
            .agg(["count", "sum", "mean"])
            .round(1)
        )
        capacity_by_role.columns = ["Members", "Total Hours/Day", "Avg Hours/Day"]
        st.dataframe(capacity_by_role, use_container_width=True)

    with col2:
        st.write("**Skills Distribution**")
        all_skills = []
        for skills in df["Skill List"]:
            all_skills.extend(skills)

        if all_skills:
            from collections import Counter
            skill_counts = Counter(all_skills)
            skill_df = pd.DataFrame(
                skill_counts.items(),
                columns=["Skill", "Members"],
            ).sort_values("Members", ascending=False)
            st.dataframe(skill_df, use_container_width=True, hide_index=True)
        else:
            st.info("No skills assigned yet")

    st.divider()
    st.write("**Team Summary**")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Team Members", len(df))

    with col2:
        total_capacity = df["Available Hours/Day"].sum()
        st.metric("Total Daily Capacity", f"{total_capacity:.1f}h")

    with col3:
        avg_capacity = df["Available Hours/Day"].mean()
        st.metric("Average Hours/Day", f"{avg_capacity:.1f}h")

    with col4:
        unique_skills = len(set(all_skills)) if all_skills else 0
        st.metric("Unique Skills", unique_skills)
