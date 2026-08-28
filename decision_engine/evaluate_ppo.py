from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean

from stable_baselines3 import PPO

if __package__:
    from .ppo_env import DEFAULT_DATA, DEFAULT_DENSITY_DATA, SmartTwinSumoEnv
else:
    # Mendukung eksekusi langsung dari folder decision_engine.
    root = Path(__file__).resolve().parents[1]
    for import_dir in (root, root / "backend"):
        if str(import_dir) not in sys.path:
            sys.path.insert(0, str(import_dir))
    from decision_engine.ppo_env import DEFAULT_DATA, DEFAULT_DENSITY_DATA, SmartTwinSumoEnv


METRIC_RULES = {
    "mean_reward": "higher",
    "mean_queue_veh": "lower",
    "mean_accumulated_wait_s": "lower",
    "total_throughput_veh": "higher",
}
TRAFFIC_METRICS = (
    "mean_queue_veh",
    "mean_accumulated_wait_s",
    "total_throughput_veh",
)


def compare_results(ppo: dict[str, float], rule_based: dict[str, float]) -> dict:
    """Bandingkan metrik operasional tanpa menyamakan reward dengan kualitas lalu lintas."""
    metrics = {}
    for name, direction in METRIC_RULES.items():
        ppo_value = float(ppo[name])
        baseline_value = float(rule_based[name])
        delta = ppo_value - baseline_value
        # Persentase reward negatif mudah menyesatkan (mis. -0,1 vs -0,3
        # terlihat sebagai perubahan >100%). Persentase hanya bermakna untuk
        # metrik lalu lintas dengan skala fisik.
        delta_percent = (
            None
            if name == "mean_reward" or baseline_value == 0
            else (delta / abs(baseline_value)) * 100.0
        )
        ppo_better = ppo_value >= baseline_value if direction == "higher" else ppo_value <= baseline_value
        metrics[name] = {
            "ppo": ppo_value,
            "rule_based": baseline_value,
            "direction": direction,
            "delta": delta,
            "delta_percent": delta_percent,
            "ppo_better_or_equal": ppo_better,
        }

    traffic_wins = sum(bool(metrics[name]["ppo_better_or_equal"]) for name in TRAFFIC_METRICS)
    quality_gate = traffic_wins == len(TRAFFIC_METRICS)
    return {
        "metrics": metrics,
        "traffic_metrics_won": traffic_wins,
        "traffic_metrics_total": len(TRAFFIC_METRICS),
        "quality_gate_passed": quality_gate,
        "recommended_for_activation": quality_gate,
        "verdict": (
            "PPO memenuhi seluruh metrik lalu lintas."
            if quality_gate
            else "PPO belum boleh diaktifkan; gunakan rule-based fallback."
        ),
    }


def run(policy: str, model: PPO | None, episodes: int, seed: int,
        data_path: str | Path = DEFAULT_DATA,
        density_data_path: str | Path = DEFAULT_DENSITY_DATA) -> dict[str, float]:
    rewards, queues, waits, throughputs = [], [], [], []
    env = SmartTwinSumoEnv(
        split="eval",
        data_path=data_path,
        density_data_path=density_data_path,
    )
    try:
        for episode in range(episodes):
            obs, _ = env.reset(seed=seed + episode)
            done = False
            while not done:
                action = env.rule_based_action() if policy == "rule-based" else model.predict(obs, deterministic=True)[0]
                obs, reward, terminated, truncated, info = env.step(action)
                rewards.append(reward); queues.append(info["queue"]); waits.append(info["waiting"])
                throughputs.append(info["throughput_interval"])
                done = terminated or truncated
    finally:
        env.close()
    return {"mean_reward": mean(rewards), "mean_queue_veh": mean(queues),
            "mean_accumulated_wait_s": mean(waits), "total_throughput_veh": sum(throughputs)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Bandingkan PPO dengan baseline rule-based pada seed sama")
    parser.add_argument("--model", default="decision_engine/models/smarttwin_ppo.zip")
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--density-data", default=str(DEFAULT_DENSITY_DATA))
    parser.add_argument("--output", default="decision_engine/models/evaluation.json")
    args = parser.parse_args()
    model = PPO.load(args.model)
    result = {"episodes": args.episodes, "seed_start": args.seed,
              "ppo": run("ppo", model, args.episodes, args.seed, args.data, args.density_data),
              "rule_based": run("rule-based", None, args.episodes, args.seed, args.data, args.density_data)}
    result["comparison"] = compare_results(result["ppo"], result["rule_based"])
    target = Path(args.output); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2)); print(f"Laporan: {target.resolve()}")


if __name__ == "__main__":
    main()
