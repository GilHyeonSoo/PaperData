from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = ROOT / "outputs" / "scenarios_wallclock_v2"
DEFAULT_FIGURES_DIR = ROOT / "figures" / "wallclock_v2"


def scenario_sort_key(value: str) -> tuple[int, str]:
    text = str(value)
    if text.startswith("S") and text[1:].isdigit():
        return int(text[1:]), text
    return 999, text


def main() -> None:
    args = parse_args()
    output_root = resolve_path(args.output_root, DEFAULT_OUTPUT_ROOT)
    figures_dir = resolve_path(args.figures_dir, DEFAULT_FIGURES_DIR)
    figure_prefix = args.figure_prefix or ("48h" if "48h" in output_root.name.lower() else "v2")
    summary_name = args.summary_name or (
        "wallclock_48h_results_summary.md"
        if "48h" in output_root.name.lower()
        else "wallclock_v2_results_summary.md"
    )
    figures_dir.mkdir(parents=True, exist_ok=True)

    scenario_path, runs_path = ensure_summary_files(output_root)
    scenario_df = pd.read_csv(scenario_path).sort_values(
        "scenario_name", key=lambda col: col.map(scenario_sort_key)
    )
    runs_df = pd.read_csv(runs_path).sort_values(
        ["scenario_name", "wallclock_model"],
        key=lambda col: col.map(scenario_sort_key) if col.name == "scenario_name" else col,
    )

    scenario_summary = build_scenario_summary(scenario_df)
    model_summary = build_model_summary(runs_df)

    scenario_summary.to_csv(output_root / "scenario_summary_for_paper.csv", index=False)
    model_summary.to_csv(output_root / "model_summary_for_paper.csv", index=False)
    write_markdown_summary(scenario_summary, model_summary, output_root / summary_name)
    write_figures(scenario_summary, model_summary, figures_dir, figure_prefix)

    print(output_root / "scenario_summary_for_paper.csv")
    print(output_root / "model_summary_for_paper.csv")
    print(output_root / summary_name)
    print(figures_dir)


def ensure_summary_files(output_root: Path) -> tuple[Path, Path]:
    scenario_path = output_root / "all_scenarios_summary.csv"
    runs_path = output_root / "all_runs_summary.csv"
    run_frames = [
        pd.read_csv(path)
        for path in sorted(output_root.glob("*/summary/scenario_runs_summary.csv"))
        if path.exists()
    ]
    if run_frames:
        pd.concat(run_frames, ignore_index=True).to_csv(runs_path, index=False)

    scenario_rows = []
    for scenario_dir in sorted(output_root.glob("S*/summary")):
        aggregate_path = scenario_dir / "scenario_aggregate_summary.csv"
        progress_path = scenario_dir / "latest_progress.yaml"
        runs_summary_path = scenario_dir / "scenario_runs_summary.csv"
        if aggregate_path.exists():
            scenario_rows.extend(pd.read_csv(aggregate_path).to_dict("records"))
        elif progress_path.exists():
            import yaml

            with progress_path.open("r", encoding="utf-8") as f:
                row = yaml.safe_load(f) or {}
            if row:
                scenario_rows.append(row)
        elif runs_summary_path.exists():
            name = scenario_dir.parent.name
            runs_df = pd.read_csv(runs_summary_path)
            scenario_rows.append(aggregate_scenario_from_runs(name, runs_df))
    if scenario_rows:
        pd.DataFrame(scenario_rows).sort_values("scenario_name").to_csv(scenario_path, index=False)
    if not scenario_path.exists() or not runs_path.exists():
        raise FileNotFoundError(
            "Missing wall-clock outputs. Expected all summary files or per-scenario "
            f"summary files under {output_root}."
        )
    return scenario_path, runs_path


