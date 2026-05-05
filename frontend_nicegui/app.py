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
# Serve uploaded files (logo, etc.) directly from NiceGUI so the browser can
# load them without going through the API/nginx proxy.
# ---------------------------------------------------------------------------
_UPLOADS_DIR = Path("/app/data/uploads")
if not _UPLOADS_DIR.parent.exists():
    # Local dev fallback
    _UPLOADS_DIR = Path(_PROJECT_ROOT) / "backend" / "data" / "uploads"
_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.add_static_files("/uploads", str(_UPLOADS_DIR))


# ---------------------------------------------------------------------------
# Shared design system — loaded into every page's <head>
# Pages add component-specific CSS on top of these tokens.
# ---------------------------------------------------------------------------

ui.add_head_html("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {
    --ed-line:      color-mix(in srgb, currentColor 18%, transparent);
    --ed-line-soft: color-mix(in srgb, currentColor 11%, transparent);
    --ed-bg-soft:   color-mix(in srgb, currentColor 4%, transparent);
    --ed-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
    --ed-sans: inherit;
  }

  /* Layout shell */
  .ed-shell { width: 100%; max-width: 1340px; margin: 0 auto; }

  /* Mono helper */
  .ed-mono       { font-family: var(--ed-mono) !important; font-variant-numeric: tabular-nums; }

  /* Type tokens */
  .ed-eyebrow    { font-family: var(--ed-sans) !important;
                   text-transform: uppercase !important; letter-spacing: 0.16em !important;
                   font-size: 10px !important; font-weight: 600 !important; opacity: 0.62 !important;
                   line-height: 1.1 !important; }
  .ed-cap        { font-family: var(--ed-sans) !important;
                   text-transform: uppercase !important; letter-spacing: 0.18em !important;
                   font-size: 11px !important; font-weight: 700 !important; opacity: 0.6 !important;
                   line-height: 1.1 !important; }

  /* Sticky toolbar */
  .ed-toolbar    { display: flex !important; align-items: center; gap: 6px; flex-wrap: wrap;
                   padding: 12px 24px; backdrop-filter: blur(14px);
                   background: var(--ed-bg-soft);
                   border-bottom: 1px solid var(--ed-line);
                   position: sticky; top: 0; z-index: 60;
                   margin: -16px -16px 28px -16px; }
  .ed-toolbar .q-btn { font-family: var(--ed-sans); text-transform: uppercase;
                       letter-spacing: 0.10em; font-size: 11px; font-weight: 600; }
  .ed-toolbar-spacer { width: 1px; height: 22px; background: var(--ed-line); margin: 0 8px; }
  .ed-toolbar-grow   { flex: 1; min-width: 16px; }

  /* Status pill (toolbar right) */
  .ed-status-now { display: inline-flex; align-items: center; gap: 10px;
                   padding: 7px 14px; border: 1px solid var(--ed-line);
                   border-radius: 99px; font-family: var(--ed-mono);
                   font-size: 11px; letter-spacing: 0.04em; }
  .ed-status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--q-info); }
  .ed-status-FEASIBLE .ed-status-dot, .ed-status-APPROVED .ed-status-dot { background: var(--q-positive); }
  .ed-status-AT_RISK  .ed-status-dot, .ed-status-REVISED  .ed-status-dot { background: var(--q-warning); }
  .ed-status-NOT_FEASIBLE .ed-status-dot { background: var(--q-negative); }
  .ed-status-FINAL .ed-status-dot { background: var(--q-primary); }

  /* Card */
  .ed-card       { display: block !important;
                   width: 100% !important; box-sizing: border-box;
                   border: 1px solid var(--ed-line) !important;
                   border-radius: 4px; padding: 24px 26px;
                   box-shadow: none !important; background: transparent !important;
                   margin-bottom: 22px; }
  .ed-card-head  { display: flex !important; align-items: baseline;
                   justify-content: space-between; margin-bottom: 18px;
                   gap: 16px; flex-wrap: wrap; }
  .ed-card-head-meta { font-family: var(--ed-mono); font-size: 12px; opacity: 0.7; }

  /* KPI strip (used in detail page; reused in inbox) */
  .ed-strip      { display: grid !important;
                   grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
                   border: 1px solid var(--ed-line); border-radius: 4px;
                   overflow: hidden; }
  .ed-strip-cell { padding: 18px 22px;
                   border-right: 1px dashed var(--ed-line-soft); }
  .ed-strip-cell:last-child { border-right: none; }
  .ed-strip-num  { font-family: var(--ed-mono);
                   font-variant-numeric: tabular-nums;
                   font-size: 22px; font-weight: 500;
                   letter-spacing: -0.01em; margin-top: 8px; }

  /* Section header */
  .ed-section-head { display: flex !important; align-items: baseline;
                     justify-content: space-between; margin: 28px 0 14px 0;
                     flex-wrap: wrap; gap: 8px; }

  /* Empty state */
  .ed-empty      { width: 100%; box-sizing: border-box;
                   padding: 28px; text-align: center;
                   border: 1px dashed var(--ed-line); border-radius: 4px;
                   opacity: 0.55;
                   font-family: var(--ed-sans);
                   text-transform: uppercase; letter-spacing: 0.14em;
                   font-size: 11px; font-weight: 600; }

  /* Reusable filter components (used by data-mgmt list pages + inbox) */
  .ed-stat-tile     { cursor: pointer; transition: background 160ms ease; }
  .ed-stat-tile:hover { background: var(--ed-bg-soft); }
  .ed-stat-tile.active { background: color-mix(in srgb, var(--q-primary) 10%, transparent); }
  .ed-stat-tile.active .ed-strip-num { color: var(--q-primary); }
  .ed-stat-tile-sub { font-family: inherit; font-size: 11px;
                      opacity: 0.6; margin-top: 4px; }

  .ed-segmented     { display: inline-flex !important; align-items: center;
                      gap: 4px; padding: 4px;
                      border: 1px solid var(--ed-line);
                      border-radius: 99px;
                      margin: 18px 0 14px 0;
                      flex-wrap: wrap; }
  .ed-segmented-item{ padding: 6px 14px; border-radius: 99px;
                      font-family: inherit; font-size: 12px; font-weight: 500;
                      cursor: pointer; transition: all 140ms ease;
                      display: inline-flex !important; align-items: center; gap: 6px;
                      border: none; background: transparent; color: inherit;
                      line-height: 1.2; }
  .ed-segmented-item .seg-count { font-family: var(--ed-mono);
                                  font-variant-numeric: tabular-nums;
                                  font-size: 11px; opacity: 0.55; }
  .ed-segmented-item:hover  { background: var(--ed-bg-soft); }
  .ed-segmented-item.active { background: var(--q-primary); color: white; }
  .ed-segmented-item.active .seg-count { opacity: 0.85; color: white; }

  .ed-filter-row    { display: flex !important; gap: 12px; align-items: center;
                      flex-wrap: wrap; margin-bottom: 14px;
                      padding: 12px 16px; border: 1px solid var(--ed-line);
                      border-radius: 4px; background: var(--ed-bg-soft); }
  .ed-filter-label  { font-family: inherit; text-transform: uppercase;
                      letter-spacing: 0.12em; font-size: 10px;
                      font-weight: 600; opacity: 0.6;
                      margin-right: 8px; }

  /* Reusable tabs + panels (used on detail page, integrations, etc.) */
  .ed-tabs       { margin: 0 0 24px 0;
                   border-bottom: 1px solid var(--ed-line); }
  .ed-tabs .q-tab{ font-family: var(--ed-sans);
                   text-transform: uppercase; letter-spacing: 0.16em;
                   font-size: 11px; font-weight: 600;
                   padding: 0 22px; min-height: 48px; }
  .ed-tabs .q-tab__indicator { height: 2px; }
  .ed-panels     { background: transparent !important;
                   overflow: hidden !important;
                   border-radius: 4px; }
  .ed-panels .q-panel { overflow: hidden !important; }
  .ed-panels .q-tab-panel { padding: 6px 2px 6px 0 !important;
                            box-sizing: border-box; }

  /* ─── Sidebar redesign ──────────────────────────────────────────── */

  /* Logo zone — top of drawer */
  .ed-side-logo  { padding: 16px 20px 14px 20px;
                   border-bottom: 1px solid color-mix(in srgb, currentColor 10%, transparent);
                   display: flex !important; align-items: center; gap: 12px; }
  .ed-side-logo-img { flex: 0 0 auto;
                      width: 36px !important; height: 36px !important;
                      min-width: 36px !important; min-height: 36px !important; }
  .ed-side-logo-img > img,
  .ed-side-logo-img .q-img__image,
  .ed-side-logo-img .q-img__container > div {
                      object-fit: contain !important;
                      object-position: center !important;
                      background-size: contain !important;
                      background-position: center !important; }
  .ed-side-logo-text { font-family: inherit; font-weight: 700;
                       font-size: 16px; letter-spacing: -0.005em;
                       margin: 0; }

  /* User card */
  .ed-side-user  { display: flex !important; align-items: center; gap: 12px;
                   padding: 14px 20px;
                   border-bottom: 1px solid color-mix(in srgb, currentColor 10%, transparent); }
  .ed-side-avatar{ width: 36px; height: 36px; min-width: 36px;
                   border-radius: 50%;
                   background: color-mix(in srgb, var(--q-primary) 80%, transparent);
                   color: white;
                   display: flex !important; align-items: center; justify-content: center;
                   font-family: var(--ed-mono); font-size: 13px; font-weight: 600;
                   text-transform: uppercase; }
  .ed-side-user-meta { flex: 1; min-width: 0; line-height: 1.2; }
  .ed-side-user-name { font-size: 13px; font-weight: 600;
                       white-space: nowrap; overflow: hidden;
                       text-overflow: ellipsis; }
  .ed-side-user-role { font-family: var(--ed-mono);
                       font-size: 10px; opacity: 0.6;
                       letter-spacing: 0.08em; margin-top: 2px; }
  .ed-side-bell  { width: 32px; height: 32px; border-radius: 50%;
                   display: flex !important; align-items: center; justify-content: center;
                   cursor: pointer; position: relative;
                   transition: background 140ms ease; }
  .ed-side-bell:hover { background: color-mix(in srgb, currentColor 10%, transparent); }
  .ed-side-bell-badge { position: absolute; top: -2px; right: -2px;
                        min-width: 16px; height: 16px; padding: 0 4px;
                        background: var(--q-negative); color: white;
                        border-radius: 99px;
                        font-family: var(--ed-mono); font-size: 9px;
                        font-weight: 700;
                        display: inline-flex; align-items: center;
                        justify-content: center; line-height: 1; }

  /* Drawer host: prevent the inner Quasar content from creating a second
     scrollbar — the nav region owns scrolling and its scrollbar is flush
     with the drawer's right edge. */
  aside.q-drawer.q-drawer--left .q-drawer__content {
                   padding: 0 !important;
                   overflow: hidden !important;
                   display: flex; flex-direction: column; }

  /* Nav list — flush scrollbar */
  .ed-side-nav   { padding: 14px 0 14px 0; flex: 1; min-height: 0;
                   overflow-y: auto; overflow-x: hidden; }
  .ed-side-nav::-webkit-scrollbar { width: 6px; }
  .ed-side-nav::-webkit-scrollbar-track { background: transparent; }
  .ed-side-nav::-webkit-scrollbar-thumb {
                   background: color-mix(in srgb, currentColor 22%, transparent);
                   border-radius: 99px; }
  .ed-side-nav::-webkit-scrollbar-thumb:hover {
                   background: color-mix(in srgb, currentColor 36%, transparent); }
  /* Firefox */
  .ed-side-nav   { scrollbar-width: thin;
                   scrollbar-color: color-mix(in srgb, currentColor 22%, transparent) transparent; }

  /* Collapsible section header */
  .ed-side-section-head {
                   display: flex !important; align-items: center;
                   justify-content: space-between;
                   padding: 14px 20px 6px 20px;
                   font-family: var(--ed-sans); font-weight: 700;
                   text-transform: uppercase; letter-spacing: 0.18em;
                   font-size: 10px; opacity: 0.55;
                   cursor: pointer; user-select: none;
                   transition: opacity 120ms ease;
                   border: none; background: transparent; color: inherit;
                   width: 100%; text-align: left; }
  .ed-side-section-head:hover { opacity: 0.9; }
  .ed-side-section-chevron {
                   font-size: 16px !important; opacity: 0.55;
                   transition: transform 200ms cubic-bezier(0.16, 1, 0.3, 1); }
  .ed-side-section-head.collapsed .ed-side-section-chevron {
                   transform: rotate(-90deg); }

  .ed-side-item  { display: grid !important;
                   grid-template-columns: 4px 22px 1fr;
                   align-items: center; gap: 10px;
                   padding: 9px 18px 9px 0;
                   cursor: pointer;
                   font-family: inherit; font-size: 13px;
                   color: inherit; opacity: 0.78;
                   border: none; background: transparent;
                   text-align: left; width: 100%;
                   transition: background 120ms ease, opacity 120ms ease; }
  .ed-side-item:hover { background: color-mix(in srgb, currentColor 6%, transparent);
                        opacity: 1; }
  .ed-side-item.active { opacity: 1; font-weight: 600;
                         background: color-mix(in srgb, var(--q-primary) 10%, transparent); }
  .ed-side-item-stripe { width: 4px; height: 20px; border-radius: 0 99px 99px 0;
                         background: transparent; align-self: center; }
  .ed-side-item.active .ed-side-item-stripe { background: var(--q-primary); }
  .ed-side-item .q-icon { font-size: 18px !important; opacity: 0.75; }
  .ed-side-item.active .q-icon { opacity: 1; color: var(--q-primary); }

  /* Footer zone */
  .ed-side-footer{ display: flex !important; align-items: center;
                   justify-content: space-between; gap: 8px;
                   padding: 12px 16px;
                   border-top: 1px solid color-mix(in srgb, currentColor 10%, transparent);
                   margin-top: auto; }
  .ed-side-footer .q-btn { font-family: var(--ed-sans);
                           text-transform: uppercase; letter-spacing: 0.10em;
                           font-size: 11px; font-weight: 600; }

  /* Refined tables wherever they appear inside an .ed-card */
  .ed-card .q-table__container { box-shadow: none !important;
                                 border: 1px solid var(--ed-line);
                                 background: transparent !important; }
  .ed-card .q-table thead th { font-family: var(--ed-sans);
                               text-transform: uppercase; letter-spacing: 0.10em;
                               font-size: 10px; font-weight: 700; opacity: 0.7; }
  .ed-card .q-table tbody td { font-family: var(--ed-mono);
                               font-variant-numeric: tabular-nums;
                               font-size: 12.5px; }
