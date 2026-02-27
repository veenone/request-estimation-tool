"""Feature Catalog and Task Templates management page.

CRUD operations for features and their associated task templates.
"""

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import func
from sqlalchemy.orm import Session

# Add backend to path
backend_path = str(Path(__file__).resolve().parent.parent.parent / "backend" / "src")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from database.migrations import get_engine
from database.models import Feature, TaskTemplate

st.set_page_config(
    page_title="Feature Catalog — Estimation Tool",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🗂️ Feature Catalog")
st.markdown("Manage test features and task templates")

engine = get_engine()

# Task type options
TASK_TYPES = ["SETUP", "EXECUTION", "ANALYSIS", "REPORTING", "STUDY"]


@st.cache_data(ttl=60)
def get_features_data():
    """Fetch all features from the database."""
    with Session(engine) as session:
        features = session.query(Feature).all()
        return [
            {
                "ID": f.id,
                "Name": f.name,
                "Category": f.category or "Uncategorized",
                "Complexity Weight": f.complexity_weight,
                "Has Tests": "Yes" if f.has_existing_tests else "No",
                "Description": f.description or "",
                "Created": f.created_at.strftime("%Y-%m-%d") if f.created_at else "",
            }
            for f in features
        ]


def get_feature_by_id(feature_id: int) -> Feature | None:
    """Fetch a single feature by ID."""
    with Session(engine) as session:
        return session.query(Feature).filter(Feature.id == feature_id).first()


def get_task_templates_for_feature(feature_id: int):
    """Fetch task templates for a specific feature."""
    with Session(engine) as session:
        templates = session.query(TaskTemplate).filter(
            TaskTemplate.feature_id == feature_id
        ).all()
        return [
            {
                "ID": t.id,
                "Name": t.name,
                "Type": t.task_type,
                "Base Hours": t.base_effort_hours,
                "Scales DUT": "Yes" if t.scales_with_dut else "No",
                "Scales Profile": "Yes" if t.scales_with_profile else "No",
                "Parallelizable": "Yes" if t.is_parallelizable else "No",
                "Description": t.description or "",
            }
            for t in templates
        ]


def add_feature(name: str, category: str, complexity_weight: float,
                has_tests: bool, description: str) -> bool:
    """Add a new feature."""
    try:
        with Session(engine) as session:
            feature = Feature(
                name=name,
                category=category if category else None,
                complexity_weight=complexity_weight,
                has_existing_tests=has_tests,
                description=description if description else None,
            )
            session.add(feature)
            session.commit()
            return True
    except Exception as e:
        st.error(f"Error adding feature: {str(e)}")
        return False


def update_feature(feature_id: int, name: str, category: str,
                   complexity_weight: float, has_tests: bool,
                   description: str) -> bool:
    """Update an existing feature."""
    try:
        with Session(engine) as session:
            feature = session.query(Feature).filter(Feature.id == feature_id).first()
            if not feature:
                st.error("Feature not found")
                return False
            feature.name = name
            feature.category = category if category else None
            feature.complexity_weight = complexity_weight
            feature.has_existing_tests = has_tests
            feature.description = description if description else None
            session.commit()
            return True
    except Exception as e:
        st.error(f"Error updating feature: {str(e)}")
        return False


def delete_feature(feature_id: int) -> bool:
    """Delete a feature and its task templates."""
    try:
        with Session(engine) as session:
            feature = session.query(Feature).filter(Feature.id == feature_id).first()
            if not feature:
                st.error("Feature not found")
                return False
            session.delete(feature)
            session.commit()
            return True
    except Exception as e:
        st.error(f"Error deleting feature: {str(e)}")
        return False


def add_task_template(feature_id: int, name: str, task_type: str,
                      base_hours: float, scales_dut: bool, scales_profile: bool,
                      parallelizable: bool, description: str) -> bool:
    """Add a new task template."""
    try:
        with Session(engine) as session:
            template = TaskTemplate(
                feature_id=feature_id,
                name=name,
                task_type=task_type,
                base_effort_hours=base_hours,
                scales_with_dut=scales_dut,
                scales_with_profile=scales_profile,
                is_parallelizable=parallelizable,
                description=description if description else None,
            )
            session.add(template)
            session.commit()
            return True
    except Exception as e:
        st.error(f"Error adding task template: {str(e)}")
        return False


def update_task_template(template_id: int, name: str, task_type: str,
                        base_hours: float, scales_dut: bool, scales_profile: bool,
                        parallelizable: bool, description: str) -> bool:
    """Update an existing task template."""
    try:
        with Session(engine) as session:
            template = session.query(TaskTemplate).filter(
                TaskTemplate.id == template_id
            ).first()
            if not template:
                st.error("Task template not found")
                return False
            template.name = name
            template.task_type = task_type
            template.base_effort_hours = base_hours
            template.scales_with_dut = scales_dut
            template.scales_with_profile = scales_profile
            template.is_parallelizable = parallelizable
            template.description = description if description else None
            session.commit()
            return True
    except Exception as e:
        st.error(f"Error updating task template: {str(e)}")
        return False


def delete_task_template(template_id: int) -> bool:
    """Delete a task template."""
    try:
        with Session(engine) as session:
            template = session.query(TaskTemplate).filter(
                TaskTemplate.id == template_id
            ).first()
            if not template:
                st.error("Task template not found")
                return False
            session.delete(template)
            session.commit()
            return True
    except Exception as e:
        st.error(f"Error deleting task template: {str(e)}")
        return False


# Main UI
tabs = st.tabs(["Features", "Add/Edit Feature"])

# Tab 1: View Features
with tabs[0]:
    st.subheader("All Features")

    features_data = get_features_data()

    if features_data:
        # Display grouped by category
        df = pd.DataFrame(features_data)
        categories = sorted(df["Category"].unique())

        for category in categories:
            st.write(f"**{category}**")
            category_df = df[df["Category"] == category][
                ["ID", "Name", "Complexity Weight", "Has Tests", "Created"]
            ]
            st.dataframe(category_df, use_container_width=True, hide_index=True)

            # Feature management for this category
            col1, col2 = st.columns(2)

            with col1:
                st.write("**Manage:**")
                selected_id = st.selectbox(
                    "Select feature",
                    category_df["ID"].tolist(),
                    format_func=lambda x: category_df[category_df["ID"] == x]["Name"].values[0],
                    key=f"select_{category}",
                )

                if selected_id:
                    feature = get_feature_by_id(selected_id)
                    if feature:
                        # Show task templates
                        st.write(f"**Task Templates for {feature.name}:**")
                        templates = get_task_templates_for_feature(feature.id)

                        if templates:
                            template_df = pd.DataFrame(templates)
                            st.dataframe(
                                template_df[["Name", "Type", "Base Hours", "Scales DUT",
                                           "Scales Profile", "Parallelizable"]],
                                use_container_width=True,
                                hide_index=True,
                            )

                            # Template management
                            template_col1, template_col2 = st.columns(2)

                            with template_col1:
                                action = st.radio(
                                    "Template action",
                                    ["View", "Edit", "Delete"],
                                    key=f"template_action_{feature.id}",
                                )

                                if action in ["Edit", "Delete"]:
                                    template_id = st.selectbox(
                                        "Select template",
                                        template_df["ID"].tolist(),
                                        format_func=lambda x: template_df[template_df["ID"] == x]["Name"].values[0],
                                        key=f"template_select_{feature.id}",
                                    )

                                    if action == "Edit":
                                        tmpl = None
                                        with Session(engine) as session:
                                            tmpl = session.query(TaskTemplate).filter(
                                                TaskTemplate.id == template_id
                                            ).first()

                                        if tmpl:
                                            with st.form(f"edit_template_{tmpl.id}"):
                                                st.write("**Edit Task Template**")
                                                name = st.text_input("Name", value=tmpl.name)
                                                task_type = st.selectbox(
                                                    "Type",
                                                    TASK_TYPES,
                                                    index=TASK_TYPES.index(tmpl.task_type),
                                                )
                                                base_hours = st.number_input(
                                                    "Base Effort (hours)",
                                                    min_value=0.5,
                                                    value=float(tmpl.base_effort_hours),
                                                    step=0.5,
                                                )
                                                scales_dut = st.checkbox(
                                                    "Scales with DUT count",
                                                    value=tmpl.scales_with_dut,
                                                )
                                                scales_profile = st.checkbox(
                                                    "Scales with profile count",
                                                    value=tmpl.scales_with_profile,
                                                )
                                                parallelizable = st.checkbox(
                                                    "Is parallelizable",
                                                    value=tmpl.is_parallelizable,
                                                )
                                                description = st.text_area(
                                                    "Description",
                                                    value=tmpl.description or "",
                                                )

                                                if st.form_submit_button("Update Template"):
                                                    if update_task_template(
                                                        tmpl.id, name, task_type,
                                                        base_hours, scales_dut,
                                                        scales_profile, parallelizable,
                                                        description,
                                                    ):
                                                        st.success("Template updated!")
                                                        st.cache_data.clear()
                                                        st.rerun()

                                    elif action == "Delete":
                                        if st.button(
                                            "Delete template",
                                            key=f"delete_template_{template_id}",
                                        ):
                                            if delete_task_template(template_id):
                                                st.success("Template deleted!")
                                                st.cache_data.clear()
                                                st.rerun()
                        else:
                            st.info("No task templates for this feature")

                        # Add new template
                        with st.expander("Add Task Template"):
                            with st.form(f"add_template_{feature.id}"):
                                st.write("**Add New Task Template**")
                                name = st.text_input("Name")
                                task_type = st.selectbox("Type", TASK_TYPES)
                                base_hours = st.number_input(
                                    "Base Effort (hours)", min_value=0.5, step=0.5
                                )
                                scales_dut = st.checkbox("Scales with DUT count")
                                scales_profile = st.checkbox("Scales with profile count")
                                parallelizable = st.checkbox("Is parallelizable")
                                description = st.text_area("Description")

                                if st.form_submit_button("Add Template"):
                                    if name and task_type and base_hours:
                                        if add_task_template(
                                            feature.id, name, task_type,
                                            base_hours, scales_dut, scales_profile,
                                            parallelizable, description,
                                        ):
                                            st.success("Template added!")
                                            st.cache_data.clear()
                                            st.rerun()
                                    else:
                                        st.error("Fill in required fields")

            with col2:
                if st.button("Delete Feature", key=f"delete_{selected_id}"):
                    if delete_feature(selected_id):
                        st.success("Feature deleted!")
                        st.cache_data.clear()
                        st.rerun()

            st.divider()
    else:
        st.info("No features found. Add one using the 'Add/Edit Feature' tab.")


# Tab 2: Add/Edit Feature
with tabs[1]:
    st.subheader("Add or Edit Feature")

    action = st.radio("Select action", ["Add New", "Edit Existing"])

    if action == "Add New":
        with st.form("add_feature_form"):
            st.write("**Create New Feature**")
            name = st.text_input("Feature Name *", placeholder="e.g., SIM Card Activation")
            category = st.text_input("Category", placeholder="e.g., SIM Management")
            complexity_weight = st.number_input(
                "Complexity Weight",
                min_value=0.5,
                max_value=5.0,
                value=1.0,
                step=0.1,
            )
            has_tests = st.checkbox("Has Existing Tests")
            description = st.text_area(
                "Description",
                placeholder="Describe this feature...",
            )

            if st.form_submit_button("Create Feature"):
                if name:
                    if add_feature(name, category, complexity_weight, has_tests, description):
                        st.success("Feature created!")
                        st.cache_data.clear()
                        st.rerun()
                else:
                    st.error("Feature name is required")

    else:
        features_data = get_features_data()
        if features_data:
            df = pd.DataFrame(features_data)
            selected_id = st.selectbox(
                "Select feature to edit",
                df["ID"].tolist(),
                format_func=lambda x: df[df["ID"] == x]["Name"].values[0],
            )

            if selected_id:
                feature = get_feature_by_id(selected_id)
                if feature:
                    with st.form("edit_feature_form"):
                        st.write(f"**Edit Feature: {feature.name}**")
                        name = st.text_input("Feature Name *", value=feature.name)
                        category = st.text_input(
                            "Category", value=feature.category or ""
                        )
                        complexity_weight = st.number_input(
                            "Complexity Weight",
                            min_value=0.5,
                            max_value=5.0,
                            value=feature.complexity_weight,
                            step=0.1,
                        )
                        has_tests = st.checkbox(
                            "Has Existing Tests",
                            value=feature.has_existing_tests,
                        )
                        description = st.text_area(
                            "Description",
                            value=feature.description or "",
                        )

                        if st.form_submit_button("Update Feature"):
                            if name:
                                if update_feature(
                                    feature.id, name, category, complexity_weight,
                                    has_tests, description,
                                ):
                                    st.success("Feature updated!")
                                    st.cache_data.clear()
                                    st.rerun()
                            else:
                                st.error("Feature name is required")
        else:
            st.info("No features found")
