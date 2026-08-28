import sys
from pathlib import Path

# Membuat `python -m decision_engine.train_ppo` dapat dijalankan dari root.
# Backend sendiri sudah memiliki folder ini di PYTHONPATH ketika Uvicorn aktif.
_backend_dir = Path(__file__).resolve().parents[1] / "backend"
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from .rule_based_engine import (
    Recommendation,
    RuleBasedEngine,
)
from .engine_factory import create_decision_engine
from .ppo_engine import PPOEngine

__all__ = [
    "Recommendation",
    "PPOEngine",
    "RuleBasedEngine",
    "create_decision_engine",
]
