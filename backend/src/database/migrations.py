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
    EstimationTeamAllocation,
    Feature,
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

SCHEMA_VERSION = 7  # v7 adds task_presets, teams, test_profile.is_active, team_member.team_id, config keys


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

    # Load task templates (global templates with feature_id=None)
    for t in data.get("task_templates", []):
        feature_name = t.get("feature_name")
        feature_id = feature_map[feature_name].id if feature_name and feature_name in feature_map else None
        template = TaskTemplate(
            feature_id=feature_id,
            name=t["name"],
            task_type=t["task_type"],
            base_effort_hours=t["base_effort_hours"],
            scales_with_dut=t.get("scales_with_dut", False),
            scales_with_profile=t.get("scales_with_profile", False),
            is_parallelizable=t.get("is_parallelizable", False),
            description=t.get("description"),
        )
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
