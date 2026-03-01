"""Dashboard page for the NiceGUI frontend."""

from nicegui import ui

from frontend_nicegui.app import api_get, is_authenticated, sidebar


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

            with ui.row().classes("q-gutter-md"):
                for label, key in [
                    ("Total Estimations", "total_estimations"),
                    ("Draft", "estimations_draft"),
                    ("Final", "estimations_final"),
                    ("Approved", "estimations_approved"),
                ]:
                    with ui.card().classes("q-pa-md"):
                        ui.label(label).classes("text-subtitle2")
                        ui.label(str(stats.get(key, 0))).classes("text-h4")

            with ui.row().classes("q-gutter-md"):
                for label, key in [
                    ("Total Requests", "total_requests"),
                    ("New", "requests_new"),
                    ("In Progress", "requests_in_progress"),
                    ("Completed", "requests_completed"),
                ]:
                    with ui.card().classes("q-pa-md"):
                        ui.label(label).classes("text-subtitle2")
                        ui.label(str(stats.get(key, 0))).classes("text-h4")

            # Recent estimations
            ui.label("Recent Estimations").classes("text-h6 q-mt-lg")
            recent = stats.get("recent_estimations", [])
            if recent:
                columns = [
                    {"name": "id", "label": "ID", "field": "id"},
                    {"name": "project_name", "label": "Project", "field": "project_name"},
                    {"name": "grand_total_hours", "label": "Total Hours", "field": "grand_total_hours"},
                    {"name": "status", "label": "Status", "field": "status"},
                    {"name": "feasibility_status", "label": "Feasibility", "field": "feasibility_status"},
                ]
                ui.table(columns=columns, rows=recent).classes("w-full")
            else:
                ui.label("No estimations yet.").classes("text-grey")

            # Recent requests
            ui.label("Recent Requests").classes("text-h6 q-mt-lg")
            recent_req = stats.get("recent_requests", [])
            if recent_req:
                columns = [
                    {"name": "id", "label": "ID", "field": "id"},
                    {"name": "request_number", "label": "Number", "field": "request_number"},
                    {"name": "title", "label": "Title", "field": "title"},
                    {"name": "priority", "label": "Priority", "field": "priority"},
                    {"name": "status", "label": "Status", "field": "status"},
                ]
                ui.table(columns=columns, rows=recent_req).classes("w-full")
            else:
                ui.label("No requests yet.").classes("text-grey")

        except Exception as e:
            ui.label(f"Error loading dashboard: {e}").classes("text-negative")
