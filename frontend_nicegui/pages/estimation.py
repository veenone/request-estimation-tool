"""Estimation pages — list, 7-step wizard, detail view, and edit.

Routes:
  /estimations            — Estimation list with search and filters
  /estimation/new         — Wizard to create a new estimation
  /estimation/{id}        — Read-only detail view with status controls and report downloads
  /estimation/{id}/edit   — Edit wizard for REVISED estimations
"""

import asyncio
import json as _json
from typing import Any

import httpx

from nicegui import ui

from frontend_nicegui.app import (
    API_URL,
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
# Shared helpers
# ---------------------------------------------------------------------------

_FEASIBILITY_COLOR: dict[str, str] = {
    "FEASIBLE": "positive",
    "AT_RISK": "warning",
    "NOT_FEASIBLE": "negative",
}

_STATUS_COLOR: dict[str, str] = {
    "DRAFT": "grey",
    "FINAL": "primary",
    "APPROVED": "positive",
    "REVISED": "orange",
}

# Valid status transitions as defined in the backend
_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "DRAFT": ["FINAL", "REVISED"],
    "FINAL": ["APPROVED", "REVISED"],
    "APPROVED": ["REVISED"],
    "REVISED": ["DRAFT"],
}


def _feasibility_badge(status: str) -> None:
    """Render a colored q-badge for a feasibility status string."""
    color = _FEASIBILITY_COLOR.get(status, "grey")
    ui.badge(status, color=color).props("rounded")


def _status_badge(status: str) -> None:
    """Render a colored q-badge for an estimation workflow status string."""
    color = _STATUS_COLOR.get(status, "grey")
    ui.badge(status, color=color).props("rounded")


def _hours_card(label: str, value: float, icon: str = "schedule") -> None:
    """Render a compact metric card."""
    with ui.card().classes("q-pa-sm text-center"):
        ui.icon(icon).classes("text-h5 text-primary")
        ui.label(f"{value:,.1f}").classes("text-h6")
        ui.label(label).classes("text-caption text-grey")


# ---------------------------------------------------------------------------
# Route 0: /estimations  — Estimation list page
# ---------------------------------------------------------------------------

@ui.page("/estimations")
async def estimations_list_page() -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    with ui.column().classes("q-pa-lg w-full"):
        with ui.row().classes("items-center q-gutter-md q-mb-md w-full"):
            ui.label("Estimations").classes("text-h4")
            ui.space()
            ui.button(
                "New Estimation",
                icon="add",
                on_click=lambda: ui.navigate.to("/estimation/new"),
            ).props("color=primary")

        # Load estimations
        try:
            estimations: list[dict] = await api_get("/estimations")
        except Exception as exc:
            show_error_page(exc)
            return

        if not estimations:
            ui.label("No estimations found. Create your first estimation to get started.").classes("text-grey")
            return

        # Filters
        search_input = ui.input("Search by project name", placeholder="Type to filter...").classes("w-64")
        status_filter = ui.select(
            options=["All", "DRAFT", "FINAL", "APPROVED", "REVISED"],
            value="All",
            label="Status",
        ).classes("w-40")

        # Table
        def _version_label(est: dict) -> str:
            v = est.get("version", 1) or 1
            num = est.get("estimation_number") or f"EST-{est['id']}"
            return f"{num} (v{v})" if v > 1 else num

        table_container = ui.column().classes("w-full q-mt-md")

        def _render_table() -> None:
            table_container.clear()
            query = (search_input.value or "").strip().lower()
            status_val = status_filter.value

            filtered = estimations
            if query:
                filtered = [e for e in filtered if query in (e.get("project_name") or "").lower()]
            if status_val and status_val != "All":
                filtered = [e for e in filtered if e.get("status") == status_val]

            rows = []
            for e in filtered:
                rows.append({
                    "id": e["id"],
                    "number": _version_label(e),
                    "project_name": e.get("project_name", ""),
                    "project_type": e.get("project_type", ""),
                    "grand_total_hours": round(e.get("grand_total_hours", 0), 1),
                    "feasibility_status": e.get("feasibility_status", ""),
                    "status": e.get("status", ""),
                    "assigned_to_name": e.get("assigned_to_name") or "Unassigned",
                    "created_at": (str(e.get("created_at") or ""))[:10],
                })

            cols = [
                {"name": "number", "label": "#", "field": "number", "align": "left", "sortable": True},
                {"name": "project_name", "label": "Project", "field": "project_name", "align": "left", "sortable": True},
                {"name": "project_type", "label": "Type", "field": "project_type", "align": "left", "sortable": True},
                {"name": "grand_total_hours", "label": "Total Hours", "field": "grand_total_hours", "align": "right", "sortable": True},
                {"name": "feasibility_status", "label": "Feasibility", "field": "feasibility_status", "align": "center"},
                {"name": "status", "label": "Status", "field": "status", "align": "center"},
                {"name": "assigned_to_name", "label": "Assigned To", "field": "assigned_to_name", "align": "left"},
                {"name": "created_at", "label": "Created", "field": "created_at", "align": "left", "sortable": True},
            ]

            with table_container:
                if not rows:
                    ui.label("No estimations match the current filters.").classes("text-grey")
                    return

                tbl = ui.table(
                    columns=cols,
                    rows=rows,
                    row_key="id",
                    pagination={"rowsPerPage": 20},
                ).classes("w-full shadow-1")

                # Feasibility badge slot
                tbl.add_slot(
                    "body-cell-feasibility_status",
                    r"""
                    <q-td :props="props">
                        <q-badge
                            :color="props.value === 'FEASIBLE' ? 'positive' : props.value === 'AT_RISK' ? 'warning' : 'negative'"
                            :label="props.value"
                            rounded
                        />
                    </q-td>
                    """,
                )

                # Status badge slot
                tbl.add_slot(
                    "body-cell-status",
                    r"""
                    <q-td :props="props">
                        <q-badge
                            :color="props.value === 'DRAFT' ? 'grey' : props.value === 'FINAL' ? 'primary' : props.value === 'APPROVED' ? 'positive' : 'orange'"
                            :label="props.value"
                            rounded
                        />
                    </q-td>
                    """,
                )

                tbl.on("rowClick", lambda e: ui.navigate.to(f"/estimation/{e.args[1]['id']}"))

        search_input.on("update:model-value", lambda _: _render_table())
        status_filter.on("update:model-value", lambda _: _render_table())
        _render_table()


# ---------------------------------------------------------------------------
# Route 1: /estimation/new  — 7-step wizard
# ---------------------------------------------------------------------------

