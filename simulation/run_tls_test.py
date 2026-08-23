from __future__ import annotations

# ============================================================
# IMPORT DASAR
# ============================================================

import sys
from pathlib import Path

from dotenv import load_dotenv

from tls_controller import TLSController


# ============================================================
# PATH CONFIGURATION
# ============================================================

SIMULATION_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = SIMULATION_ROOT.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"

# ============================================================
# LOAD ENVIRONMENT SEBELUM IMPORT BACKEND
# ============================================================

ENV_FILE = BACKEND_ROOT / ".env"

if not ENV_FILE.exists():
    raise FileNotFoundError(
        f".env backend tidak ditemukan:\n{ENV_FILE}"
    )

load_dotenv(ENV_FILE)

print("=" * 70)
print("SMARTTWIN TLS TEST")
print("=" * 70)

print()
print("Environment:")
print(f"  .env       : {ENV_FILE}")
print(f"  Backend    : {BACKEND_ROOT}")
print(f"  Simulation : {SIMULATION_ROOT}")

# ============================================================
# PYTHON PATH
# ============================================================

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# ============================================================
# CEK ENV WAJIB
# ============================================================

required_env = [
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "HF_TOKEN",
    "HF_REPO_ID",
]

missing_env = [
    key
    for key in required_env
    if not __import__("os").getenv(key)
]

if missing_env:
    raise RuntimeError(
        "Environment variable berikut belum tersedia:\n"
        + "\n".join(f"  - {key}" for key in missing_env)
    )

print()
print("Environment variables:")
for key in required_env:
    print(f"  {key}: OK")


# ============================================================
# IMPORT BACKEND
# ============================================================

from app.pipeline.traffic_state_builder import (
    TrafficStateBuilder,
    TrafficStateBuilderConfig,
)


# ============================================================
# IMPORT TLS CONTROLLER
# ============================================================

controller = TLSController()


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("LOADING TRAFFIC STATE")
    print("=" * 70)

    builder = TrafficStateBuilder(
        TrafficStateBuilderConfig(
            windowSeconds=5
        )
    )

    states = builder.build_latest_states(
        limit=1,
        save=False,
    )

    if not states:
        raise RuntimeError(
            "Tidak ada TrafficState terbaru dari Supabase."
        )

    traffic_state = states[0]

    print()
    print("TrafficState berhasil dimuat.")

    print()
    print("=" * 70)
    print("TRAFFIC STATE")
    print("=" * 70)

    print(
        f"Intersection : {traffic_state.intersectionId}"
    )

    print(
        f"Window       : "
        f"{traffic_state.windowStart} "
        f"-> "
        f"{traffic_state.windowEnd}"
    )

    print()

    for approach in traffic_state.approaches:

        print(
            f"{approach.approach.upper():7s} "
            f"| volume={approach.volume:<4} "
            f"| car={approach.carCount:<4} "
            f"| motor={approach.motorcycleCount:<4} "
            f"| bus={approach.busCount:<4} "
            f"| truck={approach.truckCount:<4} "
            f"| queue={approach.queueLengthVeh:<4}"
        )


    # ========================================================
    # TLS CONTROLLER
    # ========================================================

    print()
    print("=" * 70)
    print("TLS CONTROLLER")
    print("=" * 70)

    controller = TLSController()

    print()
    print("TLS Controller berhasil dibuat.")

    print()
    print("=" * 70)
    print("INTEGRATION READY")
    print("=" * 70)

    print()
    print("TrafficState")
    print("     ↓")
    print("Phase Plan")
    print("     ↓")
    print("TLS Controller")
    print("     ↓")
    print("TraCI")
    print("     ↓")
    print("SUMO")

    print()
    print("TEST BERHASIL.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()