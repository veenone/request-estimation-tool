"""Request Inbox page for Test Effort Estimation Tool.

Manage incoming test requests with creation, filtering, status workflow,
and detail viewing/editing capabilities.
"""

import json
import sys
from datetime import datetime, date
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

st.title("📥 Request Inbox")
st.markdown("Manage incoming test requests and track their estimation workflow")

engine = get_engine()

# Status and priority enums
STATUSES = ["NEW", "IN_ESTIMATION", "ESTIMATED", "IN_PROGRESS", "COMPLETED", "CANCELLED"]
PRIORITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
SOURCES = ["MANUAL", "REDMINE", "JIRA", "EMAIL"]


@st.cache_data(ttl=60)
def get_requests_data():
    """Fetch all requests from the database."""
    with Session(engine) as session:
        requests = session.query(Request).order_by(
            desc(Request.created_at)
        ).all()
        return [
            {
                "id": r.id,
                "request_number": r.request_number,
                "request_source": r.request_source,
                "external_id": r.external_id,
                "title": r.title,
                "description": r.description,
                "requester_name": r.requester_name,
                "requester_email": r.requester_email,
                "business_unit": r.business_unit,
                "priority": r.priority,
                "status": r.status,
                "requested_delivery_date": r.requested_delivery_date,
                "received_date": r.received_date,
                "attachments_json": r.attachments_json,
                "notes": r.notes,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
                "assigned_to_id": r.assigned_to_id,
                "assigned_to_name": (
                    r.assigned_to.display_name or r.assigned_to.username
                ) if r.assigned_to else None,
            }
            for r in requests
        ]


@st.cache_data(ttl=60)
def get_request_summary():
    """Get summary metrics for requests."""
    with Session(engine) as session:
        total_requests = session.query(func.count(Request.id)).scalar() or 0

        status_counts = {}
        for status in STATUSES:
            count = session.query(
                func.count(Request.id)
            ).filter(Request.status == status).scalar() or 0
            status_counts[status] = count

        return {
            "total": total_requests,
            "status_counts": status_counts,
        }


@st.cache_data(ttl=60)
def get_linked_estimations():
    """Get estimations linked to requests, keyed by request_id."""
    with Session(engine) as session:
        estimations = session.query(Estimation).filter(
            Estimation.request_id.isnot(None)
        ).order_by(desc(Estimation.created_at)).all()
        result = {}
        for e in estimations:
            entry = {
                "id": e.id,
                "estimation_number": e.estimation_number or f"EST-{e.id}",
                "status": e.status,
                "feasibility_status": e.feasibility_status,
                "grand_total_hours": round(e.grand_total_hours, 1),
            }
            result.setdefault(e.request_id, []).append(entry)
        return result



def get_status_color(status: str) -> str:
    """Return Streamlit color based on status."""
    colors = {
        "NEW": "blue",
        "IN_ESTIMATION": "orange",
        "ESTIMATED": "green",
        "IN_PROGRESS": "blue",
        "COMPLETED": "green",
        "CANCELLED": "gray",
    }
    return colors.get(status, "gray")


def get_priority_color(priority: str) -> str:
    """Return Streamlit color based on priority."""
    colors = {
        "LOW": "green",
        "MEDIUM": "orange",
        "HIGH": "orange",
        "CRITICAL": "red",
    }
    return colors.get(priority, "gray")


def format_request_for_display(req: dict, linked_estimations: dict | None = None) -> dict:
    """Format request data for table display."""
    est_nums = "—"
    if linked_estimations and req["id"] in linked_estimations:
        est_nums = ", ".join(
            e["estimation_number"] for e in linked_estimations[req["id"]]
        )
    return {
        "Request #": req["request_number"],
        "Title": req["title"],
        "Requester": req["requester_name"],
        "Business Unit": req["business_unit"] or "N/A",
        "Status": req["status"],
        "Priority": req["priority"],
        "Assigned To": req.get("assigned_to_name") or "—",
        "Estimation #": est_nums,
        "Source": req["request_source"],
        "Received": req["received_date"].strftime("%Y-%m-%d") if req["received_date"] else "",
    }