def aggregate_scenario_from_runs(name: str, runs_df: pd.DataFrame) -> dict[str, object]:
    if runs_df.empty:
        return {
            "scenario_name": name,
            "run_count": 0,
            "wall_time_s": 0.0,
            "generated_missions_total": 0,
            "completed_within_duration_total": 0,
            "completed_after_duration_total": 0,
            "collision_risk_count_total": 0,
            "building_collision_count_total": 0,
            "aircraft_collision_count_total": 0,
            "avg_pad_delay_s_mean": 0.0,
            "avg_flight_time_s_mean": 0.0,
            "models": "",
        }
    wall_time_s = (
        float(runs_df["worker_elapsed_s"].max())
        if "worker_elapsed_s" in runs_df.columns
        else float(runs_df.get("run_wall_time_s", pd.Series(dtype=float)).sum())
    )
    return {
        "scenario_name": name,
        "run_count": len(runs_df),
        "wall_time_s": wall_time_s,
        "generated_missions_total": int(runs_df["generated_missions"].sum()),
        "completed_within_duration_total": int(runs_df["completed_within_duration"].sum()),
        "completed_after_duration_total": int(runs_df["completed_after_duration"].sum()),
        "collision_risk_count_total": int(runs_df["collision_risk_count"].sum()),
        "building_collision_count_total": int(runs_df["building_collision_count"].sum()),
        "aircraft_collision_count_total": int(runs_df["aircraft_collision_count"].sum()),
        "avg_pad_delay_s_mean": float(runs_df["avg_pad_delay_s"].mean()),
        "avg_flight_time_s_mean": float(runs_df["avg_flight_time_s"].mean()),
        "models": ",".join(sorted(runs_df["wallclock_model"].astype(str).unique())),
    }


def build_scenario_summary(scenario_df: pd.DataFrame) -> pd.DataFrame:
    df = scenario_df.copy()
    df["completion_rate_pct"] = (
        df["completed_within_duration_total"] / df["generated_missions_total"] * 100.0
    )
    df["risk_per_1000_missions"] = (
        df["collision_risk_count_total"] / df["generated_missions_total"] * 1000.0
    )
    columns = [
        "scenario_name",
        "run_count",
        "wall_time_s",
        "generated_missions_total",
        "completed_within_duration_total",
        "completion_rate_pct",
        "collision_risk_count_total",
        "risk_per_1000_missions",
        "avg_pad_delay_s_mean",
        "avg_flight_time_s_mean",
        "models",
    ]
    return df[columns]


def build_model_summary(runs_df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        runs_df.groupby(["scenario_name", "wallclock_model"], as_index=False)
        .agg(
            run_count=("run_id", "count"),
            generated_missions=("generated_missions", "sum"),
            completed_within_duration=("completed_within_duration", "sum"),
            building_collision_count=("building_collision_count", "sum"),
            aircraft_collision_count=("aircraft_collision_count", "sum"),
            collision_risk_count=("collision_risk_count", "sum"),
            avg_pad_delay_s=("avg_pad_delay_s", "mean"),
            avg_flight_time_s=("avg_flight_time_s", "mean"),
            pad_wait_flight_count=("pad_wait_flight_count", "sum"),
        )
        .sort_values(["scenario_name", "wallclock_model"], key=sort_key_for_grouped)
    )
    grouped["risk_per_1000_missions"] = (
        grouped["collision_risk_count"] / grouped["generated_missions"] * 1000.0
    )
    grouped["completion_rate_pct"] = (
        grouped["completed_within_duration"] / grouped["generated_missions"] * 100.0
    )
    return grouped


def sort_key_for_grouped(col: pd.Series) -> pd.Series:
    if col.name == "scenario_name":
        return col.map(scenario_sort_key)
    return col


def write_markdown_summary(
    scenario_summary: pd.DataFrame,
    model_summary: pd.DataFrame,
    path: Path,
) -> None:
    lines = [
        "# S1-S6 / Model A-E wall-clock v2 결과 요약",
        "",
        "## 시나리오별 요약",
        dataframe_to_markdown(scenario_summary.round(2)),
        "",
        "## 모델별 요약",
        dataframe_to_markdown(model_summary.round(2)),
        "",
        "## 해석 메모",
        "- Model D는 건물 회피와 비행체 간 회피를 함께 적용하되 패드 점유 제약은 제외한 조건이다.",
        "- Model E는 Model D에 버티포트 패드 점유 제약을 추가한 조건이다.",
        "- D와 E 비교는 성능 우열이 아니라 운영 제약 반영 효과로 해석한다.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows_"
    columns = [str(column) for column in df.columns]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(format_cell(row[column]) for column in df.columns) + " |")
    return "\n".join(lines)


