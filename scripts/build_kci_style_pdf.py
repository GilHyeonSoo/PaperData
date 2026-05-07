from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
INPUT_MD = ROOT / "paper" / "draft_kci_style.md"
OUTPUT_PDF = ROOT / "output" / "pdf" / "evtol_paper_kci_style.pdf"

APPLE_MYUNGJO = "/System/Library/Fonts/Supplemental/AppleMyungjo.ttf"
APPLE_GOTHIC = "/System/Library/Fonts/Supplemental/AppleGothic.ttf"
TIMES = "/System/Library/Fonts/Supplemental/Times New Roman.ttf"
TIMES_BOLD = "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf"

PAGE_W = 190 * mm
PAGE_H = 260 * mm
LEFT = 20 * mm
RIGHT = 20 * mm
TOP = 22 * mm
BOTTOM = 17.5 * mm
GUTTER = 6 * mm
CONTENT_W = PAGE_W - LEFT - RIGHT
COL_W = (CONTENT_W - GUTTER) / 2


def register_fonts() -> dict[str, str]:
    fonts = {
        "ko": "Times-Roman",
        "ko_bold": "Times-Bold",
        "en": "Times-Roman",
        "en_bold": "Times-Bold",
    }
    if Path(APPLE_MYUNGJO).exists():
        pdfmetrics.registerFont(TTFont("AppleMyungjo", APPLE_MYUNGJO))
        fonts["ko"] = "AppleMyungjo"
        fonts["ko_bold"] = "AppleMyungjo"
    if Path(APPLE_GOTHIC).exists():
        pdfmetrics.registerFont(TTFont("AppleGothic", APPLE_GOTHIC))
        fonts["gothic"] = "AppleGothic"
    else:
        fonts["gothic"] = fonts["ko"]
    if Path(TIMES).exists():
        pdfmetrics.registerFont(TTFont("TimesNewRoman", TIMES))
        fonts["en"] = "TimesNewRoman"
    if Path(TIMES_BOLD).exists():
        pdfmetrics.registerFont(TTFont("TimesNewRomanBold", TIMES_BOLD))
        fonts["en_bold"] = "TimesNewRomanBold"
    return fonts


def clean_inline(text: str) -> str:
    text = text.strip().replace("`", "")
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)
    return html.escape(text)


def resolve_image_path(markdown_path: str) -> Path:
    path = Path(markdown_path)
    if path.is_absolute():
        return path
    return (INPUT_MD.parent / path).resolve()


def split_caption(text: str) -> tuple[str, str]:
    if "|" in text:
        ko, en = text.split("|", 1)
        return ko.strip(), en.strip()
    return text.strip(), ""


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


def parse_markdown(markdown_text: str) -> dict[str, object]:
    data: dict[str, object] = {
        "title": "",
        "subtitle": "",
        "english_title": "",
        "summary": "",
        "abstract": "",
        "keywords": "",
        "body": [],
        "references": [],
    }
    mode = "front"
    bucket: list[str] = []

    def flush() -> None:
        nonlocal bucket, mode
        text = "\n".join(bucket).strip()
        if mode in {"english_title", "summary", "abstract", "keywords"}:
            data[mode] = text
        bucket = []

    lines = markdown_text.splitlines()
    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith("# "):
            data["title"] = stripped[2:].strip()
            continue
        if mode == "front" and stripped and not stripped.startswith("## ") and not data["subtitle"]:
            data["subtitle"] = stripped
            continue
        if stripped == "## English Title":
            flush()
            mode = "english_title"
            continue
        if stripped == "## 요약":
            flush()
            mode = "summary"
            continue
        if stripped == "## Abstract":
            flush()
            mode = "abstract"
            continue
        if stripped == "## Keywords":
            flush()
            mode = "keywords"
            continue
        if stripped.startswith("## I."):
            flush()
            mode = "body"
            data["body"].append(raw)
            continue
        if stripped == "## References":
            flush()
            mode = "references"
            continue
        if mode == "body":
            data["body"].append(raw)
        elif mode == "references":
            data["references"].append(raw)
        elif mode in {"english_title", "summary", "abstract", "keywords"}:
            bucket.append(raw)
    flush()
    return data


