from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
INPUT_MD = ROOT / "paper" / "draft.md"
OUTPUT_PDF = ROOT / "output" / "pdf" / "evtol_paper_template.pdf"

KOREAN_FONT = "/System/Library/Fonts/Supplemental/AppleGothic.ttf"


def register_fonts() -> str:
    if Path(KOREAN_FONT).exists():
        pdfmetrics.registerFont(TTFont("AppleGothic", KOREAN_FONT))
        return "AppleGothic"
    return "Helvetica"


def clean_inline(text: str) -> str:
    text = text.strip()
    text = text.replace("`", "")
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)
    return html.escape(text)


def split_table_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def is_table_separator(line: str) -> bool:
    cells = split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def resolve_image_path(markdown_path: str) -> Path:
    path = Path(markdown_path)
    if path.is_absolute():
        return path
    return (INPUT_MD.parent / path).resolve()


def make_styles(font_name: str) -> dict[str, ParagraphStyle]:
    styles = getSampleStyleSheet()
    return {
        "title_en": ParagraphStyle(
            "title_en",
            parent=styles["Title"],
            fontName=font_name,
            fontSize=16,
            leading=20,
            alignment=TA_CENTER,
            spaceAfter=7,
        ),
        "title_ko": ParagraphStyle(
            "title_ko",
            parent=styles["Title"],
            fontName=font_name,
            fontSize=15,
            leading=20,
            alignment=TA_CENTER,
            spaceBefore=8,
            spaceAfter=7,
        ),
        "heading": ParagraphStyle(
            "heading",
            parent=styles["Heading2"],
            fontName=font_name,
            fontSize=12,
            leading=16,
            alignment=TA_LEFT,
            spaceBefore=11,
            spaceAfter=5,
            textColor=colors.black,
        ),
        "subheading": ParagraphStyle(
            "subheading",
            parent=styles["Heading3"],
            fontName=font_name,
            fontSize=10.5,
            leading=14,
            alignment=TA_LEFT,
            spaceBefore=8,
            spaceAfter=4,
            textColor=colors.black,
        ),
        "abstract_heading": ParagraphStyle(
            "abstract_heading",
            parent=styles["Heading2"],
            fontName=font_name,
            fontSize=11,
            leading=14,
            alignment=TA_CENTER,
            spaceBefore=7,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=9.2,
            leading=14,
            alignment=TA_JUSTIFY,
            firstLineIndent=9,
            spaceAfter=4,
        ),
        "keyword": ParagraphStyle(
            "keyword",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=8.8,
            leading=12,
            alignment=TA_LEFT,
            leftIndent=0,
            spaceBefore=2,
            spaceAfter=7,
        ),
        "caption": ParagraphStyle(
            "caption",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=8.3,
            leading=11,
            alignment=TA_CENTER,
            spaceBefore=3,
            spaceAfter=7,
        ),
        "table_cell": ParagraphStyle(
            "table_cell",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=6.7,
            leading=8.2,
            alignment=TA_CENTER,
        ),
        "table_head": ParagraphStyle(
            "table_head",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=6.7,
            leading=8.2,
            alignment=TA_CENTER,
            textColor=colors.black,
        ),
        "reference": ParagraphStyle(
            "reference",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=8.3,
            leading=11.5,
            leftIndent=12,
            firstLineIndent=-12,
            spaceAfter=3,
        ),
    }


def append_paragraph(story: list, buffer: list[str], styles: dict[str, ParagraphStyle], in_references: bool) -> None:
    if not buffer:
        return
    text = " ".join(part.strip() for part in buffer if part.strip())
    buffer.clear()
    if not text:
        return
    style = styles["reference"] if in_references else styles["body"]
    if text.startswith(("Keywords:", "키워드:")):
        style = styles["keyword"]
    story.append(Paragraph(clean_inline(text), style))


def append_table(
    story: list,
    table_lines: list[str],
    styles: dict[str, ParagraphStyle],
    available_width: float,
) -> None:
    rows = [split_table_row(line) for line in table_lines if not is_table_separator(line)]
    if not rows:
        return
    max_cols = max(len(row) for row in rows)
    for row in rows:
        while len(row) < max_cols:
            row.append("")

    table_data = []
    for row_index, row in enumerate(rows):
        style = styles["table_head"] if row_index == 0 else styles["table_cell"]
        table_data.append([Paragraph(clean_inline(cell), style) for cell in row])

    col_widths = [available_width / max_cols] * max_cols
    table = Table(table_data, colWidths=col_widths, repeatRows=1, hAlign="CENTER")
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#777777")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDEDED")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(Spacer(1, 3))
    story.append(table)
    story.append(Spacer(1, 7))


