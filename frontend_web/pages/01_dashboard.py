"""Dashboard page for Test Effort Estimation Tool.

Displays all estimations and requests with filtering, search, and summary metrics.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

# Add backend to path
backend_path = str(Path(__file__).resolve().parent.parent.parent / "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from src.database.migrations import get_engine
from src.database.models import Estimation, Request

st.title("📊 Dashboard")
st.markdown("View all estimations and requests at a glance")

engine = get_engine()


@st.cache_data(ttl=60)
def get_estimations_data():
    """Fetch all estimations from the database."""
    with Session(engine) as session:
        estimations = session.query(Estimation).order_by(
            desc(Estimation.created_at)
        ).all()
        results = []
        for e in estimations:
            # Eagerly resolve request while session is open
            req_num = "—"
            if e.request_id:
                req = session.get(Request, e.request_id)
                if req:
                    req_num = req.request_number
            version = getattr(e, "version", 1) or 1
            est_num = e.estimation_number or f"EST-{e.id}"
            results.append({
                "ID": e.id,
                "Estimation #": f"{est_num} (v{version})" if version > 1 else est_num,
                "Project Name": e.project_name,
                "Project Type": e.project_type,
                "Request #": req_num,
                "Total Hours": round(e.grand_total_hours, 1),
                "Total Days": round(e.grand_total_days, 1),
                "Feasibility": e.feasibility_status,
                "Status": e.status,
                "Version": version,
                "Created": e.created_at.strftime("%Y-%m-%d") if e.created_at else "",
                "Created By": e.created_by or "N/A",
            })
        return results


@st.cache_data(ttl=60)
def get_requests_data():
    """Fetch all requests from the database."""
    with Session(engine) as session:
        requests = session.query(Request).order_by(
            desc(Request.created_at)
        ).all()
        results = []
        for r in requests:
            # Find latest linked estimation
            latest_est = session.query(Estimation).filter(
                Estimation.request_id == r.id
            ).order_by(desc(Estimation.created_at)).first()
            est_num = latest_est.estimation_number or f"EST-{latest_est.id}" if latest_est else "—"
            results.append({
                "ID": r.id,
                "Request #": r.request_number,
                "Title": r.title,
                "Requester": r.requester_name,
                "Business Unit": r.business_unit or "N/A",
                "Status": r.status,
                "Priority": r.priority,
                "Estimation #": est_num,
                "Received": r.received_date.strftime("%Y-%m-%d") if r.received_date else "",
                "Created": r.created_at.strftime("%Y-%m-%d") if r.created_at else "",
            })
        return results


@st.cache_data(ttl=60)
def get_estimation_summary():
    """Get summary metrics for estimations."""
    with Session(engine) as session:
        total_estimations = session.query(func.count(Estimation.id)).scalar()
        avg_hours = session.query(func.avg(Estimation.grand_total_hours)).scalar()
        feasible_count = session.query(
            func.count(Estimation.id)
        ).filter(Estimation.feasibility_status == "FEASIBLE").scalar()
        risky_count = session.query(
            func.count(Estimation.id)
        ).filter(Estimation.feasibility_status == "RISKY").scalar()
        critical_count = session.query(
            func.count(Estimation.id)
        ).filter(Estimation.feasibility_status == "CRITICAL").scalar()

        return {
            "total": total_estimations or 0,
            "avg_hours": round(avg_hours, 1) if avg_hours else 0,
            "feasible": feasible_count or 0,
            "risky": risky_count or 0,
            "critical": critical_count or 0,
        }


@st.cache_data(ttl=60)
def get_request_summary():
    """Get summary metrics for requests."""
    with Session(engine) as session:
        total_requests = session.query(func.count(Request.id)).scalar()
        new_count = session.query(
            func.count(Request.id)
        ).filter(Request.status == "NEW").scalar()
        in_progress_count = session.query(
            func.count(Request.id)
        ).filter(Request.status == "IN_PROGRESS").scalar()
        completed_count = session.query(
            func.count(Request.id)
        ).filter(Request.status == "COMPLETED").scalar()

        return {
            "total": total_requests or 0,
            "new": new_count or 0,
            "in_progress": in_progress_count or 0,
            "completed": completed_count or 0,
        }


def get_feasibility_color(status: str) -> str:
    """Return color based on feasibility status."""
    colors = {
        "FEASIBLE": "🟢",
        "RISKY": "🟡",
        "CRITICAL": "🔴",
    }
    return colors.get(status, "⚪")


def get_status_badge(status: str) -> str:
    """Return badge emoji for request/estimation status."""
    badges = {
        "NEW": "🆕",
        "DRAFT": "📝",
        "IN_PROGRESS": "⏳",
        "COMPLETED": "✅",
        "APPROVED": "✔️",
        "REJECTED": "❌",
    }
    return badges.get(status, "•")


def create_estimations_tab():
    """Create the Estimations tab."""
    col1, col2, col3, col4, col5 = st.columns(5)

    summary = get_estimation_summary()

    with col1:
        st.metric("Total Estimations", summary["total"])

    with col2:
        st.metric("Avg Hours", summary["avg_hours"])

    with col3:
        st.metric("Feasible", summary["feasible"], delta="✓")

    with col4:
        st.metric("Risky", summary["risky"], delta="⚠", delta_color="off")

    with col5:
        st.metric("Critical", summary["critical"], delta="!", delta_color="inverse")

    st.markdown("---")

    # Filters and search
    col1, col2, col3 = st.columns(3)

    with col1:
        search_query = st.text_input(
            "🔍 Search project name",
            placeholder="Enter project name or number...",
            key="est_search",
        )

    with col2:
        status_filter = st.multiselect(
            "Filter by Status",
            ["DRAFT", "SUBMITTED", "APPROVED", "REJECTED"],
            key="est_status_filter",
        )

    with col3:
        feasibility_filter = st.multiselect(
            "Filter by Feasibility",
            ["FEASIBLE", "RISKY", "CRITICAL"],
            key="est_feasibility_filter",
        )

    # Get data
    estimations_data = get_estimations_data()

    # Apply filters
    filtered_data = estimations_data

    if search_query:
        filtered_data = [
            e for e in filtered_data
            if search_query.lower() in e["Project Name"].lower()
            or search_query.lower() in (e["Estimation #"] or "").lower()
        ]

    if status_filter:
        filtered_data = [
            e for e in filtered_data if e["Status"] in status_filter
        ]

    if feasibility_filter:
        filtered_data = [
            e for e in filtered_data if e["Feasibility"] in feasibility_filter
        ]

    # Display results count
    st.markdown(f"**Showing {len(filtered_data)} estimation(s)**")

    if filtered_data:
        # Create dataframe
        df = pd.DataFrame(filtered_data)

        # Add feasibility color column
        df_display = df.copy()
        df_display["Feasibility"] = df_display["Feasibility"].apply(
            lambda x: f"{get_feasibility_color(x)} {x}"
        )
        df_display["Status"] = df_display["Status"].apply(
            lambda x: f"{get_status_badge(x)} {x}"
        )

        # Remove ID column for display
        df_display = df_display.drop("ID", axis=1)

        # Display table
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Estimation #": st.column_config.TextColumn(width="small"),
                "Project Name": st.column_config.TextColumn(width="medium"),
                "Project Type": st.column_config.TextColumn(width="small"),
                "Request #": st.column_config.TextColumn(width="small"),
                "Total Hours": st.column_config.NumberColumn(width="small"),
                "Total Days": st.column_config.NumberColumn(width="small"),
                "Feasibility": st.column_config.TextColumn(width="small"),
                "Status": st.column_config.TextColumn(width="small"),
                "Created": st.column_config.TextColumn(width="small"),
                "Created By": st.column_config.TextColumn(width="small"),
            },
        )

        # Quick view options
        st.markdown("---")
        st.markdown("### Quick View")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📋 View Estimation Details", key="est_view_btn"):
                selected_id = st.selectbox(
                    "Select estimation",
                    [f"{e['Estimation #']} - {e['Project Name']}" for e in filtered_data],
                    key="est_detail_select",
                )
                est_idx = [
                    f"{e['Estimation #']} - {e['Project Name']}"
                    for e in filtered_data
                ].index(selected_id)
                est_id = filtered_data[est_idx]["ID"]
                st.success(f"Would navigate to estimation detail view for ID {est_id}")

        with col2:
            if st.button("📊 Export to CSV", key="est_export_btn"):
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"estimations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    key="est_download_csv",
                )

        with col3:
            if st.button("🔄 Refresh Data", key="est_refresh_btn"):
                st.cache_data.clear()
                st.rerun()
    else:
        st.info("No estimations found matching your criteria.")


def create_requests_tab():
    """Create the Requests tab."""
    col1, col2, col3, col4 = st.columns(4)

    summary = get_request_summary()

    with col1:
        st.metric("Total Requests", summary["total"])

    with col2:
        st.metric("New", summary["new"], delta="🆕")

    with col3:
        st.metric("In Progress", summary["in_progress"], delta="⏳")

    with col4:
        st.metric("Completed", summary["completed"], delta="✅")

    st.markdown("---")

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        search_query = st.text_input(
            "🔍 Search by title or requester",
            placeholder="Enter title or requester name...",
            key="req_search",
        )

    with col2:
        status_filter = st.multiselect(
            "Filter by Status",
            ["NEW", "IN_PROGRESS", "COMPLETED", "CANCELLED"],
            key="req_status_filter",
        )

    with col3:
        priority_filter = st.multiselect(
            "Filter by Priority",
            ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
            key="req_priority_filter",
        )

    # Get data
    requests_data = get_requests_data()

    # Apply filters
    filtered_data = requests_data

    if search_query:
        search_lower = search_query.lower()
        filtered_data = [
            r for r in filtered_data
            if search_lower in r["Title"].lower()
            or search_lower in r["Requester"].lower()
            or search_lower in (r["Request #"] or "").lower()
        ]

    if status_filter:
        filtered_data = [
            r for r in filtered_data if r["Status"] in status_filter
        ]

    if priority_filter:
        filtered_data = [
            r for r in filtered_data if r["Priority"] in priority_filter
        ]

    # Display results count
    st.markdown(f"**Showing {len(filtered_data)} request(s)**")

    if filtered_data:
        # Create dataframe
        df = pd.DataFrame(filtered_data)

        # Add status and priority badges
        df_display = df.copy()
        df_display["Status"] = df_display["Status"].apply(
            lambda x: f"{get_status_badge(x)} {x}"
        )

        # Create priority color mapping
        priority_emoji = {
            "LOW": "🟦",
            "MEDIUM": "🟨",
            "HIGH": "🟧",
            "CRITICAL": "🟥",
        }
        df_display["Priority"] = df_display["Priority"].apply(
            lambda x: f"{priority_emoji.get(x, '•')} {x}"
        )

        # Remove ID column for display
        df_display = df_display.drop("ID", axis=1)

        # Display table
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Request #": st.column_config.TextColumn(width="small"),
                "Title": st.column_config.TextColumn(width="medium"),
                "Requester": st.column_config.TextColumn(width="small"),
                "Business Unit": st.column_config.TextColumn(width="small"),
                "Status": st.column_config.TextColumn(width="small"),
                "Priority": st.column_config.TextColumn(width="small"),
                "Estimation #": st.column_config.TextColumn(width="small"),
                "Received": st.column_config.TextColumn(width="small"),
                "Created": st.column_config.TextColumn(width="small"),
            },
        )

        # Quick actions
        st.markdown("---")
        st.markdown("### Quick Actions")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📋 View Request Details", key="req_view_btn"):
                selected_id = st.selectbox(
                    "Select request",
                    [f"{r['Request #']} - {r['Title']}" for r in filtered_data],
                    key="req_detail_select",
                )
                req_idx = [
                    f"{r['Request #']} - {r['Title']}"
                    for r in filtered_data
                ].index(selected_id)
                req_id = filtered_data[req_idx]["ID"]
                st.success(f"Would navigate to request detail view for ID {req_id}")

        with col2:
            if st.button("📊 Export to CSV", key="req_export_btn"):
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"requests_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    key="req_download_csv",
                )

        with col3:
            if st.button("🔄 Refresh Data", key="req_refresh_btn"):
                st.cache_data.clear()
                st.rerun()
    else:
        st.info("No requests found matching your criteria.")


# Main content
tab1, tab2 = st.tabs(["📊 Estimations", "📋 Requests"])

with tab1:
    create_estimations_tab()

with tab2:
    create_requests_tab()

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #888; font-size: 0.85em;'>
    Dashboard data refreshes every 60 seconds. Last updated: """ +
    datetime.now().strftime("%Y-%m-%d %H:%M:%S") +
    """
    </div>
    """,
    unsafe_allow_html=True,
)
