"""Backup & Restore page — download/upload configuration data.

API used:
    GET  /admin/backup   -> download JSON backup file
    POST /admin/restore  -> upload and restore from JSON backup
"""

from nicegui import events, ui
from frontend_nicegui.app import (
    API_URL,
    _safe_storage,
    api_get,
    auth_headers,
    current_user,
    is_authenticated,
    sidebar,
)


@ui.page("/admin/backup")
async def backup_page():
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    user = current_user()
    if not user or user.get("role", "").upper() != "ADMIN":
        ui.navigate.to("/")
        return

    sidebar()

    with ui.column().classes("q-pa-lg w-full"):
        ui.label("Backup & Restore").classes("text-h4 q-mb-md")

        # ---- Backup section ------------------------------------------------
        with ui.card().classes("w-full q-pa-md q-mb-lg"):
            ui.label("Download Backup").classes("text-h6 q-mb-sm")
            ui.label(
                "Export all configuration data (features, task templates, DUT types, "
                "test profiles, team members, risk items, document types, public holidays) "
                "as a JSON file."
            ).classes("text-body2 text-grey q-mb-md")

            token = _safe_storage().get("token", "")

            def _download_backup_js() -> str:
                url = "/api/admin/backup"
                return (
                    f'fetch("{url}", {{'
                    f'  headers: {{"Authorization": "Bearer {token}"}}'
                    f'}})'
                    f'.then(r => {{ if (!r.ok) throw new Error("HTTP " + r.status); return r.blob(); }})'
                    f'.then(b => {{'
                    f'  const a = document.createElement("a");'
                    f'  a.href = URL.createObjectURL(b);'
                    f'  const d = new Date().toISOString().slice(0,19).replace(/[:-]/g,"");'
                    f'  a.download = "presto_backup_" + d + ".json";'
                    f'  a.click();'
                    f'}})'
                    f'.catch(err => {{ console.error("Download failed:", err); alert("Download failed: " + err.message); }});'
                )

            ui.button(
                "Download Backup",
                icon="download",
                on_click=lambda: ui.run_javascript(_download_backup_js()),
            ).props("color=primary")

        # ---- Restore section -----------------------------------------------
        with ui.card().classes("w-full q-pa-md"):
            ui.label("Restore from Backup").classes("text-h6 q-mb-sm")
            ui.label(
                "Upload a previously downloaded backup JSON file. "
                "This will replace all current configuration data with the backup contents."
            ).classes("text-body2 text-grey q-mb-md")
            ui.label(
                "Warning: This operation cannot be undone. Consider downloading a backup first."
            ).classes("text-body2 text-negative q-mb-md")

            result_container = ui.column().classes("w-full")

            async def _handle_restore(e: events.UploadEventArguments):
                upload_file = getattr(e, "file", None) or e
                fname = upload_file.name if hasattr(upload_file, "name") else "backup.json"

                if not fname.endswith(".json"):
                    ui.notify("Please upload a JSON file.", type="warning")
                    return

                # Read file content
                import asyncio
                if hasattr(upload_file, "read") and asyncio.iscoroutinefunction(upload_file.read):
                    file_content = await upload_file.read()
                elif hasattr(upload_file, "content"):
                    upload_file.content.seek(0)
                    file_content = upload_file.content.read()
                else:
                    ui.notify("Could not read upload file.", type="warning")
                    return

                # Confirm dialog
                with ui.dialog() as confirm_dlg, ui.card().classes("w-96"):
                    ui.label("Confirm Restore").classes("text-h6 q-mb-sm")
                    ui.label(
                        "This will replace all current configuration data. "
                        "Are you sure you want to continue?"
                    ).classes("text-body2 q-mb-md")

                    async def _do_restore():
                        confirm_dlg.close()
                        try:
                            import httpx
                            hdrs = auth_headers()
                            async with httpx.AsyncClient(timeout=60.0) as client:
                                resp = await client.post(
                                    f"{API_URL}/admin/restore",
                                    headers=hdrs,
                                    files={"file": (fname, file_content, "application/json")},
                                )
                                resp.raise_for_status()
                                data = resp.json()

                            result_container.clear()
                            with result_container:
                                ui.label("Restore completed successfully!").classes(
                                    "text-positive text-h6 q-mb-sm"
                                )
                                tables = data.get("tables_restored", [])
                                rows = data.get("rows_restored", {})
                                for tbl in tables:
                                    ui.label(f"  {tbl}: {rows.get(tbl, 0)} rows").classes(
                                        "text-body2"
                                    )

                            ui.notify("Restore completed successfully!", type="positive")
                        except Exception as exc:
                            ui.notify(f"Restore failed: {exc}", type="negative")

                    with ui.row().classes("q-mt-md justify-end w-full gap-2"):
                        ui.button("Cancel", on_click=confirm_dlg.close).props("flat")
                        ui.button("Restore", on_click=_do_restore).props("color=negative")

                confirm_dlg.open()

            ui.upload(
                label="Upload Backup File",
                on_upload=_handle_restore,
                auto_upload=True,
            ).props('accept=".json" color=secondary').classes("q-mb-md")
