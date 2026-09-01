from __future__ import annotations

import html
import re
import textwrap
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Flowable,
    Frame,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "REPORT.md"
OUTPUT = ROOT / "REPORT.pdf"
TMP_DIR = ROOT / "tmp" / "pdfs"

NAVY = colors.HexColor("#1e3a8a")
INK = colors.HexColor("#1e293b")
MUTED = colors.HexColor("#64748b")
LIGHT_BG = colors.HexColor("#f8fafc")
WARM_BG = colors.HexColor("#faf8f5")
BORDER = colors.HexColor("#e2e8f0")
CODE_BG = colors.HexColor("#f1f5f9")
ROW_ALT = colors.HexColor("#fbfdff")

TOC_DESCRIPTIONS = {
    "1. 시뮬레이터 개요 및 목적 (Introduction & Objectives)": "시뮬레이터의 목적, 구현 범위, 실행 경로와 파일 구성을 빠르게 파악한다.",
    "2. 핵심 알고리즘 및 작동 원리 (Core Algorithms & Mathematical Principles)": "좌표계, 맵 생성, 건물 회피, trajectory 생성, 충돌 판정, seed 구조를 설명한다.",
    "3. 비행 물체 간 충돌 회피 메커니즘 (Collision Avoidance Mechanics)": "time bucket 기반 위험 인지와 출발 지연·고도 변경 후보 선택 방식을 설명한다.",
    "4. 시뮬레이션 진행 프로세스 및 실행 순서 (Execution Sequence & Process Flow)": "기본 sweep, 단일 실험, 연속 시나리오, 병렬 반복 실행 흐름을 정리한다.",
    "5. 우선순위 및 스케줄링 결정 로직 (Ordering & Priority Determination)": "mission 처리 순서, 기체 선택, 경로 후보와 패드 선점 우선순위를 설명한다.",
    "6. 핵심 컴포넌트 및 기능 레퍼런스 (Component Reference)": "파일별 클래스·함수 역할과 핵심 설정 파라미터를 찾기 쉽게 정리한다.",
    "7. OS별 크로스 플랫폼 실행 명령어 가이드라인 (Multi-OS Execution Guide)": "Windows와 macOS에서 바로 실행할 수 있는 설정·실행 명령어를 제공한다.",
    "8. 그 외 추가로 더 설명해야 할 부분": "확장 방향, 검증 절차, 성능 병목, run 수 해석 등 운영 팁을 정리한다.",
}


def register_fonts() -> tuple[str, str]:
    korean_candidates = [
        Path("/Users/apple/Library/Fonts/NotoSansKR-VariableFont_wght.ttf"),
        Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
    ]
    mono_candidates = [
        Path("/System/Library/Fonts/Supplemental/Andale Mono.ttf"),
        Path("/Library/Fonts/Andale Mono.ttf"),
    ]

    body_font = "Helvetica"
    for font_path in korean_candidates:
        if font_path.exists():
            pdfmetrics.registerFont(TTFont("ReportBody", str(font_path)))
            body_font = "ReportBody"
            break

    mono_font = "Courier"
    for font_path in mono_candidates:
        if font_path.exists():
            try:
                pdfmetrics.registerFont(TTFont("ReportMono", str(font_path)))
                mono_font = "ReportMono"
                break
            except Exception:
                pass

    return body_font, mono_font


BODY_FONT, MONO_FONT = register_fonts()