def save_request(request_data: dict) -> bool:
    """Save or update a request in the database."""
    try:
        with Session(engine) as session:
            if request_data.get("id"):
                # Update existing request
                request = session.query(Request).filter(
                    Request.id == request_data["id"]
                ).first()
                if not request:
                    st.error("Request not found")
                    return False

                request.title = request_data["title"]
                request.description = request_data.get("description")
                request.requester_name = request_data["requester_name"]
                request.requester_email = request_data.get("requester_email")
                request.business_unit = request_data.get("business_unit")
                request.priority = request_data["priority"]
                request.status = request_data["status"]
                request.requested_delivery_date = request_data.get("requested_delivery_date")
                request.notes = request_data.get("notes")
                request.updated_at = datetime.now()
            else:
                # Create new request
                request = Request(
                    request_number=request_data["request_number"],
                    request_source=request_data.get("request_source", "MANUAL"),
                    external_id=request_data.get("external_id"),
                    title=request_data["title"],
                    description=request_data.get("description"),
                    requester_name=request_data["requester_name"],
                    requester_email=request_data.get("requester_email"),
                    business_unit=request_data.get("business_unit"),
                    priority=request_data.get("priority", "MEDIUM"),
                    status=request_data.get("status", "NEW"),
                    requested_delivery_date=request_data.get("requested_delivery_date"),
                    received_date=request_data.get("received_date", date.today()),
                    notes=request_data.get("notes"),
                )
                session.add(request)

            session.commit()
            return True
    except Exception as e:
        st.error(f"Error saving request: {str(e)}")
        return False


def update_request_status(request_id: int, new_status: str) -> bool:
    """Update the status of a request."""
    try:
        with Session(engine) as session:
            request = session.query(Request).filter(
                Request.id == request_id
            ).first()
            if not request:
                st.error("Request not found")
                return False

            request.status = new_status
            request.updated_at = datetime.now()
            session.commit()
            return True
    except Exception as e:
        st.error(f"Error updating status: {str(e)}")
        return False


def delete_request(request_id: int) -> bool:
    """Delete a request from the database."""
    try:
        with Session(engine) as session:
            request = session.query(Request).filter(
                Request.id == request_id
            ).first()
            if not request:
                st.error("Request not found")
                return False

            session.delete(request)
            session.commit()
            return True
    except Exception as e:
        st.error(f"Error deleting request: {str(e)}")
        return False


