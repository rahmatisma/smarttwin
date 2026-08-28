from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean

from stable_baselines3 import PPO

if __package__:
    from .ppo_env import SmartTwinSumoEnv
else:
    # Mendukung eksekusi langsung dari folder decision_engine.
    root = Path(__file__).resolve().parents[1]
    for import_dir in (root, root / "backend"):
        if str(import_dir) not in sys.path:
            sys.path.insert(0, str(import_dir))
    from decision_engine.ppo_env import SmartTwinSumoEnv


def run(policy: str, model: PPO | None, episodes: int, seed: int) -> dict[str, float]:
    rewards, queues, waits, throughputs = [], [], [], []
    env = SmartTwinSumoEnv(split="eval")
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
    parser.add_argument("--output", default="decision_engine/models/evaluation.json")
    args = parser.parse_args()
    model = PPO.load(args.model)
    result = {"episodes": args.episodes, "seed_start": args.seed,
              "ppo": run("ppo", model, args.episodes, args.seed),
              "rule_based": run("rule-based", None, args.episodes, args.seed)}
    result["ppo_beats_rule_on_reward"] = result["ppo"]["mean_reward"] >= result["rule_based"]["mean_reward"]
    target = Path(args.output); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2)); print(f"Laporan: {target.resolve()}")


if __name__ == "__main__":
    main()
