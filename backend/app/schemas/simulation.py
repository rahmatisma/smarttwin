from __future__ import annotations

from pydantic import BaseModel, Field


class SimulationRequest(BaseModel):
    intersectionId: str = Field(
        ...,
        description="ID intersection, contoh: simpang4-pingit",
    )

    trafficStateId: int | None = Field(
        default=None,
        description="ID traffic state. Jika null, gunakan traffic state terbaru.",
    )

    scenario: str = Field(
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