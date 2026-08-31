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


class SimulationPhasePlan(BaseModel):
    approach: str
    greenSeconds: int = Field(ge=1)
    yellowSeconds: int = Field(default=4, ge=1)


class SimulationCyclePlan(BaseModel):
    phases: list[SimulationPhasePlan] = Field(min_length=4, max_length=4)
    candidateId: str | None = None
    source: str = "rule-based"
    totalCycleSeconds: int | None = Field(default=None, ge=0)


class SimulationRequest(BaseModel):
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
        description="Durasi simulasi dalam detik.",
    )

    gui: bool = Field(
        default=False,
        description="Jalankan SUMO GUI atau tidak.",
    )

    guiDelayMs: int = Field(
        default=100,
        ge=0,
        description="Delay GUI SUMO dalam milidetik.",
    )

    seed: int = Field(
        default=42,
        description="Random seed untuk simulasi.",
    )

    approaches: list[SimulationApproachDemand] | None = None

    cyclePlan: SimulationCyclePlan | None = None

    trafficTimestamp: str | None = None


class SimulationClockRequest(BaseModel):
    videoTimeSeconds: float = Field(ge=0)


class SimulationScenarioRequest(BaseModel):
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
