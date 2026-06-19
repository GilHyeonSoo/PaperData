from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import font_manager


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = ROOT / "outputs" / "scenarios_wallclock_v2"
DEFAULT_FIGURES_DIR = ROOT / "figures" / "wallclock_v2"
MODEL_ORDER = ["A", "B", "C", "D", "E"]
MODEL_COLORS = {
    "A": "#4C78A8",
    "B": "#F58518",
    "C": "#54A24B",
    "D": "#B279A2",
    "E": "#E45756",
}


def configure_matplotlib() -> None:
    available = {font.name for font in font_manager.fontManager.ttflist}
    for name in ["AppleGothic", "NanumGothic", "Malgun Gothic", "Noto Sans CJK KR", "DejaVu Sans"]:
        if name in available:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams.update(
        {
            "axes.titlesize": 7,
            "axes.labelsize": 15,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "figure.titlesize": 7,
            "axes.unicode_minus": False,
        }
    )


def scenario_sort_key(value: str) -> tuple[int, str]:
    text = str(value)
    if text.startswith("S") and text[1:].isdigit():
        return int(text[1:]), text
    return 999, text


def main() -> None:
    configure_matplotlib()
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
    block_summary, block_model_stats = build_block_statistics(runs_df, block_size=args.block_size)

    scenario_summary.to_csv(output_root / "scenario_summary_for_paper.csv", index=False)
    model_summary.to_csv(output_root / "model_summary_for_paper.csv", index=False)
    block_summary.to_csv(output_root / f"block_statistics_{args.block_size}_runs.csv", index=False)
    block_model_stats.to_csv(output_root / f"block_model_variance_{args.block_size}_runs.csv", index=False)
    write_markdown_summary(scenario_summary, model_summary, output_root / summary_name)
    write_figures(scenario_summary, model_summary, block_summary, block_model_stats, figures_dir, figure_prefix)

    print(output_root / "scenario_summary_for_paper.csv")
    print(output_root / "model_summary_for_paper.csv")
    print(output_root / f"block_statistics_{args.block_size}_runs.csv")
    print(output_root / f"block_model_variance_{args.block_size}_runs.csv")
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


def build_block_statistics(runs_df: pd.DataFrame, block_size: int = 1000) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = runs_df.copy()
    df["model_order"] = df["wallclock_model"].map({model: idx for idx, model in enumerate(MODEL_ORDER)})
    df = df.sort_values(
        ["cycle", "scenario_name", "model_order", "run_seed", "run_id"],
        key=lambda col: col.map(scenario_sort_key) if col.name == "scenario_name" else col,
    )
    model_groups = {model: group.reset_index(drop=True) for model, group in df.groupby("wallclock_model")}
    full_blocks_by_model = {
        model: len(group) // block_size
        for model, group in model_groups.items()
        if model in MODEL_ORDER and len(group) >= block_size
    }
    if not full_blocks_by_model:
        return pd.DataFrame(), pd.DataFrame()
    common_blocks = min(full_blocks_by_model.values())

    rows = []
    for model in MODEL_ORDER:
        group = model_groups.get(model)
        if group is None:
            continue
        for block_index in range(common_blocks):
            start = block_index * block_size
            block = group.iloc[start : start + block_size]
            generated = int(block["generated_missions"].sum())
            completed = int(block["completed_within_duration"].sum())
            risks = int(block["collision_risk_count"].sum())
            rows.append(
                {
                    "wallclock_model": model,
                    "block_index": block_index + 1,
                    "cumulative_runs": (block_index + 1) * block_size,
                    "block_size": len(block),
                    "generated_missions": generated,
                    "completed_within_duration": completed,
                    "collision_risk_count": risks,
                    "risk_per_1000_missions": risks / generated * 1000.0 if generated else 0.0,
                    "completion_rate_pct": completed / generated * 100.0 if generated else 0.0,
                    "avg_pad_delay_s": float(block["avg_pad_delay_s"].mean()),
                }
            )
    block_summary = pd.DataFrame(rows)
    stats_rows = []
    for model, group in block_summary.groupby("wallclock_model"):
        values = group["risk_per_1000_missions"]
        n = int(values.count())
        mean = float(values.mean())
        variance = float(values.var(ddof=1)) if n > 1 else 0.0
        std = float(values.std(ddof=1)) if n > 1 else 0.0
        stats_rows.append(
            {
                "wallclock_model": model,
                "block_count": n,
                "common_runs_used": int(group["cumulative_runs"].max()) if n else 0,
                "risk_mean": mean,
                "risk_variance": variance,
                "risk_std": std,
            }
        )
    block_model_stats = pd.DataFrame(stats_rows).sort_values("wallclock_model")
    return block_summary, block_model_stats


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
        "# S1-S6 / Model A-E 누적 결과 요약",
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
    block_summary: pd.DataFrame,
    block_model_stats: pd.DataFrame,
    figures_dir: Path,
    prefix: str,
) -> None:
    plot_completion(scenario_summary, figures_dir / f"{prefix}_mission_completion.png")
    plot_scenario_metric(
        scenario_summary,
        "risk_per_1000_missions",
        "",
        "Collision risk / 1,000 missions",
        figures_dir / f"{prefix}_collision_risk_per_1000.png",
    )
    plot_scenario_metric(
        scenario_summary,
        "avg_pad_delay_s_mean",
        "",
        "Mean pad delay (s)",
        figures_dir / f"{prefix}_pad_delay_by_scenario.png",
    )
    plot_model_metric(
        model_summary,
        "risk_per_1000_missions",
        "",
        "Collision risk / 1,000 missions",
        figures_dir / f"{prefix}_model_risk_per_1000.png",
    )
    plot_model_metric(
        model_summary,
        "avg_pad_delay_s",
        "",
        "Mean pad delay (s)",
        figures_dir / f"{prefix}_model_pad_delay.png",
    )
    plot_de_comparison(model_summary, figures_dir / f"{prefix}_model_d_vs_e.png")
    plot_block_statistics(
        block_summary,
        block_model_stats,
        figures_dir / f"{prefix}_block_risk_statistics.png",
    )


