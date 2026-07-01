"""Database initialization, seed data loading, and schema migrations."""

import json
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from .engine import DEFAULT_DB_PATH, get_engine as _get_engine
from .models import (
    Base,
    Configuration,
    DutType,
    EstimationRisk,
    EstimationTeamAllocation,
    Feature,
    PublicHoliday,
    RiskItem,
    TaskPreset,
    TaskTemplate,
    Team,
    TestProfile,
    WebhookNotification,
)
# Import auth models so they register with Base.metadata for create_all
from ..auth.models import AuditLog, User, UserSession  # noqa: E402

SEED_DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "seed_data.json"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

SCHEMA_VERSION = 24  # v24 adds feature_presets.description


def get_engine(db_path: Path | str | None = None):
    """Backward-compatible wrapper around engine.get_engine."""
    return _get_engine(db_path)


def _get_schema_version(session: Session) -> int:
    """Read current schema version from configuration table."""
    try:
        cfg = session.query(Configuration).filter(Configuration.key == "schema_version").first()
        return int(cfg.value) if cfg else 1
    except Exception:
        return 1


def _set_schema_version(session: Session, version: int) -> None:
    cfg = session.query(Configuration).filter(Configuration.key == "schema_version").first()
    if cfg:
        cfg.value = str(version)
    else:
        session.add(Configuration(
            key="schema_version",
            value=str(version),
            description="Database schema version",
        ))


def _table_exists(engine, table_name: str) -> bool:
    insp = inspect(engine)
    return table_name in insp.get_table_names()


def _column_exists(engine, table_name: str, column_name: str) -> bool:
    insp = inspect(engine)
    columns = [c["name"] for c in insp.get_columns(table_name)]
    return column_name in columns


def _migrate_v1_to_v2(engine, session: Session) -> None:
    """Migrate from v1 (no auth) to v2 (auth, assignment, audit)."""
    is_sqlite = engine.dialect.name == "sqlite"

    # Create new tables via ORM metadata (handles both SQLite and MySQL)
    for table_name in ("users", "user_sessions", "audit_log"):
        if not _table_exists(engine, table_name):
            table = Base.metadata.tables.get(table_name)
            if table is not None:
                table.create(engine, checkfirst=True)

    # Add new columns to estimations
    if _table_exists(engine, "estimations"):
        for col_name, col_def in [
            ("created_by_id", "INTEGER REFERENCES users(id) ON DELETE SET NULL"),
            ("approved_by_id", "INTEGER REFERENCES users(id) ON DELETE SET NULL"),
            ("assigned_to_id", "INTEGER REFERENCES users(id) ON DELETE SET NULL"),
        ]:
            if not _column_exists(engine, "estimations", col_name):
                session.execute(text(
                    f"ALTER TABLE estimations ADD COLUMN {col_name} {col_def}"
                ))

    # Add assigned_to_id to requests
    if _table_exists(engine, "requests"):
        if not _column_exists(engine, "requests", "assigned_to_id"):
            session.execute(text(
                "ALTER TABLE requests ADD COLUMN assigned_to_id INTEGER REFERENCES users(id) ON DELETE SET NULL"
            ))

    # Add auth-related config defaults
    auth_configs = {
        "jwt_secret": ("", "JWT signing secret (auto-generated on first use)"),
        "smtp_host": ("", "SMTP server hostname for notifications"),
        "smtp_port": ("587", "SMTP server port"),
        "smtp_user": ("", "SMTP username"),
        "smtp_password": ("", "SMTP password"),
        "smtp_from": ("", "SMTP sender email address"),
        "smtp_tls": ("true", "Use TLS for SMTP"),
        "ldap_url": ("", "LDAP/AD server URL"),
        "ldap_bind_dn": ("", "LDAP bind distinguished name"),
        "ldap_bind_password": ("", "LDAP bind password"),
        "ldap_search_base": ("", "LDAP search base DN"),
        "ldap_user_filter": ("(sAMAccountName={username})", "LDAP user search filter"),
        "ldap_group_mapping_json": ("{}", "JSON mapping of app roles to AD groups"),
        "oidc_issuer": ("", "OpenID Connect issuer URL"),
        "oidc_client_id": ("", "OIDC client ID"),
        "oidc_client_secret": ("", "OIDC client secret"),
        "oidc_redirect_uri": ("", "OIDC redirect URI"),
        "oidc_scopes": ("openid profile email", "OIDC scopes to request"),
        "oidc_role_claim": ("roles", "OIDC claim containing user roles"),
        "oidc_role_mapping_json": ("{}", "JSON mapping of app roles to OIDC roles"),
    }

    for key, (value, desc) in auth_configs.items():
        existing = session.query(Configuration).filter(Configuration.key == key).first()
        if not existing:
            session.add(Configuration(key=key, value=value, description=desc))

    # Update schema version
    _set_schema_version(session, 2)
    session.commit()


