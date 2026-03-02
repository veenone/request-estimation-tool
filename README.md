# Test Effort Estimation Tool

A structured, data-driven application for producing professional test effort estimations for new product launches, product evolutions, and ongoing support projects. The tool combines a 7-step estimation wizard, historical project calibration, intelligent task catalogs, and automated report generation to deliver defensible estimates in minutes.

**Status:** Version 3.0.0 — Production Ready

---

## Table of Contents

- [Overview](#overview)
- [What's New in v2.0](#whats-new-in-v20)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Authentication & Authorization](#authentication--authorization)
- [Core Concepts](#core-concepts)
- [Estimation Workflow](#estimation-workflow)
- [Worked Example](#worked-example)
- [API Reference](#api-reference)
- [Database Schema](#database-schema)
- [Configuration](#configuration)
- [Environment Variables](#environment-variables)
- [Integrations](#integrations)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

---

## Overview

The Test Effort Estimation Tool automates the estimation process for QA teams, test managers, and engineering leaders. Instead of relying on intuition or spreadsheets, the tool:

- **Structures intake** through a guided 7-step wizard
- **Catalogs tasks** with base effort, complexity weights, and historical multipliers
- **Calibrates estimates** against past projects to improve accuracy
- **Calculates effort** with configurable multipliers (DUT types, test profiles, risk factors)
- **Detects feasibility issues** and suggests mitigation (extend date or add staff)
- **Generates reports** in Excel, Word, and PDF for stakeholder communication
- **Integrates** with Redmine, Jira/Xray, SMTP Email, and Outline Wiki
- **Secures access** with JWT authentication, RBAC (4 roles), LDAP/OIDC support

The tool assumes a matrix-based testing model where testing effort is a function of:
- Task base effort (hours) x DUT multiplier x Profile multiplier x Complexity weight
- Followed by test leader overhead, buffer, and risk adjustments

---

## What's New in v3.0

| Feature | Description |
|---------|-------------|
| **Estimation Versioning** | Version tracking with `PUT /revise` endpoint, wizard inputs preserved per version |
| **Configurable DUT Categories** | DUT type categories stored in configuration table, editable from Settings |
| **HTTPS/TLS Support** | Backend, NiceGUI, and Streamlit all support SSL via `SSL_CERTFILE`/`SSL_KEYFILE` env vars |
| **NiceGUI Sidebar Redesign** | Category-grouped sidebar with Material icons matching Streamlit layout |
| **RBAC Matrix UI** | LDAP/OIDC role mapping displayed as interactive matrix tables in Settings |
| **Outline Auto-Export** | Automatic wiki export on estimation status change (configurable states) |
| **267 Tests** | Up from 263; added versioning and config coverage |

### What's New in v2.0

| Feature | Description |
|---------|-------------|
| **Authentication & RBAC** | JWT auth (PyJWT + bcrypt), 4 roles: VIEWER, ESTIMATOR, APPROVER, ADMIN |
| **LDAP/OIDC** | External auth via ldap3 and authlib providers |
| **MySQL Support** | Engine factory supports SQLite + MySQL via `DB_URL` env var |
| **Notifications** | SMTP notification service with HTML email templates |
| **User Assignment** | Assign users to estimations and requests |
| **Light/Dark Theme** | Persistent toggle in both Streamlit and NiceGUI frontends |
| **Advanced Reports** | Comparison, trend, and executive summary report types |
| **Bulk Import** | CSV/Excel import with validation |
| **Outline Wiki** | 4th integration — publish estimations to Outline wiki |
| **NiceGUI Frontend** | Full SPA alternative to Streamlit with WebSocket-based updates |
| **RBAC Management** | UI page for configuring role permissions |
| **Docker** | Dockerfile + docker-compose.yml for containerized deployment |
| **Admin Script** | `backend/scripts/create_admin.py` for account management |
| **263 Tests** | Up from 152; added auth/RBAC test coverage |

---

## Key Features

### 7-Step Estimation Wizard

1. **Request & Project Type** – Classify project as NEW, EVOLUTION, or SUPPORT
2. **Feature Selection** – Pick features from the catalog; complexity weights auto-applied
3. **Reference Projects** – Select historical projects for calibration and improvement ratios
4. **DUT x Profile Matrix** – Specify device types and test profiles; cross-product combinations
5. **PR Fixes** – Count and categorize in-flight bug fixes (Simple/Medium/Complex with hours)
6. **Delivery Date & Team** – Set target delivery and assign testers + test leaders
7. **Review & Generate** – Auto-detect risk flags, generate multi-format reports

### Estimation Calculation

**Core Formula:**
```
Task_Effort = Base_Hours x DUT_Multiplier x Profile_Multiplier x Complexity_Weight
Grand_Total = Tester_Effort + Leader_Effort(50%) + PR_Fix_Effort + Study_Effort + Buffer(10%)
```

**Feasibility Assessment:**
- **FEASIBLE** (<=80% utilization) – Green, low risk
- **AT_RISK** (80-100% utilization) – Amber, may need mitigation
- **NOT_FEASIBLE** (>100% utilization) – Red, requires date extension or team growth

**Auto-Detected Risk Flags:**
- >50% of effort from new features
- No historical reference projects selected
- Delivery timeline <2 weeks
- DUT x Profile matrix exceeds 20 combinations
- Historical accuracy ratio >1.3 (consistently underestimating)

### Report Generation

**Excel Workbook** (6 sheets): Summary, Tasks, Matrix, Team, PR Fixes, References

**Word Document**: Cover page, executive summary, detailed tables, sign-off block

**PDF Report**: Color-coded feasibility, summary tables, risk flag callouts

### Three Frontend Options

| Frontend | Technology | Run Command | Port |
|----------|-----------|-------------|------|
| **NiceGUI** (recommended) | Python NiceGUI (Quasar/Vue) | `python frontend_nicegui/app.py` | 8502 |
| **Streamlit** | Python Streamlit | `streamlit run frontend_web/app.py` | 8501 |
| **Desktop** | C# WinForms (.NET 8) | `dotnet run` from frontend_desktop/ | N/A |

---

## Technology Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| **Backend** | Python 3.12+ | Core calculation engine and API |
| **Framework** | FastAPI | Async REST API with automatic OpenAPI docs |
| **ORM** | SQLAlchemy 2.0 | Type-safe database queries |
| **Database** | SQLite / MySQL | SQLite by default; MySQL via `DB_URL` env var |
| **Auth** | PyJWT, bcrypt | JWT tokens, password hashing, RBAC |
| **External Auth** | ldap3, authlib | LDAP/AD and OpenID Connect providers |
| **Frontend (Web)** | NiceGUI | SPA with Quasar framework, WebSocket updates |
| **Frontend (Web Alt)** | Streamlit | Pure Python web UI, no JavaScript |
| **Frontend (Desktop)** | C# WinForms (.NET 8) | Native Windows experience |
| **Reports** | openpyxl, python-docx, ReportLab | Professional multi-format output |
| **External APIs** | httpx, requests | HTTP clients for Redmine, Jira, SMTP, Outline |
| **Container** | Docker, docker-compose | Containerized deployment |
| **Testing** | pytest | 267 tests across 9 test modules |

---

## Project Structure

```
request-estimation-tool/
├── README.md                           # This file
├── SPEC.md                             # Detailed software requirements specification
├── CLAUDE.md                           # Development instructions for Claude Code
├── Dockerfile                          # Docker image definition
├── docker-compose.yml                  # Multi-service Docker setup
├── .dockerignore
│
├── backend/                            # Python backend (FastAPI + estimation engine)
│   ├── pyproject.toml                  # Project metadata and dependencies
│   ├── requirements.txt
│   ├── scripts/
│   │   └── create_admin.py             # Admin account creation/reset script
│   ├── src/
│   │   ├── api/                        # FastAPI application
│   │   │   ├── app.py                  # FastAPI app init, CORS, healthcheck
│   │   │   ├── routes.py               # All API endpoints (50+ routes)
│   │   │   └── schemas.py              # Pydantic request/response models
│   │   │
│   │   ├── auth/                       # Authentication & authorization (v2.0)
│   │   │   ├── models.py              # User, UserSession, AuditLog ORM models
│   │   │   ├── schemas.py            # Auth Pydantic models
│   │   │   ├── service.py            # AuthService (JWT, login, RBAC)
│   │   │   ├── dependencies.py       # get_current_user, RequireRole
│   │   │   ├── middleware.py         # AuthContextMiddleware
│   │   │   ├── ldap_provider.py      # LDAP/AD authentication
│   │   │   └── oidc_provider.py      # OpenID Connect provider
│   │   │
│   │   ├── database/                   # Data persistence layer
│   │   │   ├── engine.py              # Engine factory (SQLite + MySQL)
│   │   │   ├── models.py             # SQLAlchemy ORM models (14 tables)
│   │   │   ├── migrations.py         # Schema setup, versioning, seed data
│   │   │   └── seed_data.json        # Default catalogs and reference projects
│   │   │
│   │   ├── engine/                     # Core estimation logic
│   │   │   ├── calculator.py          # Main estimation formulas
│   │   │   ├── feasibility.py        # Feasibility checker and risk assessor
│   │   │   ├── calibration.py        # Historical accuracy analysis
│   │   │   └── allocator.py          # Team member allocation logic
│   │   │
│   │   ├── integrations/              # External system connectors
│   │   │   ├── redmine_adapter.py    # Redmine REST client
│   │   │   ├── jira_adapter.py       # Jira/Xray connector
│   │   │   ├── email_adapter.py      # SMTP email sender
│   │   │   ├── outline_adapter.py    # Outline wiki integration
│   │   │   └── service.py            # Unified integration dispatcher
│   │   │
│   │   ├── reports/                    # Report generation
│   │   │   ├── excel_report.py       # Excel workbook (openpyxl)
│   │   │   ├── word_report.py        # Word document (python-docx)
│   │   │   └── pdf_report.py         # PDF report (ReportLab)
│   │   │
│   │   ├── notifications/             # Notification service (v2.0)
│   │   │   └── service.py            # SMTP notifications with HTML templates
│   │   │
│   │   ├── imports/                    # Bulk import (v2.0)
│   │   │   └── service.py            # CSV/Excel import with validation
│   │   │
│   │   └── cli/                        # Command-line interface
│   │       └── ipc_handler.py         # JSON IPC for C# desktop app
│   │
│   └── tests/                          # 267 tests across 9 modules
│       ├── test_calculator.py          # Estimation formula tests
│       ├── test_feasibility.py        # Feasibility checking tests
│       ├── test_calibration.py        # Historical accuracy tests
│       ├── test_models.py             # Data model validation
│       ├── test_reports.py            # Report generation tests
│       ├── test_api.py                # Core API endpoint tests
│       ├── test_auth.py               # Authentication & RBAC tests (v2.0)
│       ├── test_phase6_api.py         # Integration/Request API tests
│       └── test_integrations.py       # External connector tests
│
├── frontend_nicegui/                   # NiceGUI web UI (recommended)
│   ├── app.py                          # Entry point, auth, sidebar, dashboard
│   └── pages/                          # 14 page modules
│       ├── features.py                # Feature catalog CRUD
│       ├── duts.py                    # DUT registry CRUD
│       ├── profiles.py               # Test profiles CRUD
│       ├── history.py                # Historical projects
│       ├── team.py                   # Team management
│       ├── requests.py               # Request inbox + detail view
│       ├── integrations.py           # Integration config (4 tabs)
│       ├── settings.py               # Settings + SMTP/LDAP test buttons
│       ├── estimation.py             # 7-step wizard + detail view
│       ├── users.py                  # User management (ADMIN)
│       ├── audit.py                  # Audit log viewer
│       └── rbac.py                   # RBAC permission matrix (ADMIN)
│
├── frontend_web/                       # Streamlit web UI (alternative)
│   ├── app.py                          # Main Streamlit entry point
│   └── pages/                          # 12 Streamlit pages
│       ├── 01_Dashboard.py
│       ├── 02_New_Estimation.py       # 7-step wizard
│       ├── 03_Feature_Catalog.py
│       ├── 04_DUT_Registry.py
│       ├── 05_Profiles.py
│       ├── 06_History.py
│       ├── 07_Team.py
│       ├── 08_Settings.py
│       ├── 09_Estimation_Detail.py
│       ├── 10_Request_Inbox.py
│       ├── 11_Integrations.py
│       └── 12_Users.py
│
├── frontend_desktop/                   # C# WinForms (.NET 8)
│   └── EstimationTool/
│
└── data/
    ├── estimation.db                   # SQLite database (auto-created)
    └── seed_data.json
```

---

## Quick Start

### Prerequisites

- Python 3.12 or later
- pip or uv package manager

### Installation

**1. Clone the repository:**
```bash
git clone <repository-url>
cd request-estimation-tool
```

**2. Set up the backend:**
```bash
cd backend
pip install -e .              # Install with all dependencies
# Or for development:
pip install -e ".[dev]"
```

**3. Initialize the database and admin account:**
```bash
# Auto-creates schema, seed data, and default admin (admin/admin)
python scripts/create_admin.py

# Or with a custom password:
python scripts/create_admin.py --password mypassword
```

**4. Run the FastAPI backend:**
```bash
uvicorn src.api.app:app --reload --port 8501
```

The API is at `http://localhost:8501/api`. Interactive docs at `http://localhost:8501/docs`.

**5. Run a frontend:**

**NiceGUI (recommended):**
```bash
cd ../frontend_nicegui
python app.py
# Opens at http://localhost:8502
```

**Streamlit (alternative):**
```bash
cd ../frontend_web
pip install -r requirements.txt
streamlit run app.py
# Opens at http://localhost:8501
```

**6. Login:**
- Default credentials: **admin** / **admin**
- Change the admin password after first login

### Docker Quick Start

```bash
# From project root
docker-compose up           # Start all services
docker-compose up -d        # Start in background
docker-compose down         # Stop all services
```

### Verify Installation

```bash
# Health check (no auth required)
curl http://localhost:8501/api/healthcheck
# → {"status":"ok","version":"3.0.0"}

# Login and get a token
curl -X POST http://localhost:8501/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'
# → {"access_token":"...","refresh_token":"...","user":{...}}
```

---

## Authentication & Authorization

All API endpoints (except `/api/healthcheck`, `/api/host-config`, and `/api/auth/login`) require a valid JWT token.

### Authentication Flow

1. **Login**: `POST /api/auth/login` with `{"username", "password"}` returns access + refresh tokens
2. **Use token**: Include `Authorization: Bearer <access_token>` header on all requests
3. **Refresh**: `POST /api/auth/refresh` with `{"refresh_token"}` to get a new access token
4. **Logout**: `POST /api/auth/logout` to invalidate the session

### Roles (RBAC)

| Role | Permissions |
|------|------------|
| **VIEWER** | Read-only access to estimations and reports |
| **ESTIMATOR** | Create/edit estimations, manage features/DUTs/profiles |
| **APPROVER** | All ESTIMATOR permissions + approve estimations, manage requests |
| **ADMIN** | Full access: user management, RBAC config, audit log, LDAP sync, settings |

### External Authentication

**LDAP/Active Directory:**
- Configure via `ldap_*` settings in the Configuration page
- Sync users: `POST /api/auth/ldap/sync` (ADMIN only)
- Users authenticate against LDAP; local accounts created on first login

**OpenID Connect (OIDC):**
- Configure via `oidc_*` settings or environment variables
- Supports any OIDC-compliant provider (Keycloak, Azure AD, Okta, etc.)

### Default Admin Account

Created automatically on first run:
- Username: `admin`
- Password: `admin`

Reset with the admin script:
```bash
cd backend
python scripts/create_admin.py --password newpassword
```

---

## Core Concepts

### Project Types

| Type | Scenario | Notes |
|------|----------|-------|
| **NEW** | Launch of a new product | Highest effort; all tests created from scratch |
| **EVOLUTION** | Major version upgrade or feature addition | Mix of new and existing tests |
| **SUPPORT** | Bug fixes, minor updates, ongoing maintenance | Lower effort; regression and validation |

### Features & Task Templates

A **Feature** is a testable capability (e.g., "SIM Toolkit", "OTA Update"). Each feature has:
- Complexity weight (1.0 = standard, 1.5 = complex, 2.0 = very complex)
- Mapped task templates (e.g., "Test plan review", "Execute test suite")
- Indication of whether existing test cases exist

**Task Templates** define the base effort (hours) required.

### DUT Types and Profiles

**DUT (Device Under Test)** Types represent different hardware variants with effort multipliers.

**Profiles** represent different test execution contexts (e.g., "Smoke", "Comprehensive").

**Matrix Expansion:** Each feature is tested against selected DUT x Profile combinations.

### Test Leaders and Overhead

**Default model:** Leader effort = 50% of tester effort (configurable via `leader_effort_ratio`).

### Buffer and Risk

A **10% buffer** is applied to total effort to account for unknowns and scope creep. Additional risk buffer if auto-detected risk flags are present.

### Historical Calibration

The system stores past projects with actual vs estimated hours. Reference projects' improvement ratios are applied to calibrate new estimates.

### Feasibility Assessment

```
Utilization = Total_Estimated_Hours / Available_Capacity_Hours
Available_Capacity = Delivery_Days x Team_Size x Hours_Per_Day (default: 7)
```

- **FEASIBLE**: <=80% utilization
- **AT_RISK**: 80-100% utilization
- **NOT_FEASIBLE**: >100% utilization

---

## Estimation Workflow

### Step 1: Request & Project Type
Define the project context: name, type (NEW/EVOLUTION/SUPPORT), description.

### Step 2: Feature Selection
Choose features from the catalog. Base effort and complexity weights are auto-applied.

### Step 3: Reference Projects
Select 1-3 past projects. System calculates weighted improvement ratio for calibration.

### Step 4: DUT x Profile Matrix
Specify which device types and test profiles apply. Cross-product determines multiplier combinations.

### Step 5: PR Fixes
Count bug fixes by complexity: Simple (2h), Medium (4h), Complex (8h).

### Step 6: Delivery Date & Team
Set target delivery date, team size, and leader allocation. Feasibility calculated on-the-fly.

### Step 7: Review & Generate
Final review with risk flags, mitigation suggestions, and one-click report generation.

---

## Worked Example

**Scenario:** "SIM Toolkit v2.5" estimation

### Inputs

| Field | Value |
|-------|-------|
| Project Type | EVOLUTION |
| Features | 1 existing (SIM Toolkit) + 1 new (USSD Update) |
| DUT Types | 3 (iPhone, Android, Blackberry) |
| Profiles | 2 (Smoke, Comprehensive) |
| PR Fixes | 5 (2 Simple + 2 Medium + 1 Complex) |
| Testers | 3 + 1 Test Leader |
| Delivery | 4 weeks (20 working days) |

### Result

- **Total Tester Effort:** 310 hours
- **Leader Effort (50%):** 155 hours
- **Buffer (10%):** 46.5 hours
- **Grand Total:** 511.5 hours (73.1 person-days)
- **Available Capacity:** 560 hours (20 days x 4 people x 7 hrs)
- **Utilization:** 91.3% → **AT_RISK**

---

## API Reference

### Base URL

```
http://localhost:8501/api
```

All endpoints (except healthcheck, host-config, and login) require:
```
Authorization: Bearer <access_token>
```

### System Endpoints (no auth required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/healthcheck` | Liveness probe — returns `{"status":"ok","version":"3.0.0"}` |
| GET | `/api/host-config` | Runtime config for frontends (API version, auth providers) |

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login with `{username, password}` → tokens + user info |
| POST | `/api/auth/refresh` | Refresh access token with `{refresh_token}` |
| POST | `/api/auth/logout` | Invalidate session |
| GET | `/api/auth/me` | Get current user info |
| POST | `/api/auth/ldap/sync` | Sync LDAP users (ADMIN only) |

### Features & Catalogs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/features` | List all features with task templates |
| POST | `/api/features` | Create a new feature |
| PUT | `/api/features/{id}` | Update feature |
| DELETE | `/api/features/{id}` | Delete feature |

### Task Templates

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/task-templates` | List all task templates |
| POST | `/api/task-templates` | Create template |
| PUT | `/api/task-templates/{id}` | Update template |
| DELETE | `/api/task-templates/{id}` | Delete template |

### DUT Types

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dut-categories` | List configured DUT categories |
| GET | `/api/dut-types` | List all DUT types |
| POST | `/api/dut-types` | Create DUT type |
| PUT | `/api/dut-types/{id}` | Update DUT type |
| DELETE | `/api/dut-types/{id}` | Delete DUT type |

### Test Profiles

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/profiles` | List all profiles |
| POST | `/api/profiles` | Create profile |
| PUT | `/api/profiles/{id}` | Update profile |
| DELETE | `/api/profiles/{id}` | Delete profile |

### Historical Projects

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/historical-projects` | List past projects for calibration |
| POST | `/api/historical-projects` | Add a completed project |

### Team Members

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/team-members` | List team roster |
| POST | `/api/team-members` | Add team member |
| PUT | `/api/team-members/{id}` | Update member |
| DELETE | `/api/team-members/{id}` | Remove member |

### Estimations

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/estimations/calculate` | Preview calculation without saving |
| POST | `/api/estimations` | Create estimation from wizard inputs |
| GET | `/api/estimations` | List all estimations |
| GET | `/api/estimations/{id}` | Get estimation detail |
| PUT | `/api/estimations/{id}` | Update estimation |
| DELETE | `/api/estimations/{id}` | Delete estimation |
| POST | `/api/estimations/{id}/status` | Change status (DRAFT/FINAL/APPROVED/REVISED) |
| GET | `/api/estimations/{id}/report/xlsx` | Download Excel report |
| GET | `/api/estimations/{id}/report/docx` | Download Word report |
| GET | `/api/estimations/{id}/report/pdf` | Download PDF report |

### Requests

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/requests` | List estimation requests |
| POST | `/api/requests` | Create request |
| GET | `/api/requests/{id}/detail` | Full request details |
| PUT | `/api/requests/{id}` | Update request |

### Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/configuration` | List all config key-value pairs |
| PUT | `/api/configuration/{key}` | Update or create a config key (upsert) |

### Integrations

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/integrations` | List all integration configs |
| PUT | `/api/integrations/{system}` | Update config (REDMINE, JIRA, EMAIL, OUTLINE) |
| POST | `/api/integrations/{system}/test` | Test connection |
| POST | `/api/integrations/{system}/sync` | Sync data from external system |

### User Management (ADMIN only)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users` | List all users |
| POST | `/api/users` | Create user |
| PUT | `/api/users/{id}` | Update user |
| DELETE | `/api/users/{id}` | Delete user |

### Audit Log (ADMIN only)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/audit-log` | List audit log entries |

### Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/stats` | Overview statistics |

---

## Database Schema

The tool uses 14 tables (SQLite by default, MySQL supported):

### Core Tables
1. **features** – Feature catalog (name, category, complexity_weight, has_existing_tests)
2. **task_templates** – Tasks per feature (base_effort_hours, scales_with_dut/profile)
3. **dut_types** – Device registry (name, category, complexity_multiplier)
4. **test_profiles** – Test config profiles (name, effort_multiplier)
5. **historical_projects** – Past projects with actual vs estimated hours
6. **estimations** – Estimation records (project info, totals, feasibility)
7. **estimation_tasks** – Task breakdown per estimation
8. **team_members** – Tester roster (role, available_hours_per_day, skills)
9. **configuration** – Key-value global settings
10. **requests** – Estimation requests with status tracking
11. **integration_config** – External system credentials and settings

### Auth Tables (v2.0)
12. **users** – User accounts (username, password_hash, role, auth_provider, is_active)
13. **user_sessions** – Active JWT sessions with refresh tokens
14. **audit_log** – Immutable action log (user, action, timestamp, details)

---

## Configuration

Global settings are stored in the `configuration` table and editable via the Settings page or `/api/configuration` endpoints.

### Key Settings

| Key | Default | Description |
|-----|---------|-------------|
| `leader_effort_ratio` | 0.5 | Leader effort as ratio of tester effort |
| `new_feature_study_hours` | 16.0 | Study hours for each new feature |
| `working_hours_per_day` | 7.0 | Working hours per team member per day |
| `buffer_percentage` | 10 | Buffer percentage on total effort |
| `pr_fix_base_hours` | 4.0 | Base hours for PR fix validation |
| `rbac_matrix` | (JSON) | Role-permission matrix (managed via RBAC page) |
| `dut_categories` | `SIM,eSIM,UICC,...` | Comma-separated DUT type categories |
| `outline_auto_export_states` | `FINAL,APPROVED` | Estimation states that trigger Outline export |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_URL` | `http://localhost:8501/api` | NiceGUI frontend API target |
| `DB_URL` | `sqlite:///data/estimation.db` | Database URL (supports `mysql+pymysql://...`) |
| `CORS_ORIGINS` | `*` | Comma-separated allowed CORS origins |
| `JWT_SECRET_KEY` | (auto-generated) | Secret for JWT token signing |
| `LDAP_URI` | | LDAP server URI (e.g., `ldap://dc.example.com:389`) |
| `LDAP_BASE_DN` | | LDAP base DN (e.g., `dc=example,dc=com`) |
| `LDAP_BIND_DN` | | LDAP bind DN for service account |
| `OIDC_ISSUER` | | OIDC provider URL |
| `OIDC_CLIENT_ID` | | OIDC client ID |
| `OIDC_CLIENT_SECRET` | | OIDC client secret |
| `SSL_CERTFILE` | | Path to TLS certificate PEM file (enables HTTPS) |
| `SSL_KEYFILE` | | Path to TLS private key PEM file (enables HTTPS) |
| `NICEGUI_PORT` | `8502` | NiceGUI frontend port |

---

## Integrations

### Redmine
Import issues, push estimation results to custom fields, upload reports.

**Config fields:** Base URL, API Key, Project ID, Tracker ID, field mappings (effort, feasibility, estimation number)

### Jira/Xray
Import via JQL query, export to custom fields and X-Ray test plans.

**Config fields:** Base URL, API Key, Username, JQL Filter, Project Key, Auth Mode (auto/basic/pat), Cloud toggle, SSL verify, Issue Type, field mappings, X-Ray project key

### Email (SMTP)
Send estimation reports to stakeholders.

**Config fields:** SMTP Host, Port, TLS toggle, Username, Password, Sender Email, Sender Name

### Outline Wiki
Publish estimations as wiki pages.

**Config fields:** Outline URL, API Key, Collection ID, Auto-publish toggle

### Configuration

All integrations are configured via the **Integrations** page in the frontend, with individual input fields per system. Each has **Test Connection** and **Sync** buttons.

---

## Development

### Running Tests

```bash
cd backend

# All tests
python -m pytest tests/ -v

# Specific module
python -m pytest tests/test_calculator.py -v

# With coverage
python -m pytest tests/ --cov=src --cov-report=html

# Stop on first failure
python -m pytest tests/ -x

# Skip slow tests
python -m pytest tests/ -m "not slow"
```

### Test Modules

| Module | Tests | Focus |
|--------|-------|-------|
| `test_calculator.py` | ~30 | Estimation formulas and task calculation |
| `test_feasibility.py` | ~25 | Feasibility assessment and risk flags |
| `test_calibration.py` | ~15 | Historical calibration and improvement ratios |
| `test_models.py` | ~15 | ORM model validation |
| `test_reports.py` | ~20 | Excel, Word, PDF report generation |
| `test_api.py` | ~30 | Core API endpoint coverage |
| `test_auth.py` | ~25 | Authentication, JWT, RBAC |
| `test_phase6_api.py` | ~35 | Integration/Request API tests |
| `test_integrations.py` | ~40 | Redmine, Jira, Email, Outline connectors |
| **Total** | **267** | |

### Admin Script

```bash
cd backend

# Create or reset admin (default password: admin)
python scripts/create_admin.py

# Custom password
python scripts/create_admin.py --password mypassword

# Custom username and DB path
python scripts/create_admin.py --username superadmin --password secret --db-path /path/to/db
```

---

## Deployment

### Local Development

```bash
# Terminal 1: Backend API
cd backend
uvicorn src.api.app:app --reload --port 8501

# Terminal 2: NiceGUI Frontend
cd frontend_nicegui
python app.py
# → http://localhost:8502
```

### Docker

```bash
# From project root
docker-compose up -d        # Start in background
docker-compose logs -f      # View logs
docker-compose down         # Stop
```

### Production

For production deployments:
- Set `JWT_SECRET_KEY` to a strong random value
- Set `CORS_ORIGINS` to your frontend domain(s)
- Use MySQL (`DB_URL=mysql+pymysql://user:pass@host/dbname`) for multi-user access
- Configure LDAP/OIDC for enterprise authentication
- Enable TLS directly: set `SSL_CERTFILE` and `SSL_KEYFILE` env vars pointing to PEM files
- Or place behind a reverse proxy (nginx/Caddy) with TLS

---

## Troubleshooting

### Authentication Issues

**Problem: "Invalid credentials" on login**
- Verify the backend is running on the expected port
- Reset admin password: `cd backend && python scripts/create_admin.py --password admin`

**Problem: "401 Unauthorized" on API calls**
- Token may be expired; re-login to get a fresh token
- Check that the `Authorization: Bearer <token>` header is included

### Database Issues

**Problem: "File does not exist" error**
```bash
cd backend
python -c "from src.database.migrations import init_database; init_database()"
```

**Problem: Fresh start needed**
```bash
rm data/estimation.db
cd backend && python scripts/create_admin.py
```

### API Connection Issues

**Problem: "Connection refused"**
- Ensure the backend is running: `uvicorn src.api.app:app --port 8501`
- Check that no other service is using the port

**Problem: `_stcore` 404 messages in backend log**
- These are Streamlit internal polling requests — they are silently handled as of v2.0

### Integration Failures

**Problem: Redmine/Jira test fails**
- Check credentials in Integrations page
- Verify the URL is reachable
- For Jira DC with self-signed certs, disable SSL verification

**Problem: Email not sending**
- Verify SMTP host, port, and credentials
- For Gmail, use an App Password (not regular password)
- Check TLS setting matches your provider

---

## Contributing

Contributions are welcome! Please follow these guidelines:

1. **Code Style**: Run `black`, `ruff`, and `mypy` before committing
2. **Tests**: Add tests for any new functionality
3. **Documentation**: Update README.md and docstrings as needed
4. **Commit Messages**: Use clear, descriptive messages

For major changes, please open an issue first to discuss the approach.

---

**Version**: 3.0.0
**Last Updated**: March 2026
**Status**: Production Ready