def show_request_details(request_id: int):
    """Display and allow editing of request details."""
    with Session(engine) as session:
        request = session.query(Request).filter(
            Request.id == request_id
        ).first()

        if not request:
            st.error("Request not found")
            return

    st.markdown("---")
    st.subheader(f"Request Details: {request.request_number}")

    # Display request info in tabs
    tab1, tab2, tab3 = st.tabs(["Overview", "Details", "History"])

    with tab1:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown("**Status**")
            st.markdown(
                f"<span style='color: {get_status_color(request.status)}'>"
                f"{request.status}</span>",
                unsafe_allow_html=True,
            )

        with col2:
            st.markdown("**Priority**")
            st.markdown(
                f"<span style='color: {get_priority_color(request.priority)}'>"
                f"{request.priority}</span>",
                unsafe_allow_html=True,
            )

        with col3:
            st.markdown("**Source**")
            st.text(request.request_source)

        with col4:
            st.markdown("**Received**")
            st.text(
                request.received_date.strftime("%Y-%m-%d")
                if request.received_date else "N/A"
            )

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Requester Name**")
            st.text(request.requester_name)

        with col2:
            st.markdown("**Requester Email**")
            st.text(request.requester_email or "N/A")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**Business Unit**")
            st.text(request.business_unit or "N/A")

        with col2:
            st.markdown("**Requested Delivery Date**")
            st.text(
                request.requested_delivery_date.strftime("%Y-%m-%d")
                if request.requested_delivery_date else "Not specified"
            )

        with col3:
            st.markdown("**Assigned To**")
            assigned_name = None
            if request.assigned_to:
                assigned_name = request.assigned_to.display_name or request.assigned_to.username
            st.text(assigned_name or "—")

        st.markdown("---")
        st.markdown("**Title**")
        st.text(request.title)

        st.markdown("**Description**")
        st.text_area(
            "Description",
            value=request.description or "",
            disabled=True,
            height=150,
            label_visibility="collapsed",
        )

        # Linked Estimations section
        st.markdown("---")
        st.markdown("### Linked Estimations")

        linked_est = get_linked_estimations()
        req_estimations = linked_est.get(request.id, [])

        if req_estimations:
            for est in req_estimations:
                feas_icon = {"FEASIBLE": "🟢", "AT_RISK": "🟡", "NOT_FEASIBLE": "🔴"}.get(
                    est["feasibility_status"], "⚪"
                )
                st.markdown(
                    f"- **{est['estimation_number']}** — "
                    f"Status: {est['status']} | "
                    f"Total: {est['grand_total_hours']}h | "
                    f"Feasibility: {feas_icon} {est['feasibility_status']}"
                )
        else:
            st.info("No estimations linked to this request yet.")

        if request.status in ("NEW", "IN_ESTIMATION"):
            if st.button("Create Estimation for this Request", key="create_est_from_req"):
                st.session_state["s1_request_id"] = request.id
                st.switch_page("New Estimation")

    with tab2:
        st.markdown("### Edit Request Details")

        with st.form("edit_request_form"):
            st.text_input(
                "Request Number",
                value=request.request_number,
                disabled=True,
                help="Request number is set at creation and cannot be changed",
            )

            col1, col2 = st.columns(2)

            with col1:
                new_title = st.text_input("Title", value=request.title)
                new_requester_name = st.text_input(
                    "Requester Name", value=request.requester_name
                )
                new_priority = st.selectbox(
                    "Priority", PRIORITIES, index=PRIORITIES.index(request.priority)
                )

            with col2:
                new_status = st.selectbox(
                    "Status", STATUSES, index=STATUSES.index(request.status)
                )
                new_requester_email = st.text_input(
                    "Requester Email",
                    value=request.requester_email or "",
                )
                new_business_unit = st.text_input(
                    "Business Unit",
                    value=request.business_unit or "",
                )

            new_description = st.text_area(
                "Description",
                value=request.description or "",
                height=150,
            )

            new_notes = st.text_area(
                "Notes",
                value=request.notes or "",
                height=100,
            )

            new_requested_delivery_date = st.date_input(
                "Requested Delivery Date",
                value=request.requested_delivery_date if request.requested_delivery_date else date.today(),
            )

            if st.form_submit_button("Save Changes", type="primary"):
                update_data = {
                    "id": request.id,
                    "title": new_title,
                    "requester_name": new_requester_name,
                    "requester_email": new_requester_email,
                    "business_unit": new_business_unit,
                    "priority": new_priority,
                    "status": new_status,
                    "description": new_description,
                    "notes": new_notes,
                    "requested_delivery_date": new_requested_delivery_date,
                }

                if save_request(update_data):
                    st.cache_data.clear()
                    st.success("Request updated successfully!")
                    st.rerun()

    with tab3:
        st.markdown("### Request History")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown("**Created**")
            st.text(request.created_at.strftime("%Y-%m-%d %H:%M:%S"))

        with col2:
            st.markdown("**Last Updated**")
            st.text(request.updated_at.strftime("%Y-%m-%d %H:%M:%S"))

        with col3:
            st.markdown("**Request Number**")
            st.text(request.request_number)

        with col4:
            st.markdown("**External ID**")
            st.text(request.external_id or "N/A")

        if request.attachments_json and request.attachments_json != "[]":
            try:
                attachments = json.loads(request.attachments_json)
                if attachments:
                    st.markdown("**Attachments**")
                    for att in attachments:
                        st.text(att)
            except (json.JSONDecodeError, TypeError):
                pass


def show_create_request_form():
    """Display form to create a new request."""
    st.subheader("Create New Request")

    with st.form("create_request_form"):
        year_suffix = str(datetime.now().year)[-2:]
        request_number = st.text_input(
            "Request Number *",
            placeholder=f"e.g., REQ_{year_suffix}/0001",
            help="Externally defined request number in REQ_YY/XXXX format",
        )

        col1, col2 = st.columns(2)

        with col1:
            title = st.text_input(
                "Request Title *",
                placeholder="Enter request title...",
                help="Brief title of the test request",
            )

            requester_name = st.text_input(
                "Requester Name *",
                placeholder="Enter requester name...",
                help="Name of the person submitting the request",
            )

            priority = st.selectbox(
                "Priority",
                PRIORITIES,
                index=1,  # MEDIUM is default
                help="Priority level of the request",
            )

            request_source = st.selectbox(
                "Request Source",
                SOURCES,
                index=0,  # MANUAL is default
                help="Where the request originated",
            )

        with col2:
            requester_email = st.text_input(
                "Requester Email",
                placeholder="Enter email address...",
                help="Email of the requester for follow-up",
            )

            business_unit = st.text_input(
                "Business Unit",
                placeholder="Enter business unit...",
                help="Department or team requesting the tests",
            )

            external_id = st.text_input(
                "External ID (optional)",
                placeholder="e.g., JIRA-123 or Redmine ID",
                help="Reference ID from external system",
            )

        description = st.text_area(
            "Description",
            placeholder="Describe the test requirements in detail...",
            height=150,
            help="Detailed description of what needs to be tested",
        )

        col1, col2 = st.columns(2)

        with col1:
            received_date = st.date_input(
                "Received Date",
                value=date.today(),
                help="Date when the request was received",
            )

        with col2:
            requested_delivery_date = st.date_input(
                "Requested Delivery Date (optional)",
                value=None,
                help="When the testing should be completed",
            )

        notes = st.text_area(
            "Notes (optional)",
            placeholder="Add any additional notes...",
            height=100,
            help="Internal notes about the request",
        )

        submitted = st.form_submit_button("Create Request", type="primary")

        if submitted:
            if not title or not requester_name or not request_number:
                st.error("Request Number, Title, and Requester Name are required")
            else:
                request_data = {
                    "title": title,
                    "requester_name": requester_name,
                    "requester_email": requester_email,
                    "business_unit": business_unit,
                    "priority": priority,
                    "request_source": request_source,
                    "external_id": external_id if external_id else None,
                    "description": description,
                    "received_date": received_date,
                    "requested_delivery_date": requested_delivery_date,
                    "notes": notes,
                    "request_number": request_number,
                    "status": "NEW",
                }

                if save_request(request_data):
                    st.cache_data.clear()
                    st.success("Request created successfully!")
                    st.rerun()


