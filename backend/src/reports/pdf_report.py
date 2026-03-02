"""PDF report generation with ReportLab.

Generates a formal estimation PDF matching the Word report structure per SPEC §5.2.
"""

from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .excel_report import ExcelReportData

# ── Colors ───────────────────────────────────────────────

BLUE = colors.HexColor("#2F5496")
LIGHT_BLUE = colors.HexColor("#D9E2F3")
GREEN = colors.HexColor("#C6EFCE")
AMBER = colors.HexColor("#FFEB9C")
RED = colors.HexColor("#FFC7CE")
DARK_GRAY = colors.HexColor("#404040")
LIGHT_GRAY = colors.HexColor("#F2F2F2")


def _feasibility_color(status: str) -> colors.Color:
    if status == "FEASIBLE":
        return GREEN
    elif status == "AT_RISK":
        return AMBER
    return RED


def _make_styles() -> dict:
    styles = getSampleStyleSheet()
    custom = {}

    custom["CoverTitle"] = ParagraphStyle(
        "CoverTitle", parent=styles["Title"],
        fontSize=28, textColor=BLUE, alignment=1, spaceAfter=20,
    )
    custom["CoverSubtitle"] = ParagraphStyle(
        "CoverSubtitle", parent=styles["Normal"],
        fontSize=16, textColor=DARK_GRAY, alignment=1, spaceAfter=8,
    )
    custom["CoverMeta"] = ParagraphStyle(
        "CoverMeta", parent=styles["Normal"],
        fontSize=11, textColor=colors.HexColor("#606060"), alignment=1, spaceAfter=4,
    )
    custom["SectionTitle"] = ParagraphStyle(
        "SectionTitle", parent=styles["Heading1"],
        fontSize=16, textColor=BLUE, spaceBefore=16, spaceAfter=8,
    )
    custom["SubSection"] = ParagraphStyle(
        "SubSection", parent=styles["Heading2"],
        fontSize=12, textColor=BLUE, spaceBefore=10, spaceAfter=6,
    )
    custom["Body"] = ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontSize=10, spaceAfter=6, leading=14,
    )
    custom["BoldBody"] = ParagraphStyle(
        "BoldBody", parent=styles["Normal"],
        fontSize=10, spaceAfter=6, leading=14, fontName="Helvetica-Bold",
    )
    custom["RiskItem"] = ParagraphStyle(
        "RiskItem", parent=styles["Normal"],
        fontSize=10, spaceAfter=4, leftIndent=20, bulletIndent=10,
    )
    return custom


def _make_table(headers: list[str], rows: list[list[str]], col_widths: list[float] | None = None) -> Table:
    data = [headers] + rows
    table = Table(data, colWidths=col_widths, repeatRows=1)

    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]

    table.setStyle(TableStyle(style_commands))
    return table


