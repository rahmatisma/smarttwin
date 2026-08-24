from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


# ============================================================
# PATH
# ============================================================

simulationRoot = Path(__file__).resolve().parent
projectRoot = simulationRoot.parent
backendRoot = projectRoot / "backend"
decisionEngineRoot = projectRoot / "decision_engine"

envFile = backendRoot / ".env"


# ============================================================
# PYTHON PATH
# ============================================================

# smarttwin/
# ├── backend/
# ├── decision_engine/
# └── simulation/
#
# Project root diperlukan agar:
#
# from decision_engine.rule_based_engine import RuleBasedEngine
#
# bisa ditemukan.

if str(projectRoot) not in sys.path:
    sys.path.insert(0, str(projectRoot))


# Backend root diperlukan agar:
#
# from app....
#
# bisa ditemukan.

if str(backendRoot) not in sys.path:
    sys.path.insert(0, str(backendRoot))


# ============================================================
# VALIDATE PROJECT STRUCTURE
# ============================================================

if not backendRoot.exists():
    raise RuntimeError(
        f"Backend tidak ditemukan:\n{backendRoot}"
    )


if not decisionEngineRoot.exists():
    raise RuntimeError(
        "Decision engine tidak ditemukan:\n"
        f"{decisionEngineRoot}"
    )


ruleBasedEngineFile = (
    decisionEngineRoot / "rule_based_engine.py"
)

if not ruleBasedEngineFile.exists():
    raise RuntimeError(
        "Rule-based engine tidak ditemukan:\n"
        f"{ruleBasedEngineFile}"
    )


if not envFile.exists():
    raise RuntimeError(
        "Backend .env tidak ditemukan:\n"
        f"{envFile}"
    )


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv(
    dotenv_path=envFile,
    override=False,
)


# ============================================================
# SUMO
# ============================================================

def findSumo() -> tuple[Path, Path]:
    """
    Mencari executable SUMO.

    Prioritas:

    1. simulation/.venv/Scripts/sumo.exe
    2. SUMO_HOME/bin/sumo.exe
    3. PATH
    """

    candidates = [
        simulationRoot
        / ".venv"
        / "Scripts"
        / "sumo.exe",

        simulationRoot
        / ".venv"
        / "Scripts"
        / "sumo",
    ]

    # --------------------------------------------------------
    # LOCAL VENV
    # --------------------------------------------------------

    for candidate in candidates:

        if candidate.exists():

            toolsDirectory = (
                simulationRoot
                / ".venv"
                / "Lib"
                / "site-packages"
                / "sumolib"
            )

            if not toolsDirectory.exists():

                toolsDirectory = (
                    simulationRoot
                    / ".venv"
                    / "Lib"
                    / "site-packages"
                )

            return (
                candidate,
                toolsDirectory,
            )

    # --------------------------------------------------------
    # SUMO_HOME
    # --------------------------------------------------------

    sumoHome = os.environ.get("SUMO_HOME")

    if sumoHome:

        homePath = Path(sumoHome)

        executable = (
            homePath
            / "bin"
            / "sumo.exe"
        )

        toolsDirectory = (
            homePath
            / "tools"
        )

        if executable.exists():

            return (
                executable,
                toolsDirectory,
            )

    # --------------------------------------------------------
    # SYSTEM PATH
    # --------------------------------------------------------

    try:

        result = subprocess.run(
            ["where", "sumo"],
            capture_output=True,
            text=True,
            check=True,
        )

        firstLine = (
            result.stdout
            .strip()
            .splitlines()[0]
        )

        executable = Path(firstLine)

        possibleHome = (
            executable.parent.parent
        )

        toolsDirectory = (
            possibleHome / "tools"
        )

        return (
            executable,
            toolsDirectory,
        )

    except Exception:
        pass

    raise RuntimeError(
        "SUMO tidak ditemukan.\n\n"
        "Sudah dicoba:\n"
        f"- {simulationRoot / '.venv' / 'Scripts' / 'sumo.exe'}\n"
        "- SUMO_HOME\n"
        "- PATH"
    )


sumoBinary, sumoTools = findSumo()


# ============================================================
# BACKEND IMPORT
# ============================================================

from app.pipeline.traffic_state_builder import (
    TrafficStateBuilder,
    TrafficStateBuilderConfig,
)


# ============================================================
# DECISION ENGINE IMPORT
# ============================================================

from decision_engine.rule_based_engine import (
    RuleBasedEngine,
)


# ============================================================
# TRACI
# ============================================================

try:

    import traci

