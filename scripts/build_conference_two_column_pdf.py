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
    BaseDocTemplate,
    Frame,
    FrameBreak,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
INPUT_MD = ROOT / "paper" / "draft.md"
OUTPUT_PDF = ROOT / "output" / "pdf" / "evtol_paper_conference_two_column.pdf"
KOREAN_FONT = "/System/Library/Fonts/Supplemental/AppleGothic.ttf"
HEADER_TEXT = ""

ROMAN = {
    "1": "Ⅰ",
    "2": "Ⅱ",
    "3": "Ⅲ",
    "4": "Ⅳ",
    "5": "Ⅴ",
    "6": "Ⅵ",
}


def register_font() -> str:
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


def extract_article(markdown_text: str) -> dict[str, str]:
    lines = markdown_text.splitlines()
    english_title = ""
    korean_title = ""
    abstract_en: list[str] = []
    abstract_ko: list[str] = []
    keywords_en = ""
    keywords_ko = ""
    body_start = 0
    mode: str | None = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("# ") and not english_title:
            english_title = stripped[2:].strip()
            continue
        if stripped == "## ABSTRACT":
            mode = "abstract_en"
            continue
        if stripped.startswith("Keywords:"):
            keywords_en = stripped
            mode = None
            continue
        if stripped.startswith("# ") and re.search(r"[가-힣]", stripped):
            korean_title = stripped[2:].strip()
            continue
        if stripped == "## 요약":
            mode = "abstract_ko"
            continue
        if stripped.startswith("키워드:"):
            keywords_ko = stripped
            mode = None
            continue
        if stripped.startswith("## 1. "):
            body_start = i
            break
        if mode == "abstract_en" and stripped:
            abstract_en.append(stripped)
        elif mode == "abstract_ko" and stripped:
            abstract_ko.append(stripped)

    return {
        "english_title": english_title,
        "korean_title": korean_title,
        "abstract_en": " ".join(abstract_en),
        "abstract_ko": " ".join(abstract_ko),
        "keywords_en": keywords_en,
        "keywords_ko": keywords_ko,
        "body": "\n".join(lines[body_start:]),
    }


def make_styles(font_name: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "top_title_ko": ParagraphStyle(
            "top_title_ko",
            parent=base["Title"],
            fontName=font_name,
            fontSize=15.5,
            leading=19,
            alignment=TA_CENTER,
            spaceAfter=9,
        ),
        "top_title_en": ParagraphStyle(
            "top_title_en",
            parent=base["Title"],
            fontName=font_name,
            fontSize=10.5,
            leading=13,
            alignment=TA_CENTER,
            spaceBefore=4,
            spaceAfter=7,
        ),
        "author": ParagraphStyle(
            "author",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=9.5,
            leading=13,
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "abstract_heading": ParagraphStyle(
            "abstract_heading",
            parent=base["Heading2"],
            fontName=font_name,
            fontSize=9.5,
            leading=12,
            alignment=TA_CENTER,
            spaceBefore=4,
            spaceAfter=3,
        ),
        "abstract_ko": ParagraphStyle(
            "abstract_ko",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=7.2,
            leading=10.1,
            alignment=TA_JUSTIFY,
            firstLineIndent=0,
            spaceAfter=6,
        ),
        "abstract_en": ParagraphStyle(
            "abstract_en",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=6.8,
            leading=8.4,
            alignment=TA_JUSTIFY,
            firstLineIndent=0,
            spaceAfter=5,
        ),
        "keyword": ParagraphStyle(
            "keyword",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=6.8,
            leading=8.2,
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "section": ParagraphStyle(
            "section",
            parent=base["Heading2"],
            fontName=font_name,
            fontSize=11.2,
            leading=14,
            alignment=TA_CENTER,
            spaceBefore=9,
            spaceAfter=8,
        ),
        "subsection": ParagraphStyle(
            "subsection",
            parent=base["Heading3"],
            fontName=font_name,
            fontSize=9.4,
            leading=12,
            alignment=TA_LEFT,
            spaceBefore=7,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=8.0,
            leading=12.2,
            alignment=TA_JUSTIFY,
            firstLineIndent=8,
            spaceAfter=4,
        ),
        "reference": ParagraphStyle(
            "reference",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=6.7,
            leading=8.5,
            leftIndent=9,
            firstLineIndent=-9,
            spaceAfter=2,
        ),
        "caption": ParagraphStyle(
            "caption",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=6.7,
            leading=8.5,
            alignment=TA_CENTER,
            spaceBefore=2,
            spaceAfter=5,
        ),
        "table_cell": ParagraphStyle(
            "table_cell",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=4.8,
            leading=6.0,
            alignment=TA_CENTER,
        ),
        "table_head": ParagraphStyle(
            "table_head",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=4.8,
            leading=6.0,
            alignment=TA_CENTER,
        ),
    }


def flush_paragraph(story: list, buffer: list[str], styles: dict[str, ParagraphStyle], in_refs: bool) -> None:
    if not buffer:
        return
    text = " ".join(part.strip() for part in buffer if part.strip())
    buffer.clear()
    if not text:
        return
    style = styles["reference"] if in_refs else styles["body"]
    story.append(Paragraph(clean_inline(text), style))


def append_table(story: list, table_lines: list[str], styles: dict[str, ParagraphStyle], col_width: float) -> None:
    rows = [split_table_row(line) for line in table_lines if not is_table_separator(line)]
    if not rows:
        return
    max_cols = max(len(row) for row in rows)
    for row in rows:
        row.extend([""] * (max_cols - len(row)))

    data = []
    for row_idx, row in enumerate(rows):
        style = styles["table_head"] if row_idx == 0 else styles["table_cell"]
        data.append([Paragraph(clean_inline(cell), style) for cell in row])

    table = Table(data, colWidths=[col_width / max_cols] * max_cols, repeatRows=1, hAlign="CENTER")
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#777777")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDEDED")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1.2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1.2),
                ("TOPPADDING", (0, 0), (-1, -1), 1.4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.4),
            ]
        )
    )
    story.append(KeepTogether([Spacer(1, 2), table, Spacer(1, 5)]))


