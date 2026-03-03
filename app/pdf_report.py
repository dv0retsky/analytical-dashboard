from __future__ import annotations

"""PDF-отчёт (ReportLab).
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from reportlab.lib import utils
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib import colors


@dataclass(frozen=True)
class ReportFigure:
    caption: str
    png_bytes: bytes
    description: str = ""  


@dataclass(frozen=True)
class ReportTable:
    caption: str
    rows: Sequence[Sequence[str]]


@dataclass(frozen=True)
class ReportSection:
    title: str
    description: str 
    figures: List[ReportFigure] = field(default_factory=list)
    tables: List[ReportTable] = field(default_factory=list)


_FONTS_REGISTERED = False


def _register_cyrillic_fonts() -> tuple[str, str]:
    """Регистрирует TTF-шрифты с кириллицей.

    Возвращает (regular_font_name, bold_font_name). Если регистрация не удалась,
    возвращает ("Helvetica", "Helvetica-Bold").
    """

    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return "DejaVuSans", "DejaVuSans-Bold"

    font_dir = Path(__file__).resolve().parent / "assets" / "fonts"
    regular_path = font_dir / "DejaVuSans.ttf"
    bold_path = font_dir / "DejaVuSans-Bold.ttf"

    if not regular_path.exists() or not bold_path.exists():
        sys_regular = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        sys_bold = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        if sys_regular.exists() and sys_bold.exists():
            regular_path = sys_regular
            bold_path = sys_bold

    try:
        if regular_path.exists() and bold_path.exists():
            pdfmetrics.registerFont(TTFont("DejaVuSans", str(regular_path)))
            pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(bold_path)))
            registerFontFamily(
                "DejaVuSans",
                normal="DejaVuSans",
                bold="DejaVuSans-Bold",
                italic="DejaVuSans",
                boldItalic="DejaVuSans-Bold",
            )
            _FONTS_REGISTERED = True
            return "DejaVuSans", "DejaVuSans-Bold"
    except Exception:
        # Не валим генерацию PDF из-за шрифтов.
        _FONTS_REGISTERED = False

    return "Helvetica", "Helvetica-Bold"


def _fit_image(img_bytes: bytes, max_width: float, max_height: float) -> Image:
    bio = BytesIO(img_bytes)
    pil = utils.ImageReader(bio)
    w, h = pil.getSize()

    aspect = w / float(h) if h else 1.0
    target_w = max_width
    target_h = target_w / aspect

    if target_h > max_height:
        target_h = max_height
        target_w = target_h * aspect

    bio.seek(0)
    return Image(bio, width=target_w, height=target_h)


def _draw_header_footer(app_title: str, regular_font: str):
    """Фабрика колбэков для onFirstPage/onLaterPages."""

    def _cb(canvas, doc):
        canvas.saveState()
        canvas.setFont(regular_font, 9)
        canvas.setFillGray(0.35)

        # Header
        canvas.drawString(doc.leftMargin, A4[1] - 1.1 * cm, app_title)

        # Footer: page number
        page = canvas.getPageNumber()
        canvas.drawRightString(A4[0] - doc.rightMargin, 0.85 * cm, f"Стр. {page}")
        canvas.restoreState()

    return _cb


def _make_table(rows: Sequence[Sequence[str]], max_width: float, regular_font: str, bold_font: str) -> Table:
    ncols = max((len(r) for r in rows), default=1)
    col_w = max_width / float(max(ncols, 1))
    tbl = Table(list(rows), colWidths=[col_w] * ncols, hAlign="LEFT")
    tbl.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("FONTNAME", (0, 1), (-1, -1), regular_font),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return tbl


def build_pdf_report(
    app_title: str,
    period_from: date,
    period_to: date,
    sections: List[ReportSection],
    generated_at: Optional[datetime] = None,
) -> bytes:
    """Собирает PDF и возвращает bytes."""

    regular_font, bold_font = _register_cyrillic_fonts()

    if generated_at is None:
        generated_at = datetime.utcnow()

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
        title=app_title,
        author="Streamlit App",
    )

    styles = getSampleStyleSheet()

    for st in styles.byName.values():
        st.fontName = regular_font
    if "Title" in styles.byName:
        styles["Title"].fontName = bold_font
    if "Heading1" in styles.byName:
        styles["Heading1"].fontName = bold_font
    if "Heading2" in styles.byName:
        styles["Heading2"].fontName = bold_font
    story = []

    story.append(Paragraph(app_title, styles["Title"]))
    story.append(Spacer(1, 0.25 * cm))
    story.append(
        Paragraph(
            f"<b>Период отчёта:</b> {period_from.isoformat()} — {period_to.isoformat()}",
            styles["Normal"],
        )
    )
    story.append(
        Paragraph(
            f"<b>Сформировано (UTC):</b> {generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 0.6 * cm))

    max_img_w = A4[0] - (doc.leftMargin + doc.rightMargin)
    max_img_h = 11.5 * cm

    for si, section in enumerate(sections, start=1):
        story.append(Paragraph(f"{si}. {section.title}", styles["Heading2"]))
        story.append(Spacer(1, 0.2 * cm))
        if section.description:
            story.append(Paragraph(section.description, styles["BodyText"]))
            story.append(Spacer(1, 0.35 * cm))

        # Tables
        for t in section.tables:
            if t.caption:
                story.append(Paragraph(f"<i>{t.caption}</i>", styles["BodyText"]))
                story.append(Spacer(1, 0.15 * cm))
            story.append(_make_table(t.rows, max_width=max_img_w, regular_font=regular_font, bold_font=bold_font))
            story.append(Spacer(1, 0.45 * cm))

        # Figures
        for fig in section.figures:
            img = _fit_image(fig.png_bytes, max_width=max_img_w, max_height=max_img_h)
            story.append(img)
            story.append(Spacer(1, 0.15 * cm))
            if fig.caption:
                story.append(Paragraph(f"<i>{fig.caption}</i>", styles["BodyText"]))
                story.append(Spacer(1, 0.12 * cm))

            if fig.description:
                story.append(Paragraph(fig.description, styles["BodyText"]))
            story.append(Spacer(1, 0.5 * cm))

        if si != len(sections):
            story.append(PageBreak())

    cb = _draw_header_footer(app_title, regular_font=regular_font)
    doc.build(story, onFirstPage=cb, onLaterPages=cb)
    return buf.getvalue()
