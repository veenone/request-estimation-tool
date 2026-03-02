"""DUT (Device Under Test) Registry management page.

CRUD operations for DUT types and their configurations.
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
from src.database.models import Configuration, DutType

st.title("📱 DUT Registry")
st.markdown("Manage Device Under Test (DUT) types and configurations")

engine = get_engine()


def _get_dut_categories() -> list[str]:
    """Fetch DUT categories from the configuration table."""
    default = ["SIM", "eSIM", "UICC", "IoT Device", "Mobile Device", "Other"]
    try:
        with Session(engine) as session:
            cfg = session.query(Configuration).filter(
                Configuration.key == "dut_categories"
            ).first()
            if cfg and cfg.value:
                cats = [c.strip() for c in cfg.value.split(",") if c.strip()]
                return cats if cats else default
            return default
    except Exception:
        return default


DUT_CATEGORIES = _get_dut_categories()


@st.cache_data(ttl=60)
def get_duts_data():
    """Fetch all DUT types from the database."""
    with Session(engine) as session:
        duts = session.query(DutType).all()
        return [
            {
                "ID": d.id,
                "Name": d.name,
                "Category": d.category or "Other",
                "Complexity Multiplier": d.complexity_multiplier,
            }
            for d in duts
        ]


def get_dut_by_id(dut_id: int) -> DutType | None:
    """Fetch a single DUT type by ID."""
    with Session(engine) as session:
        return session.query(DutType).filter(DutType.id == dut_id).first()


def add_dut(name: str, category: str, complexity_multiplier: float) -> bool:
    """Add a new DUT type."""
    try:
        with Session(engine) as session:
            dut = DutType(
                name=name,
                category=category if category else None,
                complexity_multiplier=complexity_multiplier,
            )
            session.add(dut)
            session.commit()
            return True
    except Exception as e:
        st.error(f"Error adding DUT: {str(e)}")
        return False


def update_dut(dut_id: int, name: str, category: str,
               complexity_multiplier: float) -> bool:
    """Update an existing DUT type."""
    try:
        with Session(engine) as session:
            dut = session.query(DutType).filter(DutType.id == dut_id).first()
            if not dut:
                st.error("DUT not found")
                return False
            dut.name = name
            dut.category = category if category else None
            dut.complexity_multiplier = complexity_multiplier
            session.commit()
            return True
    except Exception as e:
        st.error(f"Error updating DUT: {str(e)}")
        return False


def delete_dut(dut_id: int) -> bool:
    """Delete a DUT type."""
    try:
        with Session(engine) as session:
            dut = session.query(DutType).filter(DutType.id == dut_id).first()
            if not dut:
                st.error("DUT not found")
                return False
            session.delete(dut)
            session.commit()
            return True
    except Exception as e:
        st.error(f"Error deleting DUT: {str(e)}")
        return False


# Main UI
col1, col2 = st.columns([2, 1])

with col2:
    if st.button("+ Add DUT", use_container_width=True):
        st.session_state["show_add_dut"] = True

# Display DUT table
st.subheader("DUT Types")

duts_data = get_duts_data()

if duts_data:
    df = pd.DataFrame(duts_data)

    # Sort by category
    df_sorted = df.sort_values("Category")

    # Display with category grouping
    st.dataframe(
        df_sorted,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ID": st.column_config.NumberColumn(width="small"),
            "Name": st.column_config.TextColumn(width="medium"),
            "Category": st.column_config.TextColumn(width="small"),
            "Complexity Multiplier": st.column_config.NumberColumn(
                width="small", format="%.1f"
            ),
        },
    )

    st.divider()

    # DUT management
    col1, col2 = st.columns(2)

    with col1:
        selected_id = st.selectbox(
            "Select DUT to manage",
            df["ID"].tolist(),
            format_func=lambda x: df[df["ID"] == x]["Name"].values[0],
        )

        if selected_id:
            dut = get_dut_by_id(selected_id)
            if dut:
                action = st.radio(
                    "Action",
                    ["View", "Edit", "Delete"],
                    horizontal=True,
                )

                if action == "View":
                    st.info(f"**Name:** {dut.name}")
                    st.info(f"**Category:** {dut.category or 'Other'}")
                    st.info(
                        f"**Complexity Multiplier:** {dut.complexity_multiplier}"
                    )

                elif action == "Edit":
                    with st.form(f"edit_dut_{dut.id}"):
                        st.write("**Edit DUT**")
                        name = st.text_input("Name *", value=dut.name)
                        category = st.selectbox(
                            "Category",
                            DUT_CATEGORIES,
                            index=DUT_CATEGORIES.index(dut.category or "Other")
                            if dut.category in DUT_CATEGORIES
                            else DUT_CATEGORIES.index("Other"),
                        )
                        complexity = st.number_input(
                            "Complexity Multiplier",
                            min_value=0.5,
                            max_value=5.0,
                            value=float(dut.complexity_multiplier),
                            step=0.1,
                        )

                        if st.form_submit_button("Update DUT"):
                            if name:
                                if update_dut(dut.id, name, category, complexity):
                                    st.success("DUT updated!")
                                    st.cache_data.clear()
                                    st.rerun()
                            else:
                                st.error("Name is required")

                elif action == "Delete":
                    st.warning(
                        f"Are you sure you want to delete **{dut.name}**? "
                        "This action cannot be undone."
                    )
                    if st.button(
                        "Delete DUT",
                        type="primary",
                        key=f"delete_{dut.id}",
                    ):
                        if delete_dut(dut.id):
                            st.success("DUT deleted!")
                            st.cache_data.clear()
                            st.rerun()

    with col2:
        st.metric("Total DUTs", len(df))
        st.metric("Categories", df["Category"].nunique())
        avg_complexity = df["Complexity Multiplier"].mean()
        st.metric("Avg Complexity", f"{avg_complexity:.1f}")

else:
    st.info("No DUTs found. Add one using the button above.")

st.divider()

# Add DUT form
if st.session_state.get("show_add_dut"):
    st.subheader("Add New DUT")

    with st.form("add_dut_form"):
        name = st.text_input(
            "DUT Name *",
            placeholder="e.g., iPhone 15 Pro, Samsung Galaxy S24",
        )
        category = st.selectbox("Category", DUT_CATEGORIES)
        complexity = st.number_input(
            "Complexity Multiplier",
            min_value=0.5,
            max_value=5.0,
            value=1.0,
            step=0.1,
            help="Relative complexity compared to baseline (1.0)",
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Add DUT"):
                if name:
                    if add_dut(name, category, complexity):
                        st.success("DUT added successfully!")
                        st.cache_data.clear()
                        st.session_state["show_add_dut"] = False
                        st.rerun()
                else:
                    st.error("DUT name is required")

        with col2:
            if st.form_submit_button("Cancel"):
                st.session_state["show_add_dut"] = False
                st.rerun()

# Statistics
st.divider()
st.subheader("DUT Statistics")

if duts_data:
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total DUTs", len(duts_data))

    with col2:
        categories = set(dut["Category"] for dut in duts_data)
        st.metric("Categories", len(categories))

    with col3:
        avg_complexity = sum(
            dut["Complexity Multiplier"] for dut in duts_data
        ) / len(duts_data)
        st.metric("Avg Complexity", f"{avg_complexity:.1f}")

    with col4:
        max_complexity = max(dut["Complexity Multiplier"] for dut in duts_data)
        st.metric("Max Complexity", f"{max_complexity:.1f}")
