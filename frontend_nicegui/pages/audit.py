"""Audit Log page — read-only view with filter controls.

Accessible to APPROVER and ADMIN roles (enforced server-side by the API).
The frontend shows an access-denied message for VIEWER/ESTIMATOR roles before
even calling the API, avoiding a misleading 403 error in the notification area.

Route: /audit
API:
  GET /audit-log?limit=50&offset=0&action=...&resource_type=...
"""

from nicegui import ui

from frontend_nicegui.app import (
    api_get,
    current_user,
    empty_state,
    format_age,
    format_datetime,
    is_authenticated,
    loading_state,
    sidebar,
)

_ALLOWED_ROLES = {"APPROVER", "ADMIN"}


@ui.page("/audit")
async def audit_page() -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    # ---------------------------------------------------------------------------
    # Role check — show informative message rather than a raw API 403
    # ---------------------------------------------------------------------------
    user = current_user()
    role = user.get("role", "VIEWER") if user else "VIEWER"

    # ── State ────────────────────────────────────────────────────
    logs: list[dict] = []
    state: dict = {"filter_action": "All"}

    with ui.column().classes("w-full q-pa-md").style("gap: 0;"):

        # ── Sticky toolbar ──────────────────────────────────────
        with ui.element("div").classes("ed-toolbar"):
            ui.button("Refresh", icon="refresh",
                      on_click=lambda: do_refresh()) \
                .props("flat dense color=primary")
            ui.element("div").classes("ed-toolbar-grow")
            with ui.element("div").classes("ed-status-now"):
                ui.element("span").classes("ed-status-dot")
                _total_label = ui.label("LOADED · 0").classes("ed-mono")

        with ui.element("div").classes("ed-shell"):

            ui.label("Audit Log").classes("text-h4 q-mb-md")

            if role not in _ALLOWED_ROLES:
                with ui.element("div").classes("ed-card") \
                        .style("border-color: var(--q-warning);"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("lock", size="lg").classes("text-warning")
                        ui.label(
                            "Access restricted. APPROVER or ADMIN role required to view the audit log."
                        ).classes("text-subtitle1 text-warning")
                return

            kpi_container = ui.element("div").classes("ed-strip")
            seg_container = ui.element("div").classes("ed-segmented")

            # ── Filter row (input filters sent to API) ─────────
            with ui.element("div").classes("ed-filter-row"):
                ui.label("Filter").classes("ed-filter-label")
                f_action = ui.input(
                    placeholder="Action (e.g. CREATE, DELETE)…",
                ).props("dense outlined clearable").classes("flex-1")
                f_resource = ui.input(
                    placeholder="Resource type (e.g. user, estimation)…",
                ).props("dense outlined clearable").classes("flex-1")
                f_limit = ui.number(
                    label="Limit", value=50, min=1, max=500, step=10, format="%.0f",
                ).props("dense outlined").classes("w-28")

            # ── Table ──────────────────────────────────────────
            table_container = ui.element("div").classes("ed-card")

        # ---------------------------------------------------------------------------
        # Data helpers
        # ---------------------------------------------------------------------------
        async def load_logs() -> None:
            nonlocal logs
            params: dict = {"limit": int(f_limit.value or 50), "offset": 0}
            action_val = (f_action.value or "").strip()
            resource_val = (f_resource.value or "").strip()
            if action_val:
                params["action"] = action_val
            if resource_val:
                params["resource_type"] = resource_val
            try:
                data = await api_get("/audit-log", params=params)
                logs = data if isinstance(data, list) else []
                for row in logs:
                    iso = row.get("created_at") or ""
                    row["created_at_age"] = format_age(iso) if iso else "—"
                    row["created_at_full"] = format_datetime(iso) if iso else ""
            except Exception as exc:
                ui.notify(f"Failed to load audit log: {exc}", type="negative")
                logs = []

        # ── KPI / segment helpers ──────────────────────────────
        from collections import Counter

        def _set_action(a: str) -> None:
            state["filter_action"] = a
            _render_kpis()
            _render_segments()
            render_table()

        def _filtered_logs() -> list[dict]:
            a = state["filter_action"]
            if a == "All":
                return logs
            if a == "CHANGE":
                return [
                    l for l in logs
                    if (l.get("action") or "") not in ("CREATE", "UPDATE", "DELETE",
                                                       "LOGIN", "LOGOUT", "LOGIN_FAILED")
                ]
            return [l for l in logs if (l.get("action") or "") == a]

        def _render_kpis() -> None:
            kpi_container.clear()
            with kpi_container:
                _total_label.set_text(f"LOADED · {len(logs)}")
                action_counts = Counter(l.get("action", "") for l in logs)
                fail_n = action_counts.get("LOGIN_FAILED", 0)
                login_n = action_counts.get("LOGIN", 0)
                user_n = len({l.get("username") for l in logs if l.get("username")})

                def _tile(label: str, value: str, sub: str, key: str | None = None) -> None:
                    cls = "ed-strip-cell ed-stat-tile"
                    if key and state["filter_action"] == key:
                        cls += " active"
                    el = ui.element("div").classes(cls)
                    if key is not None:
                        el.on("click", lambda _, k=key: _set_action(k))
                    with el:
                        ui.label(label).classes("ed-eyebrow")
                        ui.label(value).classes("ed-strip-num")
                        if sub:
                            ui.label(sub).classes("ed-stat-tile-sub")

                _tile("Total Entries", str(len(logs)),
                      f"{user_n} unique user{'s' if user_n != 1 else ''}",
                      key="All")
                if login_n:
                    _tile("Logins", str(login_n),
                          "successful sign-ins", key="LOGIN")
                if fail_n:
                    _tile("Failed Logins", str(fail_n),
                          "auth attempts denied", key="LOGIN_FAILED")
                # Most active action besides login
                top = [(a, n) for a, n in action_counts.most_common(8)
                       if a not in ("LOGIN", "LOGOUT", "LOGIN_FAILED")][:1]
                for action_name, n in top:
                    _tile(action_name.title(), str(n),
                          "filter to action", key=action_name)

        _ACTION_PILLS = [
            ("All", "All"),
            ("Create", "CREATE"),
            ("Update", "UPDATE"),
            ("Delete", "DELETE"),
            ("Login", "LOGIN"),
            ("Failed Login", "LOGIN_FAILED"),
            ("Backup/Restore", "CHANGE"),
        ]

        def _render_segments() -> None:
            seg_container.clear()
            action_counts = Counter(l.get("action", "") for l in logs)
            with seg_container:
                def _seg(label: str, key: str, count: int) -> None:
                    cls = "ed-segmented-item" + (
                        " active" if state["filter_action"] == key else "")
                    btn = ui.element("button").classes(cls)
                    btn.on("click", lambda _, k=key: _set_action(k))
                    with btn:
                        ui.label(label)
                        ui.label(f"· {count}").classes("seg-count")
                # Always show All
                _seg("All", "All", len(logs))
                for label, key in _ACTION_PILLS[1:]:
                    if key == "CHANGE":
                        n = sum(1 for l in logs
                                if (l.get("action") or "") not in
                                ("CREATE", "UPDATE", "DELETE",
                                 "LOGIN", "LOGOUT", "LOGIN_FAILED"))
                    else:
                        n = action_counts.get(key, 0)
                    if n or key == state["filter_action"]:
                        _seg(label, key, n)

        def render_table() -> None:
            table_container.clear()
            with table_container:
                rows = _filtered_logs()
                with ui.element("div").classes("ed-card-head"):
                    ui.label("Entries").classes("ed-cap")
                    ui.label(
                        f"{len(rows)} of {len(logs)} loaded · "
                        f"showing latest first"
                    ).classes("ed-card-head-meta")

                if not rows:
                    empty_state("No audit entries match the current filters")
                    return

                columns = [
                    {"name": "username", "label": "User", "field": "username", "sortable": True, "align": "left"},
                    {"name": "action", "label": "Action", "field": "action", "sortable": True, "align": "left"},
                    {"name": "resource_type", "label": "Resource Type", "field": "resource_type", "sortable": True, "align": "left"},
                    {"name": "resource_id", "label": "Res ID", "field": "resource_id", "sortable": True, "align": "right"},
                    {"name": "ip_address", "label": "IP Address", "field": "ip_address", "align": "left"},
                    {"name": "created_at", "label": "Timestamp", "field": "created_at_age", "sortable": True, "align": "left"},
                ]

                t = ui.table(
                    columns=columns,
                    rows=rows,
                    row_key="id",
                    pagination={"rowsPerPage": 25},
                ).classes("w-full").props("flat")

                # Color-code action column
                t.add_slot(
                    "body-cell-action",
                    r"""
                    <q-td :props="props">
                        <q-badge
                            :color="props.value === 'DELETE' ? 'negative'
                                   : props.value === 'CREATE' ? 'positive'
                                   : props.value === 'UPDATE' ? 'warning'
                                   : 'grey'"
                            :label="props.value"
                        />
                    </q-td>
                    """,
                )

                # Relative age with full timestamp on hover
                t.add_slot(
                    "body-cell-created_at",
                    r"""
                    <q-td :props="props">
                        <span class="text-caption">{{ props.value }}</span>
                        <q-tooltip v-if="props.row.created_at_full">
                            {{ props.row.created_at_full }}
                        </q-tooltip>
                    </q-td>
                    """,
                )

                # Show dash for null values in resource columns
                t.add_slot(
                    "body-cell-resource_id",
                    r"""
                    <q-td :props="props">
                        {{ props.value !== null && props.value !== undefined ? props.value : '—' }}
                    </q-td>
                    """,
                )

                t.add_slot(
                    "body-cell-ip_address",
                    r"""
                    <q-td :props="props">
                        <span class="text-caption text-grey">
                            {{ props.value || '—' }}
                        </span>
                    </q-td>
                    """,
                )

                ui.label(f"Showing {len(logs)} entries.").classes(
                    "text-caption text-grey q-mt-sm"
                )

        async def do_refresh() -> None:
            await load_logs()
            _render_kpis()
            _render_segments()
            render_table()

        # Wire up filter inputs to auto-refresh on change
        f_action.on("update:model-value", lambda _: do_refresh())
        f_resource.on("update:model-value", lambda _: do_refresh())
        f_limit.on("update:model-value", lambda _: do_refresh())

        # Initial load
        async with loading_state("Loading audit log…"):
            await load_logs()
        _render_kpis()
        _render_segments()
        render_table()
