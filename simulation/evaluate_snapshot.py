"""Isolated SUMO evaluation; writes the same result to cache and history."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from scenario_worker import evaluate_state, write_cache, write_history, connectSupabase
from app.services.traffic_snapshot import load_snapshot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-id", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    state = load_snapshot("simpang4-pingit", args.state_id)
    # One observed demand snapshot, three signal plans, identical SUMO seed and horizon.
    result = evaluate_state(state, full_cycle=True)
    supabase = connectSupabase()
    write_history(supabase, result, state, strict=True)
    write_cache(supabase, result, strict=True)
    args.output.write_text(json.dumps(result), encoding="utf-8")


if __name__ == "__main__":
    main()
