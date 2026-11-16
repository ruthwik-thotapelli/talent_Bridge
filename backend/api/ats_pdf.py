import io
import json
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

def build_ats_pdf_buffer(report) -> bytes:
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    def safe_json(v, fallback):
        if not v:
            return fallback
        if isinstance(v, (dict, list)):
            return v
        try:
            return json.loads(v)
        except Exception:
            return fallback

    breakdown = safe_json(report.breakdown_json, {})
    section_status = safe_json(report.section_status_json, {})
    checklist = safe_json(report.checklist_json, [])
    issues = safe_json(report.issues_json, [])
    fixes = safe_json(report.fixes_json, [])
    examples = safe_json(report.examples_json, [])

    y = height - 50

    # Header
    p.setFont("Helvetica-Bold", 20)
    p.setFillColor(colors.HexColor("#4c1d95"))
    p.drawString(50, y, "TalentBridge ATS Report")
    y -= 25

    p.setFont("Helvetica", 10)
    p.setFillColor(colors.HexColor("#374151"))
    p.drawString(50, y, f"Generated: {report.created_at.strftime('%Y-%m-%d %H:%M:%S') if report.created_at else datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    y -= 15
    p.drawString(50, y, f"Resume: {report.resume_name or 'resume'}")
    y -= 15

    if report.job_desc_snippet:
        snippet = (report.job_desc_snippet[:100] + "...") if len(report.job_desc_snippet) > 100 else report.job_desc_snippet
        p.drawString(50, y, f"Job Desc: {snippet}")
        y -= 20
    else:
        y -= 10

    # Score Box
    p.setFont("Helvetica-Bold", 14)
    p.setFillColor(colors.HexColor("#6d28d9"))
    p.drawString(50, y, "Score Summary")
    y -= 18

    p.setFont("Helvetica", 11)
    p.setFillColor(colors.black)
    p.drawString(50, y, f"Score: {report.score}/100   |   Level: {report.level or 'N/A'}")
    y -= 16
    if report.keyword_match_percent is not None:
        p.drawString(50, y, f"Keyword Match: {report.keyword_match_percent}%")
        y -= 16

    # Breakdown
    y -= 10
    p.setFont("Helvetica-Bold", 12)
    p.setFillColor(colors.HexColor("#4c1d95"))
    p.drawString(50, y, "Score Breakdown")
    y -= 16

    p.setFont("Helvetica", 10)
    p.setFillColor(colors.black)
    p.drawString(50, y, f"Keywords: {breakdown.get('keywords', '-')}  |  Sections: {breakdown.get('sections', '-')}  |  Format: {breakdown.get('format', '-')}")
    y -= 20

    # Section Status
    p.setFont("Helvetica-Bold", 12)
    p.setFillColor(colors.HexColor("#4c1d95"))
    p.drawString(50, y, "Section Status")
    y -= 16

    p.setFont("Helvetica", 10)
    sec_str = ", ".join([f"{k.capitalize()}: {'OK' if v else 'Missing'}" for k, v in section_status.items()])
    p.drawString(50, y, sec_str or "N/A")
    y -= 20

    # Action Plan (Fixes)
    p.setFont("Helvetica-Bold", 12)
    p.setFillColor(colors.HexColor("#4c1d95"))
    p.drawString(50, y, "Action Plan (Fixes)")
    y -= 16

    p.setFont("Helvetica", 9)
    if fixes:
        for fix in fixes[:7]:
            if y < 60:
                p.showPage()
                y = height - 50
            p.drawString(60, y, f" {fix}")
            y -= 14
    else:
        p.drawString(60, y, "No major fixes suggested.")
        y -= 14

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer.getvalue()