@ui.page("/estimation/new")
async def new_estimation_page(request_id: str | None = None) -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    # Read optional query param (?request_id=123)
    linked_request_id: int | None = int(request_id) if request_id else None

    # ------------------------------------------------------------------ #
    # Wizard state — single dict keeps all inter-step data together       #
    # ------------------------------------------------------------------ #
    state: dict[str, Any] = {
        # Step 1
        "project_name": "",
        "project_type": "EVOLUTION",
        "description": "",
        # Step 2
        "feature_ids": [],
        "new_feature_ids": [],
        # Step 3
        "reference_project_ids": [],
        # Step 4
        "dut_ids": [],
        "profile_ids": [],
        "dut_profile_matrix": [],
        # Step 5
        "pr_simple": 0,
        "pr_medium": 0,
        "pr_complex": 0,
        "pr_details": [],
        # Step 6
        "start_date": None,
        "delivery_date": None,
        "working_days": 20,
        "team_size": 1,
        "has_leader": False,
        "team_allocations": [],
        # Step 7 (calculation result)
        "calc_result": None,
    }

    # Pre-load catalog data in parallel so later steps can render immediately.
    # Auth headers are captured BEFORE asyncio.gather to avoid context-propagation
    # issues: each coroutine spawned by gather gets a copy of the current context,
    # but NiceGUI's app.storage.user relies on request_contextvar which may not
    # survive the copy correctly in all environments.  By pre-capturing the headers
    # here (in the original request context) and closing over them in _safe_get we
    # guarantee every API call is authenticated.
    _catalog_headers = auth_headers()

    async def _safe_get(path: str) -> list[dict]:
        try:
            async with httpx.AsyncClient() as _client:
                _r = await _client.get(
                    f"{API_URL}{path}", headers=_catalog_headers
                )
                _r.raise_for_status()
                return _r.json()
        except Exception:
            return []

    all_features, all_duts, all_profiles, all_hist, all_team_members = await asyncio.gather(
        _safe_get("/features"),
        _safe_get("/dut-types"),
        _safe_get("/profiles"),
        _safe_get("/historical-projects"),
        _safe_get("/team-members"),
    )

    # ------------------------------------------------------------------ #
    # Page title                                                           #
    # ------------------------------------------------------------------ #
    with ui.column().classes("q-pa-lg w-full"):
        ui.label("New Estimation — 7-Step Wizard").classes("text-h4 q-mb-md")

        if linked_request_id is not None:
            ui.label(f"Linked to Request ID: {linked_request_id}").classes(
                "text-caption text-primary q-mb-sm"
            )

        # -------------------------------------------------------------- #
        # Stepper                                                          #
        # -------------------------------------------------------------- #
        with ui.stepper().props("vertical=false animated").classes("w-full") as stepper:

            # ---------------------------------------------------------- #
            # Step 1 — Project Info                                       #
            # ---------------------------------------------------------- #
            with ui.step("Project Info"):
                ui.label("Enter the basic project details.").classes(
                    "text-body2 text-grey q-mb-md"
                )

                name_input = ui.input(
                    "Project Name *",
                    value=state["project_name"],
                    placeholder="e.g. SIM Toolkit v2.1 Regression",
                ).classes("w-full")
                name_input.on(
                    "update:model-value",
                    lambda e: state.update({"project_name": e.args}),
                )

                type_select = ui.select(
                    options=["NEW", "EVOLUTION", "SUPPORT"],
                    label="Project Type",
                    value=state["project_type"],
                ).classes("w-full q-mt-sm")
                type_select.on(
                    "update:model-value",
                    lambda e: state.update({"project_type": e.args}),
                )

                desc_input = ui.textarea(
                    "Description (optional)",
                    value=state["description"],
                    placeholder="Briefly describe the scope or context.",
                ).classes("w-full q-mt-sm")
                desc_input.on(
                    "update:model-value",
                    lambda e: state.update({"description": e.args}),
                )

                with ui.stepper_navigation():
                    def _go_step2() -> None:
                        state["project_name"] = name_input.value or ""
                        state["project_type"] = type_select.value or "EVOLUTION"
                        state["description"] = desc_input.value or ""
                        if not state["project_name"].strip():
                            ui.notify("Project Name is required.", type="warning")
                            return
                        stepper.next()

                    ui.button("Next", on_click=_go_step2).props("color=primary icon-right=arrow_forward")

            # ---------------------------------------------------------- #
            # Step 2 — Features                                           #
            # ---------------------------------------------------------- #
            with ui.step("Features"):
                ui.label(
                    "Select the features under test. Toggle 'New' for features that require study time."
                ).classes("text-body2 text-grey q-mb-md")

                # Group features by category
                features_by_cat: dict[str, list[dict]] = {}
                for feat in all_features:
                    cat = feat.get("category") or "Other"
                    features_by_cat.setdefault(cat, []).append(feat)

                # We need checkbox refs to read values on navigation
                feature_checkbox_refs: dict[int, ui.checkbox] = {}
                new_feat_checkbox_refs: dict[int, ui.checkbox] = {}

                if not all_features:
                    ui.label("No features found. Add features in the Feature Catalog first.").classes(
                        "text-warning"
                    )
                else:
                    # -- Select All checkbox --
                    _programmatic_select_all = [False]
                    all_pre_selected = all(f["id"] in state["feature_ids"] for f in all_features)
                    select_all_cb = ui.checkbox(
                        f"Select all ({len(all_features)} features)",
                        value=all_pre_selected,
                    ).classes("text-weight-bold q-mb-sm")

                    def _toggle_select_all(e):
                        if _programmatic_select_all[0]:
                            return
                        checked = e.value
                        for _fid, _cb in feature_checkbox_refs.items():
                            _cb.value = checked
                            if not checked and _fid in new_feat_checkbox_refs:
                                new_feat_checkbox_refs[_fid].value = False

                    select_all_cb.on_value_change(_toggle_select_all)

                    def _update_select_all_state() -> None:
                        """Sync Select All checkbox when an individual feature is toggled."""
                        all_checked = all(cb.value for cb in feature_checkbox_refs.values())
                        if select_all_cb.value != all_checked:
                            _programmatic_select_all[0] = True
                            select_all_cb.value = all_checked
                            _programmatic_select_all[0] = False

                    ui.separator()

                    for cat_name, cat_features in features_by_cat.items():
                        ui.label(cat_name).classes("text-subtitle2 q-mt-sm text-primary")

                        # Column headers
                        with ui.grid(columns="1fr 100px 110px").classes("w-full q-pl-md items-center"):
                            ui.label("Feature").classes("text-caption text-grey")
                            ui.label("Complexity").classes("text-caption text-grey text-center")
                            ui.label("New?").classes("text-caption text-grey text-center")

                            for feat in cat_features:
                                fid = feat["id"]
                                fname = feat.get("name", f"Feature {fid}")
                                fweight = feat.get("complexity_weight", 1.0)
                                has_tests = feat.get("has_existing_tests", False)

                                cb = ui.checkbox(
                                    fname,
                                    value=(fid in state["feature_ids"]),
                                )
                                feature_checkbox_refs[fid] = cb

                                ui.label(f"x{fweight:.1f}").classes("text-center")

                                new_cb = ui.checkbox(
                                    "New",
                                    value=(fid in state["new_feature_ids"]),
                                ).props("dense color=orange").classes("text-caption")
                                new_feat_checkbox_refs[fid] = new_cb

                                # Disable "New" toggle unless parent is checked
                                def _make_sync(f_id: int, n_cb: ui.checkbox):
                                    def _sync(e) -> None:
                                        if not feature_checkbox_refs[f_id].value:
                                            n_cb.value = False
                                        _update_select_all_state()

                                    return _sync

                                cb.on("update:model-value", _make_sync(fid, new_cb))

                def _collect_features() -> None:
                    state["feature_ids"] = [
                        fid for fid, cb in feature_checkbox_refs.items() if cb.value
                    ]
                    state["new_feature_ids"] = [
                        fid
                        for fid, cb in new_feat_checkbox_refs.items()
                        if cb.value and feature_checkbox_refs[fid].value
                    ]

                with ui.stepper_navigation():
                    def _back_step2() -> None:
                        _collect_features()
                        stepper.previous()

                    def _next_step2() -> None:
                        _collect_features()
                        if not state["feature_ids"]:
                            ui.notify(
                                "Select at least one feature to continue.",
                                type="warning",
                            )
                            return
                        stepper.next()

                    ui.button("Back", on_click=_back_step2).props("flat")
                    ui.button("Next", on_click=_next_step2).props(
                        "color=primary icon-right=arrow_forward"
                    )

            # ---------------------------------------------------------- #
            # Step 3 — Reference Projects                                 #
            # ---------------------------------------------------------- #
            with ui.step("Reference Projects"):
                ui.label(
                    "Pick historical projects to use as baselines for calibration (optional)."
                ).classes("text-body2 text-grey q-mb-md")

                ref_checkbox_refs: dict[int, ui.checkbox] = {}

                if not all_hist:
                    ui.label("No historical projects available.").classes("text-grey")
                else:
                    with ui.grid(columns=1).classes("w-full"):
                        for proj in all_hist:
                            pid = proj["id"]
                            pname = proj.get("project_name", f"Project {pid}")
                            est_h = proj.get("estimated_hours") or 0
                            act_h = proj.get("actual_hours") or 0
                            accuracy = (act_h / est_h) if est_h else None
                            acc_txt = (
                                f"  accuracy ratio: {accuracy:.2f}"
                                if accuracy is not None
                                else "  (no accuracy data)"
                            )
                            label = f"{pname}  [{proj.get('project_type', '')}]{acc_txt}"
                            cb = ui.checkbox(
                                label,
                                value=(pid in state["reference_project_ids"]),
                            )
                            ref_checkbox_refs[pid] = cb

                def _collect_refs() -> None:
                    state["reference_project_ids"] = [
                        pid for pid, cb in ref_checkbox_refs.items() if cb.value
                    ]

                with ui.stepper_navigation():
                    def _back_step3() -> None:
                        _collect_refs()
                        stepper.previous()

                    def _next_step3() -> None:
                        _collect_refs()
                        stepper.next()

                    ui.button("Back", on_click=_back_step3).props("flat")
                    ui.button("Next", on_click=_next_step3).props(
                        "color=primary icon-right=arrow_forward"
                    )

            # ---------------------------------------------------------- #
            # Step 4 — DUT x Profile Matrix                               #
            # ---------------------------------------------------------- #
            with ui.step("DUT x Profile Matrix"):
                ui.label(
                    "Select the DUTs and Profiles to test, then tick the combinations you actually need."
                ).classes("text-body2 text-grey q-mb-md")

                dut_cb_refs: dict[int, ui.checkbox] = {}
                prof_cb_refs: dict[int, ui.checkbox] = {}
                matrix_cb_refs: dict[tuple[int, int], ui.checkbox] = {}
                matrix_container = ui.column().classes("w-full q-mt-md")

                def _rebuild_matrix() -> None:
                    """Repaint the DUT×Profile combination grid."""
                    matrix_container.clear()
                    sel_duts = [
                        d for d in all_duts if dut_cb_refs.get(d["id"]) and dut_cb_refs[d["id"]].value
                    ]
                    sel_profs = [
                        p for p in all_profiles if prof_cb_refs.get(p["id"]) and prof_cb_refs[p["id"]].value
                    ]
                    matrix_cb_refs.clear()

                    if not sel_duts or not sel_profs:
                        with matrix_container:
                            ui.label("Select at least one DUT and one Profile to see the matrix.").classes(
                                "text-grey text-caption"
                            )
                        return

                    with matrix_container:
                        ui.label("Combination Matrix").classes("text-subtitle2 q-mb-sm")
                        n_cols = len(sel_profs) + 1
                        with ui.grid(columns=n_cols).classes("w-full items-center"):
                            # Header row
                            ui.label("DUT \\ Profile").classes(
                                "text-caption text-grey text-weight-bold"
                            )
                            for prof in sel_profs:
                                ui.label(prof.get("name", f"P{prof['id']}")).classes(
                                    "text-caption text-center text-weight-bold"
                                )

                            # Data rows
                            for dut in sel_duts:
                                ui.label(dut.get("name", f"D{dut['id']}")).classes(
                                    "text-caption"
                                )
                                for prof in sel_profs:
                                    key = (dut["id"], prof["id"])
                                    pre_checked = key in [
                                        tuple(pair)
                                        for pair in state["dut_profile_matrix"]
                                    ]
                                    with ui.column().classes("items-center justify-center"):
                                        cb = ui.checkbox("", value=pre_checked).props(
                                            "dense"
                                        )
                                    matrix_cb_refs[key] = cb

                # Render DUT checkboxes
                if not all_duts:
                    ui.label("No DUT types found.").classes("text-grey")
                else:
                    ui.label("DUT Types").classes("text-subtitle2 q-mb-xs")
                    with ui.row().classes("flex-wrap q-gutter-sm q-mb-md"):
                        for dut in all_duts:
                            did = dut["id"]
                            cb = ui.checkbox(
                                dut.get("name", f"DUT {did}"),
                                value=(did in state["dut_ids"]),
                            )
                            dut_cb_refs[did] = cb
                            cb.on("update:model-value", lambda _: _rebuild_matrix())

                # Render Profile checkboxes
                if not all_profiles:
                    ui.label("No profiles found.").classes("text-grey")
                else:
                    ui.label("Test Profiles").classes("text-subtitle2 q-mb-xs")
                    with ui.row().classes("flex-wrap q-gutter-sm q-mb-md"):
                        for prof in all_profiles:
                            pid = prof["id"]
                            cb = ui.checkbox(
                                prof.get("name", f"Profile {pid}"),
                                value=(pid in state["profile_ids"]),
                            )
                            prof_cb_refs[pid] = cb
                            cb.on("update:model-value", lambda _: _rebuild_matrix())

                # Initial matrix render if coming back to this step with prior state
                _rebuild_matrix()

                def _collect_matrix() -> None:
                    state["dut_ids"] = [
                        did for did, cb in dut_cb_refs.items() if cb.value
                    ]
                    state["profile_ids"] = [
                        pid for pid, cb in prof_cb_refs.items() if cb.value
                    ]
                    state["dut_profile_matrix"] = [
                        list(pair)
                        for pair, cb in matrix_cb_refs.items()
                        if cb.value
                    ]

                with ui.stepper_navigation():
                    def _back_step4() -> None:
                        _collect_matrix()
                        stepper.previous()

                    def _next_step4() -> None:
                        _collect_matrix()
                        if not state["dut_ids"]:
                            ui.notify("Select at least one DUT.", type="warning")
                            return
                        if not state["profile_ids"]:
                            ui.notify("Select at least one Profile.", type="warning")
                            return
                        if not state["dut_profile_matrix"]:
                            ui.notify(
                                "Tick at least one DUT×Profile combination in the matrix.",
                                type="warning",
                            )
                            return
                        stepper.next()

                    ui.button("Back", on_click=_back_step4).props("flat")
                    ui.button("Next", on_click=_next_step4).props(
                        "color=primary icon-right=arrow_forward"
                    )

            # ---------------------------------------------------------- #
            # Step 5 — PR Fixes                                           #
            # ---------------------------------------------------------- #
            with ui.step("PR Fixes"):
                ui.label(
                    "Enter the expected number of PR fixes by complexity. These add fixed effort per PR."
                ).classes("text-body2 text-grey q-mb-md")

                pr_simple_input = ui.number(
                    "Simple PRs (2 h each)",
                    value=state["pr_simple"],
                    min=0,
                    step=1,
                    precision=0,
                ).classes("w-full")
                pr_medium_input = ui.number(
                    "Medium PRs (4 h each)",
                    value=state["pr_medium"],
                    min=0,
                    step=1,
                    precision=0,
                ).classes("w-full q-mt-sm")
                pr_complex_input = ui.number(
                    "Complex PRs (8 h each)",
                    value=state["pr_complex"],
                    min=0,
                    step=1,
                    precision=0,
                ).classes("w-full q-mt-sm")

                subtotal_label = ui.label("").classes("text-subtitle2 q-mt-sm text-primary")

                def _update_pr_subtotal() -> None:
                    s = int(pr_simple_input.value or 0)
                    m = int(pr_medium_input.value or 0)
                    c = int(pr_complex_input.value or 0)
                    total = s * 2 + m * 4 + c * 8
                    subtotal_label.set_text(f"PR fix subtotal: {total} h")

                pr_simple_input.on("update:model-value", lambda _: _update_pr_subtotal())
                pr_medium_input.on("update:model-value", lambda _: _update_pr_subtotal())
                pr_complex_input.on("update:model-value", lambda _: _update_pr_subtotal())
                _update_pr_subtotal()

                # -- PR Details (optional) --
                ui.separator().classes("q-mt-md")
                with ui.expansion("PR Details (optional)", icon="list").classes("w-full"):
                    ui.label(
                        "Optionally add individual PR details for tracking."
                    ).classes("text-body2 text-grey q-mb-sm")

                    pr_details_container = ui.column().classes("w-full")
                    pr_detail_rows: list[dict] = list(state.get("pr_details", []))

                    def _render_pr_details() -> None:
                        pr_details_container.clear()
                        with pr_details_container:
                            for idx, pr in enumerate(pr_detail_rows):
                                with ui.row().classes("items-center q-gutter-sm w-full"):
                                    _num = ui.input("PR #", value=pr.get("pr_number", "")).classes("w-24")
                                    _link = ui.input("Link", value=pr.get("link", "")).classes("flex-1")
                                    _cx = ui.select(
                                        options=["simple", "medium", "complex"],
                                        value=pr.get("complexity", "simple"),
                                        label="Complexity",
                                    ).classes("w-32")
                                    _st = ui.select(
                                        options=["Open", "Merged", "Closed"],
                                        value=pr.get("status", "Open"),
                                        label="Status",
                                    ).classes("w-28")

                                    def _make_remove(i: int):
                                        def _remove():
                                            pr_detail_rows.pop(i)
                                            _render_pr_details()
                                        return _remove

                                    ui.button(icon="close", on_click=_make_remove(idx)).props("flat dense round color=negative size=sm")

                                    # Bind updates back to data
                                    def _make_updater(i: int, n=_num, l=_link, c=_cx, s=_st):
                                        def _upd(_=None):
                                            if i < len(pr_detail_rows):
                                                pr_detail_rows[i] = {
                                                    "pr_number": n.value or "",
                                                    "link": l.value or "",
                                                    "complexity": c.value or "simple",
                                                    "status": s.value or "Open",
                                                }
                                        return _upd

                                    updater = _make_updater(idx)
                                    _num.on("update:model-value", updater)
                                    _link.on("update:model-value", updater)
                                    _cx.on("update:model-value", updater)
                                    _st.on("update:model-value", updater)

                    def _add_pr_detail() -> None:
                        pr_detail_rows.append({"pr_number": "", "link": "", "complexity": "simple", "status": "Open"})
                        _render_pr_details()

                    ui.button("Add PR Detail", icon="add", on_click=_add_pr_detail).props("flat dense color=primary")
                    _render_pr_details()

                def _collect_prs() -> None:
                    state["pr_simple"] = int(pr_simple_input.value or 0)
                    state["pr_medium"] = int(pr_medium_input.value or 0)
                    state["pr_complex"] = int(pr_complex_input.value or 0)
                    state["pr_details"] = [pr for pr in pr_detail_rows if pr.get("pr_number")]

                with ui.stepper_navigation():
                    def _back_step5() -> None:
                        _collect_prs()
                        stepper.previous()

                    def _next_step5() -> None:
                        _collect_prs()
                        stepper.next()

                    ui.button("Back", on_click=_back_step5).props("flat")
                    ui.button("Next", on_click=_next_step5).props(
                        "color=primary icon-right=arrow_forward"
                    )

            # ---------------------------------------------------------- #
            # Step 6 — Delivery & Team                                    #
            # ---------------------------------------------------------- #
            with ui.step("Delivery & Team"):
                ui.label(
                    "Specify the start date, deadline, and team capacity for feasibility assessment."
                ).classes("text-body2 text-grey q-mb-md")

                with ui.row().classes("w-full q-gutter-md"):
                    start_date_input = ui.date(
                        value=state.get("start_date") or "",
                    ).classes("flex-1").props("label='Start Date (optional)'")

                    delivery_input = ui.date(
                        value=state["delivery_date"] or "",
                    ).classes("flex-1").props("label='Deadline (optional)'")

                working_days_input = ui.number(
                    "Working Days Available",
                    value=state["working_days"],
                    min=1,
                    step=1,
                    precision=0,
                ).classes("w-full q-mt-sm")

                auto_calc_label = ui.label("").classes("text-caption text-primary q-mt-xs")

                def _auto_calc_working_days() -> None:
                    sd = start_date_input.value
                    dd = delivery_input.value
                    if sd and dd:
                        try:
                            from datetime import date as _date, timedelta
                            if isinstance(sd, str):
                                s = _date.fromisoformat(sd)
                            else:
                                s = sd
                            if isinstance(dd, str):
                                d = _date.fromisoformat(dd)
                            else:
                                d = dd
                            days = 0
                            cur = s
                            while cur <= d:
                                if cur.weekday() < 5:
                                    days += 1
                                cur += timedelta(days=1)
                            if days > 0:
                                working_days_input.value = days
                                auto_calc_label.set_text(f"Auto-calculated: {days} working days between dates")
                            else:
                                auto_calc_label.set_text("")
                        except Exception:
                            auto_calc_label.set_text("")
                    else:
                        auto_calc_label.set_text("")

                start_date_input.on("update:model-value", lambda _: _auto_calc_working_days())
                delivery_input.on("update:model-value", lambda _: _auto_calc_working_days())

                team_size_input = ui.number(
                    "Team Size (testers)",
                    value=state["team_size"],
                    min=1,
                    step=1,
                    precision=0,
                ).classes("w-full q-mt-sm")

                leader_toggle = ui.switch(
                    "Include Test Leader effort",
                    value=state["has_leader"],
                ).classes("q-mt-sm")

                # Team allocation picker
                if all_team_members:
                    ui.separator().classes("q-mt-md")
                    ui.label("Team Allocation (optional)").classes("text-subtitle2 q-mt-sm")
                    ui.label(
                        "Select team members and assign roles/hours."
                    ).classes("text-body2 text-grey q-mb-sm")

                    tm_options = {
                        m["id"]: f"{m.get('name', '')} ({m.get('role', '')})"
                        for m in all_team_members
                    }
                    alloc_container = ui.column().classes("w-full")
                    alloc_rows: list[dict] = list(state.get("team_allocations", []))

                    def _render_alloc() -> None:
                        alloc_container.clear()
                        with alloc_container:
                            for idx, alloc in enumerate(alloc_rows):
                                with ui.row().classes("items-center q-gutter-sm w-full"):
                                    _tm = ui.select(
                                        options=tm_options,
                                        value=alloc.get("team_member_id"),
                                        label="Member",
                                    ).classes("flex-1")
                                    _role = ui.select(
                                        options=["TESTER", "LEADER"],
                                        value=alloc.get("role", "TESTER"),
                                        label="Role",
                                    ).classes("w-28")
                                    _hrs = ui.number(
                                        "Hours",
                                        value=alloc.get("allocated_hours", 0),
                                        min=0,
                                        step=1,
                                    ).classes("w-24")

                                    def _make_remove(i: int):
                                        def _remove():
                                            alloc_rows.pop(i)
                                            _render_alloc()
                                        return _remove

                                    ui.button(icon="close", on_click=_make_remove(idx)).props(
                                        "flat dense round color=negative size=sm"
                                    )

                                    def _make_updater(i: int, tm=_tm, r=_role, h=_hrs):
                                        def _upd(_=None):
                                            if i < len(alloc_rows):
                                                alloc_rows[i] = {
                                                    "team_member_id": tm.value,
                                                    "role": r.value or "TESTER",
                                                    "allocated_hours": float(h.value or 0),
                                                }
                                        return _upd

                                    updater = _make_updater(idx)
                                    _tm.on("update:model-value", updater)
                                    _role.on("update:model-value", updater)
                                    _hrs.on("update:model-value", updater)

                    def _add_alloc() -> None:
                        alloc_rows.append({"team_member_id": None, "role": "TESTER", "allocated_hours": 0})
                        _render_alloc()

                    ui.button("Add Team Member", icon="add", on_click=_add_alloc).props(
                        "flat dense color=primary"
                    )
                    _render_alloc()

                def _collect_delivery() -> None:
                    raw_start = start_date_input.value
                    state["start_date"] = raw_start if raw_start else None
                    raw = delivery_input.value
                    state["delivery_date"] = raw if raw else None
                    state["working_days"] = int(working_days_input.value or 20)
                    state["team_size"] = int(team_size_input.value or 1)
                    state["has_leader"] = bool(leader_toggle.value)
                    if all_team_members:
                        state["team_allocations"] = [
                            a for a in alloc_rows if a.get("team_member_id")
                        ]

                with ui.stepper_navigation():
                    def _back_step6() -> None:
                        _collect_delivery()
                        stepper.previous()

                    def _next_step6() -> None:
                        _collect_delivery()
                        if state["team_size"] < 1:
                            ui.notify("Team size must be at least 1.", type="warning")
                            return
                        stepper.next()

                    ui.button("Back", on_click=_back_step6).props("flat")
                    ui.button("Next", on_click=_next_step6).props(
                        "color=primary icon-right=arrow_forward"
                    )

            # ---------------------------------------------------------- #
            # Step 7 — Review & Calculate                                 #
            # ---------------------------------------------------------- #
            with ui.step("Review & Save"):
                ui.label("Review your inputs, run the calculation, then save.").classes(
                    "text-body2 text-grey q-mb-md"
                )

                # Summary cards — rebuilt when this step becomes visible
                summary_container = ui.column().classes("w-full q-mb-md")
                result_container = ui.column().classes("w-full")

                def _render_summary() -> None:
                    summary_container.clear()
                    with summary_container:
                        ui.label("Summary").classes("text-subtitle1 q-mb-xs")
                        with ui.grid(columns=2).classes("w-full q-gutter-sm"):
                            with ui.card().classes("q-pa-sm"):
                                ui.label("Project").classes("text-caption text-grey")
                                ui.label(state["project_name"]).classes("text-body2")
                            with ui.card().classes("q-pa-sm"):
                                ui.label("Type").classes("text-caption text-grey")
                                ui.label(state["project_type"]).classes("text-body2")
                            with ui.card().classes("q-pa-sm"):
                                ui.label("Features").classes("text-caption text-grey")
                                ui.label(
                                    f"{len(state['feature_ids'])} selected, "
                                    f"{len(state['new_feature_ids'])} new"
                                ).classes("text-body2")
                            with ui.card().classes("q-pa-sm"):
                                ui.label("Reference Projects").classes("text-caption text-grey")
                                ui.label(str(len(state["reference_project_ids"]))).classes("text-body2")
                            with ui.card().classes("q-pa-sm"):
                                ui.label("DUTs x Profiles").classes("text-caption text-grey")
                                ui.label(
                                    f"{len(state['dut_ids'])} DUTs, "
                                    f"{len(state['profile_ids'])} profiles, "
                                    f"{len(state['dut_profile_matrix'])} combinations"
                                ).classes("text-body2")
                            with ui.card().classes("q-pa-sm"):
                                ui.label("PR Fixes").classes("text-caption text-grey")
                                ui.label(
                                    f"{state['pr_simple']}s / {state['pr_medium']}m / {state['pr_complex']}c"
                                ).classes("text-body2")
                            with ui.card().classes("q-pa-sm"):
                                ui.label("Working Days").classes("text-caption text-grey")
                                ui.label(str(state["working_days"])).classes("text-body2")
                            with ui.card().classes("q-pa-sm"):
                                ui.label("Team").classes("text-caption text-grey")
                                ui.label(
                                    f"{state['team_size']} tester(s)"
                                    + (" + leader" if state["has_leader"] else "")
                                ).classes("text-body2")

                def _render_result(res: dict) -> None:
                    """Render calculation results returned from the API."""
                    result_container.clear()
                    with result_container:
                        ui.separator()
                        ui.label("Calculation Results").classes("text-subtitle1 q-mt-md q-mb-sm")

                        # Feasibility badge
                        fs = res.get("feasibility_status", "")
                        with ui.row().classes("items-center q-gutter-sm q-mb-sm"):
                            ui.label("Feasibility:").classes("text-body2")
                            _feasibility_badge(fs)
                            util = res.get("utilization_pct", 0)
                            ui.label(f"({util:.1f}% utilization)").classes("text-caption text-grey")

                        # Hours breakdown row
                        with ui.row().classes("q-gutter-md flex-wrap q-mb-sm"):
                            _hours_card("Tester Hours", res.get("total_tester_hours", 0), "person")
                            _hours_card("Leader Hours", res.get("total_leader_hours", 0), "manage_accounts")
                            _hours_card("PR Fix Hours", res.get("pr_fix_hours", 0), "bug_report")
                            _hours_card("Study Hours", res.get("study_hours", 0), "school")
                            _hours_card("Buffer Hours", res.get("buffer_hours", 0), "security")
                            _hours_card(
                                "Grand Total Hours",
                                res.get("grand_total_hours", 0),
                                "summarize",
                            )
                            _hours_card(
                                "Grand Total Days",
                                res.get("grand_total_days", 0),
                                "calendar_today",
                            )

                        # Risk flags
                        flags = res.get("risk_flags", [])
                        messages = res.get("risk_messages", [])
                        if flags:
                            ui.label("Risk Flags").classes("text-subtitle2 q-mt-sm q-mb-xs")
                            with ui.row().classes("flex-wrap q-gutter-xs q-mb-sm"):
                                for flag in flags:
                                    ui.chip(
                                        flag.replace("_", " ").title(),
                                        icon="warning",
                                    ).props("color=negative outline dense")
                            if messages:
                                with ui.expansion("Risk Details", icon="info").classes("w-full"):
                                    for msg in messages:
                                        ui.label(f"- {msg}").classes("text-body2 text-grey")

                        # Task breakdown table
                        tasks = res.get("tasks", [])
                        if tasks:
                            ui.label("Task Breakdown").classes("text-subtitle2 q-mt-sm q-mb-xs")
                            task_cols = [
                                {"name": "name", "label": "Task", "field": "name", "align": "left", "sortable": True},
                                {"name": "task_type", "label": "Type", "field": "task_type", "align": "left"},
                                {"name": "base_hours", "label": "Base h", "field": "base_hours", "align": "right"},
                                {"name": "calculated_hours", "label": "Calc h", "field": "calculated_hours", "align": "right"},
                            ]
                            ui.table(
                                columns=task_cols,
                                rows=tasks,
                                row_key="name",
                                pagination={"rowsPerPage": 15},
                            ).classes("w-full shadow-1")

                async def run_calculate() -> None:
                    """Call POST /estimations/calculate and render the result."""
                    _render_summary()
                    payload: dict[str, Any] = {
                        "project_type": state["project_type"],
                        "feature_ids": state["feature_ids"],
                        "new_feature_ids": state["new_feature_ids"],
                        "reference_project_ids": state["reference_project_ids"],
                        "dut_ids": state["dut_ids"],
                        "profile_ids": state["profile_ids"],
                        "dut_profile_matrix": state["dut_profile_matrix"],
                        "pr_fixes": {
                            "simple": state["pr_simple"],
                            "medium": state["pr_medium"],
                            "complex": state["pr_complex"],
                        },
                        "team_size": state["team_size"],
                        "has_leader": state["has_leader"],
                        "working_days": state["working_days"],
                        "delivery_date": state["delivery_date"],
                    }
                    try:
                        result = await api_post("/estimations/calculate", json=payload)
                        state["calc_result"] = result
                        _render_result(result)
                        ui.notify("Calculation complete.", type="positive")
                    except Exception as exc:
                        ui.notify(f"Calculation failed: {exc}", type="negative")

                async def save_estimation() -> None:
                    """Call POST /estimations to persist, then navigate to detail page."""
                    if state["calc_result"] is None:
                        ui.notify("Run Calculate first.", type="warning")
                        return

                    user = current_user() or {}
                    payload: dict[str, Any] = {
                        "project_name": state["project_name"],
                        "project_type": state["project_type"],
                        "feature_ids": state["feature_ids"],
                        "new_feature_ids": state["new_feature_ids"],
                        "reference_project_ids": state["reference_project_ids"],
                        "dut_ids": state["dut_ids"],
                        "profile_ids": state["profile_ids"],
                        "dut_profile_matrix": state["dut_profile_matrix"],
                        "pr_fixes": {
                            "simple": state["pr_simple"],
                            "medium": state["pr_medium"],
                            "complex": state["pr_complex"],
                        },
                        "pr_details": state.get("pr_details", []),
                        "team_size": state["team_size"],
                        "has_leader": state["has_leader"],
                        "working_days": state["working_days"],
                        "start_date": state.get("start_date"),
                        "expected_delivery": state["delivery_date"],
                        "request_id": linked_request_id,
                        "created_by": user.get("username"),
                        "team_allocations": state.get("team_allocations", []),
                    }
                    try:
                        saved = await api_post("/estimations", json=payload)
                        est_id = saved["id"]
                        ui.notify(f"Estimation saved (ID {est_id}).", type="positive")
                        ui.navigate.to(f"/estimation/{est_id}")
                    except Exception as exc:
                        ui.notify(f"Save failed: {exc}", type="negative")

                # Render initial summary when the wizard reaches this step
                _render_summary()

                with ui.stepper_navigation():
                    ui.button("Back", on_click=lambda: stepper.previous()).props("flat")
                    ui.button(
                        "Calculate",
                        icon="calculate",
                        on_click=run_calculate,
                    ).props("color=secondary")
                    ui.button(
                        "Save Estimation",
                        icon="save",
                        on_click=save_estimation,
                    ).props("color=primary")


