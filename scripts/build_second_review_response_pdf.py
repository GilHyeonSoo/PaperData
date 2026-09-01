from __future__ import annotations

import html
import re
from dataclasses import dataclass
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
    Flowable,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "PAPER_SECOND_REVIEW.md"
OUTPUT = ROOT / "output" / "pdf" / "PAPER_SECOND_REVIEW.pdf"

INK = colors.HexColor("#1f2937")
NAVY = colors.HexColor("#1f4e79")
MUTED = colors.HexColor("#5f6b78")
BORDER = colors.HexColor("#d7dee7")
COMMENT_BG = colors.HexColor("#f3f6fa")
LOCATION_BG = colors.HexColor("#f8fafc")


@dataclass
class ReviewItem:
    number: str
    comment: str
    response: str
    location_label: str
    location: str


@dataclass
class ReviewerSection:
    title: str
    items: list[ReviewItem]


def register_font() -> str:
    candidates = [
        Path("/Users/apple/Library/Fonts/NotoSansKR-VariableFont_wght.ttf"),
        Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            pdfmetrics.registerFont(TTFont("ResponseKorean", str(candidate)))
            return "ResponseKorean"
    raise FileNotFoundError("A Korean TrueType font could not be found.")


FONT = register_font()
SAMPLE = getSampleStyleSheet()

STYLES = {
    "title": ParagraphStyle(
        "ResponseTitle",
        parent=SAMPLE["Title"],
        fontName=FONT,
        fontSize=18,
        leading=25,
        textColor=INK,
        alignment=TA_CENTER,
        spaceAfter=4 * mm,
        wordWrap="CJK",
    ),
    "subtitle": ParagraphStyle(
        "ResponseSubtitle",
        parent=SAMPLE["BodyText"],
        fontName=FONT,
        fontSize=9,
        leading=13,
        textColor=MUTED,
        alignment=TA_CENTER,
        spaceAfter=8 * mm,
        wordWrap="CJK",
    ),
    "reviewer": ParagraphStyle(
        "ReviewerHeading",
        parent=SAMPLE["Heading2"],
        fontName=FONT,
        fontSize=14,
        leading=19,
        textColor=NAVY,
        spaceBefore=1 * mm,
        spaceAfter=0,
        keepWithNext=True,
        wordWrap="CJK",
    ),
    "comment_label": ParagraphStyle(
        "CommentLabel",
        parent=SAMPLE["BodyText"],
        fontName=FONT,
        fontSize=8.5,
        leading=12,
        textColor=NAVY,
        spaceAfter=1.2 * mm,
        wordWrap="CJK",
    ),
    "comment": ParagraphStyle(
        "Comment",
        parent=SAMPLE["BodyText"],
        fontName=FONT,
        fontSize=9.6,
        leading=15.2,
        textColor=INK,
        alignment=TA_LEFT,
        wordWrap="CJK",
    ),
    "label": ParagraphStyle(
        "FieldLabel",
        parent=SAMPLE["BodyText"],
        fontName=FONT,
        fontSize=9.1,
        leading=14.8,
        textColor=NAVY,
        wordWrap="CJK",
    ),
    "body": ParagraphStyle(
        "ResponseBody",
        parent=SAMPLE["BodyText"],
        fontName=FONT,
        fontSize=9.5,
        leading=15.8,
        textColor=INK,
        alignment=TA_LEFT,
        wordWrap="CJK",
    ),
    "location": ParagraphStyle(
        "Location",
        parent=SAMPLE["BodyText"],
        fontName=FONT,
        fontSize=8.8,
        leading=14.2,
        textColor=INK,
        alignment=TA_LEFT,
        wordWrap="CJK",
    ),
}


def markup(text: str) -> str:
    escaped = html.escape(text)
    return re.sub(
        r"`([^`]+)`",
        rf'<font name="{FONT}" color="#1f4e79">\1</font>',
        escaped,
    )


def parse_source(text: str) -> tuple[str, list[ReviewerSection]]:
    title = "2차 심사의견 답변 및 논문 반영 위치"
    sections: list[ReviewerSection] = []
    current_section: ReviewerSection | None = None
    current_item: ReviewItem | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("# "):
            title = line[2:].strip()
            continue

        if line.startswith("### "):
            current_section = ReviewerSection(title=line[4:].strip(), items=[])
            sections.append(current_section)
            current_item = None
            continue

        item_match = re.match(r"^(\d+)\.\s+(.+)$", line)
        if item_match and current_section is not None:
            current_item = ReviewItem(
                number=item_match.group(1),
                comment=item_match.group(2).strip(),
                response="",
                location_label="논문 반영 위치",
                location="",
            )
            current_section.items.append(current_item)
            continue

        response_match = re.match(r"^\s+-\s+답변:\s*(.+)$", line)
        if response_match and current_item is not None:
            current_item.response = response_match.group(1).strip()
            continue

        location_match = re.match(r"^\s+-\s+(논문\s+.+?위치):\s*(.+)$", line)
        if location_match and current_item is not None:
            current_item.location_label = location_match.group(1).strip()
            current_item.location = location_match.group(2).strip()

    if not sections or any(not section.items for section in sections):
        raise ValueError("The Markdown review structure could not be parsed.")
    return title, sections


def reviewer_heading(title: str) -> Table:
    heading = Paragraph(markup(title), STYLES["reviewer"])
    table = Table(
        [["", heading]],
        colWidths=[3 * mm, 167 * mm],
        style=[
            ("BACKGROUND", (0, 0), (0, 0), NAVY),
            ("BACKGROUND", (1, 0), (1, 0), COMMENT_BG),
            ("BOX", (1, 0), (1, 0), 0.4, BORDER),
            ("LEFTPADDING", (0, 0), (0, 0), 0),
            ("RIGHTPADDING", (0, 0), (0, 0), 0),
            ("LEFTPADDING", (1, 0), (1, 0), 8),
            ("RIGHTPADDING", (1, 0), (1, 0), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ],
        hAlign="LEFT",
    )
    table.keepWithNext = True
    table.bookmark_title = title
    return table


def review_item_card(item: ReviewItem) -> Flowable:
    comment_content = [
        Paragraph(markup(f"심사의견 {item.number}"), STYLES["comment_label"]),
        Paragraph(markup(item.comment), STYLES["comment"]),
    ]
    comment = Table(
        [[comment_content]],
        colWidths=[164 * mm],
        style=[
            ("BACKGROUND", (0, 0), (-1, -1), COMMENT_BG),
            ("BOX", (0, 0), (-1, -1), 0.4, BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ],
        hAlign="LEFT",
    )

    response = Table(
        [
            [
                Paragraph(markup("답변"), STYLES["label"]),
                Paragraph(markup(item.response), STYLES["body"]),
            ]
        ],
        colWidths=[19 * mm, 145 * mm],
        style=[
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.35, BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ],
        hAlign="LEFT",
    )

    location = Table(
        [
            [
                Paragraph(markup(item.location_label), STYLES["label"]),
                Paragraph(markup(item.location), STYLES["location"]),
            ]
        ],
        colWidths=[33 * mm, 131 * mm],
        style=[
            ("BACKGROUND", (0, 0), (-1, -1), LOCATION_BG),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ],
        hAlign="LEFT",
    )

    body = Table(
        [[response], [location]],
        colWidths=[164 * mm],
        style=[
            ("BOX", (0, 0), (-1, -1), 0.4, BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ],
        hAlign="LEFT",
    )

    return KeepTogether(
        [
            comment,
            Spacer(1, 2.2 * mm),
            body,
            Spacer(1, 5 * mm),
        ]
    )


class ResponseDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str):
        super().__init__(
            filename,
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=18 * mm,
            title="2차 심사의견 답변 및 논문 반영 위치",
            author="eVTOLPaper",
            subject="2차 논문 심사의견 답변서",
        )
        frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="response",
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        self.addPageTemplates(
            [PageTemplate(id="response", frames=[frame], onPage=draw_page)]
        )

    def afterFlowable(self, flowable: Flowable) -> None:
        title = getattr(flowable, "bookmark_title", None)
        if not title:
            return
        bookmark = re.sub(r"[^0-9A-Za-z가-힣]+", "_", title).strip("_")
        self.canv.bookmarkPage(bookmark)
        self.canv.addOutlineEntry(title, bookmark, level=0, closed=False)


def draw_page(canvas, doc) -> None:
    width, height = A4
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.35)
    canvas.line(20 * mm, height - 13 * mm, width - 20 * mm, height - 13 * mm)
    canvas.line(20 * mm, 13 * mm, width - 20 * mm, 13 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont(FONT, 7.8)
    canvas.drawString(20 * mm, height - 10 * mm, "2차 논문 심사의견 답변서")
    canvas.drawRightString(width - 20 * mm, 9 * mm, str(doc.page))
    canvas.restoreState()


def main() -> None:
    title, sections = parse_source(SOURCE.read_text(encoding="utf-8"))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    story: list[Flowable] = [
        Spacer(1, 3 * mm),
        Paragraph(markup(title), STYLES["title"]),
        Paragraph(
            markup("심사위원별 의견에 대한 답변과 논문 반영 위치"),
            STYLES["subtitle"],
        ),
    ]
    for section_index, section in enumerate(sections):
        if section_index:
            story.append(Spacer(1, 2 * mm))
        story.append(
            KeepTogether(
                [
                    reviewer_heading(section.title),
                    Spacer(1, 5 * mm),
                    review_item_card(section.items[0]),
                ]
            )
        )
        for item in section.items[1:]:
            story.append(review_item_card(item))

    doc = ResponseDocTemplate(str(OUTPUT))
    doc.build(story)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