def _migrate_v2_to_v3(engine, session: Session) -> None:
    """Migrate from v2 to v3 (version tracking, wizard inputs, outline auto-export)."""
    if _table_exists(engine, "estimations"):
        for col_name, col_def in [
            ("version", "INTEGER NOT NULL DEFAULT 1"),
            ("wizard_inputs_json", "TEXT NOT NULL DEFAULT '{}'"),
        ]:
            if not _column_exists(engine, "estimations", col_name):
                session.execute(text(
                    f"ALTER TABLE estimations ADD COLUMN {col_name} {col_def}"
                ))

    # Add outline auto-export config key
    existing = session.query(Configuration).filter(
        Configuration.key == "outline_auto_export_states"
    ).first()
    if not existing:
        session.add(Configuration(
            key="outline_auto_export_states",
            value="",
            description="Comma-separated statuses that trigger auto-export to Outline wiki (e.g. FINAL,APPROVED)",
        ))

    # Add DUT categories config key
    existing_dut_cat = session.query(Configuration).filter(
        Configuration.key == "dut_categories"
    ).first()
    if not existing_dut_cat:
        session.add(Configuration(
            key="dut_categories",
            value="SIM,eSIM,UICC,IoT Device,Mobile Device,Other",
            description="Comma-separated list of DUT type categories for dropdown menus",
        ))

    _set_schema_version(session, 3)
    session.commit()


def _migrate_v3_to_v4(engine, session: Session) -> None:
    """Migrate from v3 to v4 (product_type, start_date, breakdown hours, estimation_id on history)."""
    # Add product_type to requests, features, dut_types, test_profiles
    for table_name in ("requests", "features", "dut_types", "test_profiles"):
        if _table_exists(engine, table_name):
            if not _column_exists(engine, table_name, "product_type"):
                session.execute(text(
                    f"ALTER TABLE {table_name} ADD COLUMN product_type VARCHAR"
                ))

    # Add new columns to estimations
    if _table_exists(engine, "estimations"):
        for col_name, col_def in [
            ("start_date", "DATE"),
            ("pr_fix_hours", "REAL DEFAULT 0"),
            ("study_hours", "REAL DEFAULT 0"),
            ("buffer_hours", "REAL DEFAULT 0"),
        ]:
            if not _column_exists(engine, "estimations", col_name):
                session.execute(text(
                    f"ALTER TABLE estimations ADD COLUMN {col_name} {col_def}"
                ))

    # Add estimation_id to historical_projects
    if _table_exists(engine, "historical_projects"):
        if not _column_exists(engine, "historical_projects", "estimation_id"):
            session.execute(text(
                "ALTER TABLE historical_projects ADD COLUMN estimation_id INTEGER REFERENCES estimations(id) ON DELETE SET NULL"
            ))

    # Add product_types config key
    existing = session.query(Configuration).filter(
        Configuration.key == "product_types"
    ).first()
    if not existing:
        session.add(Configuration(
            key="product_types",
            value='["Payment", "Telco"]',
            description="JSON array of available product types for categorization",
        ))

    # Add pr_scales_with_profile config key
    existing_pr = session.query(Configuration).filter(
        Configuration.key == "pr_scales_with_profile"
    ).first()
    if not existing_pr:
        session.add(Configuration(
            key="pr_scales_with_profile",
            value="false",
            description="Whether PR fix validation effort scales with profile count",
        ))

    _set_schema_version(session, 4)
    session.commit()


def _migrate_v4_to_v5(engine, session: Session) -> None:
    """Migrate from v4 to v5 (task_template.product_type, estimation_team_allocations, team_skills config)."""
    # Add product_type to task_templates
    if _table_exists(engine, "task_templates"):
        if not _column_exists(engine, "task_templates", "product_type"):
            session.execute(text(
                "ALTER TABLE task_templates ADD COLUMN product_type VARCHAR"
            ))

    # Create estimation_team_allocations table
    if not _table_exists(engine, "estimation_team_allocations"):
        table = Base.metadata.tables.get("estimation_team_allocations")
        if table is not None:
            table.create(engine, checkfirst=True)

    # Add team_skills config key
    existing = session.query(Configuration).filter(
        Configuration.key == "team_skills"
    ).first()
    if not existing:
        session.add(Configuration(
            key="team_skills",
            value='["Test Execution","Test Design","Automation","Performance","Security","API Testing","Mobile Testing","Regression"]',
            description="JSON array of available team member skills for selection",
        ))

    _set_schema_version(session, 5)
    session.commit()


