"""Historical Projects browser and accuracy analysis.

Track past projects with estimated vs actual hours and accuracy metrics.
"""

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy.orm import Session

# Add backend to path
backend_path = str(Path(__file__).resolve().parent.parent.parent / "backend" / "src")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from database.migrations import get_engine
from database.models import HistoricalProject

st.title("📊 Project History")
st.markdown("Track completed projects and analyze estimation accuracy")

engine = get_engine()

# Constants
PROJECT_TYPES = ["NEW", "EVOLUTION", "SUPPORT"]


@st.cache_data(ttl=60)
def get_projects_data():
    """Fetch all historical projects from the database."""
    with Session(engine) as session:
        projects = session.query(HistoricalProject).all()
        data = []
        for p in projects:
            # Calculate accuracy ratio
            accuracy_ratio = None
            if p.estimated_hours and p.actual_hours:
                accuracy_ratio = p.actual_hours / p.estimated_hours

            # Parse features
            features = []
            try:
                features = json.loads(p.features_json or "[]")
            except (json.JSONDecodeError, TypeError):
                features = []

            data.append({
                "ID": p.id,
                "Project Name": p.project_name,
                "Type": p.project_type,
                "Estimated (h)": p.estimated_hours,
                "Actual (h)": p.actual_hours,
                "Accuracy": accuracy_ratio,
                "DUTs": p.dut_count,
                "Profiles": p.profile_count,
                "PRs": p.pr_count,
                "Completed": p.completion_date,
                "Features": len(features),
                "Notes": p.notes,
            })
        return data


def get_project_by_id(project_id: int) -> HistoricalProject | None:
    """Fetch a single project by ID."""
    with Session(engine) as session:
        return session.query(HistoricalProject).filter(
            HistoricalProject.id == project_id
        ).first()


def add_project(
    project_name: str,
    project_type: str,
    estimated_hours: float | None,
    actual_hours: float | None,
    dut_count: int | None,
    profile_count: int | None,
    pr_count: int | None,
    features: list[str],
    completion_date: date | None,
    notes: str | None,
) -> bool:
    """Add a new historical project."""
    try:
        with Session(engine) as session:
            project = HistoricalProject(
                project_name=project_name,
                project_type=project_type,
                estimated_hours=estimated_hours,
                actual_hours=actual_hours,
                dut_count=dut_count,
                profile_count=profile_count,
                pr_count=pr_count,
                features_json=json.dumps(features),
                completion_date=completion_date,
                notes=notes,
            )
            session.add(project)
            session.commit()
            return True
    except Exception as e:
        st.error(f"Error adding project: {str(e)}")
        return False


def update_project(
    project_id: int,
    project_name: str,
    project_type: str,
    estimated_hours: float | None,
    actual_hours: float | None,
    dut_count: int | None,
    profile_count: int | None,
    pr_count: int | None,
    features: list[str],
    completion_date: date | None,
    notes: str | None,
) -> bool:
    """Update an existing project."""
    try:
        with Session(engine) as session:
            project = session.query(HistoricalProject).filter(
                HistoricalProject.id == project_id
            ).first()
            if not project:
                st.error("Project not found")
                return False
            project.project_name = project_name
            project.project_type = project_type
            project.estimated_hours = estimated_hours
            project.actual_hours = actual_hours
            project.dut_count = dut_count
            project.profile_count = profile_count
            project.pr_count = pr_count
            project.features_json = json.dumps(features)
            project.completion_date = completion_date
            project.notes = notes
            session.commit()
            return True
    except Exception as e:
        st.error(f"Error updating project: {str(e)}")
        return False


def delete_project(project_id: int) -> bool:
    """Delete a project."""
    try:
        with Session(engine) as session:
            project = session.query(HistoricalProject).filter(
                HistoricalProject.id == project_id
            ).first()
            if not project:
                st.error("Project not found")
                return False
            session.delete(project)
            session.commit()
            return True
    except Exception as e:
        st.error(f"Error deleting project: {str(e)}")
        return False


def get_accuracy_color(ratio: float | None) -> str:
    """Get color indicator for accuracy ratio."""
    if ratio is None:
        return "gray"
    if ratio < 1.0:
        return "green"
    elif ratio <= 1.3:
        return "orange"
    else:
        return "red"


# Main UI
col1, col2 = st.columns([2, 1])

with col2:
    if st.button("+ Add Project", use_container_width=True):
        st.session_state["show_add_project"] = True

# Display projects table
st.subheader("Historical Projects")

projects_data = get_projects_data()

