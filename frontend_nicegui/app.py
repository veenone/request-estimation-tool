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


def _safe_storage() -> dict:
    """Return app.storage.user or an empty dict if the storage is unavailable.

    NiceGUI raises AssertionError when the session cookie exists but the
    server-side storage was lost (e.g. after a server restart).  Returning
    an empty dict causes ``is_authenticated()`` to return False, which
    redirects the user to the login page where storage is re-initialized.
    """
    try:
        return app.storage.user
    except (AssertionError, RuntimeError):
        return {}


def is_authenticated() -> bool:
    return _safe_storage().get("token") is not None


def current_user() -> dict | None:
    return _safe_storage().get("user")


def auth_headers() -> dict[str, str]:
    token = _safe_storage().get("token")
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
async def login_page():
    # Check which providers are available
    providers = ["local"]
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{API_URL}/auth/providers")
            if r.status_code == 200:
                providers = r.json().get("providers", ["local"])
    except Exception:
        pass

    has_ldap = "ldap" in providers

    auth_method = {"value": "local"}

    async def try_login():
        try:
            payload = {
                "username": username.value,
                "password": password.value,
                "auth_method": auth_method["value"],
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(f"{API_URL}/auth/login", json=payload)
                if r.status_code == 401:
                    ui.notify("Invalid username or password", type="negative")
                    return
                if r.status_code == 502:
                    detail = r.json().get("detail", "LDAP server unreachable")
                    ui.notify(detail, type="negative")
                    return
                if r.status_code == 400:
                    detail = r.json().get("detail", "Bad request")
                    ui.notify(detail, type="negative")
                    return
                r.raise_for_status()
                data = r.json()
                app.storage.user["token"] = data["access_token"]
                app.storage.user["refresh_token"] = data["refresh_token"]
                app.storage.user["user"] = data["user"]
                ui.navigate.to("/")
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json().get("detail", "Authentication failed")
            except Exception:
                detail = "Authentication failed"
            ui.notify(detail, type="negative")
        except httpx.TimeoutException:
            ui.notify("Login timed out — server may be unreachable", type="negative")
        except Exception as e:
            ui.notify(f"Login error: {e}", type="negative")

    with ui.card().classes("absolute-center w-96"):
        ui.label("Test Effort Estimation Tool").classes("text-h5 text-center w-full")
        ui.label("Sign in to continue").classes("text-subtitle2 text-center w-full text-grey")

        if has_ldap:
            toggle = ui.toggle(
                {"local": "Internal", "ldap": "LDAP"},
                value="local",
                on_change=lambda e: auth_method.update({"value": e.value}),
            ).classes("w-full q-mb-sm")

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
            with ui.row().classes("q-px-md items-center w-full justify-between"):
                with ui.column().classes("gap-0"):
                    ui.label(f"{user.get('display_name', '')}").classes("text-caption")
                    ui.label(f"Role: {role}").classes("text-caption text-grey")
                # Notification bell
                badge_label = ui.label("").classes("hidden")  # hidden state holder
                with ui.button(icon="notifications", on_click=lambda: _open_notifications_dialog()).props("flat round dense color=white size=sm") as bell_btn:
                    bell_badge = ui.badge("0", color="red").props("floating").classes("hidden")

                async def _poll_unread() -> None:
                    try:
                        data = await api_get("/notifications/unread-count")
                        count = data.get("unread_count", 0)
                        bell_badge.set_text(str(count))
                        if count > 0:
                            bell_badge.classes(remove="hidden")
                        else:
                            bell_badge.classes(add="hidden")
                    except Exception:
                        pass

                async def _open_notifications_dialog() -> None:
                    try:
                        notifs = await api_get("/notifications")
                    except Exception:
                        notifs = []

                    with ui.dialog().props("maximized=false") as dlg, ui.card().classes("w-[500px] max-h-[80vh]"):
                        with ui.row().classes("w-full items-center justify-between q-mb-sm"):
                            ui.label("Notifications").classes("text-h6")

                            async def _mark_all_read():
                                try:
                                    await api_post("/notifications/mark-all-read")
                                    ui.notify("All notifications marked as read", type="positive")
                                except Exception as exc:
                                    ui.notify(f"Error: {exc}", type="negative")
                                dlg.close()
                                await _poll_unread()

                            ui.button("Mark all read", icon="done_all", on_click=_mark_all_read).props("flat dense color=primary")

                        if not notifs:
                            ui.label("No notifications.").classes("text-grey q-pa-md")
                        else:
                            with ui.scroll_area().classes("w-full").style("max-height: 60vh"):
                                for n in notifs:
                                    is_read = n.get("is_read", False)
                                    with ui.card().classes(f"w-full q-mb-sm {'bg-transparent' if is_read else ''}"):
                                        with ui.row().classes("items-center gap-2"):
                                            source = n.get("source", "REDMINE")
                                            source_colors = {"REDMINE": "red", "JIRA": "blue", "EMAIL": "orange"}
                                            ui.badge(source, color=source_colors.get(source, "grey")).props("dense")
                                            title_cls = "text-weight-bold" if not is_read else ""
                                            ui.label(n.get("title", "")).classes(title_cls)
                                        if n.get("message"):
                                            ui.label(n["message"]).classes("text-caption text-grey")
                                        with ui.row().classes("items-center gap-2 q-mt-xs"):
                                            ts = n.get("created_at", "")
                                            if ts:
                                                ui.label(str(ts)[:19]).classes("text-caption text-grey")
                                            req_id = n.get("request_id")
                                            if req_id:
                                                ui.button(
                                                    "View request",
                                                    icon="open_in_new",
                                                    on_click=lambda rid=req_id: (dlg.close(), ui.navigate.to(f"/requests/{rid}")),
                                                ).props("flat dense size=sm color=primary")
                                            if not is_read:
                                                nid = n["id"]

                                                async def _mark_one(nid=nid):
                                                    try:
                                                        await api_put(f"/notifications/{nid}/read")
                                                    except Exception:
                                                        pass
                                                    dlg.close()
                                                    await _poll_unread()

                                                ui.button(icon="check", on_click=_mark_one).props("flat dense round size=sm color=positive").tooltip("Mark read")
                    dlg.open()

                # Poll every 30 seconds + initial load
                ui.timer(30.0, _poll_unread)
                ui.timer(0.5, _poll_unread, once=True)

            ui.separator()

        # Notification banner (inside drawer, shown when unread > 0)
        _banner_row = ui.row().classes("w-full bg-warning text-dark q-pa-sm items-center hidden")
        with _banner_row:
            ui.icon("notifications_active", size="sm")
            _banner_label = ui.label("").classes("q-ml-sm text-caption")

        async def _update_banner() -> None:
            try:
                data = await api_get("/notifications/unread-count")
                count = data.get("unread_count", 0)
                if count > 0:
                    _banner_label.set_text(
                        f"You have {count} unread notification{'s' if count > 1 else ''}"
                    )
                    _banner_row.classes(remove="hidden")
                else:
                    _banner_row.classes(add="hidden")
            except Exception:
                pass

        ui.timer(30.0, _update_banner)
        ui.timer(1.0, _update_banner, once=True)

        # Load configuration list (cached in storage) for RBAC + theme
        _cfg_list: list[dict] | None = None
        try:
            _cfg_list = _safe_storage().get("_rbac_cache")
            if not _cfg_list:
                import httpx as _hx
                _r = _hx.get(f"{API_URL}/configuration", headers=auth_headers(), timeout=5)
                if _r.status_code == 200:
                    _cfg_list = _r.json()
                    _safe_storage()["_rbac_cache"] = _cfg_list
        except Exception:
            pass

        # Determine RBAC permissions for nav visibility
        _rbac_perms: set[str] = set()
        if role == "ADMIN":
            _rbac_perms = {"__all__"}
        else:
            try:
                _rbac_matrix_val = None
                if _cfg_list:
                    for _item in _cfg_list:
                        if _item.get("key") == "rbac_matrix":
                            _rbac_matrix_val = _item.get("value")
                            break
                if _rbac_matrix_val:
                    import json as _json_mod
                    _parsed = _json_mod.loads(_rbac_matrix_val)
                    _rbac_perms = set(_parsed.get(role, []))
            except Exception:
                _rbac_perms = set()

        def _has_perm(perm: str) -> bool:
            return "__all__" in _rbac_perms or perm in _rbac_perms

        with ui.list().props("dense"):

            # -- Overview --
            ui.item_label("OVERVIEW").props("header").classes("text-overline text-grey")
            _nav_item("Dashboard",     "dashboard", "/")
            if _has_perm("view_requests") or _has_perm("manage_requests"):
                _nav_item("Request Inbox", "inbox",     "/requests")

            ui.separator()

            # -- Estimation --
            ui.item_label("ESTIMATION").props("header").classes("text-overline text-grey")
            _nav_item("Estimations",    "list_alt",   "/estimations")
            _nav_item("New Estimation", "add_circle", "/estimation/new")

            ui.separator()

            # -- Data Management --
            ui.item_label("DATA MANAGEMENT").props("header").classes("text-overline text-grey")
            _nav_item("Feature Catalog",    "category",    "/features")
            _nav_item("Task Templates",    "assignment",  "/tasks")
            _nav_item("DUT Registry",       "devices",    "/duts")
            _nav_item("Test Profiles",      "tune",       "/profiles")
            _nav_item("Historical Projects", "history",   "/history")
            _nav_item("Team Members",       "group",      "/team")

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
        is_dark = _safe_storage().get("dark_mode", True)
        dark = ui.dark_mode(is_dark)

        # Task 14: Inject configurable table header background color
        _hdr_light = "#E0E0E0"
        _hdr_dark = "#424242"
        if _cfg_list:
            for _ci in _cfg_list:
                if _ci.get("key") == "table_header_bg_light":
                    _hdr_light = _ci.get("value") or _hdr_light
                elif _ci.get("key") == "table_header_bg_dark":
                    _hdr_dark = _ci.get("value") or _hdr_dark
        _active_hdr = _hdr_dark if is_dark else _hdr_light
        ui.add_css(f".q-table thead th {{ background-color: {_active_hdr} !important; }}")

        def toggle_theme():
            dark.toggle()
            _safe_storage()["dark_mode"] = dark.value

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
import frontend_nicegui.pages.tasks         # noqa: F401,E402
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
