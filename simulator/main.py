from __future__ import annotations

from .config import ensure_output_dirs, load_config
from .exporter import export_results
from .simulation import build_experiments, run_experiment
from .visualizer import plot_city_map, plot_summary_graphs, plot_trajectories


def main() -> None:
    config = load_config()
    ensure_output_dirs()
    experiments = build_experiments(config)
    results = []
    print(f"Running {len(experiments)} simulation experiments...")
    for index, experiment in enumerate(experiments, start=1):
        print(
            f"[{index:02d}/{len(experiments)}] {experiment.scenario_id} "
            f"sweep={experiment.sweep} model={experiment.model} "
            f"n={experiment.aircraft_count} speed={experiment.speed_kmh}km/h "
            f"density={experiment.building_density} vertiports={experiment.vertiport_count} "
            f"safety={experiment.safety_label}"
        )
        results.append(run_experiment(config, experiment))

    summary_df, raw_df = export_results(results)
    plot_summary_graphs(summary_df)
    reference = next(
        (
            result
            for result in results
            if result.experiment.sweep == "model_comparison" and result.experiment.model == "D"
        ),
        results[-1],
    )
    plot_city_map(reference.city_map)
    plot_trajectories(reference)
    print(f"Saved {len(summary_df)} summary rows and {len(raw_df)} raw trajectory rows.")


if __name__ == "__main__":
    main()