def append_image(story: list, line: str, styles: dict[str, ParagraphStyle], col_width: float, fig_no: int) -> int:
    match = re.match(r"!\[(.*?)\]\((.*?)\)", line.strip())
    if not match:
        return fig_no
    alt, path_text = match.groups()
    image_path = resolve_image_path(path_text)
    if not image_path.exists():
        story.append(Paragraph(f"[Missing figure: {clean_inline(path_text)}]", styles["caption"]))
        return fig_no

    img = Image(str(image_path))
    max_w = col_width * 0.96
    max_h = 45 * mm if "대표 eVTOL" in alt else 55 * mm
    scale = min(max_w / img.imageWidth, max_h / img.imageHeight, 1.0)
    img.drawWidth = img.imageWidth * scale
    img.drawHeight = img.imageHeight * scale
    story.append(
        KeepTogether(
            [
                Spacer(1, 3),
                img,
                Paragraph(f"그림 {fig_no}. {clean_inline(alt)}", styles["caption"]),
            ]
        )
    )
    return fig_no + 1


def transform_heading(line: str) -> str:
    text = line[3:].strip()
    if text.lower() == "references":
        return "참 고 문 헌"
    match = re.match(r"(\d+)\.\s*(.*)", text)
    if match and match.group(1) in ROMAN:
        return f"{ROMAN[match.group(1)]}. {match.group(2)}"
    return text


def build_top_story(article: dict[str, str], styles: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph(clean_inline(article["korean_title"]), styles["top_title_ko"]),
        Paragraph("저자*, 저자**", styles["author"]),
        Paragraph(clean_inline(article["english_title"]), styles["top_title_en"]),
        Paragraph("Author*, Author**", styles["author"]),
        Paragraph("요&nbsp;&nbsp;약", styles["abstract_heading"]),
        Paragraph(clean_inline(article["abstract_ko"]), styles["abstract_ko"]),
        Paragraph("Abstract", styles["abstract_heading"]),
        Paragraph(clean_inline(article["abstract_en"]), styles["abstract_en"]),
        Paragraph("Key words", styles["abstract_heading"]),
        Paragraph(clean_inline(article["keywords_en"].replace("Keywords:", "")), styles["keyword"]),
        Paragraph(clean_inline(article["keywords_ko"].replace("키워드:", "")), styles["keyword"]),
    ]