def _migrate_v5_to_v6(engine, session: Session) -> None:
    """Migrate from v5 to v6 (webhook_notifications table, webhook_watchers config)."""
    # Create webhook_notifications table
    if not _table_exists(engine, "webhook_notifications"):
        table = Base.metadata.tables.get("webhook_notifications")
        if table is not None:
            table.create(engine, checkfirst=True)

    # Add webhook_watchers config key
    existing = session.query(Configuration).filter(
        Configuration.key == "webhook_watchers"
    ).first()
    if not existing:
        session.add(Configuration(
            key="webhook_watchers",
            value="[]",
            description="JSON array of user IDs to notify on webhook imports",
        ))

    _set_schema_version(session, 6)
    session.commit()


def _migrate_v6_to_v7(engine, session: Session) -> None:
    """Migrate from v6 to v7 (task_presets, teams, profile is_active, team_member.team_id, config keys)."""
    # Task 4: Create task_presets table
    if not _table_exists(engine, "task_presets"):
        table = Base.metadata.tables.get("task_presets")
        if table is not None:
            table.create(engine, checkfirst=True)

    # Task 7: Create teams table
    if not _table_exists(engine, "teams"):
        table = Base.metadata.tables.get("teams")
        if table is not None:
            table.create(engine, checkfirst=True)

    # Task 7: Add team_id to team_members
    if _table_exists(engine, "team_members"):
        if not _column_exists(engine, "team_members", "team_id"):
            session.execute(text(
                "ALTER TABLE team_members ADD COLUMN team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL"
            ))

    # Task 6: Add is_active to test_profiles
    if _table_exists(engine, "test_profiles"):
        if not _column_exists(engine, "test_profiles", "is_active"):
            session.execute(text(
                "ALTER TABLE test_profiles ADD COLUMN is_active BOOLEAN DEFAULT 1"
            ))

    # Task 5: Add auto_create_historical_project config key
    _ensure_key = lambda k, v, d: session.add(Configuration(key=k, value=v, description=d)) if not session.query(Configuration).filter(Configuration.key == k).first() else None
    _ensure_key(
        "auto_create_historical_project",
        "manual",
        "When to auto-create historical project from estimation: manual, on_approve, on_complete",
    )

    # Task 14: Add table header color config keys
    _ensure_key(
        "table_header_bg_light",
        "#E0E0E0",
        "Table header background color for light mode (hex)",
    )
    _ensure_key(
        "table_header_bg_dark",
        "#424242",
        "Table header background color for dark mode (hex)",
    )

    _set_schema_version(session, 7)
    session.commit()


def _migrate_v7_to_v8(engine, session: Session) -> None:
    """Migrate from v7 to v8 (expected_releases, release_extra_hours, project_goals, target_customer)."""
    if _table_exists(engine, "estimations"):
        for col_name, col_def in [
            ("expected_releases", "INTEGER DEFAULT 1"),
            ("release_extra_hours", "REAL DEFAULT 0"),
            ("project_goals", "TEXT"),
            ("target_customer", "TEXT"),
        ]:
            if not _column_exists(engine, "estimations", col_name):
                session.execute(text(
                    f"ALTER TABLE estimations ADD COLUMN {col_name} {col_def}"
                ))

    # Add release_effort_factor config key
    existing = session.query(Configuration).filter(
        Configuration.key == "release_effort_factor"
    ).first()
    if not existing:
        session.add(Configuration(
            key="release_effort_factor",
            value="0.5",
            description="Fraction of (tester + leader) hours added per additional release (0.5 = 50%)",
        ))

    _set_schema_version(session, 8)
    session.commit()


def _migrate_v8_to_v9(engine, session: Session) -> None:
    """Migrate from v8 to v9 (team_id on estimations, risk_items, estimation_risks, branding config)."""
    # Add team_id to estimations
    if _table_exists(engine, "estimations"):
        if not _column_exists(engine, "estimations", "team_id"):
            session.execute(text(
                "ALTER TABLE estimations ADD COLUMN team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL"
            ))

    # Create risk_items table
    if not _table_exists(engine, "risk_items"):
        table = Base.metadata.tables.get("risk_items")
        if table is not None:
            table.create(engine, checkfirst=True)

    # Create estimation_risks table
    if not _table_exists(engine, "estimation_risks"):
        table = Base.metadata.tables.get("estimation_risks")
        if table is not None:
            table.create(engine, checkfirst=True)

    # Add branding and color config keys
    _ensure = lambda k, v, d: session.add(Configuration(key=k, value=v, description=d)) if not session.query(Configuration).filter(Configuration.key == k).first() else None
    _ensure("logo_url", "", "URL or path to custom logo image")
    _ensure("logo_height", "40", "Logo image height in pixels")
    _ensure("sidebar_bg_light", "#FFFFFF", "Sidebar background color for light mode")
    _ensure("sidebar_bg_dark", "#1D1D1D", "Sidebar background color for dark mode")
    _ensure("content_bg_light", "#FAFAFA", "Content area background color for light mode")
    _ensure("content_bg_dark", "#121212", "Content area background color for dark mode")
    _ensure("button_color_light", "#1976D2", "Primary button color for light mode")
    _ensure("button_color_dark", "#90CAF9", "Primary button color for dark mode")

    _set_schema_version(session, 9)
    session.commit()


