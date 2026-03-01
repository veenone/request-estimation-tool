"""Tests for report generation (Excel, Word, PDF)."""

import pytest

from src.reports.excel_report import ExcelReportData, generate_excel_report
from src.reports.word_report import generate_word_report
from src.reports.pdf_report import generate_pdf_report


@pytest.fixture
def sample_report_data() -> ExcelReportData:
    """Build report data matching the SPEC §9.2 worked example."""
    return ExcelReportData(
        project_name="SIM Toolkit v2.5",
        estimation_number="EST-2026-001",
        project_type="EVOLUTION",
        created_by="Test Manager",
        created_at="2026-02-26",
        request_number="REQ_26/0015",
        requester_name="Banking BU",
        business_unit="Banking",
        priority="HIGH",
        dut_count=3,
        profile_count=2,
        dut_profile_combinations=6,
        pr_fix_count=5,
        expected_delivery="2026-03-26",
        total_tester_hours=210.0,
        total_leader_hours=105.0,
        pr_fix_hours=60.0,
        study_hours=16.0,
        buffer_hours=39.1,
        grand_total_hours=430.1,
        grand_total_days=61.4,
        feasibility_status="FEASIBLE",
        capacity_hours=560.0,
        utilization_pct=76.8,
        tasks=[
            {"task_name": "Environment setup", "task_type": "SETUP", "base_hours": 8, "calculated_hours": 24, "dut_multiplier": 3, "profile_multiplier": 1, "complexity_weight": 1.0},
            {"task_name": "Test plan review", "task_type": "SETUP", "base_hours": 4, "calculated_hours": 4, "dut_multiplier": 1, "profile_multiplier": 1, "complexity_weight": 1.0},
            {"task_name": "Execute test suite", "task_type": "EXECUTION", "base_hours": 16, "calculated_hours": 96, "dut_multiplier": 3, "profile_multiplier": 2, "complexity_weight": 1.0},
            {"task_name": "Regression testing", "task_type": "EXECUTION", "base_hours": 12, "calculated_hours": 72, "dut_multiplier": 3, "profile_multiplier": 2, "complexity_weight": 1.0},
            {"task_name": "Result analysis", "task_type": "ANALYSIS", "base_hours": 6, "calculated_hours": 6, "dut_multiplier": 1, "profile_multiplier": 1, "complexity_weight": 1.0},
            {"task_name": "Test report writing", "task_type": "REPORTING", "base_hours": 8, "calculated_hours": 8, "dut_multiplier": 1, "profile_multiplier": 1, "complexity_weight": 1.0},
        ],
        dut_types=[
            {"id": 1, "name": "Standard SIM"},
            {"id": 2, "name": "USIM Card"},
            {"id": 3, "name": "eSIM Module"},
        ],
        profiles=[
            {"id": 1, "name": "Standard Profile"},
            {"id": 2, "name": "Extended Profile"},
        ],
        team_size=3,
        has_leader=True,
        pr_simple=2,
        pr_medium=2,
        pr_complex=1,
        reference_projects=[
            {
                "project_name": "SIM Toolkit v2.0",
                "project_type": "EVOLUTION",
                "estimated_hours": 400,
                "actual_hours": 450,
                "dut_count": 2,
                "profile_count": 2,
                "pr_count": 3,
            }
        ],
        risk_messages=["No compressed timeline risk detected."],
    )


class TestExcelReport:
    def test_generates_bytes(self, sample_report_data: ExcelReportData):
        result = generate_excel_report(sample_report_data)
        assert result is not None
        assert len(result) > 0
        # XLSX files start with PK (ZIP format)
        assert result[:2] == b"PK"

    def test_saves_to_file(self, sample_report_data: ExcelReportData, tmp_path):
        output = tmp_path / "test_report.xlsx"
        generate_excel_report(sample_report_data, output_path=output)
        assert output.exists()
        assert output.stat().st_size > 0


class TestWordReport:
    def test_generates_bytes(self, sample_report_data: ExcelReportData):
        result = generate_word_report(sample_report_data)
        assert result is not None
        assert len(result) > 0
        # DOCX files are also ZIP format
        assert result[:2] == b"PK"

    def test_saves_to_file(self, sample_report_data: ExcelReportData, tmp_path):
        output = tmp_path / "test_report.docx"
        generate_word_report(sample_report_data, output_path=output)
        assert output.exists()
        assert output.stat().st_size > 0


class TestPDFReport:
    def test_generates_bytes(self, sample_report_data: ExcelReportData):
        result = generate_pdf_report(sample_report_data)
        assert result is not None
        assert len(result) > 0
        # PDF files start with %PDF
        assert result[:4] == b"%PDF"

    def test_saves_to_file(self, sample_report_data: ExcelReportData, tmp_path):
        output = tmp_path / "test_report.pdf"
        generate_pdf_report(sample_report_data, output_path=output)
        assert output.exists()
        assert output.stat().st_size > 0
