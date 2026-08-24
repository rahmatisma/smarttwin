from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from supabase import Client


# ============================================================
# SIMULATION RESULT WRITER
# ============================================================

class SimulationResultWriter:
    """
    Menyimpan hasil simulasi SUMO ke tabel:

        public.simulations

    Schema database yang digunakan HARUS sesuai:

        id                  int8
        intersectionId      int8
        trafficStateId      int8
        recommendationId    int8
        simulationName      varchar
        simulationType      varchar
        engine              varchar
        status              varchar
        startedAt           timestamptz
        completedAt         timestamptz
        createdAt           timestamptz

    IMPORTANT:
    Class ini TIDAK mengirim field lain ke tabel simulations.

    Field seperti:
        confidence
        source
        description
        recommendedPhase
        recommendedGreenSeconds
        currentGreenSeconds
        currentPhase
        expectedDelayReductionPercent

    boleh digunakan oleh simulation / decision engine,
    tetapi TIDAK disimpan langsung ke tabel simulations.
    """

    TABLE_NAME = "simulations"
    INTERSECTIONS_TABLE = "intersections"

    # ========================================================
    # CONSTRUCTOR
    # ========================================================

    def __init__(
        self,
        supabase: Client,
    ) -> None:

        if supabase is None:
            raise ValueError(
                "Supabase client tidak boleh None."
            )

        self.supabase = supabase

    # ========================================================
    # RESOLVE INTERSECTION ID
    # ========================================================

    def _resolveIntersectionId(
        self,
        intersectionIdentifier: Any,
    ) -> int:
        """
        Mengubah intersection identifier menjadi
        primary key numeric dari tabel intersections.

        Input yang didukung:

            1
            "1"
            "simpang4-pingit"

        Contoh:

            intersections
            --------------------------------
            id = 1
            intersectionId = simpang4-pingit

        Maka:

            "simpang4-pingit" -> 1
        """

        if intersectionIdentifier is None:
            raise ValueError(
                "intersectionId tidak boleh None."
            )

        # ----------------------------------------------------
        # CASE 1: INTEGER
        # ----------------------------------------------------

        if isinstance(
            intersectionIdentifier,
            int,
        ):
            return intersectionIdentifier

        # ----------------------------------------------------
        # CASE 2: NUMERIC STRING
        # ----------------------------------------------------

        identifier = str(
            intersectionIdentifier
        ).strip()

        if not identifier:
            raise ValueError(
                "intersectionId tidak boleh kosong."
            )

        if identifier.isdigit():
            return int(identifier)

        # ----------------------------------------------------
        # CASE 3:
        # Cari berdasarkan intersectionId
        #
        # Ini adalah field identifier yang memang
        # terlihat pada data Supabase kamu:
        #
        # intersectionId = "simpang4-pingit"
        # ----------------------------------------------------

        try:

            response = (
                self.supabase
                .table(
                    self.INTERSECTIONS_TABLE
                )
                .select("id")
                .eq(
                    "intersectionId",
                    identifier,
                )
                .limit(1)
                .execute()
            )

        except Exception as exc:

            raise RuntimeError(
                "Gagal mencari intersection "
                f"'{identifier}' di tabel "
                "intersections: "
                f"{exc}"
            ) from exc

        rows = response.data or []

        if rows:

            return int(
                rows[0]["id"]
            )

        # ----------------------------------------------------
        # FALLBACK:
        # Cari berdasarkan name
        #
        # Berguna jika caller mengirim:
        #
        # "Simpang 4 Pingit"
        # ----------------------------------------------------

        try:

            response = (
                self.supabase
                .table(
                    self.INTERSECTIONS_TABLE
                )
                .select("id")
                .eq(
                    "name",
                    identifier,
                )
                .limit(1)
                .execute()
            )

        except Exception:
            response = None

        if response is not None:

            rows = response.data or []

            if rows:

                return int(
                    rows[0]["id"]
                )

        # ----------------------------------------------------
        # NOT FOUND
        # ----------------------------------------------------

        raise ValueError(
            "Intersection tidak ditemukan: "
            f"{identifier}. "
            "Pastikan nilainya cocok dengan "
            "intersections.intersectionId "
            "atau intersections.name."
        )

    # ========================================================
    # NORMALIZE DATETIME
    # ========================================================

    @staticmethod
    def _normalizeDatetime(
        value: Any,
    ) -> Optional[str]:
        """
        Normalisasi datetime untuk PostgreSQL timestamptz.
        """

        if value is None:
            return None

        if isinstance(
            value,
            datetime,
        ):

            # Jika datetime belum memiliki timezone,
            # gunakan UTC.

            if value.tzinfo is None:

                value = value.replace(
                    tzinfo=timezone.utc
                )

            return value.isoformat()

        return str(value)

    # ========================================================
    # EXTRACT ID
    # ========================================================

    @staticmethod
    def _extractId(
        value: Any,
    ) -> Optional[int]:
        """
        Mengambil numeric ID dari berbagai bentuk object.

        Mendukung:

            13784
            "13784"
            {"id": 13784}
            object.id
        """

        if value is None:
            return None

        # ----------------------------------------------------
        # INTEGER
        # ----------------------------------------------------

        if isinstance(
            value,
            int,
        ):

            return value

        # ----------------------------------------------------
        # STRING
        # ----------------------------------------------------

        if isinstance(
            value,
            str,
        ):

            value = value.strip()

            if value.isdigit():
                return int(value)

            return None

        # ----------------------------------------------------
        # DICT
        # ----------------------------------------------------

        if isinstance(
            value,
            dict,
        ):

            rawId = value.get("id")

            if rawId is None:
                rawId = value.get(
                    "trafficStateId"
                )

            if rawId is None:
                rawId = value.get(
                    "recommendationId"
                )

            if rawId is None:
                return None

            try:
                return int(rawId)

            except (
                TypeError,
                ValueError,
            ):
                return None

        # ----------------------------------------------------
        # OBJECT
        # ----------------------------------------------------

        rawId = getattr(
            value,
            "id",
            None,
        )

        if rawId is None:

            rawId = getattr(
                value,
                "trafficStateId",
                None,
            )

        if rawId is None:

            rawId = getattr(
                value,
                "recommendationId",
                None,
            )

        if rawId is None:
            return None

        try:

            return int(rawId)

        except (
            TypeError,
            ValueError,
        ):

            return None

    # ========================================================
    # SAVE RESULT
    # ========================================================

    def saveResult(
        self,
        simulationPayload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Menyimpan satu record ke tabel simulations.

        HANYA field berikut yang dikirim:

            intersectionId
            trafficStateId
            recommendationId
            simulationName
            simulationType
            engine
            status
            startedAt
            completedAt

        createdAt TIDAK dikirim karena PostgreSQL
        diharapkan mengisinya dengan DEFAULT now().
        """

        # ====================================================
        # VALIDATE
        # ====================================================

        if not simulationPayload:

            raise ValueError(
                "simulationPayload kosong."
            )

        # ====================================================
        # RAW INTERSECTION
        # ====================================================

        rawIntersectionId = (
            simulationPayload.get(
                "intersectionId"
            )
        )

        # ====================================================
        # RESOLVE INTERSECTION
        # ====================================================

        intersectionId = (
            self._resolveIntersectionId(
                rawIntersectionId
            )
        )

        # ====================================================
        # TRAFFIC STATE ID
        # ====================================================

        trafficStateId = (
            self._extractId(
                simulationPayload.get(
                    "trafficStateId"
                )
            )
        )

        # ====================================================
        # RECOMMENDATION ID
        # ====================================================

        recommendationId = (
            self._extractId(
                simulationPayload.get(
                    "recommendationId"
                )
            )
        )

        # ====================================================
        # REQUIRED VALUES
        # ====================================================

        simulationName = (
            simulationPayload.get(
                "simulationName"
            )
            or "SmartTwin Adaptive TLS"
        )

        simulationType = (
            simulationPayload.get(
                "simulationType"
            )
            or "traffic_signal"
        )

        engine = (
            simulationPayload.get(
                "engine"
            )
            or "SUMO"
        )

        status = (
            simulationPayload.get(
                "status"
            )
            or "completed"
        )

        # ====================================================
        # DATETIME
        # ====================================================

        startedAt = (
            self._normalizeDatetime(
                simulationPayload.get(
                    "startedAt"
                )
            )
        )

        completedAt = (
            self._normalizeDatetime(
                simulationPayload.get(
                    "completedAt"
                )
            )
        )

        # ====================================================
        # DATABASE PAYLOAD
        #
        # INI SENGAJA HANYA FIELD YANG ADA DI SCHEMA.
        # ====================================================

        payload: Dict[str, Any] = {

            "intersectionId":
                intersectionId,

            "trafficStateId":
                trafficStateId,

            "recommendationId":
                recommendationId,

            "simulationName":
                simulationName,

            "simulationType":
                simulationType,

            "engine":
                engine,

            "status":
                status,

            "startedAt":
                startedAt,

            "completedAt":
                completedAt,
        }

        # ====================================================
        # DEBUG
        # ====================================================

        print()

        print(
            "======================================================================"
        )

        print(
            "SAVING SIMULATION RESULT"
        )

        print(
            "======================================================================"
        )

        print(
            f"Raw intersectionId : "
            f"{rawIntersectionId}"
        )

        print(
            f"DB intersection ID : "
            f"{intersectionId}"
        )

        print(
            f"TrafficState ID    : "
            f"{trafficStateId}"
        )

        print(
            f"Recommendation ID  : "
            f"{recommendationId}"
        )

        print(
            "Simulation payload:"
        )

        print(
            payload
        )

        # ====================================================
        # INSERT
        # ====================================================

        try:

            response = (
                self.supabase
                .table(
                    self.TABLE_NAME
                )
                .insert(
                    payload
                )
                .execute()
            )

        except Exception as exc:

            raise RuntimeError(
                "Gagal insert ke tabel "
                f"{self.TABLE_NAME}: "
                f"{exc}"
            ) from exc

        # ====================================================
        # RESPONSE
        # ====================================================

        rows = (
            response.data
            or []
        )

        if not rows:

            raise RuntimeError(
                "Insert simulasi dipanggil "
                "tetapi Supabase tidak "
                "mengembalikan data."
            )

        simulation = rows[0]

        # ====================================================
        # SUCCESS
        # ====================================================

        print()

        print(
            "Simulation berhasil disimpan."
        )

        print(
            f"Simulation DB ID: "
            f"{simulation.get('id')}"
        )

        print(
            "======================================================================"
        )

        return simulation