def make_styles(fonts: dict[str, str]) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title_ko": ParagraphStyle(
            "title_ko",
            parent=base["Title"],
            fontName=fonts["ko_bold"],
            fontSize=17,
            leading=22,
            alignment=TA_CENTER,
            spaceBefore=12,
            spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["BodyText"],
            fontName=fonts["ko"],
            fontSize=10,
            leading=13,
            alignment=TA_CENTER,
            spaceAfter=12,
        ),
        "title_en": ParagraphStyle(
            "title_en",
            parent=base["Title"],
            fontName=fonts["en_bold"],
            fontSize=15,
            leading=18,
            alignment=TA_CENTER,
            spaceAfter=14,
        ),
        "front_heading": ParagraphStyle(
            "front_heading",
            parent=base["Heading2"],
            fontName=fonts["ko"],
            fontSize=9.2,
            leading=13,
            alignment=TA_CENTER,
            spaceBefore=8,
            spaceAfter=6,
        ),
        "summary": ParagraphStyle(
            "summary",
            parent=base["BodyText"],
            fontName=fonts["ko"],
            fontSize=9.2,
            leading=13.8,
            alignment=TA_JUSTIFY,
            firstLineIndent=10,
            spaceAfter=7,
        ),
        "abstract": ParagraphStyle(
            "abstract",
            parent=base["BodyText"],
            fontName=fonts["en"],
            fontSize=9.2,
            leading=13.8,
            alignment=TA_JUSTIFY,
            firstLineIndent=10,
            spaceAfter=7,
        ),
        "keywords": ParagraphStyle(
            "keywords",
            parent=base["BodyText"],
            fontName=fonts["en"],
            fontSize=9.2,
            leading=13,
            alignment=TA_LEFT,
            spaceBefore=4,
        ),
        "section": ParagraphStyle(
            "section",
            parent=base["Heading1"],
            fontName=fonts["ko"],
            fontSize=11,
            leading=16.5,
            alignment=TA_CENTER,
            spaceBefore=10,
            spaceAfter=8,
        ),
        "subsection": ParagraphStyle(
            "subsection",
            parent=base["Heading2"],
            fontName=fonts["ko_bold"],
            fontSize=10,
            leading=15,
            alignment=TA_LEFT,
            spaceBefore=8,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontName=fonts["ko"],
            fontSize=9.6,
            leading=14.4,
            alignment=TA_JUSTIFY,
            firstLineIndent=10,
            spaceAfter=3,
        ),
        "table_caption": ParagraphStyle(
            "table_caption",
            parent=base["BodyText"],
            fontName=fonts["ko"],
            fontSize=8.2,
            leading=10,
            alignment=TA_CENTER,
            spaceBefore=6,
            spaceAfter=1,
        ),
        "table_caption_en": ParagraphStyle(
            "table_caption_en",
            parent=base["BodyText"],
            fontName=fonts["en"],
            fontSize=8.0,
            leading=10,
            alignment=TA_CENTER,
            spaceAfter=3,
        ),
        "figure_caption": ParagraphStyle(
            "figure_caption",
            parent=base["BodyText"],
            fontName=fonts["ko"],
            fontSize=8.2,
            leading=10,
            alignment=TA_CENTER,
            spaceBefore=2,
            spaceAfter=0,
        ),
        "figure_caption_en": ParagraphStyle(
            "figure_caption_en",
            parent=base["BodyText"],
            fontName=fonts["en"],
            fontSize=8.0,
            leading=10,
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "table_cell": ParagraphStyle(
            "table_cell",
            parent=base["BodyText"],
            fontName=fonts["en"],
            fontSize=5.8,
            leading=7.0,
            alignment=TA_CENTER,
        ),
        "table_head": ParagraphStyle(
            "table_head",
            parent=base["BodyText"],
            fontName=fonts["en_bold"],
            fontSize=5.8,
            leading=7.0,
            alignment=TA_CENTER,
        ),
        "refs_heading": ParagraphStyle(
            "refs_heading",
            parent=base["Heading1"],
            fontName=fonts["en"],
            fontSize=11,
            leading=16.5,
            alignment=TA_CENTER,
            spaceBefore=10,
            spaceAfter=8,
        ),
        "reference": ParagraphStyle(
            "reference",
            parent=base["BodyText"],
            fontName=fonts["en"],
            fontSize=8.1,
            leading=11.5,
            alignment=TA_LEFT,
            leftIndent=15,
            firstLineIndent=-15,
            spaceAfter=4,
        ),
    }


