# Test Effort Estimation Tool

A structured, data-driven application for producing professional test effort estimations for new product launches, product evolutions, and ongoing support projects. The tool combines a 7-step estimation wizard, historical project calibration, intelligent task catalogs, and automated report generation to deliver defensible estimates in minutes.

**Status:** Version 0.1.0 — Active Development

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
- [Estimation Workflow](#estimation-workflow)
- [Worked Example](#worked-example)
- [API Reference](#api-reference)
- [Database Schema](#database-schema)
- [Configuration](#configuration)
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
- **Integrates** with Redmine, Jira/Xray, and SMTP for seamless workflow

The tool assumes a matrix-based testing model where testing effort is a function of:
- Task base effort (hours) × DUT multiplier × Profile multiplier × Complexity weight
- Followed by test leader overhead, buffer, and risk adjustments

---

## Key Features

### 7-Step Estimation Wizard

1. **Request & Project Type** – Classify project as NEW, EVOLUTION, or SUPPORT
2. **Feature Selection** – Pick features from the catalog; complexity weights auto-applied
3. **Reference Projects** – Select historical projects for calibration and improvement ratios
4. **DUT × Profile Matrix** – Specify device types and test profiles; cross-product combinations
5. **PR Fixes** – Count and categorize in-flight bug fixes (Simple/Medium/Complex with hours)
6. **Delivery Date & Team** – Set target delivery and assign testers + test leaders
7. **Review & Generate** – Auto-detect risk flags, generate multi-format reports

### Estimation Calculation

**Core Formula:**
```
Task_Effort = Base_Hours × DUT_Multiplier × Profile_Multiplier × Complexity_Weight
Grand_Total = Tester_Effort + Leader_Effort(50%) + PR_Fix_Effort + Study_Effort + Buffer(10%)
```

**Feasibility Assessment:**
- **FEASIBLE** (≤80% utilization) – Green, low risk
- **AT_RISK** (80–100% utilization) – Amber, may need mitigation
- **NOT_FEASIBLE** (>100% utilization) – Red, requires date extension or team growth

**Auto-Detected Risk Flags:**
- >50% of effort from new features
- No historical reference projects selected
- Delivery timeline <2 weeks
- DUT × Profile matrix exceeds 20 combinations
- Historical accuracy ratio >1.3 (consistently underestimating)

### Report Generation

**Excel Workbook** (6 sheets):
- Summary: totals, utilization, risk flags
- Tasks: detailed task breakdown by feature
- Matrix: DUT × Profile combinations and multipliers
- Team: tester/leader allocation and hours
- PR Fixes: bug fix categorization and effort
- References: historical project comparison and calibration ratios

**Word Document**:
- Professional cover page with project metadata
- Executive summary with risk assessment
- Detailed tables and feasibility analysis
- Estimation assumptions and notes
- Sign-off block for stakeholder approval

**PDF Report**:
- Color-coded feasibility status
- Summary tables with visual hierarchy
- Risk flag callouts and mitigation suggestions
- One-page executive summary option

### Integrations

- **Redmine**: Import issues from projects, push estimation results to custom fields, upload reports
- **Jira/Xray**: Import via JQL query, export to Xray test plans and custom fields
- **SMTP Email**: Send estimation reports via email with PDF attachment

---

## Technology Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| **Backend** | Python 3.12+ | Core calculation engine and API |
| **Framework** | FastAPI | Async REST API with automatic OpenAPI docs |
| **ORM** | SQLAlchemy 2.0 | Type-safe database queries |
| **Database** | SQLite | Zero-configuration, single-file, portable |
| **Frontend (Web)** | Streamlit | Pure Python web UI, no JavaScript |
| **Frontend (Desktop)** | C# WinForms (.NET 8) | Native Windows experience (separate repo) |
| **Reports** | openpyxl, python-docx, ReportLab | Professional multi-format output |
| **External APIs** | requests | HTTP client for Redmine, Jira, SMTP |
| **Testing** | pytest | 152 tests across 8 test modules |
| **Code Quality** | black, ruff, mypy | Automated formatting, linting, type checking |

---

## Project Structure

```
request-estimation-tool/
├── README.md                           # This file
├── SPEC.md                             # Detailed software requirements specification
├── CLAUDE.md                           # Development instructions for Claude Code
│
├── backend/                            # Python backend (FastAPI + estimation engine)
│   ├── pyproject.toml                  # Project metadata and dependencies
│   ├── src/
│   │   ├── api/                        # FastAPI application
│   │   │   ├── app.py                  # FastAPI app initialization
│   │   │   ├── routes.py               # All API endpoints (40+ routes)
│   │   │   └── schemas.py              # Pydantic request/response models
│   │   │
│   │   ├── database/                   # Data persistence layer
│   │   │   ├── __init__.py             # Session and engine setup
│   │   │   ├── models.py               # SQLAlchemy ORM models (11 tables)
│   │   │   ├── migrations.py           # Schema setup and seed data
│   │   │   └── seed_data.json          # Default catalogs and reference projects
│   │   │
│   │   ├── engine/                     # Core estimation logic
│   │   │   ├── calculator.py           # Main calculator class
│   │   │   ├── feasibility.py          # Feasibility checker and risk assessor
│   │   │   ├── calibration.py          # Historical accuracy analysis
│   │   │   └── allocator.py            # Team member allocation logic
│   │   │
│   │   ├── integrations/               # External system connectors
│   │   │   ├── redmine_adapter.py      # Redmine REST client
│   │   │   ├── jira_adapter.py         # Jira/Xray connector
│   │   │   ├── email_adapter.py        # SMTP email sender
│   │   │   └── integration_service.py  # Unified integration dispatcher
│   │   │
│   │   ├── reports/                    # Report generation
│   │   │   ├── excel_generator.py      # Excel workbook creator
│   │   │   ├── word_generator.py       # Word document creator
│   │   │   ├── pdf_generator.py        # PDF report via ReportLab
│   │   │   └── templates.py            # Style and layout templates
│   │   │
│   │   └── cli/                        # Command-line interface
│   │       └── ipc_handler.py          # Inter-process communication for C# desktop app
│   │
│   ├── tests/                          # 152 tests across 8 modules
│   │   ├── test_calculator.py          # Estimation formula and task calculation
│   │   ├── test_feasibility.py         # Feasibility checking logic
│   │   ├── test_calibration.py         # Historical accuracy ratios
│   │   ├── test_allocator.py           # Team member allocation
│   │   ├── test_api.py                 # API endpoint coverage
│   │   ├── test_phase6_api.py          # Integration/Request Inbox API tests
│   │   ├── test_integrations.py        # Redmine, Jira, Email integration tests
│   │   ├── test_reports.py             # Report generation tests
│   │   └── test_models.py              # Data model validation
│   │
│   └── data/
│       └── estimation_tool.db          # SQLite database (created at first run)
│
├── frontend_web/                       # Streamlit web UI (optional, development only)
│   ├── app.py                          # Main Streamlit entry point
│   ├── pages/                          # 11 Streamlit pages
│   │   ├── 1_Dashboard.py              # Overview and estimation statistics
│   │   ├── 2_New_Estimation.py         # 7-step estimation wizard
│   │   ├── 3_Feature_Catalog.py        # Feature and task template CRUD
│   │   ├── 4_DUT_Registry.py           # Device type management
│   │   ├── 5_Profiles.py               # Test profile management
│   │   ├── 6_History.py                # Historical projects browser
│   │   ├── 7_Team.py                   # Team member management
│   │   ├── 8_Settings.py               # Global configuration editor
│   │   ├── 9_Estimation_Detail.py      # View/edit saved estimation
│   │   ├── 10_Request_Inbox.py         # Request management with status tracking
│   │   └── 11_Integrations.py          # Redmine/Jira/Email configuration
│   │
│   └── requirements.txt                # Streamlit dependencies
│
├── docs/
│   └── SRS.md                          # Supplementary requirements documentation
│
└── data/
    ├── seed_data.json                  # Default feature catalog and reference projects
    └── estimation_tool.db              # SQLite database (created at first run)
```

---

## Quick Start

### Prerequisites

- Python 3.12 or later
- pip or uv package manager
- SQLite (included with Python)

### Installation

**1. Clone the repository:**
```bash
git clone <repository-url>
cd request-estimation-tool
```

**2. Set up the backend:**
```bash
cd backend
pip install -e .              # Install in editable mode with all dependencies
# Or, for development with testing tools:
pip install -e ".[dev]"
```

**3. Initialize the database:**
```bash
python -c "from src.database.migrations import init_database; init_database()"
```

**4. Run the FastAPI backend:**
```bash
uvicorn src.api.app:app --reload --port 8000
```

The backend API will be available at `http://localhost:8000`. Auto-generated API docs are at `http://localhost:8000/docs`.

**5. (Optional) Run the Streamlit web UI:**
```bash
cd ../frontend_web
pip install -r requirements.txt
streamlit run app.py
```

The web UI will open at `http://localhost:8501`.

### Verify Installation

Test that the backend is running:
```bash
curl http://localhost:8000/api/dashboard/stats
```

Expected response:
```json
{
  "total_estimations": 0,
  "total_requests": 0,
  "completed_estimations": 0,
  "at_risk_count": 0
}
```

---

## Core Concepts

### Project Types

| Type | Scenario | Notes |
|------|----------|-------|
| **NEW** | Launch of a new product | Highest effort; all tests created from scratch |
| **EVOLUTION** | Major version upgrade or feature addition | Mix of new and existing tests; some regression |
| **SUPPORT** | Bug fixes, minor updates, ongoing maintenance | Lower effort; focused on regression and validation |

### Features & Task Templates

A **Feature** is a testable capability (e.g., "SIM Toolkit", "OTA Update"). Each feature has:
- Complexity weight (1.0 = standard, 1.5 = complex, 2.0 = very complex)
- Mapped task templates (e.g., "Test plan review", "Execute test suite")
- Indication of whether existing test cases exist

**Task Templates** define the base effort (hours) required. For example:
- "Environment setup": 8 hours (per DUT)
- "Execute test suite": 16 hours (per DUT × Profile combination)
- "Test creation (new)": 24 hours (once, regardless of DUT × Profile)

### DUT Types and Profiles

**DUT (Device Under Test)** Types represent different hardware variants:
- Multiplier per type (1.0 = baseline, 1.2 = 20% harder to test)
- Reason for multiplier (e.g., "Legacy hardware", "New platform")

**Profiles** represent different test execution contexts:
- Multiplier per profile (e.g., 1.0 for "Smoke", 2.0 for "Comprehensive")
- Maps to different test scopes and depths

**Matrix Expansion:**
Each feature is tested against all DUT × Profile combinations. A feature with 3 DUTs and 2 Profiles = 6 combinations for effort calculation.

### Test Leaders and Overhead

Test leaders (QA managers, senior test engineers) typically provide:
- Test plan review and oversight
- Result analysis and reporting
- Risk assessment and mitigation planning

**Default model:** Leader effort = 50% of tester effort (configurable per estimation).

### Buffer and Risk

A **10% buffer** is applied to total tester + leader effort to account for:
- Unknowns and scope creep
- Dependency delays
- Integration testing complexity

Additional **risk buffer** is added if auto-detected risk flags are present.

### Historical Calibration

The system stores past projects with:
- Actual hours spent vs. estimated hours
- Improvement ratio (actual ÷ estimated)
- Project type, feature count, DUT count, team size

When creating a new estimation, you select 1–3 reference projects. The system applies their improvement ratios to the current estimate, e.g., if a past project was 1.15× harder than estimated, the new estimate is multiplied by 1.15.

### Feasibility Assessment

**Utilization** is calculated as:
```
Utilization = Total_Estimated_Hours / Available_Capacity_Hours
Available_Capacity = Delivery_Days × Team_Size × Hours_Per_Day (default: 7 hrs/day)
```

**Status Codes:**
- **FEASIBLE**: ≤80% → Comfortable buffer, low risk
- **AT_RISK**: 80–100% → Tight schedule, may need mitigation
- **NOT_FEASIBLE**: >100% → Impossible without extending date or adding staff

---

## Estimation Workflow

### Step 1: Request & Project Type

Define the project context:
- **Project Name** (e.g., "SIM Toolkit v2.5")
- **Project Type**: NEW, EVOLUTION, or SUPPORT
- **Description** (optional context for stakeholders)

### Step 2: Feature Selection

Choose features from the catalog. For each selected feature:
- Base effort from task templates is retrieved
- Complexity weight is applied
- Applicable DUT × Profile combinations are identified

### Step 3: Reference Projects

Select 1–3 past projects with similar characteristics:
- System fetches actual/estimated ratio for each project
- Calculates weighted average improvement ratio
- This ratio is used to calibrate the current estimate

### Step 4: DUT × Profile Matrix

Specify which device types and test profiles apply:
- **DUTs** (e.g., "iPhone 15", "Pixel 8", "Samsung Galaxy")
- **Profiles** (e.g., "Smoke", "Functional", "Comprehensive")

The system cross-products to determine how many times to apply effort multipliers.

### Step 5: PR Fixes

Count in-flight bug fixes, categorized by effort:
- **Simple**: 2 hours per fix
- **Medium**: 4 hours per fix
- **Complex**: 8 hours per fix

Total PR fix effort = (Count × Hours) × DUT_Count (testing on each device type).

### Step 6: Delivery Date & Team

- **Target Delivery Date** (date picker)
- **Team Allocation** (assign testers and test leaders from roster)

Feasibility is calculated on-the-fly as team members are added/removed.

### Step 7: Review & Generate

Final review before approval:
- Summary of total effort, utilization, feasibility status
- Highlighted risk flags and mitigation suggestions
- One-click generation of Excel, Word, and PDF reports

---

## Worked Example

**Scenario:** "SIM Toolkit v2.5" estimation (from SPEC)

### Inputs

| Field | Value |
|-------|-------|
| Project Type | EVOLUTION |
| Features | 1 existing (SIM Toolkit) + 1 new (USSD Update) |
| DUT Types | 3 (iPhone, Android, Blackberry) |
| Profiles | 2 (Smoke, Comprehensive) |
| PR Fixes | 5 (categorized as 2 Simple + 2 Medium + 1 Complex) |
| Testers | 3 (40 hrs/week × 4 weeks = 160 hrs each) |
| Test Leaders | 1 (40 hrs/week × 4 weeks = 160 hrs) |
| Delivery | 4 weeks from now |
| Reference Projects | 2 (historical projects for calibration) |

### Calculation

**Tester Effort Breakdown:**

| Task | Base | DUT | Prof | Total | Notes |
|------|------|-----|------|-------|-------|
| Environment setup | 8h | ×3 | ×1 | 24h | Once per DUT |
| Test plan review | 4h | ×1 | ×1 | 4h | Once |
| Execute test suite | 16h | ×3 | ×2 | 96h | Full matrix |
| Regression testing | 12h | ×3 | ×2 | 72h | Full matrix |
| PR fix validation | 4h×5 | ×3 | ×1 | 60h | 5 PRs × 3 DUTs |
| New feature study | 16h | ×1 | ×1 | 16h | Once |
| Test creation (new) | 24h | ×1 | ×1 | 24h | Once |
| Result analysis | 6h | ×1 | ×1 | 6h | Once |
| Test report writing | 8h | ×1 | ×1 | 8h | Once |

**Subtotal (Tester Effort):** 310 hours

**Test Leader Effort:** 310 × 0.5 = 155 hours

**Buffer (10%):** (310 + 155) × 0.10 = 46.5 hours

**Grand Total:** 310 + 155 + 46.5 = **511.5 hours** (73.1 person-days)

### Feasibility Assessment

**Available Capacity:**
- 20 working days × 4 people (3 testers + 1 leader) × 7 hrs/day = 560 hours

**Utilization:**
- 511.5 / 560 = **91.3%** → **AT_RISK** (amber)

### Risk Flags

The system would flag:
- ✓ DUT × Profile = 3 × 2 = 6 combinations (≤20, OK)
- ✓ 1 new feature out of 2 total = 50% (borderline; flagged as warning)
- ✓ Reference projects selected (mitigation present)
- ✓ 4-week delivery (not <2 weeks, OK)

### Mitigation Suggestions

The system suggests:
1. Extend delivery to 5 weeks → utilization drops to 73% (FEASIBLE)
2. Add 1 more tester → 5 people × 560 hrs = 700 hrs available → 73% (FEASIBLE)
3. Reduce scope (remove 1 PR fix or defer new feature)

### Generated Reports

The Excel, Word, and PDF reports include:
- All task details and calculations
- Team allocation and hours
- Feasibility graph and utilization breakdown
- Risk flags and mitigation options
- Sign-off section for manager approval

---

## API Reference

### Base URL

```
http://localhost:8000/api
```

### Authentication

Currently, all endpoints are open. For production, add JWT/RBAC via the `AuthenticationManager` from the SPEC.

### Core Endpoints

#### Requests Management

**GET /requests**
- List all estimation requests
- Query parameters: `status` (NEW, IN_ESTIMATION, ESTIMATED, etc.), `skip`, `limit`

**POST /requests**
- Create a new estimation request
- Request body: `{ "name": str, "project_type": str, "description": str }`
- Returns: Estimation request with ID

**GET /requests/{request_id}/detail**
- Fetch full request details with all related data

**PUT /requests/{request_id}**
- Update request status or metadata

**POST /requests/{request_id}/attachments**
- Upload supporting documents (scope, requirements, etc.)

#### Features & Catalogs

**GET /features**
- List all features in the catalog with task templates

**POST /features**
- Create a new feature
- Request body: `{ "name": str, "category": str, "complexity_weight": float, "has_existing_tests": bool }`

**PUT /features/{feature_id}**
- Update feature details

**DELETE /features/{feature_id}**
- Remove a feature from the catalog

#### Task Templates

**GET /task-templates**
- List all task templates

**POST /task-templates**
- Create a new task template
- Request body: `{ "name": str, "category": str, "base_hours": float, "scaling_type": str }`

**PUT /task-templates/{template_id}**
- Update task template

**DELETE /task-templates/{template_id}**
- Remove a task template

#### DUT Types

**GET /dut-types**
- List all device under test types with multipliers

**POST /dut-types**
- Create a new DUT type
- Request body: `{ "name": str, "multiplier": float, "reason": str }`

**PUT /dut-types/{dut_id}**
- Update DUT type

**DELETE /dut-types/{dut_id}**
- Remove a DUT type

#### Test Profiles

**GET /profiles**
- List all test profiles with multipliers

**POST /profiles**
- Create a new profile
- Request body: `{ "name": str, "multiplier": float, "description": str }`

**PUT /profiles/{profile_id}**
- Update profile

**DELETE /profiles/{profile_id}**
- Remove a profile

#### Historical Projects

**GET /historical-projects**
- List past projects used for calibration

**POST /historical-projects**
- Add a completed project to history
- Request body includes: `estimated_hours`, `actual_hours`, `project_type`, `feature_count`, etc.

#### Team Members

**GET /team-members**
- List available testers and test leaders

**POST /team-members**
- Add a team member to the roster

**PUT /team-members/{member_id}**
- Update team member availability

**DELETE /team-members/{member_id}**
- Remove a team member

#### Estimations

**POST /estimations**
- Create a new estimation from wizard inputs
- Request body: Full estimation payload with selected features, DUTs, profiles, team, etc.
- Returns: New estimation with ID and initial calculations

**GET /estimations**
- List all estimations with summary stats

**GET /estimations/{estimation_id}**
- Fetch a single estimation with full task breakdown

**PUT /estimations/{estimation_id}**
- Update estimation (e.g., adjust team members, add more PR fixes)

**DELETE /estimations/{estimation_id}**
- Delete an estimation (soft delete with audit trail)

**POST /estimations/{estimation_id}/calculate**
- Recalculate effort after adjustments

**POST /estimations/{estimation_id}/status**
- Update estimation status (DRAFT, FINAL, APPROVED, REVISED)

**POST /estimations/{estimation_id}/calibrate**
- Apply historical improvement ratio to current estimate

**POST /estimations/{estimation_id}/send-report**
- Email the estimation report to stakeholders

#### Reports

**GET /estimations/{estimation_id}/report/xlsx**
- Download Excel workbook with all estimation details

**GET /estimations/{estimation_id}/report/docx**
- Download Word document report

**GET /estimations/{estimation_id}/report/pdf**
- Download PDF report

#### Configuration

**GET /configuration**
- Fetch global configuration (hours per day, buffer %, leader overhead %, etc.)

**PUT /configuration**
- Update global configuration

#### Dashboard & Analytics

**GET /dashboard/stats**
- High-level overview: total estimations, completed, at-risk, average utilization

#### Integrations

**GET /integrations/{system}**
- Get integration configuration for Redmine, Jira, or Email

**PUT /integrations/{system}**
- Update integration credentials and settings

**POST /integrations/{system}/test**
- Test connection to external system

**POST /integrations/{system}/sync**
- Sync data (e.g., import Redmine issues, pull Jira projects)

**GET /integrations/{system}/status**
- Check integration health and last sync time

---

## Database Schema

The tool uses SQLite with 11 core tables:

### 1. requests
Incoming estimation requests from stakeholders.

| Column | Type | Key | Notes |
|--------|------|-----|-------|
| id | INTEGER | PK | Auto-increment |
| name | TEXT | UNIQUE | Project name |
| project_type | TEXT | | NEW, EVOLUTION, SUPPORT |
| status | TEXT | | NEW, IN_ESTIMATION, ESTIMATED, IN_PROGRESS, COMPLETED, CANCELLED |
| description | TEXT | | Project scope and context |
| created_at | TIMESTAMP | | Created timestamp |
| updated_at | TIMESTAMP | | Last update timestamp |

### 2. features
Master catalog of testable features.

| Column | Type | Key | Notes |
|--------|------|-----|-------|
| id | INTEGER | PK | Auto-increment |
| name | TEXT | UNIQUE | Feature name (e.g., "SIM Toolkit") |
| category | TEXT | | Feature category (e.g., "Telecom", "Security") |
| complexity_weight | REAL | | 1.0=standard, 1.5=complex, 2.0=very complex |
| has_existing_tests | BOOLEAN | | Whether test cases exist |
| description | TEXT | | Feature scope description |

### 3. task_templates
Base task definitions with effort hours.

| Column | Type | Key | Notes |
|--------|------|-----|-------|
| id | INTEGER | PK | Auto-increment |
| name | TEXT | UNIQUE | Task name (e.g., "Execute test suite") |
| category | TEXT | | Task category (e.g., "Execution", "Planning") |
| base_hours | REAL | | Base effort in hours |
| scaling_type | TEXT | | FIXED, PER_DUT, PER_PROFILE, PER_MATRIX |
| feature_id | INTEGER | FK | Optional link to feature |

### 4. dut_types
Device under test types with effort multipliers.

| Column | Type | Key | Notes |
|--------|------|-----|-------|
| id | INTEGER | PK | Auto-increment |
| name | TEXT | UNIQUE | DUT name (e.g., "iPhone 15") |
| multiplier | REAL | | Effort multiplier (1.0=baseline) |
| reason | TEXT | | Why this multiplier (e.g., "Legacy hardware") |

### 5. test_profiles
Test execution profiles (scope/depth) with multipliers.

| Column | Type | Key | Notes |
|--------|------|-----|-------|
| id | INTEGER | PK | Auto-increment |
| name | TEXT | UNIQUE | Profile name (e.g., "Comprehensive") |
| multiplier | REAL | | Effort multiplier (1.0=baseline) |
| description | TEXT | | Profile scope and test depth |

### 6. historical_projects
Past projects for calibration.

| Column | Type | Key | Notes |
|--------|------|-----|-------|
| id | INTEGER | PK | Auto-increment |
| name | TEXT | UNIQUE | Project name |
| project_type | TEXT | | NEW, EVOLUTION, SUPPORT |
| estimated_hours | REAL | | Original estimate |
| actual_hours | REAL | | Actual time spent |
| feature_count | INTEGER | | Number of features |
| dut_count | INTEGER | | Number of DUT types |
| team_size | INTEGER | | Number of testers |
| completed_date | TIMESTAMP | | Project completion date |
| notes | TEXT | | Lessons learned |

### 7. estimations
Active estimations in progress or approved.

| Column | Type | Key | Notes |
|--------|------|-----|-------|
| id | INTEGER | PK | Auto-increment |
| request_id | INTEGER | FK | Reference to request |
| status | TEXT | | DRAFT, FINAL, APPROVED, REVISED |
| estimated_hours | REAL | | Total estimated effort |
| leader_hours | REAL | | Test leader overhead |
| pr_fix_hours | REAL | | PR fix effort |
| buffer_hours | REAL | | 10% buffer |
| total_hours | REAL | | Grand total |
| utilization_percent | REAL | | Utilization % |
| feasibility_status | TEXT | | FEASIBLE, AT_RISK, NOT_FEASIBLE |
| risk_flags | TEXT | | JSON array of flagged risks |
| created_at | TIMESTAMP | | Created timestamp |
| updated_at | TIMESTAMP | | Last update timestamp |

### 8. estimation_tasks
Detailed task breakdown per estimation.

| Column | Type | Key | Notes |
|--------|------|-----|-------|
| id | INTEGER | PK | Auto-increment |
| estimation_id | INTEGER | FK | Parent estimation |
| task_template_id | INTEGER | FK | Reference to task template |
| feature_id | INTEGER | FK | Associated feature |
| dut_id | INTEGER | FK | DUT type for this instance |
| profile_id | INTEGER | FK | Profile for this instance |
| base_hours | REAL | | Original base hours |
| dut_multiplier | REAL | | DUT effort multiplier |
| profile_multiplier | REAL | | Profile effort multiplier |
| complexity_weight | REAL | | Feature complexity weight |
| calculated_hours | REAL | | Final effort (base × DUT × Prof × Complexity) |

### 9. team_members
QA staff roster with skills and availability.

| Column | Type | Key | Notes |
|--------|------|-----|-------|
| id | INTEGER | PK | Auto-increment |
| name | TEXT | UNIQUE | Full name |
| role | TEXT | | TESTER, TEST_LEADER, QA_ENGINEER |
| email | TEXT | | Contact email |
| availability_percent | REAL | | % available (0-100) |
| skills | TEXT | | JSON array of skill tags |

### 10. configuration
Global settings.

| Column | Type | Key | Notes |
|--------|------|-----|-------|
| key | TEXT | PK | Setting name (e.g., "hours_per_day") |
| value | TEXT | | Setting value |

### 11. integration_config
Credentials and settings for external integrations.

| Column | Type | Key | Notes |
|--------|------|-----|-------|
| system | TEXT | PK | "redmine", "jira", "email" |
| config | TEXT | | JSON with credentials, URLs, etc. |

---

## Configuration

Global settings are stored in the `configuration` table and can be edited via the Settings page in the Streamlit UI or the `/api/configuration` endpoints.

### Key Settings

| Key | Default | Type | Description |
|-----|---------|------|-------------|
| `hours_per_day` | 7 | Float | Working hours per team member per day |
| `buffer_percent` | 10 | Float | Standard buffer on top of estimated effort |
| `leader_overhead_percent` | 50 | Float | Test leader effort as % of tester effort |
| `days_per_week` | 5 | Integer | Working days per week |
| `max_dut_profile_combinations` | 20 | Integer | Threshold for "too many combinations" risk flag |
| `improvement_ratio_threshold` | 1.3 | Float | Threshold for "consistently underestimating" risk flag |
| `feasible_utilization_threshold` | 80 | Float | Utilization % for FEASIBLE status |
| `at_risk_utilization_threshold` | 100 | Float | Utilization % for AT_RISK status |
| `min_weeks_delivery` | 2 | Integer | Minimum weeks for delivery <2 weeks risk flag |

---

## Integrations

### Redmine Integration

Connect to a Redmine instance to import issues and push estimation results.

**Setup:**
1. Go to Settings → Integrations → Redmine
2. Enter Redmine URL and API key
3. Click "Test Connection"

**Operations:**
- **Import Issues**: Pull open issues from a Redmine project; auto-create estimation requests
- **Push Results**: Update issue custom fields with estimated hours, feasibility status, etc.
- **Upload Reports**: Attach PDF/Word/Excel reports to Redmine issues

### Jira/Xray Integration

Connect to Jira Cloud or Server to sync test cases and export estimations.

**Setup:**
1. Go to Settings → Integrations → Jira
2. Enter Jira URL, username, and API token
3. Click "Test Connection"

**Operations:**
- **Import via JQL**: Write a JQL query to fetch issues; auto-map to features
- **Export to Xray**: Push estimated hours to Xray custom fields and test plans
- **Sync Metadata**: Keep feature names and task counts in sync

### Email Integration

Send estimation reports to stakeholders via SMTP.

**Setup:**
1. Go to Settings → Integrations → Email
2. Enter SMTP server, port, username, password
3. Click "Test Connection"

**Operations:**
- **Send Report**: Email a PDF/Excel report to a distribution list
- **Batch Send**: Send estimations to multiple projects at once
- **Scheduled Digest**: Set up weekly email with all new estimations

---

## Development

### Directory Layout for Developers

```
backend/src/
├── api/
│   ├── app.py              # FastAPI initialization; mount routers
│   ├── routes.py           # All API endpoints grouped by domain
│   └── schemas.py          # Request/response Pydantic models
│
├── database/
│   ├── __init__.py         # Session factory and engine setup
│   ├── models.py           # SQLAlchemy ORM class definitions
│   ├── migrations.py       # Schema creation and seed data loading
│   └── seed_data.json      # Default features, DUTs, profiles, historical projects
│
├── engine/
│   ├── calculator.py       # Main Calculator class (effort computation)
│   ├── feasibility.py      # FeasibilityChecker and RiskAssessor classes
│   ├── calibration.py      # CalibrationEngine for improvement ratios
│   └── allocator.py        # TeamAllocator for assigning tasks to testers
│
├── integrations/
│   ├── redmine_adapter.py  # RedmineAdapter for REST API calls
│   ├── jira_adapter.py     # JiraAdapter for Jira/Xray
│   ├── email_adapter.py    # EmailAdapter for SMTP
│   └── integration_service.py  # IntegrationService dispatcher
│
├── reports/
│   ├── excel_generator.py  # ExcelReportGenerator (openpyxl)
│   ├── word_generator.py   # WordReportGenerator (python-docx)
│   ├── pdf_generator.py    # PDFReportGenerator (ReportLab)
│   └── templates.py        # Report styles and templates
│
└── cli/
    └── ipc_handler.py      # JSON stdin/stdout for C# subprocess
```

### Code Style

The project adheres to:
- **Formatter**: `black` (line length 88)
- **Linter**: `ruff` (strict rules)
- **Type Checker**: `mypy` (strict mode enabled)
- **Import Sorter**: Built into ruff

Run locally before committing:
```bash
black src/
ruff check src/ --fix
mypy src/
```

### Development Workflow

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make changes** and add tests (in `tests/` directory)

3. **Run tests:**
   ```bash
   pytest tests/ -v
   ```

4. **Format and lint:**
   ```bash
   black src/ tests/
   ruff check src/ tests/ --fix
   mypy src/
   ```

5. **Commit and push:**
   ```bash
   git add .
   git commit -m "Add my feature"
   git push origin feature/my-feature
   ```

6. **Create pull request** with description of changes

### Adding a New Feature

**Example: Add a new report format (HTML)**

1. Create `src/reports/html_generator.py`:
   ```python
   from .templates import ReportTemplate

   class HTMLReportGenerator:
       def __init__(self, estimation):
           self.estimation = estimation

       def generate(self) -> str:
           # Implementation here
           pass
   ```

2. Add tests in `tests/test_reports.py`:
   ```python
   def test_html_generation():
       # Test implementation
       pass
   ```

3. Update `src/api/routes.py` to add endpoint:
   ```python
   @router.get("/estimations/{estimation_id}/report/html")
   def get_html_report(estimation_id: int):
       # Route implementation
   ```

4. Run tests and commit:
   ```bash
   pytest tests/test_reports.py -v
   git add .
   git commit -m "Add HTML report generation"
   ```

---

## Testing

### Test Coverage

The project includes **152 tests** across 8 test modules, organized by functionality:

| Module | Tests | Coverage | Focus |
|--------|-------|----------|-------|
| `test_calculator.py` | ~30 | Core estimation formula | Task effort calculation with multipliers |
| `test_feasibility.py` | ~25 | Feasibility assessment | Status codes, utilization, risk flags |
| `test_calibration.py` | ~15 | Historical calibration | Improvement ratios, reference projects |
| `test_allocator.py` | ~20 | Team allocation | Task-to-tester assignments |
| `test_api.py` | ~30 | REST endpoints | HTTP requests, response validation |
| `test_phase6_api.py` | ~35 | Integration/Inbox API | Request management, status workflows |
| `test_integrations.py` | ~40 | External connectors | Redmine, Jira, Email mocking |
| `test_reports.py` | ~20 | Report generation | Excel, Word, PDF output |
| `test_models.py` | ~15 | Data models | ORM validation, constraints |

### Running Tests

**Run all tests:**
```bash
cd backend
pytest tests/ -v
```

**Run specific test module:**
```bash
pytest tests/test_calculator.py -v
```

**Run with coverage report:**
```bash
pytest tests/ --cov=src --cov-report=html
```

**Run and stop on first failure:**
```bash
pytest tests/ -x
```

**Run tests matching a pattern:**
```bash
pytest tests/ -k "feasibility" -v
```

### Test Markers

Tests are marked by functionality (not yet used, but available):

```python
@pytest.mark.unit
def test_something():
    pass

@pytest.mark.integration
def test_api_integration():
    pass
```

Run by marker:
```bash
pytest tests/ -m "not integration"  # Skip integration tests
```

### Continuous Integration

CI/CD is not yet configured. To set up:
- Add `.github/workflows/tests.yml` to run pytest on every push
- Add coverage requirements (e.g., ≥80%)
- Add code quality checks (black, ruff, mypy)

---

## Deployment

### Local Development

**Backend API:**
```bash
cd backend
uvicorn src.api.app:app --reload --port 8000
```

**Streamlit Web UI:**
```bash
cd frontend_web
streamlit run app.py
```

### Production Deployment

#### Option 1: Docker (Recommended)

Create `Dockerfile`:
```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY backend/pyproject.toml .
RUN pip install -e .

COPY backend/ .

EXPOSE 8000
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
docker build -t estimation-tool .
docker run -p 8000:8000 estimation-tool
```

#### Option 2: systemd Service (Linux/Mac)

Create `/etc/systemd/system/estimation-tool.service`:
```ini
[Unit]
Description=Test Effort Estimation Tool
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/estimation-tool/backend
ExecStart=/usr/bin/python3 -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable estimation-tool
sudo systemctl start estimation-tool
```

#### Option 3: Windows Service (WinForms Desktop App)

Package Python backend as a single executable using PyInstaller:
```bash
pyinstaller --onefile --specpath=dist backend/src/cli/ipc_handler.py
```

Then wrap in C# WinForms application that launches the .exe and communicates via JSON IPC.

---

## Troubleshooting

### Database Issues

**Problem: "File does not exist" error**
- Solution: Initialize the database manually:
  ```bash
  python -c "from src.database.migrations import init_database; init_database()"
  ```

**Problem: "Table already exists"**
- Solution: The database already has tables. If you need a fresh start:
  ```bash
  rm backend/data/estimation_tool.db
  python -c "from src.database.migrations import init_database; init_database()"
  ```

### API Connection Issues

**Problem: "Connection refused" when accessing `http://localhost:8000`**
- Solution: Ensure the backend is running:
  ```bash
  ps aux | grep uvicorn
  # or
  netstat -tulpn | grep 8000
  ```
- If not running, start it:
  ```bash
  cd backend && uvicorn src.api.app:app --reload --port 8000
  ```

**Problem: CORS errors in Streamlit frontend**
- Solution: The FastAPI app should have CORS middleware enabled. Check `src/api/app.py`:
  ```python
  from fastapi.middleware.cors import CORSMiddleware
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```

### Integration Failures

**Problem: Redmine integration test fails**
- Check credentials in Settings → Integrations → Redmine
- Ensure Redmine URL is reachable (ping the domain)
- Verify API key has sufficient permissions in Redmine

**Problem: Email not sending**
- Check SMTP server, port, and credentials
- Ensure "Less secure app access" is enabled (for Gmail)
- Check firewall/antivirus blocking SMTP port (usually 587 or 465)

### Performance Issues

**Problem: Slow estimation calculation**
- Solution: Reduce DUT × Profile combinations or simplify feature selection
- Check database for large historical projects table; archive old projects

**Problem: Report generation takes >30 seconds**
- Solution: This is normal for PDF with many pages. For faster reports, use Excel format
- Reduce DUT count or simplify estimation if possible

---

## Contributing

Contributions are welcome! Please follow these guidelines:

1. **Code Style**: Run `black`, `ruff`, and `mypy` before committing
2. **Tests**: Add tests for any new functionality
3. **Documentation**: Update README.md and docstrings as needed
4. **Commit Messages**: Use clear, descriptive messages (e.g., "Add Xray integration", "Fix utilization calculation")

For major changes, please open an issue first to discuss the approach.

---

## License

(To be determined)

---

## Support & Contact

For questions, bug reports, or feature requests, please open an issue in the repository or contact the development team.

---

**Version**: 0.1.0
**Last Updated**: February 27, 2026
**Status**: Active Development

