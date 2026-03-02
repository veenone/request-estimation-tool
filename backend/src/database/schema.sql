-- Test Effort Estimation Tool - Database Schema
-- SQLite database schema based on SRS v1.1

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ============================================================
-- Table: requests
-- Tracks incoming test requests from various sources
-- ============================================================
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_number TEXT UNIQUE NOT NULL,
    request_source TEXT NOT NULL DEFAULT 'MANUAL'
        CHECK (request_source IN ('MANUAL', 'REDMINE', 'JIRA', 'EMAIL')),
    external_id TEXT,
    title TEXT NOT NULL,
    description TEXT,
    requester_name TEXT NOT NULL,
    requester_email TEXT,
    business_unit TEXT,
    priority TEXT DEFAULT 'MEDIUM'
        CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    status TEXT DEFAULT 'NEW'
        CHECK (status IN ('NEW', 'IN_ESTIMATION', 'ESTIMATED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')),
    requested_delivery_date DATE,
    received_date DATE NOT NULL,
    attachments_json TEXT DEFAULT '[]',
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- Table: features
-- Master catalog of testable features
-- ============================================================
CREATE TABLE IF NOT EXISTS features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    category TEXT,
    complexity_weight REAL NOT NULL DEFAULT 1.0,
    has_existing_tests BOOLEAN NOT NULL DEFAULT 0,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- Table: task_templates
-- Predefined tasks linked to features
-- ============================================================
CREATE TABLE IF NOT EXISTS task_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feature_id INTEGER,
    name TEXT NOT NULL,
    task_type TEXT NOT NULL
        CHECK (task_type IN ('SETUP', 'EXECUTION', 'ANALYSIS', 'REPORTING', 'STUDY')),
    base_effort_hours REAL NOT NULL,
    scales_with_dut BOOLEAN NOT NULL DEFAULT 0,
    scales_with_profile BOOLEAN NOT NULL DEFAULT 0,
    is_parallelizable BOOLEAN NOT NULL DEFAULT 0,
    description TEXT,
    FOREIGN KEY (feature_id) REFERENCES features(id) ON DELETE CASCADE
);

-- ============================================================
-- Table: dut_types
-- Registry of device types with complexity multipliers
-- ============================================================
CREATE TABLE IF NOT EXISTS dut_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    category TEXT,
    complexity_multiplier REAL NOT NULL DEFAULT 1.0
);

-- ============================================================
-- Table: test_profiles
-- Test configuration profiles
-- ============================================================
CREATE TABLE IF NOT EXISTS test_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    effort_multiplier REAL NOT NULL DEFAULT 1.0
);

-- ============================================================
-- Table: historical_projects
-- Past projects with actual effort data for calibration
-- ============================================================
CREATE TABLE IF NOT EXISTS historical_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL,
    project_type TEXT NOT NULL
        CHECK (project_type IN ('NEW', 'EVOLUTION', 'SUPPORT')),
    estimated_hours REAL,
    actual_hours REAL,
    dut_count INTEGER,
    profile_count INTEGER,
    pr_count INTEGER,
    features_json TEXT DEFAULT '[]',
    completion_date DATE,
    notes TEXT
);

-- ============================================================
-- Table: estimations
-- Core estimation records
-- ============================================================
CREATE TABLE IF NOT EXISTS estimations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER,
    estimation_number TEXT UNIQUE,
    project_name TEXT NOT NULL,
    project_type TEXT NOT NULL
        CHECK (project_type IN ('NEW', 'EVOLUTION', 'SUPPORT')),
    reference_project_ids TEXT DEFAULT '[]',
    dut_count INTEGER NOT NULL DEFAULT 0,
    profile_count INTEGER NOT NULL DEFAULT 0,
    dut_profile_combinations INTEGER NOT NULL DEFAULT 0,
    pr_fix_count INTEGER NOT NULL DEFAULT 0,
    expected_delivery DATE,
    total_tester_hours REAL DEFAULT 0,
    total_leader_hours REAL DEFAULT 0,
    grand_total_hours REAL DEFAULT 0,
    grand_total_days REAL DEFAULT 0,
    feasibility_status TEXT DEFAULT 'FEASIBLE'
        CHECK (feasibility_status IN ('FEASIBLE', 'AT_RISK', 'NOT_FEASIBLE')),
    status TEXT DEFAULT 'DRAFT'
        CHECK (status IN ('DRAFT', 'FINAL', 'APPROVED', 'REVISED')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    approved_by TEXT,
    approved_at DATETIME,
    version INTEGER NOT NULL DEFAULT 1,
    wizard_inputs_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE SET NULL
);