if projects_data:
    df = pd.DataFrame(projects_data)

    # Sort by completion date (most recent first)
    df_sorted = df.sort_values("Completed", ascending=False, na_position="last")

    # Display table with styled accuracy column
    st.dataframe(
        df_sorted,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ID": st.column_config.NumberColumn(width="small"),
            "Project Name": st.column_config.TextColumn(width="medium"),
            "Type": st.column_config.TextColumn(width="small"),
            "Estimated (h)": st.column_config.NumberColumn(width="small", format="%.1f"),
            "Actual (h)": st.column_config.NumberColumn(width="small", format="%.1f"),
            "Accuracy": st.column_config.NumberColumn(width="small", format="%.2f"),
            "DUTs": st.column_config.NumberColumn(width="small"),
            "Profiles": st.column_config.NumberColumn(width="small"),
            "PRs": st.column_config.NumberColumn(width="small"),
            "Completed": st.column_config.DateColumn(width="small"),
            "Features": st.column_config.NumberColumn(width="small"),
            "Notes": st.column_config.TextColumn(width="large"),
        },
    )

    st.divider()

    # Project management
    col1, col2 = st.columns(2)

    with col1:
        selected_id = st.selectbox(
            "Select project to manage",
            df_sorted["ID"].tolist(),
            format_func=lambda x: df_sorted[df_sorted["ID"] == x]["Project Name"].values[0],
        )

        if selected_id:
            project = get_project_by_id(selected_id)
            if project:
                action = st.radio(
                    "Action",
                    ["View", "Edit", "Delete"],
                    horizontal=True,
                )

                if action == "View":
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.info(f"**Name:** {project.project_name}")
                        st.info(f"**Type:** {project.project_type}")
                        st.info(f"**Completion Date:** {project.completion_date}")
                    with col_b:
                        st.info(f"**Estimated Hours:** {project.estimated_hours or 'N/A'}")
                        st.info(f"**Actual Hours:** {project.actual_hours or 'N/A'}")
                        if project.estimated_hours and project.actual_hours:
                            accuracy = project.actual_hours / project.estimated_hours
                            color = get_accuracy_color(accuracy)
                            st.info(f"**Accuracy Ratio:** {accuracy:.2f} ({color})")

                    st.markdown("---")
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.metric("DUTs", project.dut_count or 0)
                    with col_b:
                        st.metric("Test Profiles", project.profile_count or 0)
                    with col_c:
                        st.metric("PRs Fixed", project.pr_count or 0)

                    if project.notes:
                        st.markdown("**Notes:**")
                        st.text(project.notes)

                    try:
                        features = json.loads(project.features_json or "[]")
                        if features:
                            st.markdown("**Features:**")
                            for feature in features:
                                st.caption(f"• {feature}")
                    except (json.JSONDecodeError, TypeError):
                        pass

                elif action == "Edit":
                    features = []
                    try:
                        features = json.loads(project.features_json or "[]")
                    except (json.JSONDecodeError, TypeError):
                        features = []

                    with st.form(f"edit_project_{project.id}"):
                        st.write("**Edit Project**")

                        col_a, col_b = st.columns(2)
                        with col_a:
                            name = st.text_input("Project Name *", value=project.project_name)
                            project_type = st.selectbox(
                                "Project Type *",
                                PROJECT_TYPES,
                                index=PROJECT_TYPES.index(project.project_type)
                                if project.project_type in PROJECT_TYPES
                                else 0,
                            )
                        with col_b:
                            completion = st.date_input(
                                "Completion Date",
                                value=project.completion_date,
                            )

                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            est_hours = st.number_input(
                                "Estimated Hours",
                                min_value=0.0,
                                value=float(project.estimated_hours or 0),
                                step=0.5,
                            )
                        with col_b:
                            act_hours = st.number_input(
                                "Actual Hours",
                                min_value=0.0,
                                value=float(project.actual_hours or 0),
                                step=0.5,
                            )
                        with col_c:
                            st.write("")  # Spacer
                            st.write("")  # Spacer
                            if est_hours > 0 and act_hours > 0:
                                accuracy = act_hours / est_hours
                                color = get_accuracy_color(accuracy)
                                st.metric("Accuracy", f"{accuracy:.2f} ({color})")

                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            dut_count = st.number_input(
                                "DUT Count",
                                min_value=0,
                                value=project.dut_count or 0,
                                step=1,
                            )
                        with col_b:
                            profile_count = st.number_input(
                                "Profile Count",
                                min_value=0,
                                value=project.profile_count or 0,
                                step=1,
                            )
                        with col_c:
                            pr_count = st.number_input(
                                "PR Count",
                                min_value=0,
                                value=project.pr_count or 0,
                                step=1,
                            )

                        features_text = st.text_area(
                            "Features (one per line)",
                            value="\n".join(features),
                            height=100,
                        )

                        notes = st.text_area(
                            "Notes",
                            value=project.notes or "",
                            height=80,
                        )

                        if st.form_submit_button("Update Project"):
                            if name and project_type:
                                features_list = [
                                    f.strip()
                                    for f in features_text.split("\n")
                                    if f.strip()
                                ]
                                if update_project(
                                    project.id,
                                    name,
                                    project_type,
                                    est_hours if est_hours > 0 else None,
                                    act_hours if act_hours > 0 else None,
                                    dut_count if dut_count > 0 else None,
                                    profile_count if profile_count > 0 else None,
                                    pr_count if pr_count > 0 else None,
                                    features_list,
                                    completion,
                                    notes if notes else None,
                                ):
                                    st.success("Project updated!")
                                    st.cache_data.clear()
                                    st.rerun()
                            else:
                                st.error("Name and Type are required")

                elif action == "Delete":
                    st.warning(
                        f"Are you sure you want to delete **{project.project_name}**? "
                        "This action cannot be undone."
                    )
                    if st.button(
                        "Delete Project",
                        type="primary",
                        key=f"delete_{project.id}",
                    ):
                        if delete_project(project.id):
                            st.success("Project deleted!")
                            st.cache_data.clear()
                            st.rerun()

    with col2:
        st.metric("Total Projects", len(df))
        st.metric("Project Types", df["Type"].nunique())

        # Calculate accuracy stats
        valid_accuracy = df["Accuracy"].dropna()
        if len(valid_accuracy) > 0:
            st.metric("Average Accuracy", f"{valid_accuracy.mean():.2f}")
            st.metric("Best Accuracy", f"{valid_accuracy.min():.2f}")
            st.metric("Worst Accuracy", f"{valid_accuracy.max():.2f}")
        else:
            st.metric("Average Accuracy", "N/A")

