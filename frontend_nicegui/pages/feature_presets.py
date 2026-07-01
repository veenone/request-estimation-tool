"""Feature Presets management page — admin view to edit/delete presets.

Estimators create presets from the estimation wizard; this page lets them be
renamed, re-described, re-scoped, and deleted.

Route: /feature-presets
API:
  GET    /feature-presets
  POST   /feature-presets
  PUT    /feature-presets/{id}
  DELETE /feature-presets/{id}
"""

from nicegui import ui
from frontend_nicegui.app import (
    api_delete,
    api_get,
    api_post,
    api_put,
    is_authenticated,
    loading_state,
    run_async,
    show_error_page,
    sidebar,
)


@ui.page("/feature-presets")
async def feature_presets_page() -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    all_rows: list[dict] = []
    feature_options: dict[int, str] = {}
    product_types: list[str] = []

    with ui.column().classes("w-full q-pa-md").style("gap: 0;"):

        with ui.element("div").classes("ed-toolbar"):
            ui.button("New Preset", icon="add", on_click=lambda: _open_dialog(None)) \
                .props("flat dense color=primary")
            ui.element("div").classes("ed-toolbar-grow")
            with ui.element("div").classes("ed-status-now"):
                ui.element("span").classes("ed-status-dot")
                _total_label = ui.label("TOTAL · 0").classes("ed-mono")

        with ui.element("div").classes("ed-shell"):

            ui.label("Feature Presets").classes("text-h4 q-mb-xs")
            ui.label(
                "Reusable bundles of features that estimators can apply in the wizard. "
                "Presets created there can be renamed, re-scoped, and removed here."
            ).classes("text-body2 opacity-70").style("margin-bottom: 16px;")

            list_container = ui.column().classes("w-full gap-2")

        # ── Rendering ────────────────────────────────────────────
        def _render() -> None:
            list_container.clear()
            _total_label.set_text(f"TOTAL · {len(all_rows)}")
            with list_container:
                if not all_rows:
                    ui.label(
                        "No presets yet. Create one here or from the estimation wizard."
                    ).classes("text-grey q-pa-md")
                    return
                for p in all_rows:
                    with ui.element("div").classes("ed-card"):
                        with ui.row().classes("items-start justify-between w-full no-wrap"):
                            with ui.column().classes("gap-0").style("min-width: 0;"):
                                ui.label(p["name"]).classes("text-subtitle1 text-weight-bold")
                                _meta = f"{p['feature_count']} feature(s)"
                                if p.get("product_type"):
                                    _meta += f" · {p['product_type']}"
                                else:
                                    _meta += " · any product type"
                                if p.get("owner_name"):
                                    _meta += f" · by {p['owner_name']}"
                                ui.label(_meta).classes("text-caption text-grey")
                                if p.get("description"):
                                    ui.label(p["description"]).classes("text-body2 q-mt-xs") \
                                        .style("white-space: normal;")
                            with ui.row().classes("items-center gap-1 no-wrap"):
                                ui.button(icon="edit",
                                          on_click=lambda _=None, r=p: _open_dialog(r)) \
                                    .props("flat dense round color=primary").tooltip("Edit preset")
                                ui.button(icon="delete",
                                          on_click=lambda _=None, r=p: _confirm_delete(r)) \
                                    .props("flat dense round color=negative").tooltip("Delete preset")

        async def refresh() -> None:
            nonlocal all_rows, feature_options, product_types
            try:
                feats = await api_get("/features")
                feature_options = {f["id"]: f.get("name", f"Feature {f['id']}") for f in feats}
            except Exception:
                feature_options = {}
            try:
                product_types = await api_get("/configuration/product_types")
                product_types = product_types if isinstance(product_types, list) else []
            except Exception:
                product_types = []
            try:
                presets = await api_get("/feature-presets")
                all_rows = [
                    {
                        "id": p["id"],
                        "name": p.get("name", ""),
                        "description": p.get("description") or "",
                        "product_type": p.get("product_type") or "",
                        "feature_ids": p.get("feature_ids", []),
                        "feature_count": len(p.get("feature_ids", [])),
                        "owner_name": p.get("owner_name") or "",
                    }
                    for p in presets
                ]
                _render()
            except Exception as exc:
                ui.notify(f"Failed to load presets: {exc}", type="negative")

        # ── Add / Edit dialog ────────────────────────────────────
        def _open_dialog(row: dict | None) -> None:
            editing = bool(row and "id" in row)
            pt_opts = ["All"] + product_types
            with ui.dialog() as dlg, ui.card().classes("w-[min(560px,94vw)]"):
                ui.label("Edit preset" if editing else "New preset").classes("text-h6 q-mb-sm")
                name_inp = ui.input(
                    "Name *", value=(row.get("name", "") if editing else ""),
                ).classes("w-full").props("autofocus")
                desc_inp = ui.textarea(
                    "Description", value=(row.get("description", "") if editing else ""),
                ).classes("w-full").props("autogrow")
                pt_inp = ui.select(
                    pt_opts, label="Product Type",
                    value=((row.get("product_type") or "All") if editing else "All"),
                ).classes("w-full")
                feat_inp = ui.select(
                    feature_options, label="Features *", multiple=True,
                    value=(list(row.get("feature_ids", [])) if editing else []),
                ).props("use-chips").classes("w-full")

                async def _save() -> None:
                    name = (name_inp.value or "").strip()
                    fids = list(feat_inp.value or [])
                    if not name:
                        ui.notify("Preset name is required.", type="warning")
                        return
                    if not fids:
                        ui.notify("Select at least one feature.", type="warning")
                        return
                    payload = {
                        "name": name,
                        "description": (desc_inp.value or "").strip() or None,
                        "product_type": (None if pt_inp.value in (None, "All") else pt_inp.value),
                        "feature_ids": fids,
                    }
                    if editing:
                        await api_put(f"/feature-presets/{row['id']}", json=payload)
                    else:
                        await api_post("/feature-presets", json=payload)
                    dlg.close()
                    await refresh()

                with ui.row().classes("w-full justify-end q-mt-md gap-2"):
                    ui.button("Cancel", on_click=dlg.close).props("flat")
                    save_btn = ui.button("Save").props("color=primary")
                    save_btn.on("click", run_async(
                        save_btn, _save,
                        success="Preset saved.",
                        error_prefix="Could not save preset",
                    ))
            dlg.open()

        # ── Delete confirm ───────────────────────────────────────
        def _confirm_delete(row: dict) -> None:
            with ui.dialog() as dlg, ui.card().classes("w-[min(420px,92vw)]"):
                ui.label("Delete preset?").classes("text-h6")
                ui.label(
                    f"'{row['name']}' will be permanently removed. Estimations already "
                    "created with it are not affected."
                ).classes("text-body2 text-grey")

                async def _do_delete() -> None:
                    await api_delete(f"/feature-presets/{row['id']}")
                    dlg.close()
                    await refresh()

                with ui.row().classes("w-full justify-end q-mt-md gap-2"):
                    ui.button("Cancel", on_click=dlg.close).props("flat")
                    del_btn = ui.button("Delete", icon="delete").props("color=negative")
                    del_btn.on("click", run_async(
                        del_btn, _do_delete,
                        success="Preset deleted.",
                        error_prefix="Could not delete preset",
                    ))
            dlg.open()

        try:
            async with loading_state("Loading presets…"):
                await refresh()
        except Exception as exc:
            show_error_page(exc)