def paragraph_from_buffer(story: list, buffer: list[str], style: ParagraphStyle) -> None:
    if not buffer:
        return
    text = " ".join(part.strip() for part in buffer if part.strip())
    buffer.clear()
    if text:
        story.append(Paragraph(clean_inline(text), style))


def append_table(
    story: list,
    table_lines: list[str],
    styles: dict[str, ParagraphStyle],
    table_no: int,
    caption: str,
) -> int:
    rows = [split_table_row(line) for line in table_lines if not is_table_separator(line)]
    if not rows:
        return table_no
    max_cols = max(len(row) for row in rows)
    for row in rows:
        row.extend([""] * (max_cols - len(row)))
    ko_caption, en_caption = split_caption(caption)
    flowables = [
        Paragraph(f"표 {table_no}. {clean_inline(ko_caption)}", styles["table_caption"]),
    ]
    if en_caption:
        flowables.append(Paragraph(f"Table {table_no}. {clean_inline(en_caption)}", styles["table_caption_en"]))
    data = []
    for idx, row in enumerate(rows):
        cell_style = styles["table_head"] if idx == 0 else styles["table_cell"]
        data.append([Paragraph(clean_inline(cell), cell_style) for cell in row])
    table = Table(data, colWidths=[COL_W / max_cols] * max_cols, repeatRows=1, hAlign="CENTER")
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1.0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1.0),
                ("TOPPADDING", (0, 0), (-1, -1), 1.2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
            ]
        )
    )
    flowables.extend([table, Spacer(1, 4)])
    story.append(KeepTogether(flowables))
    return table_no + 1


def append_image(story: list, line: str, styles: dict[str, ParagraphStyle], fig_no: int) -> int:
    match = re.match(r"!\[(.*?)\]\((.*?)\)", line.strip())
    if not match:
        return fig_no
    caption, path_text = match.groups()
    ko_caption, en_caption = split_caption(caption)
    image_path = resolve_image_path(path_text)
    if not image_path.exists():
        story.append(Paragraph(f"[Missing figure: {clean_inline(path_text)}]", styles["figure_caption"]))
        return fig_no
    img = Image(str(image_path))
    max_h = 45 * mm
    if "S1-S3" in ko_caption or "S4-S6" in ko_caption:
        max_h = 36 * mm
    scale = min(COL_W / img.imageWidth, max_h / img.imageHeight, 1.0)
    img.drawWidth = img.imageWidth * scale
    img.drawHeight = img.imageHeight * scale
    flowables = [
        Spacer(1, 3),
        img,
        Paragraph(f"그림 {fig_no}. {clean_inline(ko_caption)}", styles["figure_caption"]),
    ]
    if en_caption:
        flowables.append(Paragraph(f"Fig. {fig_no}. {clean_inline(en_caption)}", styles["figure_caption_en"]))
    story.append(KeepTogether(flowables))
    return fig_no + 1


def append_body_lines(story: list, body_lines: list[str], references: list[str], styles: dict[str, ParagraphStyle]) -> None:
    buffer: list[str] = []
    table_buffer: list[str] = []
    table_caption = ""
    table_no = 1
    fig_no = 1

    for raw in body_lines:
        stripped = raw.strip()
        if table_buffer and not stripped.startswith("|"):
            table_no = append_table(story, table_buffer, styles, table_no, table_caption)
            table_buffer = []
            table_caption = ""
        if not stripped:
            paragraph_from_buffer(story, buffer, styles["body"])
            continue
        if stripped.startswith("## "):
            paragraph_from_buffer(story, buffer, styles["body"])
            story.append(Paragraph(clean_inline(stripped[3:]), styles["section"]))
        elif stripped.startswith("### "):
            paragraph_from_buffer(story, buffer, styles["body"])
            story.append(Paragraph(clean_inline(stripped[4:]), styles["subsection"]))
        elif stripped.startswith("[표]"):
            paragraph_from_buffer(story, buffer, styles["body"])
            table_caption = stripped.replace("[표]", "", 1).strip()
        elif stripped.startswith("|"):
            table_buffer.append(stripped)
        elif stripped.startswith("!["):
            paragraph_from_buffer(story, buffer, styles["body"])
            fig_no = append_image(story, stripped, styles, fig_no)
        else:
            buffer.append(stripped)

    if table_buffer:
        append_table(story, table_buffer, styles, table_no, table_caption)
    paragraph_from_buffer(story, buffer, styles["body"])
    story.append(Paragraph("References", styles["refs_heading"]))

    ref_buffer: list[str] = []
    for raw in references:
        stripped = raw.strip()
        if not stripped:
            paragraph_from_buffer(story, ref_buffer, styles["reference"])
        else:
            ref_buffer.append(stripped)
    paragraph_from_buffer(story, ref_buffer, styles["reference"])


