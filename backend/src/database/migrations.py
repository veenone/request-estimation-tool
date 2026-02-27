"""Database initialization and seed data loading."""

import json
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from .models import (
    Base,
    Configuration,
    DutType,
    Feature,
    TaskTemplate,
    TestProfile,
)

DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "estimation.db"
SEED_DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "seed_data.json"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_engine(db_path: Path | str | None = None):
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", echo=False)


def init_database(db_path: Path | str | None = None) -> None:
    """Create all tables and load seed data if the database is empty."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        # Enable WAL mode and foreign keys
        session.execute(text("PRAGMA journal_mode = WAL"))
        session.execute(text("PRAGMA foreign_keys = ON"))

        # Only seed if features table is empty
        feature_count = session.query(Feature).count()
        if feature_count == 0:
            _load_seed_data(session)
        session.commit()


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
