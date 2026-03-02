"""Estimation Detail page for Test Effort Estimation Tool.

Displays a saved estimation with full details, task breakdown, and management
options including status transitions and report generation.
"""

import json
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import desc
from sqlalchemy.orm import Session

# ── Backend path setup ─────────────────────────────────────────────────────
backend_path = str(Path(__file__).resolve().parent.parent.parent / "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from src.database.migrations import get_engine
from src.database.models import Estimation, EstimationTask, Request
from src.reports.excel_report import ExcelReportData, generate_excel_report
from src.reports.pdf_report import generate_pdf_report
from src.reports.word_report import generate_word_report

st.title("Estimation Detail")
st.markdown("View and manage your saved estimations")

# ── Database setup ─────────────────────────────────────────────────────────
engine = get_engine()


@st.cache_resource
def get_session():
    """Create a cached session factory."""
    return Session(engine)


@st.cache_data(ttl=60)
def load_estimation_list():
    """Load all estimations for the selectbox."""
    with Session(engine) as session:
        estimations = session.query(Estimation).order_by(
            desc(Estimation.created_at)
        ).all()
        return [
            {
                "id": e.id,
                "display": f"{e.estimation_number or f'EST-{e.id}'} - {e.project_name}",
                "estimation_number": e.estimation_number,
                "project_name": e.project_name,
            }
            for e in estimations
        ]


def load_estimation_detail(estimation_id: int):
    """Load full details of a single estimation."""
    with Session(engine) as session:
        estimation = session.query(Estimation).filter(
            Estimation.id == estimation_id
        ).first()
        if not estimation:
            return None

        # Build task data
        tasks = []
        for task in estimation.tasks:
            tasks.append({
                "id": task.id,
                "task_name": task.task_name,
                "task_type": task.task_type,
                "base_hours": task.base_hours,
                "calculated_hours": task.calculated_hours,
                "assigned_testers": task.assigned_testers,
                "has_leader_support": task.has_leader_support,
                "leader_hours": task.leader_hours,
                "is_new_feature_study": task.is_new_feature_study,
                "notes": task.notes or "",
            })

        # Build request data if linked
        request_data = None
        if estimation.request:
            request_data = {
                "id": estimation.request.id,
                "request_number": estimation.request.request_number,
                "title": estimation.request.title,
                "description": estimation.request.description or "",
                "requester_name": estimation.request.requester_name,
                "requester_email": estimation.request.requester_email or "",
                "business_unit": estimation.request.business_unit or "",
                "priority": estimation.request.priority,
                "status": estimation.request.status,
                "request_source": estimation.request.request_source,
                "external_id": estimation.request.external_id,
                "requested_delivery_date": estimation.request.requested_delivery_date,
                "received_date": estimation.request.received_date,
            }

        # Parse reference projects
        reference_ids = []
        try:
            reference_ids = json.loads(estimation.reference_project_ids)
        except (json.JSONDecodeError, TypeError):
            pass

        return {
            "id": estimation.id,
            "estimation_number": estimation.estimation_number,
            "project_name": estimation.project_name,
            "project_type": estimation.project_type,
            "dut_count": estimation.dut_count,
            "profile_count": estimation.profile_count,
            "dut_profile_combinations": estimation.dut_profile_combinations,
            "pr_fix_count": estimation.pr_fix_count,
            "expected_delivery": estimation.expected_delivery,
            "total_tester_hours": estimation.total_tester_hours,
            "total_leader_hours": estimation.total_leader_hours,
            "grand_total_hours": estimation.grand_total_hours,
            "grand_total_days": estimation.grand_total_days,
            "feasibility_status": estimation.feasibility_status,
            "status": estimation.status,
            "version": getattr(estimation, "version", 1) or 1,
            "created_at": estimation.created_at,
            "created_by": estimation.created_by or "Unknown",
            "approved_by": estimation.approved_by,
            "approved_at": estimation.approved_at,
            "request_id": estimation.request_id,
            "request": request_data,
            "tasks": tasks,
            "reference_project_ids": reference_ids,
            "assigned_to_id": estimation.assigned_to_id,
            "assigned_to_name": (
                estimation.assigned_to.display_name or estimation.assigned_to.username
            ) if estimation.assigned_to else None,
        }


def update_estimation_status(estimation_id: int, new_status: str):
    """Update the estimation status."""
    with Session(engine) as session:
        estimation = session.query(Estimation).filter(
            Estimation.id == estimation_id
        ).first()
        if estimation:
            estimation.status = new_status
            session.commit()


def update_estimation_approval(estimation_id: int, approved_by: str):
    """Mark estimation as approved."""
    with Session(engine) as session:
        estimation = session.query(Estimation).filter(
            Estimation.id == estimation_id
        ).first()
        if estimation:
            estimation.status = "APPROVED"
            estimation.approved_by = approved_by
            estimation.approved_at = datetime.utcnow()
            session.commit()


def build_excel_report_data(est: dict) -> ExcelReportData:
    """Convert estimation dict to ExcelReportData."""
    return ExcelReportData(
        project_name=est["project_name"],
        estimation_number=est["estimation_number"] or f"EST-{est['id']}",
        project_type=est["project_type"],
        created_by=est["created_by"],
        created_at=est["created_at"].strftime("%Y-%m-%d %H:%M") if est["created_at"] else "",
        request_number=est["request"]["request_number"] if est["request"] else None,
        requester_name=est["request"]["requester_name"] if est["request"] else None,
        business_unit=est["request"]["business_unit"] if est["request"] else None,
        priority=est["request"]["priority"] if est["request"] else None,
        dut_count=est["dut_count"],
        profile_count=est["profile_count"],
        dut_profile_combinations=est["dut_profile_combinations"],
        pr_fix_count=est["pr_fix_count"],
        expected_delivery=est["expected_delivery"].strftime("%Y-%m-%d") if est["expected_delivery"] else None,
        total_tester_hours=est["total_tester_hours"],
        total_leader_hours=est["total_leader_hours"],
        grand_total_hours=est["grand_total_hours"],
        grand_total_days=est["grand_total_days"],
        feasibility_status=est["feasibility_status"],
        tasks=[
            {
                "task_name": t["task_name"],
                "task_type": t["task_type"],
                "base_hours": t["base_hours"],
                "calculated_hours": t["calculated_hours"],
                "is_new_feature_study": t["is_new_feature_study"],
                "notes": t["notes"],
            }
            for t in est["tasks"]
        ],
    )


def get_feasibility_color(status: str) -> str:
    """Map feasibility status to color."""
    status_map = {
        "FEASIBLE": "#90EE90",     # Light green
        "AT_RISK": "#FFD700",      # Gold
        "NOT_FEASIBLE": "#FF6B6B", # Light red
    }
    return status_map.get(status, "#CCCCCC")


def get_status_color(status: str) -> str:
    """Map status to color."""
    status_map = {
        "DRAFT": "#E0E0E0",        # Gray
        "FINAL": "#87CEEB",        # Sky blue
        "APPROVED": "#90EE90",     # Light green
    }
    return status_map.get(status, "#CCCCCC")


# ── Main UI ────────────────────────────────────────────────────────────────

# Load estimations list
estimations = load_estimation_list()

if not estimations:
    st.warning("No estimations found. Create one from the New Estimation page.")
    st.stop()

# Selectbox to pick an estimation
selected_idx = st.selectbox(
    "Select an estimation to view:",
    range(len(estimations)),
    format_func=lambda i: estimations[i]["display"],
    key="estimation_selector",
)

selected_estimation_id = estimations[selected_idx]["id"]

# Load full estimation details
est = load_estimation_detail(selected_estimation_id)

if not est:
    st.error("Could not load estimation details.")
    st.stop()

# Clear cache when a different estimation is selected to ensure fresh data
if "last_selected_id" not in st.session_state:
    st.session_state.last_selected_id = selected_estimation_id
elif st.session_state.last_selected_id != selected_estimation_id:
    st.session_state.last_selected_id = selected_estimation_id
    st.cache_data.clear()

# ── Overview Section ──────────────────────────────────────────────────────

st.subheader("Overview")

version = est.get("version", 1) or 1
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    est_num = est["estimation_number"] or f"EST-{est['id']}"
    st.metric(
        "Estimation #",
        f"{est_num} (v{version})" if version > 1 else est_num,
    )

with col2:
    st.metric(
        "Project Name",
        est["project_name"],
    )

with col3:
    st.metric(
        "Project Type",
        est["project_type"],
    )

with col4:
    st.metric(
        "Status",
        est["status"],
    )

with col5:
    st.metric(
        "Version",
        version,
    )

# Project parameters row
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("DUT Count", est["dut_count"])

with col2:
    st.metric("Profile Count", est["profile_count"])

with col3:
    st.metric("Combinations", est["dut_profile_combinations"])

with col4:
    st.metric("PR Fixes", est["pr_fix_count"])

with col5:
    delivery_str = est["expected_delivery"].strftime("%Y-%m-%d") if est["expected_delivery"] else "TBD"
    st.metric("Expected Delivery", delivery_str)

# Effort breakdown and feasibility
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Total Tester Hours",
        f"{est['total_tester_hours']:.1f}h"
    )

