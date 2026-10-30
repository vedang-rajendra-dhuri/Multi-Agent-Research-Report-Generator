from io import BytesIO
from xml.sax.saxutils import escape

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from app.models.research import ResearchSource, ReportVersion


def _report_sections(version: ReportVersion) -> list[tuple[str, str, list[str]]]:
    return [
        ("Executive summary", version.executive_summary, []),
        *[
            (
                str(section["title"]),
                str(section["content"]),
                list(section.get("source_ids", [])),
            )
            for section in version.sections
        ],
        ("Methodology", version.methodology, []),
    ]


def render_docx(
    version: ReportVersion,
    sources: dict[str, ResearchSource],
) -> bytes:
    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.7)
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.8)
    document.styles["Normal"].font.name = "Arial"
    document.styles["Normal"].font.size = Pt(10)

    title = document.add_heading("Research report", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for heading, content, source_ids in _report_sections(version):
        document.add_heading(heading, level=1)
        document.add_paragraph(content)
        for source_id in source_ids:
            source = sources.get(source_id)
            if source is not None:
                document.add_paragraph(
                    f"Source: {source.title} ({source.url})",
                    style="Caption",
                )

    document.add_heading("Limitations", level=1)
    for limitation in version.limitations:
        document.add_paragraph(limitation, style="List Bullet")
    document.add_heading("References", level=1)
    for source in sources.values():
        document.add_paragraph(f"[{source.provider_source_id}] {source.title} — {source.url}")

    output = BytesIO()
    document.save(output)
    return output.getvalue()


def _draw_page_number(canvas, document) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#d0d5dd"))
    canvas.line(0.7 * inch, 0.6 * inch, 7.8 * inch, 0.6 * inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#667085"))
    canvas.drawRightString(7.8 * inch, 0.4 * inch, f"Page {document.page}")
    canvas.restoreState()


def render_pdf(
    version: ReportVersion,
    sources: dict[str, ResearchSource],
) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.8 * inch,
        title="Research report",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#172033"),
        spaceAfter=18,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        spaceAfter=8,
    )
    story = [Paragraph("Research report", title_style)]
    for heading, content, source_ids in _report_sections(version):
        story.append(Paragraph(escape(heading), styles["Heading2"]))
        body = escape(content).replace("\n", "<br/>")
        story.append(Paragraph(body, body_style))
        for source_id in source_ids:
            source = sources.get(source_id)
            if source is not None:
                story.append(
                    Paragraph(
                        escape(f"Source: {source.title} ({source.url})"),
                        styles["Italic"],
                    )
                )
    story.append(Paragraph("Limitations", styles["Heading2"]))
    for limitation in version.limitations:
        story.append(Paragraph(f"- {escape(limitation)}", body_style))
    story.append(Paragraph("References", styles["Heading2"]))
    for source in sources.values():
        reference = f"[{source.provider_source_id}] {source.title} — {source.url}"
        story.append(Paragraph(escape(reference), body_style))
    document.build(story, onFirstPage=_draw_page_number, onLaterPages=_draw_page_number)
    return output.getvalue()
