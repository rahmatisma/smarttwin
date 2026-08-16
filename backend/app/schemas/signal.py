from datetime import datetime
from typing import Dict

from pydantic import BaseModel, Field


class SignalPhase(BaseModel):
    phase_id: str

    state: str

    duration_seconds: int = Field(ge=0)

    remaining_seconds: int = Field(default=0, ge=0)


class SignalStatus(BaseModel):
    intersection_id: str

    timestamp: datetime

    current_phase: str

    phase_name: str

    remaining_seconds: int = Field(ge=0)

    cycle_time_seconds: int = Field(ge=0)

    phases: Dict[str, SignalPhase] = Field(default_factory=dict)

    source: str = "simulation"


class SignalUpdate(BaseModel):
    intersection_id: str

    current_phase: str

    phase_name: str

    remaining_seconds: int = Field(ge=0)

    cycle_time_seconds: int = Field(ge=0)

    phases: Dict[str, SignalPhase] = Field(default_factory=dict)