# ---------------------------------------------------------------------------
# Route 2: /estimation/{id}  — Estimation detail view
# ---------------------------------------------------------------------------

@ui.page("/estimation/{estimation_id}")
async def estimation_detail_page(estimation_id: int) -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    hdrs = auth_headers()
    token: str = hdrs.get("Authorization", "").removeprefix("Bearer ") if hdrs else ""

    with ui.column().classes("q-pa-lg w-full"):

        # ------------------------------------------------------------------ #
        # Load the estimation                                                  #
        # ------------------------------------------------------------------ #
        try:
            est: dict = await api_get(f"/estimations/{estimation_id}")
        except Exception as exc:
            show_error_page(exc)
            return

        # We need a mutable container for the current status so the status
        # buttons can refresh after a transition without a full page reload.
        est_state: dict[str, Any] = {"data": est}

        # ------------------------------------------------------------------ #
        # Page title row                                                       #
        # ------------------------------------------------------------------ #
        with ui.row().classes("items-center q-gutter-sm q-mb-md"):
            ui.label(est.get("project_name", f"Estimation {estimation_id}")).classes("text-h4")
            if est.get("estimation_number"):
                ui.badge(est["estimation_number"], color="info").props("rounded")
            version = est.get("version", 1) or 1
            if version > 1:
                ui.badge(f"v{version}", color="accent").props("rounded")
            _feasibility_badge(est.get("feasibility_status", ""))
            _status_badge(est.get("status", ""))

        with ui.row().classes("q-gutter-sm q-mb-md"):
            ui.button(
                "Back",
                icon="arrow_back",
                on_click=lambda: ui.navigate.to("/estimations"),
            ).props("flat dense")
            if est.get("status") == "REVISED":
                ui.button(
                    "Edit Estimation",
                    icon="edit",
                    on_click=lambda: ui.navigate.to(f"/estimation/{estimation_id}/edit"),
                ).props("color=orange outline dense")

        # ------------------------------------------------------------------ #
        # Info cards                                                           #
        # ------------------------------------------------------------------ #
        with ui.row().classes("q-gutter-md flex-wrap q-mb-md"):
            with ui.card().classes("q-pa-md"):
                ui.label("Project Type").classes("text-caption text-grey")
                ui.label(est.get("project_type", "—")).classes("text-body1")
            with ui.card().classes("q-pa-md"):
                ui.label("Feasibility").classes("text-caption text-grey")
                with ui.row().classes("items-center"):
                    _feasibility_badge(est.get("feasibility_status", ""))
            with ui.card().classes("q-pa-md"):
                ui.label("Workflow Status").classes("text-caption text-grey")
                with ui.row().classes("items-center"):
                    _status_badge(est.get("status", ""))
            with ui.card().classes("q-pa-md"):
                ui.label("DUTs").classes("text-caption text-grey")
                ui.label(str(est.get("dut_count", 0))).classes("text-body1")
            with ui.card().classes("q-pa-md"):
                ui.label("Profiles").classes("text-caption text-grey")
                ui.label(str(est.get("profile_count", 0))).classes("text-body1")
            with ui.card().classes("q-pa-md"):
                ui.label("Combinations").classes("text-caption text-grey")
                ui.label(str(est.get("dut_profile_combinations", 0))).classes("text-body1")
            if est.get("start_date"):
                with ui.card().classes("q-pa-md"):
                    ui.label("Start Date").classes("text-caption text-grey")
                    ui.label(str(est["start_date"])).classes("text-body1")
            if est.get("expected_delivery"):
                with ui.card().classes("q-pa-md"):
                    ui.label("Deadline").classes("text-caption text-grey")
                    ui.label(str(est["expected_delivery"])).classes("text-body1")
            if est.get("created_at"):
                with ui.card().classes("q-pa-md"):
                    ui.label("Created").classes("text-caption text-grey")
                    ui.label(str(est["created_at"])[:10]).classes("text-body1")

        # ------------------------------------------------------------------ #
        # Assignee                                                             #
        # ------------------------------------------------------------------ #
        ui.label("Assignment").classes("text-h6 q-mb-sm")
        assign_row = ui.row().classes("items-center q-gutter-sm q-mb-md")

        async def _build_assign_ui() -> None:
            assign_row.clear()
            current_est = est_state["data"]
            with assign_row:
                assigned_name = current_est.get("assigned_to_name")
                if assigned_name:
                    ui.icon("person", color="primary").classes("text-lg")
                    ui.label(f"Assigned to: {assigned_name}").classes("text-body1")
                else:
                    ui.icon("person_off", color="grey").classes("text-lg")
                    ui.label("Unassigned").classes("text-body1 text-grey")

                # Load users for the dropdown
                try:
                    users_list: list[dict] = await api_get("/users")
                except Exception:
                    users_list = []

                if users_list:
                    user_options = {u["id"]: u.get("display_name") or u["username"] for u in users_list}
                    current_id = current_est.get("assigned_to_id")

                    sel = ui.select(
                        options=user_options,
                        value=current_id,
                        label="Assign to",
                        with_input=True,
                        clearable=True,
                    ).classes("w-64")

                    async def _do_assign() -> None:
                        uid = sel.value
                        if uid is None:
                            ui.notify("Select a user first.", type="warning")
                            return
                        try:
                            await api_post(
                                f"/estimations/{estimation_id}/assign",
                                params={"assigned_to_id": uid},
                            )
                            # Refresh estimation data
                            est_state["data"] = await api_get(f"/estimations/{estimation_id}")
                            ui.notify(f"Assigned to {user_options.get(uid, uid)}.", type="positive")
                            await _build_assign_ui()
                        except Exception as exc:
                            ui.notify(f"Assignment failed: {exc}", type="negative")

                    ui.button("Assign", icon="person_add", on_click=_do_assign).props("flat dense color=primary")

        await _build_assign_ui()

        # ------------------------------------------------------------------ #
        # Hours breakdown                                                      #
        # ------------------------------------------------------------------ #
        ui.label("Hours Breakdown").classes("text-h6 q-mb-sm")
        with ui.row().classes("q-gutter-md flex-wrap q-mb-md"):
            _hours_card("Tester Hours", est.get("total_tester_hours", 0), "person")
            _hours_card("Leader Hours", est.get("total_leader_hours", 0), "manage_accounts")
            _hours_card("PR Fix Hours", est.get("pr_fix_hours", 0), "bug_report")
            _hours_card("Study Hours", est.get("study_hours", 0), "school")
            _hours_card("Buffer Hours", est.get("buffer_hours", 0), "security")
            _hours_card("Grand Total Hours", est.get("grand_total_hours", 0), "summarize")
            _hours_card("Grand Total Days", est.get("grand_total_days", 0), "calendar_today")

        # ------------------------------------------------------------------ #
        # Task breakdown table                                                 #
        # ------------------------------------------------------------------ #
        tasks: list[dict] = est.get("tasks", [])
        if tasks:
            ui.label("Task Breakdown").classes("text-h6 q-mb-sm")
            task_cols = [
                {"name": "task_name", "label": "Task",       "field": "task_name",        "align": "left",  "sortable": True},
                {"name": "task_type", "label": "Type",       "field": "task_type",        "align": "left",  "sortable": True},
                {"name": "base_hours","label": "Base h",     "field": "base_hours",       "align": "right", "sortable": True},
                {"name": "calc_hours","label": "Calc h",     "field": "calculated_hours", "align": "right", "sortable": True},
                {"name": "new_study", "label": "New Feature","field": "is_new_feature_study", "align": "center"},
            ]
            tbl = ui.table(
                columns=task_cols,
                rows=tasks,
                row_key="id",
                pagination={"rowsPerPage": 20},
            ).classes("w-full shadow-1 q-mb-md")
            tbl.add_slot(
                "body-cell-new_study",
                r"""
                <q-td :props="props">
                    <q-badge
                        :color="props.value ? 'orange' : 'transparent'"
                        :label="props.value ? 'Study' : ''"
                        :text-color="props.value ? 'white' : 'transparent'"
                    />
                </q-td>
                """,
            )
        else:
            ui.label("No task breakdown available.").classes("text-grey q-mb-md")

        # ------------------------------------------------------------------ #
        # Team Allocation                                                      #
        # ------------------------------------------------------------------ #
        team_allocs = est.get("team_allocations") or []
        if team_allocs:
            ui.label("Team Allocation").classes("text-h6 q-mb-sm")
            alloc_cols = [
                {"name": "team_member_name", "label": "Member",  "field": "team_member_name", "align": "left"},
                {"name": "role",             "label": "Role",    "field": "role",             "align": "left"},
                {"name": "allocated_hours",  "label": "Hours",   "field": "allocated_hours",  "align": "right"},
            ]
            ui.table(
                columns=alloc_cols,
                rows=team_allocs,
                row_key="team_member_id",
            ).classes("w-full shadow-1 q-mb-md")

        # ------------------------------------------------------------------ #
        # Status transition buttons                                            #
        # ------------------------------------------------------------------ #
        ui.label("Workflow Actions").classes("text-h6 q-mb-sm")
        status_row = ui.row().classes("q-gutter-sm q-mb-md")

        async def _do_status_transition(target: str) -> None:
            try:
                updated = await api_post(
                    f"/estimations/{estimation_id}/status",
                    json={"status": target},
                )
                est_state["data"] = updated
                ui.notify(f"Status changed to {target}.", type="positive")
                # Rebuild the transition buttons to reflect new state
                _rebuild_status_buttons()
            except Exception as exc:
                ui.notify(f"Status update failed: {exc}", type="negative")

        _STATUS_BTN_PROPS: dict[str, str] = {
            "FINAL":    "color=primary",
            "APPROVED": "color=positive",
            "REVISED":  "color=orange",
            "DRAFT":    "color=grey",
        }

        def _rebuild_status_buttons() -> None:
            status_row.clear()
            current_status = est_state["data"].get("status", "DRAFT")
            allowed = _STATUS_TRANSITIONS.get(current_status, [])
            with status_row:
                if not allowed:
                    ui.label(f"No further transitions from {current_status}.").classes(
                        "text-caption text-grey"
                    )
                else:
                    for target in allowed:
                        btn_props = _STATUS_BTN_PROPS.get(target, "color=grey")
                        # Use default arg capture to avoid late-binding closure bug
                        ui.button(
                            f"Move to {target}",
                            on_click=lambda t=target: _do_status_transition(t),
                        ).props(btn_props)

        _rebuild_status_buttons()

        # ------------------------------------------------------------------ #
        # Archive to History (Feature 6)                                       #
        # ------------------------------------------------------------------ #
        if est.get("status") == "APPROVED":
            async def _archive_to_history() -> None:
                try:
                    await api_post(f"/estimations/{estimation_id}/archive")
                    ui.notify("Estimation archived to Historical Projects.", type="positive")
                except Exception as exc:
                    ui.notify(f"Archive failed: {exc}", type="negative")

            with ui.row().classes("q-mb-md"):
                ui.button(
                    "Archive to History",
                    icon="archive",
                    on_click=_archive_to_history,
                ).props("color=accent outline")

        # ------------------------------------------------------------------ #
        # Report download buttons                                              #
        # ------------------------------------------------------------------ #
        ui.label("Download Reports").classes("text-h6 q-mb-sm")

        def _download_js(fmt: str, filename: str) -> str:
            """Return JavaScript that fetches a report blob and triggers download.

            Uses a relative /api/ path so the request goes through the same
            origin the browser is connected to (nginx reverse proxy), instead
            of the internal API_URL which is unreachable from the browser.
            """
            url = f"/api/estimations/{estimation_id}/report/{fmt}"
            return (
                f'fetch("{url}", {{'
                f'  headers: {{"Authorization": "Bearer {token}"}}'
                f'}})'
                f'.then(r => {{ if (!r.ok) throw new Error("HTTP " + r.status); return r.blob(); }})'
                f'.then(b => {{'
                f'  const a = document.createElement("a");'
                f'  a.href = URL.createObjectURL(b);'
                f'  a.download = "{filename}";'
                f'  a.click();'
                f'}})'
                f'.catch(err => console.error("Download failed:", err));'
            )

        with ui.row().classes("q-gutter-sm q-mb-lg"):
            ui.button(
                "Excel (.xlsx)",
                icon="table_chart",
                on_click=lambda: ui.run_javascript(
                    _download_js("xlsx", f"estimation_{estimation_id}.xlsx")
                ),
            ).props("color=positive outline")

            ui.button(
                "Word (.docx)",
                icon="description",
                on_click=lambda: ui.run_javascript(
                    _download_js("docx", f"estimation_{estimation_id}.docx")
                ),
            ).props("color=primary outline")

            ui.button(
                "PDF (.pdf)",
                icon="picture_as_pdf",
                on_click=lambda: ui.run_javascript(
                    _download_js("pdf", f"estimation_{estimation_id}.pdf")
                ),
            ).props("color=negative outline")