def _migrate_v9_to_v10(engine, session: Session) -> None:
    """Migrate from v9 to v10 (per-feature study_effort_hours)."""
    if _table_exists(engine, "features"):
        if not _column_exists(engine, "features", "study_effort_hours"):
            session.execute(text(
                "ALTER TABLE features ADD COLUMN study_effort_hours REAL"
            ))

    _set_schema_version(session, 10)
    session.commit()


def _migrate_v10_to_v11(engine, session: Session) -> None:
    """Migrate from v10 to v11 (estimation version snapshots for diff)."""
    if not _table_exists(engine, "estimation_version_snapshots"):
        session.execute(text("""
            CREATE TABLE estimation_version_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                estimation_id INTEGER NOT NULL REFERENCES estimations(id) ON DELETE CASCADE,
                version INTEGER NOT NULL,
                snapshot_json TEXT NOT NULL DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        session.execute(text(
            "CREATE INDEX ix_estimation_version_snapshots_estimation_id "
            "ON estimation_version_snapshots(estimation_id)"
        ))

    _set_schema_version(session, 11)
    session.commit()


def _migrate_v11_to_v12(engine, session: Session) -> None:
    """Migrate from v11 to v12 (document type registry)."""
    if not _table_exists(engine, "document_types"):
        session.execute(text("""
            CREATE TABLE document_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR NOT NULL UNIQUE,
                description TEXT,
                category VARCHAR NOT NULL DEFAULT 'Report',
                base_effort_hours REAL NOT NULL DEFAULT 4.0,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        # Seed some common document types
        for name, cat, hours in [
            ("Test Plan", "Planning", 8.0),
            ("Test Report", "Report", 6.0),
            ("Test Strategy", "Planning", 12.0),
            ("Test Summary Report", "Report", 4.0),
            ("Traceability Matrix", "Report", 4.0),
            ("Release Notes", "Report", 2.0),
            ("Defect Report", "Report", 3.0),
        ]:
            session.execute(text(
                "INSERT INTO document_types (name, category, base_effort_hours) VALUES (:n, :c, :h)"
            ), {"n": name, "c": cat, "h": hours})

    # Add documentation_hours column to estimations
    if not _column_exists(engine, "estimations", "documentation_hours"):
        session.execute(text("ALTER TABLE estimations ADD COLUMN documentation_hours REAL NOT NULL DEFAULT 0"))

    _set_schema_version(session, 12)
    session.commit()


def _migrate_v12_to_v13(engine, session: Session) -> None:
    """Migrate from v12 to v13 (link document types to task templates)."""
    if not _column_exists(engine, "document_types", "task_template_id"):
        session.execute(text(
            "ALTER TABLE document_types ADD COLUMN task_template_id INTEGER "
            "REFERENCES task_templates(id) ON DELETE SET NULL"
        ))

    _set_schema_version(session, 13)
    session.commit()


def _migrate_v13_to_v14(engine, session: Session) -> None:
    """Migrate from v13 to v14 (add pr_no_test_hours to estimations)."""
    if not _column_exists(engine, "estimations", "pr_no_test_hours"):
        session.execute(text(
            "ALTER TABLE estimations ADD COLUMN pr_no_test_hours REAL DEFAULT 0"
        ))

    _set_schema_version(session, 14)
    session.commit()


def _migrate_v14_to_v15(engine, session: Session) -> None:
    """Migrate from v14 to v15: project_reference, many-to-many feature↔template, feature tracking."""
    # 1. Add project_reference to estimations
    if not _column_exists(engine, "estimations", "project_reference"):
        session.execute(text(
            "ALTER TABLE estimations ADD COLUMN project_reference VARCHAR"
        ))

    # 2. Create task_template_features association table
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS task_template_features (
            task_template_id INTEGER NOT NULL REFERENCES task_templates(id) ON DELETE CASCADE,
            feature_id INTEGER NOT NULL REFERENCES features(id) ON DELETE CASCADE,
            PRIMARY KEY (task_template_id, feature_id)
        )
    """))

    # 3. Migrate existing feature_id data to the association table
    session.execute(text("""
        INSERT OR IGNORE INTO task_template_features (task_template_id, feature_id)
        SELECT id, feature_id FROM task_templates WHERE feature_id IS NOT NULL
    """))

    # 4. Add feature_id and feature_name to estimation_tasks
    if not _column_exists(engine, "estimation_tasks", "feature_id"):
        session.execute(text(
            "ALTER TABLE estimation_tasks ADD COLUMN feature_id INTEGER"
        ))
    if not _column_exists(engine, "estimation_tasks", "feature_name"):
        session.execute(text(
            "ALTER TABLE estimation_tasks ADD COLUMN feature_name VARCHAR"
        ))

    # 5. Backfill estimation_tasks.feature_name from existing relationships
    session.execute(text("""
        UPDATE estimation_tasks SET feature_name = (
            SELECT f.name FROM task_templates tt
            JOIN features f ON tt.feature_id = f.id
            WHERE tt.id = estimation_tasks.task_template_id
        ) WHERE task_template_id IS NOT NULL AND feature_name IS NULL
    """))
    session.execute(text("""
        UPDATE estimation_tasks SET feature_id = (
            SELECT tt.feature_id FROM task_templates tt
            WHERE tt.id = estimation_tasks.task_template_id
        ) WHERE task_template_id IS NOT NULL AND feature_id IS NULL
    """))

    _set_schema_version(session, 15)
    session.commit()


def _migrate_v15_to_v16(engine, session: Session) -> None:
    """Migrate from v15 to v16: add base_hours_override to task_template_features."""
    if not _column_exists(engine, "task_template_features", "base_hours_override"):
        session.execute(text(
            "ALTER TABLE task_template_features ADD COLUMN base_hours_override REAL"
        ))
    _set_schema_version(session, 16)
    session.commit()


def _migrate_v16_to_v17(engine, session: Session) -> None:
    """Migrate from v16 to v17: add is_pr_fix to task_templates, formula to estimation_tasks."""
    if not _column_exists(engine, "task_templates", "is_pr_fix"):
        session.execute(text(
            "ALTER TABLE task_templates ADD COLUMN is_pr_fix BOOLEAN NOT NULL DEFAULT 0"
        ))
    if not _column_exists(engine, "estimation_tasks", "formula"):
        session.execute(text(
            "ALTER TABLE estimation_tasks ADD COLUMN formula TEXT"
        ))
    # Auto-flag the seed "PR fix validation" template
    session.execute(text(
        "UPDATE task_templates SET is_pr_fix = 1 WHERE LOWER(name) LIKE '%pr fix%' OR LOWER(name) LIKE '%pr validation%'"
    ))
    _set_schema_version(session, 17)
    session.commit()


def _migrate_v17_to_v18(engine, session: Session) -> None:
    """Migrate from v17 to v18: add elapsed_hours/days/weeks to estimations."""
    for col in ("elapsed_hours", "elapsed_days", "elapsed_weeks"):
        if not _column_exists(engine, "estimations", col):
            session.execute(text(f"ALTER TABLE estimations ADD COLUMN {col} REAL NOT NULL DEFAULT 0"))
    _set_schema_version(session, 18)
    session.commit()


def _migrate_v18_to_v19(engine, session: Session) -> None:
    """Migrate from v18 to v19: add estimated_completion_date to estimations."""
    if not _column_exists(engine, "estimations", "estimated_completion_date"):
        session.execute(text("ALTER TABLE estimations ADD COLUMN estimated_completion_date DATE"))
    _set_schema_version(session, 19)
    session.commit()


def _migrate_v19_to_v20(engine, session: Session) -> None:
    """Replace UNIQUE(features.name) with UNIQUE(name, category).

    Allows the same feature name to exist under different categories.
    SQLite has no DROP CONSTRAINT, so we rebuild the table.
    """
    is_sqlite = engine.dialect.name == "sqlite"
    if is_sqlite:
        # Rebuild the features table with the new constraint shape.
        session.execute(text("""
            CREATE TABLE features_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR NOT NULL,
                category VARCHAR,
                complexity_weight FLOAT NOT NULL DEFAULT 1.0,
                has_existing_tests BOOLEAN NOT NULL DEFAULT 0,
                description TEXT,
                product_type VARCHAR,
                study_effort_hours FLOAT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_features_name_category UNIQUE (name, category)
            )
        """))
        session.execute(text("""
            INSERT INTO features_new (id, name, category, complexity_weight,
                has_existing_tests, description, product_type, study_effort_hours, created_at)
            SELECT id, name, category, complexity_weight,
                has_existing_tests, description, product_type, study_effort_hours, created_at
            FROM features
        """))
        session.execute(text("DROP TABLE features"))
        session.execute(text("ALTER TABLE features_new RENAME TO features"))
    else:
        # MySQL / Postgres: drop the column-level unique index then add composite.
        try:
            session.execute(text("ALTER TABLE features DROP INDEX name"))
        except Exception:
            pass
        try:
            session.execute(text(
                "ALTER TABLE features ADD CONSTRAINT uq_features_name_category UNIQUE (name, category)"
            ))
        except Exception:
            pass
    _set_schema_version(session, 20)
    session.commit()


def _migrate_v20_to_v21(engine, session: Session) -> None:
    """Add project-scoped feature support: is_global + owner_estimation_id.

    Global features keep the unique(name, category) guarantee via a partial
    index; project-scoped features (is_global=0) are exempt so they may reuse
    a global name within their owning estimation.
    """
    is_sqlite = engine.dialect.name == "sqlite"

    if is_sqlite:
        # Rebuild the table to its final shape in one step. We read the CURRENT
        # columns from the same connection (PRAGMA) rather than inspect(engine),
        # which can return a stale schema after the v19->v20 rebuild ran on this
        # connection. This makes the migration correct whether create_all already
        # added the new columns (fresh DB) or not (upgrade).
        existing = {r[1] for r in session.execute(text("PRAGMA table_info(features)")).fetchall()}
        session.execute(text("DROP TABLE IF EXISTS features_new"))
        session.execute(text("""
            CREATE TABLE features_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR NOT NULL,
                category VARCHAR,
                complexity_weight FLOAT NOT NULL DEFAULT 1.0,
                has_existing_tests BOOLEAN NOT NULL DEFAULT 0,
                description TEXT,
                product_type VARCHAR,
                study_effort_hours FLOAT,
                is_global BOOLEAN NOT NULL DEFAULT 1,
                owner_estimation_id INTEGER REFERENCES estimations(id),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        base_cols = [
            "id", "name", "category", "complexity_weight", "has_existing_tests",
            "description", "product_type", "study_effort_hours", "created_at",
        ]
        copy_cols = [c for c in base_cols if c in existing]
        ig_sel = "is_global" if "is_global" in existing else "1"
        oe_sel = "owner_estimation_id" if "owner_estimation_id" in existing else "NULL"
        col_list = ", ".join(copy_cols)
        session.execute(text(
            f"INSERT INTO features_new ({col_list}, is_global, owner_estimation_id) "
            f"SELECT {col_list}, {ig_sel}, {oe_sel} FROM features"
        ))
        session.execute(text("DROP TABLE features"))
        session.execute(text("ALTER TABLE features_new RENAME TO features"))
        # Global features keep a unique (name, category) guarantee; project
        # features (is_global=0) are exempt via the partial WHERE clause.
        session.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_features_global_name_category "
            "ON features(name, category) WHERE is_global = 1"
        ))
        session.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_features_owner_estimation_id "
            "ON features(owner_estimation_id)"
        ))
    else:
        # MySQL / other: add columns if missing, drop the table-wide unique
        # (project dupes must be allowed; global uniqueness enforced at the API).
        if not _column_exists(engine, "features", "is_global"):
            session.execute(text("ALTER TABLE features ADD COLUMN is_global BOOLEAN NOT NULL DEFAULT 1"))
        if not _column_exists(engine, "features", "owner_estimation_id"):
            session.execute(text("ALTER TABLE features ADD COLUMN owner_estimation_id INTEGER REFERENCES estimations(id)"))
        try:
            session.execute(text("ALTER TABLE features DROP INDEX uq_features_name_category"))
        except Exception:
            pass
        try:
            session.execute(text("CREATE INDEX ix_features_owner_estimation_id ON features(owner_estimation_id)"))
        except Exception:
            pass

    _set_schema_version(session, 21)
    session.commit()


