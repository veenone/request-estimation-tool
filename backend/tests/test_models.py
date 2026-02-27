"""Unit tests for database models and migrations."""

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.database.migrations import init_database, get_engine
from src.database.models import (
    Base,
    Configuration,
    DutType,
    Estimation,
    EstimationTask,
    Feature,
    HistoricalProject,
    Request,
    TaskTemplate,
    TeamMember,
    TestProfile,
)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def session(db_path):
    init_database(db_path)
    engine = get_engine(db_path)
    with Session(engine) as s:
        yield s


class TestDatabaseInit:
    def test_tables_created(self, session: Session):
        # Verify seed data loaded
        features = session.query(Feature).all()
        assert len(features) >= 5

    def test_config_defaults(self, session: Session):
        cfg = session.query(Configuration).filter(Configuration.key == "leader_effort_ratio").first()
        assert cfg is not None
        assert cfg.value == "0.5"

    def test_task_templates_loaded(self, session: Session):
        templates = session.query(TaskTemplate).all()
        assert len(templates) >= 9

    def test_dut_types_loaded(self, session: Session):
        duts = session.query(DutType).all()
        assert len(duts) >= 3

    def test_profiles_loaded(self, session: Session):
        profiles = session.query(TestProfile).all()
        assert len(profiles) >= 3


class TestFeatureModel:
    def test_create_feature(self, session: Session):
        f = Feature(name="Test Feature", category="Test", complexity_weight=1.5)
        session.add(f)
        session.commit()
        assert f.id is not None

    def test_feature_template_relationship(self, session: Session):
        feature = session.query(Feature).first()
        # Global templates have feature_id=None, so feature-specific ones may be empty
        # Just verify the relationship loads without error
        _ = feature.task_templates


class TestEstimationModel:
    def test_create_estimation(self, session: Session):
        est = Estimation(
            project_name="Test Project",
            project_type="NEW",
            dut_count=2,
            profile_count=1,
        )
        session.add(est)
        session.commit()
        assert est.id is not None
        assert est.status == "DRAFT"

    def test_estimation_task_cascade(self, session: Session):
        est = Estimation(project_name="Cascade Test", project_type="SUPPORT")
        session.add(est)
        session.flush()

        task = EstimationTask(
            estimation_id=est.id,
            task_name="Test task",
            task_type="SETUP",
            base_hours=4,
            calculated_hours=4,
        )
        session.add(task)
        session.commit()

        assert len(est.tasks) == 1
        assert est.tasks[0].task_name == "Test task"


class TestRequestModel:
    def test_create_request(self, session: Session):
        from datetime import date
        req = Request(
            request_number="REQ-2026-001",
            title="Test Request",
            requester_name="John Doe",
            received_date=date.today(),
        )
        session.add(req)
        session.commit()
        assert req.id is not None
        assert req.status == "NEW"
        assert req.priority == "MEDIUM"
