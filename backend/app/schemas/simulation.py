from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SimulationApproachDemand(BaseModel):
    approach: str
    targetVehicleCount: int = Field(ge=0)
    motorcycleCount: int = Field(default=0, ge=0)
    carCount: int = Field(default=0, ge=0)
    busCount: int = Field(default=0, ge=0)
    truckCount: int = Field(default=0, ge=0)
    # CCTV lengan ini mati -> demand di atas berasal dari data lama yang
    # diputar ulang. Kendaraannya ditandai biru di SUMO-GUI.
    stale: bool = False
    dataTimestamp: str | None = Field(
        default=None,
        description="ISO timestamp data lama yang diputar untuk lengan ini.",
    )


class SimulationStaleApproachesRequest(BaseModel):
    context: str = Field(default="default")
    # {approach: isoTimestampDataLama | null}. Kosong = semua lengan live.
    approaches: dict[str, str | None] = Field(default_factory=dict)


class SimulationPhasePlan(BaseModel):
    approach: str
    greenSeconds: int = Field(ge=1)
    yellowSeconds: int = Field(default=4, ge=1)


class SimulationCyclePlan(BaseModel):
    phases: list[SimulationPhasePlan] = Field(min_length=4, max_length=4)
    candidateId: str | None = None
    source: str = "rule-based"
    totalCycleSeconds: int | None = Field(default=None, ge=0)
    # Geser posisi siklus (detik) supaya fase SUMO cocok dengan rekaman CCTV
    # yang tidak mulai tepat di awal siklus lampu. Dipakai _pick_camera_phase.
    startOffsetSeconds: float = Field(default=0.0, ge=0)


class SimulationRequest(BaseModel):
    context: str = Field(
        default="default",
        description=(
            "Slot instance SUMO yang dikendalikan, mis. 'dashboard' vs "
            "'digitaltwin' -- keduanya bisa jalan bersamaan tanpa saling "
            "pengaruh (start/pause/stop/skenario terpisah per context)."
        ),
    )

    intersectionId: str = Field(
        ...,
        description="ID intersection, contoh: simpang4-pingit",
    )

    trafficStateId: int | None = Field(
        default=None,
        description="ID traffic state. Jika null, gunakan traffic state terbaru.",
    )

    scenario: Literal["Traffic Realtime", "Baseline", "Aggressive", "Balanced"] = Field(
        default="Baseline",
        description="Scenario yang digunakan untuk simulasi (Baseline, Aggressive, Balanced).",
    )

    durationSeconds: int = Field(
        default=60,
        ge=1,
        le=3600,
        description="Durasi simulasi dalam detik.",
    )

    gui: bool = Field(
        default=False,
        description="Jalankan SUMO GUI atau tidak.",
    )

    guiDelayMs: int = Field(
        default=100,
        ge=0,
        le=5000,
        description="Delay GUI SUMO dalam milidetik.",
    )

    seed: int = Field(
        default=42,
        description="Random seed untuk simulasi.",
    )

    approaches: list[SimulationApproachDemand] | None = None

    cyclePlan: SimulationCyclePlan | None = None

    trafficTimestamp: str | None = None

    # Dikirim bersama demand agar pergantian live -> history tidak berlomba
    # dengan heartbeat /sync-clock. None menjaga caller lama tetap kompatibel.
    offlineApproaches: list[str] | None = None
    videoTimeSeconds: float | None = Field(default=None, ge=0)


class SimulationClockRequest(BaseModel):
    context: str = Field(default="default")
    videoTimeSeconds: float = Field(ge=0)
    videoDurationSeconds: float | None = Field(default=None, gt=0)
    # Lengan (approach) yang lagi ditandai "CCTV mati" (simulasi manual)
    # di dashboard -- lihat rencana-fallback-cctv-per-lengan.md Step 5.
    offlineApproaches: list[str] = Field(default_factory=list)


class SimulationScenarioRequest(BaseModel):
    context: str = Field(default="default")
    scenario: Literal["Traffic Realtime", "Baseline", "Aggressive", "Balanced"]
    cyclePlan: SimulationCyclePlan


class SimulationResult(BaseModel):
    trafficStateId: int | None = None
    intersectionId: str

    durationSeconds: int

    spawnedVehicles: int = 0
    departedVehicles: int = 0
    arrivedVehicles: int = 0
    activeVehicles: int = 0

    averageWaitingTimeSeconds: float = 0.0

    departedByApproach: dict[str, int] = Field(
        default_factory=dict
    )

    arrivedByApproach: dict[str, int] = Field(
        default_factory=dict
    )