def _migrate_v21_to_v22(engine, session: Session) -> None:
    """Add features.promotion_requested (estimator's request-to-global flag).

    Column existence is read from the same connection (PRAGMA on SQLite) rather
    than inspect(engine), which can be stale right after the v21 table rebuild.
    """
    if engine.dialect.name == "sqlite":
        cols = {r[1] for r in session.execute(text("PRAGMA table_info(features)")).fetchall()}
        if "promotion_requested" not in cols:
            session.execute(text(
                "ALTER TABLE features ADD COLUMN promotion_requested BOOLEAN NOT NULL DEFAULT 0"
            ))
    else:
        if not _column_exists(engine, "features", "promotion_requested"):
            session.execute(text(
                "ALTER TABLE features ADD COLUMN promotion_requested BOOLEAN NOT NULL DEFAULT 0"
            ))
    _set_schema_version(session, 22)
    session.commit()


def _migrate_v22_to_v23(engine, session: Session) -> None:
    """Add features.base_effort_hours (baseline effort for template-less features)."""
    if engine.dialect.name == "sqlite":
        cols = {r[1] for r in session.execute(text("PRAGMA table_info(features)")).fetchall()}
        if "base_effort_hours" not in cols:
            session.execute(text(
                "ALTER TABLE features ADD COLUMN base_effort_hours FLOAT NOT NULL DEFAULT 0"
            ))
    else:
        if not _column_exists(engine, "features", "base_effort_hours"):
            session.execute(text(
                "ALTER TABLE features ADD COLUMN base_effort_hours FLOAT NOT NULL DEFAULT 0"
            ))
    _set_schema_version(session, 23)
    session.commit()