def format_cell(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def write_figures(
    scenario_summary: pd.DataFrame,
    model_summary: pd.DataFrame,
    figures_dir: Path,
    prefix: str,
) -> None:
    plot_completion(scenario_summary, figures_dir / f"{prefix}_mission_completion.png")
    plot_scenario_metric(
        scenario_summary,
        "risk_per_1000_missions",
        "Collision Risk Events per 1,000 Generated Missions",
        "Risk events / 1,000 missions",
        figures_dir / f"{prefix}_collision_risk_per_1000.png",
    )
    plot_scenario_metric(
        scenario_summary,
        "avg_pad_delay_s_mean",
        "Average Vertiport Pad Delay by Scenario",
        "Average pad delay (s)",
        figures_dir / f"{prefix}_pad_delay_by_scenario.png",
    )
    plot_model_metric(
        model_summary,
        "risk_per_1000_missions",
        "Normalized Collision Risk by Scenario and Model",
        "Risk events / 1,000 missions",
        figures_dir / f"{prefix}_model_risk_per_1000.png",
    )
    plot_model_metric(
        model_summary,
        "avg_pad_delay_s",
        "Average Pad Delay by Scenario and Model",
        "Average pad delay (s)",
        figures_dir / f"{prefix}_model_pad_delay.png",
    )
    plot_de_comparison(model_summary, figures_dir / f"{prefix}_model_d_vs_e.png")


def plot_completion(df: pd.DataFrame, path: Path) -> None:
    labels = df["scenario_name"]
    within = df["completed_within_duration_total"]
    after = df["generated_missions_total"] - df["completed_within_duration_total"]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.bar(labels, within, label="completed within duration")
    ax.bar(labels, after, bottom=within, label="completed after duration")
    ax.set_title("Wall-clock v2 Run Mission Completion by Scenario")
    ax.set_xlabel("Scenario")
    ax.set_ylabel("Missions")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_scenario_metric(
    df: pd.DataFrame,
    metric: str,
    title: str,
    ylabel: str,
    path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.bar(df["scenario_name"], df[metric])
    ax.set_title(title)
    ax.set_xlabel("Scenario")
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_model_metric(
    df: pd.DataFrame,
    metric: str,
    title: str,
    ylabel: str,
    path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    for model, group in df.groupby("wallclock_model"):
        ordered = group.sort_values("scenario_name", key=lambda col: col.map(scenario_sort_key))
        ax.plot(ordered["scenario_name"], ordered[metric], marker="o", label=f"Model {model}")
    ax.set_title(title)
    ax.set_xlabel("Scenario")
    ax.set_ylabel(ylabel)
    ax.legend(ncol=3, fontsize=8)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_de_comparison(df: pd.DataFrame, path: Path) -> None:
    subset = df[df["wallclock_model"] == "E"].copy()
    if subset.empty:
        return
    subset = subset.sort_values("scenario_name", key=lambda col: col.map(scenario_sort_key))
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.bar(subset["scenario_name"], subset["avg_pad_delay_s"], color="#ff7f0e", label="Model E")
    ax.set_title("Average Pad Delay Under Vertiport Pad Occupancy Constraint")
    ax.set_xlabel("Scenario")
    ax.set_ylabel("Average pad delay (s)")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def resolve_path(value: str | None, default: Path) -> Path:
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze S1-S6 / Model A-E wall-clock v2 outputs.")
    parser.add_argument("--output-root", help="Output root, default outputs/scenarios_wallclock_v2")
    parser.add_argument("--figures-dir", help="Figure directory, default figures/wallclock_v2")
    parser.add_argument("--figure-prefix", help="Output figure filename prefix, e.g. 48h")
    parser.add_argument("--summary-name", help="Markdown summary filename")
    return parser.parse_args()


if __name__ == "__main__":
    main()
