from __future__ import annotations

import re
import importlib.util
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    FrameBreak,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
)


ROOT = Path(__file__).resolve().parents[1]
INPUT_MD = ROOT / "paper" / "draft_with_scenario_figures.md"
OUTPUT_PDF = ROOT / "output" / "pdf" / "evtol_paper_conference_two_column_with_scenario_figures.pdf"

BASE_SCRIPT = ROOT / "scripts" / "build_conference_two_column_pdf.py"
spec = importlib.util.spec_from_file_location("conference_pdf_base", BASE_SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot load base PDF builder: {BASE_SCRIPT}")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def _full_width_image_flowables(lines: list[str], styles: dict, full_width: float, fig_no: int) -> tuple[list, int]:
    flowables: list = []
    count = len(lines)
    for line in lines:
        match = re.match(r"!\[(.*?)\]\((.*?)\)", line.strip())
        if not match:
            continue
        alt, path_text = match.groups()
        caption = alt.replace("FULL:", "", 1).strip()
        image_path = base.resolve_image_path(path_text)
        if not image_path.exists():
            flowables.append(Paragraph(f"[Missing figure: {base.clean_inline(path_text)}]", styles["caption"]))
            continue

        img = Image(str(image_path))
        max_w = full_width * 0.98
        max_h = 60 * mm if count > 1 else 118 * mm
        scale = min(max_w / img.imageWidth, max_h / img.imageHeight, 1.0)
        img.drawWidth = img.imageWidth * scale
        img.drawHeight = img.imageHeight * scale
        flowables.extend(
            [
                Spacer(1, 2),
                img,
                Paragraph(f"그림 {fig_no}. {base.clean_inline(caption)}", styles["caption"]),
            ]
        )
        fig_no += 1
    return flowables, fig_no


def append_full_width_images(story: list, lines: list[str], styles: dict, full_width: float, fig_no: int) -> int:
    flowables, fig_no = _full_width_image_flowables(lines, styles, full_width, fig_no)
    if not flowables:
        return fig_no

    story.extend(
        [
            NextPageTemplate("FigurePage"),
            PageBreak(),
            KeepTogether(flowables),
            FrameBreak(),
            NextPageTemplate("Later"),
        ]
    )
    return fig_no


def append_full_width_image(story: list, line: str, styles: dict, full_width: float, fig_no: int) -> int:
    match = re.match(r"!\[(.*?)\]\((.*?)\)", line.strip())
    if not match:
        return fig_no
    alt, path_text = match.groups()
    caption = alt.replace("FULL:", "", 1).strip()
    image_path = base.resolve_image_path(path_text)
    if not image_path.exists():
        story.append(Paragraph(f"[Missing figure: {base.clean_inline(path_text)}]", styles["caption"]))
        return fig_no

    img = Image(str(image_path))
    max_w = full_width * 0.98
    max_h = 118 * mm
    scale = min(max_w / img.imageWidth, max_h / img.imageHeight, 1.0)
    img.drawWidth = img.imageWidth * scale
    img.drawHeight = img.imageHeight * scale

    story.extend(
        [
            NextPageTemplate("FigurePage"),
            PageBreak(),
            KeepTogether(
                [
                    Spacer(1, 2),
                    img,
                    Paragraph(f"그림 {fig_no}. {base.clean_inline(caption)}", styles["caption"]),
                ]
            ),
            FrameBreak(),
            NextPageTemplate("Later"),
        ]
    )
    return fig_no + 1


def build_body_story_with_full_images(body_md: str, styles: dict, col_width: float, full_width: float) -> list:
    story: list = []
    para_buffer: list[str] = []
    table_buffer: list[str] = []
    fig_no = 1
    in_refs = False

    lines = body_md.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()

        if table_buffer and not line.strip().startswith("|"):
            base.flush_paragraph(story, para_buffer, styles, in_refs)
            base.append_table(story, table_buffer, styles, col_width)
            table_buffer = []

        if not line.strip():
            base.flush_paragraph(story, para_buffer, styles, in_refs)
            i += 1
            continue

        if line.strip().startswith("|"):
            base.flush_paragraph(story, para_buffer, styles, in_refs)
            table_buffer.append(line)
            i += 1
            continue

        if line.startswith("![FULL:"):
            base.flush_paragraph(story, para_buffer, styles, in_refs)
            full_lines = [line]
            i += 1
            while i < len(lines):
                next_line = lines[i].rstrip()
                if not next_line.strip():
                    i += 1
                    continue
                if next_line.startswith("![FULL:"):
                    full_lines.append(next_line)
                    i += 1
                    continue
                break
            fig_no = append_full_width_images(story, full_lines, styles, full_width, fig_no)
            continue

        if line.startswith("!["):
            base.flush_paragraph(story, para_buffer, styles, in_refs)
            fig_no = base.append_image(story, line, styles, col_width, fig_no)
            i += 1
            continue

        if line.startswith("## "):
            base.flush_paragraph(story, para_buffer, styles, in_refs)
            heading = base.transform_heading(line)
            if heading == "참 고 문 헌":
                in_refs = True
            story.append(Paragraph(base.clean_inline(heading), styles["section"]))
            i += 1
            continue

        if line.startswith("### "):
            base.flush_paragraph(story, para_buffer, styles, in_refs)
            story.append(Paragraph(base.clean_inline(line[4:].strip()), styles["subsection"]))
            i += 1
            continue

        para_buffer.append(line)
        i += 1

    base.flush_paragraph(story, para_buffer, styles, in_refs)
    if table_buffer:
        base.append_table(story, table_buffer, styles, col_width)
    return story


def main() -> None:
    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    base.INPUT_MD = INPUT_MD
    font_name = base.register_font()
    styles = base.make_styles(font_name)
    article = base.extract_article(INPUT_MD.read_text(encoding="utf-8"))

    page_w, page_h = A4
    left_margin = 20 * mm
    right_margin = 20 * mm
    gutter = 8 * mm
    full_w = page_w - left_margin - right_margin
    col_w = (full_w - gutter) / 2
    figure_margin = 12 * mm
    figure_w = page_w - (2 * figure_margin)

    top_y = 305
    top_h = 415
    first_top = Frame(left_margin, top_y, full_w, top_h, id="first_top", showBoundary=0)
    first_left = Frame(left_margin, 24 * mm, col_w, top_y - 30 * mm, id="first_left", showBoundary=0)
    first_right = Frame(left_margin + col_w + gutter, 24 * mm, col_w, top_y - 30 * mm, id="first_right", showBoundary=0)

    later_top = page_h - 25 * mm
    later_bottom = 24 * mm
    later_h = later_top - later_bottom
    later_left = Frame(left_margin, later_bottom, col_w, later_h, id="later_left", showBoundary=0)
    later_right = Frame(left_margin + col_w + gutter, later_bottom, col_w, later_h, id="later_right", showBoundary=0)

    figure_h = 150 * mm
    figure_bottom = page_h - 25 * mm - figure_h
    figure_full = Frame(figure_margin, figure_bottom, figure_w, figure_h, id="figure_full", showBoundary=0)
    figure_left = Frame(left_margin, later_bottom, col_w, figure_bottom - later_bottom - 4 * mm, id="figure_left", showBoundary=0)
    figure_right = Frame(
        left_margin + col_w + gutter,
        later_bottom,
        col_w,
        figure_bottom - later_bottom - 4 * mm,
        id="figure_right",
        showBoundary=0,
    )

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
            PageTemplate(id="First", frames=[first_top, first_left, first_right], onPage=base.draw_page),
            PageTemplate(id="Later", frames=[later_left, later_right], onPage=base.draw_page),
            PageTemplate(id="FigurePage", frames=[figure_full, figure_left, figure_right], onPage=base.draw_page),
        ]
    )

    story: list = [NextPageTemplate("Later")]
    story.extend(base.build_top_story(article, styles))
    story.append(FrameBreak())
    story.extend(build_body_story_with_full_images(article["body"], styles, col_w, figure_w))
    doc.build(story)
    print(OUTPUT_PDF)


if __name__ == "__main__":
    main()