def _migrate_v23_to_v24(engine, session: Session) -> None:
    """Add feature_presets.description (optional preset description)."""
    if engine.dialect.name == "sqlite":
        cols = {r[1] for r in session.execute(text("PRAGMA table_info(feature_presets)")).fetchall()}
        if cols and "description" not in cols:
            session.execute(text("ALTER TABLE feature_presets ADD COLUMN description TEXT"))
    else:
        if not _column_exists(engine, "feature_presets", "description"):
            session.execute(text("ALTER TABLE feature_presets ADD COLUMN description TEXT"))
    _set_schema_version(session, 24)
    session.commit()


def init_database(db_path: Path | str | None = None, db_url: str | None = None) -> None:
    """Create all tables, run migrations, and load seed data if empty."""
    engine = _get_engine(db_path, db_url)

    # Create all tables that don't exist yet
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        # Use raw SQL for the initial emptiness check — ORM queries reference
        # all mapped columns (including newly-added ones like product_type).
        # On existing databases those columns don't exist until migration runs,
        # but seed data must load BEFORE migrations to avoid config-key conflicts.
        feature_count = session.execute(text("SELECT count(*) FROM features")).scalar()
        if feature_count == 0:
            _load_seed_data(session)

        # Run migrations
        current_version = _get_schema_version(session)
        if current_version < 2:
            _migrate_v1_to_v2(engine, session)
        if current_version < 3:
            _migrate_v2_to_v3(engine, session)
        if current_version < 4:
            _migrate_v3_to_v4(engine, session)
        if current_version < 5:
            _migrate_v4_to_v5(engine, session)
        if current_version < 6:
            _migrate_v5_to_v6(engine, session)
        if current_version < 7:
            _migrate_v6_to_v7(engine, session)
        if current_version < 8:
            _migrate_v7_to_v8(engine, session)
        if current_version < 9:
            _migrate_v8_to_v9(engine, session)
        if current_version < 10:
            _migrate_v9_to_v10(engine, session)
        if current_version < 11:
            _migrate_v10_to_v11(engine, session)
        if current_version < 12:
            _migrate_v11_to_v12(engine, session)
        if current_version < 13:
            _migrate_v12_to_v13(engine, session)
        if current_version < 14:
            _migrate_v13_to_v14(engine, session)
        if current_version < 15:
            _migrate_v14_to_v15(engine, session)
        if current_version < 16:
            _migrate_v15_to_v16(engine, session)
        if current_version < 17:
            _migrate_v16_to_v17(engine, session)
        if current_version < 18:
            _migrate_v17_to_v18(engine, session)
        if current_version < 19:
            _migrate_v18_to_v19(engine, session)
        if current_version < 20:
            _migrate_v19_to_v20(engine, session)
        if current_version < 21:
            _migrate_v20_to_v21(engine, session)
        if current_version < 22:
            _migrate_v21_to_v22(engine, session)
        if current_version < 23:
            _migrate_v22_to_v23(engine, session)
        if current_version < 24:
            _migrate_v23_to_v24(engine, session)

        # Ensure config keys added after initial schema version exist
        _ensure_config_keys(session)

        # Ensure default admin user exists (also use raw SQL to avoid ORM issues)
        user_count = session.execute(text("SELECT count(*) FROM users")).scalar()
        if user_count == 0:
            _create_default_admin(session)

        session.commit()


