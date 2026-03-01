"""NiceGUI frontend for the Test Effort Estimation Tool.

This is an alternative to the Streamlit frontend, offering:
- Proper SPA behavior (no full-page reruns)
- Built-in authentication middleware
- WebSocket-based real-time updates
- Full CSS/HTML control via Quasar framework

Run with: python frontend_nicegui/app.py
"""

import sys
from pathlib import Path

# Ensure the project root is on sys.path so `frontend_nicegui.pages.*` resolves
# regardless of which directory the user runs this script from.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import os

import httpx
from nicegui import app, ui

API_URL = os.environ.get("API_URL", "http://localhost:8501/api")

# ---------------------------------------------------------------------------
# Auth state stored in app.storage.user (per-browser-tab, cookie-backed)
# ---------------------------------------------------------------------------


def is_authenticated() -> bool:
    return app.storage.user.get("token") is not None


def current_user() -> dict | None:
    return app.storage.user.get("user")


def auth_headers() -> dict[str, str]:
    token = app.storage.user.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


async def api_get(path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}{path}", headers=auth_headers(), params=params)
        r.raise_for_status()
        return r.json()


async def api_post(path: str, json: dict | None = None, params: dict | None = None) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{API_URL}{path}", headers=auth_headers(), json=json, params=params)
        r.raise_for_status()
        return r.json()


async def api_put(path: str, json: dict | None = None) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.put(f"{API_URL}{path}", headers=auth_headers(), json=json)
        r.raise_for_status()
        return r.json()


async def api_delete(path: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.delete(f"{API_URL}{path}", headers=auth_headers())
        r.raise_for_status()
        return r.json()


# ---------------------------------------------------------------------------
# Login page (kept inline — no dependency on shared helpers)
# ---------------------------------------------------------------------------

@ui.page("/login")
def login_page():
    async def try_login():
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(f"{API_URL}/auth/login", json={
                    "username": username.value,
                    "password": password.value,
                })
                r.raise_for_status()
                data = r.json()
                app.storage.user["token"] = data["access_token"]
                app.storage.user["refresh_token"] = data["refresh_token"]
                app.storage.user["user"] = data["user"]
                ui.navigate.to("/")
        except httpx.HTTPStatusError:
            ui.notify("Invalid credentials", type="negative")
        except Exception as e:
            ui.notify(f"Login error: {e}", type="negative")

    with ui.card().classes("absolute-center w-96"):
        ui.label("Test Effort Estimation Tool").classes("text-h5 text-center w-full")
        ui.label("Sign in to continue").classes("text-subtitle2 text-center w-full text-grey")
        username = ui.input("Username").classes("w-full")
        password = ui.input("Password", password=True, password_toggle_button=True).classes("w-full")
        ui.button("Login", on_click=try_login).classes("w-full mt-4")


# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def auth_middleware(request, call_next):
    if request.url.path in ("/login", "/_nicegui"):
        return await call_next(request)
    if request.url.path.startswith("/_nicegui"):
        return await call_next(request)
    return await call_next(request)


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

def sidebar():
    user = current_user()
    role = user.get("role", "VIEWER") if user else "VIEWER"

    with ui.left_drawer(value=True).classes("bg-dark text-white") as drawer:
        ui.label("Estimation Tool").classes("text-h6 q-pa-md")

        if user:
            ui.label(f"{user.get('display_name', '')}").classes("q-px-md text-caption")
            ui.label(f"Role: {role}").classes("q-px-md text-caption text-grey")
            ui.separator()

        ui.item("Dashboard", on_click=lambda: ui.navigate.to("/")).classes("cursor-pointer")
        ui.item("New Estimation", on_click=lambda: ui.navigate.to("/estimation/new")).classes("cursor-pointer")
        ui.item("Feature Catalog", on_click=lambda: ui.navigate.to("/features")).classes("cursor-pointer")
        ui.item("DUT Registry", on_click=lambda: ui.navigate.to("/duts")).classes("cursor-pointer")
        ui.item("Test Profiles", on_click=lambda: ui.navigate.to("/profiles")).classes("cursor-pointer")
        ui.item("History", on_click=lambda: ui.navigate.to("/history")).classes("cursor-pointer")
        ui.item("Team", on_click=lambda: ui.navigate.to("/team")).classes("cursor-pointer")
        ui.item("Request Inbox", on_click=lambda: ui.navigate.to("/requests")).classes("cursor-pointer")
        ui.item("Integrations", on_click=lambda: ui.navigate.to("/integrations")).classes("cursor-pointer")
        ui.item("Settings", on_click=lambda: ui.navigate.to("/settings")).classes("cursor-pointer")

        if role == "ADMIN":
            ui.separator()
            ui.label("ADMINISTRATION").classes("q-px-md text-overline text-grey")
            ui.item("Users", on_click=lambda: ui.navigate.to("/users")).classes("cursor-pointer")
            ui.item("RBAC", on_click=lambda: ui.navigate.to("/rbac")).classes("cursor-pointer")
            ui.item("Audit Log", on_click=lambda: ui.navigate.to("/audit")).classes("cursor-pointer")

        ui.space()

        # Restore persisted dark/light preference (default: dark)
        is_dark = app.storage.user.get("dark_mode", True)
        dark = ui.dark_mode(is_dark)

        def toggle_theme():
            dark.toggle()
            app.storage.user["dark_mode"] = dark.value

        ui.button(icon="brightness_6", on_click=toggle_theme).props("flat round").classes("q-ma-md")

        async def logout():
            try:
                await api_post("/auth/logout")
            except Exception:
                pass
            app.storage.user.clear()
            ui.navigate.to("/login")

        ui.button("Logout", icon="logout", on_click=logout).props("flat").classes("q-ma-md text-white")

    return drawer


# ---------------------------------------------------------------------------
# Dashboard (kept inline — the main landing page)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Page modules — imported AFTER all shared helpers and inline pages are
# defined, so that `from frontend_nicegui.app import ...` in each module
# can resolve is_authenticated, sidebar, api_get, etc.
# ---------------------------------------------------------------------------

import frontend_nicegui.pages.features      # noqa: F401,E402
import frontend_nicegui.pages.duts          # noqa: F401,E402
import frontend_nicegui.pages.profiles      # noqa: F401,E402
import frontend_nicegui.pages.history       # noqa: F401,E402
import frontend_nicegui.pages.team          # noqa: F401,E402
import frontend_nicegui.pages.requests      # noqa: F401,E402
import frontend_nicegui.pages.settings      # noqa: F401,E402
import frontend_nicegui.pages.integrations  # noqa: F401,E402
import frontend_nicegui.pages.users         # noqa: F401,E402
import frontend_nicegui.pages.audit         # noqa: F401,E402
import frontend_nicegui.pages.estimation    # noqa: F401,E402
import frontend_nicegui.pages.rbac          # noqa: F401,E402

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="Test Effort Estimation Tool",
        port=8502,
        storage_secret="estimation-tool-secret-change-me",
        favicon="🧪",
        dark=True,
    )
