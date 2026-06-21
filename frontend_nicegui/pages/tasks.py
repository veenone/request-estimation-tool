"""Task Templates CRUD page for the NiceGUI frontend."""

from nicegui import ui

from frontend_nicegui.app import (
    api_delete,
    api_get,
    api_post,
    api_put,
    empty_state,
    is_authenticated,
    loading_state,
    run_async,
    show_error_page,
    sidebar,
)


@ui.page("/tasks")
async def tasks_page():
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    try:
        async with loading_state():
            templates = await api_get("/task-templates")
            features = await api_get("/features")
    except Exception as exc:
        show_error_page(exc)
        return

    # Fetch product types from config
    try:
        product_types: list[str] = await api_get("/configuration/product_types")
    except Exception:
        product_types = ["Payment", "Telco"]

    feature_map = {f["id"]: f["name"] for f in features}
    feature_options = {f["id"]: f["name"] for f in features}

    # ── State for filtering ─────────────────────────────────────
    state: dict = {"filter_type": "All", "filter_product_type": "All"}

    with ui.column().classes("w-full q-pa-md").style("gap: 0;"):

        # ── Sticky toolbar ──────────────────────────────────────
        with ui.element("div").classes("ed-toolbar"):
            ui.button("Add Template", icon="add",
                      on_click=lambda: _show_add_dialog()) \
                .props("flat dense color=primary")
            ui.element("div").classes("ed-toolbar-grow")
            with ui.element("div").classes("ed-status-now"):
                ui.element("span").classes("ed-status-dot")
                _total_label = ui.label("TOTAL · 0").classes("ed-mono")

        with ui.element("div").classes("ed-shell"):

            ui.label("Task Templates").classes("text-h4 q-mb-md")

            kpi_container = ui.element("div").classes("ed-strip")
            seg_container = ui.element("div").classes("ed-segmented")

            with ui.element("div").classes("ed-filter-row"):
                ui.label("Filter").classes("ed-filter-label")

                def _on_pt_change(e) -> None:
                    state["filter_product_type"] = e.args or "All"
                    _apply_filters()
                pt_sel = ui.select(["All"] + product_types,
                                   label="Product Type", value="All") \
                    .props("dense outlined").classes("w-48")
                pt_sel.on("update:model-value", _on_pt_change)

            # ── Table ──────────────────────────────────────────
            cols = [
                {"name": "name", "label": "Name", "field": "name", "align": "left", "sortable": True},
                {"name": "task_type", "label": "Type", "field": "task_type", "align": "left", "sortable": True},
                {"name": "feature", "label": "Feature", "field": "feature", "align": "left", "style": "max-width: 220px"},
                {"name": "base_effort_hours", "label": "Base Hours", "field": "base_effort_hours", "align": "right", "sortable": True},
                {"name": "scales_with_dut", "label": "Scales DUT", "field": "scales_with_dut", "align": "center"},
                {"name": "scales_with_profile", "label": "Scales Profile", "field": "scales_with_profile", "align": "center"},
                {"name": "is_pr_fix", "label": "PR Fix", "field": "is_pr_fix", "align": "center"},
                {"name": "product_type", "label": "Product Type", "field": "product_type", "align": "left", "sortable": True},
                {"name": "actions", "label": "Actions", "field": "actions", "align": "center"},
            ]

            with ui.element("div").classes("ed-card"):
                table = ui.table(
                    columns=cols,
                    rows=[],
                    row_key="id",
                    pagination={"rowsPerPage": 25},
                ).classes("w-full").props("flat")
                empty_holder = ui.element("div").classes("w-full")
                empty_holder.set_visibility(False)

        table.add_slot(
            "body-cell-actions",
            r"""
            <q-td :props="props">
                <q-btn dense flat round icon="edit" color="primary" size="sm"
                    @click="$parent.$emit('edit-row', props.row)" class="q-mr-xs"><q-tooltip>Edit</q-tooltip></q-btn>
                <q-btn dense flat round icon="delete" color="negative" size="sm"
                    @click="$parent.$emit('delete-row', props.row)"><q-tooltip>Delete</q-tooltip></q-btn>
            </q-td>
            """,
        )

        table.add_slot(
            "body-cell-feature",
            r"""
            <q-td :props="props">
                <div style="max-width: 200px; white-space: normal; word-break: break-word; line-height: 1.3;">
                    {{ props.value }}
                </div>
            </q-td>
            """,
        )

        # ------------------------------------------------------------------ #
        # Refresh helper                                                       #
        # ------------------------------------------------------------------ #
        def _build_rows() -> list[dict]:
            rows = []
            for t in templates:
                fids = t.get("feature_ids", [])
                # Backward compat: if feature_ids empty, fall back to feature_id
                if not fids and t.get("feature_id"):
                    fids = [t["feature_id"]]
                feat_names = [feature_map.get(fid, "?") for fid in fids]
                rows.append({
                    "id": t["id"],
                    "name": t["name"],
                    "task_type": t["task_type"],
                    "feature": ", ".join(feat_names) if feat_names else "Global",
                    "feature_ids": fids,
                    "base_effort_hours": t["base_effort_hours"],
                    "scales_with_dut": "Yes" if t.get("scales_with_dut") else "No",
                    "scales_with_profile": "Yes" if t.get("scales_with_profile") else "No",
                    "is_parallelizable": t.get("is_parallelizable", False),
                    "is_pr_fix": "Yes" if t.get("is_pr_fix") else "No",
                    "description": t.get("description") or "",
                    "product_type": t.get("product_type") or "",
                })
            return rows

        # ── KPI / segments / filters ────────────────────────────
        _TASK_TYPES = ["SETUP", "EXECUTION", "ANALYSIS", "REPORTING", "STUDY"]

        def _count_by_type(rows: list[dict], t: str) -> int:
            return sum(1 for r in rows if (r.get("task_type") or "") == t)

        def _set_type(t: str) -> None:
            state["filter_type"] = t
            _render_kpis()
            _render_segments()
            _apply_filters()

        def _render_kpis() -> None:
            kpi_container.clear()
            with kpi_container:
                rows = templates
                _total_label.set_text(f"TOTAL · {len(rows)}")
                top = sorted(_TASK_TYPES, key=lambda t: -_count_by_type(rows, t))[:3]

                def _tile(label: str, count: int, sub: str, key: str | None = None) -> None:
                    cls = "ed-strip-cell ed-stat-tile"
                    if key and state["filter_type"] == key:
                        cls += " active"
                    el = ui.element("div").classes(cls)
                    if key is not None:
                        el.on("click", lambda _, k=key: _set_type(k))
                    with el:
                        ui.label(label).classes("ed-eyebrow")
                        ui.label(str(count)).classes("ed-strip-num")
                        if sub:
                            ui.label(sub).classes("ed-stat-tile-sub")

                pr_n = sum(1 for r in rows if r.get("is_pr_fix"))
                _tile("Total Templates", len(rows),
                      f"{pr_n} PR-fix templates", key="All")
                for t in top:
                    n = _count_by_type(rows, t)
                    if n:
                        _tile(t.title(), n, "filter to type", key=t)

        def _render_segments() -> None:
            seg_container.clear()
            with seg_container:
                rows = templates
                def _seg(label: str, key: str, count: int) -> None:
                    cls = "ed-segmented-item" + (
                        " active" if state["filter_type"] == key else "")
                    btn = ui.element("button").classes(cls)
                    btn.on("click", lambda _, k=key: _set_type(k))
                    with btn:
                        ui.label(label)
                        ui.label(f"· {count}").classes("seg-count")
                _seg("All", "All", len(rows))
                for t in _TASK_TYPES:
                    n = _count_by_type(rows, t)
                    if n or t == state["filter_type"]:
                        _seg(t.title(), t, n)

        def _apply_filters() -> None:
            rows = _build_rows()
            if state["filter_type"] != "All":
                rows = [r for r in rows if r.get("task_type") == state["filter_type"]]
            if state["filter_product_type"] != "All":
                rows = [r for r in rows
                        if (r.get("product_type") or "") == state["filter_product_type"]]
            table.rows = rows
            table.update()
            no_rows = not rows
            empty_holder.clear()
            if no_rows:
                with empty_holder:
                    empty_state("No results match your filters.")
            empty_holder.set_visibility(no_rows)
            table.set_visibility(not no_rows)

        def _refresh_table():
            _render_kpis()
            _render_segments()
            _apply_filters()

        # ------------------------------------------------------------------ #
        # Add dialog                                                           #
        # ------------------------------------------------------------------ #
        async def _show_add_dialog():
            with ui.dialog() as dlg, ui.card().classes("w-[520px]"):
                ui.label("Add Task Template").classes("text-h6 q-mb-md")
                name_input = ui.input("Name *").props("autofocus").classes("w-full")
                type_select = ui.select(
                    options=["SETUP", "EXECUTION", "ANALYSIS", "REPORTING", "STUDY"],
                    label="Task Type",
                    value="EXECUTION",
                ).classes("w-full")
                feat_select = ui.select(
                    options=feature_options,
                    label="Features (optional, multi-select)",
                    value=[],
                    multiple=True,
                    with_input=True,
                ).classes("w-full")
                hours_input = ui.number("Base Effort Hours (default)", value=8, min=0.1, step=0.5).classes("w-full")

                # Per-feature hours override container
                ui.label("Per-Feature Hours Override").classes("text-caption text-grey q-mt-sm")
                ui.label("Leave blank to use the default base hours above.").classes("text-caption text-grey-6")
                feat_hours_container = ui.column().classes("w-full")
                feat_hours_inputs: dict[int, ui.number] = {}

                def _rebuild_feat_hours():
                    feat_hours_container.clear()
                    feat_hours_inputs.clear()
                    selected = list(feat_select.value or [])
                    if not selected:
                        return
                    with feat_hours_container:
                        for fid in selected:
                            fname = feature_map.get(fid, f"Feature {fid}")
                            inp = ui.number(
                                f"{fname}", value=None,
                                min=0.1, step=0.5,
                                placeholder="default",
                            ).classes("w-full")
                            feat_hours_inputs[fid] = inp

                feat_select.on("update:model-value", lambda _: _rebuild_feat_hours())

                dut_switch = ui.switch("Scales with DUT", value=False)
                prof_switch = ui.switch("Scales with Profile", value=False)
                para_switch = ui.switch("Is Parallelizable", value=False)
                pr_fix_switch = ui.switch("PR Fix Template", value=False).tooltip(
                    "If ON, this template is excluded when no PR fixes are expected"
                )
                pt_select = ui.select(
                    options=[""] + product_types,
                    label="Product Type (optional)",
                    value="",
                    with_input=True,
                    clearable=True,
                ).classes("w-full")
                desc_input = ui.textarea("Description").classes("w-full")

                async def _save():
                    if not name_input.value:
                        ui.notify("Name is required.", type="warning")
                        return
                    # Build feature_hours dict
                    fh: dict[str, float] = {}
                    for fid, inp in feat_hours_inputs.items():
                        if inp.value is not None and inp.value > 0:
                            fh[str(fid)] = float(inp.value)
                    payload = {
                        "name": name_input.value,
                        "task_type": type_select.value,
                        "feature_ids": list(feat_select.value or []),
                        "feature_hours": fh,
                        "base_effort_hours": float(hours_input.value or 8),
                        "scales_with_dut": dut_switch.value,
                        "scales_with_profile": prof_switch.value,
                        "is_parallelizable": para_switch.value,
                        "is_pr_fix": pr_fix_switch.value,
                        "description": desc_input.value or None,
                        "product_type": pt_select.value if pt_select.value else None,
                    }
                    new_tmpl = await api_post("/task-templates", json=payload)
                    templates.append(new_tmpl)
                    dlg.close()
                    _refresh_table()

                with ui.row().classes("w-full justify-end q-mt-md"):
                    ui.button("Cancel", on_click=dlg.close).props("flat")
                    save_btn = ui.button("Save").props("color=primary")
                    save_btn.on("click", run_async(save_btn, _save, success="Task template created.", error_prefix="Save failed"))

            dlg.open()

        # ------------------------------------------------------------------ #
        # Edit dialog                                                          #
        # ------------------------------------------------------------------ #
        async def _show_edit_dialog(row: dict):
            # Find original template by id
            tmpl = next((t for t in templates if t["id"] == row["id"]), None)
            if not tmpl:
                ui.notify("Template not found.", type="warning")
                return

            with ui.dialog() as dlg, ui.card().classes("w-[520px]"):
                ui.label("Edit Task Template").classes("text-h6 q-mb-md")
                name_input = ui.input("Name *", value=tmpl["name"]).props("autofocus").classes("w-full")
                type_select = ui.select(
                    options=["SETUP", "EXECUTION", "ANALYSIS", "REPORTING", "STUDY"],
                    label="Task Type",
                    value=tmpl["task_type"],
                ).classes("w-full")
                # Resolve current feature IDs
                _cur_fids = tmpl.get("feature_ids", [])
                if not _cur_fids and tmpl.get("feature_id"):
                    _cur_fids = [tmpl["feature_id"]]
                feat_select = ui.select(
                    options=feature_options,
                    label="Features (optional, multi-select)",
                    value=_cur_fids,
                    multiple=True,
                    with_input=True,
                ).classes("w-full")
                hours_input = ui.number(
                    "Base Effort Hours (default)",
                    value=tmpl["base_effort_hours"],
                    min=0.1,
                    step=0.5,
                ).classes("w-full")

                # Per-feature hours override
                _existing_fh = tmpl.get("feature_hours", {})
                ui.label("Per-Feature Hours Override").classes("text-caption text-grey q-mt-sm")
                ui.label("Leave blank to use the default base hours above.").classes("text-caption text-grey-6")
                feat_hours_container = ui.column().classes("w-full")
                feat_hours_inputs: dict[int, ui.number] = {}

                def _rebuild_feat_hours():
                    feat_hours_container.clear()
                    feat_hours_inputs.clear()
                    selected = list(feat_select.value or [])
                    if not selected:
                        return
                    with feat_hours_container:
                        for fid in selected:
                            fname = feature_map.get(fid, f"Feature {fid}")
                            cur_val = _existing_fh.get(str(fid))
                            inp = ui.number(
                                f"{fname}", value=cur_val,
                                min=0.1, step=0.5,
                                placeholder="default",
                            ).classes("w-full")
                            feat_hours_inputs[fid] = inp

                feat_select.on("update:model-value", lambda _: _rebuild_feat_hours())
                _rebuild_feat_hours()  # Show initial overrides

                dut_switch = ui.switch("Scales with DUT", value=bool(tmpl.get("scales_with_dut")))
                prof_switch = ui.switch("Scales with Profile", value=bool(tmpl.get("scales_with_profile")))
                para_switch = ui.switch("Is Parallelizable", value=bool(tmpl.get("is_parallelizable")))
                pr_fix_switch = ui.switch("PR Fix Template", value=bool(tmpl.get("is_pr_fix"))).tooltip(
                    "If ON, this template is excluded when no PR fixes are expected"
                )
                pt_select = ui.select(
                    options=[""] + product_types,
                    label="Product Type (optional)",
                    value=tmpl.get("product_type") or "",
                    with_input=True,
                    clearable=True,
                ).classes("w-full")
                desc_input = ui.textarea("Description", value=tmpl.get("description") or "").classes("w-full")

                async def _save():
                    if not name_input.value:
                        ui.notify("Name is required.", type="warning")
                        return
                    fh: dict[str, float] = {}
                    for fid, inp in feat_hours_inputs.items():
                        if inp.value is not None and inp.value > 0:
                            fh[str(fid)] = float(inp.value)
                    payload = {
                        "name": name_input.value,
                        "task_type": type_select.value,
                        "feature_ids": list(feat_select.value or []),
                        "feature_hours": fh,
                        "base_effort_hours": float(hours_input.value or 8),
                        "scales_with_dut": dut_switch.value,
                        "scales_with_profile": prof_switch.value,
                        "is_parallelizable": para_switch.value,
                        "is_pr_fix": pr_fix_switch.value,
                        "description": desc_input.value or None,
                        "product_type": pt_select.value if pt_select.value else None,
                    }
                    updated = await api_put(f"/task-templates/{tmpl['id']}", json=payload)
                    # Update in-memory list
                    for i, t in enumerate(templates):
                        if t["id"] == tmpl["id"]:
                            templates[i] = updated
                            break
                    dlg.close()
                    _refresh_table()

                with ui.row().classes("w-full justify-end q-mt-md"):
                    ui.button("Cancel", on_click=dlg.close).props("flat")
                    save_btn = ui.button("Save").props("color=primary")
                    save_btn.on("click", run_async(save_btn, _save, success="Task template updated.", error_prefix="Save failed"))

            dlg.open()

        # ------------------------------------------------------------------ #
        # Delete dialog                                                        #
        # ------------------------------------------------------------------ #
        async def _show_delete_dialog(row: dict):
            with ui.dialog() as dlg, ui.card().classes("w-80"):
                ui.label("Delete Task Template").classes("text-h6")
                ui.label(
                    f"Delete '{row.get('name', '')}' (ID {row.get('id')})? "
                    "This cannot be undone."
                ).classes("text-body2 q-mt-sm")

                async def _confirm():
                    await api_delete(f"/task-templates/{row['id']}")
                    templates[:] = [t for t in templates if t["id"] != row["id"]]
                    dlg.close()
                    _refresh_table()

                with ui.row().classes("q-mt-md justify-end w-full"):
                    ui.button("Cancel", on_click=dlg.close).props("flat")
                    del_btn = ui.button("Delete").props("color=negative")
                    del_btn.on("click", run_async(del_btn, _confirm, success="Task template deleted.", error_prefix="Delete failed"))

            dlg.open()

        # ------------------------------------------------------------------ #
        # Wire events                                                          #
        # ------------------------------------------------------------------ #
        table.on("edit-row", lambda e: _show_edit_dialog(e.args))
        table.on("delete-row", lambda e: _show_delete_dialog(e.args))

        _refresh_table()
