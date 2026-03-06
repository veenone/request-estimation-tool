# Feature List

Complete list of features in the Test Effort Estimation Tool (v3.2.0).

---

## Estimation Engine

- **7-step estimation wizard**: Guided workflow (Request → Features → References → DUT/Profile Matrix → PR Fixes → Team → Review)
- **Core formula**: `Task_Effort = Base_Hours × DUT_Multiplier × Profile_Multiplier × Complexity_Weight`
- **Grand total calculation**: Tester effort + Leader effort (configurable ratio) + PR fix effort + PR no-test effort + Study hours + Documentation hours + Buffer (configurable %)
- **Feasibility assessment**: Automatic classification as FEASIBLE (≤80%), AT_RISK (80-100%), or NOT_FEASIBLE (>100%) based on utilization
- **Risk flag detection**: Auto-detects >50% new feature effort, no references, short timelines (<2 weeks), large DUT×Profile matrices (>20), and high historical accuracy ratios (>1.3)
- **Historical calibration**: Past project improvement ratios applied to calibrate new estimates
- **Estimation versioning**: Create new versions via `PUT /revise` while preserving full version history
- **Working weeks**: Grand total days converted to working weeks (÷5) with optional holiday-aware calculation

## Feature & Task Management

- **Feature catalog**: CRUD with name, category, complexity weight, existing test indication
- **Task templates**: Base effort hours per feature, scales_with_dut and scales_with_profile flags
- **Complexity weights**: 1.0 (standard), 1.5 (complex), 2.0 (very complex)
- **New feature study hours**: Configurable hours added per new feature without existing tests

## DUT & Profile Matrix

- **DUT type registry**: Device types with category, complexity multiplier
- **Configurable DUT categories**: Editable from Settings (SIM, eSIM, UICC, etc.)
- **Test profile management**: Profiles with effort multipliers (e.g., Smoke, Comprehensive)
- **Matrix expansion**: Cross-product of selected DUTs × Profiles determines multiplier combinations

## PR Fix Management

- **PR complexity categories**: Simple, Medium, Complex with configurable hours per category
- **PR test availability**: Mark each PR as having existing tests or not
- **PR no-test effort**: PRs without tests generate synthetic "Test Creation" tasks with configurable hours
- **PR no-test task template link**: Link no-test effort to a task template for overlap detection
- **PR registry page**: Dedicated frontend page for PR fix tracking

## Document Deliverables

- **Document type management**: CRUD for document types with base effort hours and count
- **Task template linking**: Link document types to task templates for overlap detection
- **Overlap-aware calculation**: Automatically deducts hours when a linked template is already in the estimation
- **Visibility in detail view**: Effective hours, total hours, and deduction notes displayed
- **Synthetic documentation tasks**: Document types appear in task breakdown with effective hours
- **Report integration**: Document deliverables with overlap notes in Excel, Word, and PDF reports

## Team & Resource Management

- **Team member roster**: Name, role, available hours per day, skills
- **Team presets**: Save and load team configurations for quick setup
- **Leader effort ratio**: Configurable leader overhead (default 50% of tester effort)
- **User assignment**: Assign users to estimations and requests
- **Team allocation**: Automatic team member allocation based on skills and availability

## Report Generation

- **Excel workbook**: 6 sheets (Summary, Tasks, Matrix, Team, PR Fixes, References) with document deliverables and overlap notes
- **Word document**: Cover page, executive summary, detailed tables, document deliverables, sign-off block
- **PDF report**: Color-coded feasibility, summary tables, risk flags, PR test creation hours, working weeks
- **All reports include**: PR test creation hours, document deliverables with effective hours, working weeks, release extra hours

## Authentication & Authorization

- **JWT authentication**: Access and refresh tokens via PyJWT + bcrypt
- **4-role RBAC**: VIEWER, ESTIMATOR, APPROVER, ADMIN with configurable permission matrix
- **LDAP/Active Directory**: External auth with automatic user provisioning on first login
- **OpenID Connect (OIDC)**: Support for Keycloak, Azure AD, Okta, and other OIDC providers
- **LDAP user sync**: Bulk sync LDAP users (ADMIN only)
- **Role mapping**: LDAP/OIDC group-to-role mapping via interactive matrix UI
- **Session management**: JWT sessions with refresh tokens and logout invalidation
- **Audit logging**: Immutable action log with user, action, timestamp, details, and client IP