with col2:
    st.metric(
        "Total Leader Hours",
        f"{est['total_leader_hours']:.1f}h"
    )

with col3:
    st.metric(
        "Grand Total",
        f"{est['grand_total_hours']:.1f}h ({est['grand_total_days']:.1f}d)"
    )

# Feasibility status with color
feas_color = get_feasibility_color(est["feasibility_status"])
st.markdown(
    f"<div style='padding: 10px; background-color: {feas_color}; "
    f"border-radius: 5px; text-align: center;'>"
    f"<b>Feasibility Status:</b> {est['feasibility_status']}"
    f"</div>",
    unsafe_allow_html=True
)

# Assignee info block
assigned_display = est.get("assigned_to_name") or "Unassigned"
st.info(f"**Assigned To:** {assigned_display}")

# ── Request Details (if linked) ────────────────────────────────────────────

if est["request"]:
    st.subheader("Linked Request")
    req = est["request"]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.write(f"**Request #:** {req['request_number']}")
        st.write(f"**Title:** {req['title']}")
        st.write(f"**Requester:** {req['requester_name']}")

    with col2:
        st.write(f"**Email:** {req['requester_email']}")
        st.write(f"**Business Unit:** {req['business_unit']}")
        st.write(f"**Priority:** {req['priority']}")

    with col3:
        st.write(f"**Status:** {req['status']}")
        received = req['received_date'].strftime("%Y-%m-%d") if req['received_date'] else "N/A"
        st.write(f"**Received:** {received}")
        if req['requested_delivery_date']:
            req_delivery = req['requested_delivery_date'].strftime("%Y-%m-%d")
            st.write(f"**Requested Delivery:** {req_delivery}")

    if st.button("View Request in Inbox", key="goto_request_inbox"):
        st.session_state["show_details"] = True
        st.session_state["selected_request_id"] = req["id"]
        st.switch_page("Request Inbox")

    if req["description"]:
        with st.expander("Request Description"):
            st.write(req["description"])