-- ============================================================
-- Table: estimation_tasks
-- Individual task breakdown within an estimation
-- ============================================================
CREATE TABLE IF NOT EXISTS estimation_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estimation_id INTEGER NOT NULL,
    task_template_id INTEGER,
    task_name TEXT NOT NULL,
    task_type TEXT NOT NULL
        CHECK (task_type IN ('SETUP', 'EXECUTION', 'ANALYSIS', 'REPORTING', 'STUDY')),
    base_hours REAL NOT NULL DEFAULT 0,
    calculated_hours REAL NOT NULL DEFAULT 0,
    assigned_testers INTEGER DEFAULT 1,
    has_leader_support BOOLEAN DEFAULT 0,
    leader_hours REAL DEFAULT 0,
    is_new_feature_study BOOLEAN DEFAULT 0,
    notes TEXT,
    FOREIGN KEY (estimation_id) REFERENCES estimations(id) ON DELETE CASCADE,
    FOREIGN KEY (task_template_id) REFERENCES task_templates(id) ON DELETE SET NULL
);

-- ============================================================
-- Table: team_members
-- Available testers and test leaders
-- ============================================================
CREATE TABLE IF NOT EXISTS team_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    role TEXT NOT NULL
        CHECK (role IN ('TESTER', 'TEST_LEADER')),
    available_hours_per_day REAL NOT NULL DEFAULT 7.0,
    skills_json TEXT DEFAULT '[]'
);

-- ============================================================
-- Table: configuration
-- Global configuration parameters
-- ============================================================
CREATE TABLE IF NOT EXISTS configuration (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT
);

-- ============================================================
-- Table: integration_config
-- Connection settings for external systems
-- ============================================================
CREATE TABLE IF NOT EXISTS integration_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    system_name TEXT UNIQUE NOT NULL
        CHECK (system_name IN ('REDMINE', 'JIRA', 'XRAY', 'EMAIL')),
    base_url TEXT,
    api_key TEXT,
    username TEXT,
    additional_config_json TEXT DEFAULT '{}',
    enabled BOOLEAN NOT NULL DEFAULT 0,
    last_sync_at DATETIME
);

-- ============================================================
-- Table: users
-- Authentication accounts (v2.0)
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT,
    auth_provider TEXT NOT NULL DEFAULT 'local'
        CHECK (auth_provider IN ('local', 'ldap', 'oidc')),
    external_id TEXT,
    role TEXT NOT NULL DEFAULT 'VIEWER'
        CHECK (role IN ('VIEWER', 'ESTIMATOR', 'APPROVER', 'ADMIN')),
    is_active INTEGER NOT NULL DEFAULT 1,
    team_member_id INTEGER,
    last_login_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (team_member_id) REFERENCES team_members(id)
);

-- ============================================================
-- Table: user_sessions
-- JWT refresh token storage (v2.0)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    refresh_token TEXT NOT NULL UNIQUE,
    expires_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ============================================================
-- Table: audit_log
-- Activity tracking (v2.0)
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id INTEGER,
    details_json TEXT DEFAULT '{}',
    ip_address TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ============================================================
-- Indexes for performance
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
CREATE INDEX IF NOT EXISTS idx_requests_request_number ON requests(request_number);
CREATE INDEX IF NOT EXISTS idx_features_category ON features(category);
CREATE INDEX IF NOT EXISTS idx_task_templates_feature ON task_templates(feature_id);
CREATE INDEX IF NOT EXISTS idx_task_templates_type ON task_templates(task_type);
CREATE INDEX IF NOT EXISTS idx_estimations_request ON estimations(request_id);
CREATE INDEX IF NOT EXISTS idx_estimations_status ON estimations(status);
CREATE INDEX IF NOT EXISTS idx_estimation_tasks_estimation ON estimation_tasks(estimation_id);
CREATE INDEX IF NOT EXISTS idx_historical_projects_type ON historical_projects(project_type);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions(refresh_token);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_estimations_assigned ON estimations(assigned_to_id);
CREATE INDEX IF NOT EXISTS idx_requests_assigned ON requests(assigned_to_id);

-- ============================================================
-- Default configuration values
-- ============================================================
INSERT OR IGNORE INTO configuration (key, value, description) VALUES
    ('leader_effort_ratio', '0.5', 'Test leader gets this fraction of total tester effort'),
    ('pr_fix_base_hours', '4.0', 'Average hours per PR fix for testing'),
    ('new_feature_study_hours', '16.0', 'Hours to study and create tests for a new feature'),
    ('working_hours_per_day', '7.0', 'Productive hours per working day'),
    ('buffer_percentage', '10', 'Additional percentage buffer for unknowns'),
    ('estimation_number_prefix', 'EST', 'Prefix for auto-generated estimation numbers');
