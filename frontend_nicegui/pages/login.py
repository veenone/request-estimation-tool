"""Login page for the NiceGUI frontend."""

import httpx
from nicegui import app, ui

from frontend_nicegui.app import API_URL


@ui.page("/login")
def login_page():
    async def try_login():
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(f"{API_URL}/auth/login", json={
                    "username": username.value,
                    "password": password.value,
                })
                r.raise_for_status()
                data = r.json()
                app.storage.user["token"] = data["access_token"]
                app.storage.user["refresh_token"] = data["refresh_token"]
                app.storage.user["user"] = data["user"]
                ui.navigate.to("/")
        except httpx.HTTPStatusError:
            ui.notify("Invalid credentials", type="negative")
        except Exception as e:
            ui.notify(f"Login error: {e}", type="negative")

    with ui.card().classes("absolute-center w-96"):
        ui.label("Test Effort Estimation Tool").classes("text-h5 text-center w-full")
        ui.label("Sign in to continue").classes("text-subtitle2 text-center w-full text-grey")
        username = ui.input("Username").classes("w-full")
        password = ui.input("Password", password=True, password_toggle_button=True).classes("w-full")
        ui.button("Login", on_click=try_login).classes("w-full mt-4")
