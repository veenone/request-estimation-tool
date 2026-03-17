"""Dashboard page for the NiceGUI frontend."""

from nicegui import ui

from frontend_nicegui.app import api_get, is_authenticated, show_error_page, sidebar


def _status_color(status: str) -> str:
    """Map a status to a Quasar color name for badges."""
    return {
        "DRAFT": "blue-grey",
        "FINAL": "blue",
        "APPROVED": "green",
        "NEW": "info",
        "IN_ESTIMATION": "warning",
        "IN_PROGRESS": "warning",
        "ESTIMATED": "teal",
        "COMPLETED": "positive",
        "REJECTED": "negative",
    }.get(status, "grey")


@ui.page("/")
async def dashboard_page():
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    with ui.column().classes("q-pa-lg w-full"):
        ui.label("Dashboard").classes("text-h4")

        try:
            stats = await api_get("/dashboard/stats")

            # ── Charts row ────────────────────────────────────
            with ui.row().classes("w-full q-gutter-md q-mb-lg"):
                # Estimation status donut
                with ui.card().classes("q-pa-md flex-1"):
                    total_est = stats.get("total_estimations", 0)
                    ui.label(f"Estimations — {total_est} total").classes("text-subtitle1 q-mb-sm")
                    est_data = [
                        {"value": stats.get("estimations_draft", 0), "name": "Draft", "itemStyle": {"color": "#78909C"}},
                        {"value": stats.get("estimations_final", 0), "name": "Final", "itemStyle": {"color": "#1976D2"}},
                        {"value": stats.get("estimations_approved", 0), "name": "Approved", "itemStyle": {"color": "#4CAF50"}},
                    ]
                    ui.echart({
                        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
                        "legend": {"orient": "horizontal", "bottom": 0},
                        "series": [{
                            "name": "Estimations",
                            "type": "pie",
                            "radius": ["45%", "75%"],
                            "center": ["50%", "45%"],
                            "avoidLabelOverlap": False,
                            "label": {"show": True, "formatter": "{b}\n{c}", "fontSize": 11},
                            "emphasis": {"label": {"show": True, "fontSize": 14, "fontWeight": "bold"}},
                            "data": est_data,
                        }],
                    }).classes("w-full").style("height: 280px")

                # Request status donut
                with ui.card().classes("q-pa-md flex-1"):
                    total_req = stats.get("total_requests", 0)
                    ui.label(f"Requests — {total_req} total").classes("text-subtitle1 q-mb-sm")
                    req_data = [
                        {"value": stats.get("requests_new", 0), "name": "New", "itemStyle": {"color": "#26A69A"}},
                        {"value": stats.get("requests_in_progress", 0), "name": "In Progress", "itemStyle": {"color": "#FFA726"}},
                        {"value": stats.get("requests_completed", 0), "name": "Completed", "itemStyle": {"color": "#66BB6A"}},
                    ]
                    # Add rejected count if available
                    rejected = total_req - sum(d["value"] for d in req_data)
                    if rejected > 0:
                        req_data.append({"value": rejected, "name": "Other", "itemStyle": {"color": "#BDBDBD"}})
                    ui.echart({
                        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
                        "legend": {"orient": "horizontal", "bottom": 0},
                        "series": [{
                            "name": "Requests",
                            "type": "pie",
                            "radius": ["45%", "75%"],
                            "center": ["50%", "45%"],
                            "avoidLabelOverlap": False,
                            "label": {"show": True, "formatter": "{b}\n{c}", "fontSize": 11},
                            "emphasis": {"label": {"show": True, "fontSize": 14, "fontWeight": "bold"}},
                            "data": req_data,
                        }],
                    }).classes("w-full").style("height: 280px")

            # ── Recent estimations ────────────────────────────
            ui.label("Recent Estimations").classes("text-h6 q-mt-md")
            recent = stats.get("recent_estimations", [])
            if recent:
                columns = [
                    {"name": "id", "label": "ID", "field": "id", "sortable": True, "align": "left"},
                    {"name": "estimation_number", "label": "Number", "field": "estimation_number", "sortable": True, "align": "left"},
                    {"name": "project_name", "label": "Project", "field": "project_name", "sortable": True, "align": "left"},
                    {"name": "grand_total_hours", "label": "Total Hours", "field": "grand_total_hours", "sortable": True, "align": "right"},
                    {"name": "status", "label": "Status", "field": "status", "sortable": True, "align": "left"},
                    {"name": "feasibility_status", "label": "Feasibility", "field": "feasibility_status", "sortable": True, "align": "left"},
                    {"name": "created_at", "label": "Created", "field": "created_at", "sortable": True, "align": "left"},
                ]
                est_tbl = ui.table(
                    columns=columns,
                    rows=recent,
                    row_key="id",
                    pagination={"rowsPerPage": 10, "sortBy": "id", "descending": True},
                ).classes("w-full")
                est_tbl.add_slot("body-cell-status", r"""
                    <q-td :props="props">
                        <q-badge outline :color="
                            props.value === 'DRAFT' ? 'blue-grey' :
                            props.value === 'FINAL' ? 'blue' :
                            props.value === 'APPROVED' ? 'green' : 'grey'
                        ">{{ props.value }}</q-badge>
                    </q-td>
                """)
                est_tbl.add_slot("body-cell-feasibility_status", r"""
                    <q-td :props="props">
                        <q-badge outline :color="
                            props.value === 'FEASIBLE' ? 'positive' :
                            props.value === 'AT_RISK' ? 'warning' : 'negative'
                        ">{{ props.value }}</q-badge>
                    </q-td>
                """)
            else:
                ui.label("No estimations yet.").classes("text-grey")

            # ── Recent requests ───────────────────────────────
            ui.label("Recent Requests").classes("text-h6 q-mt-lg")
            recent_req = stats.get("recent_requests", [])
            if recent_req:
                columns = [
                    {"name": "id", "label": "ID", "field": "id", "sortable": True, "align": "left"},
                    {"name": "request_number", "label": "Number", "field": "request_number", "sortable": True, "align": "left"},
                    {"name": "title", "label": "Title", "field": "title", "sortable": True, "align": "left"},
                    {"name": "priority", "label": "Priority", "field": "priority", "sortable": True, "align": "left"},
                    {"name": "status", "label": "Status", "field": "status", "sortable": True, "align": "left"},
                    {"name": "created_at", "label": "Created", "field": "created_at", "sortable": True, "align": "left"},
                ]
                req_tbl = ui.table(
                    columns=columns,
                    rows=recent_req,
                    row_key="id",
                    pagination={"rowsPerPage": 10, "sortBy": "id", "descending": True},
                ).classes("w-full")
                req_tbl.add_slot("body-cell-priority", r"""
                    <q-td :props="props">
                        <q-badge outline :color="
                            props.value === 'HIGH' || props.value === 'CRITICAL' ? 'negative' :
                            props.value === 'MEDIUM' ? 'warning' : 'positive'
                        ">{{ props.value }}</q-badge>
                    </q-td>
                """)
                req_tbl.add_slot("body-cell-status", r"""
                    <q-td :props="props">
                        <q-badge outline :color="
                            props.value === 'NEW' ? 'info' :
                            props.value === 'IN_ESTIMATION' ? 'warning' :
                            props.value === 'COMPLETED' ? 'positive' : 'grey'
                        ">{{ props.value }}</q-badge>
                    </q-td>
                """)
            else:
                ui.label("No requests yet.").classes("text-grey")

        except Exception as e:
            show_error_page(e)
