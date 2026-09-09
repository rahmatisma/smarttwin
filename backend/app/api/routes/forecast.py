from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.per_approach_forecast_service import per_approach_forecast_service


router = APIRouter(
    prefix="/api/forecast",
    tags=["Forecast"],
)


# ============================================================
# REQUEST SCHEMA
# ============================================================

class ForecastRecord(BaseModel):
    timestamp: datetime = Field(
        ...,
        description="Timestamp data traffic",
        examples=["2026-08-15T17:19:15"],
    )

    vehicleCount: float = Field(
        ...,
        ge=0,
        description="Jumlah kendaraan",
        examples=[10],
    )

    queueLengthVeh: float = Field(
        ...,
        ge=0,
        description="Panjang antrean dalam kendaraan",
        examples=[0],
    )

    queueLengthMEst: float = Field(
        ...,
        ge=0,
        description="Estimasi panjang antrean dalam meter",
        examples=[0],
    )

    densityIndex: float = Field(
        ...,
        ge=0,
        le=1,
        description="Indeks kepadatan 0 sampai 1",
        examples=[0.171212],
    )


class ForecastRequest(BaseModel):
    records: list[ForecastRecord] = Field(
        ...,
        min_length=12,
        description="Minimal 12 timestep data traffic",
    )


class ForecastApproachRecord(BaseModel):
    approach: str
    vehicleCount: float = Field(default=0.0, ge=0)
    queueLengthVeh: float = Field(default=0.0, ge=0)
    queueLengthMEst: float = Field(default=0.0, ge=0)
    densityIndex: float = Field(default=0.0, ge=0, le=1)


class ForecastTrafficStateRecord(BaseModel):
    timestamp: datetime
    approaches: list[ForecastApproachRecord] = Field(..., min_length=1)


class ForecastApproachRequest(BaseModel):
    records: list[ForecastTrafficStateRecord] = Field(..., min_length=12)


# ============================================================
# FORECAST
# ============================================================

@router.post(
    "",
    summary="Traffic Forecast 60 Detik",
    description=(
        "Menjalankan model LSTM SmartTwin menggunakan "
        "12 timestep terakhir dan menghasilkan prediksi "
        "12 timestep berikutnya dengan interval 5 detik."
    ),
)
def predict_forecast(
    request: ForecastRequest,
) -> dict[str, Any]:

    try:
        records = [
            record.model_dump(mode="json")
            for record in request.records
        ]

        from app.services.forecast_service import forecast_service

        result = forecast_service.predict_records(
            records
        )

        return result

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Forecast gagal dijalankan: {exc}",
        ) from exc


# ============================================================
# HEALTH
# ============================================================

@router.get(
    "/health",
    summary="Forecast Service Health",
)
def forecast_health() -> dict[str, Any]:

    try:
        from app.services.forecast_service import forecast_service

        return forecast_service.health()

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Forecast health check gagal: {exc}",
        ) from exc


@router.get("/approaches/snapshot/{traffic_state_id}")
def predict_snapshot(traffic_state_id: int, intersectionId: str = "simpang4-pingit") -> dict[str, Any]:
    from app.services.traffic_snapshot import load_snapshot
    from app.services.traffic_repository import TrafficRepository
    from app.services.supabase_client import get_supabase
    try:
        snapshot = load_snapshot(intersectionId, traffic_state_id)
        repository = TrafficRepository()
        intersection_row_id = repository.get_intersection_row_id(intersectionId)
        # Ambil 40, bukan 12: sebagian row bisa tidak lengkap 4 lengan, dan
        # _history perlu ruang untuk mencari blok 5-detik yang bersih (atau
        # jatuh ke 12 terbaru kalau rekaman ada celah).
        rows = (get_supabase().table("trafficStates").select("id,windowStart,windowEnd")
                .eq("intersectionId", intersection_row_id)
                .lte("windowEnd", snapshot.windowEnd.isoformat())
                .order("windowEnd", desc=True).limit(40).execute()).data or []
        # Satu query .in_ untuk 12 state, bukan 12 get_approach_states() berurutan
        # (~3,7 dtk -> ~0,5 dtk). Urutan approach tidak penting: konsumen
        # (per_approach_forecast_service._history) mengindeks per nama lengan.
        approaches_by_state = repository.get_approach_states_by_state(
            traffic_state_ids=[int(row["id"]) for row in rows]
        )
        records = [{"timestamp": row["windowEnd"],
                    "approaches": approaches_by_state.get(int(row["id"]), [])} for row in rows]
        # Only actual, complete observations are admitted; no zero-filled missing arms.
        result = per_approach_forecast_service.predict_records(records)
        # Riwayat harus berakhir DEKAT window yang diminta (toleransi 60 dtk --
        # rekaman kadang ada celah kecil; forecast dari ~beberapa detik lalu
        # masih berguna di dashboard).
        selisih = abs(
            (datetime.fromisoformat(result["input"]["to"]) - snapshot.windowEnd).total_seconds()
        )
        if selisih > 60:
            raise ValueError(
                "Riwayat LSTM berakhir terlalu jauh dari TrafficState yang dipilih."
            )
        return {**result, "trafficStateId": traffic_state_id}
    except ValueError as exc:
        # Bukan error server: window ini memang belum punya 12 TrafficState
        # berurutan (biasa terjadi di dekat awal batch / celah rekaman).
        # Balas 200 dengan penanda supaya dashboard tidak memenuhi konsol
        # dengan 422 tiap kali video melewati window seperti ini.
        return {
            "trafficStateId": traffic_state_id,
            "available": False,
            "reason": str(exc),
            "approachForecasts": [],
        }


@router.post(
    "/approaches",
    summary="Traffic Forecast 60 Detik Per Pendekat",
    description=(
        "Menjalankan LSTM per-approach menggunakan 12 TrafficState lengkap "
        "berinterval 5 detik. Jika model per-approach tidak tersedia, layanan "
        "jatuh ke alokasi model agregat."
    ),
)
def predict_approach_forecast(
    request: ForecastApproachRequest,
) -> dict[str, Any]:
    try:
        records = [record.model_dump(mode="json") for record in request.records]
        try:
            return per_approach_forecast_service.predict_records(records)
        except Exception as primary_exc:
            from app.services.forecast_service import forecast_service

            result = forecast_service.predict_approach_records(records)
            result["forecastSource"] = "aggregate-recent-share-fallback"
            result["fallbackUsed"] = True
            result["fallbackReason"] = str(primary_exc)
            return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Forecast per pendekat gagal dijalankan: {exc}",
        ) from exc
