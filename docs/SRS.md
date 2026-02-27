# Test Effort Estimation Tool — Software Requirements Specification

| Field | Value |
|---|---|
| **Document Title** | Test Effort Estimation Tool – SRS |
| **Version** | 1.1 – Draft |
| **Author** | Test Engineering Team |
| **Date** | 2026-02-26 |
| **Status** | For Review |

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Data Model](#2-data-model)
3. [Wizard Workflow](#3-wizard-workflow)
4. [Estimation Calculation Engine](#4-estimation-calculation-engine)
5. [Output Reports](#5-output-reports)
6. [User Interface Specifications](#6-user-interface-specifications)
7. [Integration Layer](#7-integration-layer)
8. [Implementation Roadmap](#8-implementation-roadmap)
9. [Appendix](#9-appendix)

---

## 1. Introduction

### 1.1 Purpose

This document defines the complete software requirements specification for a **Test Effort Estimation Tool**. The tool enables test managers to quickly and accurately estimate testing effort for new products, evolutions, and support projects by leveraging a structured intake workflow, a predefined task catalog, historical project data, and automated calculation logic.

The tool also tracks **incoming requests** from various business units and links them to estimation sessions, providing full traceability from request to delivery.

### 1.2 Scope

The tool covers the full estimation lifecycle:

- **Request intake** — capture and track incoming test requests with external references
- **Project classification** — new product, evolution, or support
- **Feature-to-task mapping** — automated task generation from feature catalog
- **Effort calculation** — multipliers for DUT, profiles, complexity, PR fixes
- **Tester and test leader allocation** — staffing plan with feasibility check
- **Report generation** — on-screen, PDF/Word, and Excel
- **Integration** — Redmine, Jira/Xray, and email notifications (Phase 2)

### 1.3 Stakeholders

| Role | Responsibility | Interaction |
|---|---|---|
| **Test Manager** | Creates estimations, assigns testers | Primary user – wizard workflow |
| **Test Leader** | Reviews estimations, supports testers | Reviews generated reports |
| **Tester** | Executes assigned tasks | Views task assignments |
| **Admin** | Maintains catalogs and config | Data management interface |
| **Requester** | Submits test requests | Receives estimation reports via email |

### 1.4 Technology Stack

| Component | Technology |
|---|---|
| **Frontend** | React (web app) or C# WinForms (desktop) |
| **Backend API** | Node.js (Express) or Python (FastAPI) |
| **Database** | SQLite (file-based, portable, no server needed) |
| **Reports** | PDF (WeasyPrint/ReportLab), Word (docx), Excel (openpyxl/ExcelJS) |
| **Integrations** | Redmine REST API, Jira/Xray REST API, SMTP email |

---

## 2. Data Model

All data is stored in a SQLite database. Below are the core entities and their schemas.

### 2.1 Entity Relationship Overview

```
requests ──────┐
               ├──▶ estimations ──▶ estimation_tasks
               │         │
features ──────┤         ├──▶ estimation_features (junction)
               │         │
task_templates ┘         ├──▶ estimation_duts (junction)
                         │
dut_types ───────────────┤
                         │
test_profiles ───────────┤
                         │
historical_projects ─────┘
                         
team_members ────────────▶ estimation_tasks (allocation)

configuration (global settings)
integration_config (external system connections)
```

### 2.2 Table: `requests`

Tracks incoming test requests from various sources. Each request may result in one or more estimations.

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | INTEGER | PK | Auto-increment primary key |
| `request_number` | TEXT | UNIQUE | External reference number (e.g., REQ-2026-001, Redmine #4521) |
| `request_source` | TEXT | | Origin system: `MANUAL`, `REDMINE`, `JIRA`, `EMAIL` |
| `external_id` | TEXT | | ID in the source system (Redmine issue ID, Jira key, etc.) |
| `title` | TEXT | NOT NULL | Request title / short description |
| `description` | TEXT | | Detailed request description |
| `requester_name` | TEXT | NOT NULL | Name of the person making the request |
| `requester_email` | TEXT | | Email for notifications and report delivery |
| `business_unit` | TEXT | | Business unit / department (e.g., "Telecom", "Banking", "IoT") |
| `priority` | TEXT | | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `status` | TEXT | | `NEW`, `IN_ESTIMATION`, `ESTIMATED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED` |
| `requested_delivery_date` | DATE | | Client's desired delivery date |
| `received_date` | DATE | NOT NULL | Date the request was received |
| `attachments_json` | TEXT | | JSON array of attachment metadata (see 2.3) |
| `notes` | TEXT | | Internal notes about the request |
| `created_at` | DATETIME | | Record creation timestamp |
| `updated_at` | DATETIME | | Last update timestamp |

### 2.3 Attachment Metadata Schema

Stored in `requests.attachments_json` as a JSON array:

```json
[
  {
    "filename": "spec_v2.pdf",
    "filepath": "attachments/REQ-2026-001/spec_v2.pdf",
    "file_size_bytes": 245760,
    "mime_type": "application/pdf",
    "uploaded_at": "2026-02-26T10:30:00Z",
    "source": "MANUAL",
    "external_url": null
  },
  {
    "filename": "test_scope.xlsx",
    "filepath": "attachments/REQ-2026-001/test_scope.xlsx",
    "file_size_bytes": 51200,
    "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "uploaded_at": "2026-02-26T10:31:00Z",
    "source": "REDMINE",
    "external_url": "https://redmine.example.com/attachments/download/1234/test_scope.xlsx"
  }
]
```

> **Storage**: Attachments are stored on disk under `data/attachments/{request_number}/`. The JSON metadata tracks filenames, sources, and optional external URLs for linked (not downloaded) files.

### 2.4 Table: `features`

Master catalog of testable features. Each feature belongs to a category and has a complexity weight.

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | INTEGER | PK | Auto-increment primary key |
| `name` | TEXT | UNIQUE | Feature name (e.g., "SIM Toolkit", "OTA Update") |
| `category` | TEXT | | Grouping category (e.g., "Telecom", "Security") |
| `complexity_weight` | REAL | | 1.0 = standard, 1.5 = complex, 2.0 = very complex |
| `has_existing_tests` | BOOLEAN | | Whether premade tests exist for this feature |
| `description` | TEXT | | Detailed description of the feature scope |
| `created_at` | DATETIME | | Record creation timestamp |

### 2.5 Table: `task_templates`

Predefined tasks linked to features. Each template stores the base effort in hours for one tester.

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | INTEGER | PK | Auto-increment primary key |
| `feature_id` | INTEGER | FK | References `features.id` |
| `name` | TEXT | | Task name (e.g., "Execute regression suite") |
| `task_type` | TEXT | | `SETUP` · `EXECUTION` · `ANALYSIS` · `REPORTING` · `STUDY` |
| `base_effort_hours` | REAL | | Base effort for 1 tester, 1 DUT, 1 profile |
| `scales_with_dut` | BOOLEAN | | If true, effort multiplied by DUT count |
| `scales_with_profile` | BOOLEAN | | If true, effort multiplied by profile count |
| `is_parallelizable` | BOOLEAN | | Can be split across multiple testers |
| `description` | TEXT | | Detailed task description |

### 2.6 Table: `dut_types`

Registry of device types with their test complexity multiplier.

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | INTEGER | PK | Auto-increment primary key |
| `name` | TEXT | UNIQUE | Device name/model |
| `category` | TEXT | | Device category (SIM, eSIM, UICC, etc.) |
| `complexity_multiplier` | REAL | | 1.0 = standard, higher = more effort per test |

### 2.7 Table: `test_profiles`

Test configuration profiles that define execution parameters.

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | INTEGER | PK | Auto-increment primary key |
| `name` | TEXT | UNIQUE | Profile name |
| `description` | TEXT | | Profile configuration details |
| `effort_multiplier` | REAL | | Multiplier applied to tasks scaling with profiles |

### 2.8 Table: `historical_projects`

Archive of past projects with actual effort data for calibration and reference.

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | INTEGER | PK | Auto-increment primary key |
| `project_name` | TEXT | | Project identifier/name |
| `project_type` | TEXT | | `NEW` · `EVOLUTION` · `SUPPORT` |
| `estimated_hours` | REAL | | Original estimated total hours |
| `actual_hours` | REAL | | Actual hours spent (post-completion) |
| `dut_count` | INTEGER | | Number of DUTs used |
| `profile_count` | INTEGER | | Number of test profiles |
| `pr_count` | INTEGER | | Number of PR fixes |
| `features_json` | TEXT | | JSON array of feature IDs tested |
| `completion_date` | DATE | | Project completion date |
| `notes` | TEXT | | Lessons learned / deviation notes |

### 2.9 Table: `estimations`

Core estimation records – one per estimation session.

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | INTEGER | PK | Auto-increment primary key |
| `request_id` | INTEGER | FK | References `requests.id` — links estimation to source request |
| `estimation_number` | TEXT | UNIQUE | Auto-generated (e.g., EST-2026-001) |
| `project_name` | TEXT | | Name of the project being estimated |
| `project_type` | TEXT | | `NEW` · `EVOLUTION` · `SUPPORT` |
| `reference_project_ids` | TEXT | | JSON array of `historical_projects.id` references |
| `dut_count` | INTEGER | | Number of DUTs |
| `profile_count` | INTEGER | | Number of test profiles |
| `dut_profile_combinations` | INTEGER | | Actual DUT × Profile combinations to test |
| `pr_fix_count` | INTEGER | | Number of PR fixes |
| `expected_delivery` | DATE | | Target delivery date |
| `total_tester_hours` | REAL | | Calculated total tester effort |
| `total_leader_hours` | REAL | | Calculated test leader effort (50% of tester) |
| `grand_total_hours` | REAL | | Sum of all effort |
| `grand_total_days` | REAL | | Grand total converted to person-days |
| `feasibility_status` | TEXT | | `FEASIBLE` · `AT_RISK` · `NOT_FEASIBLE` |
| `status` | TEXT | | `DRAFT` · `FINAL` · `APPROVED` · `REVISED` |
| `created_at` | DATETIME | | Estimation creation timestamp |
| `created_by` | TEXT | | Manager who created the estimation |
| `approved_by` | TEXT | | Manager who approved (if applicable) |
| `approved_at` | DATETIME | | Approval timestamp |

### 2.10 Table: `estimation_tasks`

Individual task breakdown within an estimation, with tester allocation.

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | INTEGER | PK | Auto-increment primary key |
| `estimation_id` | INTEGER | FK | References `estimations.id` |
| `task_template_id` | INTEGER | FK | References `task_templates.id` (NULL if custom) |
| `task_name` | TEXT | | Task name (from template or custom) |
| `task_type` | TEXT | | `SETUP` · `EXECUTION` · `ANALYSIS` · `REPORTING` · `STUDY` |
| `base_hours` | REAL | | Base effort before multipliers |
| `calculated_hours` | REAL | | Final effort after multipliers |
| `assigned_testers` | INTEGER | | Number of testers assigned |
| `has_leader_support` | BOOLEAN | | Whether test leader supports this task |
| `leader_hours` | REAL | | Test leader effort (50% of tester hours) |
| `is_new_feature_study` | BOOLEAN | | Flagged as new feature study task |
| `notes` | TEXT | | Additional notes or assumptions |

### 2.11 Table: `team_members`

Available testers and test leaders with capacity information.

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | INTEGER | PK | Auto-increment primary key |
| `name` | TEXT | | Team member name |
| `role` | TEXT | | `TESTER` · `TEST_LEADER` |
| `available_hours_per_day` | REAL | | Daily available hours (default 7) |
| `skills_json` | TEXT | | JSON array of feature IDs they are skilled in |

### 2.12 Table: `configuration`

Global configuration parameters for the estimation engine.

| Column | Type | Key | Description |
|---|---|---|---|
| `key` | TEXT | PK | Configuration key name |
| `value` | TEXT | | Configuration value |
| `description` | TEXT | | What this setting controls |

**Default configuration values:**

- `leader_effort_ratio`: `0.5` — test leader gets 50% of tester effort
- `pr_fix_base_hours`: `4.0` — average hours per PR fix for testing
- `new_feature_study_hours`: `16.0` — hours to study and create tests for a new feature
- `working_hours_per_day`: `7.0` — productive hours per working day
- `buffer_percentage`: `10` — additional percentage buffer for unknowns
- `estimation_number_prefix`: `EST` — prefix for auto-generated estimation numbers
- `request_number_prefix`: `REQ` — prefix for auto-generated request numbers

### 2.13 Table: `integration_config`

Connection settings for external systems (Redmine, Jira, Email).

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | INTEGER | PK | Auto-increment primary key |
| `system_name` | TEXT | UNIQUE | `REDMINE`, `JIRA`, `XRAY`, `EMAIL` |
| `base_url` | TEXT | | API base URL (e.g., `https://redmine.example.com`) |
| `api_key` | TEXT | | API key or token (encrypted at rest) |
| `username` | TEXT | | Username if needed |
| `additional_config_json` | TEXT | | System-specific config (project IDs, custom fields, etc.) |
| `enabled` | BOOLEAN | | Whether this integration is active |
| `last_sync_at` | DATETIME | | Last successful sync timestamp |

---

## 3. Wizard Workflow

The estimation process follows a **7-step wizard**. Each step collects specific input, and the UI dynamically adapts based on selections in previous steps.

### 3.1 Step 1: Request & Project Type

The manager either **links an existing request** or creates an inline request entry:

**If linking existing request:**
- Search/select from pending requests list
- Request details auto-populate (title, requester, business unit, delivery date)

**If creating new:**
- Enter request number (or auto-generate)
- Request title, requester name, requester email, business unit
- Upload attachments (specs, scope documents)

**Then select project type:**

| Type | Description | Next Step Behavior |
|---|---|---|
| **NEW** | Brand new product requiring full test creation | Show full feature catalog; flag all as new study tasks |
| **EVOLUTION** | Existing product with new features added | Show features from reference project + new feature selection |
| **SUPPORT** | Maintenance/fix release for existing product | Show only PR fix section + regression scope selection |

### 3.2 Step 2: Feature Selection

Conditional display based on project type:

- **NEW**: Full feature catalog displayed as checklist. All selected features are flagged as requiring new test study effort.
- **EVOLUTION**: Features from reference project pre-selected. Manager adds new features from catalog and marks which are genuinely new (requiring study). Removed features can be unchecked.
- **SUPPORT**: Feature selection is limited to the scope of regression testing. Manager selects which areas are impacted by the PR fixes.

For each selected feature, the system automatically maps to available task templates. Features without existing tests are flagged, and a "Study and Create Tests" task is auto-added.

### 3.3 Step 3: Reference Projects

The manager can link one or more historical projects for baseline comparison. The system displays:

- Previous project estimated vs. actual hours (accuracy ratio)
- Feature overlap percentage with the current project
- DUT and profile counts from the reference for comparison
- Auto-suggested adjustment factor based on historical accuracy

### 3.4 Step 4: DUT and Profile Matrix

The manager defines the test matrix:

1. Select DUT types from the registry (or add new ones)
2. Select test profiles from the catalog (or add new ones)
3. Define the DUT × Profile combination matrix — not all combinations may be needed
4. The system calculates total combinations and displays the matrix as a grid

Example: 3 DUTs × 4 profiles = 12 possible combinations, but manager might select only 8 relevant ones.

### 3.5 Step 5: PR Fixes

For all project types (but especially SUPPORT):

- Enter total number of PR fixes to be validated
- Optionally categorize by complexity: Simple (2h), Medium (4h), Complex (8h)
- System calculates total PR validation effort
- For SUPPORT projects, this is the primary effort driver alongside regression

### 3.6 Step 6: Delivery Date and Team

The manager enters the target delivery date and available team:

- Expected delivery date (calendar picker), pre-filled from request if available
- Number of available testers (or select specific team members)
- Whether a test leader is assigned (0 or 1)
- Any known constraints (holidays, partial availability)

### 3.7 Step 7: Review and Generate

The system presents a complete estimation summary with:

1. **Request details** — request number, title, requester, business unit
2. Task-by-task effort breakdown table
3. Tester allocation per task
4. Test leader overhead calculation
5. New feature study hours (flagged separately)
6. PR fix validation hours
7. Grand total in person-hours and person-days
8. Timeline feasibility check with risk flags
9. Comparison with reference project(s) if linked

The manager can adjust any values before finalizing. Once confirmed:
- Estimation is saved with status `DRAFT` or `FINAL`
- Request status updates to `ESTIMATED`
- Reports can be exported
- If email integration is enabled, report can be sent to requester

---

## 4. Estimation Calculation Engine

### 4.1 Core Formula

For each task in the estimation:

```
Task_Effort = Base_Hours × DUT_Multiplier × Profile_Multiplier × Complexity_Weight
```

Where:

- **Base_Hours**: From `task_templates.base_effort_hours`
- **DUT_Multiplier**: If `scales_with_dut` is true → number of DUTs; otherwise 1
- **Profile_Multiplier**: If `scales_with_profile` is true → number of profiles; otherwise 1
- **Complexity_Weight**: From `features.complexity_weight`

### 4.2 Aggregation

```
Total_Tester_Effort  = Σ(all task efforts)
Test_Leader_Effort   = Total_Tester_Effort × leader_effort_ratio
PR_Fix_Effort        = Σ(PR_count_by_complexity × hours_per_complexity)
New_Feature_Study    = New_Feature_Count × new_feature_study_hours
Buffer               = Subtotal × buffer_percentage / 100

GRAND TOTAL = Tester + Leader + PR_Fix + Study + Buffer
```

### 4.3 Feasibility Check

```
Available_Capacity = Working_Days × Team_Size × Hours_Per_Day
```

| Status | Condition | Action |
|---|---|---|
| **FEASIBLE** | Grand Total ≤ 80% of Capacity | Green — comfortable margin |
| **AT_RISK** | Grand Total between 80%-100% | Amber — tight schedule warning |
| **NOT_FEASIBLE** | Grand Total > 100% of Capacity | Red — suggest more team or later date |

### 4.4 Historical Calibration

When reference projects are linked:

```
Accuracy_Ratio = Actual_Hours / Estimated_Hours  (from reference projects)
```

If the average accuracy ratio across reference projects is above 1.0 (consistent underestimation), the system suggests applying the ratio as an adjustment factor and displays a warning. The manager decides whether to apply it.

### 4.5 Risk Flags

The system automatically flags these risk conditions:

- More than 50% of features are new (no existing tests) — high estimation uncertainty
- No reference projects linked — no baseline for comparison
- Delivery date is less than 2 weeks away — compressed timeline risk
- DUT × Profile combinations exceed 20 — high matrix complexity
- Historical accuracy ratio > 1.3 — team tends to significantly underestimate

---

## 5. Output Reports

### 5.1 On-Screen Summary

Displayed immediately after Step 7 of the wizard. Interactive dashboard with:

- **Request card** — request number, title, requester, business unit, priority
- Estimation overview card (project name, type, total hours, feasibility status)
- Task breakdown table (sortable, filterable by task type)
- DUT × Profile matrix heatmap showing effort distribution
- Timeline Gantt-style bar showing effort vs. available time
- Reference project comparison side panel
- Risk flags displayed as alert banners

### 5.2 PDF / Word Report

Formal estimation document suitable for sharing with stakeholders:

1. Cover page with project name, estimation ID, request number, date, and author
2. Request details section (requester, business unit, priority, description)
3. Executive summary (total effort, feasibility, key risks)
4. Project parameters table (type, DUTs, profiles, PR count, delivery date)
5. Detailed task breakdown table with all columns
6. Tester allocation summary
7. Timeline feasibility analysis
8. Reference project comparison (if linked)
9. Assumptions and risk flags

### 5.3 Excel Export

Editable spreadsheet for managers who need to fine-tune or present data:

- **Sheet 1 – Summary**: Key metrics, request details, and totals
- **Sheet 2 – Task Breakdown**: Full task list with all calculation columns, editable effort values
- **Sheet 3 – DUT-Profile Matrix**: Grid showing combinations and per-combination effort
- **Sheet 4 – Team Allocation**: Tester assignments with hours per person
- **Sheet 5 – PR Fixes**: PR breakdown by complexity
- **Sheet 6 – Reference Data**: Historical project comparison

---

## 6. User Interface Specifications

### 6.1 Screen Layout

| Screen | Description |
|---|---|
| **Dashboard** | List of all requests and estimations with status, date, total hours. Search and filter. |
| **Request Inbox** | Incoming requests list with status tracking and source indicator |
| **New Estimation** | 7-step wizard (see Section 3) |
| **Estimation Detail** | View/edit a saved estimation with all reports |
| **Feature Catalog** | CRUD for features and their linked task templates |
| **DUT Registry** | CRUD for device types and complexity multipliers |
| **Profile Manager** | CRUD for test profiles |
| **Historical Projects** | Browse/import past projects and actual effort data |
| **Team Manager** | Manage testers, leaders, and their availability |
| **Integrations** | Configure Redmine, Jira/Xray, and email connections |
| **Settings** | Global configuration parameters |

### 6.2 Wizard UX Guidelines

- Progress indicator showing current step (1–7) at the top
- Back/Next navigation with validation before proceeding
- Auto-save draft state so the wizard can be resumed
- Inline help tooltips explaining each field
- Real-time effort preview panel on the right side (updates as inputs change)
- Keyboard navigation support for power users

---

## 7. Integration Layer

### 7.1 Overview

The system supports integration with external tools via a plugin architecture. Each integration is independently configurable and can be enabled/disabled without affecting core functionality.

```
┌─────────────────────────────────────────────────┐
│              Estimation Tool Core                │
│                                                  │
│  Requests ──▶ Estimation ──▶ Reports             │
└──────┬──────────────┬───────────────┬────────────┘
       │              │               │
  ┌────▼────┐   ┌─────▼─────┐   ┌────▼────┐
  │ Redmine │   │ Jira/Xray │   │  Email  │
  │ Adapter │   │  Adapter  │   │ Adapter │
  └─────────┘   └───────────┘   └─────────┘
```

### 7.2 Redmine Integration

**Purpose**: Sync test requests from Redmine issues and push estimation results back.

| Capability | Direction | Description |
|---|---|---|
| Import requests | Redmine → Tool | Fetch issues from a configured project/tracker as new requests |
| Sync attachments | Redmine → Tool | Download issue attachments to local storage |
| Push estimation | Tool → Redmine | Update issue custom fields with effort estimate, feasibility |
| Status sync | Bidirectional | Map Redmine issue statuses to request statuses |
| Link estimation report | Tool → Redmine | Attach PDF/Word report to the Redmine issue |

**Configuration required:**
- Redmine base URL and API key
- Project ID(s) to monitor
- Tracker ID for test requests
- Custom field mappings (effort hours, feasibility status, estimation number)
- Polling interval or webhook URL

### 7.3 Jira / Xray Integration

**Purpose**: Link estimations to Jira issues and sync test plans with Xray.

| Capability | Direction | Description |
|---|---|---|
| Import requests | Jira → Tool | Fetch Jira issues (by JQL filter) as new requests |
| Push estimation | Tool → Jira | Update issue fields with effort and feasibility data |
| Create test plan | Tool → Xray | Generate Xray test plan from estimation task breakdown |
| Sync test coverage | Xray → Tool | Import existing test coverage to validate feature mapping |
| Link report | Tool → Jira | Attach estimation report to Jira issue |

**Configuration required:**
- Jira Cloud/Server base URL and API token
- JQL filter for incoming requests
- Xray project key and test plan folder
- Field mappings (effort, status, estimation number)
- Issue type for test requests

### 7.4 Email Integration

**Purpose**: Receive requests via email and send estimation reports to requesters.

| Capability | Direction | Description |
|---|---|---|
| Receive requests | Email → Tool | Parse incoming emails to create requests (subject → title, body → description, sender → requester) |
| Send estimation report | Tool → Email | Email PDF report to requester with summary |
| Notification alerts | Tool → Email | Notify managers of new requests, notify requesters of status changes |
| Attachment handling | Email → Tool | Save email attachments as request attachments |

**Configuration required:**
- SMTP server settings (host, port, TLS, credentials)
- IMAP/POP3 settings for incoming email (optional)
- Monitored mailbox address
- Email templates (configurable HTML templates for notifications)
- Sender display name and reply-to address

### 7.5 Integration Sync Architecture

```
┌──────────────────────────────────────────┐
│           Integration Service            │
│                                          │
│  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │  Poller  │  │ Webhook  │  │  IMAP  │ │
│  │ (cron)   │  │ Receiver │  │ Client │ │
│  └────┬─────┘  └────┬─────┘  └───┬────┘ │
│       │              │            │      │
│       ▼              ▼            ▼      │
│  ┌──────────────────────────────────┐    │
│  │       Sync Queue (SQLite)       │    │
│  │  - pending imports              │    │
│  │  - pending exports              │    │
│  │  - retry with backoff           │    │
│  └──────────────┬───────────────────┘    │
│                 │                        │
│       ┌─────────▼──────────┐             │
│       │  Adapter Router    │             │
│       │  (maps system →    │             │
│       │   handler)         │             │
│       └────────────────────┘             │
└──────────────────────────────────────────┘
```

- **Polling**: Configurable interval (default: every 15 minutes) checks external systems for new/updated issues
- **Webhooks**: Optional real-time push from Redmine/Jira (requires endpoint exposure)
- **Retry**: Failed syncs retry with exponential backoff (max 3 retries)
- **Audit log**: All sync operations logged with timestamps and outcomes

---

## 8. Implementation Roadmap

### Phase 1: Foundation (Weeks 1–2)

- Set up SQLite database with all tables and seed data
- Implement backend API (CRUD for all entities including requests)
- Build Feature Catalog and DUT Registry management screens
- Import existing premade test templates into `task_templates`
- Request management screen (manual input)

### Phase 2: Estimation Engine (Weeks 3–4)

- Implement the 7-step wizard UI with request linking
- Build calculation engine with all formulas
- Implement feasibility check logic
- On-screen summary report

### Phase 3: Reporting (Weeks 5–6)

- PDF/Word report generation with request details
- Excel export with formatted sheets
- Historical project import and calibration logic

### Phase 4: Polish and Deployment (Week 7)

- Team management and tester allocation
- Risk flag system
- User testing and refinement
- Deployment and documentation

### Phase 5: Integrations (Weeks 8–10)

- Email adapter (SMTP sending + optional IMAP receiving)
- Redmine adapter (REST API polling + push)
- Jira/Xray adapter (REST API + test plan generation)
- Integration configuration UI
- End-to-end sync testing

---

## 9. Appendix

### 9.1 Sample Task Templates

| Task Name | Type | Base Hrs | Scales DUT? | Scales Profile? | Parallelizable? |
|---|---|---|---|---|---|
| Environment setup | SETUP | 8 | Yes | No | No |
| Test plan review | SETUP | 4 | No | No | No |
| Execute test suite | EXECUTION | 16 | Yes | Yes | Yes |
| Regression testing | EXECUTION | 12 | Yes | Yes | Yes |
| PR fix validation | EXECUTION | 4 | Yes | No | Yes |
| Result analysis | ANALYSIS | 6 | No | No | No |
| Test report writing | REPORTING | 8 | No | No | No |
| New feature study | STUDY | 16 | No | No | No |
| Test creation | STUDY | 24 | No | No | No |

### 9.2 Estimation Worked Example

**Request**: REQ-2026-015 from Banking BU, "SIM Toolkit v2.5 certification"
**Project**: EVOLUTION, 3 DUTs, 2 Profiles, 5 PR fixes, 1 new feature, 3 testers + 1 leader, delivery in 4 weeks

| Task | Base | DUT× | Prof× | Total | Notes |
|---|---|---|---|---|---|
| Environment setup | 8h | ×3 | ×1 | 24h | Per DUT |
| Test plan review | 4h | ×1 | ×1 | 4h | Once |
| Execute test suite | 16h | ×3 | ×2 | 96h | Full matrix |
| Regression testing | 12h | ×3 | ×2 | 72h | Full matrix |
| PR fix validation | 4h×5 | ×3 | ×1 | 60h | 5 PRs × 3 DUTs |
| New feature study | 16h | ×1 | ×1 | 16h | 1 new feature |
| Test creation (new) | 24h | ×1 | ×1 | 24h | 1 new feature |
| Result analysis | 6h | ×1 | ×1 | 6h | Once |
| Test report writing | 8h | ×1 | ×1 | 8h | Once |

**Totals:**
- Total Tester Effort: **310 hours**
- Test Leader Effort: 310 × 0.5 = **155 hours**
- Buffer (10%): **46.5 hours**
- **Grand Total: 511.5 hours (73.1 person-days)**

**Feasibility:**
- Available Capacity: 20 working days × 4 people × 7 hrs = **560 hours**
- Utilization: 511.5 / 560 = **91.3% → AT_RISK**
- Recommendation: Extend delivery by 1 week or add 1 tester

### 9.3 API Endpoints Summary

| Method | Endpoint | Description |
|---|---|---|
| **GET** | `/api/requests` | List all requests with filtering |
| **POST** | `/api/requests` | Create a new request |
| **GET** | `/api/requests/:id` | Get request detail with linked estimations |
| **PUT** | `/api/requests/:id` | Update request |
| **POST** | `/api/requests/:id/attachments` | Upload attachment to request |
| **GET** | `/api/features` | List all features with task templates |
| **POST** | `/api/features` | Create a new feature |
| **GET** | `/api/dut-types` | List all DUT types |
| **GET** | `/api/profiles` | List all test profiles |
| **GET** | `/api/historical-projects` | List past projects for reference |
| **POST** | `/api/estimations` | Create new estimation (full wizard payload) |
| **GET** | `/api/estimations/:id` | Get estimation detail with tasks |
| **PUT** | `/api/estimations/:id` | Update estimation (adjust values) |
| **POST** | `/api/estimations/:id/calculate` | Recalculate effort after adjustments |
| **GET** | `/api/estimations/:id/report/pdf` | Download PDF report |
| **GET** | `/api/estimations/:id/report/docx` | Download Word report |
| **GET** | `/api/estimations/:id/report/xlsx` | Download Excel export |
| **POST** | `/api/estimations/:id/send-report` | Email report to requester |
| **GET** | `/api/team-members` | List available testers and leaders |
| **GET** | `/api/configuration` | Get global configuration values |
| **GET** | `/api/integrations` | List integration configurations |
| **PUT** | `/api/integrations/:system` | Update integration config |
| **POST** | `/api/integrations/:system/sync` | Trigger manual sync |
| **GET** | `/api/integrations/:system/status` | Check integration health |

### 9.4 Request Status Flow

```
NEW ──▶ IN_ESTIMATION ──▶ ESTIMATED ──▶ IN_PROGRESS ──▶ COMPLETED
 │                           │
 └──▶ CANCELLED              └──▶ REVISED (loops back to IN_ESTIMATION)
```

### 9.5 Estimation Status Flow

```
DRAFT ──▶ FINAL ──▶ APPROVED
              │
              └──▶ REVISED (creates new version)
```
