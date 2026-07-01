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
    has_permission,
    is_authenticated,
    notify_error,
    run_async,
    show_error_page,
    sidebar,
)

# ---------------------------------------------------------------------------
# Wizard component CSS — injected once at import (module level) so it is part
# of the global stylesheet. Injecting inside the @ui.page function is
# unreliable on SPA client-side navigation in some browsers, which left the
# floating progress strip and summary rail unstyled (only text rendered).
# ---------------------------------------------------------------------------

ui.add_head_html("""
<style>
  /* Wizard 2-column grid */
  .ed-wizard-grid   { display: grid !important;
                      grid-template-columns: 1fr 320px; gap: 22px;
                      align-items: start; }
  @media (max-width: 960px) {
    .ed-wizard-grid { grid-template-columns: 1fr; }
    .ed-summary-rail { position: static !important; max-height: none !important; }
  }

  /* Hide Quasar default stepper header */
  .ed-wizard-grid .q-stepper__header { display: none !important; }
  .ed-wizard-grid .q-stepper { box-shadow: none !important;
                               background: transparent !important;
                               border: 1px solid var(--ed-line);
                               border-radius: 4px; }
  .ed-wizard-grid .q-stepper__step-inner { padding: 24px 26px !important; }
  /* Sticky per-step nav */
  .ed-wizard-grid .q-stepper__nav { padding: 16px 26px !important;
                                    position: sticky; bottom: 0;
                                    background: var(--ed-bg-soft);
                                    backdrop-filter: blur(10px);
                                    border-top: 1px solid var(--ed-line); }

  /* Custom progress strip */
  .ed-progress      { display: grid !important;
                      grid-auto-flow: column;
                      grid-auto-columns: 1fr;
                      align-items: start; gap: 0;
                      padding: 18px 24px;
                      border: 1px solid var(--ed-line); border-radius: 4px;
                      margin-bottom: 24px; }
  .ed-progress-step { display: flex !important; flex-direction: column;
                      align-items: center; gap: 8px;
                      cursor: pointer; position: relative;
                      text-align: center; }
  .ed-progress-step:not(:last-child)::after {
                      content: ""; position: absolute;
                      top: 14px; left: calc(50% + 18px); right: calc(-50% + 18px);
                      height: 1px; background: var(--ed-line); z-index: 0; }
  .ed-progress-step.done:not(:last-child)::after { background: var(--q-primary); }
  .ed-progress-num  { width: 28px; height: 28px; border-radius: 50%;
                      border: 1px solid var(--ed-line);
                      display: flex !important; align-items: center; justify-content: center;
                      font-family: var(--ed-mono); font-size: 12px; font-weight: 500;
                      background: var(--q-page, transparent); z-index: 1;
                      transition: all 200ms ease; }
  .ed-progress-step.active .ed-progress-num {
                      border: 2px solid var(--q-primary); color: var(--q-primary);
                      transform: scale(1.05); }
  .ed-progress-step.done .ed-progress-num {
                      background: var(--q-primary); border-color: var(--q-primary);
                      color: white; }
  .ed-progress-label{ font-family: inherit; font-size: 11px;
                      text-transform: uppercase; letter-spacing: 0.10em;
                      font-weight: 500; opacity: 0.6;
                      line-height: 1.2; max-width: 100px; }
  .ed-progress-step.active .ed-progress-label { opacity: 1; color: var(--q-primary); }
  .ed-progress-step.done .ed-progress-label   { opacity: 0.85; }

  /* Summary rail */
  .ed-summary-rail  { position: sticky; top: 88px;
                      border: 1px solid var(--ed-line); border-radius: 4px;
                      padding: 22px;
                      display: flex !important; flex-direction: column; gap: 0;
                      max-height: calc(100vh - 110px); overflow-y: auto; }
  .ed-summary-title { font-family: inherit; font-size: 16px; font-weight: 600;
                      line-height: 1.25; margin: 4px 0 16px 0;
                      word-break: break-word; }
  .ed-summary-section { margin-top: 14px; padding-top: 14px;
                        border-top: 1px dashed var(--ed-line-soft); }
  .ed-summary-row   { display: grid !important; grid-template-columns: 1fr auto;
                      align-items: baseline; gap: 8px; padding: 5px 0; }
  .ed-summary-label { font-family: inherit; text-transform: uppercase;
                      letter-spacing: 0.10em; font-size: 10px;
                      font-weight: 600; opacity: 0.6; }
  .ed-summary-value { font-family: var(--ed-mono); font-variant-numeric: tabular-nums;
                      font-size: 13px; }
  .ed-summary-value.empty { opacity: 0.35; font-style: italic;
                            font-family: inherit; font-size: 12px; }
  .ed-summary-total { margin-top: 18px; padding-top: 16px;
                      border-top: 1px solid var(--ed-line);
                      text-align: right; }
  .ed-summary-total-num { font-family: var(--ed-mono);
                          font-variant-numeric: tabular-nums;
                          font-size: 28px; font-weight: 500;
                          line-height: 1; margin-top: 6px; }
</style>
""", shared=True)

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