def make_styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=sample["Title"],
            fontName=BODY_FONT,
            fontSize=22,
            leading=30,
            textColor=INK,
            alignment=TA_CENTER,
            spaceAfter=8,
            wordWrap="CJK",
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=sample["BodyText"],
            fontName=BODY_FONT,
            fontSize=10.5,
            leading=17,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=18,
            wordWrap="CJK",
        ),
        "toc_title": ParagraphStyle(
            "TocTitle",
            parent=sample["Heading1"],
            fontName=BODY_FONT,
            fontSize=18,
            leading=25,
            textColor=INK,
            alignment=TA_CENTER,
            spaceBefore=14,
            spaceAfter=8,
            wordWrap="CJK",
        ),
        "toc_note": ParagraphStyle(
            "TocNote",
            parent=sample["BodyText"],
            fontName=BODY_FONT,
            fontSize=9.4,
            leading=14.5,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=12,
            wordWrap="CJK",
        ),
        "toc_cell": ParagraphStyle(
            "TocCell",
            parent=sample["BodyText"],
            fontName=BODY_FONT,
            fontSize=8.5,
            leading=12.2,
            textColor=INK,
            wordWrap="CJK",
        ),
        "toc_page": ParagraphStyle(
            "TocPage",
            parent=sample["BodyText"],
            fontName=BODY_FONT,
            fontSize=9,
            leading=12.2,
            textColor=INK,
            alignment=TA_CENTER,
            wordWrap="CJK",
        ),
        "h2": ParagraphStyle(
            "Heading2Text",
            parent=sample["Heading2"],
            fontName=BODY_FONT,
            fontSize=15,
            leading=20,
            textColor=INK,
            spaceBefore=0,
            spaceAfter=0,
            keepWithNext=True,
            wordWrap="CJK",
        ),
        "h3": ParagraphStyle(
            "Heading3Text",
            parent=sample["Heading3"],
            fontName=BODY_FONT,
            fontSize=12,
            leading=17,
            textColor=NAVY,
            spaceBefore=10,
            spaceAfter=5,
            keepWithNext=False,
            wordWrap="CJK",
        ),
        "body": ParagraphStyle(
            "Body",
            parent=sample["BodyText"],
            fontName=BODY_FONT,
            fontSize=10.3,
            leading=16.8,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=5,
            wordWrap="CJK",
        ),
        "small": ParagraphStyle(
            "Small",
            parent=sample["BodyText"],
            fontName=BODY_FONT,
            fontSize=8.5,
            leading=12.5,
            textColor=INK,
            wordWrap="CJK",
        ),
        "code": ParagraphStyle(
            "Code",
            parent=sample["Code"],
            fontName=MONO_FONT,
            fontSize=7.4,
            leading=10.6,
            textColor=colors.HexColor("#0f172a"),
            wordWrap="CJK",
        ),
        "code_kr": ParagraphStyle(
            "CodeKorean",
            parent=sample["Code"],
            fontName=BODY_FONT,
            fontSize=7.6,
            leading=11.0,
            textColor=colors.HexColor("#0f172a"),
            wordWrap="CJK",
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=sample["BodyText"],
            fontName=BODY_FONT,
            fontSize=8.3,
            leading=11.5,
            textColor=colors.white,
            alignment=TA_CENTER,
            wordWrap="CJK",
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            parent=sample["BodyText"],
            fontName=BODY_FONT,
            fontSize=8.2,
            leading=12.0,
            textColor=INK,
            wordWrap="CJK",
        ),
    }


STYLES = make_styles()


class SectionBreak(Flowable):
    def __init__(self, height: float = 3.5 * mm):
        super().__init__()
        self.height = height

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        return avail_width, self.height

    def draw(self) -> None:
        self.canv.setStrokeColor(BORDER)
        self.canv.setLineWidth(0.35)
        self.canv.line(0, self.height / 2, self.width, self.height / 2)


def inline_markup(text: str) -> str:
    escaped = html.escape(text)

    def code_repl(match: re.Match[str]) -> str:
        value = match.group(1)
        return f'<font name="{MONO_FONT}" color="#0f172a">{value}</font>'

    escaped = re.sub(r"`([^`]+)`", code_repl, escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)
    return escaped


def paragraph(text: str, style_name: str = "body") -> Paragraph:
    return Paragraph(inline_markup(text), STYLES[style_name])


