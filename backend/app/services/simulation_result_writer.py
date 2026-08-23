from __future__ import annotations

"""
SMARTTWIN - Simulation Result Writer

Tugas:
    Menyimpan hasil simulasi SUMO ke Supabase.

Flow:
    SUMO
      ↓
    simulation result
      ↓
    simulations
      ↓
    simulationMetrics

Tidak menggunakan CSV.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from app.services.supabase_client import get_supabase


# ============================================================
# HELPERS
# ============================================================

def utc_now() -> str:
    """
    Return current UTC timestamp dalam format ISO.
    """
    return datetime.now(timezone.utc).isoformat()


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


# ============================================================
# SIMULATION RESULT WRITER
# ============================================================

class SimulationResultWriter:
    """
    Menulis hasil simulasi SUMO ke Supabase.

    Tables:
        simulations
        simulationMetrics
    """

    def __init__(self):
        self.supabase = get_supabase()

    # ========================================================
    # CREATE SIMULATION
    # ========================================================

    def create_simulation(
        self,
        intersection_id: str,
        traffic_state_id: int,
        simulation_name: str = "SmartTwin SUMO Simulation",
        simulation_type: str = "adaptive_tls",
        engine: str = "SUMO",
        recommendation_id: Optional[int] = None,
    ) -> int:

        payload = {
            "intersectionId": intersection_id,
            "trafficStateId": traffic_state_id,
            "recommendationId": recommendation_id,
            "simulationName": simulation_name,
            "simulationType": simulation_type,
            "engine": engine,
            "status": "running",
            "startedAt": utc_now(),
        }

        # Jangan kirim recommendationId jika tidak ada.
        if recommendation_id is None:
            payload.pop("recommendationId")

        response = (
            self.supabase
            .table("simulations")
            .insert(payload)
            .execute()
        )

        if not response.data:
            raise RuntimeError(
                "Gagal membuat record pada tabel simulations."
            )

        simulation_id = response.data[0]["id"]

        print()
        print("=" * 70)
        print("SIMULATION RECORD CREATED")
        print("=" * 70)
        print(f"Simulation ID    : {simulation_id}")
        print(f"Intersection     : {intersection_id}")
        print(f"Traffic State ID : {traffic_state_id}")
        print()

        return int(simulation_id)

    # ========================================================
    # UPDATE STATUS
    # ========================================================

    def complete_simulation(
        self,
        simulation_id: int,
        status: str = "completed",
    ) -> None:

        payload = {
            "status": status,
            "completedAt": utc_now(),
        }

        (
            self.supabase
            .table("simulations")
            .update(payload)
            .eq("id", simulation_id)
            .execute()
        )

        print()
        print("=" * 70)
        print("SIMULATION RECORD UPDATED")
        print("=" * 70)
        print(f"Simulation ID : {simulation_id}")
        print(f"Status        : {status}")
        print()

    # ========================================================
    # SAVE METRIC
    # ========================================================

    def save_metric(
        self,
        simulation_id: int,
        metric_name: str,
        metric_value: float,
        unit: Optional[str] = None,
    ) -> int:

        payload = {
            "simulationId": simulation_id,
            "metricName": metric_name,
            "metricValue": safe_float(metric_value),
            "unit": unit,
            "createdAt": utc_now(),
        }

        response = (
            self.supabase
            .table("simulationMetrics")
            .insert(payload)
            .execute()
        )

        if not response.data:
            raise RuntimeError(
                f"Gagal menyimpan metric: {metric_name}"
            )

        return int(response.data[0]["id"])

    # ========================================================
    # SAVE MULTIPLE METRICS
    # ========================================================

    def save_metrics(
        self,
        simulation_id: int,
        metrics: Dict[str, Any],
    ) -> None:

        rows = []

        # Mapping unit berdasarkan nama metric.
        units = {
            "simulation_steps": "step",
            "active_vehicles": "vehicle",
            "departed_vehicles": "vehicle",
            "arrived_vehicles": "vehicle",
            "expected_vehicles": "vehicle",
            "tls_phase": "phase",
            "tls_duration": "s",
            "simulation_time": "s",
            "queue_north": "vehicle",
            "queue_south": "vehicle",
            "queue_east": "vehicle",
            "queue_west": "vehicle",
            "total_queue": "vehicle",
            "total_delay": "s",
            "average_delay": "s",
            "waiting_time": "s",
            "throughput": "vehicle",
        }

        for metric_name, metric_value in metrics.items():

            if metric_value is None:
                continue

            rows.append(
                {
                    "simulationId": simulation_id,
                    "metricName": metric_name,
                    "metricValue": safe_float(metric_value),
                    "unit": units.get(metric_name),
                    "createdAt": utc_now(),
                }
            )

        if not rows:
            print("Tidak ada metric untuk disimpan.")
            return

        (
            self.supabase
            .table("simulationMetrics")
            .insert(rows)
            .execute()
        )

        print()
        print("=" * 70)
        print("SIMULATION METRICS SAVED")
        print("=" * 70)

        for row in rows:
            print(
                f"{row['metricName']:25s}"
                f" = {row['metricValue']}"
                f" {row['unit'] or ''}"
            )

        print()

    # ========================================================
    # SAVE COMPLETE RESULT
    # ========================================================

    def save_result(
        self,
        *,
        intersection_id: str,
        traffic_state_id: int,
        metrics: Dict[str, Any],
        simulation_name: str = "SmartTwin SUMO Simulation",
        simulation_type: str = "adaptive_tls",
        engine: str = "SUMO",
        recommendation_id: Optional[int] = None,
    ) -> int:

        simulation_id = self.create_simulation(
            intersection_id=intersection_id,
            traffic_state_id=traffic_state_id,
            simulation_name=simulation_name,
            simulation_type=simulation_type,
            engine=engine,
            recommendation_id=recommendation_id,
        )

        try:

            self.save_metrics(
                simulation_id=simulation_id,
                metrics=metrics,
            )

            self.complete_simulation(
                simulation_id=simulation_id,
                status="completed",
            )

            return simulation_id

        except Exception:

            # Kalau proses penyimpanan metric gagal,
            # simulation tetap tercatat tetapi status failed.
            try:
                self.complete_simulation(
                    simulation_id=simulation_id,
                    status="failed",
                )
            except Exception:
                pass

            raise


# ============================================================
# TEST
# ============================================================

def main():

    print("=" * 70)
    print("SMARTTWIN SIMULATION RESULT WRITER TEST")
    print("=" * 70)

    writer = SimulationResultWriter()

    simulation_id = writer.save_result(
        intersection_id="simpang4-pingit",
        traffic_state_id=6497,
        metrics={
            "simulation_steps": 118,
            "simulation_time": 118,
            "active_vehicles": 0,
            "departed_vehicles": 0,
            "arrived_vehicles": 1,
            "tls_phase": 0,
            "tls_duration": 39,
        },
        simulation_name="SmartTwin TLS Test",
        simulation_type="adaptive_tls",
        engine="SUMO",
    )

    print("=" * 70)
    print("TEST BERHASIL")
    print("=" * 70)
    print(f"Simulation ID : {simulation_id}")


if __name__ == "__main__":
    main()