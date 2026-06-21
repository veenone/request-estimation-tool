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
    run_async,
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

    with ui.column().classes("w-full q-pa-md").style("gap: 0;"):

        # ── Sticky toolbar ──────────────────────────────────────
        # (Download action lives as the primary action in the card body below
        #  to avoid a duplicate button.)
        with ui.element("div").classes("ed-toolbar"):
            ui.element("div").classes("ed-toolbar-grow")
            with ui.element("div").classes("ed-status-now"):
                ui.element("span").classes("ed-status-dot")
                ui.label("ADMIN ONLY").classes("ed-mono")

        with ui.element("div").classes("ed-shell"):

            ui.label("Backup & Restore").classes("text-h4 q-mb-md")
            ui.label(
                "Export all configuration data as a JSON file, or restore "
                "from a previous backup. Affects features, task templates, "
                "DUTs, profiles, team members, risks, document types, "
                "and public holidays."
            ).classes("ed-eyebrow").style("margin-bottom: 22px;")

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

            # ── Backup section ─────────────────────────────────
            with ui.element("div").classes("ed-card"):
                with ui.element("div").classes("ed-card-head"):
                    ui.label("Download Backup").classes("ed-cap")
                    ui.label("read-only operation").classes("ed-card-head-meta")
                ui.label(
                    "Export all configuration data (features, task templates, DUT types, "
                    "test profiles, team members, risk items, document types, public holidays) "
                    "as a JSON file you can store off-platform or hand to another instance."
                ).style("font-size: 13px; opacity: 0.78; margin-bottom: 18px;")
                download_btn = ui.button("Download Backup", icon="download") \
                    .props("color=primary")
                download_btn.on_click(run_async(
                    download_btn,
                    lambda: ui.run_javascript(_download_backup_js()),
                    error_prefix="Download failed",
                ))

            # ── Restore section ────────────────────────────────
            with ui.element("div").classes("ed-card") \
                    .style("border-color: var(--q-warning);"):
                with ui.element("div").classes("ed-card-head"):
                    ui.label("Restore from Backup").classes("ed-cap") \
                        .style("color: var(--q-warning);")
                    ui.label("destructive · cannot be undone").classes("ed-card-head-meta") \
                        .style("color: var(--q-warning);")
                ui.label(
                    "Upload a previously downloaded backup JSON file. "
                    "This will replace all current configuration data with "
                    "the backup contents."
                ).style("font-size: 13px; opacity: 0.78; margin-bottom: 8px;")
                ui.label(
                    "Consider downloading a backup first as a safety net."
                ).style("font-size: 12px; color: var(--q-warning); "
                        "font-weight: 500; margin-bottom: 18px;")

                result_container = ui.column().classes("w-full")

                ui.label(
                    "Select a file, then confirm the restore in the dialog that "
                    "appears. Nothing is sent to the server until you confirm."
                ).style("font-size: 12px; opacity: 0.7; margin-bottom: 6px;")
                # No auto_upload: the file is only read locally on selection; the
                # actual overwrite happens after explicit confirmation below.
                ui.upload(
                    label="Select Backup File",
                    on_upload=lambda e: _handle_restore(e),
                    auto_upload=False,
                ).props('accept=".json" color=secondary').classes("q-mb-md w-full")

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

                # Confirm dialog — the restore (upload + overwrite) only runs
                # when the user explicitly clicks "Restore" below.
                with ui.dialog() as confirm_dlg, ui.card().classes("w-96"):
                    ui.label("Confirm Restore").classes("text-h6 q-mb-sm")
                    ui.label(
                        f"Restore from '{fname}'? This OVERWRITES all current "
                        "configuration data (features, task templates, DUTs, "
                        "profiles, team members, risks, document types, public "
                        "holidays) with the backup contents. This cannot be undone."
                    ).classes("text-body2 q-mb-md")

                    async def _run_restore():
                        import httpx
                        hdrs = auth_headers()
                        async with httpx.AsyncClient(timeout=60.0) as client:
                            resp = await client.post(
                                f"{API_URL}/admin/restore",
                                headers=hdrs,
                                files={"file": (fname, file_content, "application/json")},
                            )
                            resp.raise_for_status()
                            return resp.json()

                    def _render_result(data: dict) -> None:
                        confirm_dlg.close()
                        tables = data.get("tables_restored", []) or []
                        rows = data.get("rows_restored", {}) or {}
                        parts = [f"{tbl} ({rows.get(tbl, 0)})" for tbl in tables]
                        result_container.clear()
                        with result_container:
                            ui.label("Restore completed successfully!").classes(
                                "text-positive text-h6 q-mb-sm"
                            )
                            if parts:
                                ui.label("Restored: " + ", ".join(parts)).classes(
                                    "text-body2"
                                )
                            else:
                                ui.label("No tables reported.").classes("text-body2")

                    with ui.row().classes("q-mt-md justify-end w-full gap-2"):
                        ui.button("Cancel", on_click=confirm_dlg.close).props("flat")
                        restore_btn = ui.button("Restore").props("color=negative")
                        restore_btn.on_click(run_async(
                            restore_btn,
                            _run_restore,
                            success="Restore completed successfully!",
                            on_success=_render_result,
                            error_prefix="Restore failed",
                        ))

                confirm_dlg.open()