def show_requests_table():
    """Display requests in a filtered table."""
    # Summary metrics
    summary = get_request_summary()

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total Requests", summary["total"])

    with col2:
        st.metric("New", summary["status_counts"].get("NEW", 0))

    with col3:
        st.metric("In Estimation", summary["status_counts"].get("IN_ESTIMATION", 0))

    with col4:
        st.metric("Estimated", summary["status_counts"].get("ESTIMATED", 0))

    with col5:
        st.metric("Completed", summary["status_counts"].get("COMPLETED", 0))

    st.markdown("---")

    # Filters
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        search_query = st.text_input(
            "Search",
            placeholder="Title, requester, or request number...",
            key="req_search",
        )

    with col2:
        status_filter = st.multiselect(
            "Filter by Status",
            STATUSES,
            key="req_status_filter",
        )

    with col3:
        priority_filter = st.multiselect(
            "Filter by Priority",
            PRIORITIES,
            key="req_priority_filter",
        )

    with col4:
        source_filter = st.multiselect(
            "Filter by Source",
            SOURCES,
            key="req_source_filter",
        )

    # Get data
    requests_data = get_requests_data()

    # Apply filters
    filtered_data = requests_data

    if search_query:
        search_lower = search_query.lower()
        filtered_data = [
            r for r in filtered_data
            if search_lower in r["title"].lower()
            or search_lower in r["requester_name"].lower()
            or search_lower in (r["request_number"] or "").lower()
        ]

    if status_filter:
        filtered_data = [
            r for r in filtered_data if r["status"] in status_filter
        ]

    if priority_filter:
        filtered_data = [
            r for r in filtered_data if r["priority"] in priority_filter
        ]

    if source_filter:
        filtered_data = [
            r for r in filtered_data if r["request_source"] in source_filter
        ]

    st.markdown(f"**Showing {len(filtered_data)} request(s)**")

    if filtered_data:
        # Format data for display
        linked_est = get_linked_estimations()
        display_data = [format_request_for_display(r, linked_est) for r in filtered_data]
        df = pd.DataFrame(display_data)

        # Display table
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Request #": st.column_config.TextColumn(width="small"),
                "Title": st.column_config.TextColumn(width="medium"),
                "Requester": st.column_config.TextColumn(width="small"),
                "Business Unit": st.column_config.TextColumn(width="small"),
                "Status": st.column_config.TextColumn(width="small"),
                "Priority": st.column_config.TextColumn(width="small"),
                "Assigned To": st.column_config.TextColumn(width="small"),
                "Estimation #": st.column_config.TextColumn(width="small"),
                "Source": st.column_config.TextColumn(width="small"),
                "Received": st.column_config.TextColumn(width="small"),
            },
        )

        st.markdown("---")
        st.markdown("### Request Actions")

        col1, col2, col3 = st.columns(3)

        with col1:
            selected_request = st.selectbox(
                "Select Request",
                [f"{r['request_number']} - {r['title']}" for r in filtered_data],
                key="select_request_action",
            )

            if selected_request:
                req_idx = [
                    f"{r['request_number']} - {r['title']}"
                    for r in filtered_data
                ].index(selected_request)
                selected_req = filtered_data[req_idx]

                col_a, col_b = st.columns(2)

                with col_a:
                    if st.button("View Details", key="view_details_btn"):
                        st.session_state.show_details = True
                        st.session_state.selected_request_id = selected_req["id"]

                with col_b:
                    if st.button("Delete", key="delete_btn"):
                        if delete_request(selected_req["id"]):
                            st.cache_data.clear()
                            st.success("Request deleted successfully!")
                            st.rerun()

        with col2:
            if st.button("Export to CSV", key="export_csv_btn"):
                csv = pd.DataFrame(display_data).to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"requests_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                )

        with col3:
            if st.button("Refresh Data", key="refresh_btn"):
                st.cache_data.clear()
                st.rerun()

        # Show details if selected
        if st.session_state.get("show_details") and st.session_state.get("selected_request_id"):
            show_request_details(st.session_state.selected_request_id)

    else:
        st.info("No requests found matching your filters.")