def _ensure_config_keys(session: Session) -> None:
    """Ensure configuration keys exist that may have been added after initial migrations."""
    _keys = {
        "dut_categories": (
            "SIM,eSIM,UICC,IoT Device,Mobile Device,Other",
            "Comma-separated list of DUT type categories for dropdown menus",
        ),
        "pr_priority_list": (
            "LOW,MEDIUM,HIGH,CRITICAL",
            "Comma-separated PR priority levels used in PR detail entries (maps to Jira priorities)",
        ),
        "pr_hours_simple": (
            "2.0",
            "Hours per simple PR fix validation",
        ),
        "pr_hours_medium": (
            "4.0",
            "Hours per medium PR fix validation",
        ),
        "pr_hours_complex": (
            "8.0",
            "Hours per complex PR fix validation",
        ),
        "pr_no_test_hours": (
            "8.0",
            "Hours to create tests when PR has no existing test available",
        ),
        "pr_no_test_task_template_id": (
            "",
            "Task template ID linked to PR test creation effort (optional)",
        ),
        "feature_categories": (
            "Telecom,Security,Platform,Other",
            "Comma-separated list of feature categories for dropdown menus",
        ),
        "calendar_today_bg_light": (
            "#e0e0e0",
            "Calendar today cell background color (light mode)",
        ),
        "calendar_today_bg_dark": (
            "#37474f",
            "Calendar today cell background color (dark mode)",
        ),
        "calendar_weekend_bg_light": (
            "#f0f0f0",
            "Calendar weekend cell background color (light mode)",
        ),
        "calendar_weekend_bg_dark": (
            "#263238",
            "Calendar weekend cell background color (dark mode)",
        ),
        "project_types": (
            "NEW,EVOLUTION,SUPPORT,CHANGE_REQUEST",
            "Comma-separated list of project types for estimation wizard",
        ),
        "label_project_start_date": (
            "Project Start Date - T0 (optional)",
            "Wizard field label for the project start date",
        ),
        "label_testing_start_date": (
            "Testing Start Date (optional)",
            "Wizard field label for the testing start date",
        ),
        "label_deadline": (
            "Deadline (optional)",
            "Wizard field label for the delivery deadline date",
        ),
        "release_effort_factor": (
            "0.5",
            "Effort multiplier per additional release (0.0 to 1.0)",
        ),
        "release_effort_task_types": (
            "EXECUTION",
            "Comma-separated task types affected by release effort multiplier (e.g. EXECUTION,REVIEW)",
        ),
    }
    for key, (value, desc) in _keys.items():
        existing = session.query(Configuration).filter(Configuration.key == key).first()
        if not existing:
            session.add(Configuration(key=key, value=value, description=desc))
    session.flush()


