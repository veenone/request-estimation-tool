"""Import service for bulk data operations.

Provides two entry points:

- :func:`preview_import` — parse and validate a file without persisting
  anything; safe to call repeatedly for a dry-run preview.
- :func:`execute_import` — parse the file and insert valid rows into the
  database, with optional duplicate skipping.
"""

from sqlalchemy.orm import Session

from ..database.models import DutType, Feature, HistoricalProject, TaskTemplate, TestProfile
from .csv_importer import parse_csv, parse_excel

# ---------------------------------------------------------------------------
# Configuration tables
# ---------------------------------------------------------------------------

# Maps entity type strings to SQLAlchemy model classes.
MODEL_MAP: dict[str, type] = {
    "features": Feature,
    "dut_types": DutType,
    "test_profiles": TestProfile,
    "task_templates": TaskTemplate,
    "historical_projects": HistoricalProject,
}

# The attribute name that defines uniqueness for duplicate detection.
# ``None`` means no uniqueness check is performed for that entity type.
UNIQUE_FIELDS: dict[str, str | None] = {
    "features": "name",
    "dut_types": "name",
    "test_profiles": "name",
    "task_templates": None,
    "historical_projects": None,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def preview_import(content: bytes, entity_type: str, filename: str) -> dict:
    """Parse and validate *content* without writing to the database.

    The file format is inferred from *filename*: files ending in ``.xlsx``
    are treated as Excel workbooks; everything else is treated as CSV.

    Args:
        content:     Raw file bytes.
        entity_type: Entity type key (e.g. ``"features"``, ``"dut_types"``).
        filename:    Original filename, used to detect the file format.

    Returns:
        A result dict with keys:

        - ``rows``         – list of validated, type-coerced record dicts
        - ``errors``       – list of human-readable error strings
        - ``total_parsed`` – number of data rows read from the file
        - ``valid_count``  – number of rows that passed all validation
    """
    if filename.lower().endswith(".xlsx"):
        return parse_excel(content, entity_type)
    return parse_csv(content, entity_type)


def execute_import(
    content: bytes,
    entity_type: str,
    filename: str,
    session: Session,
    skip_duplicates: bool = True,
) -> dict:
    """Parse *content* and insert valid rows into the database.

    Each valid row is inserted individually so that a single bad record does
    not block the rest of the batch.  The session is committed once at the
    end when at least one row was imported successfully.

    Duplicate detection is performed before insertion: when *skip_duplicates*
    is ``True`` and a unique field is defined for the entity type, any row
    whose unique-field value already exists in the database is counted as
    ``skipped`` rather than inserted.

    Args:
        content:         Raw file bytes.
        entity_type:     Entity type key (e.g. ``"features"``).
        filename:        Original filename, used to detect the file format.
        session:         Active SQLAlchemy session.
        skip_duplicates: When ``True``, silently skip rows whose unique-field
                         value already exists in the database.

    Returns:
        A result dict with keys:

        - ``imported``     – number of rows successfully inserted
        - ``skipped``      – number of rows skipped (duplicates)
        - ``errors``       – list of human-readable error strings (includes
                             both parse errors and DB insert errors)
        - ``total_parsed`` – total data rows read from the file
    """
    parsed = preview_import(content, entity_type, filename)

    result: dict = {
        "imported": 0,
        "skipped": 0,
        "errors": list(parsed["errors"]),
        "total_parsed": parsed["total_parsed"],
    }

    model_class = MODEL_MAP.get(entity_type)
    if not model_class:
        result["errors"].append(f"Unknown entity type: {entity_type}")
        return result

    unique_field = UNIQUE_FIELDS.get(entity_type)

    for row in parsed["rows"]:
        # ------------------------------------------------------------------
        # Duplicate check
        # ------------------------------------------------------------------
        if skip_duplicates and unique_field and row.get(unique_field):
            existing = (
                session.query(model_class)
                .filter(getattr(model_class, unique_field) == row[unique_field])
                .first()
            )
            if existing:
                result["skipped"] += 1
                continue

        # ------------------------------------------------------------------
        # Insert
        # ------------------------------------------------------------------
        try:
            obj = model_class(**row)
            session.add(obj)
            session.flush()  # raise DB errors early while still recoverable
            result["imported"] += 1
        except Exception as exc:
            result["errors"].append(f"Insert failed for {row}: {exc}")
            session.rollback()

    if result["imported"] > 0:
        session.commit()

    return result