def build_body_story(body_md: str, styles: dict[str, ParagraphStyle], col_width: float) -> list:
    story: list = []
    para_buffer: list[str] = []
    table_buffer: list[str] = []
    fig_no = 1
    in_refs = False

    for raw in body_md.splitlines():
        line = raw.rstrip()

        if table_buffer and not line.strip().startswith("|"):
            flush_paragraph(story, para_buffer, styles, in_refs)
            append_table(story, table_buffer, styles, col_width)
            table_buffer = []

        if not line.strip():
            flush_paragraph(story, para_buffer, styles, in_refs)
            continue

        if line.strip().startswith("|"):
            flush_paragraph(story, para_buffer, styles, in_refs)
            table_buffer.append(line)
            continue

        if line.startswith("!["):
            flush_paragraph(story, para_buffer, styles, in_refs)
            fig_no = append_image(story, line, styles, col_width, fig_no)
            continue

        if line.startswith("## "):
            flush_paragraph(story, para_buffer, styles, in_refs)
            heading = transform_heading(line)
            if heading == "참 고 문 헌":
                in_refs = True
            story.append(Paragraph(clean_inline(heading), styles["section"]))
            continue

        if line.startswith("### "):
            flush_paragraph(story, para_buffer, styles, in_refs)
            story.append(Paragraph(clean_inline(line[4:].strip()), styles["subsection"]))
            continue

        para_buffer.append(line)

    flush_paragraph(story, para_buffer, styles, in_refs)
    if table_buffer:
        append_table(story, table_buffer, styles, col_width)
    return story


def draw_page(canvas, doc) -> None:
    canvas.saveState()
    font_name = "AppleGothic" if "AppleGothic" in pdfmetrics.getRegisteredFontNames() else "Helvetica"
    if HEADER_TEXT:
        canvas.setFont(font_name, 8.5)
        canvas.drawCentredString(A4[0] / 2, A4[1] - 16 * mm, HEADER_TEXT)
    canvas.setStrokeColor(colors.HexColor("#777777"))
    canvas.setLineWidth(0.25)
    canvas.line(19 * mm, 19 * mm, A4[0] - 19 * mm, 19 * mm)
    canvas.setFont(font_name, 8)
    canvas.drawCentredString(A4[0] / 2, 12 * mm, f"-{doc.page}-")
    canvas.restoreState()


def main() -> None:
    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    font_name = register_font()
    styles = make_styles(font_name)
    article = extract_article(INPUT_MD.read_text(encoding="utf-8"))

    page_w, page_h = A4
    left_margin = 20 * mm
    right_margin = 20 * mm
    gutter = 8 * mm
    col_w = (page_w - left_margin - right_margin - gutter) / 2

    top_y = 305
    top_h = 415
    first_top = Frame(left_margin, top_y, page_w - left_margin - right_margin, top_h, id="first_top", showBoundary=0)
    first_left = Frame(left_margin, 24 * mm, col_w, top_y - 30 * mm, id="first_left", showBoundary=0)
    first_right = Frame(left_margin + col_w + gutter, 24 * mm, col_w, top_y - 30 * mm, id="first_right", showBoundary=0)

    later_top = page_h - 25 * mm
    later_bottom = 24 * mm
    later_h = later_top - later_bottom
    later_left = Frame(left_margin, later_bottom, col_w, later_h, id="later_left", showBoundary=0)
    later_right = Frame(left_margin + col_w + gutter, later_bottom, col_w, later_h, id="later_right", showBoundary=0)

    doc = BaseDocTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        leftMargin=left_margin,
        rightMargin=right_margin,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title="eVTOL Mobility Model Simulator",
        author="",
    )
    doc.addPageTemplates(
        [
            PageTemplate(id="First", frames=[first_top, first_left, first_right], onPage=draw_page),
            PageTemplate(id="Later", frames=[later_left, later_right], onPage=draw_page),
        ]
    )

    story: list = [NextPageTemplate("Later")]
    story.extend(build_top_story(article, styles))
    story.append(FrameBreak())
    story.extend(build_body_story(article["body"], styles, col_w))
    doc.build(story)
    print(OUTPUT_PDF)


if __name__ == "__main__":
    main()