def _create_default_admin(session: Session) -> None:
    """Create the default admin user with password 'admin'."""
    try:
        import bcrypt
        password_hash = bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode()
    except ImportError:
        password_hash = None

    admin = User(
        username="admin",
        display_name="Administrator",
        email="admin@localhost",
        password_hash=password_hash,
        auth_provider="local",
        role="ADMIN",
        is_active=True,
    )
    session.add(admin)
    session.flush()


def _load_seed_data(session: Session) -> None:
    """Load seed data from JSON file."""
    if not SEED_DATA_PATH.exists():
        return

    data = json.loads(SEED_DATA_PATH.read_text(encoding="utf-8"))

    # Load features
    feature_map: dict[str, Feature] = {}
    for f in data.get("features", []):
        feature = Feature(
            name=f["name"],
            category=f.get("category"),
            complexity_weight=f.get("complexity_weight", 1.0),
            has_existing_tests=f.get("has_existing_tests", False),
            description=f.get("description"),
        )
        session.add(feature)
        session.flush()
        feature_map[f["name"]] = feature

    # Load task templates (with many-to-many feature links)
    for t in data.get("task_templates", []):
        feature_name = t.get("feature_name")
        linked_feature = feature_map.get(feature_name) if feature_name else None
        template = TaskTemplate(
            feature_id=linked_feature.id if linked_feature else None,
            name=t["name"],
            task_type=t["task_type"],
            base_effort_hours=t["base_effort_hours"],
            scales_with_dut=t.get("scales_with_dut", False),
            scales_with_profile=t.get("scales_with_profile", False),
            is_parallelizable=t.get("is_parallelizable", False),
            description=t.get("description"),
        )
        if linked_feature:
            template.features = [linked_feature]
        session.add(template)

    # Load DUT types
    for d in data.get("dut_types", []):
        session.add(DutType(
            name=d["name"],
            category=d.get("category"),
            complexity_multiplier=d.get("complexity_multiplier", 1.0),
        ))

    # Load test profiles
    for p in data.get("test_profiles", []):
        session.add(TestProfile(
            name=p["name"],
            description=p.get("description"),
            effort_multiplier=p.get("effort_multiplier", 1.0),
        ))

    # Load configuration defaults
    for key, cfg in data.get("configuration", {}).items():
        session.add(Configuration(
            key=key,
            value=cfg["value"],
            description=cfg.get("description"),
        ))

    session.flush()


if __name__ == "__main__":
    init_database()
    print(f"Database initialized at {DEFAULT_DB_PATH}")
