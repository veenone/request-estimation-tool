"""DUT Assets page — view Snipe-IT assets and import as DUT entries.

Route: /assets
API:
  GET  /integrations/SNIPE_IT/assets?categories=
  GET  /integrations/SNIPE_IT
  POST /dut-types
"""

import json

from nicegui import ui
from frontend_nicegui.app import (
    api_get,
    api_post,
    is_authenticated,
    sidebar,
)

_COLUMNS = [
    {"name": "name",      "label": "Name",      "field": "name",       "align": "left", "sortable": True},
    {"name": "serial",    "label": "Serial",     "field": "serial",     "align": "left", "sortable": True},
    {"name": "model_name","label": "Model",      "field": "model_name", "align": "left", "sortable": True},
    {"name": "category",  "label": "Category",   "field": "category",   "align": "left", "sortable": True},
    {"name": "status",    "label": "Status",     "field": "status",     "align": "left", "sortable": True},
    {"name": "asset_tag", "label": "Asset Tag",  "field": "asset_tag",  "align": "left", "sortable": True},
]


@ui.page("/assets")
async def assets_page() -> None:
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    # ── State ────────────────────────────────────────────────────
    state: dict = {
        "all_rows": [],
        "configured": True,
        "categories_str": "",
        "categories_list": [],
        "filter_category": "All",
    }

    with ui.column().classes("w-full q-pa-md").style("gap: 0;"):

        # ── Sticky toolbar ──────────────────────────────────────
        with ui.element("div").classes("ed-toolbar"):
            ui.button("Refresh", icon="refresh",
                      on_click=lambda: refresh()) \
                .props("flat dense color=secondary")
            ui.element("div").classes("ed-toolbar-spacer")
            ui.button("Import as DUT", icon="download",
                      on_click=lambda: import_selected()) \
                .props("flat dense color=primary")
            ui.element("div").classes("ed-toolbar-spacer")
            ui.button("Open DUT Registry", icon="devices",
                      on_click=lambda: ui.navigate.to("/duts")) \
                .props("flat dense")
            ui.element("div").classes("ed-toolbar-grow")
            with ui.element("div").classes("ed-status-now"):
                ui.element("span").classes("ed-status-dot")
                _total_label = ui.label("TOTAL · 0").classes("ed-mono")

        with ui.element("div").classes("ed-shell"):

            ui.label("DUT Assets").classes("text-h4 q-mb-md")

            # Info banner — shown when integration is not configured
            info_banner = ui.element("div").classes("ed-card hidden") \
                .style("border-color: var(--q-info); margin-bottom: 16px;")
            with info_banner:
                with ui.row().classes("items-center"):
                    ui.icon("info", color="info", size="sm").classes("q-mr-sm")
                    ui.label(
                        "The Snipe-IT integration is not configured or not enabled. "
                        "Please configure it under Settings > Integrations before "
                        "using this page."
                    )

            kpi_container = ui.element("div").classes("ed-strip")
            seg_container = ui.element("div").classes("ed-segmented")

            with ui.element("div").classes("ed-filter-row"):
                ui.label("Filter").classes("ed-filter-label")
                search_input = ui.input(
                    placeholder="Search by name, serial, model, status…",
                ).props('dense outlined clearable').style("min-width: 320px;")

            # ── Table ──────────────────────────────────────────
            with ui.element("div").classes("ed-card"):
                table = ui.table(
                    columns=_COLUMNS,
                    rows=[],
                    row_key="id",
                    selection="multiple",
                    pagination={"rowsPerPage": 25},
                ).classes("w-full").props("flat")

        # ------------------------------------------------------------------ #
        # Load saved categories from Snipe-IT integration config               #
        # ------------------------------------------------------------------ #
        async def _load_config() -> None:
            """Read categories from Snipe-IT integration settings."""
            try:
                config: dict = await api_get("/integrations/SNIPE_IT")
                raw_json = config.get("additional_config_json") or "{}"
                extra = json.loads(raw_json)
                saved_str = extra.get("categories", "")
                state["categories_str"] = saved_str
                if saved_str:
                    cats = [c.strip() for c in saved_str.split(",") if c.strip()]
                    state["categories_list"] = cats
                else:
                    state["categories_list"] = []
            except Exception:
                state["categories_list"] = []

        # ------------------------------------------------------------------ #
        # KPI / segments / filter                                              #
        # ------------------------------------------------------------------ #
        def _count_by_cat(rows: list[dict], cat: str) -> int:
            return sum(1 for r in rows if (r.get("category") or "") == cat)

        def _set_category(c: str) -> None:
            state["filter_category"] = c
            _render_kpis()
            _render_segments()
            _apply_filter()

        def _render_kpis() -> None:
            kpi_container.clear()
            with kpi_container:
                rows = state["all_rows"]
                _total_label.set_text(f"TOTAL · {len(rows)}")

                def _tile(label: str, count: int, sub: str, key: str | None = None) -> None:
                    cls = "ed-strip-cell ed-stat-tile"
                    if key and state["filter_category"] == key:
                        cls += " active"
                    el = ui.element("div").classes(cls)
                    if key is not None:
                        el.on("click", lambda _, k=key: _set_category(k))
                    with el:
                        ui.label(label).classes("ed-eyebrow")
                        ui.label(str(count)).classes("ed-strip-num")
                        if sub:
                            ui.label(sub).classes("ed-stat-tile-sub")

                from collections import Counter
                status_counts = Counter((r.get("status") or "Unknown") for r in rows)
                top_status = status_counts.most_common(3)
                _tile("Total Assets", len(rows),
                      f"{len(state['categories_list'])} categories tracked",
                      key="All")
                for stat, n in top_status:
                    _tile(stat, n, "by status", key=None)

        def _render_segments() -> None:
            seg_container.clear()
            with seg_container:
                rows = state["all_rows"]
                cats = state["categories_list"] or sorted({r.get("category") or "" for r in rows} - {""})

                def _seg(label: str, key: str, count: int) -> None:
                    cls = "ed-segmented-item" + (
                        " active" if state["filter_category"] == key else "")
                    btn = ui.element("button").classes(cls)
                    btn.on("click", lambda _, k=key: _set_category(k))
                    with btn:
                        ui.label(label)
                        ui.label(f"· {count}").classes("seg-count")

                _seg("All", "All", len(rows))
                for c in cats:
                    n = _count_by_cat(rows, c)
                    if n or c == state["filter_category"]:
                        _seg(c, c, n)

        def _apply_filter() -> None:
            """Filter table rows by the selected category and search query."""
            filt = state["filter_category"]
            if filt == "All":
                rows = list(state["all_rows"])
            else:
                rows = [r for r in state["all_rows"] if r.get("category") == filt]
            query = (search_input.value or "").strip().lower()
            if query:
                rows = [
                    r for r in rows
                    if query in (r.get("name") or "").lower()
                    or query in (r.get("serial") or "").lower()
                    or query in (r.get("model_name") or "").lower()
                    or query in (r.get("category") or "").lower()
                    or query in (r.get("status") or "").lower()
                    or query in (r.get("asset_tag") or "").lower()
                ]
            table.rows = rows
            table.update()

        search_input.on("update:model-value", lambda _: _apply_filter())

        # ------------------------------------------------------------------ #
        # Refresh helper                                                       #
        # ------------------------------------------------------------------ #
        async def refresh() -> None:
            try:
                rows: list = await api_get(
                    "/integrations/SNIPE_IT/assets",
                    params={"categories": state["categories_str"]},
                )
                state["all_rows"] = rows
                state["configured"] = True
                info_banner.classes(add="hidden")
                _render_kpis()
                _render_segments()
                _apply_filter()
            except Exception as exc:
                err_msg = str(exc)
                if "400" in err_msg:
                    state["configured"] = False
                    info_banner.classes(remove="hidden")
                    table.rows = []
                    table.update()
                else:
                    ui.notify(f"Failed to load assets: {exc}", type="negative")

        # ------------------------------------------------------------------ #
        # Import selected assets as DUT entries                                #
        # ------------------------------------------------------------------ #
        async def import_selected() -> None:
            selected = table.selected
            if not selected:
                ui.notify("No assets selected.", type="warning")
                return

            # Fetch existing DUT names to detect duplicates upfront
            try:
                existing_duts: list[dict] = await api_get("/dut-types")
                existing_names: set[str] = {d.get("name", "").lower() for d in existing_duts}
            except Exception:
                existing_names = set()

            success_count = 0
            skipped_names: list[str] = []
            failed_names: list[str] = []

            for asset in selected:
                name = asset.get("name", "Unknown")
                if name.lower() in existing_names:
                    skipped_names.append(name)
                    continue
                try:
                    await api_post(
                        "/dut-types",
                        json={
                            "name": name,
                            "category": asset.get("category", "Other"),
                            "complexity_multiplier": 1.0,
                        },
                    )
                    success_count += 1
                    existing_names.add(name.lower())
                except Exception as exc:
                    failed_names.append(f"{name}: {exc}")

            if success_count > 0:
                ui.notify(
                    f"Successfully imported {success_count} asset(s) as DUT entries.",
                    type="positive",
                )
            if skipped_names:
                ui.notify(
                    f"Skipped {len(skipped_names)} duplicate(s): {', '.join(skipped_names)}",
                    type="warning",
                )
            if failed_names:
                ui.notify(
                    f"Failed {len(failed_names)}: {'; '.join(failed_names)}",
                    type="negative",
                )

            # Clear selection after import
            table.selected.clear()
            table.update()

        # ------------------------------------------------------------------ #
        # Initial data load                                                    #
        # ------------------------------------------------------------------ #
        await _load_config()
        await refresh()
