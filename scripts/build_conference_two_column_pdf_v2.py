from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_conference_two_column_pdf_with_scenario_figures.py"
INPUT_MD = ROOT / "paper" / "draft_v2_with_scenario_figures.md"
OUTPUT_PDF = ROOT / "output" / "pdf" / "evtol_paper_conference_two_column_v2.pdf"


def main() -> None:
    spec = importlib.util.spec_from_file_location("conference_pdf_with_figures", BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load PDF builder: {BUILDER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.INPUT_MD = INPUT_MD
    module.OUTPUT_PDF = OUTPUT_PDF
    module.main()


if __name__ == "__main__":
    main()
