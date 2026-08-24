from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client


# ============================================================
# ENVIRONMENT
# ============================================================

def loadEnvironment() -> None:
    """
    Load environment variable dari backend/.env jika tersedia.
    """

    currentFile = os.path.abspath(__file__)

    backendRoot = os.path.abspath(
        os.path.join(
            currentFile,
            "..",
            "..",
        )
    )

    envFile = os.path.join(
        backendRoot,
        ".env",
    )

    if os.path.exists(envFile):
        load_dotenv(
            envFile,
            override=False,
        )


# ============================================================
# SUPABASE
# ============================================================

def getSupabase() -> Client:
    """
    Membuat Supabase client.

    Tidak bergantung pada:
        app.core.supabase

    sehingga service ini bisa dipanggil langsung
    oleh simulation/run_tls_simulation.py.
    """

    loadEnvironment()

    supabaseUrl = os.getenv(
        "SUPABASE_URL"
    )

    supabaseKey = os.getenv(
        "SUPABASE_SERVICE_ROLE_KEY"
    )

    if not supabaseUrl:
        raise RuntimeError(
            "SUPABASE_URL tidak ditemukan."
        )

    if not supabaseKey:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY tidak ditemukan."
        )

    return create_client(
        supabaseUrl,
        supabaseKey,
    )


# ============================================================
# SIMULATION RESULT WRITER
# ============================================================