def h2_block(text: str) -> Table:
    heading = Paragraph(inline_markup(text), STYLES["h2"])
    table = Table(
        [["", heading]],
        colWidths=[5 * mm, 160 * mm],
        style=[
            ("BACKGROUND", (0, 0), (0, 0), NAVY),
            ("BACKGROUND", (1, 0), (1, 0), LIGHT_BG),
            ("LEFTPADDING", (0, 0), (0, 0), 0),
            ("RIGHTPADDING", (0, 0), (0, 0), 0),
            ("LEFTPADDING", (1, 0), (1, 0), 9),
            ("RIGHTPADDING", (1, 0), (1, 0), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("BOX", (1, 0), (1, 0), 0.25, BORDER),
        ],
        hAlign="LEFT",
    )
    table.keepWithNext = True
    table.toc_title = text
    return table


def toc_page(page_numbers: dict[str, int] | None = None) -> list[Flowable]:
    page_numbers = page_numbers or {}
    rows: list[list[Paragraph]] = [
        [
            Paragraph(inline_markup("대주제"), STYLES["table_header"]),
            Paragraph(inline_markup("해설"), STYLES["table_header"]),
            Paragraph(inline_markup("페이지"), STYLES["table_header"]),
        ]
    ]
    for title, description in TOC_DESCRIPTIONS.items():
        page_value = str(page_numbers.get(title, "-"))
        rows.append(
            [
                Paragraph(inline_markup(title), STYLES["toc_cell"]),
                Paragraph(inline_markup(description), STYLES["toc_cell"]),
                Paragraph(inline_markup(page_value), STYLES["toc_page"]),
            ]
        )

    table_style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    for row_index in range(1, len(rows)):
        if row_index % 2 == 0:
            table_style.append(("BACKGROUND", (0, row_index), (-1, row_index), ROW_ALT))

    table = Table(
        rows,
        colWidths=[58 * mm, 86 * mm, 21 * mm],
        repeatRows=1,
        style=table_style,
        hAlign="LEFT",
    )
    return [
        Paragraph(inline_markup("목차"), STYLES["toc_title"]),
        Paragraph(
            inline_markup("각 대주제가 시작되는 페이지와 해당 장에서 확인할 수 있는 핵심 내용을 함께 정리하였다."),
            STYLES["toc_note"],
        ),
        table,
    ]


def code_box(lines: list[str]) -> Flowable:
    code_text = "\n".join(lines).rstrip("\n")
    has_korean = any(ord(ch) > 127 for ch in code_text)
    style = STYLES["code_kr"] if has_korean else STYLES["code"]
    wrapped_lines: list[str] = []
    for line in code_text.splitlines() or [""]:
        if len(line) <= 96:
            wrapped_lines.append(line)
        else:
            wrapped_lines.extend(textwrap.wrap(line, width=96, break_long_words=False, replace_whitespace=False))
    safe = html.escape("\n".join(wrapped_lines))
    safe = safe.replace("\n", "<br/>")
    inner = Paragraph(safe, style)
    table = Table(
        [[inner]],
        colWidths=[165 * mm],
        style=[
            ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
            ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor("#cbd5e1")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ],
        hAlign="LEFT",
    )
    if len(wrapped_lines) <= 18:
        return KeepTogether([table, Spacer(1, 5)])
    return table


def markdown_table(rows: list[str]) -> Flowable:
    parsed: list[list[str]] = []
    for raw in rows:
        stripped = raw.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        parsed.append(cells)

    if not parsed:
        return Spacer(1, 0)

    max_cols = max(len(row) for row in parsed)
    normalized = [row + [""] * (max_cols - len(row)) for row in parsed]
    data = []
    for r_index, row in enumerate(normalized):
        style = "table_header" if r_index == 0 else "table_cell"
        data.append([Paragraph(inline_markup(cell), STYLES[style]) for cell in row])

    page_width = 165 * mm
    if max_cols == 2:
        col_widths = [45 * mm, page_width - 45 * mm]
    elif max_cols == 3:
        col_widths = [45 * mm, 60 * mm, page_width - 105 * mm]
    elif max_cols == 4:
        col_widths = [35 * mm, 43 * mm, 43 * mm, page_width - 121 * mm]
    else:
        col_widths = [page_width / max_cols] * max_cols

    table_style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for row_index in range(1, len(data)):
        if row_index % 2 == 0:
            table_style.append(("BACKGROUND", (0, row_index), (-1, row_index), ROW_ALT))

    table = Table(data, colWidths=col_widths, repeatRows=1, style=table_style, hAlign="LEFT")
    if len(data) <= 10:
        return KeepTogether([table, Spacer(1, 6)])
    return table


def list_block(items: list[tuple[str, str]]) -> Flowable:
    flowables: list[ListItem] = []
    for marker, text in items:
        bullet = "•" if marker == "-" else f"{marker}."
        flowables.append(
            ListItem(
                paragraph(text, "body"),
                bulletText=bullet,
                leftIndent=14,
                bulletFontName=BODY_FONT,
                bulletFontSize=8.8,
            )
        )
    return ListFlowable(flowables, bulletType="bullet", leftIndent=10, spaceAfter=4)


def parse_markdown(markdown: str, page_numbers: dict[str, int] | None = None) -> list[Flowable]:
    story: list[Flowable] = []
    paragraph_lines: list[str] = []
    list_items: list[tuple[str, str]] = []
    code_lines: list[str] | None = None
    table_lines: list[str] = []
    first_h1 = True

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if paragraph_lines:
            text = " ".join(line.strip() for line in paragraph_lines).strip()
            if text:
                story.append(paragraph(text))
            paragraph_lines = []

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            story.append(list_block(list_items))
            list_items = []

    def flush_table() -> None:
        nonlocal table_lines
        if table_lines:
            story.append(markdown_table(table_lines))
            story.append(Spacer(1, 7))
            table_lines = []

    lines = markdown.splitlines()
    for line in lines:
        if line.startswith("```"):
            flush_paragraph()
            flush_list()
            flush_table()
            if code_lines is None:
                code_lines = []
            else:
                story.append(code_box(code_lines))
                story.append(Spacer(1, 6))
                code_lines = None
            continue

        if code_lines is not None:
            code_lines.append(line)
            continue

        if line.strip().startswith("|"):
            flush_paragraph()
            flush_list()
            table_lines.append(line)
            continue
        flush_table()

        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            flush_list()
            continue

        if stripped.startswith("# "):
            flush_paragraph()
            flush_list()
            title = stripped[2:].strip()
            if first_h1:
                story.append(Spacer(1, 8))
                story.append(Paragraph(inline_markup("eVTOL Simulator Technical Guide"), STYLES["title"]))
                story.append(
                    Paragraph(
                        inline_markup("REPORT.md 기반 시스템 구조·실행·확장 가이드"),
                        STYLES["subtitle"],
                    )
                )
                story.append(SectionBreak())
                story.extend(toc_page(page_numbers))
                story.append(PageBreak())
                first_h1 = False
            else:
                story.append(PageBreak())
                story.append(Paragraph(inline_markup(title), STYLES["title"]))
            continue

        if stripped.startswith("## "):
            flush_paragraph()
            flush_list()
            story.append(Spacer(1, 8))
            story.append(h2_block(stripped[3:].strip()))
            story.append(Spacer(1, 7))
            continue

        if stripped.startswith("### "):
            flush_paragraph()
            flush_list()
            story.append(CondPageBreak(35 * mm))
            story.append(Paragraph(inline_markup(stripped[4:].strip()), STYLES["h3"]))
            continue

        bullet_match = re.match(r"^-\s+(.+)$", stripped)
        ordered_match = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        indented_bullet = re.match(r"^\s{2,}-\s+(.+)$", line)
        if bullet_match:
            flush_paragraph()
            list_items.append(("-", bullet_match.group(1)))
            continue
        if ordered_match:
            flush_paragraph()
            list_items.append((ordered_match.group(1), ordered_match.group(2)))
            continue
        if indented_bullet:
            flush_paragraph()
            list_items.append(("-", indented_bullet.group(1)))
            continue

        paragraph_lines.append(line)

    flush_paragraph()
    flush_list()
    flush_table()
    return story


class ReportDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str):
        super().__init__(
            filename,
            pagesize=A4,
            leftMargin=22 * mm,
            rightMargin=22 * mm,
            topMargin=20 * mm,
            bottomMargin=18 * mm,
            title="eVTOL Simulator Technical Guide",
            author="Codex",
        )
        self.section_pages: dict[str, int] = {}
        frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="normal",
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        self.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=draw_page)])

    def afterFlowable(self, flowable: Flowable) -> None:
        title = getattr(flowable, "toc_title", None)
        if not title or title in self.section_pages:
            return
        self.section_pages[title] = self.page
        bookmark = re.sub(r"[^0-9A-Za-z가-힣]+", "_", title).strip("_")
        if bookmark:
            self.canv.bookmarkPage(bookmark)
            self.canv.addOutlineEntry(title, bookmark, level=0, closed=False)


def draw_page(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(colors.HexColor("#f8fafc"))
    canvas.rect(0, height - 12 * mm, width, 12 * mm, stroke=0, fill=1)
    canvas.setFillColor(MUTED)
    canvas.setFont(BODY_FONT, 8)
    canvas.drawString(22 * mm, height - 8 * mm, "eVTOL Simulator Technical Guide")
    canvas.drawRightString(width - 22 * mm, 10 * mm, f"{doc.page}")
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.3)
    canvas.line(22 * mm, 15 * mm, width - 22 * mm, 15 * mm)
    canvas.restoreState()


def main() -> None:
    markdown = SOURCE.read_text(encoding="utf-8")
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    draft_output = TMP_DIR / "REPORT_toc_pass.pdf"

    draft_doc = ReportDocTemplate(str(draft_output))
    draft_doc.build(parse_markdown(markdown))

    story = parse_markdown(markdown, draft_doc.section_pages)
    doc = ReportDocTemplate(str(OUTPUT))
    doc.build(story)
    print(f"Wrote {OUTPUT}")
    print("Section pages:")
    for title in TOC_DESCRIPTIONS:
        print(f"- {title}: {draft_doc.section_pages.get(title, '-')}")


if __name__ == "__main__":
    main()
