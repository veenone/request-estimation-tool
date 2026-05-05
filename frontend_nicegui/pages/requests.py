"""NiceGUI pages for the Request Inbox.

Route 1: /requests        — paginated, filterable list with an Add dialog.
Route 2: /requests/{id}  — detail view with edit, assignment, and linked
                            estimations.
"""

import json
from datetime import date

from nicegui import ui

import httpx

from frontend_nicegui.app import (
    API_URL,
    api_delete,
    api_get,
    api_post,
    api_put,
    auth_headers,
    current_user,
    is_authenticated,
    show_error_page,
    sidebar,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PRIORITY_CLASSES: dict[str, str] = {
    "LOW": "text-positive",
    "MEDIUM": "text-warning",
    "HIGH": "text-negative",
    "CRITICAL": "text-negative text-bold",
}

_STATUS_CLASSES: dict[str, str] = {
    "NEW": "text-info",
    "IN_ESTIMATION": "text-warning",
    "ESTIMATED": "text-positive",
    "COMPLETED": "text-positive",
    "REJECTED": "text-negative",
    "DELETED_UPSTREAM": "text-negative",
}

_SOURCE_OPTIONS = ["MANUAL", "REDMINE", "JIRA", "EMAIL"]
_PRIORITY_OPTIONS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
_STATUS_FILTER_OPTIONS = ["All", "NEW", "IN_ESTIMATION", "ESTIMATED", "COMPLETED", "REJECTED", "DELETED_UPSTREAM"]


def _priority_badge(priority: str) -> None:
    """Render an inline priority chip with colour coding."""
    css = _PRIORITY_CLASSES.get(priority, "")
    ui.badge(priority).props("outline").classes(css)


def _status_badge(status: str) -> None:
    """Render an inline status chip with colour coding."""
    css = _STATUS_CLASSES.get(status, "")
    ui.badge(status).props("outline").classes(css)


def _fmt_date(iso: str | None) -> str:
    """Return only the date portion of an ISO datetime string."""
    if not iso:
        return ""
    return iso[:10]


# ---------------------------------------------------------------------------
# Route 1: /requests — Request List
# ---------------------------------------------------------------------------


@ui.page("/requests")
async def requests_list_page() -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    # (filter component CSS — .ed-stat-tile, .ed-segmented, .ed-filter-row —
    # is now in app.py global head)

    # ─────────────────────────────────────────────────────────────
    # Fetch reference data
    # ─────────────────────────────────────────────────────────────
    try:
        product_types: list[str] = await api_get("/configuration/product_types")
    except Exception:
        product_types = ["Payment", "Telco"]

    # ── State ────────────────────────────────────────────────────
    requests_data: list[dict] = []
    table_ref: ui.table | None = None
    state: dict = {
        "status": "All",
        "source": "All",
        "priority": "All",
        "search": "",
    }
    kpi_container: ui.element | None = None
    seg_container: ui.element | None = None

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

    def _count_by_status(rows: list[dict], st: str) -> int:
        return sum(1 for r in rows if (r.get("status") or "") == st)

    def _today_count(rows: list[dict], st: str) -> int:
        today = date.today().isoformat()
        return sum(1 for r in rows
                   if (r.get("status") or "") == st
                   and (r.get("created_at") or "").startswith(today))

    def _high_pri_count(rows: list[dict], st: str) -> int:
        return sum(1 for r in rows
                   if (r.get("status") or "") == st
                   and (r.get("priority") or "") in ("HIGH", "CRITICAL"))

    def _filter_rows() -> list[dict]:
        out = list(requests_data)
        if state["status"] != "All":
            out = [r for r in out if (r.get("status") or "") == state["status"]]
        if state["source"] != "All":
            out = [r for r in out if (r.get("request_source") or "") == state["source"]]
        if state["priority"] != "All":
            out = [r for r in out if (r.get("priority") or "") == state["priority"]]
        q = (state["search"] or "").strip().lower()
        if q:
            out = [r for r in out
                   if q in (r.get("request_number") or "").lower()
                   or q in (r.get("title") or "").lower()
                   or q in (r.get("requester_name") or "").lower()
                   or q in (r.get("external_id") or "").lower()]
        return out

    def _refresh_table():
        rows = _filter_rows()
        for r in rows:
            r["age"] = _format_age(r.get("created_at"))
        if table_ref:
            table_ref.rows = rows
            table_ref.update()

    def _set_status(st: str):
        state["status"] = st
        _render_kpis()
        _render_segments()
        _refresh_table()

    # ─────────────────────────────────────────────────────────────
    # Page body
    # ─────────────────────────────────────────────────────────────
    with ui.column().classes("w-full q-pa-md").style("gap: 0;"):

        # ── Sticky toolbar ─────────────────────────────────────
        with ui.element("div").classes("ed-toolbar"):
            ui.button("Add Request", icon="add",
                      on_click=lambda: add_dialog.open()) \
                .props("flat dense color=primary")
            ui.element("div").classes("ed-toolbar-spacer")
            search_input = ui.input(placeholder="Search number, title, requester…") \
                .props("dense outlined clearable") \
                .style("min-width: 280px;")

            def _on_search(e):
                state["search"] = e.args or ""
                _refresh_table()
            search_input.on("update:model-value", _on_search)

            ui.element("div").classes("ed-toolbar-grow")
            with ui.element("div").classes("ed-status-now"):
                ui.element("span").classes("ed-status-dot")
                _total_label = ui.label("TOTAL · 0").classes("ed-mono")

        with ui.element("div").classes("ed-shell"):

            # Page title
            ui.label("Request Inbox").classes("text-h4 q-mb-md")

            # ── KPI tiles (clickable) ──────────────────────────
            kpi_container = ui.element("div").classes("ed-strip")

            def _stat_tile(label: str, count: int, sub: str, status_key: str) -> None:
                cls = "ed-strip-cell ed-stat-tile"
                if state["status"] == status_key:
                    cls += " active"
                el = ui.element("div").classes(cls)
                el.on("click", lambda _, k=status_key: _set_status(k))
                with el:
                    ui.label(label).classes("ed-eyebrow")
                    ui.label(str(count)).classes("ed-strip-num")
                    if sub:
                        ui.label(sub).classes("ed-stat-tile-sub")

            def _render_kpis():
                kpi_container.clear()
                with kpi_container:
                    n_new = _count_by_status(requests_data, "NEW")
                    n_in  = _count_by_status(requests_data, "IN_ESTIMATION")
                    n_est = _count_by_status(requests_data, "ESTIMATED")
                    n_co  = _count_by_status(requests_data, "COMPLETED")
                    _stat_tile("New",            n_new,
                               f"{_today_count(requests_data, 'NEW')} today" if n_new else "—",
                               "NEW")
                    _stat_tile("In Estimation",  n_in,
                               f"{_high_pri_count(requests_data, 'IN_ESTIMATION')} high priority" if n_in else "—",
                               "IN_ESTIMATION")
                    _stat_tile("Estimated",      n_est,
                               "ready for approval" if n_est else "—",
                               "ESTIMATED")
                    _stat_tile("Completed",      n_co,
                               "archived" if n_co else "—",
                               "COMPLETED")

            # ── Segmented status pills (full set) ──────────────
            seg_container = ui.element("div").classes("ed-segmented")

            def _seg_item(label: str, key: str, count: int) -> None:
                cls = "ed-segmented-item" + (" active" if state["status"] == key else "")
                btn = ui.element("button").classes(cls)
                btn.on("click", lambda _, k=key: _set_status(k))
                with btn:
                    ui.label(label)
                    ui.label(f"· {count}").classes("seg-count")

            def _render_segments():
                seg_container.clear()
                with seg_container:
                    counts = {
                        "All":              len(requests_data),
                        "NEW":              _count_by_status(requests_data, "NEW"),
                        "IN_ESTIMATION":    _count_by_status(requests_data, "IN_ESTIMATION"),
                        "ESTIMATED":        _count_by_status(requests_data, "ESTIMATED"),
                        "COMPLETED":        _count_by_status(requests_data, "COMPLETED"),
                        "REJECTED":         _count_by_status(requests_data, "REJECTED"),
                        "DELETED_UPSTREAM": _count_by_status(requests_data, "DELETED_UPSTREAM"),
                    }
                    _seg_item("All",            "All",              counts["All"])
                    _seg_item("New",            "NEW",              counts["NEW"])
                    _seg_item("In Estimation",  "IN_ESTIMATION",    counts["IN_ESTIMATION"])
                    _seg_item("Estimated",      "ESTIMATED",        counts["ESTIMATED"])
                    _seg_item("Completed",      "COMPLETED",        counts["COMPLETED"])
                    if counts["REJECTED"]:
                        _seg_item("Rejected",   "REJECTED",         counts["REJECTED"])
                    if counts["DELETED_UPSTREAM"]:
                        _seg_item("Deleted",    "DELETED_UPSTREAM", counts["DELETED_UPSTREAM"])

            # ── Source / Priority / Assignee filters ───────────
            with ui.element("div").classes("ed-filter-row"):
                ui.label("Filter").classes("ed-filter-label")

                def _source_change(e):
                    state["source"] = e.args or "All"
                    _refresh_table()
                src_sel = ui.select(label="Source",
                                    options=["All", "JIRA", "REDMINE", "EMAIL", "MANUAL"],
                                    value="All").props("dense outlined").classes("w-40")
                src_sel.on("update:model-value", _source_change)

                def _pri_change(e):
                    state["priority"] = e.args or "All"
                    _refresh_table()
                pri_sel = ui.select(label="Priority",
                                    options=["All", "CRITICAL", "HIGH", "MEDIUM", "LOW"],
                                    value="All").props("dense outlined").classes("w-40")
                pri_sel.on("update:model-value", _pri_change)

            # ── Table ──────────────────────────────────────────
            columns = [
                {"name": "request_number", "label": "Number",   "field": "request_number", "sortable": True, "align": "left"},
                {"name": "source_icon",    "label": "",         "field": "request_source", "align": "center"},
                {"name": "title",          "label": "Title",    "field": "title",          "sortable": True, "align": "left"},
                {"name": "priority",       "label": "Priority", "field": "priority",       "sortable": True, "align": "left"},
                {"name": "status",         "label": "Status",   "field": "status",         "sortable": True, "align": "left"},
                {"name": "requester_name", "label": "Requester","field": "requester_name", "sortable": True, "align": "left"},
                {"name": "assigned",       "label": "Assigned", "field": "assigned_to_name","align": "left"},
                {"name": "age",            "label": "Age",      "field": "age",            "sortable": True, "align": "right"},
                {"name": "actions",        "label": "",         "field": "actions",        "align": "center"},
            ]

            with ui.element("div").classes("ed-card ed-inbox-table"):
                table_ref = ui.table(
                    columns=columns,
                    rows=[],
                    row_key="id",
                    pagination={"rowsPerPage": 25},
                ).classes("w-full").props("flat")

                # Priority stripe rendered as a colored left border on the
                # first visible cell (the request number column).
                table_ref.add_slot("body-cell-request_number", r"""
                    <q-td :props="props" :style="{
                        'box-shadow':
                          (props.row.priority === 'CRITICAL' || props.row.priority === 'HIGH')
                            ? 'inset 3px 0 0 var(--q-negative)' :
                          props.row.priority === 'MEDIUM'
                            ? 'inset 3px 0 0 var(--q-warning)' :
                          props.row.priority === 'LOW'
                            ? 'inset 3px 0 0 var(--q-positive)' : 'none'
                    }">
                        <span class="ed-mono">{{ props.value }}</span>
                    </q-td>
                """)

                table_ref.add_slot("body-cell-source_icon", r"""
                    <q-td :props="props" class="text-center">
                        <q-icon :name="{
                            'JIRA':'integration_instructions','REDMINE':'rss_feed',
                            'EMAIL':'mail','MANUAL':'edit'
                        }[props.value] || 'help_outline'" size="18px" class="text-grey-6" />
                    </q-td>
                """)

                table_ref.add_slot("body-cell-priority", r"""
                    <q-td :props="props">
                        <q-badge outline :color="
                            props.value === 'HIGH' || props.value === 'CRITICAL' ? 'negative' :
                            props.value === 'MEDIUM' ? 'warning' : 'positive'
                        ">{{ props.value }}</q-badge>
                    </q-td>
                """)

                table_ref.add_slot("body-cell-status", r"""
                    <q-td :props="props">
                        <q-badge outline :color="
                            props.value === 'NEW' ? 'info' :
                            props.value === 'IN_ESTIMATION' ? 'warning' :
                            props.value === 'ESTIMATED' || props.value === 'COMPLETED' ? 'positive' :
                            'negative'
                        ">{{ props.value === 'DELETED_UPSTREAM' ? 'Deleted' : props.value }}</q-badge>
                    </q-td>
                """)

                table_ref.add_slot("body-cell-assigned", r"""
                    <q-td :props="props">
                        <span :class="props.value ? '' : 'text-grey'">
                            {{ props.value || 'Unassigned' }}
                        </span>
                    </q-td>
                """)

                table_ref.add_slot("body-cell-age", r"""
                    <q-td :props="props">
                        <span class="ed-mono" style="font-size:11px; opacity:0.7;">{{ props.value }}</span>
                    </q-td>
                """)

                table_ref.add_slot("body-cell-actions", r"""
                    <q-td :props="props" class="text-center">
                        <q-btn flat dense icon="visibility" color="primary"
                            @click="$parent.$emit('view-request', props.row)" />
                    </q-td>
                """)

                table_ref.on("view-request",
                             lambda e: ui.navigate.to(f"/requests/{e.args['id']}"))

    # ─────────────────────────────────────────────────────────────
    # Add Request Dialog (preserved verbatim)
    # ─────────────────────────────────────────────────────────────
    with ui.dialog() as add_dialog, ui.card().classes("w-full max-w-2xl"):
        ui.label("New Request").classes("text-h6")
        ui.separator()

        with ui.grid(columns=2).classes("w-full q-gutter-sm"):
            f_request_number = ui.input("Request Number *").classes("w-full")
            f_request_source = ui.select(
                label="Source",
                options=_SOURCE_OPTIONS,
                value="MANUAL",
            ).classes("w-full")

        f_external_id = ui.input("External ID (optional)").classes("w-full")
        f_title = ui.input("Title *").classes("w-full")
        f_description = ui.textarea("Description").classes("w-full")

        with ui.grid(columns=2).classes("w-full q-gutter-sm"):
            f_requester_name = ui.input("Requester Name *").classes("w-full")
            f_requester_email = ui.input("Requester Email").classes("w-full")

        with ui.grid(columns=2).classes("w-full q-gutter-sm"):
            f_business_unit = ui.input("Business Unit").classes("w-full")
            f_priority = ui.select(
                label="Priority",
                options=_PRIORITY_OPTIONS,
                value="MEDIUM",
            ).classes("w-full")

        f_product_type = ui.select(
            label="Product Type (optional)",
            options=[""] + product_types,
            value="",
            with_input=True,
            clearable=True,
        ).classes("w-full")

        with ui.grid(columns=2).classes("w-full q-gutter-sm"):
            f_requested_delivery_date = ui.date(value=None).classes("w-full")
            with ui.column().classes("w-full"):
                ui.label("Requested Delivery Date").classes("text-caption text-grey")

            f_received_date = ui.date(value=date.today().isoformat()).classes("w-full")
            with ui.column().classes("w-full"):
                ui.label("Received Date").classes("text-caption text-grey")

        f_notes = ui.textarea("Notes").classes("w-full")

        form_error = ui.label("").classes("text-negative text-caption")

        async def submit_add_request() -> None:
            form_error.set_text("")
            missing = []
            if not f_request_number.value:
                missing.append("Request Number")
            if not f_title.value:
                missing.append("Title")
            if not f_requester_name.value:
                missing.append("Requester Name")
            if missing:
                form_error.set_text(f"Required: {', '.join(missing)}")
                return

            payload: dict = {
                "request_number": f_request_number.value.strip(),
                "request_source": f_request_source.value,
                "title": f_title.value.strip(),
                "description": f_description.value.strip() or None,
                "requester_name": f_requester_name.value.strip(),
                "requester_email": f_requester_email.value.strip() or None,
                "business_unit": f_business_unit.value.strip() or None,
                "priority": f_priority.value,
                "notes": f_notes.value.strip() or None,
            }
            if f_external_id.value.strip():
                payload["external_id"] = f_external_id.value.strip()
            if f_requested_delivery_date.value:
                payload["requested_delivery_date"] = f_requested_delivery_date.value
            if f_received_date.value:
                payload["received_date"] = f_received_date.value
            if f_product_type.value:
                payload["product_type"] = f_product_type.value

            try:
                await api_post("/requests", json=payload)
                add_dialog.close()
                ui.notify("Request created successfully.", type="positive")
                await load_requests()
            except Exception as exc:
                ui.notify(f"Error: {exc}", type="negative")

        with ui.row().classes("justify-end q-mt-md"):
            ui.button("Cancel", on_click=add_dialog.close).props("flat")
            ui.button("Create", on_click=submit_add_request).props("color=primary")

    # ─────────────────────────────────────────────────────────────
    # Data loader
    # ─────────────────────────────────────────────────────────────
    async def load_requests() -> None:
        nonlocal requests_data
        try:
            requests_data = await api_get("/requests")
            _total_label.set_text(f"TOTAL · {len(requests_data)}")
            _render_kpis()
            _render_segments()
            _refresh_table()
        except Exception as exc:
            ui.notify(f"Failed to load requests: {exc}", type="negative")

    await load_requests()

# ---------------------------------------------------------------------------
# Route 2: /requests/{id} — Request Detail
# ---------------------------------------------------------------------------


@ui.page("/requests/{request_id}")
async def request_detail_page(request_id: int) -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    with ui.column().classes("q-pa-lg w-full"):

        # ── Load data ────────────────────────────────────────────────────────
        req: dict = {}
        users: list[dict] = []

        try:
            req = await api_get(f"/requests/{request_id}/detail")
        except Exception as exc:
            show_error_page(exc)
            return

        try:
            users = await api_get("/users/assignable")
        except Exception:
            users = []

        # ── Header ───────────────────────────────────────────────────────────
        with ui.row().classes("items-center justify-between w-full"):
            with ui.row().classes("items-center q-gutter-sm"):
                ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/requests")).props("flat round")
                ui.label(f"Request #{req.get('request_number', request_id)}").classes("text-h4")

            with ui.row().classes("q-gutter-sm"):
                ui.button(
                    "Edit",
                    icon="edit",
                    on_click=lambda: edit_dialog.open(),
                ).props("color=primary outline")
                ui.button(
                    "Create Estimation",
                    icon="calculate",
                    on_click=lambda: ui.navigate.to(f"/estimation/new?request_id={request_id}"),
                ).props("color=positive")

        ui.separator()

        # ── Detail card ──────────────────────────────────────────────────────
        with ui.card().classes("w-full q-mb-md"):
            ui.label("Request Details").classes("text-h6 q-mb-sm")

            with ui.grid(columns=3).classes("w-full q-gutter-sm"):
                # Column 1
                with ui.column().classes("q-gutter-xs"):
                    _detail_row("Request Number", req.get("request_number", ""))
                    _detail_row("Source", req.get("request_source", ""))
                    _detail_row("External ID", req.get("external_id") or "—")
                    _detail_row("Business Unit", req.get("business_unit") or "—")

                # Column 2
                with ui.column().classes("q-gutter-xs"):
                    _detail_row("Requester", req.get("requester_name", ""))
                    _detail_row("Email", req.get("requester_email") or "—")
                    _detail_row("Received", _fmt_date(req.get("received_date")))
                    _detail_row("Delivery Requested", _fmt_date(req.get("requested_delivery_date")))

                # Column 3
                with ui.column().classes("q-gutter-xs"):
                    with ui.row().classes("items-center q-gutter-xs"):
                        ui.label("Priority:").classes("text-caption text-grey")
                        priority = req.get("priority", "")
                        ui.badge(priority).props("outline").classes(
                            _PRIORITY_CLASSES.get(priority, "")
                        )
                    with ui.row().classes("items-center q-gutter-xs"):
                        ui.label("Status:").classes("text-caption text-grey")
                        status = req.get("status", "")
                        ui.badge(status).props("outline").classes(
                            _STATUS_CLASSES.get(status, "")
                        )
                    _detail_row("Created", _fmt_date(req.get("created_at")))
                    _detail_row("Updated", _fmt_date(req.get("updated_at")))

            ui.separator().classes("q-my-sm")

            # Title + description full-width
            with ui.column().classes("q-gutter-xs"):
                ui.label("Title").classes("text-caption text-grey")
                ui.label(req.get("title", "")).classes("text-body1")

            if req.get("description"):
                with ui.column().classes("q-gutter-xs q-mt-sm"):
                    ui.label("Description").classes("text-caption text-grey")
                    ui.label(req.get("description", "")).classes("text-body2")

            if req.get("notes"):
                with ui.column().classes("q-gutter-xs q-mt-sm"):
                    ui.label("Notes").classes("text-caption text-grey")
                    ui.label(req.get("notes", "")).classes("text-body2 text-italic")

        # ── Attachments ──────────────────────────────────────────────────────
        raw_attachments = req.get("attachments_json") or "[]"
        try:
            attachments: list[dict] = json.loads(raw_attachments) if isinstance(raw_attachments, str) else raw_attachments
        except (json.JSONDecodeError, TypeError):
            attachments = []

        with ui.card().classes("w-full q-mb-md"):
            ui.label("Attachments").classes("text-h6 q-mb-sm")
            if attachments:
                with ui.list().props("bordered separator").classes("w-full"):
                    for att in attachments:
                        with ui.item():
                            with ui.item_section().props("avatar"):
                                ui.icon("attach_file").classes("text-grey")
                            with ui.item_section():
                                ui.item_label(att.get("filename", "unknown"))
                                meta_parts = []
                                if att.get("mime_type"):
                                    meta_parts.append(att["mime_type"])
                                if att.get("file_size_bytes"):
                                    size_kb = round(att["file_size_bytes"] / 1024, 1)
                                    meta_parts.append(f"{size_kb} KB")
                                if att.get("uploaded_at"):
                                    meta_parts.append(_fmt_date(att["uploaded_at"]))
                                ui.item_label(", ".join(meta_parts)).props("caption")
                            if att.get("external_url"):
                                with ui.item_section().props("side"):
                                    ui.button(
                                        icon="open_in_new",
                                        on_click=lambda url=att["external_url"]: ui.navigate.to(url),
                                    ).props("flat round dense")
            else:
                ui.label("No attachments.").classes("text-grey")

        # ── Assignment ───────────────────────────────────────────────────────
        with ui.card().classes("w-full q-mb-md"):
            ui.label("Assignment").classes("text-h6 q-mb-sm")

            user_options: dict[int, str] = {
                u["id"]: f"{u.get('display_name') or u.get('username', '')} ({u.get('role', '')})"
                for u in users
            }
            current_assigned_id: int | None = req.get("assigned_to_id")

            with ui.row().classes("items-center q-gutter-sm"):
                assign_select = ui.select(
                    label="Assign to",
                    options=user_options,
                    value=current_assigned_id,
                    with_input=True,
                ).classes("w-72")

                async def do_assign() -> None:
                    selected_id = assign_select.value
                    if not selected_id:
                        ui.notify("Please select a user.", type="warning")
                        return
                    try:
                        # /requests/{id}/assign takes assigned_to_id as a query param
                        async with httpx.AsyncClient() as client:
                            r = await client.post(
                                f"{API_URL}/requests/{request_id}/assign",
                                headers=auth_headers(),
                                params={"assigned_to_id": selected_id},
                            )
                            r.raise_for_status()
                        ui.notify("Request assigned successfully.", type="positive")
                    except Exception as exc:
                        ui.notify(f"Assignment failed: {exc}", type="negative")

                ui.button("Assign", icon="person_add", on_click=do_assign).props("color=primary")

        # ── Linked estimations ───────────────────────────────────────────────
        with ui.card().classes("w-full q-mb-md"):
            ui.label("Linked Estimations").classes("text-h6 q-mb-sm")

            estimations: list[dict] = req.get("estimations") or []
            if estimations:
                est_columns = [
                    {"name": "id",                "label": "ID",           "field": "id",                "sortable": True, "align": "left"},
                    {"name": "project_name",      "label": "Project",      "field": "project_name",      "sortable": True, "align": "left"},
                    {"name": "project_type",      "label": "Type",         "field": "project_type",      "sortable": True, "align": "left"},
                    {"name": "grand_total_hours",  "label": "Total Hours",  "field": "grand_total_hours", "sortable": True, "align": "right"},
                    {"name": "feasibility_status", "label": "Feasibility",  "field": "feasibility_status","sortable": True, "align": "left"},
                    {"name": "status",            "label": "Status",       "field": "status",            "sortable": True, "align": "left"},
                    {"name": "created_at",        "label": "Created",      "field": "created_at",        "sortable": True, "align": "left"},
                    {"name": "actions",           "label": "Actions",      "field": "actions",           "sortable": False,"align": "center"},
                ]

                est_table = ui.table(
                    columns=est_columns,
                    rows=estimations,
                    row_key="id",
                    pagination={"rowsPerPage": 15},
                ).classes("w-full")

                est_table.add_slot("body-cell-feasibility_status", """
                    <q-td :props="props">
                        <q-badge outline :color="
                            props.value === 'FEASIBLE' ? 'positive' :
                            props.value === 'AT_RISK' ? 'warning' : 'negative'
                        ">{{ props.value }}</q-badge>
                    </q-td>
                """)

                est_table.add_slot("body-cell-created_at", """
                    <q-td :props="props">{{ props.value ? props.value.slice(0, 10) : '' }}</q-td>
                """)

                est_table.add_slot("body-cell-actions", """
                    <q-td :props="props" class="text-center">
                        <q-btn flat dense icon="visibility" color="primary"
                            @click="$parent.$emit('view-estimation', props.row)" />
                    </q-td>
                """)

                est_table.on("view-estimation", lambda e: ui.navigate.to(f"/estimation/{e.args['id']}"))
            else:
                with ui.row().classes("items-center q-gutter-sm"):
                    ui.label("No estimations linked to this request yet.").classes("text-grey")
                    ui.button(
                        "Create Estimation",
                        icon="add",
                        on_click=lambda: ui.navigate.to(f"/estimation/new?request_id={request_id}"),
                    ).props("flat color=primary")

    # ── Edit Dialog ──────────────────────────────────────────────────────────
    with ui.dialog() as edit_dialog, ui.card().classes("w-full max-w-2xl"):
        ui.label("Edit Request").classes("text-h6")
        ui.separator()

        e_title = ui.input("Title *", value=req.get("title", "")).classes("w-full")
        e_description = ui.textarea("Description", value=req.get("description") or "").classes("w-full")

        with ui.grid(columns=2).classes("w-full q-gutter-sm"):
            e_priority = ui.select(
                label="Priority",
                options=_PRIORITY_OPTIONS,
                value=req.get("priority", "MEDIUM"),
            ).classes("w-full")
            e_status = ui.select(
                label="Status",
                options=["NEW", "IN_ESTIMATION", "ESTIMATED", "COMPLETED", "REJECTED"],
                value=req.get("status", "NEW"),
            ).classes("w-full")

        e_notes = ui.textarea("Notes", value=req.get("notes") or "").classes("w-full")

        edit_error = ui.label("").classes("text-negative text-caption")

        async def submit_edit_request() -> None:
            edit_error.set_text("")
            if not e_title.value.strip():
                edit_error.set_text("Title is required.")
                return

            payload: dict = {
                "title": e_title.value.strip(),
                "description": e_description.value.strip() or None,
                "priority": e_priority.value,
                "status": e_status.value,
                "notes": e_notes.value.strip() or None,
            }

            try:
                await api_put(f"/requests/{request_id}", json=payload)
                edit_dialog.close()
                ui.notify("Request updated. Refreshing…", type="positive")
                # Reload the page to reflect new values
                ui.navigate.to(f"/requests/{request_id}")
            except Exception as exc:
                ui.notify(f"Update failed: {exc}", type="negative")

        with ui.row().classes("justify-end q-mt-md"):
            ui.button("Cancel", on_click=edit_dialog.close).props("flat")
            ui.button("Save", on_click=submit_edit_request).props("color=primary")


# ---------------------------------------------------------------------------
# Internal helper — labelled read-only field
# ---------------------------------------------------------------------------


def _detail_row(label: str, value: str) -> None:
    """Render a small labelled read-only field."""
    with ui.column().classes("q-gutter-none"):
        ui.label(label).classes("text-caption text-grey")
        ui.label(str(value) if value else "—").classes("text-body2")
