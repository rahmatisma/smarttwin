from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import sys
from datetime import datetime, timezone
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


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("nilai harus lebih besar dari 0")
    return parsed


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Train PPO SmartTwin di SUMO headless")
    parser.add_argument("--timesteps", type=_positive_int, default=100_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--density-data", default=str(DEFAULT_DENSITY_DATA))
    parser.add_argument("--output", default="decision_engine/models/smarttwin_ppo")
    parser.add_argument("--episode-steps", type=_positive_int, default=12)
    parser.add_argument("--decision-seconds", type=_positive_int, default=30)
    parser.add_argument("--n-steps", type=_positive_int, default=512, help="Ukuran rollout PPO; gunakan 8 hanya untuk smoke test")
    parser.add_argument("--device", choices=("cpu", "cuda", "auto"), default="cpu",
                        help="PPO MLP+SUMO default ke CPU; gunakan cuda hanya setelah benchmark")
    parser.add_argument("--resume", help="Checkpoint .zip untuk melanjutkan training")
    parser.add_argument("--checkpoint-freq", type=_positive_int, default=10_000)
    parser.add_argument("--check-env", action="store_true")
    args = parser.parse_args()

    data_path = Path(args.data).expanduser().resolve()
    density_path = Path(args.density_data).expanduser().resolve()
    missing = [str(path) for path in (data_path, density_path) if not path.is_file()]
    if missing:
        parser.error("data training tidak ditemukan: " + ", ".join(missing))
    resume_path = Path(args.resume).expanduser().resolve() if args.resume else None
    if resume_path is not None and not resume_path.is_file():
        parser.error(f"checkpoint resume tidak ditemukan: {resume_path}")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    make_env = lambda: SmartTwinSumoEnv(data_path=data_path, density_data_path=density_path,
                                        episode_steps=args.episode_steps,
                                        decision_seconds=args.decision_seconds, split="train")
    if args.check_env:
        probe = make_env()
        check_env(probe, warn=True)
        probe.close()
        print("Gymnasium environment valid.")
    env = Monitor(
        make_env(),
        filename=str(output.parent / "training_monitor.csv"),
        override_existing=resume_path is None,
    )
    callback = CheckpointCallback(
        save_freq=args.checkpoint_freq,
        save_path=str(output.parent / "checkpoints"),
        name_prefix="smarttwin_ppo",
    )
    tensorboard_log = str(output.parent / "tensorboard") if importlib.util.find_spec("tensorboard") else None
    batch_size = min(64, args.n_steps)
    if resume_path is not None:
        model = PPO.load(str(resume_path), env=env, device=args.device)
        print(f"Melanjutkan checkpoint: {resume_path}")
    else:
        model = PPO(
            "MlpPolicy", env, learning_rate=3e-4, n_steps=args.n_steps,
            batch_size=batch_size, gamma=0.99, gae_lambda=0.95,
            clip_range=0.2, ent_coef=0.01, seed=args.seed, verbose=1,
            tensorboard_log=tensorboard_log, device=args.device,
        )
    started_at = datetime.now(timezone.utc)
    try:
        model.learn(
            total_timesteps=args.timesteps,
            callback=callback,
            progress_bar=False,
            reset_num_timesteps=resume_path is None,
        )
        model.save(str(output))
        model_path = output.with_suffix(".zip").resolve()
        metadata = {
            "startedAt": started_at.isoformat(),
            "finishedAt": datetime.now(timezone.utc).isoformat(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "stableBaselines3": __import__("stable_baselines3").__version__,
            "timestepsRequestedThisRun": args.timesteps,
            "modelTotalTimesteps": int(model.num_timesteps),
            "seed": args.seed,
            "deviceRequested": args.device,
            "deviceUsed": str(model.device),
            "episodeSteps": args.episode_steps,
            "decisionSeconds": args.decision_seconds,
            "nSteps": int(model.n_steps),
            "checkpointFrequency": args.checkpoint_freq,
            "resumedFrom": str(resume_path) if resume_path else None,
            "model": str(model_path),
            "data": {"path": str(data_path), "sha256": _sha256(data_path)},
            "densityData": {"path": str(density_path), "sha256": _sha256(density_path)},
        }
        metadata_path = output.with_suffix(".training.json").resolve()
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        print(f"Model tersimpan: {model_path}")
        print(f"Metadata training: {metadata_path}")
    finally:
        env.close()


if __name__ == "__main__":
    main()
