"""Public Holidays page — manage public holidays for working week calculations.

API used:
    GET    /public-holidays         -> list[{id, date, name, country, is_recurring}]
    POST   /public-holidays         -> create
    PUT    /public-holidays/{id}    -> update
    DELETE /public-holidays/{id}    -> delete
"""

from nicegui import ui
from frontend_nicegui.app import API_URL, api_get, api_post, api_put, auth_headers, is_authenticated, show_error_page, sidebar

import httpx


@ui.page("/public-holidays")
async def public_holidays_page():
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    sidebar()

    with ui.column().classes("q-pa-lg w-full"):
        ui.label("Public Holidays").classes("text-h4 q-mb-md")

        # ---- load ----------------------------------------------------------------
        try:
            holidays: list[dict] = await api_get("/public-holidays")
        except Exception as exc:
            show_error_page(exc)
            return

        # ---- state ---------------------------------------------------------------
        table_rows = ui.state([])

        def _refresh_rows():
            table_rows.clear()
            for h in holidays:
                table_rows.append({
                    "id": h["id"],
                    "date": h["date"],
                    "name": h["name"],
                    "country": h.get("country", ""),
                    "is_recurring": h.get("is_recurring", False),
                })

        _refresh_rows()

        # ---- add dialog ----------------------------------------------------------
        async def add_holiday():
            with ui.dialog() as dlg, ui.card().classes("q-pa-md"):
                ui.label("Add Public Holiday").classes("text-h6 q-mb-sm")
                date_input = ui.input("Date (YYYY-MM-DD)", value="").classes("w-full")
                name_input = ui.input("Holiday Name", value="").classes("w-full")
                country_input = ui.input("Country / Region", value="").classes("w-full")
                recurring_switch = ui.switch("Recurring annually", value=False)

                async def _save():
                    if not date_input.value or not name_input.value:
                        ui.notify("Date and Name are required.", type="warning")
                        return
                    try:
                        result = await api_post("/public-holidays", json={
                            "date": date_input.value,
                            "name": name_input.value,
                            "country": country_input.value or "",
                            "is_recurring": recurring_switch.value,
                        })
                        holidays.append(result)
                        _refresh_rows()
                        table.update()
                        dlg.close()
                        ui.notify(f"Holiday '{name_input.value}' added.", type="positive")
                    except Exception as exc:
                        ui.notify(f"Error: {exc}", type="negative")

                with ui.row().classes("gap-2 q-mt-md"):
                    ui.button("Cancel", on_click=dlg.close).props("flat")
                    ui.button("Save", on_click=_save).props("color=primary")
            dlg.open()

        # ---- delete handler ------------------------------------------------------
        async def delete_holiday(holiday_id: int):
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.delete(
                        f"{API_URL}/public-holidays/{holiday_id}",
                        headers=auth_headers(),
                        timeout=10,
                    )
                    resp.raise_for_status()
                # Remove from local list
                for i, h in enumerate(holidays):
                    if h["id"] == holiday_id:
                        holidays.pop(i)
                        break
                _refresh_rows()
                table.update()
                ui.notify("Holiday deleted.", type="positive")
            except Exception as exc:
                ui.notify(f"Delete failed: {exc}", type="negative")

        # ---- toolbar -------------------------------------------------------------
        with ui.row().classes("q-mb-md gap-2 items-center"):
            ui.button("Add Holiday", icon="add", on_click=add_holiday).props("color=primary")

        # ---- table ---------------------------------------------------------------
        columns = [
            {"name": "date", "label": "Date", "field": "date", "align": "left", "sortable": True},
            {"name": "name", "label": "Name", "field": "name", "align": "left", "sortable": True},
            {"name": "country", "label": "Country", "field": "country", "align": "left"},
            {"name": "is_recurring", "label": "Recurring", "field": "is_recurring", "align": "center"},
            {"name": "actions", "label": "Actions", "field": "actions", "align": "center"},
        ]

        table = ui.table(
            columns=columns,
            rows=table_rows,
            row_key="id",
        ).classes("w-full").props("flat bordered dense")

        # Add slot for recurring badge and delete button
        table.add_slot("body-cell-is_recurring", """
            <q-td :props="props">
                <q-badge :color="props.row.is_recurring ? 'green' : 'grey'" :label="props.row.is_recurring ? 'Yes' : 'No'" />
            </q-td>
        """)

        table.add_slot("body-cell-actions", """
            <q-td :props="props">
                <q-btn flat dense icon="delete" color="negative"
                       @click="$parent.$emit('delete', props.row)" />
            </q-td>
        """)

        table.on("delete", lambda e: delete_holiday(e.args["id"]))
