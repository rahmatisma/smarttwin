from __future__ import annotations

import json
import os
import subprocess
import tempfile

from datetime import datetime, timezone
from pathlib import Path

from app.pipeline.traffic_state_builder import (
    TrafficStateBuilder,
)
from app.schemas.simulation import (
    SimulationRequest,
    SimulationResult,
)
from app.services.traffic_repository import (
    TrafficRepository,
)


class SimulationServiceError(Exception):
    """Error saat menjalankan simulasi SUMO."""


class SimulationService:

    def __init__(
        self,
        repository: TrafficRepository | None = None,
    ) -> None:

        self.repository = (
            repository
            or TrafficRepository()
        )

        # ====================================================
        # PROJECT ROOT
        # ====================================================

        self.project_root = (
            Path(__file__)
            .resolve()
            .parents[2]
        )

        # ====================================================
        # SIMULATION ROOT
        #
        # smarttwin/
        # ├── backend/
        # └── simulation/
        # ====================================================

        self.simulation_root = (
            self.project_root
            / "simulation"
        )

        # ====================================================
        # SUMO RUNNER
        # ====================================================

        self.runner = (
            self.simulation_root
            / "run_simulation.py"
        )

        # ====================================================
        # PYTHON SIMULATION ENV
        # ====================================================

        self.python = (
            self.simulation_root
            / ".venv"
            / "Scripts"
            / "python.exe"
        )

        # ====================================================
        # SUMO NETWORK
        # ====================================================

        self.net_file = (
            self.simulation_root
            / "network"
            / "simpang4_pingit.net.xml.gz"
        )

    # ========================================================
    # RUN
    # ========================================================

    def run(
        self,
        request: SimulationRequest,
    ) -> SimulationResult:

        # ====================================================
        # VALIDATE FILES
        # ====================================================

        if not self.python.exists():

            raise SimulationServiceError(
                "Python simulation tidak ditemukan: "
                f"{self.python}"
            )

        if not self.runner.exists():

            raise SimulationServiceError(
                "SUMO runner tidak ditemukan: "
                f"{self.runner}"
            )

        if not self.net_file.exists():

            raise SimulationServiceError(
                "Network SUMO tidak ditemukan: "
                f"{self.net_file}"
            )

        # ====================================================
        # LOAD TRAFFIC STATE
        # ====================================================

        intersectionRowId = (
            self.repository
            .get_intersection_row_id(
                request.intersectionId
            )
        )

        raw_states = (
            self.repository
            .get_latest_traffic_states(
                intersection_row_id=intersectionRowId,
                limit=100,
            )
        )

        # ====================================================
        # FILTER TRAFFIC STATE ID
        # ====================================================

        if request.trafficStateId is not None:

            raw_states = [
                row
                for row in raw_states
                if int(row["id"])
                == request.trafficStateId
            ]

        if not raw_states:

            raise SimulationServiceError(
                "TrafficState tidak ditemukan."
            )

        raw_state = raw_states[0]

        # ====================================================
        # BUILD TRAFFIC STATE
        # ====================================================

        builder = TrafficStateBuilder()

        states = (
            builder.buildFromSupabase(
                intersectionId=(
                    request.intersectionId
                ),
                trafficStateId=(
                    request.trafficStateId
                ),
                limit=(
                    None
                    if request.trafficStateId
                    is not None
                    else 100
                ),
            )
        )

        if not states:

            raise SimulationServiceError(
                "TrafficState tidak memiliki "
                "data approach."
            )

        target = states[0]

        # ====================================================
        # CREATE INPUT JSON
        # ====================================================

        payload = target.model_dump(
            mode="json"
        )

        payload["trafficStateId"] = int(
            raw_state["id"]
        )

        # ====================================================
        # TEMP DIRECTORY
        # ====================================================

        with tempfile.TemporaryDirectory(
            prefix="smarttwin-sumo-"
        ) as directory:

            directory_path = Path(
                directory
            )

            input_file = (
                directory_path
                / "traffic_state.json"
            )

            output_file = (
                directory_path
                / "simulation_result.json"
            )

            input_file.write_text(
                json.dumps(
                    payload
                ),
                encoding="utf-8",
            )

            # =================================================
            # COMMAND
            # =================================================

            command = [
                str(self.python),
                str(self.runner),
                "--input",
                str(input_file),
                "--output",
                str(output_file),
                "--net-file",
                str(self.net_file),
                "--duration",
                str(
                    request.durationSeconds
                ),
            ]

            if request.seed is not None:

                command.extend(
                    [
                        "--seed",
                        str(request.seed),
                    ]
                )

            if request.gui:

                command.extend(
                    [
                        "--gui",
                        "--gui-delay",
                        str(
                            request.guiDelayMs
                        ),
                    ]
                )

            # =================================================
            # RUN SUMO
            # =================================================

            try:

                subprocess.run(
                    command,
                    cwd=self.simulation_root,
                    check=True,
                    timeout=(
                        request.durationSeconds
                        + 120
                    ),
                    env=self._environment(),
                )

            except (
                OSError,
                subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
            ) as exc:

                raise SimulationServiceError(
                    f"SUMO gagal dijalankan: {exc}"
                ) from exc

            # =================================================
            # RESULT
            # =================================================

            if not output_file.exists():

                raise SimulationServiceError(
                    "SUMO tidak menghasilkan "
                    "result JSON."
                )

            result = json.loads(
                output_file.read_text(
                    encoding="utf-8"
                )
            )

            result["simulatedAt"] = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

            return SimulationResult.model_validate(
                result
            )

    # ========================================================
    # ENVIRONMENT
    # ========================================================

    def _environment(
        self,
    ) -> dict[str, str]:

        environment = os.environ.copy()

        sumo_home = (
            self.simulation_root
            / ".venv"
            / "Lib"
            / "site-packages"
            / "sumo"
        )

        environment["SUMO_HOME"] = str(
            sumo_home
        )

        environment["PATH"] = (
            f"{sumo_home / 'bin'}"
            f"{os.pathsep}"
            f"{environment.get('PATH', '')}"
        )

        return environment


simulation_service = (
    SimulationService()
)