def show_status_workflow():
    """Display status workflow management."""
    st.subheader("Status Workflow")

    col1, col2 = st.columns(2)

    with col1:
        selected_request = st.selectbox(
            "Select Request for Status Update",
            [f"{r['request_number']} - {r['title']}" for r in get_requests_data()],
            key="select_request_workflow",
        )

    if selected_request:
        filtered_data = get_requests_data()
        req_idx = [
            f"{r['request_number']} - {r['title']}"
            for r in filtered_data
        ].index(selected_request)
        selected_req = filtered_data[req_idx]

        with col2:
            current_status = st.text_input(
                "Current Status",
                value=selected_req["status"],
                disabled=True,
            )

        st.markdown("---")
        st.markdown("### Status Transition Options")

        # Define allowed transitions
        transitions = {
            "NEW": ["IN_ESTIMATION", "CANCELLED"],
            "IN_ESTIMATION": ["ESTIMATED", "NEW", "CANCELLED"],
            "ESTIMATED": ["IN_PROGRESS", "IN_ESTIMATION", "CANCELLED"],
            "IN_PROGRESS": ["COMPLETED", "ESTIMATED", "CANCELLED"],
            "COMPLETED": ["CANCELLED"],
            "CANCELLED": ["NEW"],
        }

        allowed_next = transitions.get(selected_req["status"], [])

        if allowed_next:
            col1, col2, col3 = st.columns(3)

            for i, next_status in enumerate(allowed_next):
                with [col1, col2, col3][i % 3]:
                    if st.button(
                        f"Move to {next_status}",
                        key=f"status_{next_status}",
                        use_container_width=True,
                    ):
                        if update_request_status(selected_req["id"], next_status):
                            st.cache_data.clear()
                            st.success(f"Status updated to {next_status}!")
                            st.rerun()
        else:
            st.warning("No status transitions available for this request.")


# Initialize session state
if "show_details" not in st.session_state:
    st.session_state.show_details = False
if "selected_request_id" not in st.session_state:
    st.session_state.selected_request_id = None

# Main tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "Requests List",
    "Create Request",
    "Status Workflow",
    "Help",
])

with tab1:
    show_requests_table()

with tab2:
    show_create_request_form()

with tab3:
    show_status_workflow()

with tab4:
    st.markdown("""
    ### How to Use Request Inbox

    **Requests List Tab:**
    - View all incoming test requests
    - Filter by status, priority, source, or search text
    - See request metrics at the top
    - Select a request to view details or delete
    - Export requests to CSV for external processing

    **Create Request Tab:**
    - Create new test requests manually
    - Enter externally defined request numbers (REQ_YY/XXXX format)
    - Optionally link to external systems (JIRA, Redmine, Email)
    - Set priority and requested delivery date

    **Status Workflow Tab:**
    - Manage request progression through the estimation pipeline
    - Typical workflow: NEW -> IN_ESTIMATION -> ESTIMATED -> IN_PROGRESS -> COMPLETED
    - Can cancel requests at any stage
    - System prevents invalid status transitions

    **Request Statuses:**
    - **NEW** - Request just received, awaiting triage
    - **IN_ESTIMATION** - Currently being estimated
    - **ESTIMATED** - Estimation complete, waiting approval
    - **IN_PROGRESS** - Testing actively underway
    - **COMPLETED** - Testing finished
    - **CANCELLED** - Request cancelled or no longer needed

    **Request Priorities:**
    - **LOW** - Can be scheduled later
    - **MEDIUM** - Standard priority
    - **HIGH** - Should be expedited
    - **CRITICAL** - Must be done ASAP

    **Request Sources:**
    - **MANUAL** - Entered directly in the tool
    - **REDMINE** - From Redmine issue tracker
    - **JIRA** - From Atlassian JIRA
    - **EMAIL** - Submitted via email
    """)

# Footer
st.markdown("---")
st.markdown(
    f"""
    <div style='text-align: center; color: #888; font-size: 0.85em;'>
    Request data refreshes every 60 seconds. Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    </div>
    """,
    unsafe_allow_html=True,
)