def plot_completion(df: pd.DataFrame, path: Path) -> None:
    labels = df["scenario_name"]
    within = df["completed_within_duration_total"]
    after = df["generated_missions_total"] - df["completed_within_duration_total"]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.bar(labels, within, label="Completed within horizon", color="#4C78A8")
    ax.bar(labels, after, bottom=within, label="Completed after horizon", color="#F58518")
    ax.set_xlabel("Scenario")
    ax.set_ylabel("Missions")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)


def plot_scenario_metric(
    df: pd.DataFrame,
    metric: str,
    title: str,
    ylabel: str,
    path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.bar(df["scenario_name"], df[metric], color="#4C78A8")
    ax.set_xlabel("Scenario")
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)


def plot_model_metric(
    df: pd.DataFrame,
    metric: str,
    title: str,
    ylabel: str,
    path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    for model in MODEL_ORDER:
        group = df[df["wallclock_model"] == model]
        if group.empty:
            continue
        ordered = group.sort_values("scenario_name", key=lambda col: col.map(scenario_sort_key))
        ax.plot(
            ordered["scenario_name"],
            ordered[metric],
            marker="o",
            linewidth=1.6,
            markersize=4.2,
            label=f"Model {model}",
            color=MODEL_COLORS.get(model),
        )
    ax.set_xlabel("Scenario")
    ax.set_ylabel(ylabel)
    ax.legend(ncol=3, frameon=False)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)


def plot_de_comparison(df: pd.DataFrame, path: Path) -> None:
    subset = df[df["wallclock_model"] == "E"].copy()
    if subset.empty:
        return
    subset = subset.sort_values("scenario_name", key=lambda col: col.map(scenario_sort_key))
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.bar(subset["scenario_name"], subset["avg_pad_delay_s"], color="#E45756", label="Model E")
    ax.set_xlabel("Scenario")
    ax.set_ylabel("Mean pad delay (s)")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)


def plot_block_statistics(block_summary: pd.DataFrame, block_model_stats: pd.DataFrame, path: Path) -> None:
    if block_summary.empty or block_model_stats.empty:
        return
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    stats = block_model_stats.set_index("wallclock_model").reindex(
        [m for m in MODEL_ORDER if m in set(block_model_stats["wallclock_model"])]
    )
    for model, row in stats.iterrows():
        mean = float(row["risk_mean"])
        std = float(row["risk_std"])
        if std <= 0:
            continue
        x = pd.Series([mean - 4 * std + (8 * std) * i / 239 for i in range(240)])
        density = (1.0 / (std * (2.0 * 3.141592653589793) ** 0.5)) * (
            ((-(x - mean) ** 2) / (2.0 * std**2)).apply(lambda value: 2.718281828459045 ** value)
        )
        ax.plot(
            x,
            density,
            linewidth=1.4,
            color=MODEL_COLORS.get(model),
            label=f"Model {model}",
        )
        ax.axvline(mean, color=MODEL_COLORS.get(model), linewidth=0.6, alpha=0.55)
    ax.set_xlabel("Collision risk / 1,000 missions")
    ax.set_ylabel("Density")
    ax.grid(alpha=0.22)
    ax.legend(frameon=False, loc="upper right", ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=300)
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
    parser.add_argument("--block-size", type=int, default=1000, help="Complete run block size for statistical plots")
    return parser.parse_args()


if __name__ == "__main__":
    main()
