from __future__ import annotations

import os
from typing import Any

from .ppo_engine import PPOEngine
from .rule_based_engine import RuleBasedEngine

DECISION_ENGINE_ENV = "SMARTTWIN_DECISION_ENGINE"


def create_decision_engine(mode: str | None = None, **ppo_options: Any):
    """Buat engine tanpa pernah menjadikan PPO dependency wajib.

    Default tetap rule-based. Aktifkan PPO dengan
    ``SMARTTWIN_DECISION_ENGINE=ppo``. PPOEngine sendiri akan fallback jika
    checkpoint atau dependency belum siap.
    """
    selected = (mode or os.getenv(DECISION_ENGINE_ENV, "rule-based")).strip().lower()
    if selected == "ppo":
        return PPOEngine(**ppo_options)
    if selected not in {"rule-based", "rule_based", "rulebased"}:
        raise ValueError(f"Decision engine tidak dikenal: {selected}")
    return RuleBasedEngine()