# ---------------------------------------------------------------------------
# Route 3: /estimation/{id}/edit  — Edit wizard for REVISED estimations
# ---------------------------------------------------------------------------

@ui.page("/estimation/{estimation_id}/edit")
async def edit_estimation_page(estimation_id: int) -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    with ui.column().classes("q-pa-lg w-full"):
        # Load the estimation
        try:
            est: dict = await api_get(f"/estimations/{estimation_id}")
        except Exception as exc:
            show_error_page(exc)
            return

        if est.get("status") != "REVISED":
            ui.label("This estimation is not in REVISED status and cannot be edited.").classes(
                "text-warning text-h6"
            )
            ui.button("Back to Detail", on_click=lambda: ui.navigate.to(f"/estimation/{estimation_id}"))
            return

        # Parse wizard inputs
        wizard_raw = est.get("wizard_inputs_json", "{}")
        try:
            saved_inputs: dict = _json.loads(wizard_raw) if wizard_raw else {}
        except (_json.JSONDecodeError, TypeError):
            saved_inputs = {}

        has_saved_inputs = bool(saved_inputs.get("feature_ids"))

        if not has_saved_inputs:
            ui.label(
                "This estimation was created before wizard input tracking was available. "
                "You can re-enter the inputs below."
            ).classes("text-warning q-mb-md")

        # Pre-load catalog data in parallel.
        # Auth headers are captured BEFORE asyncio.gather to avoid context-propagation
        # issues (see new_estimation_page for a full explanation).
        _catalog_headers = auth_headers()

        async def _safe_get(path: str) -> list[dict]:
            try:
                async with httpx.AsyncClient() as _client:
                    _r = await _client.get(
                        f"{API_URL}{path}", headers=_catalog_headers
                    )
                    _r.raise_for_status()
                    return _r.json()
            except Exception:
                return []

        all_features, all_duts, all_profiles, all_hist, all_team_members = await asyncio.gather(
            _safe_get("/features"),
            _safe_get("/dut-types"),
            _safe_get("/profiles"),
            _safe_get("/historical-projects"),
            _safe_get("/team-members"),
        )

        # Pre-fill state from saved inputs
        existing_allocs = [
            {"team_member_id": a.get("team_member_id"), "role": a.get("role", "TESTER"), "allocated_hours": a.get("allocated_hours", 0)}
            for a in (est.get("team_allocations") or [])
        ]
        state: dict[str, Any] = {
            "project_name": est.get("project_name", ""),
            "project_type": est.get("project_type", "EVOLUTION"),
            "description": "",
            "feature_ids": saved_inputs.get("feature_ids", []),
            "new_feature_ids": saved_inputs.get("new_feature_ids", []),
            "reference_project_ids": saved_inputs.get("reference_project_ids", []),
            "dut_ids": saved_inputs.get("dut_ids", []),
            "profile_ids": saved_inputs.get("profile_ids", []),
            "dut_profile_matrix": saved_inputs.get("dut_profile_matrix", []),
            "pr_simple": saved_inputs.get("pr_fixes", {}).get("simple", 0),
            "pr_medium": saved_inputs.get("pr_fixes", {}).get("medium", 0),
            "pr_complex": saved_inputs.get("pr_fixes", {}).get("complex", 0),
            "pr_details": saved_inputs.get("pr_details", []),
            "start_date": str(est.get("start_date") or "") or None,
            "delivery_date": str(est.get("expected_delivery") or "") or None,
            "working_days": saved_inputs.get("working_days", 20),
            "team_size": saved_inputs.get("team_size", 1),
            "has_leader": saved_inputs.get("has_leader", False),
            "team_allocations": existing_allocs,
            "calc_result": None,
        }

        version = est.get("version", 1) or 1
        ui.label(f"Edit Estimation — {est.get('estimation_number', '')} (v{version})").classes("text-h4 q-mb-md")

        # ---- Wizard (same 7 steps as new, but pre-filled) ---- #
        with ui.stepper().props("vertical=false animated").classes("w-full") as stepper:

            # Step 1 — Project Info
            with ui.step("Project Info"):
                ui.label("Edit the basic project details.").classes("text-body2 text-grey q-mb-md")
                name_input = ui.input("Project Name *", value=state["project_name"]).classes("w-full")
                name_input.on("update:model-value", lambda e: state.update({"project_name": e.args}))
                type_select = ui.select(
                    options=["NEW", "EVOLUTION", "SUPPORT"],
                    label="Project Type",
                    value=state["project_type"],
                ).classes("w-full q-mt-sm")
                type_select.on("update:model-value", lambda e: state.update({"project_type": e.args}))

                with ui.stepper_navigation():
                    def _go_s2():
                        state["project_name"] = name_input.value or ""
                        state["project_type"] = type_select.value or "EVOLUTION"
                        if not state["project_name"].strip():
                            ui.notify("Project Name is required.", type="warning")
                            return
                        stepper.next()
                    ui.button("Next", on_click=_go_s2).props("color=primary icon-right=arrow_forward")

            # Step 2 — Features
            with ui.step("Features"):
                ui.label("Select features under test.").classes("text-body2 text-grey q-mb-md")

                features_by_cat: dict[str, list[dict]] = {}
                for feat in all_features:
                    cat = feat.get("category") or "Other"
                    features_by_cat.setdefault(cat, []).append(feat)

                feature_checkbox_refs: dict[int, ui.checkbox] = {}
                new_feat_checkbox_refs: dict[int, ui.checkbox] = {}

                if not all_features:
                    ui.label("No features found.").classes("text-warning")
                else:
                    # -- Select All checkbox --
                    _programmatic_select_all = [False]
                    all_pre_selected = all(f["id"] in state["feature_ids"] for f in all_features)
                    select_all_cb = ui.checkbox(
                        f"Select all ({len(all_features)} features)",
                        value=all_pre_selected,
                    ).classes("text-weight-bold q-mb-sm")

                    def _toggle_select_all(e):
                        if _programmatic_select_all[0]:
                            return
                        checked = e.value
                        for _fid, _cb in feature_checkbox_refs.items():
                            _cb.value = checked
                            if not checked and _fid in new_feat_checkbox_refs:
                                new_feat_checkbox_refs[_fid].value = False

                    select_all_cb.on_value_change(_toggle_select_all)

                    def _update_select_all_state() -> None:
                        all_checked = all(cb.value for cb in feature_checkbox_refs.values())
                        if select_all_cb.value != all_checked:
                            _programmatic_select_all[0] = True
                            select_all_cb.value = all_checked
                            _programmatic_select_all[0] = False

                    ui.separator()

                    for cat_name, cat_features in features_by_cat.items():
                        ui.label(cat_name).classes("text-subtitle2 q-mt-sm text-primary")

                        with ui.grid(columns="1fr 100px 110px").classes("w-full q-pl-md items-center"):
                            ui.label("Feature").classes("text-caption text-grey")
                            ui.label("Complexity").classes("text-caption text-grey text-center")
                            ui.label("New?").classes("text-caption text-grey text-center")

                            for feat in cat_features:
                                fid = feat["id"]
                                fname = feat.get("name", f"Feature {fid}")
                                fweight = feat.get("complexity_weight", 1.0)

                                cb = ui.checkbox(
                                    fname,
                                    value=(fid in state["feature_ids"]),
                                )
                                feature_checkbox_refs[fid] = cb

                                ui.label(f"x{fweight:.1f}").classes("text-center")

                                new_cb = ui.checkbox(
                                    "New",
                                    value=(fid in state["new_feature_ids"]),
                                ).props("dense color=orange").classes("text-caption")
                                new_feat_checkbox_refs[fid] = new_cb

                                def _make_sync(f_id: int, n_cb: ui.checkbox):
                                    def _sync(e):
                                        if not feature_checkbox_refs[f_id].value:
                                            n_cb.value = False
                                        _update_select_all_state()
                                    return _sync
                                cb.on("update:model-value", _make_sync(fid, new_cb))

                def _collect_features():
                    state["feature_ids"] = [fid for fid, cb in feature_checkbox_refs.items() if cb.value]
                    state["new_feature_ids"] = [
                        fid for fid, cb in new_feat_checkbox_refs.items()
                        if cb.value and feature_checkbox_refs[fid].value
                    ]

                with ui.stepper_navigation():
                    def _back_s2():
                        _collect_features()
                        stepper.previous()
                    def _next_s2():
                        _collect_features()
                        if not state["feature_ids"]:
                            ui.notify("Select at least one feature.", type="warning")
                            return
                        stepper.next()
                    ui.button("Back", on_click=_back_s2).props("flat")
                    ui.button("Next", on_click=_next_s2).props("color=primary icon-right=arrow_forward")

            # Step 3 — Reference Projects
            with ui.step("Reference Projects"):
                ui.label("Pick historical projects for calibration (optional).").classes("text-body2 text-grey q-mb-md")
                ref_checkbox_refs: dict[int, ui.checkbox] = {}
                if not all_hist:
                    ui.label("No historical projects available.").classes("text-grey")
                else:
                    with ui.grid(columns=1).classes("w-full"):
                        for proj in all_hist:
                            pid = proj["id"]
                            pname = proj.get("project_name", f"Project {pid}")
                            est_h = proj.get("estimated_hours") or 0
                            act_h = proj.get("actual_hours") or 0
                            accuracy = (act_h / est_h) if est_h else None
                            acc_txt = f"  accuracy ratio: {accuracy:.2f}" if accuracy is not None else "  (no accuracy data)"
                            label = f"{pname}  [{proj.get('project_type', '')}]{acc_txt}"
                            cb = ui.checkbox(label, value=(pid in state["reference_project_ids"]))
                            ref_checkbox_refs[pid] = cb

                def _collect_refs():
                    state["reference_project_ids"] = [pid for pid, cb in ref_checkbox_refs.items() if cb.value]

                with ui.stepper_navigation():
                    def _back_s3():
                        _collect_refs()
                        stepper.previous()
                    def _next_s3():
                        _collect_refs()
                        stepper.next()
                    ui.button("Back", on_click=_back_s3).props("flat")
                    ui.button("Next", on_click=_next_s3).props("color=primary icon-right=arrow_forward")

            # Step 4 — DUT x Profile Matrix
            with ui.step("DUT x Profile Matrix"):
                ui.label("Select DUTs and Profiles, then tick the combinations.").classes("text-body2 text-grey q-mb-md")
                dut_cb_refs: dict[int, ui.checkbox] = {}
                prof_cb_refs: dict[int, ui.checkbox] = {}
                matrix_cb_refs: dict[tuple[int, int], ui.checkbox] = {}
                matrix_container = ui.column().classes("w-full q-mt-md")

                def _rebuild_matrix():
                    matrix_container.clear()
                    sel_duts = [d for d in all_duts if dut_cb_refs.get(d["id"]) and dut_cb_refs[d["id"]].value]
                    sel_profs = [p for p in all_profiles if prof_cb_refs.get(p["id"]) and prof_cb_refs[p["id"]].value]
                    matrix_cb_refs.clear()
                    if not sel_duts or not sel_profs:
                        with matrix_container:
                            ui.label("Select at least one DUT and one Profile.").classes("text-grey text-caption")
                        return
                    with matrix_container:
                        ui.label("Combination Matrix").classes("text-subtitle2 q-mb-sm")
                        n_cols = len(sel_profs) + 1
                        with ui.grid(columns=n_cols).classes("w-full items-center"):
                            # Header row
                            ui.label("DUT \\ Profile").classes("text-caption text-grey text-weight-bold")
                            for prof in sel_profs:
                                ui.label(prof.get("name", f"P{prof['id']}")).classes("text-caption text-center text-weight-bold")
                            # Data rows
                            for dut in sel_duts:
                                ui.label(dut.get("name", f"D{dut['id']}")).classes("text-caption")
                                for prof in sel_profs:
                                    key = (dut["id"], prof["id"])
                                    pre_checked = key in [tuple(pair) for pair in state["dut_profile_matrix"]]
                                    cb = ui.checkbox("", value=pre_checked).props("dense")
                                    matrix_cb_refs[key] = cb

                if not all_duts:
                    ui.label("No DUT types found.").classes("text-grey")
                else:
                    ui.label("DUT Types").classes("text-subtitle2 q-mb-xs")
                    with ui.row().classes("flex-wrap q-gutter-sm q-mb-md"):
                        for dut in all_duts:
                            did = dut["id"]
                            cb = ui.checkbox(dut.get("name", f"DUT {did}"), value=(did in state["dut_ids"]))
                            dut_cb_refs[did] = cb
                            cb.on("update:model-value", lambda _: _rebuild_matrix())

                if not all_profiles:
                    ui.label("No profiles found.").classes("text-grey")
                else:
                    ui.label("Test Profiles").classes("text-subtitle2 q-mb-xs")
                    with ui.row().classes("flex-wrap q-gutter-sm q-mb-md"):
                        for prof in all_profiles:
                            pid = prof["id"]
                            cb = ui.checkbox(prof.get("name", f"Profile {pid}"), value=(pid in state["profile_ids"]))
                            prof_cb_refs[pid] = cb
                            cb.on("update:model-value", lambda _: _rebuild_matrix())

                _rebuild_matrix()

                def _collect_matrix():
                    state["dut_ids"] = [did for did, cb in dut_cb_refs.items() if cb.value]
                    state["profile_ids"] = [pid for pid, cb in prof_cb_refs.items() if cb.value]
                    state["dut_profile_matrix"] = [list(pair) for pair, cb in matrix_cb_refs.items() if cb.value]

                with ui.stepper_navigation():
                    def _back_s4():
                        _collect_matrix()
                        stepper.previous()
                    def _next_s4():
                        _collect_matrix()
                        if not state["dut_ids"]:
                            ui.notify("Select at least one DUT.", type="warning")
                            return
                        if not state["profile_ids"]:
                            ui.notify("Select at least one Profile.", type="warning")
                            return
                        if not state["dut_profile_matrix"]:
                            ui.notify("Tick at least one DUT×Profile combination.", type="warning")
                            return
                        stepper.next()
                    ui.button("Back", on_click=_back_s4).props("flat")
                    ui.button("Next", on_click=_next_s4).props("color=primary icon-right=arrow_forward")

            # Step 5 — PR Fixes
            with ui.step("PR Fixes"):
                ui.label("Enter the expected PR fixes.").classes("text-body2 text-grey q-mb-md")
                pr_simple_input = ui.number("Simple PRs (2 h each)", value=state["pr_simple"], min=0, step=1, precision=0).classes("w-full")
                pr_medium_input = ui.number("Medium PRs (4 h each)", value=state["pr_medium"], min=0, step=1, precision=0).classes("w-full q-mt-sm")
                pr_complex_input = ui.number("Complex PRs (8 h each)", value=state["pr_complex"], min=0, step=1, precision=0).classes("w-full q-mt-sm")

                # -- PR Details (optional) --
                ui.separator().classes("q-mt-md")
                with ui.expansion("PR Details (optional)", icon="list").classes("w-full"):
                    ui.label("Optionally add individual PR details.").classes("text-body2 text-grey q-mb-sm")
                    pr_details_container = ui.column().classes("w-full")
                    pr_detail_rows: list[dict] = list(state.get("pr_details", []))

                    def _render_pr_details() -> None:
                        pr_details_container.clear()
                        with pr_details_container:
                            for idx, pr in enumerate(pr_detail_rows):
                                with ui.row().classes("items-center q-gutter-sm w-full"):
                                    _num = ui.input("PR #", value=pr.get("pr_number", "")).classes("w-24")
                                    _link = ui.input("Link", value=pr.get("link", "")).classes("flex-1")
                                    _cx = ui.select(options=["simple", "medium", "complex"], value=pr.get("complexity", "simple"), label="Complexity").classes("w-32")
                                    _st = ui.select(options=["Open", "Merged", "Closed"], value=pr.get("status", "Open"), label="Status").classes("w-28")

                                    def _make_remove(i: int):
                                        def _remove():
                                            pr_detail_rows.pop(i)
                                            _render_pr_details()
                                        return _remove
                                    ui.button(icon="close", on_click=_make_remove(idx)).props("flat dense round color=negative size=sm")

                                    def _make_updater(i: int, n=_num, l=_link, c=_cx, s=_st):
                                        def _upd(_=None):
                                            if i < len(pr_detail_rows):
                                                pr_detail_rows[i] = {"pr_number": n.value or "", "link": l.value or "", "complexity": c.value or "simple", "status": s.value or "Open"}
                                        return _upd
                                    updater = _make_updater(idx)
                                    _num.on("update:model-value", updater)
                                    _link.on("update:model-value", updater)
                                    _cx.on("update:model-value", updater)
                                    _st.on("update:model-value", updater)

                    def _add_pr_detail() -> None:
                        pr_detail_rows.append({"pr_number": "", "link": "", "complexity": "simple", "status": "Open"})
                        _render_pr_details()

                    ui.button("Add PR Detail", icon="add", on_click=_add_pr_detail).props("flat dense color=primary")
                    _render_pr_details()

                def _collect_prs():
                    state["pr_simple"] = int(pr_simple_input.value or 0)
                    state["pr_medium"] = int(pr_medium_input.value or 0)
                    state["pr_complex"] = int(pr_complex_input.value or 0)
                    state["pr_details"] = [pr for pr in pr_detail_rows if pr.get("pr_number")]

                with ui.stepper_navigation():
                    def _back_s5():
                        _collect_prs()
                        stepper.previous()
                    def _next_s5():
                        _collect_prs()
                        stepper.next()
                    ui.button("Back", on_click=_back_s5).props("flat")
                    ui.button("Next", on_click=_next_s5).props("color=primary icon-right=arrow_forward")

            # Step 6 — Delivery & Team
            with ui.step("Delivery & Team"):
                ui.label("Specify start date, deadline, and team capacity.").classes("text-body2 text-grey q-mb-md")
                start_date_input = ui.date(value=state.get("start_date") or "").classes("w-full").props("label='Start Date (optional)'")
                delivery_input = ui.date(value=state["delivery_date"] or "").classes("w-full q-mt-sm").props("label='Deadline (optional)'")
                working_days_input = ui.number("Working Days Available", value=state["working_days"], min=1, step=1, precision=0).classes("w-full q-mt-sm")

                auto_calc_label = ui.label("").classes("text-caption text-primary q-mt-xs")

                def _auto_calc_working_days() -> None:
                    sd = start_date_input.value
                    dd = delivery_input.value
                    if sd and dd:
                        try:
                            from datetime import date as _date, timedelta
                            s = _date.fromisoformat(sd) if isinstance(sd, str) else sd
                            d = _date.fromisoformat(dd) if isinstance(dd, str) else dd
                            days = sum(1 for i in range((d - s).days + 1) if (s + timedelta(days=i)).weekday() < 5)
                            if days > 0:
                                working_days_input.value = days
                                auto_calc_label.set_text(f"Auto-calculated: {days} working days")
                            else:
                                auto_calc_label.set_text("")
                        except Exception:
                            auto_calc_label.set_text("")
                    else:
                        auto_calc_label.set_text("")

                start_date_input.on("update:model-value", lambda _: _auto_calc_working_days())
                delivery_input.on("update:model-value", lambda _: _auto_calc_working_days())

                team_size_input = ui.number("Team Size (testers)", value=state["team_size"], min=1, step=1, precision=0).classes("w-full q-mt-sm")
                leader_toggle = ui.switch("Include Test Leader effort", value=state["has_leader"]).classes("q-mt-sm")

                # Team allocation picker
                if all_team_members:
                    ui.separator().classes("q-mt-md")
                    ui.label("Team Allocation (optional)").classes("text-subtitle2 q-mt-sm")
                    tm_options = {
                        m["id"]: f"{m.get('name', '')} ({m.get('role', '')})"
                        for m in all_team_members
                    }
                    alloc_container = ui.column().classes("w-full")
                    alloc_rows: list[dict] = list(state.get("team_allocations", []))

                    def _render_alloc() -> None:
                        alloc_container.clear()
                        with alloc_container:
                            for idx, alloc in enumerate(alloc_rows):
                                with ui.row().classes("items-center q-gutter-sm w-full"):
                                    _tm = ui.select(options=tm_options, value=alloc.get("team_member_id"), label="Member").classes("flex-1")
                                    _role = ui.select(options=["TESTER", "LEADER"], value=alloc.get("role", "TESTER"), label="Role").classes("w-28")
                                    _hrs = ui.number("Hours", value=alloc.get("allocated_hours", 0), min=0, step=1).classes("w-24")
                                    def _make_remove(i: int):
                                        def _remove():
                                            alloc_rows.pop(i)
                                            _render_alloc()
                                        return _remove
                                    ui.button(icon="close", on_click=_make_remove(idx)).props("flat dense round color=negative size=sm")
                                    def _make_updater(i: int, tm=_tm, r=_role, h=_hrs):
                                        def _upd(_=None):
                                            if i < len(alloc_rows):
                                                alloc_rows[i] = {"team_member_id": tm.value, "role": r.value or "TESTER", "allocated_hours": float(h.value or 0)}
                                        return _upd
                                    updater = _make_updater(idx)
                                    _tm.on("update:model-value", updater)
                                    _role.on("update:model-value", updater)
                                    _hrs.on("update:model-value", updater)

                    def _add_alloc() -> None:
                        alloc_rows.append({"team_member_id": None, "role": "TESTER", "allocated_hours": 0})
                        _render_alloc()

                    ui.button("Add Team Member", icon="add", on_click=_add_alloc).props("flat dense color=primary")
                    _render_alloc()

                def _collect_delivery():
                    raw_start = start_date_input.value
                    state["start_date"] = raw_start if raw_start else None
                    raw = delivery_input.value
                    state["delivery_date"] = raw if raw else None
                    state["working_days"] = int(working_days_input.value or 20)
                    state["team_size"] = int(team_size_input.value or 1)
                    state["has_leader"] = bool(leader_toggle.value)
                    if all_team_members:
                        state["team_allocations"] = [a for a in alloc_rows if a.get("team_member_id")]

                with ui.stepper_navigation():
                    def _back_s6():
                        _collect_delivery()
                        stepper.previous()
                    def _next_s6():
                        _collect_delivery()
                        if state["team_size"] < 1:
                            ui.notify("Team size must be at least 1.", type="warning")
                            return
                        stepper.next()
                    ui.button("Back", on_click=_back_s6).props("flat")
                    ui.button("Next", on_click=_next_s6).props("color=primary icon-right=arrow_forward")

            # Step 7 — Review & Save Revision
            with ui.step("Review & Save"):
                ui.label("Review, recalculate, and save the revised estimation.").classes("text-body2 text-grey q-mb-md")

                summary_container = ui.column().classes("w-full q-mb-md")
                result_container = ui.column().classes("w-full")

                def _render_summary():
                    summary_container.clear()
                    with summary_container:
                        ui.label("Summary").classes("text-subtitle1 q-mb-xs")
                        with ui.grid(columns=2).classes("w-full q-gutter-sm"):
                            with ui.card().classes("q-pa-sm"):
                                ui.label("Project").classes("text-caption text-grey")
                                ui.label(state["project_name"]).classes("text-body2")
                            with ui.card().classes("q-pa-sm"):
                                ui.label("Type").classes("text-caption text-grey")
                                ui.label(state["project_type"]).classes("text-body2")
                            with ui.card().classes("q-pa-sm"):
                                ui.label("Features").classes("text-caption text-grey")
                                ui.label(f"{len(state['feature_ids'])} selected, {len(state['new_feature_ids'])} new").classes("text-body2")
                            with ui.card().classes("q-pa-sm"):
                                ui.label("DUTs x Profiles").classes("text-caption text-grey")
                                ui.label(f"{len(state['dut_ids'])} DUTs, {len(state['profile_ids'])} profiles, {len(state['dut_profile_matrix'])} combinations").classes("text-body2")
                            with ui.card().classes("q-pa-sm"):
                                ui.label("PR Fixes").classes("text-caption text-grey")
                                ui.label(f"{state['pr_simple']}s / {state['pr_medium']}m / {state['pr_complex']}c").classes("text-body2")
                            with ui.card().classes("q-pa-sm"):
                                ui.label("Team").classes("text-caption text-grey")
                                ui.label(f"{state['team_size']} tester(s)" + (" + leader" if state["has_leader"] else "")).classes("text-body2")

                def _render_result(res: dict):
                    result_container.clear()
                    with result_container:
                        ui.separator()
                        ui.label("Calculation Results").classes("text-subtitle1 q-mt-md q-mb-sm")
                        fs = res.get("feasibility_status", "")
                        with ui.row().classes("items-center q-gutter-sm q-mb-sm"):
                            ui.label("Feasibility:").classes("text-body2")
                            _feasibility_badge(fs)
                            util = res.get("utilization_pct", 0)
                            ui.label(f"({util:.1f}% utilization)").classes("text-caption text-grey")
                        with ui.row().classes("q-gutter-md flex-wrap q-mb-sm"):
                            _hours_card("Tester Hours", res.get("total_tester_hours", 0), "person")
                            _hours_card("Leader Hours", res.get("total_leader_hours", 0), "manage_accounts")
                            _hours_card("PR Fix Hours", res.get("pr_fix_hours", 0), "bug_report")
                            _hours_card("Study Hours", res.get("study_hours", 0), "school")
                            _hours_card("Buffer Hours", res.get("buffer_hours", 0), "security")
                            _hours_card("Grand Total Hours", res.get("grand_total_hours", 0), "summarize")
                            _hours_card("Grand Total Days", res.get("grand_total_days", 0), "calendar_today")
                        flags = res.get("risk_flags", [])
                        if flags:
                            ui.label("Risk Flags").classes("text-subtitle2 q-mt-sm q-mb-xs")
                            with ui.row().classes("flex-wrap q-gutter-xs"):
                                for flag in flags:
                                    ui.chip(flag.replace("_", " ").title(), icon="warning").props("color=negative outline dense")

                async def run_calculate():
                    _render_summary()
                    payload: dict[str, Any] = {
                        "project_type": state["project_type"],
                        "feature_ids": state["feature_ids"],
                        "new_feature_ids": state["new_feature_ids"],
                        "reference_project_ids": state["reference_project_ids"],
                        "dut_ids": state["dut_ids"],
                        "profile_ids": state["profile_ids"],
                        "dut_profile_matrix": state["dut_profile_matrix"],
                        "pr_fixes": {
                            "simple": state["pr_simple"],
                            "medium": state["pr_medium"],
                            "complex": state["pr_complex"],
                        },
                        "team_size": state["team_size"],
                        "has_leader": state["has_leader"],
                        "working_days": state["working_days"],
                        "delivery_date": state["delivery_date"],
                    }
                    try:
                        result = await api_post("/estimations/calculate", json=payload)
                        state["calc_result"] = result
                        _render_result(result)
                        ui.notify("Calculation complete.", type="positive")
                    except Exception as exc:
                        ui.notify(f"Calculation failed: {exc}", type="negative")

                async def save_revision():
                    if state["calc_result"] is None:
                        ui.notify("Run Calculate first.", type="warning")
                        return
                    payload: dict[str, Any] = {
                        "project_name": state["project_name"],
                        "project_type": state["project_type"],
                        "feature_ids": state["feature_ids"],
                        "new_feature_ids": state["new_feature_ids"],
                        "reference_project_ids": state["reference_project_ids"],
                        "dut_ids": state["dut_ids"],
                        "profile_ids": state["profile_ids"],
                        "dut_profile_matrix": state["dut_profile_matrix"],
                        "pr_fixes": {
                            "simple": state["pr_simple"],
                            "medium": state["pr_medium"],
                            "complex": state["pr_complex"],
                        },
                        "pr_details": state.get("pr_details", []),
                        "team_size": state["team_size"],
                        "has_leader": state["has_leader"],
                        "working_days": state["working_days"],
                        "start_date": state.get("start_date"),
                        "expected_delivery": state["delivery_date"],
                        "team_allocations": state.get("team_allocations", []),
                    }
                    try:
                        saved = await api_put(f"/estimations/{estimation_id}/revise", json=payload)
                        new_ver = saved.get("version", "?")
                        ui.notify(f"Revision saved (v{new_ver}).", type="positive")
                        ui.navigate.to(f"/estimation/{estimation_id}")
                    except Exception as exc:
                        ui.notify(f"Save failed: {exc}", type="negative")

                _render_summary()

                with ui.stepper_navigation():
                    ui.button("Back", on_click=lambda: stepper.previous()).props("flat")
                    ui.button("Calculate", icon="calculate", on_click=run_calculate).props("color=secondary")
                    ui.button("Save Revision", icon="save", on_click=save_revision).props("color=primary")