except ModuleNotFoundError:

    if sumoTools.exists():

        if str(sumoTools) not in sys.path:

            sys.path.insert(
                0,
                str(sumoTools),
            )

    import traci


# ============================================================
# CONFIGURATION
# ============================================================

intersectionId = "simpang4-pingit"

sumoConfig = (
    simulationRoot
    / "network"
    / "simpang4_pingit.sumocfg"
)

tlsId = "SIMPANG_CENTER"

simulationStepLimit = 300


# ============================================================
# APPROACH → SUMO PHASE
# ============================================================

approachToPhase = {

    "south": 0,

    "east": 1,

    "north": 2,

    "west": 3,
}


# ============================================================
# HEADER
# ============================================================

def printHeader(
    title: str,
) -> None:

    print()

    print("=" * 70)

    print(title)

    print("=" * 70)


# ============================================================
# ENVIRONMENT INFO
# ============================================================

def printEnvironment() -> None:

    printHeader(
        "ENVIRONMENT"
    )

    print(
        f"Simulation root : "
        f"{simulationRoot}"
    )

    print(
        f"Backend root    : "
        f"{backendRoot}"
    )

    print(
        f"Decision engine : "
        f"{decisionEngineRoot}"
    )

    print(
        f".env            : "
        f"{envFile}"
    )

    print(
        f"SUMO binary     : "
        f"{sumoBinary}"
    )

    print(
        f"SUMO tools      : "
        f"{sumoTools}"
    )

    print(
        "SUPABASE_URL    : OK"
        if os.getenv("SUPABASE_URL")
        else "SUPABASE_URL    : MISSING"
    )

    print(
        "SUPABASE_KEY    : OK"
        if os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        else "SUPABASE_KEY    : MISSING"
    )


# ============================================================
# LOAD TRAFFIC STATE
# ============================================================

def loadTrafficState():

    printHeader(
        "LOADING TRAFFIC STATE"
    )

    builder = TrafficStateBuilder(
        TrafficStateBuilderConfig(
            windowSeconds=5
        )
    )

    trafficState = (
        builder.build_latest_state_for_intersection(
            intersection_id=intersectionId,
            save=False,
        )
    )

    if trafficState is None:

        raise RuntimeError(
            "TrafficState tidak ditemukan "
            "di Supabase."
        )

    print()

    print(
        "TrafficState berhasil dimuat."
    )

    builder.print_state(
        trafficState
    )

    return trafficState


# ============================================================
# DECISION ENGINE
# ============================================================

def createDecision(
    trafficState,
):

    printHeader(
        "RUNNING DECISION ENGINE"
    )

    engine = RuleBasedEngine()

    recommendation = (
        engine.recommend(
            state=trafficState,
            currentGreenSeconds=15,
            currentPhase="south",
        )
    )

    print()

    print(
        "Decision Engine berhasil."
    )

    print()

    print(
        f"Recommended approach : "
        f"{recommendation.recommendedPhase}"
    )

    recommendedApproach = (
        recommendation.recommendedPhase
    )

    sumoPhase = approachToPhase.get(
        recommendedApproach
    )

    if sumoPhase is None:

        raise ValueError(
            "Approach tidak memiliki "
            "mapping SUMO phase: "
            f"{recommendedApproach}"
        )

    print(
        f"SUMO phase            : "
        f"{sumoPhase}"
    )

    print(
        f"Green duration        : "
        f"{recommendation.recommendedGreenSeconds}s"
    )

    print(
        f"Current green         : "
        f"{recommendation.currentGreenSeconds}s"
    )

    print(
        f"Confidence            : "
        f"{recommendation.confidence}"
    )

    print(
        f"Delay reduction       : "
        f"{recommendation.expectedDelayReductionPercent}"
    )

    print(
        f"Source                : "
        f"{recommendation.source}"
    )

    print(
        f"Reason                : "
        f"{recommendation.reason}"
    )

    # ========================================================
    # PHASE PLAN
    # ========================================================

    phasePlan = {

        "approach":
            recommendedApproach,

        "sumoPhase":
            sumoPhase,

        "duration":
            recommendation.recommendedGreenSeconds,

        "reason":
            recommendation.reason,

        "confidence":
            recommendation.confidence,

        "source":
            recommendation.source,
    }

    print()

    print(
        "Phase plan berhasil dibuat."
    )

    print(
        f"  Approach   : "
        f"{phasePlan['approach']}"
    )

    print(
        f"  SUMO phase : "
        f"{phasePlan['sumoPhase']}"
    )

    print(
        f"  Duration   : "
        f"{phasePlan['duration']}s"
    )

    return (
        recommendation,
        phasePlan,
    )


# ============================================================
# START SUMO
# ============================================================

