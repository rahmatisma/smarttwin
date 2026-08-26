from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# BASE MODEL
# ============================================================

class CamelCaseModel(BaseModel):

    model_config = ConfigDict(
        populate_by_name=True,
    )


# ============================================================
# SIGNAL PHASE
# ============================================================

class SignalPhase(
    CamelCaseModel
):

    phaseId: str

    state: str

    durationSeconds: int = Field(
        ge=0
    )

    remainingSeconds: int = Field(
        default=0,
        ge=0,
    )


# ============================================================
# SIGNAL STATUS
# ============================================================

class SignalStatus(
    CamelCaseModel
):

    intersectionId: str

    timestamp: datetime

    currentPhase: str

    phaseName: str

    remainingSeconds: int = Field(
        ge=0
    )

    cycleTimeSeconds: int = Field(
        ge=0
    )

    phases: dict[
        str,
        SignalPhase
    ] = Field(
        default_factory=dict
    )

    # Lengan berikutnya dalam rotasi (FIXED_CYCLE_ORDER) -- durasinya
    # bisa dilihat lewat phases[nextPhase].durationSeconds, SAMA
    # sumbernya dengan yang ditampilkan di panel Rekomendasi Sinyal
    # (lihat SignalService._cycle_plan / RecommendationService).
    nextPhase: str = ""

    nextPhaseName: str = ""

    source: str = "simulation"


# ============================================================
# SIGNAL UPDATE
# ============================================================

class SignalUpdate(
    CamelCaseModel
):

    intersectionId: str

    currentPhase: str

    phaseName: str

    remainingSeconds: int = Field(
        ge=0
    )

    cycleTimeSeconds: int = Field(
        ge=0
    )

    phases: dict[
        str,
        SignalPhase
    ] = Field(
        default_factory=dict
    )