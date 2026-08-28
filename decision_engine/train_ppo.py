from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.monitor import Monitor

if __package__:
    from .ppo_env import DEFAULT_DATA, DEFAULT_DENSITY_DATA, SmartTwinSumoEnv
else:
    # Mendukung: cd decision_engine; python -m train_ppo / python train_ppo.py
    root = Path(__file__).resolve().parents[1]
    for import_dir in (root, root / "backend"):
        if str(import_dir) not in sys.path:
            sys.path.insert(0, str(import_dir))
    from decision_engine.ppo_env import DEFAULT_DATA, DEFAULT_DENSITY_DATA, SmartTwinSumoEnv


def main() -> None:
    parser = argparse.ArgumentParser(description="Train PPO SmartTwin di SUMO headless")
    parser.add_argument("--timesteps", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--density-data", default=str(DEFAULT_DENSITY_DATA))
    parser.add_argument("--output", default="decision_engine/models/smarttwin_ppo")
    parser.add_argument("--episode-steps", type=int, default=12)
    parser.add_argument("--decision-seconds", type=int, default=30)
    parser.add_argument("--n-steps", type=int, default=512, help="Ukuran rollout PPO; gunakan 8 hanya untuk smoke test")
    parser.add_argument("--check-env", action="store_true")
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    make_env = lambda: SmartTwinSumoEnv(data_path=args.data, density_data_path=args.density_data,
                                        episode_steps=args.episode_steps,
                                        decision_seconds=args.decision_seconds, split="train")
    if args.check_env:
        probe = make_env()
        check_env(probe, warn=True)
        probe.close()
        print("Gymnasium environment valid.")
    env = Monitor(make_env(), filename=str(output.parent / "training_monitor.csv"))
    callback = CheckpointCallback(save_freq=10_000, save_path=str(output.parent / "checkpoints"), name_prefix="smarttwin_ppo")
    tensorboard_log = str(output.parent / "tensorboard") if importlib.util.find_spec("tensorboard") else None
    batch_size = min(64, args.n_steps)
    model = PPO("MlpPolicy", env, learning_rate=3e-4, n_steps=args.n_steps, batch_size=batch_size,
                gamma=0.99, gae_lambda=0.95, clip_range=0.2, ent_coef=0.01,
                seed=args.seed, verbose=1, tensorboard_log=tensorboard_log)
    try:
        model.learn(total_timesteps=args.timesteps, callback=callback, progress_bar=False)
        model.save(str(output))
        print(f"Model tersimpan: {output.with_suffix('.zip').resolve()}")
    finally:
        env.close()


if __name__ == "__main__":
    main()
