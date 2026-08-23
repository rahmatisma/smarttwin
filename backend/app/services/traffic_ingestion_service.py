from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.pipeline.traffic_state_builder import (
    TrafficStateBuilder,
    TrafficStateBuilderConfig,
)
from app.services.traffic_repository import (
    TrafficRepository,
)
from app.schemas.traffic import TrafficState


# ============================================================
# RESULT
# ============================================================

@dataclass(frozen=True)
class TrafficIngestionResult:
    """
    Hasil proses ingestion traffic.
    """

    csvPath: str
    totalStates: int
    processedStates: int


# ============================================================
# SERVICE
# ============================================================

class TrafficIngestionService:
    """
    Service utama untuk ingestion data traffic.

    Flow:

        CSV
          ↓
        TrafficStateBuilder
          ↓
        TrafficState[]
          ↓
        TrafficRepository
          ↓
        Supabase
    """

    def __init__(
        self,
        *,
        builder: TrafficStateBuilder | None = None,
        repository: TrafficRepository | None = None,
    ) -> None:

        self.builder = (
            builder
            if builder is not None
            else TrafficStateBuilder(
                TrafficStateBuilderConfig(
                    windowSeconds=5
                )
            )
        )

        self.repository = (
            repository
            if repository is not None
            else TrafficRepository()
        )

    # ========================================================
    # BUILD STATES
    # ========================================================

    def buildStates(
        self,
        crossPath: str | Path,
        densityPath: str | Path,
    ) -> list[TrafficState]:

        return self.builder.buildFromCvOutput(
            crossPath,
            densityPath
        )

    # ========================================================
    # INGEST ONE STATE
    # ========================================================

    def ingestState(
        self,
        state: TrafficState,
        *,
        source: str = "cv",
        processingJobId: int | None = None,
    ) -> dict:

        return self.repository.save_traffic_state(
            state,
            source=source,
            processing_job_id=processingJobId,
        )

    # ========================================================
    # INGEST MANY STATES
    # ========================================================

    def ingestStates(
        self,
        states: list[TrafficState],
        *,
        source: str = "cv",
        processingJobId: int | None = None,
    ) -> int:

        if not states:
            return 0

        return self.repository.save_traffic_states(
            states,
            source=source,
            processing_job_id=processingJobId,
        )

    # ========================================================
    # INGEST CSV
    # ========================================================

    def ingestCvOutput(
        self,
        crossPath: str | Path,
        densityPath: str | Path,
        *,
        source: str = "cv",
        processingJobId: int | None = None,
    ) -> TrafficIngestionResult:

        crossPath = Path(crossPath)
        densityPath = Path(densityPath)

        states = self.buildStates(
            crossPath,
            densityPath
        )

        processedStates = self.ingestStates(
            states,
            source=source,
            processingJobId=processingJobId,
        )

        return TrafficIngestionResult(
            csvPath=f"{crossPath.name} & {densityPath.name}",
            totalStates=len(states),
            processedStates=processedStates,
        )