## Request Inbox

- **Request management**: Create, view, update estimation requests
- **Status tracking**: NEW, IN_PROGRESS, COMPLETED, DELETED_UPSTREAM
- **External sync**: Import requests from Redmine/Jira with automatic deduplication
- **Request-to-estimation linking**: Convert requests into estimations

## Public Holidays & Calendar

- **Holiday CRUD**: Create, update, delete public holidays
- **Recurring holidays**: Mark holidays as annually recurring
- **Country/region support**: Tag holidays by country or region
- **Working week calculation**: Holiday-aware working week endpoint (`GET /working-weeks`)

## Integrations

- **Redmine**: Import issues, export estimations to custom fields, upload reports, webhook support for real-time sync
- **Jira/Xray**: JQL-based import with priority and test_available fields, export to custom fields, X-Ray test plan support
- **Email (SMTP)**: Send estimation reports to stakeholders with HTML templates
- **Outline Wiki**: Publish estimations as wiki pages with full data (tasks, DUT/profiles, team, documents, risks, working weeks)
- **Snipe-IT**: Asset management integration for tracking test equipment
- **Unified dispatcher**: Adapter pattern with test connection and sync for all systems
- **Auto-export**: Automatic Outline export on configurable estimation status changes

## Frontend (NiceGUI)

- **Single-page application**: WebSocket-based with Quasar/Vue components
- **Category-grouped sidebar**: Material icons with organized navigation
- **Dashboard**: Overview statistics and recent activity
- **Estimation wizard**: 7-step stepper with live preview and validation
- **Estimation detail view**: Full breakdown with tasks, documents, PR details, working weeks, risk flags
- **Feature catalog**: CRUD with task template management
- **DUT registry**: CRUD with category filtering
- **Profile management**: CRUD for test profiles
- **Historical projects**: Past project management for calibration
- **Team management**: Team member CRUD with preset support
- **Request inbox**: Request list with detail view and import dialog
- **Integration config**: 5-tab configuration with test/sync buttons
- **Settings**: Global configuration with PR parameters, SMTP test, LDAP test
- **User management**: ADMIN-only user CRUD
- **Audit log viewer**: Filterable action log
- **RBAC matrix**: Interactive permission configuration
- **Public holidays**: Holiday calendar management
- **Document types**: Document deliverable management
- **PR registry**: PR fix tracking
- **Risk registry**: Risk tracking and management
- **Asset management**: Snipe-IT asset tracking
- **Light/dark theme**: Persistent toggle

## Frontend (Streamlit)

- **12 pages**: Dashboard, New Estimation, Feature Catalog, DUT Registry, Profiles, History, Team, Settings, Estimation Detail, Request Inbox, Integrations, Users
- **Light/dark theme**: Persistent toggle

## Frontend (Desktop)

- **C# WinForms (.NET 8)**: Native Windows experience
- **JSON IPC**: Communication with backend via JSON interface

## API

- **60+ REST endpoints**: Full CRUD for all entities
- **OpenAPI documentation**: Auto-generated at `/docs`
- **Health check**: Unauthenticated liveness probe
- **Host config**: Runtime configuration for frontends
- **Webhook support**: Redmine webhook for real-time sync (shared secret auth)

## Infrastructure

- **Docker**: Dockerfile + docker-compose.yml with optional MySQL profile
- **SQLite**: Default zero-config database with auto-initialization
- **MySQL**: Production database support via `DB_URL` environment variable
- **HTTPS/TLS**: Direct SSL support via `SSL_CERTFILE`/`SSL_KEYFILE`
- **CORS**: Configurable origins via `CORS_ORIGINS` environment variable
- **Schema versioning**: Automatic migrations with version tracking (currently v14)
- **Seed data**: Default catalogs and reference projects loaded on first run

## Testing

- **274 tests** across 9 test modules
- **Isolated test databases**: Temporary SQLite per test via fixtures
- **Full API coverage**: TestClient with authenticated Bearer tokens
- **Calculator, feasibility, calibration, models, reports, API, auth, integrations** test coverage