class SimulationResultWriter:
    """
    Menyimpan hasil simulasi SUMO ke Supabase.

    Flow:

        TrafficState
             ↓
        Decision Engine
             ↓
        SUMO
             ↓
        Simulation Metrics
             ↓
        simulationRuns
             ↓
        simulationMetrics

    Semua payload menggunakan camelCase.
    """

    def __init__(
        self,
        supabaseClient: Client | None = None,
    ) -> None:

        self.supabaseClient = (
            supabaseClient
            if supabaseClient is not None
            else getSupabase()
        )

    # ========================================================
    # SAVE RESULT
    # ========================================================

    def saveResult(
        self,
        trafficState: Any,
        phasePlan: dict[str, Any],
        simulationMetrics: dict[str, Any],
    ) -> int:

        intersectionId = self.getValue(
            trafficState,
            "intersectionId",
        )

        if not intersectionId:
            raise ValueError(
                "TrafficState tidak memiliki intersectionId."
            )

        # ----------------------------------------------------
        # TIMESTAMP
        # ----------------------------------------------------

        startedAt = self.getValue(
            trafficState,
            "windowStart",
        )

        endedAt = datetime.now(
            timezone.utc
        )

        if startedAt is None:
            startedAt = endedAt

        # ----------------------------------------------------
        # SIMULATION RUN
        # ----------------------------------------------------

        simulationRunPayload = {
            "intersectionId": intersectionId,
            "startedAt": self.toIsoString(
                startedAt
            ),
            "endedAt": self.toIsoString(
                endedAt
            ),
            "status": "completed",
            "source": "rule-based",
        }

        print()
        print(
            "SimulationRun payload:"
        )
        print(
            simulationRunPayload
        )

        try:

            runResponse = (
                self.supabaseClient
                .table("simulationRuns")
                .insert(
                    simulationRunPayload
                )
                .execute()
            )

        except Exception as exc:

            raise RuntimeError(
                "Gagal insert ke tabel "
                f"simulationRuns: {exc}"
            ) from exc

        if not runResponse.data:

            raise RuntimeError(
                "Insert simulationRuns tidak "
                "mengembalikan data."
            )

        simulationRun = (
            runResponse.data[0]
        )

        simulationRunId = (
            simulationRun.get("id")
        )

        if simulationRunId is None:

            raise RuntimeError(
                "simulationRuns berhasil dibuat "
                "tetapi id tidak ditemukan."
            )

        print()
        print(
            "SimulationRun berhasil disimpan."
        )
        print(
            f"Simulation ID : {simulationRunId}"
        )

        # ----------------------------------------------------
        # SIMULATION METRICS
        # ----------------------------------------------------

        metricsPayload = (
            self.buildMetricsPayload(
                simulationRunId=simulationRunId,
                phasePlan=phasePlan,
                simulationMetrics=simulationMetrics,
            )
        )

        print()
        print(
            "SimulationMetrics payload:"
        )
        print(
            metricsPayload
        )

        try:

            metricsResponse = (
                self.supabaseClient
                .table("simulationMetrics")
                .insert(
                    metricsPayload
                )
                .execute()
            )

        except Exception as exc:

            raise RuntimeError(
                "Gagal insert ke tabel "
                f"simulationMetrics: {exc}"
            ) from exc

        if not metricsResponse.data:

            raise RuntimeError(
                "Insert simulationMetrics tidak "
                "mengembalikan data."
            )

        print()
        print(
            "SimulationMetrics berhasil disimpan."
        )

        return int(
            simulationRunId
        )

    # ========================================================
    # BUILD METRICS PAYLOAD
    # ========================================================

    def buildMetricsPayload(
        self,
        simulationRunId: int,
        phasePlan: dict[str, Any],
        simulationMetrics: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Membentuk payload untuk simulationMetrics.

        Seluruh field menggunakan camelCase.
        """

        return {
            "simulationRunId": simulationRunId,

            "steps": self.toNumber(
                simulationMetrics.get(
                    "steps"
                ),
                default=0,
            ),

            "activeVehicles": self.toNumber(
                simulationMetrics.get(
                    "activeVehicles"
                ),
                default=0,
            ),

            "arrivedVehicles": self.toNumber(
                simulationMetrics.get(
                    "arrivedVehicles"
                ),
                default=0,
            ),

            "departedVehicles": self.toNumber(
                simulationMetrics.get(
                    "departedVehicles"
                ),
                default=0,
            ),

            "recommendedPhase": (
                phasePlan.get(
                    "approach"
                )
                or ""
            ),

            "sumoPhase": self.toNumber(
                phasePlan.get(
                    "sumoPhase"
                ),
                default=0,
            ),

            "greenDurationSeconds": self.toNumber(
                phasePlan.get(
                    "duration"
                ),
                default=0,
            ),

            "finalPhase": self.toNumber(
                simulationMetrics.get(
                    "finalPhase"
                ),
                default=0,
            ),

            "tlsState": (
                simulationMetrics.get(
                    "tlsState"
                )
                or ""
            ),

            "confidence": self.toNumber(
                phasePlan.get(
                    "confidence"
                ),
                default=0,
            ),

            "source": (
                phasePlan.get(
                    "source"
                )
                or "rule-based"
            ),
        }

    # ========================================================
    # VALUE HELPER
    # ========================================================

    @staticmethod
    def getValue(
        obj: Any,
        fieldName: str,
    ) -> Any:

        if obj is None:
            return None

        if isinstance(
            obj,
            dict,
        ):
            return obj.get(
                fieldName
            )

        return getattr(
            obj,
            fieldName,
            None,
        )

    # ========================================================
    # NUMBER HELPER
    # ========================================================

    @staticmethod
    def toNumber(
        value: Any,
        default: int | float = 0,
    ) -> int | float:

        if value is None:
            return default

        try:

            number = float(
                value
            )

            if number.is_integer():
                return int(
                    number
                )

            return number

        except (
            TypeError,
            ValueError,
        ):

            return default

    # ========================================================
    # DATETIME HELPER
    # ========================================================

    @staticmethod
    def toIsoString(
        value: Any,
    ) -> str:

        if isinstance(
            value,
            datetime,
        ):

            if value.tzinfo is None:

                value = value.replace(
                    tzinfo=timezone.utc
                )

            return value.isoformat()

        if isinstance(
            value,
            str,
        ):

            return value

        return datetime.now(
            timezone.utc
        ).isoformat()