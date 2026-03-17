# Changelog

All notable changes to the Test Effort Estimation Tool are documented here.

---

## [3.3.0] - 2026-03-17

### Added
- **Dashboard ECharts** — interactive donut and bar charts for estimation status, request status, feature categories, task types, risk categories, and risk likelihood with dark mode legend colors
- **DUT registry bulk operations** — multi-select rows with bulk edit (category, multiplier) and bulk delete with confirmation dialog
- **User management search** — real-time search/filter across username, display name, email, role, and auth provider
- **Bulk role assignment** — select multiple users and assign a new role in bulk from user management page
- **Descriptive error pages** — HTTP 400, 401, 403, 422 errors display user-friendly banners with detailed Pydantic validation error parsing
- **Dashboard stats API extensions** — `GET /api/dashboard/stats` returns `features_by_category`, `tasks_by_type`, `risks_by_category`, `risks_by_likelihood` breakdowns
- **Page screenshots** — 16 automated Playwright screenshots of all NiceGUI pages in `docs/screenshots/`
- **Design document** — `docs/design-document.md` with architecture overview, data flow, and Mermaid diagrams

### Fixed
- **Estimation revision 422 error** — empty strings sent for `Optional[date]` fields (`start_date`, `expected_delivery`, `testing_start_date`) now converted to `None` before API call
- **DUT edit modal not opening** — Vue slot `@click` events changed from `$parent.$emit(...)` to arrow function `() => $parent.$emit(...)` for reliable event emission
- **User role reverting to VIEWER** — LDAP/OIDC providers no longer overwrite admin-assigned roles; `_map_role()` returns `None` when no group mapping matches, preserving existing role
- **Duplicate `testing_start_date` keys** — removed duplicate key in both create and revise estimation payloads

### Changed
- Dashboard moved from placeholder to full inline implementation in `app.py` with 3 chart rows and paginated tables
- DUT registry uses `selection="multiple"` table with action buttons via arrow function event emission
- User management table supports multi-select with conditional bulk role button visibility
- Version bumped to 3.3.0 across `pyproject.toml`, `app.py`, and `README.md`

---

## [3.2.0] - 2026-03-06

### Added
- **Configurable PR complexity hours** — Simple/Medium/Complex PR fix hours editable from Settings (`pr_hours_simple`, `pr_hours_medium`, `pr_hours_complex`) instead of hardcoded values
- **PR test availability tracking** — each PR fix can be marked as `test_available`; PRs without existing tests generate synthetic "Test Creation" tasks in the task breakdown
- **PR no-test hours** — configurable hours per PR without existing tests (`pr_no_test_hours`), linkable to a task template for overlap detection (`pr_no_test_task_template_id`)
- **Document deliverables visibility** — document type overlap adjustments now visible in estimation detail view and all 3 report formats (Excel, Word, PDF) with effective hours, total hours, and deduction notes
- **Synthetic documentation tasks** — document types appear as synthetic tasks in the task breakdown, showing effective hours after overlap deduction with linked templates
- **Public holiday calendar** — CRUD management page for public holidays with support for recurring annual holidays (`GET/POST/PUT/DELETE /public-holidays`)
- **Working weeks calculation** — grand total days converted to working weeks (÷5) displayed in detail view and reports; holiday-aware calculation endpoint (`GET /working-weeks`)
- **Enhanced Outline wiki export** — full estimation data in wiki pages: DUT/profile names, team allocation, document deliverables, risk assessment, PR details with test_available column, task notes, and working weeks
- **Jira import enhancements** — PR priority field, test_available property, description modal in import dialog
- **Snipe-IT integration** — new adapter for Snipe-IT asset management system
- **Risk registry page** — new frontend page for risk tracking and management
- **PR registry page** — dedicated frontend page for PR fix management
- **Document types page** — frontend page for managing document type deliverables
- **Asset management page** — frontend page for Snipe-IT asset tracking
- Database migration v14: `pr_no_test_hours` column on estimations, `public_holidays` table

### Changed
- Estimation calculation engine supports configurable PR complexity hours via `EstimationInput`
- Grand total formula includes PR no-test effort and documentation effort
- Excel, Word, and PDF reports include PR Test Creation hours, document deliverables with overlap notes, and working weeks
- Outline export generates comprehensive markdown with team allocation, DUT/profile names, and risk assessment sections
- Settings page includes PR configuration parameters section
- Integration service supports 5 adapters (Redmine, Jira, Email, Outline, Snipe-IT)
- Database schema version bumped to 14 (15 tables total)

### Fixed
- `SyntaxError: 'await' outside async function` in Jira import dialog — changed `_import_selected()` to `async def`
- Per-document vs per-template-group overlap deduction in documentation hours calculation

### Tests
- 274 tests (up from 267): added PR config, public holiday, and integration coverage

---

## [3.1.0] - 2026-02-28

### Added
- RBAC enhancements with fine-grained role permissions
- Team presets for quick estimation setup
- Client IP tracking in audit log entries
- 14 feature enhancements: batch of UI, auth, and integration improvements

### Fixed
- Login authentication for both internal and LDAP providers

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