# ── Task Breakdown ─────────────────────────────────────────────────────────

st.subheader("Task Breakdown")

# Convert tasks to DataFrame for display
tasks_df = pd.DataFrame(est["tasks"])
if not tasks_df.empty:
    # Reorder and format columns
    display_df = tasks_df[[
        "task_name",
        "task_type",
        "base_hours",
        "calculated_hours",
        "assigned_testers",
        "has_leader_support",
        "leader_hours",
        "is_new_feature_study",
    ]].copy()

    display_df.columns = [
        "Task Name",
        "Type",
        "Base Hours",
        "Calculated Hours",
        "Assigned Testers",
        "Has Leader",
        "Leader Hours",
        "New Feature Study",
    ]

    # Format boolean column
    display_df["Has Leader"] = display_df["Has Leader"].apply(lambda x: "Yes" if x else "No")
    display_df["New Feature Study"] = display_df["New Feature Study"].apply(lambda x: "Yes" if x else "No")

    # Round numeric columns
    for col in ["Base Hours", "Calculated Hours", "Leader Hours"]:
        display_df[col] = display_df[col].round(2)

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Summary row
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Tasks", len(est["tasks"]))
    with col2:
        new_feature_count = sum(1 for t in est["tasks"] if t["is_new_feature_study"])
        st.metric("New Feature Studies", new_feature_count)
    with col3:
        leader_support_count = sum(1 for t in est["tasks"] if t["has_leader_support"])
        st.metric("Tasks with Leader Support", leader_support_count)

    # Task notes
    if any(t["notes"] for t in est["tasks"]):
        with st.expander("Task Notes"):
            for task in est["tasks"]:
                if task["notes"]:
                    st.write(f"**{task['task_name']}:** {task['notes']}")
else:
    st.info("No tasks found in this estimation.")

# ── Status Management ──────────────────────────────────────────────────────

st.subheader("Status Management")

col1, col2, col3 = st.columns(3)

status_color = get_status_color(est["status"])
st.markdown(
    f"<div style='padding: 10px; background-color: {status_color}; "
    f"border-radius: 5px; text-align: center;'>"
    f"<b>Current Status:</b> {est['status']}"
    f"</div>",
    unsafe_allow_html=True
)

# Status transition buttons
col1, col2, col3, col4 = st.columns(4)

with col1:
    if est["status"] == "DRAFT":
        if st.button("Mark as Final", use_container_width=True):
            update_estimation_status(est["id"], "FINAL")
            st.cache_data.clear()
            st.success("Estimation marked as FINAL")
            st.rerun()

with col2:
    if est["status"] in ["DRAFT", "FINAL"]:
        if st.button("Request Approval", use_container_width=True):
            st.session_state.show_approval_dialog = True