else:
    st.info("No historical projects found. Add one using the button above.")

st.divider()

# Add project form
if st.session_state.get("show_add_project"):
    st.subheader("Add New Historical Project")

    with st.form("add_project_form"):
        col_a, col_b = st.columns(2)
        with col_a:
            name = st.text_input(
                "Project Name *",
                placeholder="e.g., Project Alpha v2.0",
            )
            project_type = st.selectbox("Project Type *", PROJECT_TYPES)
        with col_b:
            completion_date = st.date_input("Completion Date")

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            est_hours = st.number_input(
                "Estimated Hours",
                min_value=0.0,
                value=0.0,
                step=0.5,
            )
        with col_b:
            act_hours = st.number_input(
                "Actual Hours",
                min_value=0.0,
                value=0.0,
                step=0.5,
            )
        with col_c:
            if est_hours > 0 and act_hours > 0:
                accuracy = act_hours / est_hours
                color = get_accuracy_color(accuracy)
                st.metric("Accuracy", f"{accuracy:.2f} ({color})")

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            dut_count = st.number_input(
                "DUT Count",
                min_value=0,
                value=1,
                step=1,
            )
        with col_b:
            profile_count = st.number_input(
                "Profile Count",
                min_value=0,
                value=1,
                step=1,
            )
        with col_c:
            pr_count = st.number_input(
                "PR Count",
                min_value=0,
                value=0,
                step=1,
            )

        features_text = st.text_area(
            "Features (one per line)",
            placeholder="Feature 1\nFeature 2\nFeature 3",
            height=100,
        )

        notes = st.text_area(
            "Notes",
            placeholder="Any additional notes about the project...",
            height=80,
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Add Project"):
                if name and project_type:
                    features_list = [
                        f.strip()
                        for f in features_text.split("\n")
                        if f.strip()
                    ]
                    if add_project(
                        name,
                        project_type,
                        est_hours if est_hours > 0 else None,
                        act_hours if act_hours > 0 else None,
                        dut_count if dut_count > 0 else None,
                        profile_count if profile_count > 0 else None,
                        pr_count if pr_count > 0 else None,
                        features_list,
                        completion_date,
                        notes if notes else None,
                    ):
                        st.success("Project added successfully!")
                        st.cache_data.clear()
                        st.session_state["show_add_project"] = False
                        st.rerun()
                else:
                    st.error("Name and Type are required")

        with col2:
            if st.form_submit_button("Cancel"):
                st.session_state["show_add_project"] = False
                st.rerun()

# Analytics
if projects_data:
    st.divider()
    st.subheader("Accuracy Analytics")

    df = pd.DataFrame(projects_data)
    valid_df = df[df["Accuracy"].notna()].copy()

    if len(valid_df) > 0:
        col1, col2 = st.columns(2)

        with col1:
            st.write("**Accuracy Distribution by Project Type**")
            accuracy_by_type = valid_df.groupby("Type")["Accuracy"].agg(
                ["count", "mean", "min", "max"]
            ).round(2)
            st.dataframe(accuracy_by_type, use_container_width=True)

        with col2:
            st.write("**Accuracy Status Summary**")
            status_counts = {
                "Under-estimated (<1.0)": len(valid_df[valid_df["Accuracy"] < 1.0]),
                "Well-estimated (1.0-1.3)": len(
                    valid_df[(valid_df["Accuracy"] >= 1.0) & (valid_df["Accuracy"] <= 1.3)]
                ),
                "Over-estimated (>1.3)": len(valid_df[valid_df["Accuracy"] > 1.3]),
            }
            for status, count in status_counts.items():
                st.write(f"{status}: **{count}** projects")