def _render_preset_bar(state: dict, feature_checkbox_refs: dict, config_map: dict):
    """Render the estimator self-service feature-preset bar (Apply + Save).

    Shared by both the new and edit estimation wizards so presets work in each.
    Returns an async ``refresh()`` that (re)loads presets for the wizard's
    current product type — call it once after the feature list is built.
    """
    presets_holder: dict = {"items": []}
    with ui.row().classes("items-center gap-2 q-mb-sm flex-wrap"):
        preset_select = ui.select({}, label="Apply preset", with_input=True) \
            .props("dense outlined clearable").style("min-width: 240px;")

        async def _refresh_presets() -> None:
            pt = state.get("product_type_filter") or ""
            params = {"product_type": pt} if pt and pt != "All" else None
            try:
                items = await api_get("/feature-presets", params=params)
            except Exception:
                items = []
            items = items if isinstance(items, list) else []
            presets_holder["items"] = items
            preset_select.set_options({p["id"]: p["name"] for p in items})

        def _apply_preset(*_) -> None:
            preset = next(
                (p for p in presets_holder["items"] if p["id"] == preset_select.value), None
            )
            if not preset:
                ui.notify("Pick a preset to apply.", type="warning")
                return
            applied = 0
            for fid in preset.get("feature_ids", []):  # additive: never deselects
                if fid in feature_checkbox_refs:
                    feature_checkbox_refs[fid].value = True
                if fid not in state["feature_ids"]:
                    state["feature_ids"].append(fid)
                applied += 1
            # Record which presets were applied (used in reports).
            _ap = state.setdefault("applied_presets", [])
            if not any(x.get("id") == preset["id"] for x in _ap):
                _ap.append({"id": preset["id"], "name": preset["name"]})
            ui.notify(f"Applied preset '{preset['name']}' (+{applied} feature(s)).",
                      type="positive")

        ui.button("Apply", icon="playlist_add_check",
                  on_click=_apply_preset).props("dense color=primary")

        async def _save_preset() -> None:
            selected = set(state["feature_ids"])
            for fid, cb in feature_checkbox_refs.items():
                if cb.value:
                    selected.add(fid)
                else:
                    selected.discard(fid)
            if not selected:
                ui.notify("Select at least one feature first.", type="warning")
                return
            _pt = state.get("product_type_filter") or "All"
            with ui.dialog() as _pdlg, ui.card().classes("w-[min(420px,92vw)]"):
                ui.label("Save selection as preset").classes("text-h6")
                ui.label(f"{len(selected)} feature(s) · product type: {_pt}") \
                    .classes("text-caption text-grey")
                _pname = ui.input("Preset name *").classes("w-full").props("autofocus")
                _pdesc = ui.textarea("Description (optional)") \
                    .classes("w-full").props("autogrow")

                async def _do_save() -> None:
                    if not (_pname.value or "").strip():
                        ui.notify("Preset name is required.", type="warning")
                        return
                    await api_post("/feature-presets", json={
                        "name": _pname.value.strip(),
                        "description": (_pdesc.value or "").strip() or None,
                        "product_type": (None if _pt == "All" else _pt),
                        "feature_ids": sorted(selected),
                    })
                    _pdlg.close()
                    await _refresh_presets()
                    ui.notify("Preset saved.", type="positive")

                with ui.row().classes("w-full justify-end q-mt-sm"):
                    ui.button("Cancel", on_click=_pdlg.close).props("flat")
                    _sb = ui.button("Save", icon="save").props("color=primary")
                    _sb.on("click", run_async(_sb, _do_save,
                                              error_prefix="Could not save preset"))
            _pdlg.open()

        _save_btn = ui.button("Save selection as preset", icon="bookmark_add") \
            .props("dense flat color=secondary")
        _save_btn.on("click", run_async(_save_btn, _save_preset,
                                        error_prefix="Could not save preset"))
    return _refresh_presets


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
                    "request_number": e.get("request_number") or "",
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
                {"name": "request_number", "label": "Request", "field": "request_number", "align": "left", "sortable": True},
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
                    pagination={"rowsPerPage": 15},
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

    # When opened from the request inbox, prefill the description with a
    # reference to the originating request (plus title / requester / original
    # text) so the estimator has context without retyping it.
    _prefill_description = ""
    if linked_request_id is not None:
        try:
            _linked_request = await api_get(f"/requests/{linked_request_id}")
        except Exception:
            _linked_request = None
        if _linked_request:
            _req_no = _linked_request.get("request_number") or f"#{linked_request_id}"
            _req_title = (_linked_request.get("title") or "").strip()
            _req_requester = (_linked_request.get("requester_name") or "").strip()
            _head = f"Estimation request based on {_req_no}"
            if _req_title:
                _head += f": {_req_title}"
            _parts = [_head]
            if _req_requester:
                _parts.append(f"Requested by {_req_requester}.")
            _orig = (_linked_request.get("description") or "").strip()
            if _orig:
                _parts.append("")
                _parts.append("Original request:")
                _parts.append(_orig)
            _prefill_description = "\n".join(_parts)

    # ------------------------------------------------------------------ #
    # Wizard state — single dict keeps all inter-step data together       #
    # ------------------------------------------------------------------ #
    state: dict[str, Any] = {
        # Step 1
        "project_name": "",
        "project_type": "EVOLUTION",
        "product_type_filter": "All",
        "applied_presets": [],
        "description": _prefill_description,
        "project_goals": "",
        "target_customer": "",
        "project_reference": "",
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
        "testing_start_date": None,
        "delivery_date": None,
        "working_days": 20,
        "team_size": 1,
        "has_leader": False,
        "expected_releases": 1,
        "team_allocations": [],
        "team_id": None,
        "risk_item_ids": [],
        "document_type_ids": [],
        "document_counts": {},
        # Step 7 (calculation result)
        "calc_result": None,
        # Autosave: id of the draft this wizard is backed by (created lazily),
        # and a signature of the last successfully autosaved payload.
        "autosave_id": None,
        "autosave_sig": None,
    }

    # Pre-load catalog data in parallel so later steps can render immediately.
    # Auth headers are captured BEFORE asyncio.gather to avoid context-propagation
    # issues: each coroutine spawned by gather gets a copy of the current context,
    # but NiceGUI's app.storage.user relies on request_contextvar which may not
    # survive the copy correctly in all environments.  By pre-capturing the headers
    # here (in the original request context) and closing over them in _safe_get we
    # guarantee every API call is authenticated.
    _catalog_headers = auth_headers()
    # Captured once in the request context so the background autosave timer
    # (which runs outside per-client storage context) can still authenticate
    # and stamp the author — mirrors the _catalog_headers pattern above.
    _persist_username = (current_user() or {}).get("username")

    def _build_persist_payload() -> dict[str, Any]:
        """Collect the current wizard state into a create/draft payload.

        Shared by manual Save and the background autosave so both persist
        exactly the same inputs.
        """
        return {
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
            "start_date": state.get("start_date") or None,
            "testing_start_date": state.get("testing_start_date") or None,
            "expected_delivery": state.get("delivery_date") or None,
            "request_id": linked_request_id,
            "created_by": _persist_username,
            "team_allocations": state.get("team_allocations", []),
            "expected_releases": state.get("expected_releases", 1),
            "project_goals": state.get("project_goals") or None,
            "target_customer": state.get("target_customer") or None,
            "project_reference": state.get("project_reference") or None,
            "team_id": state.get("team_id"),
            "risk_item_ids": state.get("risk_item_ids", []),
            "document_type_ids": state.get("document_type_ids", []),
            "document_counts": state.get("document_counts", {}),
            "task_assigned_testers": state.get("task_assigned_testers", {}),
            "product_type_filter": state.get("product_type_filter", "All"),
            "applied_presets": state.get("applied_presets", []),
        }

    async def autosave() -> None:
        """Persist in-progress wizard input to a DRAFT so a browser/session
        timeout never loses work. Creates the draft once enough is filled in,
        then updates it in place. Runs on a page-level timer (active from the
        first step) and uses pre-captured auth headers + a direct httpx call,
        because the timer fires outside per-client storage context."""
        if not _catalog_headers.get("Authorization"):
            return
        # Require a name plus at least one real selection before we materialize
        # a draft — avoids littering the list with empty estimations.
        if not (state["project_name"] or "").strip():
            return
        has_content = any([
            state["feature_ids"], state["new_feature_ids"], state["dut_ids"],
            state["pr_simple"], state["pr_medium"], state["pr_complex"],
            (state.get("team_size") or 0) > 0,
            state.get("delivery_date"),
            state.get("working_days"),
        ])
        if state["autosave_id"] is None and not has_content:
            return
        payload = _build_persist_payload()
        sig = repr(payload)
        if sig == state["autosave_sig"]:
            return  # nothing changed since last autosave
        try:
            async with httpx.AsyncClient() as _client:
                if state["autosave_id"] is None:
                    _r = await _client.post(
                        f"{API_URL}/estimations", json=payload, headers=_catalog_headers,
                    )
                    _r.raise_for_status()
                    state["autosave_id"] = _r.json()["id"]
                else:
                    _r = await _client.put(
                        f"{API_URL}/estimations/{state['autosave_id']}/draft",
                        json=payload, headers=_catalog_headers,
                    )
                    _r.raise_for_status()
            state["autosave_sig"] = sig
            if _autosave_label is not None:
                _autosave_label.set_text("✓ Draft autosaved")
        except Exception:
            # Never let autosave interrupt the user; retry on the next tick.
            if _autosave_label is not None:
                _autosave_label.set_text("Autosave pending…")

    # Autosave status label — created inside the rendered content container
    # below (a timer/label attached at bare page scope never fires; it must
    # live inside an active element slot, like the sidebar's poll timer).
    _autosave_label = None

    async def save_draft_now() -> None:
        """Explicitly save the wizard's current progress as a DRAFT, from any step.

        Unlike the final "Save Estimation", this does not require a calculation —
        it persists whatever has been entered so the user can stop and resume
        later. Creates the draft on first save, then updates it in place."""
        if not (state["project_name"] or "").strip():
            ui.notify("Enter a project name before saving a draft.", type="warning")
            return
        payload = _build_persist_payload()
        try:
            if state["autosave_id"] is None:
                saved = await api_post("/estimations", json=payload)
                state["autosave_id"] = saved["id"]
            else:
                await api_put(f"/estimations/{state['autosave_id']}/draft", json=payload)
            state["autosave_sig"] = repr(payload)
            if _autosave_label is not None:
                _autosave_label.set_text("✓ Draft saved")
            ui.notify(f"Draft saved (ID {state['autosave_id']}). Resume it any time from Estimations.",
                      type="positive")
        except Exception as exc:
            ui.notify(f"Could not save draft: {exc}", type="negative")

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

    all_features, all_duts, all_profiles, all_hist, all_team_members, all_teams, all_risk_items, _all_configs, _all_estimations = await asyncio.gather(
        _safe_get("/features"),
        _safe_get("/dut-types"),
        _safe_get("/profiles"),
        _safe_get("/historical-projects"),
        _safe_get("/team-members"),
        _safe_get("/teams"),
        _safe_get("/risk-items"),
        _safe_get("/configuration"),
        _safe_get("/estimations"),
    )
    _config_map: dict[str, str] = {c.get("key", ""): c.get("value", "") for c in _all_configs if isinstance(c, dict)}
    _pr_priority_list = [p.strip() for p in _config_map.get("pr_priority_list", "LOW,MEDIUM,HIGH,CRITICAL").split(",") if p.strip()]
    _project_types = [p.strip() for p in _config_map.get("project_types", "NEW,EVOLUTION,SUPPORT,CHANGE_REQUEST").split(",") if p.strip()]
    # Build options for project reference: estimation_number + project_name
    _est_ref_options: dict[str, str] = {}
    for _e in (_all_estimations or []):
        _num = _e.get("estimation_number") or ""
        _pname = _e.get("project_name") or ""
        _label = f"{_num} — {_pname}" if _num else _pname
        _est_ref_options[_label] = _label

    # Derive product types from features, DUTs, and profiles for filtering
    _product_types_set: set[str] = set()
    for _item in [*all_features, *all_duts, *all_profiles]:
        _pt = _item.get("product_type")
        if _pt:
            _product_types_set.add(_pt)
    product_types: list[str] = sorted(_product_types_set)

    # ------------------------------------------------------------------ #
    # Page title                                                           #
    # ------------------------------------------------------------------ #
    with ui.column().classes("w-full q-pa-md").style("gap: 0;"):

        # Background autosave timers. These must live inside a rendered slot to
        # fire (a timer attached at bare page scope never runs). The visible
        # "Save draft" button + status label are placed in the toolbar below.
        ui.timer(30.0, autosave)
        # Fire once shortly after the client connects (mirrors the sidebar's
        # notification poller) so a draft is created promptly once input exists.
        ui.timer(5.0, autosave, once=True)

        # Wizard component CSS is injected once at module import (see top of
        # this file) so it survives SPA navigation in all browsers.

        # ── Sticky toolbar ──────────────────────────────────────
        with ui.element("div").classes("ed-toolbar"):
            ui.button(icon="arrow_back",
                      on_click=lambda: ui.navigate.to("/estimations")) \
                .props("flat dense").tooltip("Back to estimations")
            ui.element("div").classes("ed-toolbar-spacer")
            ui.label("New Estimation").classes("ed-eyebrow")
            title_label = ui.label("Untitled estimation").classes("ed-mono") \
                .style("font-size: 13px; opacity: 0.85;")
            ui.element("div").classes("ed-toolbar-grow")
            if linked_request_id is not None:
                ui.label(f"REQ · {linked_request_id}").classes("ed-mono") \
                    .style("opacity: 0.7;")
            _autosave_label = ui.label("").classes("ed-autosave-note ed-mono") \
                .style("opacity: 0.7; font-size: 12px;")
            ui.button("Save draft", icon="save", on_click=save_draft_now) \
                .props("flat dense color=primary") \
                .tooltip("Save current progress as a draft — resume later from Estimations")

        with ui.element("div").classes("ed-shell"):
            ui.label("New Estimation").classes("text-h4 q-mb-md")

            # Define wizard step metadata (display labels for progress strip)
            WIZARD_STEPS = [
                ("Project Info",          "Project Info"),
                ("Features",              "Features"),
                ("Reference Projects",    "References"),
                ("DUT x Profile Matrix",  "DUTs / Profiles"),
                ("PR Fixes",              "PR Fixes"),
                ("Delivery & Team",       "Schedule"),
                ("Review & Save",         "Review"),
            ]
            progress_container = ui.element("div").classes("ed-progress")

            with ui.element("div").classes("ed-wizard-grid"):
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
                        _name_error = ui.label("Project Name is required.").classes(
                            "text-negative text-caption"
                        )
                        _name_error.set_visibility(False)

                        def _on_name_change(e) -> None:
                            state.update({"project_name": e.args})
                            if (e.args or "").strip():
                                _name_error.set_visibility(False)

                        name_input.on("update:model-value", _on_name_change)

                        type_select = ui.select(
                            options=_project_types,
                            label="Project Type",
                            value=state["project_type"],
                        ).classes("w-full q-mt-sm")
                        type_select.on(
                            "update:model-value",
                            lambda e: state.update({"project_type": e.args}),
                        )

                        # Project Reference — shown only for CHANGE_REQUEST
                        _ref_opts = list(_est_ref_options.keys())
                        _ref_val = state.get("project_reference", "") or None
                        if _ref_val and _ref_val not in _ref_opts:
                            _ref_opts.append(_ref_val)
                        ref_input = ui.select(
                            options=_ref_opts,
                            label="Project Reference *",
                            value=_ref_val,
                            with_input=True,
                            new_value_mode="add-unique",
                        ).classes("w-full q-mt-sm")
                        ref_input.bind_visibility_from(type_select, "value", backward=lambda v: v == "CHANGE_REQUEST")
                        ref_input.on(
                            "update:model-value",
                            lambda e: state.update({"project_reference": e.args}),
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

                        goals_input = ui.textarea(
                            "Project Goals (optional)",
                            value=state["project_goals"],
                            placeholder="What are the main goals of this project?",
                        ).classes("w-full q-mt-sm")
                        goals_input.on(
                            "update:model-value",
                            lambda e: state.update({"project_goals": e.args}),
                        )

                        customer_input = ui.input(
                            "Target Customer (optional)",
                            value=state["target_customer"],
                            placeholder="e.g. Vodafone, Deutsche Telekom",
                        ).classes("w-full q-mt-sm")
                        customer_input.on(
                            "update:model-value",
                            lambda e: state.update({"target_customer": e.args}),
                        )

                        ui.separator().classes("q-mt-md")
                        ui.label("Product Type Filter").classes("text-subtitle2")
                        ui.label(
                            "Select a product type to filter Features, DUTs, and Profiles in subsequent steps."
                        ).classes("text-caption text-grey q-mb-xs")
                        pt_filter_select = ui.select(
                            options=["All"] + product_types,
                            value=state["product_type_filter"],
                            label="Product Type",
                        ).classes("w-64")

                        with ui.stepper_navigation():
                            def _go_step2() -> None:
                                state["project_name"] = name_input.value or ""
                                state["project_type"] = type_select.value or "EVOLUTION"
                                state["product_type_filter"] = pt_filter_select.value or "All"
                                state["description"] = desc_input.value or ""
                                state["project_goals"] = goals_input.value or ""
                                state["target_customer"] = customer_input.value or ""
                                state["project_reference"] = ref_input.value or ""
                                if not state["project_name"].strip():
                                    _name_error.set_visibility(True)
                                    ui.notify("Project Name is required.", type="warning")
                                    return
                                _name_error.set_visibility(False)
                                if state["project_type"] == "CHANGE_REQUEST" and not state["project_reference"].strip():
                                    ui.notify("Project Reference is required for Change Request.", type="warning")
                                    return
                                # Rebuild feature list with current product type filter
                                _rebuild_feature_list()
                                stepper.next()

                            ui.button("Next", on_click=_go_step2).props("color=primary icon-right=arrow_forward")

                    # ---------------------------------------------------------- #
                    # Step 2 — Features                                           #
                    # ---------------------------------------------------------- #
                    with ui.step("Features"):
                        ui.label(
                            "Select the features under test. Toggle 'New' for features that require study time."
                        ).classes("text-body2 text-grey q-mb-md")

                        async def _add_custom_feature() -> None:
                            """Add a project-specific feature for this estimation.

                            Project features must be owned by a saved estimation, so we
                            persist the draft first (creating it if needed) and scope the
                            new feature to it — it then counts toward THIS estimation only."""
                            if state["autosave_id"] is None:
                                await save_draft_now()
                                if state["autosave_id"] is None:
                                    return  # save_draft_now already warned (e.g. no project name)
                            with ui.dialog() as _dlg, ui.card().classes("w-[min(460px,92vw)]"):
                                ui.label("Add custom feature for this project").classes("text-h6")
                                ui.label(
                                    "Used in this estimation only. You can request adding it to the "
                                    "global catalog at the Review step."
                                ).classes("text-caption text-grey q-mb-sm")
                                _name = ui.input("Feature name *").classes("w-full").props("autofocus")
                                _cat = ui.input("Category", value="Project-Specific").classes("w-full")
                                _weight = ui.number("Complexity weight", value=1.0, min=0.1, step=0.1).classes("w-full")
                                _base = ui.number("Base effort (hours)", value=8.0, min=0, step=0.5).classes("w-full")
                                _ptype = ui.select(["All"] + product_types, label="Product Type",
                                                   value=(state.get("product_type_filter") or "All")).classes("w-full")
                                _has_tests = ui.checkbox("Has existing tests", value=False)
                                _desc = ui.textarea("Description (optional)").classes("w-full")

                                async def _create() -> None:
                                    if not (_name.value or "").strip():
                                        ui.notify("Feature name is required.", type="warning")
                                        return
                                    created = await api_post(
                                        f"/estimations/{state['autosave_id']}/features",
                                        json={
                                            "name": _name.value.strip(),
                                            "category": (_cat.value or "").strip() or None,
                                            "complexity_weight": float(_weight.value or 1.0),
                                            "base_effort_hours": float(_base.value or 0),
                                            "product_type": (None if _ptype.value in (None, "All") else _ptype.value),
                                            "has_existing_tests": bool(_has_tests.value),
                                            "description": (_desc.value or "").strip() or None,
                                        },
                                    )
                                    all_features.append(created)
                                    if created["id"] not in state["feature_ids"]:
                                        state["feature_ids"].append(created["id"])
                                    _rebuild_feature_list()
                                    ui.notify(f"Added project feature '{created['name']}'.", type="positive")
                                    _dlg.close()

                                with ui.row().classes("w-full justify-end q-mt-sm"):
                                    ui.button("Cancel", on_click=_dlg.close).props("flat")
                                    _add_btn = ui.button("Add", icon="add").props("color=primary")
                                    _add_btn.on("click", run_async(
                                        _add_btn, _create, error_prefix="Could not add feature"))
                            _dlg.open()

                        async def _edit_custom_feature(feat: dict) -> None:
                            """Edit a project feature already added (fix a typo or detail)."""
                            with ui.dialog() as _dlg, ui.card().classes("w-[min(460px,92vw)]"):
                                ui.label("Edit project feature").classes("text-h6")
                                _name = ui.input("Feature name *", value=feat.get("name", "")).classes("w-full").props("autofocus")
                                _cat = ui.input("Category", value=feat.get("category") or "").classes("w-full")
                                _weight = ui.number("Complexity weight", value=feat.get("complexity_weight", 1.0), min=0.1, step=0.1).classes("w-full")
                                _base = ui.number("Base effort (hours)", value=feat.get("base_effort_hours", 0.0) or 0.0, min=0, step=0.5).classes("w-full")
                                _ptype = ui.select(["All"] + product_types, label="Product Type",
                                                   value=(feat.get("product_type") or "All")).classes("w-full")
                                _has_tests = ui.checkbox("Has existing tests", value=bool(feat.get("has_existing_tests")))
                                _desc = ui.textarea("Description (optional)", value=feat.get("description") or "").classes("w-full")

                                async def _save() -> None:
                                    if not (_name.value or "").strip():
                                        ui.notify("Feature name is required.", type="warning")
                                        return
                                    updated = await api_put(
                                        f"/features/{feat['id']}",
                                        json={
                                            "name": _name.value.strip(),
                                            "category": (_cat.value or "").strip() or None,
                                            "complexity_weight": float(_weight.value or 1.0),
                                            "base_effort_hours": float(_base.value or 0),
                                            "product_type": (None if _ptype.value in (None, "All") else _ptype.value),
                                            "has_existing_tests": bool(_has_tests.value),
                                            "description": (_desc.value or "").strip() or None,
                                        },
                                    )
                                    feat.update(updated)
                                    _rebuild_feature_list()
                                    ui.notify(f"Updated '{updated['name']}'.", type="positive")
                                    _dlg.close()

                                with ui.row().classes("w-full justify-end q-mt-sm"):
                                    ui.button("Cancel", on_click=_dlg.close).props("flat")
                                    _save_btn = ui.button("Save", icon="save").props("color=primary")
                                    _save_btn.on("click", run_async(
                                        _save_btn, _save, error_prefix="Could not update feature"))
                            _dlg.open()

                        with ui.row().classes("items-center q-mb-sm"):
                            ui.button("Add custom feature", icon="add", on_click=_add_custom_feature) \
                                .props("outline dense color=primary")
                            ui.label("No suitable template entry? Add a project-specific one.") \
                                .classes("text-caption text-grey")

                        pt_info_label = ui.label("").classes("text-caption text-primary q-mb-sm")

                        # We need checkbox refs to read values on navigation
                        feature_checkbox_refs: dict[int, ui.checkbox] = {}
                        new_feat_checkbox_refs: dict[int, ui.checkbox] = {}

                        # -- Feature presets (estimator self-service) ----------------
                        _presets_holder: dict = {"items": []}
                        with ui.row().classes("items-center gap-2 q-mb-sm flex-wrap"):
                            preset_select = ui.select(
                                {}, label="Apply preset", with_input=True,
                            ).props("dense outlined clearable").style("min-width: 240px;")

                            async def _refresh_presets() -> None:
                                pt = state.get("product_type_filter") or ""
                                params = {"product_type": pt} if pt and pt != "All" else None
                                try:
                                    items = await api_get("/feature-presets", params=params)
                                except Exception:
                                    items = []
                                items = items if isinstance(items, list) else []
                                _presets_holder["items"] = items
                                preset_select.set_options({p["id"]: p["name"] for p in items})

                            def _apply_preset(*_) -> None:
                                pid = preset_select.value
                                preset = next(
                                    (p for p in _presets_holder["items"] if p["id"] == pid), None
                                )
                                if not preset:
                                    ui.notify("Pick a preset to apply.", type="warning")
                                    return
                                applied = 0
                                # Additive: only ever selects, never deselects.
                                for fid in preset.get("feature_ids", []):
                                    if fid in feature_checkbox_refs:
                                        feature_checkbox_refs[fid].value = True
                                    if fid not in state["feature_ids"]:
                                        state["feature_ids"].append(fid)
                                    applied += 1
                                _ap = state.setdefault("applied_presets", [])
                                if not any(x.get("id") == preset["id"] for x in _ap):
                                    _ap.append({"id": preset["id"], "name": preset["name"]})
                                ui.notify(
                                    f"Applied preset '{preset['name']}' (+{applied} feature(s)).",
                                    type="positive",
                                )

                            ui.button("Apply", icon="playlist_add_check",
                                      on_click=_apply_preset).props("dense color=primary")

                            async def _save_preset() -> None:
                                selected = set(state["feature_ids"])
                                for fid, cb in feature_checkbox_refs.items():
                                    if cb.value:
                                        selected.add(fid)
                                    else:
                                        selected.discard(fid)
                                if not selected:
                                    ui.notify("Select at least one feature first.", type="warning")
                                    return
                                _pt = state.get("product_type_filter") or "All"
                                with ui.dialog() as _pdlg, ui.card().classes("w-[min(420px,92vw)]"):
                                    ui.label("Save selection as preset").classes("text-h6")
                                    ui.label(
                                        f"{len(selected)} feature(s) · product type: {_pt}"
                                    ).classes("text-caption text-grey")
                                    _pname = ui.input("Preset name *").classes("w-full").props("autofocus")
                                    _pdesc = ui.textarea("Description (optional)").classes("w-full").props("autogrow")

                                    async def _do_save() -> None:
                                        if not (_pname.value or "").strip():
                                            ui.notify("Preset name is required.", type="warning")
                                            return
                                        await api_post("/feature-presets", json={
                                            "name": _pname.value.strip(),
                                            "description": (_pdesc.value or "").strip() or None,
                                            "product_type": (None if _pt == "All" else _pt),
                                            "feature_ids": sorted(selected),
                                        })
                                        _pdlg.close()
                                        await _refresh_presets()
                                        ui.notify("Preset saved.", type="positive")

                                    with ui.row().classes("w-full justify-end q-mt-sm"):
                                        ui.button("Cancel", on_click=_pdlg.close).props("flat")
                                        _sb = ui.button("Save", icon="save").props("color=primary")
                                        _sb.on("click", run_async(
                                            _sb, _do_save, error_prefix="Could not save preset"))
                                _pdlg.open()

                            _save_preset_btn = ui.button(
                                "Save selection as preset", icon="bookmark_add",
                            ).props("dense flat color=secondary")
                            _save_preset_btn.on("click", run_async(
                                _save_preset_btn, _save_preset, error_prefix="Could not save preset"))

                        features_container = ui.column().classes("w-full")

                        # -- Select All checkbox (outside container so it persists) --
                        _programmatic_select_all = [False]

                        def _rebuild_feature_list() -> None:
                            """Rebuild the feature checkbox list based on the product type filter from Step 1."""
                            # Collect current selections before clearing
                            for _fid, _cb in feature_checkbox_refs.items():
                                if _cb.value and _fid not in state["feature_ids"]:
                                    state["feature_ids"].append(_fid)
                                elif not _cb.value and _fid in state["feature_ids"]:
                                    state["feature_ids"].remove(_fid)
                            for _fid, _cb in new_feat_checkbox_refs.items():
                                if _cb.value and _fid not in state["new_feature_ids"]:
                                    state["new_feature_ids"].append(_fid)
                                elif not _cb.value and _fid in state["new_feature_ids"]:
                                    state["new_feature_ids"].remove(_fid)

                            feature_checkbox_refs.clear()
                            new_feat_checkbox_refs.clear()
                            features_container.clear()

                            selected_pt = state.get("product_type_filter") or "All"
                            if selected_pt and selected_pt != "All":
                                visible_features = [f for f in all_features if not f.get("product_type") or f.get("product_type") == selected_pt]
                                pt_info_label.set_text(f"Filtered by product type: {selected_pt}")
                            else:
                                visible_features = list(all_features)
                                pt_info_label.set_text("")

                            # Group visible features by category
                            vis_by_cat: dict[str, list[dict]] = {}
                            for feat in visible_features:
                                cat = feat.get("category") or "Other"
                                vis_by_cat.setdefault(cat, []).append(feat)

                            with features_container:
                                if not visible_features:
                                    ui.label("No features match the selected product type.").classes("text-grey")
                                    return

                                all_pre_selected = all(f["id"] in state["feature_ids"] for f in visible_features)
                                select_all_cb = ui.checkbox(
                                    f"Select all ({len(visible_features)} features)",
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
                                    if not feature_checkbox_refs:
                                        return
                                    all_checked = all(cb.value for cb in feature_checkbox_refs.values())
                                    if select_all_cb.value != all_checked:
                                        _programmatic_select_all[0] = True
                                        select_all_cb.value = all_checked
                                        _programmatic_select_all[0] = False

                                ui.separator()

                                for cat_name, cat_features in vis_by_cat.items():
                                    ui.label(cat_name).classes("text-subtitle2 q-mt-sm text-primary")

                                    with ui.grid(columns="1.3fr 1.7fr 90px 70px 90px").classes("w-full q-pl-md items-center"):
                                        ui.label("Feature").classes("text-caption text-grey")
                                        ui.label("Description").classes("text-caption text-grey")
                                        ui.label("Complexity").classes("text-caption text-grey text-center")
                                        ui.label("New?").classes("text-caption text-grey text-center")
                                        ui.label("Scope").classes("text-caption text-grey text-center")

                                        for feat in cat_features:
                                            fid = feat["id"]
                                            fname = feat.get("name", f"Feature {fid}")
                                            fweight = feat.get("complexity_weight", 1.0)
                                            _is_project = not feat.get("is_global", True)

                                            cb = ui.checkbox(
                                                fname,
                                                value=(fid in state["feature_ids"]),
                                            )
                                            feature_checkbox_refs[fid] = cb

                                            _fdesc = (feat.get("description") or "").strip()
                                            ui.label(_fdesc or "—").classes(
                                                "text-caption text-grey"
                                            ).style("white-space: normal; line-height: 1.25;")

                                            ui.label(f"x{fweight:.1f}").classes("text-center")

                                            new_cb = ui.checkbox(
                                                "New",
                                                value=(fid in state["new_feature_ids"]),
                                            ).props("dense color=orange").classes("text-caption")
                                            new_feat_checkbox_refs[fid] = new_cb

                                            if _is_project:
                                                with ui.row().classes("items-center gap-1 justify-center"):
                                                    ui.badge("project", color="orange").props("dense")
                                                    ui.button(icon="edit",
                                                              on_click=lambda _e=None, f=feat: _edit_custom_feature(f)) \
                                                        .props("flat dense round size=sm color=primary") \
                                                        .tooltip("Edit this project feature")
                                            else:
                                                ui.label("").classes("text-center")

                                            def _make_sync(f_id: int, n_cb: ui.checkbox):
                                                def _sync(e) -> None:
                                                    if not feature_checkbox_refs[f_id].value:
                                                        n_cb.value = False
                                                    _update_select_all_state()
                                                return _sync

                                            cb.on("update:model-value", _make_sync(fid, new_cb))

                        _rebuild_feature_list()
                        await _refresh_presets()

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
                                # Rebuild DUT/Profile lists with current product type filter
                                _rebuild_dut_prof_lists()
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

                        dut_pt_info = ui.label("").classes("text-caption text-primary q-mb-sm")

                        dut_cb_refs: dict[int, ui.checkbox] = {}
                        prof_cb_refs: dict[int, ui.checkbox] = {}
                        matrix_cb_refs: dict[tuple[int, int], ui.checkbox] = {}
                        # Order: DUTs, then Profiles, then the combination matrix
                        # below them (matrix last so long DUT lists don't push it
                        # far down / force excessive scrolling to reach profiles).
                        dut_container = ui.column().classes("w-full")
                        prof_container = ui.column().classes("w-full")
                        matrix_container = ui.column().classes("w-full q-mt-md")

                        def _rebuild_matrix() -> None:
                            """Repaint the DUT×Profile combination grid."""
                            matrix_container.clear()
                            # Apply product type filter to matrix
                            _mpt = state.get("product_type_filter") or "All"
                            if _mpt and _mpt != "All":
                                _m_duts = [d for d in all_duts if d.get("product_type") == _mpt or not d.get("product_type")]
                                _m_profs = [p for p in all_profiles if p.get("product_type") == _mpt or not p.get("product_type")]
                            else:
                                _m_duts = all_duts
                                _m_profs = all_profiles
                            sel_duts = [
                                d for d in _m_duts if dut_cb_refs.get(d["id"]) and dut_cb_refs[d["id"]].value
                            ]
                            sel_profs = [
                                p for p in _m_profs if prof_cb_refs.get(p["id"]) and prof_cb_refs[p["id"]].value
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
                                # Wrap the matrix in a horizontally scrollable container so
                                # wide DUT×Profile grids scroll on narrow screens instead of
                                # breaking the layout.
                                with ui.element("div").classes("w-full").style(
                                    "overflow-x: auto; -webkit-overflow-scrolling: touch;"
                                ):
                                    with ui.grid(columns=n_cols).classes("items-center"):
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

                        def _rebuild_dut_prof_lists() -> None:
                            """Rebuild DUT and Profile checkbox lists filtered by product type."""
                            # Preserve current selections
                            for _did, _cb in dut_cb_refs.items():
                                if _cb.value and _did not in state["dut_ids"]:
                                    state["dut_ids"].append(_did)
                                elif not _cb.value and _did in state["dut_ids"]:
                                    state["dut_ids"].remove(_did)
                            for _pid, _cb in prof_cb_refs.items():
                                if _cb.value and _pid not in state["profile_ids"]:
                                    state["profile_ids"].append(_pid)
                                elif not _cb.value and _pid in state["profile_ids"]:
                                    state["profile_ids"].remove(_pid)

                            dut_cb_refs.clear()
                            prof_cb_refs.clear()
                            dut_container.clear()
                            prof_container.clear()

                            selected_pt = state.get("product_type_filter") or "All"
                            if selected_pt and selected_pt != "All":
                                visible_duts = [d for d in all_duts if d.get("product_type") == selected_pt or not d.get("product_type")]
                                visible_profs = [p for p in all_profiles if p.get("product_type") == selected_pt or not p.get("product_type")]
                                dut_pt_info.set_text(f"Filtered by product type: {selected_pt} (items without product type are also shown)")
                            else:
                                visible_duts = list(all_duts)
                                visible_profs = list(all_profiles)
                                dut_pt_info.set_text("")

                            with dut_container:
                                if not visible_duts:
                                    ui.label("No DUT types found.").classes("text-grey")
                                else:
                                    ui.label("DUT Types").classes("text-subtitle2 q-mb-xs")
                                    with ui.element("div").classes("w-full q-mb-md").style("max-height: 250px; overflow-y: auto;"):
                                        with ui.element("table").classes("w-full").style("border-collapse: collapse;"):
                                            for dut in visible_duts:
                                                did = dut["id"]
                                                with ui.element("tr").style("border-bottom: 1px solid rgba(128,128,128,0.2);"):
                                                    with ui.element("td").style("padding: 2px 4px; width: 40px;"):
                                                        cb = ui.checkbox(
                                                            "",
                                                            value=(did in state["dut_ids"]),
                                                        ).props("dense")
                                                        dut_cb_refs[did] = cb
                                                        cb.on("update:model-value", lambda _: _rebuild_matrix())
                                                    with ui.element("td").style("padding: 2px 4px;"):
                                                        ui.label(dut.get("name", f"DUT {did}")).classes("text-body2")
                                                    with ui.element("td").style("padding: 2px 4px;"):
                                                        ui.label(dut.get("category", "")).classes("text-caption text-grey")

                            with prof_container:
                                if not visible_profs:
                                    ui.label("No profiles found.").classes("text-grey")
                                else:
                                    ui.label("Test Profiles").classes("text-subtitle2 q-mb-xs")
                                    with ui.element("div").classes("w-full q-mb-md").style("max-height: 200px; overflow-y: auto;"):
                                        with ui.element("table").classes("w-full").style("border-collapse: collapse;"):
                                            for prof in visible_profs:
                                                pid = prof["id"]
                                                with ui.element("tr").style("border-bottom: 1px solid rgba(128,128,128,0.2);"):
                                                    with ui.element("td").style("padding: 2px 4px; width: 40px;"):
                                                        cb = ui.checkbox(
                                                            "",
                                                            value=(pid in state["profile_ids"]),
                                                        ).props("dense")
                                                        prof_cb_refs[pid] = cb
                                                        cb.on("update:model-value", lambda _: _rebuild_matrix())
                                                    with ui.element("td").style("padding: 2px 4px;"):
                                                        ui.label(prof.get("name", f"Profile {pid}")).classes("text-body2")

                            _rebuild_matrix()

                        # Initial render
                        _rebuild_dut_prof_lists()

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

                        with ui.card().classes("w-full q-pa-sm q-mb-md").props("flat bordered"):
                            ui.label("PR Fix Calculation:").classes("text-caption text-weight-bold")
                            for _info_line in [
                                "Each PR is validated per DUT (scales with DUT count)",
                                "Simple: 2h x DUT count, Medium: 4h x DUT count, Complex: 8h x DUT count",
                                "Total PR Fix Hours = (simple x 2 + medium x 4 + complex x 8) x DUT_count [x profile_count if enabled]",
                                "Configurable via 'pr_fix_base_hours' and 'pr_scales_with_profile' settings",
                            ]:
                                ui.label(f"  {_info_line}").classes("text-caption text-grey")

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
                                        with ui.card().classes("w-full q-pa-xs q-mb-xs").props("flat bordered"):
                                            with ui.row().classes("items-center q-gutter-sm w-full"):
                                                _num = ui.input("PR #", value=pr.get("pr_number", "")).classes("w-24")
                                                _link = ui.input("Link", value=pr.get("link", "")).classes("flex-1")
                                                _pri_opts = list(_pr_priority_list)
                                                _pri_val = pr.get("priority", _pri_opts[1] if len(_pri_opts) > 1 else _pri_opts[0])
                                                if _pri_val not in _pri_opts:
                                                    _pri_opts.append(_pri_val)
                                                _pri = ui.select(
                                                    options=_pri_opts,
                                                    value=_pri_val,
                                                    label="Priority",
                                                ).classes("w-28")
                                                _cx_opts = ["simple", "medium", "complex"]
                                                _cx_val = pr.get("complexity", "simple")
                                                if _cx_val not in _cx_opts:
                                                    _cx_opts.append(_cx_val)
                                                _cx = ui.select(
                                                    options=_cx_opts,
                                                    value=_cx_val,
                                                    label="Complexity",
                                                ).classes("w-32")
                                                _st_options = ["Open", "In Progress", "Postponed", "Merged", "Closed"]
                                                _st_val = pr.get("status", "Open")
                                                if _st_val not in _st_options:
                                                    _st_options.append(_st_val)
                                                _st = ui.select(
                                                    options=_st_options,
                                                    value=_st_val,
                                                    label="Status",
                                                ).classes("w-28")

                                                def _make_remove(i: int):
                                                    def _remove():
                                                        pr_detail_rows.pop(i)
                                                        _render_pr_details()
                                                    return _remove

                                                ui.button(icon="close", on_click=_make_remove(idx)).props("flat dense round color=negative size=sm")

                                            with ui.row().classes("items-center q-gutter-sm w-full"):
                                                _ta = ui.switch(
                                                    "Test Available",
                                                    value=pr.get("test_available", True),
                                                )
                                            # Description is collapsible (collapsed by default) — it can
                                            # hold many lines of Markdown / Jira-macro text.
                                            with ui.expansion("Description", icon="notes") \
                                                    .classes("w-full").props("dense"):
                                                _desc = ui.textarea(
                                                    value=pr.get("description", ""),
                                                    placeholder="Supports Markdown and Jira macros, e.g. {color:#de350b}text{color}, 9{^}th{^}",
                                                ).classes("w-full").props("autogrow")

                                            # Bind updates back to data
                                            def _make_updater(i: int, n=_num, l=_link, p=_pri, c=_cx, s=_st, d=_desc, ta=_ta):
                                                def _upd(_=None):
                                                    if i < len(pr_detail_rows):
                                                        pr_detail_rows[i] = {
                                                            "pr_number": n.value or "",
                                                            "link": l.value or "",
                                                            "priority": p.value or "",
                                                            "complexity": c.value or "simple",
                                                            "status": s.value or "Open",
                                                            "description": d.value or "",
                                                            "test_available": bool(ta.value),
                                                        }
                                                return _upd

                                            updater = _make_updater(idx)
                                            _num.on("update:model-value", updater)
                                            _link.on("update:model-value", updater)
                                            _pri.on("update:model-value", updater)
                                            _cx.on("update:model-value", updater)
                                            _st.on("update:model-value", updater)
                                            _desc.on("update:model-value", updater)
                                            _ta.on("update:model-value", updater)

                            def _add_pr_detail() -> None:
                                _default_pri = _pr_priority_list[1] if len(_pr_priority_list) > 1 else _pr_priority_list[0]
                                pr_detail_rows.append({"pr_number": "", "link": "", "priority": _default_pri, "complexity": "simple", "status": "Open", "description": "", "test_available": True})
                                _render_pr_details()

                            with ui.row().classes("items-center gap-2"):
                                ui.button("Add PR Detail", icon="add", on_click=_add_pr_detail).props("flat dense color=primary")

                                async def _import_from_jira(
                                    _pr_rows=pr_detail_rows,
                                    _render=_render_pr_details,
                                ) -> None:
                                    """Open dialog to fetch and import PR items from Jira."""
                                    try:
                                        jira_config = await api_get("/integrations/JIRA")
                                        if not jira_config.get("enabled"):
                                            ui.notify("Jira integration is not enabled.", type="warning")
                                            return
                                    except Exception:
                                        ui.notify("Jira integration not configured.", type="warning")
                                        return

                                    with ui.dialog().props("maximized=false") as dlg, \
                                            ui.card().classes("w-[1100px] max-w-[95vw] max-h-[85vh]") \
                                            .style("display:flex; flex-direction:column;"):
                                        # Header (fixed)
                                        with ui.row().classes("items-center w-full q-mb-sm").style("flex:0 0 auto;"):
                                            ui.label("Import PR Items from Registry").classes("text-h6")
                                            ui.element("div").classes("ed-toolbar-grow")
                                            _fetch_btn = ui.button("Reload", icon="refresh").props("color=secondary flat dense")
                                        ui.label(
                                            "PR items from the registry (configured PR JQL filter)."
                                        ).classes("text-caption text-grey q-mb-sm").style("flex:0 0 auto;")

                                        # Scrollable list area
                                        with ui.element("div").classes("w-full").style(
                                            "flex:1 1 auto; overflow:auto; min-height:0;"
                                        ):
                                            jira_items_table = ui.table(
                                                columns=[
                                                    {"name": "key", "label": "Key", "field": "key", "align": "left", "sortable": True},
                                                    {"name": "summary", "label": "Summary", "field": "summary", "align": "left"},
                                                    {"name": "description", "label": "Description", "field": "description", "align": "left"},
                                                    {"name": "priority", "label": "Priority", "field": "priority", "align": "left", "sortable": True},
                                                    {"name": "status", "label": "Status", "field": "status", "align": "left", "sortable": True},
                                                ],
                                                rows=[],
                                                row_key="key",
                                                selection="multiple",
                                                pagination={"rowsPerPage": 10},
                                            ).classes("w-full")

                                        async def _fetch_jira_prs() -> None:
                                            # Load from the PR registry (configured PR JQL + PR token).
                                            items = await api_get("/integrations/JIRA/pr-items")
                                            jira_items_table.rows = items if isinstance(items, list) else []
                                            jira_items_table.update()
                                            ui.notify(f"Loaded {len(jira_items_table.rows)} PR item(s).", type="positive")

                                        _fetch_btn.on("click", run_async(
                                            _fetch_btn, _fetch_jira_prs, error_prefix="Failed to load"))

                                        async def _import_selected() -> None:
                                            selected = jira_items_table.selected
                                            if not selected:
                                                ui.notify("No items selected.", type="warning")
                                                return
                                            imported = 0
                                            for item in selected:
                                                key = item.get("key", "")
                                                existing_nums = {r.get("pr_number") for r in _pr_rows}
                                                if key and key not in existing_nums:
                                                    priority = (item.get("priority") or "Medium").lower()
                                                    complexity = "simple"
                                                    if priority in ("high", "highest", "critical", "blocker"):
                                                        complexity = "complex"
                                                    elif priority in ("medium",):
                                                        complexity = "medium"
                                                    # Prefer the registry-provided link; the description
                                                    # falls back to the summary when empty.
                                                    jira_link = item.get("link") or ""
                                                    desc = item.get("description") or item.get("summary", "")
                                                    _pr_rows.append({
                                                        "pr_number": key,
                                                        "link": jira_link,
                                                        "description": desc,
                                                        "priority": item.get("priority", "Medium"),
                                                        "complexity": complexity,
                                                        "status": item.get("status", "Open"),
                                                        "test_available": True,
                                                    })
                                                    imported += 1
                                            _render()
                                            ui.notify(f"Imported {imported} PR item(s).", type="positive")
                                            dlg.close()

                                        # Pinned footer (fixed, never scrolls)
                                        with ui.row().classes("q-mt-md gap-2 w-full justify-end").style(
                                            "flex:0 0 auto; border-top:1px solid var(--ed-line); padding-top:12px;"
                                        ):
                                            ui.button("Cancel", on_click=dlg.close).props("flat")
                                            _import_btn = ui.button("Import Selected", icon="download").props("color=primary")
                                            _import_btn.on("click", run_async(
                                                _import_btn, _import_selected, error_prefix="Import failed"))

                                    try:
                                        await _fetch_jira_prs()
                                    except Exception as exc:
                                        notify_error(exc, "Failed to load")
                                    dlg.open()

                                ui.button("Import from Jira", icon="bug_report", on_click=_import_from_jira).props("flat dense color=secondary")

                            _render_pr_details()

                        # -- Documentation Deliverables --
                        ui.separator().classes("q-mt-lg")
                        with ui.expansion("Documentation Deliverables", icon="description").classes("w-full"):
                            ui.label(
                                "Select document types to be created and specify the count for each. "
                                "Document effort hours are added to the total estimation."
                            ).classes("text-body2 text-grey q-mb-sm")

                            doc_types_container = ui.column().classes("w-full")
                            doc_cb_refs: dict[int, ui.checkbox] = {}
                            doc_count_refs: dict[int, ui.number] = {}

                            async def _load_doc_types() -> None:
                                try:
                                    doc_types = await api_get("/document-types")
                                except Exception:
                                    doc_types = []
                                doc_types_container.clear()
                                doc_cb_refs.clear()
                                doc_count_refs.clear()
                                saved_ids = state.get("document_type_ids", [])
                                saved_counts = state.get("document_counts", {})
                                with doc_types_container:
                                    if not doc_types:
                                        ui.label("No document types configured.").classes("text-grey")
                                        return
                                    with ui.grid(columns="1fr 120px 200px").classes("w-full q-pl-md items-center"):
                                        ui.label("Document Type").classes("text-caption text-grey")
                                        ui.label("Count").classes("text-caption text-grey text-center")
                                        ui.label("Base Hours (each)").classes("text-caption text-grey")
                                        for dt in doc_types:
                                            did = dt["id"]
                                            cb = ui.checkbox(
                                                dt.get("name", ""),
                                                value=(did in saved_ids),
                                            )
                                            doc_cb_refs[did] = cb
                                            cnt = ui.number(
                                                "",
                                                value=int(saved_counts.get(str(did), 1)),
                                                min=1, step=1, precision=0,
                                            ).props("dense").classes("w-20")
                                            doc_count_refs[did] = cnt
                                            ui.label(f"{dt.get('base_effort_hours', 0):.1f}h").classes("text-caption")

                            await _load_doc_types()

                        def _collect_prs() -> None:
                            state["pr_simple"] = int(pr_simple_input.value or 0)
                            state["pr_medium"] = int(pr_medium_input.value or 0)
                            state["pr_complex"] = int(pr_complex_input.value or 0)
                            state["pr_details"] = [pr for pr in pr_detail_rows if pr.get("pr_number")]
                            # Collect document types
                            state["document_type_ids"] = [did for did, cb in doc_cb_refs.items() if cb.value]
                            state["document_counts"] = {
                                str(did): int(cnt.value or 1) for did, cnt in doc_count_refs.items()
                            }

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
                            with ui.input(
                                _config_map.get("label_project_start_date") or "Project Start Date - T0 (optional)",
                                value=state.get("start_date") or "",
                            ).classes("flex-1") as start_date_input:
                                with ui.menu() as start_menu:
                                    with ui.date().bind_value(start_date_input) as _start_dp:
                                        _start_dp.on("update:model-value", lambda: start_menu.close())
                                with start_date_input.add_slot("append"):
                                    ui.icon("edit_calendar").on("click", start_menu.open).classes("cursor-pointer")

                            with ui.input(
                                _config_map.get("label_testing_start_date") or "Testing Start Date (optional)",
                                value=state.get("testing_start_date") or "",
                            ).classes("flex-1") as testing_start_input:
                                with ui.menu() as testing_start_menu:
                                    with ui.date().bind_value(testing_start_input) as _testing_dp:
                                        _testing_dp.on("update:model-value", lambda: testing_start_menu.close())
                                with testing_start_input.add_slot("append"):
                                    ui.icon("edit_calendar").on("click", testing_start_menu.open).classes("cursor-pointer")

                            with ui.input(
                                _config_map.get("label_deadline") or "Deadline (optional)",
                                value=state.get("delivery_date") or "",
                            ).classes("flex-1") as delivery_input:
                                with ui.menu() as delivery_menu:
                                    with ui.date().bind_value(delivery_input) as _delivery_dp:
                                        _delivery_dp.on("update:model-value", lambda: delivery_menu.close())
                                with delivery_input.add_slot("append"):
                                    ui.icon("edit_calendar").on("click", delivery_menu.open).classes("cursor-pointer")

                        working_days_input = ui.number(
                            "Working Days Available",
                            value=state["working_days"],
                            min=1,
                            step=1,
                            precision=0,
                        ).classes("w-full q-mt-sm")

                        ui.label(
                            "Used only for the feasibility / capacity check — it does NOT "
                            "change the calculated effort. The proposed delivery duration is "
                            "the Proposed Duration (elapsed) shown at the Review step."
                        ).classes("text-caption text-grey q-mt-xs")

                        auto_calc_label = ui.label("").classes("text-caption text-primary q-mt-xs")

                        def _auto_calc_working_days() -> None:
                            sd = testing_start_input.value
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

                        testing_start_input.on("update:model-value", lambda _: _auto_calc_working_days())
                        delivery_input.on("update:model-value", lambda _: _auto_calc_working_days())

                        team_size_input = ui.number(
                            "Team Size (testers)",
                            value=state["team_size"],
                            min=1,
                            step=1,
                            precision=0,
                        ).classes("w-full q-mt-sm")
                        _team_size_error = ui.label("Team size must be at least 1.").classes(
                            "text-negative text-caption"
                        )
                        _team_size_error.set_visibility(False)
                        team_size_input.on(
                            "update:model-value",
                            lambda e: _team_size_error.set_visibility(
                                not ((e.args or 0) and int(e.args) >= 1)
                            ),
                        )

                        leader_toggle = ui.switch(
                            "Include Test Leader effort",
                            value=state["has_leader"],
                        ).classes("q-mt-sm")

                        releases_input = ui.number(
                            "Expected Releases",
                            value=state["expected_releases"],
                            min=1,
                            step=1,
                            precision=0,
                        ).classes("w-full q-mt-sm").tooltip(
                            "Number of releases within this estimation period. "
                            "Each additional release adds extra effort for regression and deployment."
                        )

                        # Team selector
                        if all_teams:
                            ui.separator().classes("q-mt-md")
                            ui.label("Team (optional)").classes("text-subtitle2 q-mt-sm")
                            team_options = {t["id"]: t.get("name", f"Team {t['id']}") for t in all_teams}
                            team_select = ui.select(
                                options={None: "-- No Team --", **team_options},
                                value=state.get("team_id"),
                                label="Select Team",
                                with_input=True,
                                clearable=True,
                            ).classes("w-full q-mb-sm")

                            def _on_team_selected(e) -> None:
                                selected_team_id = e.args
                                state["team_id"] = selected_team_id if selected_team_id else None
                                if selected_team_id and all_team_members:
                                    # Auto-populate allocation rows from team members
                                    team_members = [m for m in all_team_members if m.get("team_id") == selected_team_id]
                                    alloc_rows.clear()
                                    for m in team_members:
                                        alloc_rows.append({
                                            "team_member_id": m["id"],
                                            "role": m.get("role", "TESTER"),
                                            "allocated_hours": 0,
                                        })
                                    _render_alloc()

                            team_select.on("update:model-value", _on_team_selected)

                        # Team allocation picker
                        if all_team_members:
                            ui.separator().classes("q-mt-md")
                            ui.label("Team Allocation (optional)").classes("text-subtitle2 q-mt-sm")

                            with ui.card().classes("w-full q-pa-sm q-mb-sm").props("flat bordered"):
                                ui.label("How team parameters affect the calculation:").classes("text-caption text-weight-bold")
                                for line in [
                                    "Team Size and Include Leader determine capacity (= working_days x (testers + leader) x hours/day) for feasibility.",
                                    "Feasibility: <=80% = Feasible, 80-100% = At Risk, >100% = Not Feasible.",
                                    "Team Allocation below is optional planning metadata — it records who works on the estimation but does not change calculated totals.",
                                ]:
                                    ui.label(f"- {line}").classes("text-caption text-grey")

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

                        # Risk items selection
                        risk_cb_refs: dict[int, ui.checkbox] = {}
                        if all_risk_items:
                            ui.separator().classes("q-mt-md")
                            ui.label("Risk Items (optional)").classes("text-subtitle2 q-mt-sm")
                            ui.label("Select applicable risks for this estimation.").classes("text-body2 text-grey q-mb-sm")

                            # Group risk items by category
                            risks_by_cat: dict[str, list[dict]] = {}
                            for ri in all_risk_items:
                                rcat = ri.get("category") or "General"
                                risks_by_cat.setdefault(rcat, []).append(ri)

                            for rcat_name, rcat_items in risks_by_cat.items():
                                ui.label(rcat_name).classes("text-caption text-weight-bold text-primary q-mt-xs")
                                for ri in rcat_items:
                                    rid = ri["id"]
                                    rlabel = ri.get("name", f"Risk {rid}")
                                    if ri.get("likelihood") or ri.get("impact"):
                                        rlabel += f"  [{ri.get('likelihood', '?')}/{ri.get('impact', '?')}]"
                                    rcb = ui.checkbox(
                                        rlabel,
                                        value=(rid in state.get("risk_item_ids", [])),
                                    )
                                    risk_cb_refs[rid] = rcb

                        def _collect_delivery() -> None:
                            raw_start = start_date_input.value
                            state["start_date"] = raw_start if raw_start else None
                            raw_testing_start = testing_start_input.value
                            state["testing_start_date"] = raw_testing_start if raw_testing_start else None
                            raw = delivery_input.value
                            state["delivery_date"] = raw if raw else None
                            state["working_days"] = int(working_days_input.value or 20)
                            state["team_size"] = int(team_size_input.value or 1)
                            state["has_leader"] = bool(leader_toggle.value)
                            state["expected_releases"] = int(releases_input.value or 1)
                            if all_team_members:
                                state["team_allocations"] = [
                                    a for a in alloc_rows if a.get("team_member_id")
                                ]
                            state["risk_item_ids"] = [
                                rid for rid, rcb in risk_cb_refs.items() if rcb.value
                            ]

                        with ui.stepper_navigation():
                            def _back_step6() -> None:
                                _collect_delivery()
                                stepper.previous()

                            def _next_step6() -> None:
                                _collect_delivery()
                                if state["team_size"] < 1:
                                    _team_size_error.set_visibility(True)
                                    ui.notify("Team size must be at least 1.", type="warning")
                                    return
                                _team_size_error.set_visibility(False)
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
                        custom_feat_container = ui.column().classes("w-full q-mb-md")
                        result_container = ui.column().classes("w-full")

                        _can_promote_new = has_permission("APPROVER")

                        async def _request_global(feat: dict) -> None:
                            try:
                                updated = await api_post(f"/features/{feat['id']}/request-promotion")
                            except Exception as exc:
                                ui.notify(f"Request failed: {exc}", type="negative")
                                return
                            feat["promotion_requested"] = updated.get("promotion_requested", True)
                            _render_custom_features()
                            ui.notify(f"Requested adding '{feat.get('name')}' to the global catalog.", type="positive")

                        async def _promote_global(feat: dict) -> None:
                            try:
                                updated = await api_put(f"/features/{feat['id']}/promote")
                            except Exception as exc:
                                ui.notify(f"Promote failed: {exc}", type="negative")
                                return
                            feat["is_global"] = updated.get("is_global", True)
                            feat["owner_estimation_id"] = updated.get("owner_estimation_id")
                            feat["promotion_requested"] = False
                            _render_custom_features()
                            ui.notify(f"'{feat.get('name')}' is now a global feature.", type="positive")

                        def _render_custom_features() -> None:
                            """Show this estimation's custom (project) features with a
                            request-to-global action (or promote, for approvers)."""
                            custom_feat_container.clear()
                            project_feats = [
                                f for f in all_features
                                if not f.get("is_global", True)
                                and f.get("owner_estimation_id") == state.get("autosave_id")
                            ]
                            if not project_feats:
                                return
                            with custom_feat_container:
                                ui.label("Custom features for this project").classes("text-subtitle1 q-mb-xs")
                                ui.label(
                                    "These exist only in this estimation. Request adding any of them to the "
                                    "global catalog for future reuse."
                                ).classes("text-caption text-grey q-mb-xs")
                                for f in project_feats:
                                    with ui.row().classes("items-center gap-2 w-full"):
                                        ui.label(f.get("name", "")).classes("text-body2")
                                        cat = f.get("category")
                                        if cat:
                                            ui.label(f"· {cat}").classes("text-caption text-grey")
                                        ui.element("div").classes("ed-toolbar-grow")
                                        if _can_promote_new:
                                            ui.button("Promote to global", icon="public",
                                                      on_click=lambda _e=None, ff=f: _promote_global(ff)) \
                                                .props("flat dense color=primary")
                                        elif f.get("promotion_requested"):
                                            ui.badge("requested", color="positive").props("dense")
                                        else:
                                            ui.button("Request to add to global", icon="upgrade",
                                                      on_click=lambda _e=None, ff=f: _request_global(ff)) \
                                                .props("outline dense color=primary")

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
                                    releases = state.get("expected_releases", 1)
                                    if releases and releases > 1:
                                        with ui.card().classes("q-pa-sm"):
                                            ui.label("Expected Releases").classes("text-caption text-grey")
                                            ui.label(str(releases)).classes("text-body2")
                                    if state.get("project_goals"):
                                        with ui.card().classes("q-pa-sm"):
                                            ui.label("Project Goals").classes("text-caption text-grey")
                                            ui.label(state["project_goals"]).classes("text-body2")
                                    if state.get("target_customer"):
                                        with ui.card().classes("q-pa-sm"):
                                            ui.label("Target Customer").classes("text-caption text-grey")
                                            ui.label(state["target_customer"]).classes("text-body2")
                            _render_custom_features()

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
                                    if res.get("pr_no_test_hours", 0) > 0:
                                        _hours_card("PR Test Creation", res["pr_no_test_hours"], "science")
                                    _hours_card("Study Hours", res.get("study_hours", 0), "school")
                                    if res.get("release_extra_hours", 0) > 0:
                                        _hours_card("Release Extra Hours", res["release_extra_hours"], "rocket_launch")
                                    if res.get("documentation_hours", 0) > 0:
                                        _hours_card("Documentation Hours", res["documentation_hours"], "description")
                                    _hours_card("Buffer Hours", res.get("buffer_hours", 0), "security")
                                    _hours_card("Grand Total Hours", res.get("grand_total_hours", 0), "summarize")
                                    _gt_days = res.get("grand_total_days", 0)
                                    _hours_card("Grand Total (Person-Days)", _gt_days, "calendar_today")
                                    _ww = round(_gt_days / 5.0, 1) if _gt_days else 0
                                    if _ww > 0:
                                        _hours_card("Working Weeks", _ww, "date_range")
                                    _cap = res.get("capacity_hours", 0)
                                    if _cap > 0:
                                        _hours_card("Capacity Hours", _cap, "fitness_center")

                                # Elapsed time (wall-clock estimate)
                                _el_days = res.get("elapsed_days", 0)
                                _el_weeks = res.get("elapsed_weeks", 0)
                                if _el_days > 0:
                                    ui.separator().classes("q-mt-sm")
                                    ui.label("Proposed Duration (elapsed, wall-clock)").classes("text-subtitle2 q-mt-xs q-mb-xs")
                                    ui.label(
                                        "The actual time to deliver given the team — use this as the "
                                        "estimation proposal. Parallelizable tasks are divided by team "
                                        "size; sequential tasks are not. (Working Days Available is only "
                                        "a feasibility input and does not affect this.)"
                                    ).classes("text-caption text-grey q-mb-xs")
                                    with ui.row().classes("q-gutter-md flex-wrap q-mb-sm"):
                                        _hours_card("Elapsed Hours", res.get("elapsed_hours", 0), "hourglass_top")
                                        _hours_card("Elapsed Days", _el_days, "today")
                                        _hours_card("Elapsed Weeks", _el_weeks, "date_range")

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
                                    # Initialise per-task assigned_testers in state
                                    if "task_assigned_testers" not in state:
                                        state["task_assigned_testers"] = {}
                                    for t in tasks:
                                        t["assigned_testers"] = state["task_assigned_testers"].get(t["name"], 1)
                                    ui.label("Task Breakdown").classes("text-subtitle2 q-mt-sm q-mb-xs")
                                    task_cols = [
                                        {"name": "feature_name", "label": "Feature", "field": "feature_name", "align": "left", "sortable": True},
                                        {"name": "name", "label": "Task", "field": "name", "align": "left", "sortable": True},
                                        {"name": "task_type", "label": "Type", "field": "task_type", "align": "left"},
                                        {"name": "base_hours", "label": "Base h", "field": "base_hours", "align": "right"},
                                        {"name": "formula", "label": "Formula", "field": "formula", "align": "left"},
                                        {"name": "calculated_hours", "label": "Calc h", "field": "calculated_hours", "align": "right"},
                                        {"name": "assigned_testers", "label": "Resources", "field": "assigned_testers", "align": "center"},
                                    ]
                                    _tbl = ui.table(
                                        columns=task_cols,
                                        rows=tasks,
                                        row_key="name",
                                        pagination={"rowsPerPage": 15},
                                    ).classes("w-full shadow-1")
                                    _tbl.add_slot(
                                        "body-cell-feature_name",
                                        r"""
                                        <q-td :props="props">
                                            <q-badge v-if="props.value" outline color="primary" :label="props.value" />
                                            <span v-else class="text-grey-5 text-italic">Global</span>
                                        </q-td>
                                        """,
                                    )
                                    _tbl.add_slot(
                                        "body-cell-assigned_testers",
                                        r"""
                                        <q-td :props="props">
                                            <q-input
                                                v-model.number="props.row.assigned_testers"
                                                type="number"
                                                dense
                                                outlined
                                                :min="1"
                                                style="max-width: 70px"
                                                @update:model-value="(v) => $parent.$emit('update_testers', {name: props.row.name, value: v})"
                                            />
                                        </q-td>
                                        """,
                                    )
                                    _tbl.on(
                                        "update_testers",
                                        lambda e: state["task_assigned_testers"].update(
                                            {e.args["name"]: max(1, int(e.args["value"] or 1))}
                                        ),
                                    )

                        async def run_calculate() -> None:
                            """Call POST /estimations/calculate and render the result."""
                            # Re-entrancy + double-submit guard: disable the button and
                            # show Quasar's loading spinner for the duration of the call,
                            # but keep the inline result rendering that follows.
                            if getattr(calc_btn, "_busy", False):
                                return
                            calc_btn._busy = True
                            calc_btn.enabled = False
                            calc_btn.props("loading")
                            try:
                                await _run_calculate_body()
                            finally:
                                calc_btn._busy = False
                                calc_btn.enabled = True
                                calc_btn.props(remove="loading")

                        async def _run_calculate_body() -> None:
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
                                "expected_releases": state.get("expected_releases", 1),
                                "risk_item_ids": state.get("risk_item_ids", []),
                                "document_type_ids": state.get("document_type_ids", []),
                                "document_counts": state.get("document_counts", {}),
                            }
                            try:
                                result = await api_post("/estimations/calculate", json=payload)
                                state["calc_result"] = result
                                _render_result(result)
                                ui.notify("Calculation complete.", type="positive")
                            except Exception as exc:
                                ui.notify(f"Calculation failed: {exc}", type="negative")

                        async def save_estimation() -> None:
                            """Persist the estimation and navigate to its detail page.

                            Reuses the autosaved draft when one exists so we never create a
                            duplicate of the in-progress work."""
                            if state["calc_result"] is None:
                                ui.notify("Run Calculate first.", type="warning")
                                return

                            payload = _build_persist_payload()
                            if state["autosave_id"] is not None:
                                await api_put(f"/estimations/{state['autosave_id']}/draft", json=payload)
                                est_id = state["autosave_id"]
                            else:
                                saved = await api_post("/estimations", json=payload)
                                est_id = saved["id"]
                                state["autosave_id"] = est_id
                            ui.notify(f"Estimation saved (ID {est_id}).", type="positive")
                            ui.navigate.to(f"/estimation/{est_id}")

                        # Render initial summary when the wizard reaches this step
                        _render_summary()

                        with ui.stepper_navigation():
                            ui.button("Back", on_click=lambda: stepper.previous()).props("flat")
                            calc_btn = ui.button(
                                "Calculate",
                                icon="calculate",
                                on_click=run_calculate,
                            ).props("color=secondary")
                            save_btn = ui.button(
                                "Save Estimation",
                                icon="save",
                            ).props("color=primary")
                            save_btn.on("click", run_async(
                                save_btn, save_estimation, error_prefix="Save failed"))


        # ---------------------------------------------------------------------------
        # Route 2: /estimation/{id}  — Estimation detail view
        # ---------------------------------------------------------------------------

                # ── Summary rail (sibling of stepper inside ed-wizard-grid) ──
                summary_rail = ui.element("div").classes("ed-summary-rail")

            # ── Live updaters for progress + summary rail ──────────
            def _render_steps() -> None:
                current_name = stepper.value or WIZARD_STEPS[0][0]
                current_idx = next(
                    (i for i, s in enumerate(WIZARD_STEPS) if s[0] == current_name), 0
                )
                progress_container.clear()
                with progress_container:
                    for i, (step_name, label_text) in enumerate(WIZARD_STEPS):
                        cls = "ed-progress-step"
                        if i < current_idx:
                            cls += " done"
                        elif i == current_idx:
                            cls += " active"
                        step_el = ui.element("div").classes(cls)
                        # Allow jumping to any step directly (non-sequential nav),
                        # not only completed/current steps.
                        step_el.on("click",
                                   lambda _, n=step_name: stepper.set_value(n))
                        with step_el:
                            with ui.element("div").classes("ed-progress-num"):
                                if i < current_idx:
                                    ui.icon("check").style("font-size: 16px;")
                                else:
                                    ui.label(str(i + 1))
                            ui.label(label_text).classes("ed-progress-label")

            def _render_rail() -> None:
                summary_rail.clear()
                with summary_rail:
                    ui.label("Estimation").classes("ed-eyebrow")
                    ui.label(state.get("project_name") or "Untitled estimation") \
                        .classes("ed-summary-title")

                    def _row(label_txt: str, value: str, empty: bool = False) -> None:
                        with ui.element("div").classes("ed-summary-row"):
                            ui.label(label_txt).classes("ed-summary-label")
                            cls = "ed-summary-value empty" if empty else "ed-summary-value"
                            ui.label(value).classes(cls)

                    with ui.element("div").classes("ed-summary-section"):
                        _row("Type",     state.get("project_type") or "—",
                             empty=not state.get("project_type"))
                        _row("Customer", state.get("target_customer") or "—",
                             empty=not state.get("target_customer"))
                        if state.get("product_type_filter") and state["product_type_filter"] != "All":
                            _row("Product", state["product_type_filter"])

                    with ui.element("div").classes("ed-summary-section"):
                        fids = state.get("feature_ids") or []
                        nfids = state.get("new_feature_ids") or []
                        refs = state.get("reference_project_ids") or []
                        _row("Features",   str(len(fids)) if fids else "—",   empty=not fids)
                        _row("New Feat.",  str(len(nfids)) if nfids else "—", empty=not nfids)
                        _row("References", str(len(refs)) if refs else "—",   empty=not refs)

                    with ui.element("div").classes("ed-summary-section"):
                        duts = state.get("dut_ids") or []
                        profs = state.get("profile_ids") or []
                        _row("DUTs",     str(len(duts)) if duts else "—",   empty=not duts)
                        _row("Profiles", str(len(profs)) if profs else "—", empty=not profs)

                    with ui.element("div").classes("ed-summary-section"):
                        pr_t = (state.get("pr_simple") or 0) + \
                               (state.get("pr_medium") or 0) + \
                               (state.get("pr_complex") or 0)
                        _row("PR Fixes", str(pr_t) if pr_t else "—", empty=not pr_t)

                    with ui.element("div").classes("ed-summary-section"):
                        ts = state.get("team_size") or 0
                        wd = state.get("working_days") or 0
                        rl = state.get("expected_releases") or 0
                        _row("Team Size",    str(ts) if ts else "—", empty=not ts)
                        _row("Working Days", str(wd) if wd else "—", empty=not wd)
                        _row("Releases",     str(rl) if rl else "—", empty=not rl)

                    with ui.element("div").classes("ed-summary-total"):
                        ui.label("Estimated Total").classes("ed-eyebrow")
                        cr = state.get("calc_result")
                        if cr and cr.get("grand_total_hours"):
                            ui.label(f"{cr['grand_total_hours']:,.0f}h") \
                                .classes("ed-summary-total-num")
                        else:
                            ui.label("TBD").classes("ed-summary-total-num") \
                                .style("opacity: 0.4;")

                # Sync toolbar title with project name
                if state.get("project_name"):
                    title_label.set_text(state["project_name"])

            # Re-render on every step transition
            stepper.on_value_change(lambda _: (_render_steps(), _render_rail()))
            _render_steps()
            _render_rail()


@ui.page("/estimation/{estimation_id}")
async def estimation_detail_page(estimation_id: int) -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    hdrs = auth_headers()
    token: str = hdrs.get("Authorization", "").removeprefix("Bearer ") if hdrs else ""

    with ui.column().classes("w-full q-pa-md").style("gap: 0;"):

        # ─────────────────────────────────────────────────────────────
        # Inject typography + design system CSS (theme-aware via tokens)
        # ─────────────────────────────────────────────────────────────
        ui.add_head_html("""
        <style>
          /* Hero */
          .ed-hero       { position: relative; display: grid !important;
                           grid-template-columns: 1fr auto; gap: 36px;
                           padding: 32px 36px 32px 44px;
                           border: 1px solid var(--ed-line); border-radius: 4px;
                           overflow: hidden; margin: 0 16px 28px 16px; }
          @media (max-width: 720px) {
            .ed-hero { grid-template-columns: 1fr; }
          }
          .ed-hero-stripe { position: absolute; left: 0; top: 0; bottom: 0; width: 5px; }
          .ed-stripe-FEASIBLE     { background: var(--q-positive); }
          .ed-stripe-AT_RISK      { background: var(--q-warning); }
          .ed-stripe-NOT_FEASIBLE { background: var(--q-negative); }
          .ed-stripe-default      { background: var(--q-info); }

          .ed-hero-left  { display: flex !important; flex-direction: column; min-width: 0; }
          .ed-hero-meta  { display: flex !important; align-items: center; gap: 8px;
                           flex-wrap: wrap; margin-bottom: 14px; min-height: 22px; }

          .ed-hero-num-pill { font-family: var(--ed-mono); font-size: 12px;
                              padding: 3px 10px; border: 1px solid var(--ed-line);
                              border-radius: 99px; }
          .ed-hero-ver-pill { font-family: var(--ed-mono); font-size: 11px;
                              padding: 3px 10px; background: var(--q-warning);
                              color: white; border-radius: 99px; font-weight: 600; }
          .ed-hero-ptype    { font-family: var(--ed-sans); text-transform: uppercase;
                              letter-spacing: 0.14em; font-size: 10px; font-weight: 600;
                              opacity: 0.55; margin-left: 4px; }

          .ed-hero-title { font-family: inherit !important;
                           font-size: 32px !important; font-weight: 600 !important;
                           letter-spacing: -0.012em !important; line-height: 1.15 !important;
                           margin: 4px 0 14px 0 !important; }
          .ed-hero-sub   { font-family: var(--ed-sans);
                           font-size: 14px; opacity: 0.72; max-width: 64ch;
                           line-height: 1.5; }

          .ed-hero-right { display: flex !important; flex-direction: column;
                           align-items: flex-end; justify-content: center;
                           padding-left: 36px; border-left: 1px dashed var(--ed-line);
                           min-width: 240px; }
          @media (max-width: 720px) {
            .ed-hero-right { padding-left: 0; border-left: none;
                             border-top: 1px dashed var(--ed-line); padding-top: 22px;
                             align-items: flex-start; }
          }

          .ed-hero-bignum { font-family: var(--ed-mono) !important;
                            font-variant-numeric: tabular-nums;
                            font-size: 60px !important; font-weight: 500 !important;
                            line-height: 0.95 !important; letter-spacing: -0.02em !important;
                            margin: 8px 0 0 0 !important; }
          .ed-hero-unit  { font-family: var(--ed-sans);
                           text-transform: uppercase; letter-spacing: 0.10em;
                           font-size: 13px; opacity: 0.62; margin-top: 8px; }
          .ed-hero-completion { margin-top: 14px; font-family: var(--ed-sans);
                                font-size: 12px; opacity: 0.85; }
          .ed-hero-completion .ed-mono { font-size: 13px; margin-left: 6px; }
          .ed-hero-completion-label { opacity: 0.55; text-transform: uppercase;
                                      letter-spacing: 0.10em; font-size: 11px; }

          /* Tabs */
          .ed-tabs       { margin: 0 16px 24px 16px;
                           border-bottom: 1px solid var(--ed-line); }
          .ed-tabs .q-tab{ font-family: var(--ed-sans);
                           text-transform: uppercase; letter-spacing: 0.16em;
                           font-size: 11px; font-weight: 600;
                           padding: 0 22px; min-height: 48px; }
          .ed-tabs .q-tab__indicator { height: 2px; }
          .ed-panels     { background: transparent !important;
                           margin: 0 16px;
                           overflow: hidden !important;
                           border-radius: 4px; }
          .ed-panels .q-panel { overflow: hidden !important; }
          .ed-panels .q-tab-panel { padding: 6px 2px 6px 0 !important;
                                    box-sizing: border-box; }

          /* Spec sheet */
          .ed-spec       { display: grid !important; grid-template-columns: 1fr 1fr;
                           gap: 0 40px; }
          @media (max-width: 720px) { .ed-spec { grid-template-columns: 1fr; } }
          .ed-spec-row   { display: grid !important; grid-template-columns: 140px 1fr;
                           padding: 10px 0; border-bottom: 1px dashed var(--ed-line-soft);
                           align-items: baseline; gap: 12px; }
          .ed-spec-label { font-family: var(--ed-sans);
                           text-transform: uppercase; letter-spacing: 0.12em;
                           font-size: 10px; font-weight: 600; opacity: 0.6; }
          .ed-spec-value { font-family: var(--ed-mono);
                           font-size: 13px; word-break: break-word; }
          .ed-spec-value.long { font-family: var(--ed-sans);
                                font-size: 13px; line-height: 1.5; }

          /* Hours bar chart */
          .ed-bar-row    { display: grid !important; grid-template-columns: 220px 1fr 100px;
                           align-items: center; gap: 18px; padding: 11px 0;
                           border-bottom: 1px dashed var(--ed-line-soft); }
          @media (max-width: 720px) {
            .ed-bar-row  { grid-template-columns: 1fr; gap: 6px; }
          }
          .ed-bar-row:last-child { border-bottom: none; }
          .ed-bar-row.total { border-top: 1px solid var(--ed-line);
                              border-bottom: none !important; padding-top: 16px;
                              margin-top: 6px; }
          .ed-bar-label  { display: flex !important; align-items: center; gap: 8px;
                           font-family: var(--ed-sans); font-size: 12px;
                           text-transform: uppercase; letter-spacing: 0.10em;
                           font-weight: 500; opacity: 0.78; }
          .ed-bar-row.total .ed-bar-label { font-weight: 700; opacity: 1; }
          .ed-bar-icon   { font-size: 16px !important; opacity: 0.55; }
          .ed-bar-track  { height: 6px; background: var(--ed-line-soft);
                           border-radius: 99px; overflow: hidden; }
          .ed-bar-fill   { height: 100%; background: var(--q-primary);
                           border-radius: 99px;
                           transition: width 600ms cubic-bezier(0.16, 1, 0.3, 1); }
          .ed-bar-row.total .ed-bar-fill { background: currentColor; opacity: 0.85; }
          .ed-bar-value  { font-family: var(--ed-mono);
                           font-variant-numeric: tabular-nums;
                           font-size: 13px; font-weight: 500; text-align: right; }
          .ed-bar-row.total .ed-bar-value { font-size: 16px; font-weight: 600; }

          /* KPI strip extras (base in global) */
          .ed-strip-unit { opacity: 0.4; font-size: 14px; font-weight: 400; margin-left: 2px; }
          .ed-strip-date { font-family: var(--ed-mono);
                           font-size: 17px; font-weight: 500; margin-top: 8px; }

          /* PR tiles */
          .ed-pr-grid    { display: grid !important;
                           grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                           gap: 14px; margin-bottom: 22px; }
          .ed-pr-tile    { padding: 18px 20px; border: 1px solid var(--ed-line);
                           border-radius: 4px; }
          .ed-pr-tile.total { border-color: var(--q-primary); }
          .ed-pr-tile-num { font-family: var(--ed-mono);
                            font-variant-numeric: tabular-nums;
                            font-size: 22px; font-weight: 500; margin-top: 10px; }
          .ed-pr-tile-x   { font-family: var(--ed-sans);
                            font-size: 12px; opacity: 0.65; margin-top: 4px; }
          .ed-pr-tile-x strong { font-weight: 700; }
          .ed-pr-unit     { font-size: 14px; opacity: 0.5; margin-left: 1px; }

          /* Risk chips */
          .ed-chips      { display: flex !important; flex-wrap: wrap; gap: 6px; }

          /* Workflow assignment */
          .ed-assign-block { display: flex !important; align-items: center; gap: 10px; }
          .ed-assign-name  { font-size: 15px; font-weight: 500; line-height: 1.2; }
          .ed-assign-empty { opacity: 0.6; line-height: 1.2; }

          /* Footer download */
          .ed-download   { display: grid !important;
                           grid-template-columns: 1fr auto auto auto;
                           align-items: center; gap: 14px;
                           margin: 36px 16px 12px 16px;
                           padding: 24px 28px; border: 1px solid var(--ed-line);
                           border-radius: 4px; }
          @media (max-width: 720px) { .ed-download { grid-template-columns: 1fr; } }
          .ed-dl-meta-title { font-family: inherit !important;
                              font-size: 18px !important; font-weight: 600 !important;
                              line-height: 1.2 !important; margin: 6px 0 4px 0 !important; }
          .ed-dl-meta-sub   { font-family: var(--ed-sans);
                              opacity: 0.65; font-size: 12px; }

          .ed-dl-btn .q-btn__content {
            font-family: var(--ed-sans); text-transform: uppercase;
            letter-spacing: 0.14em; font-size: 11px; font-weight: 600;
          }

        </style>
        """)

        # ─────────────────────────────────────────────────────────────
        # Load the estimation
        # ─────────────────────────────────────────────────────────────
        try:
            est: dict = await api_get(f"/estimations/{estimation_id}")
        except Exception as exc:
            show_error_page(exc)
            return

        # Configurable field labels (A5) — also applied to this read-only view.
        try:
            _det_configs = await api_get("/configuration")
            _config_map: dict[str, str] = {
                c.get("key", ""): c.get("value", "")
                for c in _det_configs if isinstance(c, dict)
            }
        except Exception:
            _config_map = {}

        def _disp_label(key: str, default: str) -> str:
            """Configured label minus any trailing '(optional)' form hint."""
            import re as _re
            raw = _config_map.get(key) or default
            return _re.sub(r"\s*\(optional\)\s*$", "", raw, flags=_re.I)

        est_state: dict[str, Any] = {"data": est}
        version = est.get("version", 1) or 1
        feasibility = est.get("feasibility_status", "")
        status = est.get("status", "")

        # ─────────────────────────────────────────────────────────────
        # Inline helpers/dialogs (preserved verbatim from original)
        # ─────────────────────────────────────────────────────────────
        async def _do_export() -> None:
            try:
                result = await api_post(f"/estimations/{estimation_id}/export")
                status_v = result.get("status", "unknown")
                errors = result.get("errors", [])
                if errors:
                    ui.notify(f"Export completed with errors: {', '.join(errors)}", type="warning")
                else:
                    ui.notify(f"Export successful (status: {status_v}).", type="positive")
            except Exception as exc:
                ui.notify(f"Export failed: {exc}", type="negative")

        async def _open_export_tasks_dialog() -> None:
            _linked_ext_id = ""
            _linked_source = ""
            if est.get("request_id"):
                try:
                    req_data = await api_get(f"/requests/{est['request_id']}")
                    _linked_ext_id = req_data.get("external_id") or ""
                    _linked_source = req_data.get("request_source") or ""
                except Exception:
                    pass

            with ui.dialog() as dlg, ui.card().classes("w-[420px]"):
                ui.label("Export Task Breakdown").classes("text-h6 q-mb-sm")
                ui.label("Create sub-tasks in Jira or Redmine for each estimation task.").classes("text-caption text-grey q-mb-md")
                sys_select = ui.select(
                    label="Target System",
                    options=["JIRA", "REDMINE"],
                    value=_linked_source if _linked_source in ("JIRA", "REDMINE") else "JIRA",
                ).classes("w-full")
                with ui.row().classes("w-full items-end gap-1"):
                    issue_input = ui.input(
                        label="Parent Issue Key (optional)",
                        placeholder="e.g. PROJ-123 or leave empty",
                    ).classes("flex-grow")
                    if _linked_ext_id:
                        def _fill_from_request(ext=_linked_ext_id):
                            issue_input.value = ext
                        ui.button(
                            icon="link", on_click=_fill_from_request
                        ).props("flat dense round").tooltip(f"Use linked request: {_linked_ext_id}")
                ui.label("If empty, tasks are created as standalone issues in the configured project.").classes("text-caption text-grey q-mb-md")

                async def _do_export_tasks() -> None:
                    payload = {"target_system": sys_select.value}
                    if issue_input.value and issue_input.value.strip():
                        payload["issue_key"] = issue_input.value.strip()
                    try:
                        result = await api_post(f"/estimations/{estimation_id}/export-tasks", json=payload)
                        created = result.get("items_created", 0)
                        total = result.get("items_processed", 0)
                        errors = result.get("errors", [])
                        dlg.close()
                        if errors:
                            ui.notify(f"Task export: {created}/{total} created. Errors: {', '.join(errors[:3])}", type="warning")
                        else:
                            ui.notify(f"Task breakdown exported: {created}/{total} tasks created in {sys_select.value}.", type="positive")
                    except Exception as exc:
                        ui.notify(f"Task export failed: {exc}", type="negative")

                with ui.row().classes("w-full justify-end gap-2 q-mt-sm"):
                    ui.button("Cancel", on_click=dlg.close).props("flat")
                    ui.button("Export", icon="account_tree", on_click=_do_export_tasks).props("color=teal")
            dlg.open()

        async def _open_version_diff_dialog() -> None:
            try:
                versions_list = await api_get(f"/estimations/{estimation_id}/versions")
            except Exception as exc:
                ui.notify(f"Failed to load versions: {exc}", type="negative")
                return

            with ui.dialog().props("maximized=false") as dlg, ui.card().classes("w-[900px] max-h-[85vh]"):
                ui.label("Compare Versions").classes("text-h6 q-mb-md")

                with ui.row().classes("items-end gap-4 q-mb-md"):
                    ver_options = {v["version"]: f"v{v['version']} — {v.get('grand_total_hours', 0):.1f}h ({v.get('status', '')})" for v in versions_list}
                    ver_a_select = ui.select(
                        options=ver_options,
                        value=versions_list[0]["version"] if versions_list else 1,
                        label="Version A",
                    ).classes("w-64")
                    ver_b_select = ui.select(
                        options=ver_options,
                        value=versions_list[-1]["version"] if versions_list else 1,
                        label="Version B",
                    ).classes("w-64")

                diff_container = ui.column().classes("w-full")

                async def _run_diff(
                    _va=ver_a_select,
                    _vb=ver_b_select,
                    _container=diff_container,
                ) -> None:
                    va = _va.value
                    vb = _vb.value
                    if va == vb:
                        ui.notify("Select two different versions.", type="warning")
                        return
                    try:
                        diff = await api_get(f"/estimations/{estimation_id}/versions/{va}/diff/{vb}")
                    except Exception as exc:
                        ui.notify(f"Diff failed: {exc}", type="negative")
                        return

                    _container.clear()
                    with _container:
                        changes = diff.get("changes", [])
                        if changes:
                            ui.label("Field Changes").classes("text-subtitle1 text-weight-medium q-mt-md")
                            diff_rows = []
                            for c in changes:
                                va_val = c.get("version_a")
                                vb_val = c.get("version_b")
                                if isinstance(va_val, float):
                                    va_val = f"{va_val:,.1f}"
                                if isinstance(vb_val, float):
                                    vb_val = f"{vb_val:,.1f}"
                                diff_rows.append({
                                    "field": c["field"],
                                    "version_a": str(va_val) if va_val is not None else "—",
                                    "version_b": str(vb_val) if vb_val is not None else "—",
                                })
                            ui.table(
                                columns=[
                                    {"name": "field", "label": "Field", "field": "field", "align": "left"},
                                    {"name": "version_a", "label": f"v{va}", "field": "version_a", "align": "right"},
                                    {"name": "version_b", "label": f"v{vb}", "field": "version_b", "align": "right"},
                                ],
                                rows=diff_rows,
                                row_key="field",
                            ).classes("w-full q-mb-md")

                        modified = diff.get("modified_tasks", [])
                        if modified:
                            ui.label("Modified Tasks").classes("text-subtitle1 text-weight-medium q-mt-sm")
                            mod_rows = []
                            for m in modified:
                                delta = (m.get("hours_b", 0) or 0) - (m.get("hours_a", 0) or 0)
                                mod_rows.append({
                                    "task": m["task_name"],
                                    "hours_a": f"{m.get('hours_a', 0):.1f}",
                                    "hours_b": f"{m.get('hours_b', 0):.1f}",
                                    "delta": f"{delta:+.1f}",
                                })
                            ui.table(
                                columns=[
                                    {"name": "task", "label": "Task", "field": "task", "align": "left"},
                                    {"name": "hours_a", "label": f"v{va} Hours", "field": "hours_a", "align": "right"},
                                    {"name": "hours_b", "label": f"v{vb} Hours", "field": "hours_b", "align": "right"},
                                    {"name": "delta", "label": "Delta", "field": "delta", "align": "right"},
                                ],
                                rows=mod_rows,
                                row_key="task",
                            ).classes("w-full q-mb-md")

                        added = diff.get("added_tasks", [])
                        removed = diff.get("removed_tasks", [])
                        if added:
                            ui.label(f"Added Tasks (v{vb})").classes("text-subtitle2 text-positive q-mt-sm")
                            for t in added:
                                ui.label(f"  + {t['task_name']} ({t.get('calculated_hours', 0):.1f}h)").classes("text-body2")
                        if removed:
                            ui.label(f"Removed Tasks (v{va})").classes("text-subtitle2 text-negative q-mt-sm")
                            for t in removed:
                                ui.label(f"  - {t['task_name']} ({t.get('calculated_hours', 0):.1f}h)").classes("text-body2")

                        input_changes = diff.get("input_changes", {})
                        if input_changes:
                            ui.label("Input Changes").classes("text-subtitle1 text-weight-medium q-mt-md")
                            for key, vals in input_changes.items():
                                label = key.replace("_", " ").title()
                                added_ids = vals.get("added", [])
                                removed_ids = vals.get("removed", [])
                                if added_ids:
                                    ui.label(f"  {label} added: {added_ids}").classes("text-body2 text-positive")
                                if removed_ids:
                                    ui.label(f"  {label} removed: {removed_ids}").classes("text-body2 text-negative")

                        if not changes and not modified and not added and not removed and not input_changes:
                            ui.label("No differences found between the two versions.").classes("text-grey q-mt-md")

                ui.button("Compare", icon="compare_arrows", on_click=_run_diff).props("color=primary")
                ui.separator().classes("q-mt-md")
                ui.button("Close", on_click=dlg.close).props("flat")
            dlg.open()

        async def _do_status_transition(target: str) -> None:
            try:
                await api_post(
                    f"/estimations/{estimation_id}/status",
                    json={"status": target},
                )
                ui.notify(f"Status changed to {target}.", type="positive")
                ui.navigate.to(f"/estimation/{estimation_id}")
            except Exception as exc:
                ui.notify(f"Status update failed: {exc}", type="negative")
                try:
                    est_state["data"] = await api_get(f"/estimations/{estimation_id}")
                    _rebuild_status_buttons()
                except Exception:
                    pass

        async def _archive_to_history() -> None:
            try:
                await api_post(f"/estimations/{estimation_id}/archive")
                ui.notify("Estimation archived to Historical Projects.", type="positive")
            except Exception as exc:
                ui.notify(f"Archive failed: {exc}", type="negative")

        def _download_js(fmt: str, fallback: str) -> str:
            # Use the server filename (<request id>-<title>-YYYYMMDDHHmm) from
            # Content-Disposition. Offer a real Save-As dialog where supported
            # (showSaveFilePicker, secure context), else fall back to a normal
            # download to the browser's default folder.
            url = f"/api/estimations/{estimation_id}/report/{fmt}"
            # Emits report_downloaded / report_cancelled / report_failed back to
            # NiceGUI (see ui.on handlers) so the UI can show progress + result.
            return (
                f'(async () => {{'
                f'  try {{'
                f'    const r = await fetch("{url}", {{headers: {{"Authorization": "Bearer {token}"}}}});'
                f'    if (!r.ok) throw new Error("HTTP " + r.status);'
                f'    const cd = r.headers.get("Content-Disposition") || "";'
                f'    let name = "{fallback}";'
                f'    const m = /filename\\*?=(?:UTF-8\'\')?"?([^";]+)"?/i.exec(cd);'
                f'    if (m) name = decodeURIComponent(m[1]);'
                f'    const blob = await r.blob();'
                f'    if (window.showSaveFilePicker) {{'
                f'      try {{'
                f'        const h = await window.showSaveFilePicker({{suggestedName: name}});'
                f'        const w = await h.createWritable();'
                f'        await w.write(blob); await w.close();'
                f'        emitEvent("report_downloaded", {{fmt: "{fmt}"}});'
                f'        return;'
                f'      }} catch (e) {{ if (e && e.name === "AbortError") {{ emitEvent("report_cancelled", {{fmt: "{fmt}"}}); return; }} }}'
                f'    }}'
                f'    const a = document.createElement("a");'
                f'    a.href = URL.createObjectURL(blob);'
                f'    a.download = name;'
                f'    a.click();'
                f'    URL.revokeObjectURL(a.href);'
                f'    emitEvent("report_downloaded", {{fmt: "{fmt}"}});'
                f'  }} catch (err) {{ console.error("Download failed:", err); emitEvent("report_failed", {{fmt: "{fmt}"}}); }}'
                f'}})();'
            )

        # Download buttons registry + progress/result feedback (B4).
        _dl_buttons: dict[str, Any] = {}

        def _dl_click(fmt: str, fallback: str, label: str) -> None:
            btn = _dl_buttons.get(fmt)
            if btn is not None:
                btn.props(add="loading")
            ui.notify(f"Preparing {label} report…", type="ongoing", spinner=True, timeout=2500)
            ui.run_javascript(_download_js(fmt, fallback))

        def _dl_clear(fmt: str) -> None:
            btn = _dl_buttons.get(fmt)
            if btn is not None:
                btn.props(remove="loading")

        def _on_report_downloaded(e: Any) -> None:
            fmt = (e.args or {}).get("fmt", "") if isinstance(e.args, dict) else ""
            _dl_clear(fmt)
            ui.notify("Report downloaded.", type="positive", icon="download_done")

        def _on_report_cancelled(e: Any) -> None:
            fmt = (e.args or {}).get("fmt", "") if isinstance(e.args, dict) else ""
            _dl_clear(fmt)
            ui.notify("Download cancelled.", type="info")

        def _on_report_failed(e: Any) -> None:
            fmt = (e.args or {}).get("fmt", "") if isinstance(e.args, dict) else ""
            _dl_clear(fmt)
            ui.notify("Report download failed. Please try again.", type="negative")

        ui.on("report_downloaded", _on_report_downloaded)
        ui.on("report_cancelled", _on_report_cancelled)
        ui.on("report_failed", _on_report_failed)

        _STATUS_BTN_PROPS: dict[str, str] = {
            "FINAL":    "color=primary",
            "APPROVED": "color=positive",
            "REVISED":  "color=orange",
            "DRAFT":    "color=grey",
        }

        # ─────────────────────────────────────────────────────────────
        # 1. STICKY ACTION TOOLBAR
        # ─────────────────────────────────────────────────────────────
        with ui.element("div").classes("ed-toolbar"):
            ui.button(icon="arrow_back",
                      on_click=lambda: ui.navigate.to("/estimations")) \
                .props("flat dense").tooltip("Back to estimations")

            ui.element("div").classes("ed-toolbar-spacer")

            if est.get("status") in ("DRAFT", "REVISED"):
                _edit_label = "Resume editing" if est.get("status") == "DRAFT" else "Edit"
                ui.button(_edit_label, icon="edit",
                          on_click=lambda: ui.navigate.to(f"/estimation/{estimation_id}/edit")) \
                    .props("flat dense color=orange")

            if est.get("request_id"):
                ui.button("Export to External", icon="cloud_upload",
                          on_click=_do_export).props("flat dense color=accent")

            ui.button("Export Tasks", icon="account_tree",
                      on_click=_open_export_tasks_dialog).props("flat dense color=teal")

            if version > 1:
                ui.button(f"Compare ({version} versions)", icon="compare_arrows",
                          on_click=_open_version_diff_dialog).props("flat dense")

            ui.element("div").classes("ed-toolbar-grow")

            with ui.element("div").classes(f"ed-status-now ed-status-{feasibility} ed-status-{status}"):
                ui.element("span").classes("ed-status-dot")
                ui.label(f"{feasibility or 'UNKNOWN'} · {status or 'DRAFT'}")

        # ─────────────────────────────────────────────────────────────
        # 2. HERO CARD — project identity + grand total
        # ─────────────────────────────────────────────────────────────
        stripe_class = (
            f"ed-stripe-{feasibility}"
            if feasibility in ("FEASIBLE", "AT_RISK", "NOT_FEASIBLE")
            else "ed-stripe-default"
        )

        with ui.element("div").classes("ed-shell"):
            with ui.element("div").classes("ed-hero"):
                ui.element("div").classes(f"ed-hero-stripe {stripe_class}")

                # Left column: identity
                with ui.element("div").classes("ed-hero-left"):
                    with ui.element("div").classes("ed-hero-meta"):
                        ui.label("Estimation").classes("ed-eyebrow")
                        if est.get("estimation_number"):
                            ui.label(est["estimation_number"]).classes("ed-hero-num-pill")
                        if version > 1:
                            ui.label(f"v{version}").classes("ed-hero-ver-pill")
                        if est.get("project_type"):
                            ui.label(f"· {est['project_type']}").classes("ed-hero-ptype")

                    ui.label(est.get("project_name", f"Estimation {estimation_id}")) \
                        .classes("ed-hero-title")

                    _bits = []
                    if est.get("dut_count"):
                        _bits.append(f"{est['dut_count']} DUT{'s' if est['dut_count'] != 1 else ''}")
                    if est.get("profile_count"):
                        _bits.append(f"{est['profile_count']} profile{'s' if est['profile_count'] != 1 else ''}")
                    if est.get("dut_profile_combinations"):
                        _bits.append(f"{est['dut_profile_combinations']} combinations")
                    if est.get("expected_releases", 1) > 1:
                        _bits.append(f"{est['expected_releases']} releases")
                    if _bits:
                        ui.label(" · ".join(_bits)).classes("ed-hero-sub")

                # Right column: grand total
                with ui.element("div").classes("ed-hero-right"):
                    ui.label("Grand Total").classes("ed-eyebrow")
                    ui.label(f"{est.get('grand_total_hours', 0):,.0f}").classes("ed-hero-bignum")
                    _gd = est.get("grand_total_days", 0)
                    _gw = round(_gd / 5.0, 1) if _gd else 0
                    ui.label(f"hours · {_gd:,.1f} days · {_gw:,.1f} weeks") \
                        .classes("ed-hero-unit")
                    if est.get("estimated_completion_date"):
                        with ui.element("div").classes("ed-hero-completion"):
                            ui.label("Est. Completion").classes("ed-hero-completion-label")
                            ui.label(str(est["estimated_completion_date"])).classes("ed-mono")

        # ─────────────────────────────────────────────────────────────
        # 3. TABS
        # ─────────────────────────────────────────────────────────────
        with ui.element("div").classes("ed-shell"):
            with ui.tabs().classes("ed-tabs").props("inline-label align=left no-caps") as _tabs:
                ui.tab("overview", label="Overview", icon="dashboard")
                ui.tab("tasks",    label=f"Tasks ({len(est.get('tasks', []))})", icon="checklist")
                ui.tab("docs",     label=f"Documents ({len(est.get('document_deliverables') or [])})", icon="description")
                ui.tab("prs",      label=f"PR Fixes ({est.get('pr_fix_count', 0)})", icon="bug_report")
                ui.tab("team",     label=f"Team ({len(est.get('team_allocations') or [])})", icon="groups")
                ui.tab("workflow", label="Workflow", icon="account_tree")

            with ui.tab_panels(_tabs, value="overview").classes("ed-panels w-full"):

                # ─── OVERVIEW ─────────────────────────────────────────
                with ui.tab_panel("overview"):

                    # Project Specification card
                    with ui.element("div").classes("ed-card"):
                        ui.label("Project Specification").classes("ed-cap")

                        with ui.element("div").classes("ed-spec"):
                            def _spec(label_txt: str, value: str, long: bool = False) -> None:
                                with ui.element("div").classes("ed-spec-row"):
                                    ui.label(label_txt).classes("ed-spec-label")
                                    cls = "ed-spec-value long" if long else "ed-spec-value"
                                    ui.label(value).classes(cls)

                            _spec("Project Type", est.get("project_type") or "—")
                            _spec("DUTs", str(est.get("dut_count", 0)))
                            _spec("Profiles", str(est.get("profile_count", 0)))
                            _spec("Combinations", str(est.get("dut_profile_combinations", 0)))
                            _spec(_disp_label("label_project_start_date", "Start Date"),
                                  str(est.get("start_date") or "—"))
                            _spec(_disp_label("label_deadline", "Deadline"),
                                  str(est.get("expected_delivery") or "—"))
                            _spec(
                                "Created",
                                str(est.get("created_at", ""))[:10] if est.get("created_at") else "—",
                            )
                            _spec("Releases", str(est.get("expected_releases") or 1))
                            if est.get("team_name"):
                                _spec("Team", est["team_name"])
                            if est.get("project_reference"):
                                _spec("Reference", est["project_reference"])
                            if est.get("target_customer"):
                                _spec("Target Customer", est["target_customer"])
                            if est.get("project_goals"):
                                _spec("Project Goals", est["project_goals"], long=True)

                    # Hours Breakdown card
                    with ui.element("div").classes("ed-card"):
                        with ui.element("div").classes("ed-card-head"):
                            ui.label("Hours Breakdown").classes("ed-cap")
                            ui.label(f"TOTAL · {est.get('grand_total_hours', 0):,.1f}h") \
                                .classes("ed-card-head-meta")

                        _gtot = max(est.get("grand_total_hours", 0) or 1, 1)
                        _hour_items = [
                            ("Tester Hours",     est.get("total_tester_hours", 0),  "person"),
                            ("Leader Hours",     est.get("total_leader_hours", 0),  "manage_accounts"),
                            ("PR Fix Hours",     est.get("pr_fix_hours", 0),         "bug_report"),
                            ("PR Test Creation", est.get("pr_no_test_hours", 0),     "science"),
                            ("Study Hours",      est.get("study_hours", 0),          "school"),
                            ("Release Extra",    est.get("release_extra_hours", 0),  "rocket_launch"),
                            ("Documentation",    est.get("documentation_hours", 0),  "description"),
                            ("Buffer",           est.get("buffer_hours", 0),         "security"),
                        ]
                        for label_txt, val, icon in _hour_items:
                            if not val:
                                continue
                            pct = max((val / _gtot) * 100, 0.5)
                            with ui.element("div").classes("ed-bar-row"):
                                with ui.element("div").classes("ed-bar-label"):
                                    ui.icon(icon).classes("ed-bar-icon")
                                    ui.label(label_txt)
                                with ui.element("div").classes("ed-bar-track"):
                                    ui.element("div").classes("ed-bar-fill") \
                                        .style(f"width: {pct:.1f}%")
                                ui.label(f"{val:,.1f}h").classes("ed-bar-value")

                        # Grand total row
                        with ui.element("div").classes("ed-bar-row total"):
                            with ui.element("div").classes("ed-bar-label"):
                                ui.icon("summarize").classes("ed-bar-icon")
                                ui.label("Grand Total")
                            with ui.element("div").classes("ed-bar-track"):
                                ui.element("div").classes("ed-bar-fill") \
                                    .style("width: 100%")
                            ui.label(f"{est.get('grand_total_hours', 0):,.1f}h") \
                                .classes("ed-bar-value")

                    # Proposed Duration strip (A4) — the wall-clock delivery time,
                    # shown for every estimation (not only when team > 1).
                    _el_days = est.get("elapsed_days", 0)
                    _el_weeks = est.get("elapsed_weeks", 0)
                    if _el_days > 0:
                        with ui.element("div").classes("ed-card"):
                            with ui.element("div").classes("ed-card-head"):
                                ui.label("Proposed Duration · Wall Clock").classes("ed-cap")
                                ui.label("parallelizable ÷ team · sequential by one") \
                                    .classes("ed-eyebrow")

                            with ui.element("div").classes("ed-strip"):
                                for lbl, val, unit in [
                                    ("Elapsed Hours", est.get("elapsed_hours", 0), "h"),
                                    ("Elapsed Days",  _el_days, "d"),
                                    ("Elapsed Weeks", _el_weeks, "w"),
                                ]:
                                    with ui.element("div").classes("ed-strip-cell"):
                                        ui.label(lbl).classes("ed-eyebrow")
                                        with ui.element("div").classes("ed-strip-num"):
                                            ui.label(f"{val:,.1f}")
                                            ui.label(unit).classes("ed-strip-unit")
                                if est.get("estimated_completion_date"):
                                    with ui.element("div").classes("ed-strip-cell"):
                                        ui.label("Est. Completion").classes("ed-eyebrow")
                                        ui.label(str(est["estimated_completion_date"])) \
                                            .classes("ed-strip-date")

                    # Risks
                    est_risks = est.get("risks") or []
                    if est_risks:
                        with ui.element("div").classes("ed-card"):
                            with ui.element("div").classes("ed-card-head"):
                                ui.label("Associated Risks").classes("ed-cap")
                                ui.label(f"{len(est_risks)} flagged").classes("ed-card-head-meta")
                            with ui.element("div").classes("ed-chips"):
                                for risk in est_risks:
                                    risk_name = risk.get("risk_item_name") or risk.get("name") or f"Risk #{risk.get('risk_item_id', '?')}"
                                    risk_cat = risk.get("category") or ""
                                    chip_label = f"{risk_cat}: {risk_name}" if risk_cat else risk_name
                                    ui.chip(chip_label, icon="warning").props("color=warning outline dense")

                # ─── TASKS ────────────────────────────────────────────
                with ui.tab_panel("tasks"):
                    tasks: list[dict] = est.get("tasks", [])
                    with ui.element("div").classes("ed-card"):
                        with ui.element("div").classes("ed-card-head"):
                            ui.label("Task Breakdown").classes("ed-cap")
                            _tasks_total = sum(t.get("calculated_hours", 0) for t in tasks)
                            ui.label(f"{len(tasks)} tasks · {_tasks_total:,.1f}h total") \
                                .classes("ed-card-head-meta")
                        if tasks:
                            task_cols = [
                                {"name": "feature",          "label": "Feature",   "field": "feature_name",        "align": "left",  "sortable": True},
                                {"name": "task_name",        "label": "Task",      "field": "task_name",           "align": "left",  "sortable": True},
                                {"name": "task_type",        "label": "Type",      "field": "task_type",           "align": "left",  "sortable": True},
                                {"name": "base_hours",       "label": "Base h",    "field": "base_hours",          "align": "right", "sortable": True},
                                {"name": "formula",          "label": "Formula",   "field": "formula",             "align": "left",  "sortable": False},
                                {"name": "calc_hours",       "label": "Calc h",    "field": "calculated_hours",    "align": "right", "sortable": True},
                                {"name": "assigned_testers", "label": "Resources", "field": "assigned_testers",    "align": "center","sortable": True},
                                {"name": "new_study",        "label": "Study",     "field": "is_new_feature_study","align": "center"},
                            ]
                            tbl = ui.table(
                                columns=task_cols,
                                rows=tasks,
                                row_key="id",
                                pagination={"rowsPerPage": 25},
                            ).classes("w-full").props("flat")
                            tbl.add_slot(
                                "body-cell-feature",
                                r"""
                                <q-td :props="props">
                                    <q-badge v-if="props.value" outline color="primary" :label="props.value" />
                                    <span v-else class="text-grey-5 text-italic">Global</span>
                                </q-td>
                                """,
                            )
                            tbl.add_slot(
                                "body-cell-new_study",
                                r"""
                                <q-td :props="props">
                                    <q-badge
                                        :color="props.value ? 'orange' : 'transparent'"
                                        :label="props.value ? '★' : ''"
                                        :text-color="props.value ? 'white' : 'transparent'"
                                    />
                                </q-td>
                                """,
                            )
                        else:
                            ui.label("No task breakdown available").classes("ed-empty")

                # ─── DOCUMENTS ────────────────────────────────────────
                with ui.tab_panel("docs"):
                    _doc_deliverables = est.get("document_deliverables") or []
                    with ui.element("div").classes("ed-card"):
                        with ui.element("div").classes("ed-card-head"):
                            ui.label("Document Deliverables").classes("ed-cap")
                            ui.label(f"{est.get('documentation_hours', 0):.1f}h documentation total") \
                                .classes("ed-card-head-meta")
                        if _doc_deliverables:
                            doc_cols = [
                                {"name": "name",            "label": "Document Type",   "field": "name",             "align": "left",  "sortable": True},
                                {"name": "category",        "label": "Category",        "field": "category",         "align": "left",  "sortable": True},
                                {"name": "linked_task",     "label": "Linked Task",     "field": "linked_task",      "align": "left"},
                                {"name": "count",           "label": "Count",           "field": "count",            "align": "right"},
                                {"name": "total_hours",     "label": "Total Hours",     "field": "total_hours",      "align": "right"},
                                {"name": "effective_hours", "label": "Effective Hours", "field": "effective_hours",  "align": "right"},
                                {"name": "overlap_note",    "label": "Note",            "field": "overlap_note",     "align": "left"},
                            ]
                            _doc_rows = []
                            for dd in _doc_deliverables:
                                _doc_rows.append({
                                    **dd,
                                    "linked_task": dd.get("linked_task") or "—",
                                    "overlap_note": dd.get("overlap_note") or "",
                                })
                            doc_tbl = ui.table(
                                columns=doc_cols,
                                rows=_doc_rows,
                                row_key="name",
                                pagination={"rowsPerPage": 25},
                            ).classes("w-full").props("flat")
                            doc_tbl.add_slot(
                                "body-cell-overlap_note",
                                r"""
                                <q-td :props="props">
                                    <span v-if="props.value" class="text-orange">{{ props.value }}</span>
                                    <span v-else></span>
                                </q-td>
                                """,
                            )
                        else:
                            ui.label("No document deliverables").classes("ed-empty")

                # ─── PRs ──────────────────────────────────────────────
                with ui.tab_panel("prs"):
                    _wizard = {}
                    try:
                        _wizard = _json.loads(est.get("wizard_inputs_json") or "{}")
                    except Exception:
                        pass
                    _pr_fixes = _wizard.get("pr_fixes", {})
                    _pr_simple = _pr_fixes.get("simple", 0)
                    _pr_medium = _pr_fixes.get("medium", 0)
                    _pr_complex = _pr_fixes.get("complex", 0)
                    _pr_details = _wizard.get("pr_details", [])
                    _pr_total = est.get("pr_fix_count", 0)

                    with ui.element("div").classes("ed-card"):
                        with ui.element("div").classes("ed-card-head"):
                            ui.label("PR Fix Summary").classes("ed-cap")
                            ui.label(f"{_pr_total} PRs · {est.get('pr_fix_hours', 0):.1f}h") \
                                .classes("ed-card-head-meta")

                        if _pr_total > 0 or _pr_details:
                            with ui.element("div").classes("ed-pr-grid"):
                                for label_txt, count, rate in [
                                    ("Simple",  _pr_simple,  2),
                                    ("Medium",  _pr_medium,  4),
                                    ("Complex", _pr_complex, 8),
                                ]:
                                    with ui.element("div").classes("ed-pr-tile"):
                                        ui.label(label_txt).classes("ed-eyebrow")
                                        ui.label(str(count)).classes("ed-pr-tile-num")
                                        with ui.element("div").classes("ed-pr-tile-x"):
                                            ui.html(f"× {rate}h = <strong>{count * rate}h</strong>")
                                with ui.element("div").classes("ed-pr-tile total"):
                                    ui.label("Total PR Hours").classes("ed-eyebrow")
                                    with ui.element("div").classes("ed-pr-tile-num"):
                                        ui.label(f"{est.get('pr_fix_hours', 0):.1f}")
                                        ui.label("h").classes("ed-pr-unit")

                            if _pr_details:
                                ui.label("PR Details").classes("ed-cap").style("margin-top: 24px;")
                                pr_detail_cols = [
                                    {"name": "pr_number",      "label": "PR #",           "field": "pr_number",      "align": "left"},
                                    {"name": "link",           "label": "Link",           "field": "link",           "align": "left"},
                                    {"name": "description",    "label": "Description",    "field": "description",    "align": "left"},
                                    {"name": "priority",       "label": "Priority",       "field": "priority",       "align": "left"},
                                    {"name": "complexity",     "label": "Complexity",     "field": "complexity",     "align": "left"},
                                    {"name": "status",         "label": "Status",         "field": "status",         "align": "left"},
                                    {"name": "test_available", "label": "Test Available", "field": "test_available", "align": "center"},
                                ]
                                pr_tbl = ui.table(
                                    columns=pr_detail_cols,
                                    rows=_pr_details,
                                    row_key="pr_number",
                                    pagination={"rowsPerPage": 15},
                                ).classes("w-full q-mt-md").props("flat")
                                pr_tbl.add_slot(
                                    "body-cell-link",
                                    r"""
                                    <q-td :props="props">
                                        <a v-if="props.value" :href="props.value" target="_blank" class="text-primary">
                                            {{ props.value }}
                                        </a>
                                        <span v-else>—</span>
                                    </q-td>
                                    """,
                                )
                                pr_tbl.add_slot(
                                    "body-cell-test_available",
                                    r"""
                                    <q-td :props="props">
                                        <q-badge :color="props.value === false ? 'negative' : 'positive'"
                                                 :label="props.value === false ? 'No' : 'Yes'" />
                                    </q-td>
                                    """,
                                )
                        else:
                            ui.label("No PR fixes").classes("ed-empty")

                # ─── TEAM ─────────────────────────────────────────────
                with ui.tab_panel("team"):
                    team_allocs = est.get("team_allocations") or []
                    with ui.element("div").classes("ed-card"):
                        _alloc_total = sum(a.get("allocated_hours", 0) for a in team_allocs)
                        _alloc_n = len(team_allocs)
                        with ui.element("div").classes("ed-card-head"):
                            ui.label("Team Allocation").classes("ed-cap")
                            ui.label(
                                f"{_alloc_n} member{'s' if _alloc_n != 1 else ''} · {_alloc_total:,.1f}h"
                            ).classes("ed-card-head-meta")
                        if team_allocs:
                            alloc_cols = [
                                {"name": "team_member_name", "label": "Member", "field": "team_member_name", "align": "left"},
                                {"name": "role",             "label": "Role",   "field": "role",             "align": "left"},
                                {"name": "allocated_hours",  "label": "Hours",  "field": "allocated_hours",  "align": "right"},
                            ]
                            ui.table(
                                columns=alloc_cols,
                                rows=team_allocs,
                                row_key="team_member_id",
                                pagination={"rowsPerPage": 25},
                            ).classes("w-full").props("flat")
                        else:
                            ui.label("No team allocations").classes("ed-empty")

                # ─── WORKFLOW ─────────────────────────────────────────
                with ui.tab_panel("workflow"):

                    # Assignment card
                    with ui.element("div").classes("ed-card"):
                        ui.label("Assignment").classes("ed-cap")
                        assign_row = ui.row().classes("items-center q-gutter-md q-mt-sm")

                        async def _build_assign_ui() -> None:
                            assign_row.clear()
                            current_est = est_state["data"]
                            with assign_row:
                                assigned_name = current_est.get("assigned_to_name")
                                with ui.element("div").classes("ed-assign-block"):
                                    if assigned_name:
                                        ui.icon("person", color="primary").classes("text-h5")
                                        with ui.column().classes("gap-0"):
                                            ui.label("Assigned To").classes("ed-eyebrow")
                                            ui.label(assigned_name).classes("ed-assign-name")
                                    else:
                                        ui.icon("person_off", color="grey").classes("text-h5")
                                        with ui.column().classes("gap-0"):
                                            ui.label("Unassigned").classes("ed-eyebrow")
                                            ui.label("No assignee set").classes("ed-assign-empty")

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
                                        label="Reassign to",
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
                                            est_state["data"] = await api_get(f"/estimations/{estimation_id}")
                                            ui.notify(f"Assigned to {user_options.get(uid, uid)}.", type="positive")
                                            await _build_assign_ui()
                                        except Exception as exc:
                                            ui.notify(f"Assignment failed: {exc}", type="negative")

                                    ui.button("Assign", icon="person_add",
                                              on_click=_do_assign).props("flat dense color=primary")

                        await _build_assign_ui()

                    # Status transitions card
                    with ui.element("div").classes("ed-card"):
                        with ui.element("div").classes("ed-card-head"):
                            ui.label("Status Transitions").classes("ed-cap")
                            ui.label(f"current · {status}").classes("ed-card-head-meta")
                        status_row = ui.row().classes("q-gutter-sm q-mt-sm")

                        def _rebuild_status_buttons() -> None:
                            status_row.clear()
                            current_status = est_state["data"].get("status", "DRAFT")
                            allowed = _STATUS_TRANSITIONS.get(current_status, [])
                            with status_row:
                                if not allowed:
                                    ui.label(f"No further transitions from {current_status}") \
                                        .classes("ed-eyebrow").style("padding: 8px 0;")
                                else:
                                    for target in allowed:
                                        btn_props = _STATUS_BTN_PROPS.get(target, "color=grey")
                                        ui.button(
                                            f"Move to {target}",
                                            icon="arrow_forward",
                                            on_click=lambda t=target: _do_status_transition(t),
                                        ).props(f"outline {btn_props}")

                        _rebuild_status_buttons()

                    # Archive (only when APPROVED)
                    if est.get("status") == "APPROVED":
                        with ui.element("div").classes("ed-card"):
                            ui.label("Archive").classes("ed-cap")
                            ui.label(
                                "Move this approved estimation into Historical Projects "
                                "for future calibration."
                            ).style(
                                "opacity:0.7; font-size:13px; margin: 14px 0;"
                            )
                            ui.button(
                                "Archive to History",
                                icon="archive",
                                on_click=_archive_to_history,
                            ).props("outline color=accent")

        # ─────────────────────────────────────────────────────────────
        # 4. FOOTER — DOWNLOAD REPORTS
        # ─────────────────────────────────────────────────────────────
        with ui.element("div").classes("ed-shell"):
            with ui.element("div").classes("ed-download"):
                with ui.column().classes("gap-1"):
                    ui.label("Export").classes("ed-eyebrow")
                    ui.label("Download report").classes("ed-dl-meta-title")
                    ui.label(
                        "A formatted summary of this estimation in your preferred format."
                    ).classes("ed-dl-meta-sub")

                _dl_buttons["xlsx"] = ui.button(
                    "Excel",
                    icon="table_chart",
                    on_click=lambda: _dl_click("xlsx", f"estimation_{estimation_id}.xlsx", "Excel"),
                ).props("outline color=positive").classes("ed-dl-btn")

                _dl_buttons["docx"] = ui.button(
                    "Word",
                    icon="description",
                    on_click=lambda: _dl_click("docx", f"estimation_{estimation_id}.docx", "Word"),
                ).props("outline color=primary").classes("ed-dl-btn")

                _dl_buttons["pdf"] = ui.button(
                    "PDF",
                    icon="picture_as_pdf",
                    on_click=lambda: _dl_click("pdf", f"estimation_{estimation_id}.pdf", "PDF"),
                ).props("outline color=negative").classes("ed-dl-btn")


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

        if est.get("status") not in ("DRAFT", "REVISED"):
            ui.label("Only DRAFT or REVISED estimations can be edited.").classes(
                "text-warning text-h6"
            )
            ui.button("Back to Detail", on_click=lambda: ui.navigate.to(f"/estimation/{estimation_id}"))
            return

        _is_draft_edit = est.get("status") == "DRAFT"

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

        all_features, all_duts, all_profiles, all_hist, all_team_members, all_teams, all_risk_items, _all_configs, _all_estimations = await asyncio.gather(
            _safe_get(f"/features?estimation_id={estimation_id}"),
            _safe_get("/dut-types"),
            _safe_get("/profiles"),
            _safe_get("/historical-projects"),
            _safe_get("/team-members"),
            _safe_get("/teams"),
            _safe_get("/risk-items"),
            _safe_get("/configuration"),
            _safe_get("/estimations"),
        )
        _config_map: dict[str, str] = {c.get("key", ""): c.get("value", "") for c in _all_configs if isinstance(c, dict)}
        _pr_priority_list = [p.strip() for p in _config_map.get("pr_priority_list", "LOW,MEDIUM,HIGH,CRITICAL").split(",") if p.strip()]
        _project_types = [p.strip() for p in _config_map.get("project_types", "NEW,EVOLUTION,SUPPORT,CHANGE_REQUEST").split(",") if p.strip()]
        _est_ref_options: dict[str, str] = {}
        for _e in (_all_estimations or []):
            _num = _e.get("estimation_number") or ""
            _pname = _e.get("project_name") or ""
            _label = f"{_num} — {_pname}" if _num else _pname
            _est_ref_options[_label] = _label

        # Derive product types from features, DUTs, and profiles for filtering
        _product_types_set: set[str] = set()
        for _item in [*all_features, *all_duts, *all_profiles]:
            _pt = _item.get("product_type")
            if _pt:
                _product_types_set.add(_pt)
        product_types: list[str] = sorted(_product_types_set)

        # Pre-fill state from saved inputs
        existing_allocs = [
            {"team_member_id": a.get("team_member_id"), "role": a.get("role", "TESTER"), "allocated_hours": a.get("allocated_hours", 0)}
            for a in (est.get("team_allocations") or [])
        ]
        state: dict[str, Any] = {
            "project_name": est.get("project_name", ""),
            "project_type": est.get("project_type", "EVOLUTION"),
            "product_type_filter": saved_inputs.get("product_type_filter", "All"),
            "applied_presets": saved_inputs.get("applied_presets", []),
            "description": "",
            "project_goals": est.get("project_goals", "") or "",
            "target_customer": est.get("target_customer", "") or "",
            "project_reference": est.get("project_reference", "") or "",
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
            "testing_start_date": str(est.get("testing_start_date") or saved_inputs.get("testing_start_date") or "") or None,
            "delivery_date": str(est.get("expected_delivery") or "") or None,
            "working_days": saved_inputs.get("working_days", 20),
            "team_size": saved_inputs.get("team_size", 1),
            "has_leader": saved_inputs.get("has_leader", False),
            "expected_releases": saved_inputs.get("expected_releases", est.get("expected_releases", 1)),
            "team_allocations": existing_allocs,
            "team_id": est.get("team_id"),
            "risk_item_ids": [r.get("risk_item_id") for r in (est.get("risks") or [])],
            "document_type_ids": saved_inputs.get("document_type_ids", []),
            "document_counts": saved_inputs.get("document_counts", {}),
            "task_assigned_testers": {
                t.get("task_name", ""): t.get("assigned_testers", 1)
                for t in (est.get("tasks") or [])
                if t.get("assigned_testers", 1) != 1
            },
            "calc_result": None,
        }

        version = est.get("version", 1) or 1
        ui.label(f"Edit Estimation — {est.get('estimation_number', '')} (v{version})").classes("text-h4 q-mb-md")

        # ---- Wizard (same 7 steps as new, but pre-filled) ---- #
        # header-nav makes the step headers clickable so users can jump between
        # stages directly (non-sequential navigation), not only via Next/Back.
        with ui.stepper().props("vertical=false animated header-nav").classes("w-full") as stepper:

            # Step 1 — Project Info
            with ui.step("Project Info"):
                ui.label("Edit the basic project details.").classes("text-body2 text-grey q-mb-md")
                name_input = ui.input("Project Name *", value=state["project_name"]).classes("w-full")
                _name_error = ui.label("Project Name is required.").classes(
                    "text-negative text-caption"
                )
                _name_error.set_visibility(False)

                def _on_name_change(e) -> None:
                    state.update({"project_name": e.args})
                    if (e.args or "").strip():
                        _name_error.set_visibility(False)

                name_input.on("update:model-value", _on_name_change)
                _pt_opts = list(_project_types)
                _pt_val = state["project_type"]
                if _pt_val and _pt_val not in _pt_opts:
                    _pt_opts.append(_pt_val)
                type_select = ui.select(
                    options=_pt_opts,
                    label="Project Type",
                    value=_pt_val,
                ).classes("w-full q-mt-sm")
                type_select.on("update:model-value", lambda e: state.update({"project_type": e.args}))

                # Project Reference — shown only for CHANGE_REQUEST
                _ref_opts = list(_est_ref_options.keys())
                _ref_val = state.get("project_reference", "") or None
                if _ref_val and _ref_val not in _ref_opts:
                    _ref_opts.append(_ref_val)
                ref_input = ui.select(
                    options=_ref_opts,
                    label="Project Reference *",
                    value=_ref_val,
                    with_input=True,
                    new_value_mode="add-unique",
                ).classes("w-full q-mt-sm")
                ref_input.bind_visibility_from(type_select, "value", backward=lambda v: v == "CHANGE_REQUEST")
                ref_input.on("update:model-value", lambda e: state.update({"project_reference": e.args}))

                goals_input = ui.textarea(
                    "Project Goals (optional)",
                    value=state["project_goals"],
                    placeholder="What are the main goals of this project?",
                ).classes("w-full q-mt-sm")
                goals_input.on("update:model-value", lambda e: state.update({"project_goals": e.args}))

                customer_input = ui.input(
                    "Target Customer (optional)",
                    value=state["target_customer"],
                    placeholder="e.g. Vodafone, Deutsche Telekom",
                ).classes("w-full q-mt-sm")
                customer_input.on("update:model-value", lambda e: state.update({"target_customer": e.args}))

                ui.separator().classes("q-mt-md")
                ui.label("Product Type Filter").classes("text-subtitle2")
                ui.label(
                    "Select a product type to filter Features, DUTs, and Profiles in subsequent steps."
                ).classes("text-caption text-grey q-mb-xs")
                pt_filter_select = ui.select(
                    options=["All"] + product_types,
                    value=state["product_type_filter"],
                    label="Product Type",
                ).classes("w-64")

                with ui.stepper_navigation():
                    def _go_s2():
                        state["project_name"] = name_input.value or ""
                        state["project_type"] = type_select.value or "EVOLUTION"
                        state["product_type_filter"] = pt_filter_select.value or "All"
                        state["project_goals"] = goals_input.value or ""
                        state["target_customer"] = customer_input.value or ""
                        state["project_reference"] = ref_input.value or ""
                        if not state["project_name"].strip():
                            _name_error.set_visibility(True)
                            ui.notify("Project Name is required.", type="warning")
                            return
                        _name_error.set_visibility(False)
                        if state["project_type"] == "CHANGE_REQUEST" and not state["project_reference"].strip():
                            ui.notify("Project Reference is required for Change Request.", type="warning")
                            return
                        # Rebuild feature list with current product type filter
                        _rebuild_feature_list()
                        stepper.next()
                    ui.button("Next", on_click=_go_s2).props("color=primary icon-right=arrow_forward")

            # Step 2 — Features
            with ui.step("Features"):
                ui.label("Select features under test.").classes("text-body2 text-grey q-mb-md")

                async def _add_custom_feature() -> None:
                    """Create a project-specific feature owned by this estimation."""
                    with ui.dialog() as _dlg, ui.card().classes("w-[min(460px,92vw)]"):
                        ui.label("Add project-specific feature").classes("text-h6")
                        ui.label(
                            "Exists only in this estimation until promoted to the global catalog."
                        ).classes("text-caption text-grey q-mb-sm")
                        _name = ui.input("Feature name *").classes("w-full").props("autofocus")
                        _cat = ui.input("Category", value="Project-Specific").classes("w-full")
                        _weight = ui.number("Complexity weight", value=1.0, min=0.1, step=0.1).classes("w-full")
                        _base = ui.number("Base effort (hours)", value=8.0, min=0, step=0.5).classes("w-full")
                        _ptype = ui.select(["All"] + product_types, label="Product Type",
                                           value=(state.get("product_type_filter") or "All")).classes("w-full")
                        _has_tests = ui.checkbox("Has existing tests", value=False)
                        _desc = ui.textarea("Description (optional)").classes("w-full")

                        async def _create() -> None:
                            if not (_name.value or "").strip():
                                ui.notify("Feature name is required.", type="warning")
                                return
                            created = await api_post(
                                f"/estimations/{estimation_id}/features",
                                json={
                                    "name": _name.value.strip(),
                                    "category": (_cat.value or "").strip() or None,
                                    "complexity_weight": float(_weight.value or 1.0),
                                    "base_effort_hours": float(_base.value or 0),
                                    "product_type": (None if _ptype.value in (None, "All") else _ptype.value),
                                    "has_existing_tests": bool(_has_tests.value),
                                    "description": (_desc.value or "").strip() or None,
                                },
                            )
                            all_features.append(created)
                            # Pre-select the new feature so it's included right away.
                            if created["id"] not in state["feature_ids"]:
                                state["feature_ids"].append(created["id"])
                            _rebuild_feature_list()
                            ui.notify(f"Added project feature '{created['name']}'.", type="positive")
                            _dlg.close()

                        with ui.row().classes("w-full justify-end q-mt-sm"):
                            ui.button("Cancel", on_click=_dlg.close).props("flat")
                            _add_btn = ui.button("Add", icon="add").props("color=primary")
                            _add_btn.on("click", run_async(
                                _add_btn, _create, error_prefix="Could not add feature"))
                    _dlg.open()

                async def _promote_feature(feat: dict) -> None:
                    """Promote a project-specific feature into the global catalog."""
                    try:
                        updated = await api_put(f"/features/{feat['id']}/promote")
                    except Exception as exc:
                        ui.notify(f"Promote failed: {exc}", type="negative")
                        return
                    feat["is_global"] = updated.get("is_global", True)
                    feat["owner_estimation_id"] = updated.get("owner_estimation_id")
                    _rebuild_feature_list()
                    ui.notify(f"'{feat.get('name')}' is now a global feature.", type="positive")

                async def _edit_custom_feature(feat: dict) -> None:
                    """Edit a project feature already added (fix a typo or detail)."""
                    with ui.dialog() as _dlg, ui.card().classes("w-[min(460px,92vw)]"):
                        ui.label("Edit project feature").classes("text-h6")
                        _name = ui.input("Feature name *", value=feat.get("name", "")).classes("w-full").props("autofocus")
                        _cat = ui.input("Category", value=feat.get("category") or "").classes("w-full")
                        _weight = ui.number("Complexity weight", value=feat.get("complexity_weight", 1.0), min=0.1, step=0.1).classes("w-full")
                        _base = ui.number("Base effort (hours)", value=feat.get("base_effort_hours", 0.0) or 0.0, min=0, step=0.5).classes("w-full")
                        _ptype = ui.select(["All"] + product_types, label="Product Type",
                                           value=(feat.get("product_type") or "All")).classes("w-full")
                        _has_tests = ui.checkbox("Has existing tests", value=bool(feat.get("has_existing_tests")))
                        _desc = ui.textarea("Description (optional)", value=feat.get("description") or "").classes("w-full")

                        async def _save() -> None:
                            if not (_name.value or "").strip():
                                ui.notify("Feature name is required.", type="warning")
                                return
                            updated = await api_put(
                                f"/features/{feat['id']}",
                                json={
                                    "name": _name.value.strip(),
                                    "category": (_cat.value or "").strip() or None,
                                    "complexity_weight": float(_weight.value or 1.0),
                                    "base_effort_hours": float(_base.value or 0),
                                    "product_type": (None if _ptype.value in (None, "All") else _ptype.value),
                                    "has_existing_tests": bool(_has_tests.value),
                                    "description": (_desc.value or "").strip() or None,
                                },
                            )
                            feat.update(updated)
                            _rebuild_feature_list()
                            ui.notify(f"Updated '{updated['name']}'.", type="positive")
                            _dlg.close()

                        with ui.row().classes("w-full justify-end q-mt-sm"):
                            ui.button("Cancel", on_click=_dlg.close).props("flat")
                            _save_btn = ui.button("Save", icon="save").props("color=primary")
                            _save_btn.on("click", run_async(
                                _save_btn, _save, error_prefix="Could not update feature"))
                    _dlg.open()

                _can_promote = has_permission("APPROVER")

                with ui.row().classes("items-center q-mb-sm"):
                    ui.button("Add custom feature", icon="add", on_click=_add_custom_feature) \
                        .props("outline dense color=primary")
                    ui.label("Project-specific — promote to global later if reusable.") \
                        .classes("text-caption text-grey")

                pt_info_label = ui.label("").classes("text-caption text-primary q-mb-sm")

                feature_checkbox_refs: dict[int, ui.checkbox] = {}
                new_feat_checkbox_refs: dict[int, ui.checkbox] = {}

                # Feature presets (estimator self-service) — same bar as the new wizard.
                _refresh_presets = _render_preset_bar(state, feature_checkbox_refs, _config_map)

                features_container = ui.column().classes("w-full")
                _programmatic_select_all = [False]

                def _rebuild_feature_list() -> None:
                    # Preserve current selections before clearing
                    for _fid, _cb in feature_checkbox_refs.items():
                        if _cb.value and _fid not in state["feature_ids"]:
                            state["feature_ids"].append(_fid)
                        elif not _cb.value and _fid in state["feature_ids"]:
                            state["feature_ids"].remove(_fid)
                    for _fid, _cb in new_feat_checkbox_refs.items():
                        if _cb.value and _fid not in state["new_feature_ids"]:
                            state["new_feature_ids"].append(_fid)
                        elif not _cb.value and _fid in state["new_feature_ids"]:
                            state["new_feature_ids"].remove(_fid)

                    feature_checkbox_refs.clear()
                    new_feat_checkbox_refs.clear()
                    features_container.clear()

                    selected_pt = state.get("product_type_filter") or "All"
                    if selected_pt and selected_pt != "All":
                        visible_features = [f for f in all_features if f.get("product_type") == selected_pt]
                        pt_info_label.set_text(f"Filtered by product type: {selected_pt}")
                    else:
                        visible_features = list(all_features)
                        pt_info_label.set_text("")

                    vis_by_cat: dict[str, list[dict]] = {}
                    for feat in visible_features:
                        cat = feat.get("category") or "Other"
                        vis_by_cat.setdefault(cat, []).append(feat)

                    with features_container:
                        if not visible_features:
                            ui.label("No features match the selected product type.").classes("text-grey")
                            return

                        all_pre_selected = all(f["id"] in state["feature_ids"] for f in visible_features)
                        select_all_cb = ui.checkbox(
                            f"Select all ({len(visible_features)} features)",
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
                            if not feature_checkbox_refs:
                                return
                            all_checked = all(cb.value for cb in feature_checkbox_refs.values())
                            if select_all_cb.value != all_checked:
                                _programmatic_select_all[0] = True
                                select_all_cb.value = all_checked
                                _programmatic_select_all[0] = False

                        ui.separator()

                        for cat_name, cat_features in vis_by_cat.items():
                            ui.label(cat_name).classes("text-subtitle2 q-mt-sm text-primary")

                            with ui.grid(columns="1.3fr 1.7fr 90px 70px 140px").classes("w-full q-pl-md items-center"):
                                ui.label("Feature").classes("text-caption text-grey")
                                ui.label("Description").classes("text-caption text-grey")
                                ui.label("Complexity").classes("text-caption text-grey text-center")
                                ui.label("New?").classes("text-caption text-grey text-center")
                                ui.label("Scope").classes("text-caption text-grey text-center")

                                for feat in cat_features:
                                    fid = feat["id"]
                                    fname = feat.get("name", f"Feature {fid}")
                                    fweight = feat.get("complexity_weight", 1.0)
                                    _is_project = not feat.get("is_global", True)

                                    cb = ui.checkbox(
                                        fname,
                                        value=(fid in state["feature_ids"]),
                                    )
                                    feature_checkbox_refs[fid] = cb

                                    _fdesc = (feat.get("description") or "").strip()
                                    ui.label(_fdesc or "—").classes(
                                        "text-caption text-grey"
                                    ).style("white-space: normal; line-height: 1.25;")

                                    ui.label(f"x{fweight:.1f}").classes("text-center")

                                    new_cb = ui.checkbox(
                                        "New",
                                        value=(fid in state["new_feature_ids"]),
                                    ).props("dense color=orange").classes("text-caption")
                                    new_feat_checkbox_refs[fid] = new_cb

                                    # Scope cell: project features show a badge + (for
                                    # APPROVER+) a Promote-to-global action; globals blank.
                                    if _is_project:
                                        with ui.row().classes("items-center gap-1 justify-center"):
                                            ui.badge("project", color="orange").props("dense")
                                            ui.button(
                                                icon="edit",
                                                on_click=lambda _e=None, f=feat: _edit_custom_feature(f),
                                            ).props("flat dense round size=sm color=primary") \
                                                .tooltip("Edit this project feature")
                                            if _can_promote:
                                                ui.button(
                                                    icon="public",
                                                    on_click=lambda _e=None, f=feat: _promote_feature(f),
                                                ).props("flat dense round size=sm color=primary") \
                                                    .tooltip("Promote to global catalog")
                                    else:
                                        ui.label("").classes("text-center")

                                    def _make_sync(f_id: int, n_cb: ui.checkbox):
                                        def _sync(e):
                                            if not feature_checkbox_refs[f_id].value:
                                                n_cb.value = False
                                            _update_select_all_state()
                                        return _sync
                                    cb.on("update:model-value", _make_sync(fid, new_cb))

                _rebuild_feature_list()
                await _refresh_presets()

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
                        # Rebuild DUT/Profile lists with current product type filter
                        _rebuild_dut_prof_lists()
                        stepper.next()
                    ui.button("Back", on_click=_back_s3).props("flat")
                    ui.button("Next", on_click=_next_s3).props("color=primary icon-right=arrow_forward")

            # Step 4 — DUT x Profile Matrix
            with ui.step("DUT x Profile Matrix"):
                ui.label("Select DUTs and Profiles, then tick the combinations.").classes("text-body2 text-grey q-mb-md")

                dut_pt_info = ui.label("").classes("text-caption text-primary q-mb-sm")

                dut_cb_refs: dict[int, ui.checkbox] = {}
                prof_cb_refs: dict[int, ui.checkbox] = {}
                matrix_cb_refs: dict[tuple[int, int], ui.checkbox] = {}
                # DUTs, then Profiles, then the combination matrix below them.
                dut_container = ui.column().classes("w-full")
                prof_container = ui.column().classes("w-full")
                matrix_container = ui.column().classes("w-full q-mt-md")

                def _rebuild_matrix():
                    matrix_container.clear()
                    # Apply product type filter to matrix
                    _mpt = state.get("product_type_filter") or "All"
                    if _mpt and _mpt != "All":
                        _m_duts = [d for d in all_duts if d.get("product_type") == _mpt or not d.get("product_type")]
                        _m_profs = [p for p in all_profiles if p.get("product_type") == _mpt or not p.get("product_type")]
                    else:
                        _m_duts = all_duts
                        _m_profs = all_profiles
                    sel_duts = [d for d in _m_duts if dut_cb_refs.get(d["id"]) and dut_cb_refs[d["id"]].value]
                    sel_profs = [p for p in _m_profs if prof_cb_refs.get(p["id"]) and prof_cb_refs[p["id"]].value]
                    matrix_cb_refs.clear()
                    if not sel_duts or not sel_profs:
                        with matrix_container:
                            ui.label("Select at least one DUT and one Profile.").classes("text-grey text-caption")
                        return
                    with matrix_container:
                        ui.label("Combination Matrix").classes("text-subtitle2 q-mb-sm")
                        n_cols = len(sel_profs) + 1
                        # Wrap the matrix in a horizontally scrollable container so
                        # wide DUT×Profile grids scroll on narrow screens instead of
                        # breaking the layout.
                        with ui.element("div").classes("w-full").style(
                            "overflow-x: auto; -webkit-overflow-scrolling: touch;"
                        ):
                            with ui.grid(columns=n_cols).classes("items-center"):
                                ui.label("DUT \\ Profile").classes("text-caption text-grey text-weight-bold")
                                for prof in sel_profs:
                                    ui.label(prof.get("name", f"P{prof['id']}")).classes("text-caption text-center text-weight-bold")
                                for dut in sel_duts:
                                    ui.label(dut.get("name", f"D{dut['id']}")).classes("text-caption")
                                    for prof in sel_profs:
                                        key = (dut["id"], prof["id"])
                                        pre_checked = key in [tuple(pair) for pair in state["dut_profile_matrix"]]
                                        cb = ui.checkbox("", value=pre_checked).props("dense")
                                        matrix_cb_refs[key] = cb

                def _rebuild_dut_prof_lists() -> None:
                    for _did, _cb in dut_cb_refs.items():
                        if _cb.value and _did not in state["dut_ids"]:
                            state["dut_ids"].append(_did)
                        elif not _cb.value and _did in state["dut_ids"]:
                            state["dut_ids"].remove(_did)
                    for _pid, _cb in prof_cb_refs.items():
                        if _cb.value and _pid not in state["profile_ids"]:
                            state["profile_ids"].append(_pid)
                        elif not _cb.value and _pid in state["profile_ids"]:
                            state["profile_ids"].remove(_pid)

                    dut_cb_refs.clear()
                    prof_cb_refs.clear()
                    dut_container.clear()
                    prof_container.clear()

                    selected_pt = state.get("product_type_filter") or "All"
                    if selected_pt and selected_pt != "All":
                        visible_duts = [d for d in all_duts if d.get("product_type") == selected_pt or not d.get("product_type")]
                        visible_profs = [p for p in all_profiles if p.get("product_type") == selected_pt or not p.get("product_type")]
                        dut_pt_info.set_text(f"Filtered by product type: {selected_pt} (items without product type are also shown)")
                    else:
                        visible_duts = list(all_duts)
                        visible_profs = list(all_profiles)
                        dut_pt_info.set_text("")

                    with dut_container:
                        if not visible_duts:
                            ui.label("No DUT types found.").classes("text-grey")
                        else:
                            ui.label("DUT Types").classes("text-subtitle2 q-mb-xs")
                            with ui.element("div").classes("w-full q-mb-md").style("max-height: 250px; overflow-y: auto;"):
                                with ui.element("table").classes("w-full").style("border-collapse: collapse;"):
                                    for dut in visible_duts:
                                        did = dut["id"]
                                        with ui.element("tr").style("border-bottom: 1px solid rgba(128,128,128,0.2);"):
                                            with ui.element("td").style("padding: 2px 4px; width: 40px;"):
                                                cb = ui.checkbox("", value=(did in state["dut_ids"])).props("dense")
                                                dut_cb_refs[did] = cb
                                                cb.on("update:model-value", lambda _: _rebuild_matrix())
                                            with ui.element("td").style("padding: 2px 4px;"):
                                                ui.label(dut.get("name", f"DUT {did}")).classes("text-body2")
                                            with ui.element("td").style("padding: 2px 4px;"):
                                                ui.label(dut.get("category", "")).classes("text-caption text-grey")

                    with prof_container:
                        if not visible_profs:
                            ui.label("No profiles found.").classes("text-grey")
                        else:
                            ui.label("Test Profiles").classes("text-subtitle2 q-mb-xs")
                            with ui.element("div").classes("w-full q-mb-md").style("max-height: 200px; overflow-y: auto;"):
                                with ui.element("table").classes("w-full").style("border-collapse: collapse;"):
                                    for prof in visible_profs:
                                        pid = prof["id"]
                                        with ui.element("tr").style("border-bottom: 1px solid rgba(128,128,128,0.2);"):
                                            with ui.element("td").style("padding: 2px 4px; width: 40px;"):
                                                cb = ui.checkbox("", value=(pid in state["profile_ids"])).props("dense")
                                                prof_cb_refs[pid] = cb
                                                cb.on("update:model-value", lambda _: _rebuild_matrix())
                                            with ui.element("td").style("padding: 2px 4px;"):
                                                ui.label(prof.get("name", f"Profile {pid}")).classes("text-body2")

                    _rebuild_matrix()

                _rebuild_dut_prof_lists()

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

                with ui.card().classes("w-full q-pa-sm q-mb-md").props("flat bordered"):
                    ui.label("PR Fix Calculation:").classes("text-caption text-weight-bold")
                    for _info_line in [
                        "Each PR is validated per DUT (scales with DUT count)",
                        "Simple: 2h x DUT count, Medium: 4h x DUT count, Complex: 8h x DUT count",
                        "Total PR Fix Hours = (simple x 2 + medium x 4 + complex x 8) x DUT_count [x profile_count if enabled]",
                        "Configurable via 'pr_fix_base_hours' and 'pr_scales_with_profile' settings",
                    ]:
                        ui.label(f"  {_info_line}").classes("text-caption text-grey")

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
                                with ui.card().classes("w-full q-pa-xs q-mb-xs").props("flat bordered"):
                                    with ui.row().classes("items-center q-gutter-sm w-full"):
                                        _num = ui.input("PR #", value=pr.get("pr_number", "")).classes("w-24")
                                        _link = ui.input("Link", value=pr.get("link", "")).classes("flex-1")
                                        _pri_opts_e = list(_pr_priority_list)
                                        _pri_val_e = pr.get("priority", _pri_opts_e[1] if len(_pri_opts_e) > 1 else _pri_opts_e[0])
                                        if _pri_val_e not in _pri_opts_e:
                                            _pri_opts_e.append(_pri_val_e)
                                        _pri = ui.select(options=_pri_opts_e, value=_pri_val_e, label="Priority").classes("w-28")
                                        _cx_opts_e = ["simple", "medium", "complex"]
                                        _cx_val_e = pr.get("complexity", "simple")
                                        if _cx_val_e not in _cx_opts_e:
                                            _cx_opts_e.append(_cx_val_e)
                                        _cx = ui.select(options=_cx_opts_e, value=_cx_val_e, label="Complexity").classes("w-32")
                                        _st_options_e = ["Open", "In Progress", "Postponed", "Merged", "Closed"]
                                        _st_val_e = pr.get("status", "Open")
                                        if _st_val_e not in _st_options_e:
                                            _st_options_e.append(_st_val_e)
                                        _st = ui.select(options=_st_options_e, value=_st_val_e, label="Status").classes("w-28")

                                        def _make_remove(i: int):
                                            def _remove():
                                                pr_detail_rows.pop(i)
                                                _render_pr_details()
                                            return _remove
                                        ui.button(icon="close", on_click=_make_remove(idx)).props("flat dense round color=negative size=sm")

                                    with ui.row().classes("items-center q-gutter-sm w-full"):
                                        _ta = ui.switch("Test Available", value=pr.get("test_available", True))
                                    # Collapsible, collapsed by default (can be many lines).
                                    with ui.expansion("Description", icon="notes").classes("w-full").props("dense"):
                                        _desc = ui.textarea(value=pr.get("description", ""), placeholder="Markdown + Jira macros supported").classes("w-full").props("autogrow")

                                    def _make_updater(i: int, n=_num, l=_link, p=_pri, c=_cx, s=_st, d=_desc, ta=_ta):
                                        def _upd(_=None):
                                            if i < len(pr_detail_rows):
                                                pr_detail_rows[i] = {"pr_number": n.value or "", "link": l.value or "", "priority": p.value or "", "complexity": c.value or "simple", "status": s.value or "Open", "description": d.value or "", "test_available": bool(ta.value)}
                                        return _upd
                                    updater = _make_updater(idx)
                                    _num.on("update:model-value", updater)
                                    _link.on("update:model-value", updater)
                                    _pri.on("update:model-value", updater)
                                    _cx.on("update:model-value", updater)
                                    _st.on("update:model-value", updater)
                                    _desc.on("update:model-value", updater)
                                    _ta.on("update:model-value", updater)
                                    _ta.on("update:model-value", updater)

                    def _add_pr_detail() -> None:
                        _default_pri = _pr_priority_list[1] if len(_pr_priority_list) > 1 else _pr_priority_list[0]
                        pr_detail_rows.append({"pr_number": "", "link": "", "priority": _default_pri, "complexity": "simple", "status": "Open", "description": "", "test_available": True})
                        _render_pr_details()

                    with ui.row().classes("items-center gap-2"):
                        ui.button("Add PR Detail", icon="add", on_click=_add_pr_detail).props("flat dense color=primary")

                        async def _import_from_jira_edit(
                            _pr_rows=pr_detail_rows,
                            _render=_render_pr_details,
                        ) -> None:
                            try:
                                jira_config = await api_get("/integrations/JIRA")
                                if not jira_config.get("enabled"):
                                    ui.notify("Jira integration is not enabled.", type="warning")
                                    return
                            except Exception:
                                ui.notify("Jira integration not configured.", type="warning")
                                return

                            with ui.dialog().props("maximized=false") as dlg, \
                                    ui.card().classes("w-[1100px] max-w-[95vw] max-h-[85vh]") \
                                    .style("display:flex; flex-direction:column;"):
                                with ui.row().classes("items-center w-full q-mb-sm").style("flex:0 0 auto;"):
                                    ui.label("Import PR Items from Registry").classes("text-h6")
                                    ui.element("div").classes("ed-toolbar-grow")
                                    _fetch_btn = ui.button("Reload", icon="refresh").props("color=secondary flat dense")
                                with ui.element("div").classes("w-full").style(
                                    "flex:1 1 auto; overflow:auto; min-height:0;"
                                ):
                                    jira_items_table = ui.table(
                                        columns=[
                                            {"name": "key", "label": "Key", "field": "key", "align": "left", "sortable": True},
                                            {"name": "summary", "label": "Summary", "field": "summary", "align": "left"},
                                            {"name": "description", "label": "Description", "field": "description", "align": "left"},
                                            {"name": "priority", "label": "Priority", "field": "priority", "align": "left", "sortable": True},
                                            {"name": "status", "label": "Status", "field": "status", "align": "left", "sortable": True},
                                        ],
                                        rows=[],
                                        row_key="key",
                                        selection="multiple",
                                        pagination={"rowsPerPage": 10},
                                    ).classes("w-full")

                                async def _fetch() -> None:
                                    items = await api_get("/integrations/JIRA/pr-items")
                                    jira_items_table.rows = items if isinstance(items, list) else []
                                    jira_items_table.update()
                                    ui.notify(f"Loaded {len(jira_items_table.rows)} PR item(s).", type="positive")

                                _fetch_btn.on("click", run_async(
                                    _fetch_btn, _fetch, error_prefix="Failed to load"))

                                def _do_import() -> None:
                                    selected = jira_items_table.selected
                                    if not selected:
                                        ui.notify("No items selected.", type="warning")
                                        return
                                    imported = 0
                                    for item in selected:
                                        key = item.get("key", "")
                                        existing_nums = {r.get("pr_number") for r in _pr_rows}
                                        if key and key not in existing_nums:
                                            priority = (item.get("priority") or "Medium").lower()
                                            complexity = "simple"
                                            if priority in ("high", "highest", "critical", "blocker"):
                                                complexity = "complex"
                                            elif priority in ("medium",):
                                                complexity = "medium"
                                            _pr_rows.append({
                                                "pr_number": key,
                                                "link": item.get("link") or "",
                                                "description": item.get("description") or item.get("summary", ""),
                                                "priority": item.get("priority", "Medium"),
                                                "complexity": complexity,
                                                "status": item.get("status", "Open"),
                                                "test_available": True,
                                            })
                                            imported += 1
                                    _render()
                                    ui.notify(f"Imported {imported} PR item(s).", type="positive")
                                    dlg.close()

                                with ui.row().classes("q-mt-md gap-2 w-full justify-end").style(
                                    "flex:0 0 auto; border-top:1px solid var(--ed-line); padding-top:12px;"
                                ):
                                    ui.button("Cancel", on_click=dlg.close).props("flat")
                                    ui.button("Import Selected", icon="download", on_click=_do_import).props("color=primary")

                            await _fetch()
                            dlg.open()

                        ui.button("Import from Jira", icon="bug_report", on_click=_import_from_jira_edit).props("flat dense color=secondary")

                    _render_pr_details()

                # -- Documentation Deliverables (edit) --
                ui.separator().classes("q-mt-lg")
                with ui.expansion("Documentation Deliverables", icon="description").classes("w-full"):
                    ui.label("Select documents to create and specify count.").classes("text-body2 text-grey q-mb-sm")
                    doc_types_container = ui.column().classes("w-full")
                    doc_cb_refs: dict[int, ui.checkbox] = {}
                    doc_count_refs: dict[int, ui.number] = {}

                    async def _load_doc_types() -> None:
                        try:
                            doc_types = await api_get("/document-types")
                        except Exception:
                            doc_types = []
                        doc_types_container.clear()
                        doc_cb_refs.clear()
                        doc_count_refs.clear()
                        saved_ids = state.get("document_type_ids", [])
                        saved_counts = state.get("document_counts", {})
                        with doc_types_container:
                            if not doc_types:
                                ui.label("No document types configured.").classes("text-grey")
                                return
                            with ui.grid(columns="1fr 120px 200px").classes("w-full q-pl-md items-center"):
                                ui.label("Document Type").classes("text-caption text-grey")
                                ui.label("Count").classes("text-caption text-grey text-center")
                                ui.label("Base Hours (each)").classes("text-caption text-grey")
                                for dt in doc_types:
                                    did = dt["id"]
                                    cb = ui.checkbox(dt.get("name", ""), value=(did in saved_ids))
                                    doc_cb_refs[did] = cb
                                    cnt = ui.number("", value=int(saved_counts.get(str(did), 1)), min=1, step=1, precision=0).props("dense").classes("w-20")
                                    doc_count_refs[did] = cnt
                                    ui.label(f"{dt.get('base_effort_hours', 0):.1f}h").classes("text-caption")

                    await _load_doc_types()

                def _collect_prs():
                    state["pr_simple"] = int(pr_simple_input.value or 0)
                    state["pr_medium"] = int(pr_medium_input.value or 0)
                    state["pr_complex"] = int(pr_complex_input.value or 0)
                    state["pr_details"] = [pr for pr in pr_detail_rows if pr.get("pr_number")]
                    state["document_type_ids"] = [did for did, cb in doc_cb_refs.items() if cb.value]
                    state["document_counts"] = {str(did): int(cnt.value or 1) for did, cnt in doc_count_refs.items()}

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
                with ui.row().classes("w-full q-gutter-md"):
                    with ui.input(
                        _config_map.get("label_project_start_date") or "Project Start Date - T0 (optional)",
                        value=state.get("start_date") or "",
                    ).classes("flex-1") as start_date_input:
                        with ui.menu() as start_menu:
                            with ui.date().bind_value(start_date_input) as _start_dp:
                                _start_dp.on("update:model-value", lambda: start_menu.close())
                        with start_date_input.add_slot("append"):
                            ui.icon("edit_calendar").on("click", start_menu.open).classes("cursor-pointer")

                    with ui.input(
                        _config_map.get("label_testing_start_date") or "Testing Start Date (optional)",
                        value=state.get("testing_start_date") or "",
                    ).classes("flex-1") as testing_start_input:
                        with ui.menu() as testing_start_menu:
                            with ui.date().bind_value(testing_start_input) as _testing_dp:
                                _testing_dp.on("update:model-value", lambda: testing_start_menu.close())
                        with testing_start_input.add_slot("append"):
                            ui.icon("edit_calendar").on("click", testing_start_menu.open).classes("cursor-pointer")

                    with ui.input(
                        _config_map.get("label_deadline") or "Deadline (optional)",
                        value=state.get("delivery_date") or "",
                    ).classes("flex-1") as delivery_input:
                        with ui.menu() as delivery_menu:
                            with ui.date().bind_value(delivery_input) as _delivery_dp:
                                _delivery_dp.on("update:model-value", lambda: delivery_menu.close())
                        with delivery_input.add_slot("append"):
                            ui.icon("edit_calendar").on("click", delivery_menu.open).classes("cursor-pointer")

                working_days_input = ui.number("Working Days Available", value=state["working_days"], min=1, step=1, precision=0).classes("w-full q-mt-sm")

                ui.label(
                    "Used only for the feasibility / capacity check — it does NOT change "
                    "the calculated effort. The proposed delivery duration is the Proposed "
                    "Duration (elapsed) shown at the Review step."
                ).classes("text-caption text-grey q-mt-xs")

                auto_calc_label = ui.label("").classes("text-caption text-primary q-mt-xs")

                def _auto_calc_working_days() -> None:
                    sd = testing_start_input.value
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

                testing_start_input.on("update:model-value", lambda _: _auto_calc_working_days())
                delivery_input.on("update:model-value", lambda _: _auto_calc_working_days())

                team_size_input = ui.number("Team Size (testers)", value=state["team_size"], min=1, step=1, precision=0).classes("w-full q-mt-sm")
                leader_toggle = ui.switch("Include Test Leader effort", value=state["has_leader"]).classes("q-mt-sm")

                releases_input = ui.number(
                    "Expected Releases",
                    value=state["expected_releases"],
                    min=1,
                    step=1,
                    precision=0,
                ).classes("w-full q-mt-sm").tooltip(
                    "Number of releases within this estimation period. "
                    "Each additional release adds extra effort for regression and deployment."
                )

                # Team selector
                if all_teams:
                    ui.separator().classes("q-mt-md")
                    ui.label("Team (optional)").classes("text-subtitle2 q-mt-sm")
                    team_options = {t["id"]: t.get("name", f"Team {t['id']}") for t in all_teams}
                    team_select = ui.select(
                        options={None: "-- No Team --", **team_options},
                        value=state.get("team_id"),
                        label="Select Team",
                        with_input=True,
                        clearable=True,
                    ).classes("w-full q-mb-sm")

                    def _on_team_selected(e) -> None:
                        selected_team_id = e.args
                        state["team_id"] = selected_team_id if selected_team_id else None
                        if selected_team_id and all_team_members:
                            team_members = [m for m in all_team_members if m.get("team_id") == selected_team_id]
                            alloc_rows.clear()
                            for m in team_members:
                                alloc_rows.append({
                                    "team_member_id": m["id"],
                                    "role": m.get("role", "TESTER"),
                                    "allocated_hours": 0,
                                })
                            _render_alloc()

                    team_select.on("update:model-value", _on_team_selected)

                # Team allocation picker
                if all_team_members:
                    ui.separator().classes("q-mt-md")
                    ui.label("Team Allocation (optional)").classes("text-subtitle2 q-mt-sm")

                    with ui.card().classes("w-full q-pa-sm q-mb-sm").props("flat bordered"):
                        ui.label("How team parameters affect the calculation:").classes("text-caption text-weight-bold")
                        for line in [
                            "Team Size and Include Leader determine capacity (= working_days x (testers + leader) x hours/day) for feasibility.",
                            "Feasibility: <=80% = Feasible, 80-100% = At Risk, >100% = Not Feasible.",
                            "Team Allocation below is optional planning metadata — it records who works on the estimation but does not change calculated totals.",
                        ]:
                            ui.label(f"- {line}").classes("text-caption text-grey")

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

                # Risk items selection
                risk_cb_refs: dict[int, ui.checkbox] = {}
                if all_risk_items:
                    ui.separator().classes("q-mt-md")
                    ui.label("Risk Items (optional)").classes("text-subtitle2 q-mt-sm")
                    ui.label("Select applicable risks for this estimation.").classes("text-body2 text-grey q-mb-sm")

                    risks_by_cat: dict[str, list[dict]] = {}
                    for ri in all_risk_items:
                        rcat = ri.get("category") or "General"
                        risks_by_cat.setdefault(rcat, []).append(ri)

                    for rcat_name, rcat_items in risks_by_cat.items():
                        ui.label(rcat_name).classes("text-caption text-weight-bold text-primary q-mt-xs")
                        for ri in rcat_items:
                            rid = ri["id"]
                            rlabel = ri.get("name", f"Risk {rid}")
                            if ri.get("likelihood") or ri.get("impact"):
                                rlabel += f"  [{ri.get('likelihood', '?')}/{ri.get('impact', '?')}]"
                            rcb = ui.checkbox(
                                rlabel,
                                value=(rid in state.get("risk_item_ids", [])),
                            )
                            risk_cb_refs[rid] = rcb

                def _collect_delivery():
                    raw_start = start_date_input.value
                    state["start_date"] = raw_start if raw_start else None
                    raw_testing_start = testing_start_input.value
                    state["testing_start_date"] = raw_testing_start if raw_testing_start else None
                    raw = delivery_input.value
                    state["delivery_date"] = raw if raw else None
                    state["working_days"] = int(working_days_input.value or 20)
                    state["team_size"] = int(team_size_input.value or 1)
                    state["has_leader"] = bool(leader_toggle.value)
                    state["expected_releases"] = int(releases_input.value or 1)
                    if all_team_members:
                        state["team_allocations"] = [a for a in alloc_rows if a.get("team_member_id")]
                    state["risk_item_ids"] = [
                        rid for rid, rcb in risk_cb_refs.items() if rcb.value
                    ]

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
                            releases = state.get("expected_releases", 1)
                            if releases and releases > 1:
                                with ui.card().classes("q-pa-sm"):
                                    ui.label("Expected Releases").classes("text-caption text-grey")
                                    ui.label(str(releases)).classes("text-body2")
                            if state.get("project_goals"):
                                with ui.card().classes("q-pa-sm"):
                                    ui.label("Project Goals").classes("text-caption text-grey")
                                    ui.label(state["project_goals"]).classes("text-body2")
                            if state.get("target_customer"):
                                with ui.card().classes("q-pa-sm"):
                                    ui.label("Target Customer").classes("text-caption text-grey")
                                    ui.label(state["target_customer"]).classes("text-body2")

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
                            if res.get("pr_no_test_hours", 0) > 0:
                                _hours_card("PR Test Creation", res["pr_no_test_hours"], "science")
                            _hours_card("Study Hours", res.get("study_hours", 0), "school")
                            if res.get("release_extra_hours", 0) > 0:
                                _hours_card("Release Extra Hours", res["release_extra_hours"], "rocket_launch")
                            if res.get("documentation_hours", 0) > 0:
                                _hours_card("Documentation Hours", res["documentation_hours"], "description")
                            _hours_card("Buffer Hours", res.get("buffer_hours", 0), "security")
                            _hours_card("Grand Total Hours", res.get("grand_total_hours", 0), "summarize")
                            _gt_days = res.get("grand_total_days", 0)
                            _hours_card("Grand Total (Person-Days)", _gt_days, "calendar_today")
                            _ww = round(_gt_days / 5.0, 1) if _gt_days else 0
                            if _ww > 0:
                                _hours_card("Working Weeks", _ww, "date_range")
                            _cap = res.get("capacity_hours", 0)
                            if _cap > 0:
                                _hours_card("Capacity Hours", _cap, "fitness_center")

                        _el_days = res.get("elapsed_days", 0)
                        _el_weeks = res.get("elapsed_weeks", 0)
                        if _el_days > 0:
                            ui.separator().classes("q-mt-sm")
                            ui.label("Proposed Duration (elapsed, wall-clock)").classes("text-subtitle2 q-mt-xs q-mb-xs")
                            ui.label(
                                "The actual time to deliver given the team — use this as the "
                                "estimation proposal. Parallelizable tasks are divided by team "
                                "size; sequential tasks are not."
                            ).classes("text-caption text-grey q-mb-xs")
                            with ui.row().classes("q-gutter-md flex-wrap q-mb-sm"):
                                _hours_card("Elapsed Hours", res.get("elapsed_hours", 0), "hourglass_top")
                                _hours_card("Elapsed Days", _el_days, "today")
                                _hours_card("Elapsed Weeks", _el_weeks, "date_range")

                        flags = res.get("risk_flags", [])
                        if flags:
                            ui.label("Risk Flags").classes("text-subtitle2 q-mt-sm q-mb-xs")
                            with ui.row().classes("flex-wrap q-gutter-xs"):
                                for flag in flags:
                                    ui.chip(flag.replace("_", " ").title(), icon="warning").props("color=negative outline dense")

                        # Task breakdown table
                        _tasks = res.get("tasks", [])
                        if _tasks:
                            # Initialise per-task assigned_testers in state
                            if "task_assigned_testers" not in state:
                                state["task_assigned_testers"] = {}
                            for t in _tasks:
                                t["assigned_testers"] = state["task_assigned_testers"].get(t["name"], 1)
                            ui.label("Task Breakdown").classes("text-subtitle2 q-mt-sm q-mb-xs")
                            _tcols = [
                                {"name": "feature_name", "label": "Feature", "field": "feature_name", "align": "left", "sortable": True},
                                {"name": "name", "label": "Task", "field": "name", "align": "left", "sortable": True},
                                {"name": "task_type", "label": "Type", "field": "task_type", "align": "left"},
                                {"name": "base_hours", "label": "Base h", "field": "base_hours", "align": "right"},
                                {"name": "formula", "label": "Formula", "field": "formula", "align": "left"},
                                {"name": "calculated_hours", "label": "Calc h", "field": "calculated_hours", "align": "right"},
                                {"name": "assigned_testers", "label": "Resources", "field": "assigned_testers", "align": "center"},
                            ]
                            _ttbl = ui.table(columns=_tcols, rows=_tasks, row_key="name", pagination={"rowsPerPage": 15}).classes("w-full shadow-1")
                            _ttbl.add_slot(
                                "body-cell-feature_name",
                                r"""
                                <q-td :props="props">
                                    <q-badge v-if="props.value" outline color="primary" :label="props.value" />
                                    <span v-else class="text-grey-5 text-italic">Global</span>
                                </q-td>
                                """,
                            )
                            _ttbl.add_slot(
                                "body-cell-assigned_testers",
                                r"""
                                <q-td :props="props">
                                    <q-input
                                        v-model.number="props.row.assigned_testers"
                                        type="number"
                                        dense
                                        outlined
                                        :min="1"
                                        style="max-width: 70px"
                                        @update:model-value="(v) => $parent.$emit('update_testers', {name: props.row.name, value: v})"
                                    />
                                </q-td>
                                """,
                            )
                            _ttbl.on(
                                "update_testers",
                                lambda e: state["task_assigned_testers"].update(
                                    {e.args["name"]: max(1, int(e.args["value"] or 1))}
                                ),
                            )

                async def run_calculate():
                    # Re-entrancy + double-submit guard: disable the button and
                    # show Quasar's loading spinner for the duration of the call,
                    # but keep the inline result rendering that follows.
                    if getattr(calc_btn, "_busy", False):
                        return
                    calc_btn._busy = True
                    calc_btn.enabled = False
                    calc_btn.props("loading")
                    try:
                        await _run_calculate_body()
                    finally:
                        calc_btn._busy = False
                        calc_btn.enabled = True
                        calc_btn.props(remove="loading")

                async def _run_calculate_body():
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
                        "expected_releases": state.get("expected_releases", 1),
                        "risk_item_ids": state.get("risk_item_ids", []),
                        "document_type_ids": state.get("document_type_ids", []),
                        "document_counts": state.get("document_counts", {}),
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
                        "start_date": state.get("start_date") or None,
                        "testing_start_date": state.get("testing_start_date") or None,
                        "expected_delivery": state.get("delivery_date") or None,
                        "team_allocations": state.get("team_allocations", []),
                        "expected_releases": state.get("expected_releases", 1),
                        "project_goals": state.get("project_goals") or None,
                        "target_customer": state.get("target_customer") or None,
                        "project_reference": state.get("project_reference") or None,
                        "team_id": state.get("team_id"),
                        "risk_item_ids": state.get("risk_item_ids", []),
                        "document_type_ids": state.get("document_type_ids", []),
                        "document_counts": state.get("document_counts", {}),
                        "task_assigned_testers": state.get("task_assigned_testers", {}),
                        "product_type_filter": state.get("product_type_filter", "All"),
                        "applied_presets": state.get("applied_presets", []),
                    }
                    if _is_draft_edit:
                        await api_put(f"/estimations/{estimation_id}/draft", json=payload)
                        ui.notify("Draft updated.", type="positive")
                    else:
                        saved = await api_put(f"/estimations/{estimation_id}/revise", json=payload)
                        new_ver = saved.get("version", "?")
                        ui.notify(f"Revision saved (v{new_ver}).", type="positive")
                    ui.navigate.to(f"/estimation/{estimation_id}")

                _render_summary()

                with ui.stepper_navigation():
                    ui.button("Back", on_click=lambda: stepper.previous()).props("flat")
                    calc_btn = ui.button("Calculate", icon="calculate", on_click=run_calculate).props("color=secondary")
                    save_btn = ui.button(
                        "Save Draft" if _is_draft_edit else "Save Revision",
                        icon="save",
                    ).props("color=primary")
                    save_btn.on("click", run_async(
                        save_btn, save_revision, error_prefix="Save failed"))
