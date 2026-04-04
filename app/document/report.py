"""PDF report generation — annotated detection reports with color-coded highlights."""

import io
import logging
from typing import Optional

from app.core.config import SCORE_GREEN, SCORE_YELLOW
from app.document.structure import Document

logger = logging.getLogger(__name__)


def _score_color(score: float) -> tuple:
    """Return RGB tuple for score. Red >60%, Yellow 20-60%, Green <20%."""
    if score > SCORE_YELLOW:
        return (0.9, 0.2, 0.2)  # red
    if score > SCORE_GREEN:
        return (0.9, 0.7, 0.1)  # yellow
    return (0.2, 0.7, 0.3)  # green


def generate_report(
    document: Document,
    segment_scores: list[dict],
    overall_score: float,
    overall_verdict: str,
    output_path: Optional[str] = None,
) -> bytes:
    """Generate an annotated PDF detection report.

    Args:
        document: Parsed document structure.
        segment_scores: List of dicts with 'score', 'verdict' per paragraph.
        overall_score: Overall detection score.
        overall_verdict: Overall verdict string.
        output_path: Optional path to save the PDF.

    Returns:
        PDF bytes.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import inch, mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import Color, HexColor
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph as RLParagraph, Spacer, Table,
        TableStyle, HRFlowable,
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=25 * mm,
        rightMargin=25 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        "SectionHead",
        parent=styles["Heading2"],
        fontSize=14,
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "BodyText",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        spaceAfter=6,
    )
    score_style = ParagraphStyle(
        "ScoreText",
        parent=styles["BodyText"],
        fontSize=9,
        textColor=HexColor("#666666"),
    )

    elements = []

    # --- Title page / summary ---
    elements.append(RLParagraph("AI Detection Report", title_style))
    if document.title:
        elements.append(RLParagraph(f"Document: {document.title}", body_style))
    elements.append(Spacer(1, 12))

    # Overall score
    r, g, b = _score_color(overall_score)
    score_color = Color(r, g, b)
    elements.append(RLParagraph(
        f'<font color="#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}">'
        f"Overall Score: {overall_score:.1f}% — {overall_verdict}</font>",
        heading_style,
    ))
    elements.append(Spacer(1, 8))

    # Score breakdown table
    if segment_scores:
        table_data = [["Paragraph", "Score", "Verdict"]]
        for i, seg in enumerate(segment_scores):
            score = seg.get("score", 0)
            verdict = seg.get("verdict", "")
            r, g, b = _score_color(score)
            table_data.append([
                f"#{i + 1}",
                f"{score:.1f}%",
                verdict,
            ])

        table = Table(table_data, colWidths=[60, 80, 250])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#333333")),
            ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#F9F9F9"), HexColor("#FFFFFF")]),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(table)

    elements.append(Spacer(1, 16))
    elements.append(HRFlowable(width="100%", color=HexColor("#CCCCCC")))
    elements.append(Spacer(1, 12))

    # --- Annotated text ---
    elements.append(RLParagraph("Annotated Text", title_style))
    elements.append(Spacer(1, 8))

    para_idx = 0
    for section in document.sections:
        if section.heading:
            elements.append(RLParagraph(section.heading, heading_style))

        for para in section.paragraphs:
            score_info = segment_scores[para_idx] if para_idx < len(segment_scores) else {}
            score = score_info.get("score", 0)
            r, g, b = _score_color(score)

            # Color-coded score annotation
            elements.append(RLParagraph(
                f'<font color="#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}">'
                f"[{score:.0f}%]</font>",
                score_style,
            ))

            # Paragraph text with background tint
            # Use a light background version of the score color
            bg_hex = f"#{int(r*255*0.15 + 255*0.85):02x}{int(g*255*0.15 + 255*0.85):02x}{int(b*255*0.15 + 255*0.85):02x}"
            para_style = ParagraphStyle(
                f"para_{para_idx}",
                parent=body_style,
                backColor=HexColor(bg_hex),
                borderPadding=4,
            )
            # Escape XML entities in text
            safe_text = (
                para.text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            elements.append(RLParagraph(safe_text, para_style))
            elements.append(Spacer(1, 4))
            para_idx += 1

    doc.build(elements)
    pdf_bytes = buffer.getvalue()

    if output_path:
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        logger.info("Report saved to %s", output_path)

    return pdf_bytes
