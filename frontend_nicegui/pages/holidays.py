"""Public Holidays page — calendar view with CRUD and ICS import.

API used:
    GET    /public-holidays         -> list[{id, date, name, country, is_recurring}]
    POST   /public-holidays         -> create
    PUT    /public-holidays/{id}    -> update
    DELETE /public-holidays/{id}    -> delete
    POST   /public-holidays/import-ics -> import from ICS file
"""

import asyncio
import json
from datetime import date, timedelta

import httpx
from nicegui import events, ui
from frontend_nicegui.app import (
    API_URL,
    _safe_storage,
    api_delete,
    api_get,
    api_post,
    api_put,
    auth_headers,
    is_authenticated,
    sidebar,
)


def _month_name(m: int) -> str:
    return [
        "", "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ][m]


def _weekday_name(d: int) -> str:
    return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][d]


@ui.page("/public-holidays")
async def public_holidays_page():
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    with ui.column().classes("w-full q-pa-md").style("gap: 0;"):

        # ── Sticky toolbar (Add lives in the calendar header below;
        # we keep the toolbar minimal — total count + Today shortcut)
        with ui.element("div").classes("ed-toolbar"):
            ui.button("Add Holiday", icon="add",
                      on_click=lambda: _show_add_dialog()) \
                .props("flat dense color=primary")
            ui.element("div").classes("ed-toolbar-grow")
            with ui.element("div").classes("ed-status-now"):
                ui.element("span").classes("ed-status-dot")
                _total_label = ui.label("TOTAL · 0").classes("ed-mono")

        ui.element("div").classes("ed-shell").style("display: contents;")
        ui.label("Public Holidays").classes("text-h4 q-mb-md")

        # ── KPI strip (populated after _load_holidays) ──────────
        kpi_container = ui.element("div").classes("ed-strip").style("margin-bottom: 18px;")

        # ---- load config for calendar colors ------------------------------------
        is_dark = _safe_storage().get("dark_mode", True)
        _today_bg = "#37474f" if is_dark else "#e0e0e0"
        _weekend_bg = "#263238" if is_dark else "#f0f0f0"
        _holiday_cell_bg = "#3e2723" if is_dark else "#fff3e0"
        _holiday_badge_bg = "#e65100" if is_dark else "#ff9800"
        try:
            _cfg_list = await api_get("/configuration")
            for _ci in _cfg_list:
                k, v = _ci.get("key", ""), _ci.get("value", "")
                if not v:
                    continue
                if k == "calendar_today_bg_dark" and is_dark:
                    _today_bg = v
                elif k == "calendar_today_bg_light" and not is_dark:
                    _today_bg = v
                elif k == "calendar_weekend_bg_dark" and is_dark:
                    _weekend_bg = v
                elif k == "calendar_weekend_bg_light" and not is_dark:
                    _weekend_bg = v
        except Exception:
            pass

        # ---- state ---------------------------------------------------------------
        today = date.today()
        state: dict = {
            "holidays": [],
            "year": today.year,
            "month": today.month,
        }

        async def _load_holidays():
            try:
                state["holidays"] = await api_get("/public-holidays")
            except Exception as exc:
                ui.notify(f"Failed to load holidays: {exc}", type="negative")
                state["holidays"] = []
            _render_kpis()

        def _render_kpis() -> None:
            """Refresh the KPI strip and total-count pill from current holiday data."""
            try:
                kpi_container.clear()
            except Exception:
                return
            holidays = state["holidays"]
            _total_label.set_text(f"TOTAL · {len(holidays)}")
            try:
                _list_count_label.set_text(
                    f"{len(holidays)} entr{'ies' if len(holidays) != 1 else 'y'}"
                )
            except Exception:
                pass
            this_year = date.today().year
            this_year_n = sum(
                1 for h in holidays
                if (h.get("date") or "").startswith(str(this_year))
            )
            recurring_n = sum(1 for h in holidays if h.get("is_recurring"))
            countries = {h.get("country") or "" for h in holidays} - {""}

            with kpi_container:
                with ui.element("div").classes("ed-strip-cell"):
                    ui.label("Total Holidays").classes("ed-eyebrow")
                    ui.label(str(len(holidays))).classes("ed-strip-num")
                    ui.label(
                        f"{len(countries)} countr{'ies' if len(countries) != 1 else 'y'}"
                    ).classes("ed-stat-tile-sub")
                with ui.element("div").classes("ed-strip-cell"):
                    ui.label(f"This Year ({this_year})").classes("ed-eyebrow")
                    ui.label(str(this_year_n)).classes("ed-strip-num")
                    ui.label("specific dates").classes("ed-stat-tile-sub")
                with ui.element("div").classes("ed-strip-cell"):
                    ui.label("Recurring").classes("ed-eyebrow")
                    ui.label(str(recurring_n)).classes("ed-strip-num")
                    ui.label("annual repeat").classes("ed-stat-tile-sub")
                if countries:
                    with ui.element("div").classes("ed-strip-cell"):
                        ui.label("Countries").classes("ed-eyebrow")
                        ui.label(str(len(countries))).classes("ed-strip-num")
                        top_country = max(
                            countries,
                            key=lambda c: sum(
                                1 for h in holidays if h.get("country") == c
                            ),
                        )
                        ui.label(f"top: {top_country}").classes("ed-stat-tile-sub")

        await _load_holidays()

        # ---- helpers -------------------------------------------------------------
        def _holidays_for_date(y: int, m: int, d: int) -> list[dict]:
            ds = f"{y:04d}-{m:02d}-{d:02d}"
            result = []
            for h in state["holidays"]:
                if h["date"] == ds:
                    result.append(h)
                elif h.get("is_recurring"):
                    # Recurring: match month and day
                    hd = h["date"]  # "YYYY-MM-DD"
                    if hd[5:] == f"{m:02d}-{d:02d}":
                        result.append(h)
            return result

        # ---- calendar renderer ---------------------------------------------------
        calendar_container = ui.element("div").classes("ed-card")

        def _render_calendar():
            calendar_container.clear()
            y, m = state["year"], state["month"]

            with calendar_container:
                # Navigation header — month nav on the left
                with ui.row().classes("items-center q-mb-sm gap-2 w-full"):
                    ui.button(icon="chevron_left", on_click=_prev_month).props("flat dense round")
                    ui.label(f"{_month_name(m)} {y}").classes("text-h6").style("min-width: 200px; text-align: center;")
                    ui.button(icon="chevron_right", on_click=_next_month).props("flat dense round")
                    ui.button("Today", on_click=_goto_today).props("flat dense")

                # Weekday headers
                with ui.row().classes("w-full gap-0"):
                    with ui.element("div").classes("text-center text-caption text-bold").style(
                        "width: calc(100% / 8); padding: 4px 0;"
                    ):
                        ui.label("Wk")
                    for wd in range(7):
                        with ui.element("div").classes("text-center text-caption text-bold").style(
                            "width: calc(100% / 8); padding: 4px 0;"
                        ):
                            ui.label(_weekday_name(wd))

                # Calculate first day offset and days in month
                first_day = date(y, m, 1)
                start_weekday = first_day.weekday()  # 0=Mon
                if m == 12:
                    next_month = date(y + 1, 1, 1)
                else:
                    next_month = date(y, m + 1, 1)
                days_in_month = (next_month - first_day).days

                # Render calendar grid
                with ui.element("div").classes("w-full").style(
                    "display: flex; flex-wrap: wrap; gap: 0;"
                ):
                    # Week number for first (partial) row
                    first_wk = date(y, m, 1).isocalendar()[1]
                    with ui.element("div").classes("text-center text-caption text-grey").style(
                        "width: calc(100% / 8); min-height: 80px; border: 1px solid #e0e0e0; "
                        "padding: 4px; display: flex; align-items: flex-start; justify-content: center;"
                    ):
                        ui.label(str(first_wk)).classes("text-bold")

                    # Empty cells for offset
                    for _ in range(start_weekday):
                        ui.element("div").style("width: calc(100% / 8); min-height: 80px;")

                    for day in range(1, days_in_month + 1):
                        day_date = date(y, m, day)
                        # At the start of a new week (Monday), add week number cell
                        if day > 1 and day_date.weekday() == 0:
                            wk = day_date.isocalendar()[1]
                            with ui.element("div").classes("text-center text-caption text-grey").style(
                                "width: calc(100% / 8); min-height: 80px; border: 1px solid #e0e0e0; "
                                "padding: 4px; display: flex; align-items: flex-start; justify-content: center;"
                            ):
                                ui.label(str(wk)).classes("text-bold")

                        is_weekend = day_date.weekday() >= 5
                        is_today = day_date == today
                        day_holidays = _holidays_for_date(y, m, day)

                        bg = f"background: {_weekend_bg};" if is_weekend else ""
                        if is_today:
                            bg = f"background: {_today_bg};"
                        if day_holidays:
                            bg = f"background: {_holiday_cell_bg};"

                        with ui.element("div").style(
                            f"width: calc(100% / 8); min-height: 80px; border: 1px solid #e0e0e0; "
                            f"padding: 4px; cursor: pointer; {bg}"
                        ).on("click", lambda _, d=day: _on_day_click(d)):
                            day_label_color = "color: primary" if is_today else ""
                            ui.label(str(day)).classes(f"text-body2 text-bold {day_label_color}")

                            for hol in day_holidays:
                                with ui.element("div").classes("q-mt-xs").style(
                                    f"background: {_holiday_badge_bg}; color: white; border-radius: 4px; "
                                    "padding: 1px 4px; font-size: 11px; cursor: pointer;"
                                ).on("click.stop", lambda _, h=hol: _show_edit_dialog(h)):
                                    ui.label(hol["name"]).style("white-space: nowrap; overflow: hidden; text-overflow: ellipsis;")

                # Bottom-left: Import ICS uploader
                with ui.row().classes("w-full q-mt-md justify-start"):
                    ui.upload(
                        label="Import ICS",
                        on_upload=_handle_ics_upload,
                        auto_upload=True,
                    ).props('accept=".ics" flat dense color=secondary').classes("max-w-sm")

        async def _prev_month():
            if state["month"] == 1:
                state["month"] = 12
                state["year"] -= 1
            else:
                state["month"] -= 1
            _render_calendar()

        async def _next_month():
            if state["month"] == 12:
                state["month"] = 1
                state["year"] += 1
            else:
                state["month"] += 1
            _render_calendar()

        async def _goto_today():
            state["year"] = today.year
            state["month"] = today.month
            _render_calendar()

        def _on_day_click(day: int):
            """Click on a day cell → open add dialog pre-filled with that date."""
            dt = f"{state['year']:04d}-{state['month']:02d}-{day:02d}"
            _show_add_dialog(dt)

        # ---- Add dialog ----------------------------------------------------------
        def _show_add_dialog(prefill_date: str = ""):
            with ui.dialog() as dlg, ui.card().classes("w-96"):
                ui.label("Add Public Holiday").classes("text-h6 q-mb-sm")

                date_input = ui.input("Date (YYYY-MM-DD)", value=prefill_date).classes("w-full")
                name_input = ui.input("Holiday Name").classes("w-full")
                country_input = ui.input("Country / Region", value="").classes("w-full")
                recurring_switch = ui.switch("Recurring annually", value=False)

                def _normalize_date(raw):
                    if hasattr(raw, "isoformat"):
                        return raw.isoformat()
                    if isinstance(raw, str) and raw.strip():
                        return raw.strip()
                    return None

                async def _save():
                    if not date_input.value or not name_input.value:
                        ui.notify("Date and Name are required.", type="warning")
                        return
                    date_val = _normalize_date(date_input.value)
                    if not date_val:
                        ui.notify("Invalid date value.", type="warning")
                        return
                    try:
                        result = await api_post("/public-holidays", json={
                            "date": date_val,
                            "name": name_input.value.strip(),
                            "country": country_input.value or "",
                            "is_recurring": recurring_switch.value,
                        })
                        state["holidays"].append(result)
                        _render_calendar()
                        _render_table()
                        dlg.close()
                        ui.notify(f"Holiday '{name_input.value}' added.", type="positive")
                    except Exception as exc:
                        ui.notify(f"Error: {exc}", type="negative")

                with ui.row().classes("q-mt-md justify-end w-full"):
                    ui.button("Cancel", on_click=dlg.close).props("flat")
                    ui.button("Save", on_click=_save).props("color=primary")
            dlg.open()

        # ---- Edit dialog ---------------------------------------------------------
        def _show_edit_dialog(holiday: dict):
            with ui.dialog() as dlg, ui.card().classes("w-96"):
                ui.label("Edit Public Holiday").classes("text-h6 q-mb-sm")

                date_input = ui.input("Date (YYYY-MM-DD)", value=holiday.get("date", "")).classes("w-full")
                name_input = ui.input("Holiday Name", value=holiday.get("name", "")).classes("w-full")
                country_input = ui.input("Country / Region", value=holiday.get("country", "")).classes("w-full")
                recurring_switch = ui.switch("Recurring annually", value=holiday.get("is_recurring", False))

                def _normalize_date(raw):
                    if hasattr(raw, "isoformat"):
                        return raw.isoformat()
                    if isinstance(raw, str) and raw.strip():
                        return raw.strip()
                    return None

                async def _save_edit():
                    if not date_input.value or not name_input.value:
                        ui.notify("Date and Name are required.", type="warning")
                        return
                    date_val = _normalize_date(date_input.value)
                    if not date_val:
                        ui.notify("Invalid date value.", type="warning")
                        return
                    try:
                        updated = await api_put(f"/public-holidays/{holiday['id']}", json={
                            "date": date_val,
                            "name": name_input.value.strip(),
                            "country": country_input.value or "",
                            "is_recurring": recurring_switch.value,
                        })
                        # Update local state
                        for i, h in enumerate(state["holidays"]):
                            if h["id"] == holiday["id"]:
                                state["holidays"][i] = updated
                                break
                        _render_calendar()
                        _render_table()
                        dlg.close()
                        ui.notify("Holiday updated.", type="positive")
                    except Exception as exc:
                        ui.notify(f"Error: {exc}", type="negative")

                async def _delete_from_edit():
                    try:
                        await api_delete(f"/public-holidays/{holiday['id']}")
                        state["holidays"] = [h for h in state["holidays"] if h["id"] != holiday["id"]]
                        _render_calendar()
                        _render_table()
                        dlg.close()
                        ui.notify("Holiday deleted.", type="positive")
                    except Exception as exc:
                        ui.notify(f"Delete failed: {exc}", type="negative")

                with ui.row().classes("q-mt-md justify-between w-full"):
                    ui.button("Delete", icon="delete", on_click=_delete_from_edit).props("flat color=negative")
                    with ui.row().classes("gap-2"):
                        ui.button("Cancel", on_click=dlg.close).props("flat")
                        ui.button("Save", on_click=_save_edit).props("color=primary")
            dlg.open()

        # ---- ICS import ----------------------------------------------------------
        async def _handle_ics_upload(e: events.UploadEventArguments):
            try:
                # NiceGUI 3.8+: e.content may not exist; use e.file or fallback
                upload_file = getattr(e, "file", None) or e
                fname = upload_file.name if hasattr(upload_file, "name") else getattr(e, "name", "import.ics")
                if hasattr(upload_file, "read") and asyncio.iscoroutinefunction(upload_file.read):
                    file_content = await upload_file.read()
                elif hasattr(upload_file, "content"):
                    upload_file.content.seek(0)
                    file_content = upload_file.content.read()
                else:
                    ui.notify("Could not read upload file.", type="warning")
                    return
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"{API_URL}/public-holidays/import-ics",
                        headers=auth_headers(),
                        files={"file": (fname, file_content, "text/calendar")},
                        timeout=30,
                    )
                    resp.raise_for_status()
                    result = resp.json()

                imported = result.get("imported", 0)
                skipped = result.get("skipped", 0)
                errors = result.get("errors", [])

                if imported > 0:
                    ui.notify(f"Imported {imported} holiday(s).", type="positive")
                if skipped > 0:
                    ui.notify(f"Skipped {skipped} (duplicates or invalid).", type="info")
                if errors:
                    ui.notify(f"Errors: {'; '.join(errors[:5])}", type="warning")

                # Reload all holidays
                await _load_holidays()
                _render_calendar()
                _render_table()
            except Exception as exc:
                ui.notify(f"Import failed: {exc}", type="negative")

        # ---- Calendar view -------------------------------------------------------
        _render_calendar()

        # ---- Table view (below calendar, in its own ed-card) ---------------------
        with ui.element("div").classes("ed-card"):
            with ui.element("div").classes("ed-card-head"):
                ui.label("All Holidays").classes("ed-cap")
                _list_count_label = ui.label("").classes("ed-card-head-meta")
            table_container = ui.element("div").classes("w-full")

        _TABLE_COLUMNS = [
            {"name": "date", "label": "Date", "field": "date", "align": "left", "sortable": True},
            {"name": "name", "label": "Name", "field": "name", "align": "left", "sortable": True},
            {"name": "country", "label": "Country", "field": "country", "align": "left"},
            {"name": "is_recurring", "label": "Recurring", "field": "is_recurring", "align": "center"},
            {"name": "actions", "label": "Actions", "field": "actions", "align": "center"},
        ]

        def _render_table():
            table_container.clear()
            sorted_holidays = sorted(state["holidays"], key=lambda h: h.get("date", ""))
            with table_container:
                tbl = ui.table(
                    columns=_TABLE_COLUMNS,
                    rows=sorted_holidays,
                    row_key="id",
                    pagination={"rowsPerPage": 15},
                ).classes("w-full").props("flat bordered dense")

                tbl.add_slot("body-cell-is_recurring", """
                    <q-td :props="props">
                        <q-badge :color="props.row.is_recurring ? 'green' : 'grey'"
                                 :label="props.row.is_recurring ? 'Yes' : 'No'" />
                    </q-td>
                """)

                tbl.add_slot("body-cell-actions", """
                    <q-td :props="props">
                        <q-btn flat dense icon="edit" color="primary" size="sm"
                               @click="() => $parent.$emit('edit-row', props.row)" class="q-mr-xs" />
                        <q-btn flat dense icon="delete" color="negative" size="sm"
                               @click="() => $parent.$emit('delete-row', props.row)" />
                    </q-td>
                """)

                tbl.on("edit-row", lambda e: _show_edit_dialog(e.args))

                async def _delete_from_table(e):
                    row = e.args
                    try:
                        await api_delete(f"/public-holidays/{row['id']}")
                        state["holidays"] = [h for h in state["holidays"] if h["id"] != row["id"]]
                        _render_calendar()
                        _render_table()
                        ui.notify("Holiday deleted.", type="positive")
                    except Exception as exc:
                        ui.notify(f"Delete failed: {exc}", type="negative")

                tbl.on("delete-row", _delete_from_table)

        _render_table()