def startSumo():

    printHeader(
        "STARTING SUMO"
    )

    if not sumoConfig.exists():

        raise FileNotFoundError(
            "SUMO config tidak ditemukan:\n"
            f"{sumoConfig}"
        )

    command = [

        str(sumoBinary),

        "-c",

        str(sumoConfig),

        "--start",
    ]

    print(
        "Command:",
        " ".join(command),
    )

    traci.start(
        command
    )

    print(
        "SUMO berhasil dimulai."
    )

    trafficLightIds = (
        traci.trafficlight
        .getIDList()
    )

    print(
        f"Traffic Light ID: "
        f"{tlsId}"
    )

    if tlsId not in trafficLightIds:

        raise RuntimeError(
            f"TLS '{tlsId}' tidak ditemukan. "
            f"Available: {trafficLightIds}"
        )


# ============================================================
# APPLY TLS
# ============================================================

def applyTls(
    phasePlan: dict[str, Any],
) -> None:

    printHeader(
        "TLS PHASE APPLIED"
    )

    traci.trafficlight.setPhase(
        tlsId,
        phasePlan["sumoPhase"],
    )

    traci.trafficlight.setPhaseDuration(
        tlsId,
        phasePlan["duration"],
    )

    print(
        f"TLS       : {tlsId}"
    )

    print(
        f"Approach  : "
        f"{phasePlan['approach']}"
    )

    print(
        f"SUMO phase: "
        f"{phasePlan['sumoPhase']}"
    )

    print(
        f"Duration  : "
        f"{phasePlan['duration']}s"
    )

    print(
        f"Reason    : "
        f"{phasePlan['reason']}"
    )

    print(
        f"Confidence: "
        f"{phasePlan['confidence']}"
    )

    print(
        f"Source    : "
        f"{phasePlan['source']}"
    )


# ============================================================
# RUN SIMULATION
# ============================================================

def runSimulation():

    printHeader(
        "SIMULATION RUNNING"
    )

    steps = 0

    arrivedVehicles = 0

    departedVehicles = 0

    while steps < simulationStepLimit:

        try:

            traci.simulationStep()

        except Exception as exception:

            print(
                "SUMO step error:",
                exception,
            )

            break

        steps += 1

        try:

            arrivedVehicles = (
                traci.simulation
                .getArrivedNumber()
            )

            departedVehicles = (
                traci.simulation
                .getDepartedNumber()
            )

            activeVehicles = (
                traci.vehicle
                .getIDCount()
            )

            expectedVehicles = (
                traci.simulation
                .getMinExpectedNumber()
            )

        except Exception:

            activeVehicles = 0

            expectedVehicles = 0

        if steps % 10 == 0:

            print(
                f"[t={steps:4d}s] "
                f"active={activeVehicles:<4} "
                f"expected={expectedVehicles:<4}"
            )

        if expectedVehicles == 0:

            break

    # ========================================================
    # FINAL VALUES
    # ========================================================

    try:

        activeVehicles = (
            traci.vehicle
            .getIDCount()
        )

    except Exception:

        activeVehicles = 0

    return {

        "steps":
            steps,

        "activeVehicles":
            activeVehicles,

        "arrivedVehicles":
            arrivedVehicles,

        "departedVehicles":
            departedVehicles,
    }


# ============================================================
# TLS RESULT
# ============================================================

def getTlsResult(
    phasePlan: dict[str, Any],
):

    finalPhase = (
        traci.trafficlight
        .getPhase(
            tlsId
        )
    )

    tlsState = (
        traci.trafficlight
        .getRedYellowGreenState(
            tlsId
        )
    )

    return {

        "approach":
            phasePlan["approach"],

        "finalPhase":
            finalPhase,

        "greenDurationSeconds":
            phasePlan["duration"],

        "tlsState":
            tlsState,
    }


# ============================================================
# BUILD SIMULATION RESULT
# ============================================================

def buildSimulationMetrics(
    simulationMetrics: dict[str, Any],
    tlsResult: dict[str, Any],
):

    return {

        "steps":
            simulationMetrics["steps"],

        "activeVehicles":
            simulationMetrics["activeVehicles"],

        "arrivedVehicles":
            simulationMetrics["arrivedVehicles"],

        "departedVehicles":
            simulationMetrics["departedVehicles"],

        "finalPhase":
            tlsResult["finalPhase"],

        "tlsState":
            tlsResult["tlsState"],
    }


# ============================================================
# PRINT RESULT
# ============================================================

