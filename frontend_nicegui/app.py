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
# Friendly error pages
# ---------------------------------------------------------------------------

_ERROR_PAGES: dict[int, dict[str, str]] = {
    401: {
        "icon": "lock",
        "title": "Session Expired",
        "message": "Your session has expired or you are not logged in.",
        "action_label": "Go to Login",
        "action_url": "/login",
        "color": "warning",
    },
    403: {
        "icon": "block",
        "title": "Access Denied",
        "message": "You don't have permission to view this page. Contact your administrator if you believe this is an error.",
        "action_label": "Back to Dashboard",
        "action_url": "/",
        "color": "negative",
    },
    404: {
        "icon": "search_off",
        "title": "Not Found",
        "message": "The resource you're looking for doesn't exist or has been moved.",
        "action_label": "Back to Dashboard",
        "action_url": "/",
        "color": "info",
    },
    500: {
        "icon": "error_outline",
        "title": "Server Error",
        "message": "Something went wrong on the server. Please try again later or contact support.",
        "action_label": "Retry",
        "action_url": None,
        "color": "negative",
    },
    502: {
        "icon": "cloud_off",
        "title": "Backend Unavailable",
        "message": "The backend server is not responding. Make sure it is running on the configured address.",
        "action_label": "Retry",
        "action_url": None,
        "color": "negative",
    },
    520: {
        "icon": "warning_amber",
        "title": "Unknown Error",
        "message": "An unexpected error occurred. Please try again.",
        "action_label": "Back to Dashboard",
        "action_url": "/",
        "color": "warning",
    },
}


class ApiError(Exception):
    """Raised by api_* helpers with a parsed HTTP status code."""

    def __init__(self, status_code: int, detail: str = "") -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


def show_error_page(exc: Exception) -> None:
    """Render a full-page friendly error card.

    Call this inside a ``ui.column`` or similar container when a page-level
    API call fails.  It replaces the raw traceback with a user-friendly
    message, icon, and action button.
    """
    # Determine status code from the exception
    status = 520  # default "unknown"
    detail = ""
    if isinstance(exc, ApiError):
        status = exc.status_code
        detail = exc.detail
    elif isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        detail = str(exc)
    elif isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        status = 502
        detail = "Could not reach the backend server."
    elif isinstance(exc, httpx.TimeoutException):
        status = 504
        detail = "The request timed out."

    cfg = _ERROR_PAGES.get(status, _ERROR_PAGES[520])

    with ui.card().classes("absolute-center w-[460px] q-pa-xl text-center"):
        ui.icon(cfg["icon"], size="80px", color=cfg["color"]).classes("q-mb-md")
        ui.label(f"{status}").classes(f"text-h2 text-{cfg['color']} q-mb-none")
        ui.label(cfg["title"]).classes("text-h5 q-mb-sm")
        ui.label(cfg["message"]).classes("text-body1 text-grey q-mb-md")
        if detail:
            with ui.expansion("Technical Details", icon="code").classes("w-full q-mb-md"):
                ui.label(detail).classes("text-caption text-grey-6 break-all")

        action_url = cfg["action_url"]
        if status == 401:
            # Clear stale auth state and redirect
            def go_login():
                app.storage.user.clear()
                ui.navigate.to("/login")

            ui.button(cfg["action_label"], icon="login", on_click=go_login).props(
                f"color={cfg['color']} unelevated"
            ).classes("q-mt-sm")
        elif action_url:
            ui.button(
                cfg["action_label"],
                icon="arrow_back",
                on_click=lambda url=action_url: ui.navigate.to(url),
            ).props(f"color={cfg['color']} unelevated").classes("q-mt-sm")
        else:
            # Retry = reload current page
            ui.button(
                cfg["action_label"],
                icon="refresh",
                on_click=lambda: ui.navigate.to(ui.context.client.page.path),
            ).props(f"color={cfg['color']} unelevated").classes("q-mt-sm")


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
        username.on("keydown.enter", lambda: password.run_method("focus"))
        password = ui.input("Password", password=True, password_toggle_button=True).classes("w-full")
        password.on("keydown.enter", try_login)
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

def _nav_item(label: str, icon_name: str, path: str) -> None:
    """Render a sidebar navigation item with a Material icon."""
    with ui.item(on_click=lambda p=path: ui.navigate.to(p)).classes("cursor-pointer"):
        with ui.item_section().props("avatar"):
            ui.icon(icon_name, color="white", size="24px")
        with ui.item_section():
            ui.item_label(label)


def sidebar():
    user = current_user()
    role = user.get("role", "VIEWER") if user else "VIEWER"

    with ui.left_drawer(value=True).classes("bg-dark text-white") as drawer:
        ui.label("Estimation Tool").classes("text-h6 q-pa-md")

        if user:
            ui.label(f"{user.get('display_name', '')}").classes("q-px-md text-caption")
            ui.label(f"Role: {role}").classes("q-px-md text-caption text-grey")
            ui.separator()

        with ui.list().props("dense"):

            # -- Overview --
            ui.item_label("OVERVIEW").props("header").classes("text-overline text-grey")
            _nav_item("Dashboard",     "dashboard", "/")
            _nav_item("Request Inbox", "inbox",     "/requests")

            ui.separator()

            # -- Estimation --
            ui.item_label("ESTIMATION").props("header").classes("text-overline text-grey")
            _nav_item("Estimations",    "list_alt",   "/estimations")
            _nav_item("New Estimation", "add_circle", "/estimation/new")

            ui.separator()

            # -- Data Management --
            ui.item_label("DATA MANAGEMENT").props("header").classes("text-overline text-grey")
            _nav_item("Feature Catalog",    "category", "/features")
            _nav_item("DUT Registry",       "devices",  "/duts")
            _nav_item("Test Profiles",      "tune",     "/profiles")
            _nav_item("Historical Projects", "history", "/history")
            _nav_item("Team Members",       "group",    "/team")

            ui.separator()

            # -- Administration --
            ui.item_label("ADMINISTRATION").props("header").classes("text-overline text-grey")
            _nav_item("Settings",     "settings",            "/settings")
            _nav_item("Integrations", "sync",                "/integrations")

            if role == "ADMIN":
                _nav_item("Users",     "manage_accounts",      "/users")
                _nav_item("RBAC",      "admin_panel_settings", "/rbac")
                _nav_item("Audit Log", "receipt_long",         "/audit")

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
            show_error_page(e)


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
    import ssl as _ssl

    _ssl_certfile = os.environ.get("SSL_CERTFILE", "") or None
    _ssl_keyfile = os.environ.get("SSL_KEYFILE", "") or None

    _ssl_kwargs: dict = {}
    if _ssl_certfile and _ssl_keyfile:
        ssl_ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(_ssl_certfile, _ssl_keyfile)
        _ssl_kwargs["ssl_certfile"] = _ssl_certfile
        _ssl_kwargs["ssl_keyfile"] = _ssl_keyfile
        scheme = "https"
    else:
        scheme = "http"

    _port = int(os.environ.get("NICEGUI_PORT", "8502"))
    print(f"Starting NiceGUI on {scheme}://0.0.0.0:{_port}")

    ui.run(
        title="Test Effort Estimation Tool",
        port=_port,
        storage_secret="estimation-tool-secret-change-me",
        favicon="🧪",
        dark=True,
        **_ssl_kwargs,
    )