</style>
""", shared=True)


# ---------------------------------------------------------------------------
# Friendly error pages
# ---------------------------------------------------------------------------

_ERROR_PAGES: dict[int, dict[str, str]] = {
    400: {
        "icon": "report_problem",
        "title": "Bad Request",
        "message": "The server could not process the request. This usually means invalid or missing data was sent. Please check your input and try again.",
        "action_label": "Go Back",
        "action_url": "/",
        "color": "warning",
    },
    401: {
        "icon": "lock",
        "title": "Session Expired",
        "message": "Your session has expired or you are not logged in. Please log in again to continue.",
        "action_label": "Go to Login",
        "action_url": "/login",
        "color": "warning",
    },
    403: {
        "icon": "block",
        "title": "Access Denied",
        "message": "You do not have the required permissions to perform this action. Your current role may not be authorized. Contact your administrator if you believe this is an error.",
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
    422: {
        "icon": "edit_off",
        "title": "Validation Error",
        "message": "The submitted data did not pass validation. One or more fields have invalid values (e.g. wrong format, missing required fields, or out-of-range values). Please review your input and try again.",
        "action_label": "Go Back",
        "action_url": "/",
        "color": "orange",
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
    504: {
        "icon": "hourglass_disabled",
        "title": "Gateway Timeout",
        "message": "The backend server took too long to respond. This may indicate heavy load or a long-running operation. Please try again.",
        "action_label": "Retry",
        "action_url": None,
        "color": "warning",
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
        # Try to extract structured error detail from JSON response body
        try:
            body = exc.response.json()
            if isinstance(body, dict):
                if "detail" in body:
                    raw_detail = body["detail"]
                    if isinstance(raw_detail, list):
                        # Pydantic 422 validation errors
                        parts = []
                        for err in raw_detail:
                            loc = " -> ".join(str(l) for l in err.get("loc", []))
                            msg = err.get("msg", "")
                            parts.append(f"{loc}: {msg}" if loc else msg)
                        detail = "; ".join(parts)
                    else:
                        detail = str(raw_detail)
                elif "message" in body:
                    detail = str(body["message"])
                else:
                    detail = str(body)
            else:
                detail = str(body)
        except Exception:
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
    _capture_client_ip()
    return _safe_storage().get("token") is not None


def current_user() -> dict | None:
    return _safe_storage().get("user")


def _get_client_ip() -> str | None:
    """Extract the real client IP from the NiceGUI request headers.

    NiceGUI sits behind nginx, so ``request.client.host`` is always the
    proxy address.  The real client IP is in the ``X-Forwarded-For`` or
    ``X-Real-IP`` headers set by nginx.

    Falls back to the value cached in user storage (set once per session
    by ``_capture_client_ip``).
    """
    try:
        from nicegui import context
        req = context.client.request
        # X-Forwarded-For may be a comma-separated chain; take the leftmost
        forwarded = req.headers.get("x-forwarded-for")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
            if ip:
                return ip
        real_ip = req.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        if req.client:
            return req.client.host
    except Exception:
        pass
    # Fallback: read from storage (set once per page load)
    return _safe_storage().get("client_ip")


def _capture_client_ip() -> None:
    """Snapshot the real client IP into user storage.

    Call this early in every page handler so that subsequent ``api_*``
    calls can forward the IP even if the NiceGUI context is unavailable.
    """
    ip = _get_client_ip()
    if ip:
        _safe_storage()["client_ip"] = ip


def auth_headers() -> dict[str, str]:
    token = _safe_storage().get("token")
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    # Forward the real client IP so the backend audit log records it
    client_ip = _get_client_ip()
    if client_ip:
        headers["X-Forwarded-For"] = client_ip
        headers["X-Real-IP"] = client_ip
    return headers


def has_permission(perm: str) -> bool:
    """Check if the current user has a specific RBAC permission."""
    user = current_user()
    if not user:
        return False
    role = (user.get("role") or "").upper()
    if role == "ADMIN":
        return True
    cache = _safe_storage().get("_rbac_cache")
    if cache:
        import json as _json
        for item in cache:
            if item.get("key") == "rbac_matrix":
                try:
                    parsed = _json.loads(item.get("value", "{}"))
                    return perm in parsed.get(role, [])
                except Exception:
                    return False
    return False


def extract_error_detail(exc: Exception) -> str:
    """Pull a human-readable detail string out of an httpx error or ApiError.

    Falls back to ``str(exc)`` if no structured detail is available."""
    if isinstance(exc, ApiError):
        return exc.detail or str(exc)
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            body = exc.response.json()
            if isinstance(body, dict):
                raw = body.get("detail") or body.get("message")
                if isinstance(raw, list):
                    parts = []
                    for err in raw:
                        loc = " -> ".join(str(l) for l in err.get("loc", []))
                        msg = err.get("msg", "")
                        parts.append(f"{loc}: {msg}" if loc else msg)
                    return "; ".join(parts)
                if raw:
                    return str(raw)
        except Exception:
            pass
    return str(exc)


def _handle_401() -> None:
    """Clear auth state and redirect to login, preserving return URL."""
    try:
        current_path = ui.context.client.page.path
    except Exception:
        current_path = "/"
    return_url = current_path if current_path != "/login" else "/"
    app.storage.user.clear()
    app.storage.user["_return_url"] = return_url
    ui.navigate.to("/login")


async def api_get(path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}{path}", headers=auth_headers(), params=params)
        if r.status_code == 401:
            _handle_401()
            raise Exception("Session expired")
        r.raise_for_status()
        return r.json()


async def api_post(path: str, json: dict | None = None, params: dict | None = None) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{API_URL}{path}", headers=auth_headers(), json=json, params=params)
        if r.status_code == 401:
            _handle_401()
            raise Exception("Session expired")
        r.raise_for_status()
        return r.json()


async def api_put(path: str, json: dict | None = None) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.put(f"{API_URL}{path}", headers=auth_headers(), json=json)
        if r.status_code == 401:
            _handle_401()
            raise Exception("Session expired")
        r.raise_for_status()
        return r.json()


async def api_delete(path: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.delete(f"{API_URL}{path}", headers=auth_headers())
        if r.status_code == 401:
            _handle_401()
            raise Exception("Session expired")
        r.raise_for_status()
        if r.status_code == 204 or not r.content:
            return {}
        return r.json()


# ---------------------------------------------------------------------------
# Login page (kept inline — no dependency on shared helpers)
# ---------------------------------------------------------------------------

@ui.page("/login")
async def login_page():
    _capture_client_ip()
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
            login_headers: dict[str, str] = {}
            client_ip = _get_client_ip()
            if client_ip:
                login_headers["X-Forwarded-For"] = client_ip
                login_headers["X-Real-IP"] = client_ip
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(f"{API_URL}/auth/login", json=payload, headers=login_headers)
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
                return_url = app.storage.user.pop("_return_url", "/")
                ui.navigate.to(return_url)
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

    # Fetch logo config from public branding endpoint (no auth required)
    _login_logo_url = ""
    _login_logo_height = "50"
    try:
        async with httpx.AsyncClient() as client:
            r_cfg = await client.get(f"{API_URL}/configuration/branding")
            if r_cfg.status_code == 200:
                branding = r_cfg.json()
                _login_logo_url = branding.get("logo_url") or ""
                _login_logo_height = branding.get("logo_height") or "50"
    except Exception:
        pass
    if _login_logo_url and "/api/static/uploads/" in _login_logo_url:
        _login_logo_url = _login_logo_url.replace("/api/static/uploads/", "/uploads/")

    # ── Inject login-page CSS ─────────────────────────────────────
    # The app runs in dark mode by default (ui.run(dark=True)). Use dark
    # surfaces so text on the login screen remains readable.
    ui.add_head_html("""
    <style>
      .ed-login-bg {
        position: fixed; inset: 0;
        display: flex; align-items: center; justify-content: center;
        padding: 24px;
        background:
          radial-gradient(circle at 18% 18%,
            color-mix(in srgb, var(--q-primary) 24%, transparent) 0%,
            transparent 45%),
          radial-gradient(circle at 88% 82%,
            color-mix(in srgb, var(--q-info) 18%, transparent) 0%,
            transparent 50%),
          #0d1117;
        color: #e6edf3;
      }
      .ed-login-shell {
        display: grid !important;
        grid-template-columns: 1fr;
        gap: 0;
        max-width: 880px; width: 100%;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 6px;
        overflow: hidden;
        backdrop-filter: blur(20px);
        background: rgba(22, 27, 34, 0.78);
        box-shadow: 0 24px 60px rgba(0, 0, 0, 0.45);
      }
      @media (min-width: 720px) {
        .ed-login-shell { grid-template-columns: 1fr 1fr; }
      }

      /* Brand panel (left) */
      .ed-login-brand {
        position: relative;
        padding: 44px 40px;
        display: flex !important; flex-direction: column;
        justify-content: space-between;
        gap: 24px;
        min-height: 420px;
        background:
          linear-gradient(160deg,
            color-mix(in srgb, var(--q-primary) 22%, transparent) 0%,
            color-mix(in srgb, var(--q-primary) 6%, transparent) 100%);
        border-right: 1px solid rgba(255, 255, 255, 0.08);
        color: #f0f6fc;
      }
      .ed-login-brand::before {
        content: ""; position: absolute; top: 0; left: 0;
        width: 4px; height: 100%;
        background: var(--q-primary);
      }
      /* Login brand logo — scales to ~60% of the brand panel width while
         preserving the logo's natural aspect ratio. */
      .ed-login-brand-logo { width: 60% !important;
                             min-width: 180px !important;
                             max-width: 280px !important;
                             min-height: 100px !important;
                             margin-bottom: 8px;
                             flex: 0 0 auto;
                             filter: drop-shadow(0 2px 6px rgba(0,0,0,0.35)); }
      .ed-login-brand-logo > img,
      .ed-login-brand-logo .q-img__image,
      .ed-login-brand-logo .q-img__container > div {
                             object-fit: contain !important;
                             object-position: left center !important;
                             background-size: contain !important;
                             background-position: left center !important; }
      .ed-login-brand-title { font-family: inherit; font-weight: 700;
                              font-size: 32px; line-height: 1.1;
                              letter-spacing: -0.015em;
                              margin: 14px 0 10px 0;
                              color: #ffffff; }
      .ed-login-brand-tagline { font-family: inherit; font-size: 14px;
                                opacity: 0.82; line-height: 1.55;
                                max-width: 32ch;
                                color: #c9d1d9; }
      .ed-login-brand-meta { font-family: var(--ed-mono);
                             font-size: 11px; opacity: 0.65;
                             letter-spacing: 0.06em;
                             color: #8b949e; }

      /* Form panel (right) */
      .ed-login-form {
        padding: 44px 40px;
        display: flex !important; flex-direction: column;
        justify-content: center; gap: 14px; min-height: 420px;
        color: #e6edf3;
      }
      .ed-login-cap { font-family: var(--ed-sans); text-transform: uppercase;
                      letter-spacing: 0.18em; font-size: 11px; font-weight: 700;
                      opacity: 0.6; margin-bottom: 6px;
                      color: #8b949e; }
      .ed-login-heading { font-family: inherit; font-size: 22px; font-weight: 600;
                          line-height: 1.2; margin: 0 0 22px 0;
                          color: #ffffff; }

      /* Force input fields to render with readable contrast on the dark surface */
      .ed-login-form .q-field__control { background: rgba(255, 255, 255, 0.04);
                                         border-radius: 4px; }
      .ed-login-form .q-field__native,
      .ed-login-form .q-field__label { color: #e6edf3 !important; }
      .ed-login-form .q-field__native::placeholder { color: rgba(230, 237, 243, 0.4); }
      .ed-login-form .q-field--outlined .q-field__control:before { border-color: rgba(255,255,255,0.18); }
      .ed-login-form .q-field--outlined.q-field--focused .q-field__control:after {
                                                  border-color: var(--q-primary); }
      .ed-login-form .q-field { margin-bottom: 4px; }

      .ed-login-method  { display: inline-flex !important; align-items: center;
                          gap: 4px; padding: 4px;
                          border: 1px solid rgba(255, 255, 255, 0.12);
                          border-radius: 99px;
                          margin-bottom: 18px; align-self: flex-start; }
      .ed-login-method-btn { padding: 6px 14px; border-radius: 99px;
                             font-family: inherit; font-size: 12px; font-weight: 500;
                             cursor: pointer; transition: all 140ms ease;
                             border: none; background: transparent;
                             color: #c9d1d9; line-height: 1.2; }
      .ed-login-method-btn:hover  { background: rgba(255, 255, 255, 0.06);
                                    color: #ffffff; }
      .ed-login-method-btn.active { background: var(--q-primary); color: #ffffff; }

      .ed-login-submit { margin-top: 12px !important; height: 44px;
                         font-family: var(--ed-sans);
                         text-transform: uppercase; letter-spacing: 0.14em;
                         font-size: 12px; font-weight: 600; }
      .ed-login-foot { margin-top: 18px; font-family: var(--ed-mono);
                       font-size: 10px; opacity: 0.45; text-align: center;
                       letter-spacing: 0.08em; text-transform: uppercase;
                       color: #8b949e; }
    </style>
    """)

    with ui.element("div").classes("ed-login-bg"):
        with ui.element("div").classes("ed-login-shell"):

            # ── Left: brand panel ──────────────────────────────
            with ui.element("div").classes("ed-login-brand"):
                with ui.element("div"):
                    if _login_logo_url:
                        # No `ratio` prop — q-img uses the loaded image's
                        # natural aspect ratio so wide-aspect logos render
                        # at their intended proportions (not a square box).
                        # The CSS class enforces width: 40% of the brand
                        # panel, capped at 200px, with a min-height so the
                        # element reserves space before the image loads.
                        ui.image(_login_logo_url) \
                            .classes("ed-login-brand-logo") \
                            .props("fit=contain no-spinner")
                    ui.label("PRESTO").classes("ed-login-brand-title")
                    ui.label(
                        "Project Request Estimation Tool. "
                        "Plan test effort, track requests, "
                        "and ship predictable estimations."
                    ).classes("ed-login-brand-tagline")
                ui.label("v3.4.0 · INTERNAL TOOL").classes("ed-login-brand-meta")

            # ── Right: form panel ──────────────────────────────
            with ui.element("div").classes("ed-login-form"):
                ui.label("Sign In").classes("ed-login-cap")
                ui.label("Welcome back").classes("ed-login-heading")

                if has_ldap:
                    method_local = ui.element("button").classes(
                        "ed-login-method-btn active")
                    method_ldap = ui.element("button").classes(
                        "ed-login-method-btn")
                    with ui.element("div").classes("ed-login-method"):
                        with method_local:
                            ui.label("Internal")
                        with method_ldap:
                            ui.label("LDAP")

                    def _set_method_local():
                        auth_method["value"] = "local"
                        method_local.classes(add="active")
                        method_ldap.classes(remove="active")

                    def _set_method_ldap():
                        auth_method["value"] = "ldap"
                        method_ldap.classes(add="active")
                        method_local.classes(remove="active")

                    method_local.on("click", lambda: _set_method_local())
                    method_ldap.on("click", lambda: _set_method_ldap())

                username = ui.input("Username").props("outlined dense").classes("w-full")
                username.on("keydown.enter", lambda: password.run_method("focus"))
                password = ui.input("Password", password=True,
                                    password_toggle_button=True) \
                    .props("outlined dense").classes("w-full")
                password.on("keydown.enter", try_login)

                ui.button("Sign In", on_click=try_login) \
                    .props("color=primary unelevated") \
                    .classes("w-full ed-login-submit")

                ui.label("PRESTO · authenticated session").classes("ed-login-foot")


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

def _nav_item(label: str, icon_name: str, path: str, current_path: str = "") -> None:
    """Render a sidebar navigation item with active-route highlighting."""
    is_active = current_path == path or (
        path != "/" and current_path.startswith(path)
    )
    cls = "ed-side-item" + (" active" if is_active else "")
    btn = ui.element("button").classes(cls)
    btn.on("click", lambda p=path: ui.navigate.to(p))
    with btn:
        ui.element("span").classes("ed-side-item-stripe")
        ui.icon(icon_name)
        ui.label(label)


def _initials(name: str) -> str:
    """Return up to 2 initials from a display name (e.g. 'Jane Doe' → 'JD')."""
    if not name:
        return "?"
    parts = [p for p in name.strip().split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return parts[0][:2].upper() if parts else "?"


def _section_header(section_id: str, label: str):
    """Render a clickable section header that toggles the visibility of its
    items container. Returns the items container so callers can add nav items
    inside a `with` block. The open/collapsed state persists per user across
    page navigations via app.storage.user.
    """
    storage = _safe_storage()
    state_dict = storage.get("_sidebar_sections") or {}
    is_open = state_dict.get(section_id, True)  # default: open

    head_cls = "ed-side-section-head" + ("" if is_open else " collapsed")
    head = ui.element("button").classes(head_cls)
    with head:
        ui.label(label)
        chevron = ui.icon("expand_more").classes("ed-side-section-chevron")

    items_container = ui.element("div").classes("ed-side-section-items")
    if not is_open:
        items_container.set_visibility(False)

    def _toggle():
        store = _safe_storage()
        s = store.get("_sidebar_sections") or {}
        new_state = not s.get(section_id, True)
        s[section_id] = new_state
        store["_sidebar_sections"] = s
        items_container.set_visibility(new_state)
        if new_state:
            head.classes(remove="collapsed")
        else:
            head.classes(add="collapsed")

    head.on("click", _toggle)
    return items_container


def sidebar():
    user = current_user()
    role = user.get("role", "VIEWER") if user else "VIEWER"

    # Load configuration list (cached in storage) for logo, RBAC, and theme
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

    # Extract logo config from the already-loaded config list
    _logo_url = ""
    _logo_height = "40"
    if _cfg_list:
        for _ci_logo in _cfg_list:
            if _ci_logo.get("key") == "logo_url":
                _logo_url = _ci_logo.get("value") or ""
            elif _ci_logo.get("key") == "logo_height":
                _logo_height = _ci_logo.get("value") or "40"
    if _logo_url and "/api/static/uploads/" in _logo_url:
        _logo_url = _logo_url.replace("/api/static/uploads/", "/uploads/")

    # Detect current route for active-nav highlighting
    try:
        current_path = ui.context.client.page.path
    except Exception:
        current_path = "/"

    # Drawer background is controlled by the injected theme CSS below
    # (sidebar_bg_light / sidebar_bg_dark). We avoid `bg-dark` because its
    # `!important` rule wins over our injected style.
    with ui.left_drawer(value=True) \
            .style("display: flex; flex-direction: column; padding: 0;") as drawer:

        # ── Logo zone ─────────────────────────────────────────
        with ui.element("div").classes("ed-side-logo"):
            if _logo_url:
                # Q-img wrapper with a 1:1 ratio + class-driven sizing so
                # the image renders reliably inside the flex row.
                ui.image(_logo_url) \
                    .classes("ed-side-logo-img") \
                    .props("ratio=1 fit=contain no-spinner")
            ui.label("PRESTO").classes("ed-side-logo-text")

        # ── User card ─────────────────────────────────────────
        if user:
            with ui.element("div").classes("ed-side-user"):
                ui.label(_initials(user.get("display_name") or user.get("username", ""))) \
                    .classes("ed-side-avatar")
                with ui.element("div").classes("ed-side-user-meta"):
                    ui.label(user.get("display_name") or user.get("username", "")) \
                        .classes("ed-side-user-name")
                    ui.label(f"{role}").classes("ed-side-user-role")
                # Notification bell
                bell_btn = ui.element("div").classes("ed-side-bell")
                bell_btn.on("click", lambda: _open_notifications_dialog())
                with bell_btn:
                    ui.icon("notifications").style("font-size: 18px;")
                    bell_badge = ui.label("0").classes("ed-side-bell-badge hidden")

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

        with ui.element("div").classes("ed-side-nav"):

            # -- Overview --
            with _section_header("overview", "Overview"):
                _nav_item("Dashboard",     "dashboard", "/", current_path)
                if _has_perm("view_requests") or _has_perm("manage_requests"):
                    _nav_item("Request Inbox", "inbox", "/requests", current_path)

            # -- Estimation --
            with _section_header("estimation", "Estimation"):
                _nav_item("Estimations",    "list_alt",   "/estimations",     current_path)
                _nav_item("New Estimation", "add_circle", "/estimation/new",  current_path)

            # -- Data Management --
            with _section_header("data_management", "Data Management"):
                _nav_item("Feature Catalog",     "category",    "/features",         current_path)
                _nav_item("Task Templates",      "assignment",  "/tasks",            current_path)
                _nav_item("DUT Registry",        "devices",     "/duts",             current_path)
                _nav_item("DUT Assets",          "inventory",   "/assets",           current_path)
                _nav_item("Test Profiles",       "tune",        "/profiles",         current_path)
                _nav_item("Historical Projects", "history",     "/history",          current_path)
                _nav_item("Team Members",        "group",       "/team",             current_path)
                _nav_item("Risk Registry",       "warning",     "/risks",            current_path)
                _nav_item("PR Registry",         "bug_report",  "/pr-registry",      current_path)
                _nav_item("Document Types",      "description", "/document-types",   current_path)
                _nav_item("Public Holidays",     "event",       "/public-holidays",  current_path)

            # -- Administration --
            with _section_header("administration", "Administration"):
                _nav_item("Settings",     "settings", "/settings",     current_path)
                _nav_item("Integrations", "sync",     "/integrations", current_path)

                if role == "ADMIN":
                    _nav_item("Users",            "manage_accounts",      "/users",        current_path)
                    _nav_item("RBAC",             "admin_panel_settings", "/rbac",         current_path)
                    _nav_item("Audit Log",        "receipt_long",         "/audit",        current_path)
                    _nav_item("Backup & Restore", "backup",               "/admin/backup", current_path)

        # Restore persisted dark/light preference (default: dark)
        is_dark = _safe_storage().get("dark_mode", True)
        dark = ui.dark_mode(is_dark)

        # Precompute both light and dark theme colors
        _theme = {
            "hdr_light": "#E0E0E0", "hdr_dark": "#424242",
            "sidebar_light": "#FFFFFF", "sidebar_dark": "#1D1D1D",
            "content_light": "#FAFAFA", "content_dark": "#121212",
            "button_light": "#1976D2", "button_dark": "#90CAF9",
        }
        if _cfg_list:
            _theme_keys = {
                "table_header_bg_light": "hdr_light",
                "table_header_bg_dark": "hdr_dark",
                "sidebar_bg_light": "sidebar_light",
                "sidebar_bg_dark": "sidebar_dark",
                "content_bg_light": "content_light",
                "content_bg_dark": "content_dark",
                "button_color_light": "button_light",
                "button_color_dark": "button_dark",
            }
            for _ci in _cfg_list:
                k, v = _ci.get("key", ""), _ci.get("value", "")
                if v and k in _theme_keys:
                    _theme[_theme_keys[k]] = v

        def _apply_theme_css(dark_mode: bool) -> None:
            suffix = "dark" if dark_mode else "light"
            hdr = _theme[f"hdr_{suffix}"]
            sidebar_bg = _theme[f"sidebar_{suffix}"]
            content_bg = _theme[f"content_{suffix}"]
            btn = _theme[f"button_{suffix}"]
            # Compute readable text color for sidebar based on its background luminance
            try:
                _sb = sidebar_bg.lstrip("#")
                _r, _g, _b = int(_sb[0:2], 16), int(_sb[2:4], 16), int(_sb[4:6], 16)
                _lum = (0.299 * _r + 0.587 * _g + 0.114 * _b)
                sidebar_text = "#FFFFFF" if _lum < 140 else "#212121"
            except Exception:
                sidebar_text = "#FFFFFF" if dark_mode else "#212121"
            ui.run_javascript(f"""
                document.getElementById('theme-dynamic')?.remove();
                var s = document.createElement('style');
                s.id = 'theme-dynamic';
                s.textContent = `
                    .q-table thead th {{ background-color: {hdr} !important; }}
                    aside.q-drawer.q-drawer--left,
                    aside.q-drawer.q-drawer--left .q-drawer__content {{
                        background-color: {sidebar_bg} !important;
                        color: {sidebar_text} !important;
                    }}
                    aside.q-drawer.q-drawer--left .q-item__label,
                    aside.q-drawer.q-drawer--left .text-caption,
                    aside.q-drawer.q-drawer--left .text-h6 {{
                        color: {sidebar_text} !important;
                    }}
                    .q-page {{ background-color: {content_bg} !important; }}
                    .q-btn--standard.bg-primary {{ background-color: {btn} !important; }}
                `;
                document.head.appendChild(s);
            """)

        _apply_theme_css(is_dark)

        def toggle_theme():
            dark.toggle()
            _safe_storage()["dark_mode"] = dark.value
            _apply_theme_css(dark.value)

        async def logout():
            try:
                await api_post("/auth/logout")
            except Exception:
                pass
            app.storage.user.clear()
            ui.navigate.to("/login")

        # ── Footer (theme toggle + logout) ────────────────────
        with ui.element("div").classes("ed-side-footer"):
            ui.button(icon="brightness_6", on_click=toggle_theme) \
                .props("flat round dense").tooltip("Toggle theme")
            ui.button("Logout", icon="logout", on_click=logout) \
                .props("flat dense")

    return drawer


# ---------------------------------------------------------------------------
# Dashboard (kept inline — the main landing page)
# ---------------------------------------------------------------------------

@ui.page("/")
async def dashboard_page():
    _capture_client_ip()
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    # ─────────────────────────────────────────────────────────────
    # Inject dashboard-specific component CSS (base CSS is in the
    # global head added in this file at module load time).
    # ─────────────────────────────────────────────────────────────
    ui.add_head_html("""
    <style>
      /* KPI hero grid */
      .ed-kpi-hero-grid { display: grid !important; gap: 1px;
                          grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                          border: 1px solid var(--ed-line); border-radius: 4px;
                          overflow: hidden; margin-bottom: 28px;
                          background: var(--ed-line); }
      .ed-kpi-hero-cell { padding: 22px 24px; background: var(--q-page, transparent);
                          display: flex; flex-direction: column; gap: 10px;
                          min-height: 120px; }
      .ed-kpi-hero-num  { font-family: var(--ed-mono); font-variant-numeric: tabular-nums;
                          font-size: 38px; font-weight: 500; line-height: 1;
                          letter-spacing: -0.02em; }
      .ed-kpi-hero-unit { font-family: inherit; font-size: 12px; opacity: 0.65;
                          display: flex; align-items: center; gap: 6px; }

      /* Pipeline flow */
      .ed-pipeline      { display: flex !important; align-items: stretch;
                          gap: 0; margin-top: 14px; flex-wrap: wrap; }
      .ed-pipeline-stage{ flex: 1 1 0; min-width: 110px;
                          padding: 18px 14px;
                          border: 1px solid var(--ed-line); border-radius: 4px;
                          background: transparent; cursor: pointer;
                          transition: border-color 160ms ease, background 160ms ease;
                          display: flex; flex-direction: column; gap: 8px; }
      .ed-pipeline-stage:hover { border-color: var(--q-primary);
                                 background: color-mix(in srgb, var(--q-primary) 6%, transparent); }
      .ed-pipeline-stage.empty { opacity: 0.45; }
      .ed-pipeline-stage-num { font-family: var(--ed-mono);
                               font-variant-numeric: tabular-nums;
                               font-size: 30px; font-weight: 500; line-height: 1; }
      .ed-pipeline-arrow { display: flex !important; align-items: center;
                           justify-content: center;
                           padding: 0 6px; opacity: 0.4;
                           font-family: var(--ed-mono); font-size: 18px; }

      /* Activity feed */
      .ed-feed        { display: flex !important; flex-direction: column;
                        border: 1px solid var(--ed-line); border-radius: 4px;
                        overflow: hidden; margin-bottom: 22px; }
      .ed-feed-item   { display: grid !important;
                        grid-template-columns: 4px auto 1fr auto auto;
                        gap: 14px; align-items: center;
                        padding: 14px 18px; cursor: pointer;
                        border-bottom: 1px dashed var(--ed-line-soft);
                        transition: background 140ms ease; }
      .ed-feed-item:last-child { border-bottom: none; }
      .ed-feed-item:hover { background: var(--ed-bg-soft); }
      .ed-feed-stripe { width: 4px; height: 32px; border-radius: 99px;
                        background: var(--q-info); }
      .ed-feed-stripe.positive { background: var(--q-positive); }
      .ed-feed-stripe.warning  { background: var(--q-warning); }
      .ed-feed-stripe.negative { background: var(--q-negative); }
      .ed-feed-id     { font-family: var(--ed-mono); font-size: 12px; opacity: 0.7; }
      .ed-feed-title  { font-size: 14px; font-weight: 500; line-height: 1.3;
                        white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .ed-feed-num    { font-family: var(--ed-mono); font-variant-numeric: tabular-nums;
                        font-size: 13px; }
      .ed-feed-meta   { font-family: var(--ed-mono); font-size: 11px;
                        opacity: 0.6; text-align: right; min-width: 80px; }

      .ed-section-link { font-family: inherit; font-size: 12px;
                         color: var(--q-primary); text-decoration: none;
                         opacity: 0.85; cursor: pointer; }
      .ed-section-link:hover { opacity: 1; text-decoration: underline; }

      /* Compressed chart cards */
      .ed-chart-grid    { display: grid !important;
                          grid-template-columns: repeat(2, 1fr); gap: 14px;
                          margin-bottom: 12px; }
      @media (max-width: 720px) { .ed-chart-grid { grid-template-columns: 1fr; } }
      .ed-chart-card    { padding: 18px 20px !important; margin-bottom: 0 !important; }
      .ed-chart-card .echarts { height: 280px !important; }
    </style>
    """)

    # Resolve chart text color from dark/light mode
    _is_dark = _safe_storage().get("dark_mode", True)
    _chart_text = "#FFFFFF" if _is_dark else "#333333"

    # Use scrollable horizontal legend so it never wraps + clips into the donut.
    # Pads from the bottom edge to leave room for the scroll arrows.
    _legend = {
        "type": "scroll",
        "orient": "horizontal",
        "bottom": 4,
        "left": "center",
        "padding": [4, 24],
        "textStyle": {"color": _chart_text, "fontSize": 10},
        "pageIconColor": _chart_text,
        "pageIconInactiveColor": "rgba(150,150,150,0.3)",
        "pageTextStyle": {"color": _chart_text, "fontSize": 9},
        "itemGap": 12,
        "itemWidth": 12,
        "itemHeight": 8,
    }
    _label = {"show": True, "formatter": "{b}\n{c}", "fontSize": 10, "color": _chart_text}
    _emphasis = {"label": {"show": True, "fontSize": 13, "fontWeight": "bold"}}

    _palette = ["#42A5F5", "#66BB6A", "#FFA726", "#EF5350", "#AB47BC",
                "#26C6DA", "#EC407A", "#8D6E63", "#78909C", "#FFEE58"]

    # ─── Helpers ─────────────────────────────────────────────────
    def _kpi_hero(label: str, value: str, sub: str = "", icon: str = "") -> None:
        with ui.element("div").classes("ed-kpi-hero-cell"):
            ui.label(label).classes("ed-eyebrow")
            ui.label(value).classes("ed-kpi-hero-num")
            if sub or icon:
                with ui.element("div").classes("ed-kpi-hero-unit"):
                    if icon:
                        ui.icon(icon).style("font-size: 14px; opacity: 0.7;")
                    if sub:
                        ui.label(sub)

    def _pipeline_stage(label: str, count: int, nav: str | None = None) -> None:
        cls = "ed-pipeline-stage" + (" empty" if count == 0 else "")
        el = ui.element("div").classes(cls)
        if nav:
            el.on("click", lambda _, n=nav: ui.navigate.to(n))
        with el:
            ui.label(str(count)).classes("ed-pipeline-stage-num")
            ui.label(label).classes("ed-eyebrow")

    def _feed_item(stripe: str, id_text: str, title: str, num: str, meta: str, nav: str) -> None:
        item = ui.element("div").classes("ed-feed-item")
        item.on("click", lambda _, n=nav: ui.navigate.to(n))
        with item:
            ui.element("div").classes(f"ed-feed-stripe {stripe}")
            ui.label(id_text or "—").classes("ed-feed-id")
            ui.label(title or "(untitled)").classes("ed-feed-title")
            ui.label(num).classes("ed-feed-num")
            ui.label(meta).classes("ed-feed-meta")

    def _format_age(iso: str | None) -> str:
        if not iso:
            return ""
        try:
            from datetime import datetime, timezone
            d = datetime.fromisoformat(iso.replace("Z", "+00:00")) if "T" in iso else datetime.fromisoformat(iso)
            now = datetime.now(timezone.utc) if d.tzinfo else datetime.now()
            delta = now - d
            days = delta.days
            if days < 1:
                return "today"
            if days < 7:
                return f"{days}d"
            if days < 30:
                return f"{days // 7}w"
            return f"{days // 30}mo"
        except Exception:
            return iso[:10]

    def _donut(title: str, series_name: str, data: list[dict]) -> None:
        with ui.element("div").classes("ed-card ed-chart-card"):
            with ui.element("div").classes("ed-card-head"):
                ui.label(title).classes("ed-cap")
                _t = sum(d.get("value", 0) for d in data)
                ui.label(f"{_t} TOTAL").classes("ed-card-head-meta")
            ui.echart({
                "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
                "legend": _legend,
                "series": [{
                    "name": series_name,
                    "type": "pie",
                    "radius": ["38%", "62%"],
                    "center": ["50%", "44%"],
                    "avoidLabelOverlap": True,
                    "label": _label,
                    "emphasis": _emphasis,
                    "data": data,
                }],
            }).classes("w-full")

    def _bar(title: str, categories: list[str], values: list[int], color: str = "#42A5F5") -> None:
        with ui.element("div").classes("ed-card ed-chart-card"):
            with ui.element("div").classes("ed-card-head"):
                ui.label(title).classes("ed-cap")
                ui.label(f"{sum(values)} TOTAL").classes("ed-card-head-meta")
            ui.echart({
                "tooltip": {"trigger": "axis"},
                "grid": {"left": "3%", "right": "6%", "bottom": "3%", "top": "8%", "containLabel": True},
                "xAxis": {"type": "value", "axisLabel": {"color": _chart_text, "fontSize": 10}},
                "yAxis": {"type": "category", "data": categories,
                          "axisLabel": {"color": _chart_text, "fontSize": 10}},
                "series": [{
                    "type": "bar",
                    "data": values,
                    "itemStyle": {"color": color},
                    "label": {"show": True, "position": "right",
                              "color": _chart_text, "fontSize": 10},
                }],
            }).classes("w-full")

    # ─── Page body ───────────────────────────────────────────────
    with ui.column().classes("w-full q-pa-md").style("gap: 0;"):

        try:
            stats = await api_get("/dashboard/stats")
        except Exception as e:
            show_error_page(e)
            return

        with ui.element("div").classes("ed-shell"):

            # Page header row
            with ui.row().classes("items-baseline justify-between q-mb-md w-full"):
                ui.label("Dashboard").classes("text-h4")
                ui.label("Operational summary · live").classes("ed-eyebrow")

            # ── KPI hero strip ─────────────────────────────────
            active = stats.get("estimations_draft", 0) + stats.get("estimations_final", 0)
            open_req = max(stats.get("total_requests", 0) - stats.get("requests_completed", 0), 0)
            avg_h = stats.get("avg_grand_total_hours", 0)
            util = stats.get("avg_utilization_pct", 0)

            with ui.element("div").classes("ed-kpi-hero-grid"):
                _kpi_hero(
                    "Open Requests",
                    str(open_req),
                    f"{stats.get('requests_new', 0)} new in inbox",
                    "inbox",
                )
                _kpi_hero(
                    "Active Estimations",
                    str(active),
                    f"{stats.get('estimations_final', 0)} awaiting approval",
                    "edit_note",
                )
                _kpi_hero(
                    "Avg Estimation",
                    f"{avg_h:,.0f}h",
                    "across final + approved",
                    "schedule",
                )
                _kpi_hero(
                    "Team Utilization",
                    f"{util:.0f}%",
                    "of allocated capacity",
                    "speed",
                )

            # ── Pipeline flow card ──────────────────────────────
            with ui.element("div").classes("ed-card"):
                with ui.element("div").classes("ed-card-head"):
                    ui.label("Pipeline State").classes("ed-cap")
                    ui.label("requests → estimations → approval").classes("ed-eyebrow")
                with ui.element("div").classes("ed-pipeline"):
                    _pipeline_stage("Inbox · New",
                                    stats.get("requests_new", 0),
                                    "/requests")
                    ui.label("→").classes("ed-pipeline-arrow")
                    _pipeline_stage("Estimating",
                                    stats.get("requests_in_progress", 0),
                                    "/requests")
                    ui.label("→").classes("ed-pipeline-arrow")
                    _pipeline_stage("Draft",
                                    stats.get("estimations_draft", 0),
                                    "/estimations")
                    ui.label("→").classes("ed-pipeline-arrow")
                    _pipeline_stage("Final",
                                    stats.get("estimations_final", 0),
                                    "/estimations")
                    ui.label("→").classes("ed-pipeline-arrow")
                    _pipeline_stage("Approved",
                                    stats.get("estimations_approved", 0),
                                    "/estimations")

            # ── Distribution charts (compact, 2x2) ──────────────
            with ui.element("div").classes("ed-section-head"):
                ui.label("Distribution").classes("ed-cap")

            with ui.element("div").classes("ed-chart-grid"):
                # Estimations donut
                total_est = stats.get("total_estimations", 0)
                _donut(
                    f"Estimations · {total_est}",
                    "Estimations",
                    [
                        {"value": stats.get("estimations_draft", 0), "name": "Draft",
                         "itemStyle": {"color": "#78909C"}},
                        {"value": stats.get("estimations_final", 0), "name": "Final",
                         "itemStyle": {"color": "#1976D2"}},
                        {"value": stats.get("estimations_approved", 0), "name": "Approved",
                         "itemStyle": {"color": "#4CAF50"}},
                    ],
                )

                # Requests donut
                total_req = stats.get("total_requests", 0)
                req_data = [
                    {"value": stats.get("requests_new", 0), "name": "New",
                     "itemStyle": {"color": "#26A69A"}},
                    {"value": stats.get("requests_in_progress", 0), "name": "In Progress",
                     "itemStyle": {"color": "#FFA726"}},
                    {"value": stats.get("requests_completed", 0), "name": "Completed",
                     "itemStyle": {"color": "#66BB6A"}},
                ]
                rejected = total_req - sum(d["value"] for d in req_data)
                if rejected > 0:
                    req_data.append({"value": rejected, "name": "Other",
                                     "itemStyle": {"color": "#BDBDBD"}})
                _donut(f"Requests · {total_req}", "Requests", req_data)

            with ui.element("div").classes("ed-chart-grid"):
                # Features by category
                feat_cat = stats.get("features_by_category", {})
                if feat_cat:
                    feat_data = [
                        {"value": cnt, "name": cat,
                         "itemStyle": {"color": _palette[i % len(_palette)]}}
                        for i, (cat, cnt) in enumerate(feat_cat.items())
                    ]
                    _donut(f"Features · {sum(d['value'] for d in feat_data)}",
                           "Features", feat_data)
                else:
                    with ui.element("div").classes("ed-card ed-chart-card"):
                        ui.label("Features").classes("ed-cap")
                        ui.label("No features configured").classes("ed-empty q-mt-md")

                # Risks by likelihood
                risk_lh = stats.get("risks_by_likelihood", {})
                _lh_colors = {"LOW": "#66BB6A", "MEDIUM": "#FFA726",
                              "HIGH": "#EF5350", "CRITICAL": "#B71C1C"}
                if risk_lh:
                    risk_lh_data = [
                        {"value": cnt, "name": lh,
                         "itemStyle": {"color": _lh_colors.get(lh, "#78909C")}}
                        for lh, cnt in risk_lh.items()
                    ]
                    _donut(f"Risks · {sum(d['value'] for d in risk_lh_data)}",
                           "Likelihood", risk_lh_data)
                else:
                    with ui.element("div").classes("ed-card ed-chart-card"):
                        ui.label("Risk Likelihood").classes("ed-cap")
                        ui.label("No risks configured").classes("ed-empty q-mt-md")

            # Tasks bar (full width since it's horizontal)
            tasks_type = stats.get("tasks_by_type", {})
            if tasks_type:
                sorted_tasks = sorted(tasks_type.items(), key=lambda x: x[1], reverse=True)
                cats = [t[0] for t in sorted_tasks]
                vals = [t[1] for t in sorted_tasks]
                _bar(f"Task Templates · {sum(vals)}", cats, vals, "#42A5F5")

            # ── Recent estimations feed ─────────────────────────
            with ui.element("div").classes("ed-section-head"):
                ui.label("Recent Estimations").classes("ed-cap")
                _link = ui.element("span").classes("ed-section-link")
                _link.on("click", lambda: ui.navigate.to("/estimations"))
                with _link:
                    ui.label("see all →")

            recent = stats.get("recent_estimations", [])
            if recent:
                with ui.element("div").classes("ed-feed"):
                    for est in recent[:6]:
                        _stripe_map = {
                            "FEASIBLE": "positive",
                            "AT_RISK": "warning",
                            "NOT_FEASIBLE": "negative",
                        }
                        stripe = _stripe_map.get(est.get("feasibility_status", ""), "")
                        _feed_item(
                            stripe=stripe,
                            id_text=est.get("estimation_number") or f"#{est.get('id', '?')}",
                            title=est.get("project_name", ""),
                            num=f"{est.get('grand_total_hours', 0):,.0f}h",
                            meta=_format_age(est.get("created_at")),
                            nav=f"/estimation/{est.get('id')}",
                        )
            else:
                ui.label("No estimations yet").classes("ed-empty")

            # ── Recent requests feed ────────────────────────────
            with ui.element("div").classes("ed-section-head"):
                ui.label("Recent Requests").classes("ed-cap")
                _link2 = ui.element("span").classes("ed-section-link")
                _link2.on("click", lambda: ui.navigate.to("/requests"))
                with _link2:
                    ui.label("see all →")

            recent_req = stats.get("recent_requests", [])
            if recent_req:
                with ui.element("div").classes("ed-feed"):
                    for req in recent_req[:6]:
                        _pri = req.get("priority", "")
                        _pri_stripe = {
                            "CRITICAL": "negative",
                            "HIGH": "negative",
                            "MEDIUM": "warning",
                            "LOW": "positive",
                        }.get(_pri, "")
                        _feed_item(
                            stripe=_pri_stripe,
                            id_text=req.get("request_number") or f"#{req.get('id', '?')}",
                            title=req.get("title", ""),
                            num=_pri,
                            meta=_format_age(req.get("created_at")),
                            nav=f"/requests/{req.get('id')}",
                        )
            else:
                ui.label("No requests yet").classes("ed-empty")


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
import frontend_nicegui.pages.risks         # noqa: F401,E402
import frontend_nicegui.pages.assets        # noqa: F401,E402
import frontend_nicegui.pages.pr_registry   # noqa: F401,E402
import frontend_nicegui.pages.documents    # noqa: F401,E402
import frontend_nicegui.pages.holidays    # noqa: F401,E402
import frontend_nicegui.pages.backup     # noqa: F401,E402

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
        title="PRESTO",
        port=_port,
        storage_secret="estimation-tool-secret-change-me",
        favicon="🧪",
        dark=True,
        **_ssl_kwargs,
    )