def printSimulationResult(
    simulationMetrics,
    tlsResult,
):

    printHeader(
        "SIMULATION METRICS"
    )

    print(
        f"Simulation steps : "
        f"{simulationMetrics['steps']}"
    )

    print(
        f"Active vehicles  : "
        f"{simulationMetrics['activeVehicles']}"
    )

    print(
        f"Arrived vehicles : "
        f"{simulationMetrics['arrivedVehicles']}"
    )

    print(
        f"Departed         : "
        f"{simulationMetrics['departedVehicles']}"
    )

    print(
        f"TLS approach     : "
        f"{tlsResult['approach']}"
    )

    print(
        f"TLS phase        : "
        f"{tlsResult['finalPhase']}"
    )

    print(
        f"TLS duration     : "
        f"{tlsResult['greenDurationSeconds']}s"
    )

    print(
        f"TLS state        : "
        f"{tlsResult['tlsState']}"
    )


# ============================================================
# SAVE RESULT TO SUPABASE
# ============================================================

def saveSimulationResult(
    trafficState,
    phasePlan,
    simulationMetrics,
    tlsResult,
):

    printHeader(
        "SAVING SIMULATION RESULT"
    )

    try:

        from app.services.simulation_result_writer import (
            SimulationResultWriter,
        )

    except Exception as exception:

        print(
            "SimulationResultWriter tidak dapat "
            "di-import."
        )

        print(
            f"Error: {exception}"
        )

        return None

    resultWriter = (
        SimulationResultWriter()
    )

    metricsPayload = (
        buildSimulationMetrics(
            simulationMetrics,
            tlsResult,
        )
    )

    simulationRunId = (
        resultWriter.saveResult(
            trafficState=trafficState,
            phasePlan=phasePlan,
            simulationMetrics=metricsPayload,
        )
    )

    print()

    print(
        "Hasil simulasi berhasil disimpan."
    )

    print(
        f"Simulation run ID : "
        f"{simulationRunId}"
    )

    return simulationRunId


# ============================================================
# MAIN
# ============================================================

def main():

    print()

    print("=" * 70)

    print(
        "SMARTTWIN ADAPTIVE TLS SIMULATION"
    )

    print("=" * 70)

    # --------------------------------------------------------
    # ENVIRONMENT
    # --------------------------------------------------------

    printEnvironment()

    # --------------------------------------------------------
    # TRAFFIC STATE
    # --------------------------------------------------------

    trafficState = (
        loadTrafficState()
    )

    # --------------------------------------------------------
    # DECISION ENGINE
    # --------------------------------------------------------

    (
        recommendation,
        phasePlan,
    ) = createDecision(
        trafficState
    )

    # --------------------------------------------------------
    # START SUMO
    # --------------------------------------------------------

    startSumo()

    try:

        # ----------------------------------------------------
        # APPLY TLS
        # ----------------------------------------------------

        applyTls(
            phasePlan
        )

        # ----------------------------------------------------
        # RUN SIMULATION
        # ----------------------------------------------------

        simulationMetrics = (
            runSimulation()
        )

        # ----------------------------------------------------
        # TLS RESULT
        # ----------------------------------------------------

        tlsResult = (
            getTlsResult(
                phasePlan
            )
        )

        # ----------------------------------------------------
        # PRINT RESULT
        # ----------------------------------------------------

        printSimulationResult(
            simulationMetrics,
            tlsResult,
        )

        # ----------------------------------------------------
        # BUILD RESULT
        # ----------------------------------------------------

        finalMetrics = (
            buildSimulationMetrics(
                simulationMetrics,
                tlsResult,
            )
        )

        # ----------------------------------------------------
        # SAVE TO SUPABASE
        # ----------------------------------------------------

        saveSimulationResult(
            trafficState=trafficState,
            phasePlan=phasePlan,
            simulationMetrics=finalMetrics,
            tlsResult=tlsResult,
        )

    finally:

        try:

            traci.close()

            print()

            print(
                "SUMO connection ditutup."
            )

        except Exception:

            pass

    # --------------------------------------------------------
    # FINAL
    # --------------------------------------------------------

    printHeader(
        "SMARTTWIN TLS SIMULATION SELESAI"
    )

    print(
        "TrafficState"
    )

    print(
        "     ↓"
    )

    print(
        "Rule-Based Decision Engine"
    )

    print(
        "     ↓"
    )

    print(
        "Phase Mapping"
    )

    print(
        "     ↓"
    )

    print(
        "TLS Controller"
    )

    print(
        "     ↓"
    )

    print(
        "SUMO"
    )

    print(
        "     ↓"
    )

    print(
        "Simulation Metrics"
    )

    print(
        "     ↓"
    )

    print(
        "Supabase"
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()