def make_story(data: dict[str, object], styles: dict[str, ParagraphStyle]) -> list:
    story: list = [
        Paragraph(clean_inline(str(data["title"])), styles["title_ko"]),
        Paragraph(clean_inline(str(data["subtitle"])), styles["subtitle"]),
        Paragraph(clean_inline(str(data["english_title"])), styles["title_en"]),
        HRFlowable(width="100%", thickness=0.6, color=colors.black, spaceBefore=2, spaceAfter=8),
        Paragraph("요&nbsp;&nbsp;약", styles["front_heading"]),
        Paragraph(clean_inline(str(data["summary"])), styles["summary"]),
        Paragraph("Abstract", styles["front_heading"]),
        Paragraph(clean_inline(str(data["abstract"])), styles["abstract"]),
        Paragraph("<b>Keywords:</b> " + clean_inline(str(data["keywords"])), styles["keywords"]),
        HRFlowable(width="100%", thickness=0.4, color=colors.black, spaceBefore=10, spaceAfter=0),
        NextPageTemplate("Body"),
        PageBreak(),
    ]
    append_body_lines(story, data["body"], data["references"], styles)
    return story


def draw_header(canvas, doc) -> None:
    canvas.saveState()
    page_no = doc.page
    canvas.setFont("TimesNewRoman" if "TimesNewRoman" in pdfmetrics.getRegisteredFontNames() else "Times-Roman", 8)
    y = PAGE_H - 9.5 * mm
    if page_no % 2 == 1:
        text = (
            "Journal of KIIT. Vol. 23, No. 0, pp. 00-00, 00 (0), 2025. "
            "pISSN 1598-8619, eISSN 2093-7571"
        )
        canvas.drawCentredString(PAGE_W / 2, y, text)
        canvas.drawRightString(PAGE_W - RIGHT, y, str(page_no))
    else:
        canvas.drawString(LEFT, y, str(page_no))
        canvas.setFont("AppleMyungjo" if "AppleMyungjo" in pdfmetrics.getRegisteredFontNames() else "Times-Roman", 8)
        canvas.drawString(LEFT + 7 * mm, y, "eVTOL 이동성 모델 시뮬레이터 구현 및 충돌 회피 성능 분석")
    canvas.restoreState()


def main() -> None:
    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    fonts = register_fonts()
    styles = make_styles(fonts)
    first_frame = Frame(LEFT, BOTTOM, CONTENT_W, PAGE_H - TOP - BOTTOM, id="front")
    left_frame = Frame(LEFT, BOTTOM, COL_W, PAGE_H - TOP - BOTTOM, id="left")
    right_frame = Frame(LEFT + COL_W + GUTTER, BOTTOM, COL_W, PAGE_H - TOP - BOTTOM, id="right")
    doc = BaseDocTemplate(
        str(OUTPUT_PDF),
        pagesize=(PAGE_W, PAGE_H),
        leftMargin=LEFT,
        rightMargin=RIGHT,
        topMargin=TOP,
        bottomMargin=BOTTOM,
        title="eVTOL KIIT Style Draft",
    )
    doc.addPageTemplates(
        [
            PageTemplate(id="Front", frames=[first_frame], onPage=draw_header),
            PageTemplate(id="Body", frames=[left_frame, right_frame], onPage=draw_header),
        ]
    )
    data = parse_markdown(INPUT_MD.read_text(encoding="utf-8"))
    doc.build(make_story(data, styles))
    print(OUTPUT_PDF)


if __name__ == "__main__":
    main()