def generate_pdf_report(data: ExcelReportData, output_path: str | Path | None = None) -> bytes | None:
    """Generate a PDF report.

    Args:
        data: ExcelReportData with all estimation information.
        output_path: If provided, saves to file. If None, returns bytes.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer if output_path is None else str(output_path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = _make_styles()
    story: list = []
    page_width = A4[0] - 40 * mm

    # ── 1. Cover page ──────────────────────────────────
    story.append(Spacer(1, 80))
    story.append(Paragraph("Test Effort Estimation Report", styles["CoverTitle"]))
    story.append(Spacer(1, 20))
    story.append(Paragraph(data.project_name, styles["CoverSubtitle"]))
    story.append(Spacer(1, 30))

    meta_lines = [
        f"Estimation: {data.estimation_number}",
        f"Project Type: {data.project_type}",
    ]
    if data.request_number:
        meta_lines.append(f"Request: {data.request_number}")
    meta_lines.extend([
        f"Author: {data.created_by}",
        f"Date: {data.created_at}",
    ])
    for line in meta_lines:
        story.append(Paragraph(line, styles["CoverMeta"]))

    story.append(PageBreak())

    # ── 2. Request details ─────────────────────────────
    if data.request_number:
        story.append(Paragraph("Request Details", styles["SectionTitle"]))
        story.append(_make_table(
            ["Field", "Value"],
            [
                ["Request Number", data.request_number],
                ["Requester", data.requester_name],
                ["Business Unit", data.business_unit],
                ["Priority", data.priority],
                ["Requested Delivery", data.expected_delivery],
            ],
            col_widths=[page_width * 0.35, page_width * 0.65],
        ))
        story.append(Spacer(1, 12))

    # ── 3. Executive summary ───────────────────────────
    story.append(Paragraph("Executive Summary", styles["SectionTitle"]))
    summary_text = (
        f"This estimation covers the <b>{data.project_type}</b> project "
        f'"{data.project_name}" with {data.dut_count} DUT(s), '
        f"{data.profile_count} test profile(s), and {data.pr_fix_count} PR fix(es)."
    )
    story.append(Paragraph(summary_text, styles["Body"]))
    story.append(Spacer(1, 6))

    story.append(_make_table(
        ["Metric", "Value"],
        [
            ["Grand Total (Hours)", f"{data.grand_total_hours:.1f}"],
            ["Grand Total (Person-Days)", f"{data.grand_total_days:.1f}"],
            ["Capacity (Hours)", f"{data.capacity_hours:.1f}"],
            ["Utilization", f"{data.utilization_pct:.1f}%"],
            ["Feasibility", data.feasibility_status],
        ],
        col_widths=[page_width * 0.45, page_width * 0.55],
    ))
    story.append(Spacer(1, 12))

    # ── 4. Project parameters ──────────────────────────
    story.append(Paragraph("Project Parameters", styles["SectionTitle"]))
    story.append(_make_table(
        ["Parameter", "Value"],
        [
            ["Project Type", data.project_type],
            ["DUT Count", str(data.dut_count)],
            ["Profile Count", str(data.profile_count)],
            ["Combinations", str(data.dut_profile_combinations)],
            ["PR Fixes", str(data.pr_fix_count)],
            ["Team Size", str(data.team_size)],
            ["Test Leader", "Yes" if data.has_leader else "No"],
            ["Delivery Date", data.expected_delivery],
        ],
        col_widths=[page_width * 0.40, page_width * 0.60],
    ))
    story.append(Spacer(1, 12))

    # ── 4b. DUT x Profile Matrix ─────────────────────
    if data.dut_types and data.profiles:
        story.append(Paragraph("DUT x Profile Matrix", styles["SectionTitle"]))
        matrix_headers = ["DUT \\ Profile"] + [p.get("name", "") for p in data.profiles]
        active_combos = set()
        for combo in data.dut_profile_matrix:
            if len(combo) >= 2:
                active_combos.add((combo[0], combo[1]))
        matrix_rows = []
        for dut in data.dut_types:
            row = [dut.get("name", "")]
            for prof in data.profiles:
                is_active = (dut.get("id"), prof.get("id")) in active_combos or not data.dut_profile_matrix
                row.append("Yes" if is_active else "-")
            matrix_rows.append(row)
        num_cols = len(data.profiles) + 1
        matrix_col_w = [page_width / num_cols] * num_cols
        story.append(_make_table(matrix_headers, matrix_rows, col_widths=matrix_col_w))
        story.append(Spacer(1, 12))

    # ── 5. Task breakdown ──────────────────────────────
    story.append(Paragraph("Task Breakdown", styles["SectionTitle"]))
    task_rows = []
    for task in data.tasks:
        task_rows.append([
            task.get("task_name", task.get("name", "")),
            task.get("task_type", ""),
            f"{task.get('base_hours', 0):.1f}",
            f"{task.get('calculated_hours', 0):.1f}",
            f"{task.get('leader_hours', 0):.1f}",
        ])
    col_w = [page_width * 0.32, page_width * 0.17, page_width * 0.17, page_width * 0.17, page_width * 0.17]
    story.append(_make_table(["Task", "Type", "Base Hrs", "Tester Hrs", "Leader Hrs"], task_rows, col_widths=col_w))
    story.append(Spacer(1, 12))

    # ── 6. Effort summary ──────────────────────────────
    story.append(Paragraph("Effort Summary", styles["SectionTitle"]))
    story.append(_make_table(
        ["Component", "Hours"],
        [
            ["Total Tester Effort", f"{data.total_tester_hours:.1f}"],
            ["Test Leader Effort", f"{data.total_leader_hours:.1f}"],
            ["PR Fix Validation", f"{data.pr_fix_hours:.1f}"],
            ["New Feature Study", f"{data.study_hours:.1f}"],
            ["Buffer (10%)", f"{data.buffer_hours:.1f}"],
            ["GRAND TOTAL", f"{data.grand_total_hours:.1f}"],
        ],
        col_widths=[page_width * 0.55, page_width * 0.45],
    ))
    story.append(Spacer(1, 12))

    # ── 7. Feasibility analysis ────────────────────────
    story.append(Paragraph("Timeline Feasibility", styles["SectionTitle"]))
    leader_text = " and 1 test leader" if data.has_leader else ""
    feasibility_text = (
        f"With {data.team_size} tester(s){leader_text}, capacity is "
        f"{data.capacity_hours:.0f} hours. The estimated {data.grand_total_hours:.1f} hours "
        f"represents <b>{data.utilization_pct:.1f}%</b> utilization — "
        f"<b>{data.feasibility_status}</b>."
    )
    story.append(Paragraph(feasibility_text, styles["Body"]))
    story.append(Spacer(1, 12))

    # ── 8. Reference projects ──────────────────────────
    if data.reference_projects:
        story.append(Paragraph("Reference Projects", styles["SectionTitle"]))
        ref_rows = []
        for proj in data.reference_projects:
            est = proj.get("estimated_hours", 0) or 0
            act = proj.get("actual_hours", 0) or 0
            ratio = f"{act/est:.2f}" if est > 0 else "N/A"
            ref_rows.append([
                proj.get("project_name", ""),
                proj.get("project_type", ""),
                f"{est:.0f}", f"{act:.0f}", ratio,
            ])
        story.append(_make_table(
            ["Project", "Type", "Est.", "Actual", "Ratio"],
            ref_rows,
        ))
        story.append(Spacer(1, 12))

    # ── 9. Risk flags ──────────────────────────────────
    if data.risk_messages:
        story.append(Paragraph("Risk Flags", styles["SectionTitle"]))
        for msg in data.risk_messages:
            story.append(Paragraph(f"• {msg}", styles["RiskItem"]))

    # Build PDF
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.build(story)
        return None
    else:
        doc.build(story)
        return buffer.getvalue()
