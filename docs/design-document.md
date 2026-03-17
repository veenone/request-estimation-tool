# Test Effort Estimation Tool — Design Document

**Version:** 3.3.0
**Date:** 2026-03-17

---

## Table of Contents

- [1. Architecture Overview](#1-architecture-overview)
- [2. Component Diagram](#2-component-diagram)
- [3. Data Flow](#3-data-flow)
- [4. Estimation Workflow](#4-estimation-workflow)
- [5. Authentication Flow](#5-authentication-flow)
- [6. Calculation Engine](#6-calculation-engine)
- [7. Database Schema](#7-database-schema)
- [8. API Layer](#8-api-layer)
- [9. Frontend Architecture](#9-frontend-architecture)
- [10. Integration Architecture](#10-integration-architecture)
- [11. Report Generation](#11-report-generation)
- [12. Deployment Architecture](#12-deployment-architecture)

---

## 1. Architecture Overview

The application follows a **three-tier architecture** with strict separation between presentation, business logic, and data access layers.

```
┌─────────────────────────────────────────────────────────────┐
│                      Presentation Tier                       │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │   NiceGUI    │  │  Streamlit   │  │  C# WinForms      │  │
│  │  (Port 8502) │  │ (Port 8501)  │  │  (Desktop)        │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬──────────┘  │
│         │                 │                    │             │
│         └────────────┬────┘                    │             │
│                      │ HTTP/REST               │ JSON IPC    │
├──────────────────────┼─────────────────────────┼─────────────┤
│                      ▼                         ▼             │
│                  Business Logic Tier                          │
│  ┌───────────────────────────────────────────────────────┐   │
│  │                FastAPI Application                     │   │
│  │  ┌──────────┐  ┌───────────┐  ┌───────────────────┐  │   │
│  │  │  Routes   │  │   Auth    │  │   Integrations    │  │   │
│  │  │ (60+ EP)  │  │  (RBAC)  │  │ (5 adapters)      │  │   │
│  │  └─────┬────┘  └─────┬────┘  └───────┬───────────┘  │   │
│  │        │              │               │               │   │
│  │  ┌─────▼──────────────▼───────────────▼───────────┐  │   │
│  │  │              Engine (Pure Logic)                │  │   │
│  │  │  calculator │ feasibility │ calibration │ alloc │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  └───────────────────────┬───────────────────────────────┘   │
├──────────────────────────┼───────────────────────────────────┤
│                          ▼                                    │
│                    Data Access Tier                           │
│  ┌───────────────────────────────────────────────────────┐   │
│  │   SQLAlchemy 2.0 ORM  →  SQLite / MySQL               │   │
│  │   15 tables │ auto-migration │ seed data               │   │
│  └───────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Key design decisions:**
- The **estimation engine** (`engine/`) is kept pure — no database imports, only dataclasses and math. This enables unit testing without DB fixtures.
- All API routes live in a **single `routes.py`** file for discoverability (60+ endpoints).
- Configuration is **database-driven** (not env vars) for runtime flexibility.
- Authentication supports **three providers** (local, LDAP, OIDC) with a unified JWT session model.

---

## 2. Component Diagram

```mermaid
graph TB
    subgraph Frontends
        NG[NiceGUI SPA<br/>Python + Quasar/Vue]
        ST[Streamlit<br/>Python]
        DT[C# WinForms<br/>.NET 8 Desktop]
    end

    subgraph Backend["FastAPI Backend"]
        API[API Routes<br/>routes.py]
        AUTH[Auth Module<br/>JWT + RBAC]
        ENG[Estimation Engine<br/>Pure Logic]
        RPT[Report Generator<br/>Excel/Word/PDF]
        INT[Integration Service<br/>Adapter Pattern]
        MIG[Database Migrations<br/>Schema + Seed Data]
    end

    subgraph External["External Systems"]
        RM[Redmine]
        JR[Jira/Xray]
        SM[SMTP Email]
        OL[Outline Wiki]
        SN[Snipe-IT]
        LD[LDAP/AD]
        OI[OIDC Provider]
    end

    subgraph Data["Data Layer"]
        DB[(SQLite/MySQL<br/>15 tables)]
    end

    NG -->|HTTP/REST| API
    ST -->|HTTP/REST| API
    DT -->|JSON IPC| API

    API --> AUTH
    API --> ENG
    API --> RPT
    API --> INT
    API --> MIG

    AUTH -->|Verify| LD
    AUTH -->|Verify| OI
    AUTH --> DB

    ENG -.->|Pure dataclasses<br/>no DB dependency| ENG

    INT --> RM
    INT --> JR
    INT --> SM
    INT --> OL
    INT --> SN

    MIG --> DB
    API --> DB
    RPT --> DB
```

---

## 3. Data Flow

### 3.1 Estimation Creation Flow

```mermaid
sequenceDiagram
    actor User
    participant FE as NiceGUI Frontend
    participant API as FastAPI Routes
    participant ENG as Calculator Engine
    participant FEA as Feasibility Checker
    participant DB as Database

    User->>FE: Complete 7-step wizard
    FE->>API: POST /api/estimations/calculate (preview)
    API->>DB: Load config (buffer%, leader ratio, PR hours)
    API->>DB: Load features, task templates, DUT types, profiles
    API->>ENG: EstimationInput dataclass
    ENG->>ENG: Calculate per-task effort<br/>Base × DUT × Profile × Complexity
    ENG->>ENG: Sum tester + leader + PR + study + buffer
    ENG-->>API: EstimationResult
    API->>FEA: Check feasibility (utilization thresholds)
    FEA-->>API: FEASIBLE / AT_RISK / NOT_FEASIBLE
    API-->>FE: Preview response (totals + feasibility)
    FE-->>User: Display summary with risk flags

    User->>FE: Click "Create Estimation"
    FE->>API: POST /api/estimations
    API->>DB: Insert estimation + task rows
    API-->>FE: Created estimation with ID
    FE-->>User: Redirect to detail view
```

### 3.2 Request-to-Estimation Flow

```mermaid
sequenceDiagram
    actor Requester
    actor Estimator
    participant FE as Frontend
    participant API as FastAPI
    participant DB as Database
    participant INT as Integration Service
    participant EXT as Redmine/Jira

    alt Manual Request
        Requester->>FE: Create estimation request
        FE->>API: POST /api/requests
    else External Import
        EXT->>API: Webhook / Sync trigger
        API->>INT: Fetch issues
        INT->>EXT: GET issues via REST API
        INT-->>API: Parsed issue list
        API->>DB: Upsert requests
    end

    API->>DB: Store request (status: NEW)
    DB-->>FE: Request appears in inbox

    Estimator->>FE: Open request, start estimation
    FE->>API: POST /api/estimations (linked to request)
    API->>DB: Create estimation, update request status

    Estimator->>FE: Complete estimation
    FE->>API: POST /api/estimations/{id}/status (FINAL)
    API->>DB: Update status
    API->>INT: Auto-export to Outline (if configured)
```

---

## 4. Estimation Workflow

### 7-Step Wizard State Machine

```mermaid
stateDiagram-v2
    [*] --> Step1_Request: Start New Estimation
    Step1_Request --> Step2_Features: Select project type
    Step2_Features --> Step3_References: Choose features + complexity
    Step3_References --> Step4_Matrix: Select reference projects
    Step4_Matrix --> Step5_PRFixes: Configure DUT × Profile matrix
    Step5_PRFixes --> Step6_Delivery: Add PR fixes + test availability
    Step6_Delivery --> Step7_Review: Set date, team, leader
    Step7_Review --> Preview: Calculate preview
    Preview --> Step7_Review: Adjust parameters
    Step7_Review --> Created: Save estimation

    Created --> [*]

    note right of Step4_Matrix
        Cross-product expansion:
        N DUTs × M Profiles = N×M combinations
        Each task multiplied by all combinations
    end note

    note right of Step7_Review
        Auto-detected risk flags:
        - >50% new features
        - No reference projects
        - Timeline <2 weeks
        - >20 DUT×Profile combos
        - Historical accuracy >1.3
    end note
```

### Estimation Status Lifecycle

```mermaid
stateDiagram-v2
    [*] --> DRAFT: Create
    DRAFT --> FINAL: Submit
    FINAL --> APPROVED: Approve
    FINAL --> DRAFT: Revert to draft
    APPROVED --> REVISED: Revise (creates new version)
    REVISED --> FINAL: Submit revision
    DRAFT --> REVISED: Revise
```

---

## 5. Authentication Flow

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend
    participant API as FastAPI
    participant AUTH as AuthService
    participant LP as Local Provider
    participant LDAP as LDAP Provider
    participant OIDC as OIDC Provider
    participant DB as Database

    User->>FE: Enter username + password
    FE->>API: POST /api/auth/login

    API->>AUTH: authenticate(username, password)

    alt Local Auth
        AUTH->>LP: Verify bcrypt hash
        LP->>DB: Query users table
        LP-->>AUTH: User or None
    else LDAP Auth
        AUTH->>LDAP: Bind + search
        LDAP->>LDAP: Service bind → search user
        LDAP->>LDAP: User bind → verify password
        LDAP->>LDAP: Map AD groups → app role
        LDAP->>DB: Upsert local user (preserve role if no mapping)
        LDAP-->>AUTH: User or None
    else OIDC Auth
        AUTH->>OIDC: Token exchange
        OIDC->>OIDC: Validate ID token
        OIDC->>OIDC: Map claims → app role
        OIDC->>DB: Upsert local user (preserve role if no mapping)
        OIDC-->>AUTH: User or None
    end

    AUTH->>DB: Create session (access + refresh tokens)
    AUTH-->>API: Tokens + user info
    API-->>FE: JWT access_token + refresh_token

    Note over FE,API: All subsequent requests include<br/>Authorization: Bearer <access_token>
```

### RBAC Permission Model

```
┌──────────┬────────┬───────────┬──────────┬───────┐
│ Resource │ VIEWER │ ESTIMATOR │ APPROVER │ ADMIN │
├──────────┼────────┼───────────┼──────────┼───────┤
│ View     │   ✓    │     ✓     │    ✓     │   ✓   │
│ Create   │   ✗    │     ✓     │    ✓     │   ✓   │
│ Edit     │   ✗    │     ✓     │    ✓     │   ✓   │
│ Approve  │   ✗    │     ✗     │    ✓     │   ✓   │
│ Delete   │   ✗    │     ✗     │    ✗     │   ✓   │
│ Users    │   ✗    │     ✗     │    ✗     │   ✓   │
│ Settings │   ✗    │     ✗     │    ✗     │   ✓   │
│ Audit    │   ✗    │     ✗     │    ✗     │   ✓   │
└──────────┴────────┴───────────┴──────────┴───────┘
```

---

## 6. Calculation Engine

### Core Formula

```
Task_Effort = Base_Hours × DUT_Multiplier × Profile_Multiplier × Complexity_Weight

Tester_Total = Σ(Task_Effort for all tasks × all DUT×Profile combinations)
Leader_Total = Tester_Total × leader_effort_ratio (default 0.5)
PR_Fix_Hours = Σ(count × hours_per_complexity) for Simple/Medium/Complex
PR_NoTest_Hours = count_without_tests × pr_no_test_hours
Study_Hours = count_new_features × new_feature_study_hours
Doc_Hours = Σ(doc_type.base_hours × count) - overlap_deductions
Buffer = (Tester + Leader + PR + Study + Doc) × buffer_percentage

Grand_Total = Tester + Leader + PR + PR_NoTest + Study + Doc + Buffer
```

### Calculation Pipeline

```mermaid
graph LR
    subgraph Inputs
        FT[Features +<br/>Task Templates]
        DUT[DUT Types +<br/>Multipliers]
        PRF[Profiles +<br/>Multipliers]
        PR[PR Fixes +<br/>Complexity]
        CFG[Config<br/>Parameters]
    end

    subgraph Engine["Calculator Engine"]
        MX[Matrix<br/>Expansion]
        TC[Task Effort<br/>Calculation]
        LO[Leader<br/>Overhead]
        PH[PR Fix<br/>Hours]
        SH[Study<br/>Hours]
        DH[Doc<br/>Hours]
        BF[Buffer<br/>Calculation]
    end

    subgraph Output
        TR[Task Results<br/>Per-task breakdown]
        GT[Grand Total<br/>Hours + Days]
        FS[Feasibility<br/>Assessment]
        RF[Risk Flags<br/>Auto-detected]
    end

    FT --> MX
    DUT --> MX
    PRF --> MX
    MX --> TC
    CFG --> TC
    TC --> LO
    TC --> BF
    PR --> PH
    FT --> SH
    CFG --> DH
    LO --> GT
    PH --> GT
    SH --> GT
    DH --> GT
    BF --> GT
    TC --> TR
    GT --> FS
    GT --> RF
```

### Feasibility Assessment

```
Available_Capacity = delivery_days × team_size × working_hours_per_day
Utilization = Grand_Total / Available_Capacity × 100%

┌─────────────────┬────────────────┬────────────────────────────┐
│ Utilization      │ Status         │ Action                     │
├─────────────────┼────────────────┼────────────────────────────┤
│ ≤ 80%           │ FEASIBLE       │ Proceed as planned         │
│ 80% – 100%      │ AT_RISK        │ Consider mitigation        │
│ > 100%          │ NOT_FEASIBLE   │ Extend date or add staff   │
└─────────────────┴────────────────┴────────────────────────────┘
```

---

## 7. Database Schema

### Entity Relationship Diagram

```mermaid
erDiagram
    features ||--o{ task_templates : "has many"
    features ||--o{ feature_task_templates : "many-to-many"
    task_templates ||--o{ feature_task_templates : "many-to-many"
    estimations ||--o{ estimation_tasks : "contains"
    estimations }o--|| requests : "linked to"
    estimations }o--|| users : "assigned to"
    users ||--o{ user_sessions : "has sessions"
    users ||--o{ audit_log : "generates"
    users }o--o| team_members : "linked to"

    features {
        int id PK
        string name
        string category
        float complexity_weight
        bool has_existing_tests
    }

    task_templates {
        int id PK
        string name
        string task_type
        float base_effort_hours
        bool scales_with_dut
        bool scales_with_profile
    }

    dut_types {
        int id PK
        string name
        string category
        float complexity_multiplier
    }

    test_profiles {
        int id PK
        string name
        float effort_multiplier
    }

    estimations {
        int id PK
        string project_name
        string project_type
        int version
        string status
        float grand_total_hours
        string feasibility_status
        date start_date
        date expected_delivery
    }

    estimation_tasks {
        int id PK
        int estimation_id FK
        string task_name
        float calculated_hours
        string task_type
    }

    requests {
        int id PK
        string title
        string status
        string priority
        int estimation_id FK
    }

    users {
        int id PK
        string username
        string role
        string auth_provider
        bool is_active
        int team_member_id FK
    }

    configuration {
        int id PK
        string key UK
        string value
        string description
    }
```

### Migration Strategy

The application uses a **version-based migration** system:
1. Schema version tracked in `configuration` table (`schema_version` key)
2. `init_database()` runs on FastAPI startup via lifespan handler
3. Migrations are applied sequentially (v1 → v2 → ... → v14)
4. `_ensure_config_keys()` guarantees config entries exist even on fresh installs
5. Seed data loaded from `database/seed_data.json` on first init

---

## 8. API Layer

### Request Processing Pipeline

```mermaid
graph TD
    REQ[HTTP Request] --> CORS[CORS Middleware]
    CORS --> ACTX[Auth Context Middleware<br/>Extract client IP]
    ACTX --> ROUTE[Route Handler]

    ROUTE --> AUTH_DEP{Auth Required?}
    AUTH_DEP -->|Yes| JWT[get_current_user<br/>JWT validation]
    AUTH_DEP -->|No| HANDLER

    JWT --> ROLE{Role Check?}
    ROLE -->|Yes| RBAC[RequireRole<br/>Permission check]
    ROLE -->|No| HANDLER

    RBAC --> HANDLER[Route Handler Logic]
    HANDLER --> DB_OP[Database Operations]
    HANDLER --> ENGINE[Engine Calculations]
    HANDLER --> INTEG[Integration Calls]

    DB_OP --> RESP[JSON Response]
    ENGINE --> RESP
    INTEG --> RESP

    RESP --> AUDIT[Audit Log Entry<br/>user + action + IP]
```

### Endpoint Organization

All 60+ endpoints are in a single `routes.py` organized by resource:

```
/api/auth/*              Authentication (login, refresh, logout, me, ldap/sync)
/api/features/*          Feature catalog CRUD
/api/task-templates/*    Task template CRUD
/api/dut-types/*         DUT registry CRUD + categories
/api/profiles/*          Test profile CRUD
/api/historical-projects/* Historical project management
/api/team-members/*      Team roster CRUD
/api/estimations/*       Estimation CRUD + calculate + revise + reports
/api/requests/*          Request inbox CRUD
/api/configuration/*     Key-value settings
/api/integrations/*      External system config + test + sync
/api/users/*             User management (ADMIN)
/api/audit-log           Audit log viewer (ADMIN)
/api/dashboard/stats     Dashboard statistics
/api/public-holidays/*   Holiday calendar CRUD
/api/working-weeks       Working weeks calculator
/api/webhooks/redmine    Redmine webhook receiver
```

---

## 9. Frontend Architecture

### NiceGUI SPA Architecture

```mermaid
graph TB
    subgraph Browser["Browser (Quasar/Vue)"]
        WS[WebSocket Connection]
        QC[Quasar Components]
        EC[ECharts Widgets]
    end

    subgraph NiceGUI["NiceGUI Server (Python)"]
        APP[app.py<br/>Entry + Dashboard + Auth]
        subgraph Pages
            P1[estimation.py]
            P2[features.py]
            P3[duts.py]
            P4[users.py]
            P5[settings.py]
            P6[... 12 more pages]
        end

        SB[Sidebar Navigation]
        AH[Auth Helpers<br/>api_get/post/put/delete]
        ERR[Error Pages<br/>400/401/403/422/504]
    end

    subgraph Backend["FastAPI Backend"]
        API[REST API<br/>Port 8000]
    end

    WS <-->|Real-time updates| APP
    APP --> Pages
    APP --> SB
    APP --> AH
    APP --> ERR
    AH -->|HTTP + Bearer token<br/>+ X-Forwarded-For| API

    style Browser fill:#1a1a2e
    style NiceGUI fill:#16213e
    style Backend fill:#0f3460
```

### Page Structure Pattern

Each NiceGUI page follows a consistent pattern:

```python
@ui.page("/page-name")
async def page_name() -> None:
    # 1. Auth guard
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    # 2. Sidebar
    sidebar()

    # 3. Load data
    data = await api_get("/endpoint")

    # 4. Table with columns, slots, and pagination
    table = ui.table(columns=..., rows=data, pagination={"rowsPerPage": 15})

    # 5. Custom slots for badges, actions
    table.add_slot("body-cell-status", "<q-badge .../>")
    table.add_slot("body-cell-actions", "<q-btn @click='() => $parent.$emit(...)' />")

    # 6. Event handlers → dialog CRUD
    table.on("edit", lambda e: open_edit_dialog(e.args))
```

---

## 10. Integration Architecture

### Adapter Pattern

```mermaid
classDiagram
    class BaseAdapter {
        <<abstract>>
        +test_connection() bool
        +sync_data() dict
    }

    class RedmineAdapter {
        +test_connection() bool
        +sync_data() dict
        +push_estimation() dict
        +upload_report() dict
    }

    class JiraAdapter {
        +test_connection() bool
        +sync_data() dict
        +import_issues() list
    }

    class EmailAdapter {
        +test_connection() bool
        +send_report() bool
    }

    class OutlineAdapter {
        +test_connection() bool
        +publish_estimation() dict
    }

    class SnipeITAdapter {
        +test_connection() bool
        +sync_assets() dict
    }

    class IntegrationService {
        +get_adapter(system) BaseAdapter
        +test(system) dict
        +sync(system) dict
    }

    BaseAdapter <|-- RedmineAdapter
    BaseAdapter <|-- JiraAdapter
    BaseAdapter <|-- EmailAdapter
    BaseAdapter <|-- OutlineAdapter
    BaseAdapter <|-- SnipeITAdapter
    IntegrationService --> BaseAdapter
```

### Integration Data Flow

```
┌──────────────────┐     ┌──────────────────┐     ┌────────────────┐
│  External System  │────▶│ Integration      │────▶│   Database     │
│  (Redmine/Jira)  │     │ Adapter          │     │  (requests)    │
└──────────────────┘     └──────────────────┘     └────────────────┘
        ▲                         │
        │                         │ Sync results
        │                         ▼
        │                 ┌──────────────────┐
        └─────────────────│ Push estimation  │
          Export results  │ results back     │
                          └──────────────────┘
```

---

## 11. Report Generation

### Report Pipeline

```mermaid
graph LR
    EST[Estimation<br/>Record] --> LOAD[Load Full Data<br/>Tasks, Team, DUTs,<br/>PRs, Docs, Risks]

    LOAD --> EXCEL[Excel Generator<br/>openpyxl]
    LOAD --> WORD[Word Generator<br/>python-docx]
    LOAD --> PDF[PDF Generator<br/>ReportLab]

    EXCEL --> XLS[".xlsx<br/>6 sheets:<br/>Summary, Tasks,<br/>Matrix, Team,<br/>PR Fixes, References"]

    WORD --> DOC[".docx<br/>Cover page,<br/>Executive summary,<br/>Tables, Sign-off,<br/>Doc deliverables"]

    PDF --> PDFF[".pdf<br/>Color-coded feasibility,<br/>Summary tables,<br/>Risk callouts,<br/>Working weeks"]
```

### Report Contents

| Section | Excel | Word | PDF |
|---------|-------|------|-----|
| Project Summary | Sheet 1 | Page 1-2 | Page 1 |
| Task Breakdown | Sheet 2 | Table | Table |
| DUT × Profile Matrix | Sheet 3 | Table | Table |
| Team Allocation | Sheet 4 | Table | Table |
| PR Fixes (with test_available) | Sheet 5 | Table | Table |
| Document Deliverables | In Summary | Section | Section |
| Feasibility Assessment | In Summary | Callout | Color-coded |
| Risk Flags | In Summary | Bullet list | Callout box |
| Working Weeks | In Summary | Footer | Footer |
| References | Sheet 6 | Table | Table |

---

## 12. Deployment Architecture

### Docker Deployment

```mermaid
graph TB
    subgraph Docker["Docker Container"]
        subgraph Services
            UV[Uvicorn<br/>FastAPI Backend<br/>Port 8000]
            NG[NiceGUI Frontend<br/>Port 8502]
        end

        subgraph Volumes
            DB[(data/<br/>estimation.db)]
            UL[data/uploads/<br/>logos, files]
        end

        UV --> DB
        NG -->|HTTP| UV
    end

    subgraph Host
        NGINX[Nginx Reverse Proxy<br/>Port 80/443]
    end

    BROWSER[Browser] --> NGINX
    NGINX -->|proxy_pass| NG
    NGINX -->|proxy_pass /api| UV

    style Docker fill:#1a1a2e
    style Host fill:#16213e
```

### Environment Configuration

```
┌─────────────────────┬──────────────────────────────────────┐
│ Environment         │ Configuration                        │
├─────────────────────┼──────────────────────────────────────┤
│ Development         │ SQLite, no auth, debug mode          │
│ Docker (default)    │ SQLite, JWT auth, single container   │
│ Docker (MySQL)      │ MySQL, JWT auth, --profile mysql     │
│ Production          │ MySQL, LDAP/OIDC, TLS, nginx proxy  │
└─────────────────────┴──────────────────────────────────────┘
```

### Startup Sequence

```mermaid
sequenceDiagram
    participant D as Docker / Shell
    participant UV as Uvicorn
    participant FA as FastAPI Lifespan
    participant MIG as Migrations
    participant DB as Database
    participant SCH as Sync Scheduler

    D->>UV: Start server
    UV->>FA: Trigger lifespan startup
    FA->>MIG: init_database()
    MIG->>DB: Check schema version
    MIG->>DB: Apply pending migrations
    MIG->>DB: _ensure_config_keys()
    MIG->>DB: Load seed data (if fresh)
    MIG-->>FA: Database ready
    FA->>SCH: start_scheduler() (optional)
    SCH-->>FA: Scheduler running
    FA-->>UV: App ready
    UV-->>D: Listening on port 8000
```