with col3:
    if est["status"] in ["DRAFT", "FINAL", "APPROVED"]:
        if st.button("Request Revision", type="secondary", use_container_width=True):
            update_estimation_status(est["id"], "REVISED")
            st.cache_data.clear()
            st.success("Estimation marked as REVISED — ready for editing")
            st.rerun()

with col4:
    if est["status"] == "APPROVED":
        st.write("Approved by: " + (est["approved_by"] or "N/A"))
        if est["approved_at"]:
            st.write(f"Approved at: {est['approved_at'].strftime('%Y-%m-%d %H:%M')}")

# Edit button for REVISED estimations
if est["status"] == "REVISED":
    st.info("This estimation is in REVISED status. You can edit and recalculate it.")
    if st.button("Edit Estimation", type="primary", use_container_width=True, icon=":material/edit:"):
        st.session_state["edit_estimation_id"] = est["id"]
        st.switch_page("pages/02_new_estimation.py")

# Approval dialog
if st.session_state.get("show_approval_dialog"):
    with st.form("approval_form"):
        approved_by = st.text_input(
            "Your name (for approval record):",
            value=st.session_state.get("current_user", ""),
        )
        submitted = st.form_submit_button("Approve Estimation", use_container_width=True)

        if submitted and approved_by:
            update_estimation_approval(est["id"], approved_by)
            st.session_state.show_approval_dialog = False
            st.cache_data.clear()
            st.success(f"Estimation approved by {approved_by}")
            st.rerun()

# ── Export to External System ──────────────────────────────────────────────

req_data = est.get("request")
if (
    req_data
    and req_data.get("external_id")
    and req_data.get("request_source") not in (None, "MANUAL")
    and est["status"] in ("FINAL", "APPROVED")
):
    source = req_data["request_source"]
    if st.button(
        f"Export to {source.title()}",
        use_container_width=True,
        help=f"Push estimation results back to {source.title()} issue #{req_data['external_id']}",
    ):
        with st.spinner(f"Exporting to {source.title()}..."):
            from src.integrations.service import sync_export

            with Session(engine) as session:
                estimation_data = {
                    "external_id": req_data["external_id"],
                    "grand_total_hours": est["grand_total_hours"],
                    "feasibility_status": est["feasibility_status"],
                    "estimation_number": est["estimation_number"] or f"EST-{est['id']}",
                }
                result = sync_export(source, estimation_data, session)

            if result.status.value == "SUCCESS":
                st.success(
                    f"Exported to {source.title()} issue #{req_data['external_id']}"
                )
            else:
                st.error(f"Export failed: {', '.join(result.errors)}")

# ── Report Generation ──────────────────────────────────────────────────────

st.subheader("Download Reports")

col1, col2, col3 = st.columns(3)

# Build report data
report_data = build_excel_report_data(est)

with col1:
    st.markdown("**Excel Report**")
    try:
        excel_bytes = generate_excel_report(report_data)
        st.download_button(
            label="Download Excel",
            data=excel_bytes,
            file_name=f"{est['estimation_number'] or f'EST-{est['id']}'}_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"Error generating Excel: {str(e)}")

with col2:
    st.markdown("**Word Report**")
    try:
        word_bytes = generate_word_report(report_data)
        st.download_button(
            label="Download Word",
            data=word_bytes,
            file_name=f"{est['estimation_number'] or f'EST-{est['id']}'}_report.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"Error generating Word: {str(e)}")

with col3:
    st.markdown("**PDF Report**")
    try:
        pdf_bytes = generate_pdf_report(report_data)
        st.download_button(
            label="Download PDF",
            data=pdf_bytes,
            file_name=f"{est['estimation_number'] or f'EST-{est['id']}'}_report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")

# ── Metadata ───────────────────────────────────────────────────────────────

st.divider()
st.subheader("Metadata")

col1, col2, col3 = st.columns(3)

with col1:
    created = est["created_at"].strftime("%Y-%m-%d %H:%M") if est["created_at"] else "N/A"
    st.write(f"**Created:** {created}")
    st.write(f"**Created By:** {est['created_by']}")

with col2:
    if est["approved_at"]:
        approved = est["approved_at"].strftime("%Y-%m-%d %H:%M")
        st.write(f"**Approved:** {approved}")
        st.write(f"**Approved By:** {est['approved_by']}")
    else:
        st.write("**Approved:** Not yet approved")
    assigned_meta = est.get("assigned_to_name") or "Unassigned"
    st.write(f"**Assigned To:** {assigned_meta}")

with col3:
    if est["reference_project_ids"]:
        st.write(f"**Reference Projects:** {len(est['reference_project_ids'])} linked")
    else:
        st.write("**Reference Projects:** None")