def append_image(
    story: list,
    markdown_line: str,
    styles: dict[str, ParagraphStyle],
    available_width: float,
    figure_number: int,
) -> int:
    match = re.match(r"!\[(.*?)\]\((.*?)\)", markdown_line.strip())
    if not match:
        return figure_number
    alt_text, image_path_text = match.groups()
    image_path = resolve_image_path(image_path_text)
    if not image_path.exists():
        story.append(Paragraph(f"[Missing figure: {clean_inline(image_path_text)}]", styles["caption"]))
        return figure_number

    img = Image(str(image_path))
    max_width = min(available_width * 0.92, 150 * mm)
    max_height = 75 * mm
    scale = min(max_width / img.imageWidth, max_height / img.imageHeight, 1.0)
    img.drawWidth = img.imageWidth * scale
    img.drawHeight = img.imageHeight * scale
    caption = Paragraph(f"Fig. {figure_number}. {clean_inline(alt_text)}", styles["caption"])
    story.append(KeepTogether([Spacer(1, 5), img, caption]))
    return figure_number + 1


def build_story(markdown_text: str, styles: dict[str, ParagraphStyle], available_width: float) -> list:
    story: list = []
    paragraph_buffer: list[str] = []
    table_buffer: list[str] = []
    figure_number = 1
    in_references = False
    seen_korean_title = False

    lines = markdown_text.splitlines()
    for raw_line in lines:
        line = raw_line.rstrip()

        if table_buffer and (not line.strip().startswith("|")):
            append_paragraph(story, paragraph_buffer, styles, in_references)
            append_table(story, table_buffer, styles, available_width)
            table_buffer = []

        if not line.strip():
            append_paragraph(story, paragraph_buffer, styles, in_references)
            continue

        if line.strip().startswith("|"):
            append_paragraph(story, paragraph_buffer, styles, in_references)
            table_buffer.append(line)
            continue

        if line.startswith("!["):
            append_paragraph(story, paragraph_buffer, styles, in_references)
            figure_number = append_image(story, line, styles, available_width, figure_number)
            continue

        if line.startswith("# "):
            append_paragraph(story, paragraph_buffer, styles, in_references)
            title = line[2:].strip()
            style = styles["title_ko"] if re.search(r"[가-힣]", title) else styles["title_en"]
            if re.search(r"[가-힣]", title):
                seen_korean_title = True
            story.append(Paragraph(clean_inline(title), style))
            if not seen_korean_title:
                story.append(Spacer(1, 3))
            continue

        if line.startswith("## "):
            append_paragraph(story, paragraph_buffer, styles, in_references)
            heading = line[3:].strip()
            if heading.lower() == "references":
                in_references = True
                story.append(Spacer(1, 5))
                story.append(Paragraph("References", styles["heading"]))
            elif heading in {"ABSTRACT", "요약"}:
                display = "요     약" if heading == "요약" else heading
                story.append(Paragraph(display, styles["abstract_heading"]))
            else:
                story.append(Paragraph(clean_inline(heading), styles["heading"]))
            continue

        if line.startswith("### "):
            append_paragraph(story, paragraph_buffer, styles, in_references)
            story.append(Paragraph(clean_inline(line[4:].strip()), styles["subheading"]))
            continue

        paragraph_buffer.append(line)

    append_paragraph(story, paragraph_buffer, styles, in_references)
    if table_buffer:
        append_table(story, table_buffer, styles, available_width)
    return story


def on_page(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("AppleGothic" if "AppleGothic" in pdfmetrics.getRegisteredFontNames() else "Helvetica", 8)
    canvas.drawCentredString(A4[0] / 2, 10 * mm, str(doc.page))
    canvas.restoreState()


def main() -> None:
    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    font_name = register_fonts()
    styles = make_styles(font_name)
    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=17 * mm,
        title="eVTOL Mobility Model Simulator",
        author="",
    )
    markdown_text = INPUT_MD.read_text(encoding="utf-8")
    story = build_story(markdown_text, styles, doc.width)
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(OUTPUT_PDF)


if __name__ == "__main__":
    main()
