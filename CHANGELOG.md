# Changelog

All notable changes to the Test Effort Estimation Tool are documented here.

---

## [3.0.0] - 2026-03-02

### Added
- **Estimation Versioning** — estimations track version number and preserve wizard inputs per revision via `PUT /api/estimations/{id}/revise`
- **Configurable DUT Categories** — DUT type categories stored in `configuration` table (`dut_categories` key), editable from Settings; replaces hardcoded lists in all frontends
- **HTTPS/TLS Support** — backend (uvicorn), NiceGUI, and Streamlit all support SSL via `SSL_CERTFILE` and `SSL_KEYFILE` environment variables; pre-generated PEM files can be mounted into Docker via `certs/` volume
- **`GET /api/dut-categories`** endpoint — returns configured DUT category list for frontend dropdowns
- **`get_dut_categories` IPC command** — desktop frontend fetches categories from backend config
- **Outline Auto-Export** — automatic wiki export when estimation status changes to configured states (`outline_auto_export_states` config key)
- **RBAC Matrix UI** — LDAP group mapping and OIDC role mapping displayed as interactive matrix tables in Settings pages (NiceGUI and Streamlit)
- **NiceGUI sidebar icons** — Material icons on all navigation items with explicit white color for dark theme visibility
- **NiceGUI sidebar categories** — sidebar reorganized into Overview, Estimation, Data Management, and Administration sections matching Streamlit layout
- **Login Enter key** — NiceGUI login form submits on Enter key press (Tab from username to password, Enter to submit)
- **`_ensure_config_keys()`** — migration helper guarantees config keys exist even when database is already at latest schema version
- **`backend/run_server.py`** — standalone uvicorn runner with SSL environment variable support
- **`.streamlit/config.toml`** — Streamlit server configuration with SSL settings

### Changed
- Desktop DUT Registry: `TextBox` for category replaced with `ComboBox` populated from backend config
- Streamlit DUT Registry: hardcoded category list replaced with database-driven fetch
- NiceGUI DUT Registry: hardcoded category list replaced with API-driven fetch with fallback
- NiceGUI Settings: `dut_categories` classified under "Data Management" section
- Streamlit Settings: `dut_categories` added to default config with dedicated input field
- Dockerfile entrypoint: conditional SSL arguments for both uvicorn and Streamlit processes
- `docker-compose.yml`: added `SSL_CERTFILE`, `SSL_KEYFILE` environment variables and `certs/` volume mount
- Schema version bumped to v3 (`SCHEMA_VERSION=3`)

### Fixed
- DUT categories config key not created for databases already at schema v3 — solved with `_ensure_config_keys()` post-migration step

---

## [2.0.0] - 2026-02

### Added
- **Authentication & RBAC** — JWT auth (PyJWT + bcrypt), 4 roles: VIEWER, ESTIMATOR, APPROVER, ADMIN
- **LDAP/OIDC** — external auth via ldap3 and authlib providers
- **MySQL Support** — engine factory supports SQLite + MySQL via `DB_URL` env var
- **Notifications** — SMTP notification service with HTML email templates
- **User Assignment** — assign users to estimations and requests
- **Light/Dark Theme** — persistent toggle in both Streamlit and NiceGUI frontends
- **Advanced Reports** — comparison, trend, and executive summary report types
- **Bulk Import** — CSV/Excel import with validation
- **Outline Wiki** — 4th integration: publish estimations to Outline wiki
- **NiceGUI Frontend** — full SPA alternative to Streamlit with WebSocket-based updates
- **RBAC Management** — UI page for configuring role permissions
- **Docker** — Dockerfile + docker-compose.yml for containerized deployment
- **Admin Script** — `backend/scripts/create_admin.py` for account management
- 263 tests (up from 152)

---

## [1.0.0] - 2026-01

### Added
- Core estimation engine with 7-step wizard workflow
- Feature catalog with task templates and complexity weights
- DUT registry and test profile management
- Historical project calibration
- Feasibility assessment with auto-detected risk flags
- Report generation: Excel (openpyxl), Word (python-docx), PDF (ReportLab)
- FastAPI REST API with 50+ endpoints
- JSON IPC handler for C# desktop frontend
- Streamlit web frontend with 11 pages
- C# WinForms desktop frontend (.NET 8)
- Redmine, Jira/Xray, and Email integration adapters
- SQLite database with seed data
- 152 tests across calculation, feasibility, calibration, models, reports, and API
