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

    with ui.column().classes("q-pa-lg w-full"):
        with ui.row().classes("items-center q-mb-md gap-4"):
            ui.label("DUT Assets").classes("text-h4")
            ui.button(
                "Open DUT Registry",
                icon="devices",
                on_click=lambda: ui.navigate.to("/duts"),
            ).props("flat color=secondary")

        # ------------------------------------------------------------------ #
        # State                                                                #
        # ------------------------------------------------------------------ #
        state: dict = {
            "all_rows": [],
            "configured": True,
            "categories_str": "",
            "categories_list": [],
            "filter_category": "All",
        }

        # ------------------------------------------------------------------ #
        # Info banner (shown when integration is not configured)               #
        # ------------------------------------------------------------------ #
        info_banner = ui.card().classes("w-full q-mb-md hidden bg-blue-1")
        with info_banner:
            with ui.row().classes("items-center q-pa-sm"):
                ui.icon("info", color="info", size="sm").classes("q-mr-sm")
                ui.label(
                    "The Snipe-IT integration is not configured or not enabled. "
                    "Please configure it under Settings > Integrations before using this page."
                )

        # ------------------------------------------------------------------ #
        # Search input                                                         #
        # ------------------------------------------------------------------ #
        search_input = ui.input(
            placeholder="Search by name, serial, model, category, status...",
        ).classes("w-full q-mb-sm").props('outlined dense clearable')
        with search_input:
            ui.icon("search").classes("text-grey").props('slot="prepend"')

        # ------------------------------------------------------------------ #
        # Table with checkbox selection                                        #
        # ------------------------------------------------------------------ #
        table = ui.table(
            columns=_COLUMNS,
            rows=[],
            row_key="id",
            selection="multiple",
            pagination={"rowsPerPage": 15},
        ).classes("w-full shadow-1")

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
        # Apply local category filter to table                                 #
        # ------------------------------------------------------------------ #
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
        # Toolbar: Category filter + Refresh + Import                          #
        # ------------------------------------------------------------------ #
        with ui.row().classes("items-center q-gutter-sm q-mb-md"):
            def _on_cat_filter_change(e) -> None:
                state["filter_category"] = e.value if e.value else "All"
                _apply_filter()

            cat_filter = ui.select(
                options=["All"],
                value="All",
                label="Filter by Category",
                on_change=_on_cat_filter_change,
            ).classes("w-48")

            ui.button(
                "Refresh",
                icon="refresh",
                on_click=refresh,
            ).props("color=secondary")

            ui.space()

            ui.button(
                "Import as DUT",
                icon="download",
                on_click=import_selected,
            ).props("color=primary")

        # ------------------------------------------------------------------ #
        # Initial data load                                                    #
        # ------------------------------------------------------------------ #
        await _load_config()

        # Populate the category filter dropdown with configured categories
        if state["categories_list"]:
            cat_filter.options = ["All"] + state["categories_list"]
            cat_filter.update()

        await refresh()
