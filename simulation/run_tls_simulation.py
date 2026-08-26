from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


# ============================================================
# PATH
# ============================================================

simulationRoot = (
    Path(__file__)
    .resolve()
    .parent
)

projectRoot = (
    simulationRoot.parent
)

backendRoot = (
    projectRoot
    / "backend"
)

decisionEngineRoot = (
    projectRoot
    / "decision_engine"
)

envFile = (
    backendRoot
    / ".env"
)


# ============================================================
# PYTHON PATH
# ============================================================

if str(projectRoot) not in sys.path:

    sys.path.insert(
        0,
        str(projectRoot),
    )

if str(backendRoot) not in sys.path:

    sys.path.insert(
        0,
        str(backendRoot)
    )


# ============================================================
# VALIDATE STRUCTURE
# ============================================================

if not backendRoot.exists():

    raise RuntimeError(
        "Backend tidak ditemukan:\n"
        f"{backendRoot}"
    )


if not decisionEngineRoot.exists():

    raise RuntimeError(
        "Decision engine tidak ditemukan:\n"
        f"{decisionEngineRoot}"
    )


if not envFile.exists():

    raise RuntimeError(
        "Backend .env tidak ditemukan:\n"
        f"{envFile}"
    )


ruleBasedEngineFile = (
    decisionEngineRoot
    / "rule_based_engine.py"
)

if not ruleBasedEngineFile.exists():

    raise RuntimeError(
        "Rule-based engine tidak ditemukan:\n"
        f"{ruleBasedEngineFile}"
    )


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv(
    dotenv_path=envFile,
    override=True,
)


# ============================================================
# SUMO
# ============================================================

def findSumo() -> tuple[Path, Path]:
    """
    Mencari SUMO executable.
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

    sumoHome = os.environ.get(
        "SUMO_HOME"
    )

    if sumoHome:

        homePath = Path(
            sumoHome
        )

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
            [
                "where",
                "sumo",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        lines = (
            result.stdout
            .strip()
            .splitlines()
        )

        if lines:

            executable = Path(
                lines[0]
            )

            possibleHome = (
                executable
                .parent
                .parent
            )

            toolsDirectory = (
                possibleHome
                / "tools"
            )

            return (
                executable,
                toolsDirectory,
            )

    except Exception:
        pass

    raise RuntimeError(
        "SUMO tidak ditemukan."
    )


sumoBinary, sumoTools = findSumo()


# ============================================================
# BACKEND IMPORTS
# ============================================================

from app.pipeline.traffic_state_builder import (
    TrafficStateBuilder,
    TrafficStateBuilderConfig,
)


from app.services.simulation_result_writer import (
    SimulationResultWriter,
)


# ============================================================
# SCENARIO GENERATOR (kotak 7-8-9-10, bungkus RuleBasedEngine)
# ============================================================

from scenario_generator import (
    ScenarioEngine,
)

from forecast_client import (
    ForecastClient,
)


# ============================================================
# SUPABASE
# ============================================================

from supabase import (
    Client,
    create_client,
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

intersectionId = (
    "simpang4-pingit"
)

sumoConfig = (
    simulationRoot
    / "network"
    / "simpang4_pingit.sumocfg"
)

tlsId = (
    "SIMPANG_CENTER"
)

simulationStepLimit = 300


# ============================================================
# APPROACH → SUMO PHASE
# ============================================================

approachToPhase = {

    "south": 0,

    "east": 2,

    "north": 4,

    "west": 6,
}


# ============================================================
# GLOBAL SUPABASE CLIENT
# ============================================================

supabaseClient: Client | None = None


# ============================================================
# HEADER
# ============================================================

def printHeader(
    title: str,
) -> None:

    print()

    print(
        "=" * 70
    )

    print(
        title
    )

    print(
        "=" * 70
    )


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
        if os.getenv(
            "SUPABASE_URL"
        )
        else
        "SUPABASE_URL    : MISSING"
    )

    print(
        "SUPABASE_KEY    : OK"
        if os.getenv(
            "SUPABASE_SERVICE_ROLE_KEY"
        )
        else
        "SUPABASE_KEY    : MISSING"
    )


# ============================================================
# CONNECT SUPABASE
# ============================================================

def connectSupabase() -> Client:

    global supabaseClient

    printHeader(
        "CONNECTING TO SUPABASE"
    )

    supabaseUrl = (
        os.getenv(
            "SUPABASE_URL"
        )
        or ""
    ).strip()

    supabaseKey = (
        os.getenv(
            "SUPABASE_SERVICE_ROLE_KEY"
        )
        or ""
    ).strip()

    if not supabaseUrl:

        raise RuntimeError(
            "SUPABASE_URL tidak ditemukan "
            "di backend/.env"
        )

    if not supabaseKey:

        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY "
            "tidak ditemukan di backend/.env"
        )

    try:

        supabaseClient = (
            create_client(
                supabaseUrl,
                supabaseKey,
            )
        )

        # ----------------------------------------------------
        # Test connection
        # ----------------------------------------------------

        (
            supabaseClient
            .table("intersections")
            .select("id")
            .limit(1)
            .execute()
        )

    except Exception as exc:

        raise RuntimeError(
            "Gagal terhubung ke Supabase: "
            f"{exc}"
        ) from exc

    print(
        "Supabase connection : OK"
    )

    return supabaseClient


# ============================================================
# LOAD TRAFFIC STATE
# ============================================================

def loadTrafficState():

    printHeader(
        "LOADING TRAFFIC STATE"
    )

    builder = (
        TrafficStateBuilder(
            TrafficStateBuilderConfig(
                windowSeconds=5
            )
        )
    )

    trafficState = (
        builder
        .build_latest_state_for_intersection(
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
# EXTRACT TRAFFIC STATE ID
# ============================================================

def getTrafficStateId(
    trafficState: Any,
) -> int | None:
    """
    Mengambil ID TrafficState.

    Mendukung object maupun dict.
    """

    if trafficState is None:
        return None

    # --------------------------------------------------------
    # DICT
    # --------------------------------------------------------

    if isinstance(
        trafficState,
        dict,
    ):

        rawId = (
            trafficState.get(
                "id"
            )
        )

        if rawId is None:

            rawId = (
                trafficState.get(
                    "trafficStateId"
                )
            )

        if rawId is not None:

            try:

                return int(
                    rawId
                )

            except (
                TypeError,
                ValueError,
            ):

                pass

    # --------------------------------------------------------
    # OBJECT
    # --------------------------------------------------------

    rawId = getattr(
        trafficState,
        "id",
        None,
    )

    if rawId is None:

        rawId = getattr(
            trafficState,
            "trafficStateId",
            None,
        )

    if rawId is not None:

        try:

            return int(
                rawId
            )

        except (
            TypeError,
            ValueError,
        ):

            pass

    return None


# ============================================================
# GET RECOMMENDATION ID
# ============================================================

def getRecommendationId(
    recommendation: Any,
) -> int | None:
    """
    Mengambil recommendation.id jika decision engine
    menghasilkan object recommendation yang memiliki ID.

    Kalau decision engine hanya menghasilkan recommendation
    tanpa ID database, maka None.

    Ini aman karena recommendationId memang nullable.
    """

    if recommendation is None:
        return None

    # --------------------------------------------------------
    # DICT
    # --------------------------------------------------------

    if isinstance(
        recommendation,
        dict,
    ):

        rawId = (
            recommendation.get(
                "id"
            )
        )

        if rawId is None:

            rawId = (
                recommendation.get(
                    "recommendationId"
                )
            )

        if rawId is not None:

            try:

                return int(
                    rawId
                )

            except (
                TypeError,
                ValueError,
            ):

                return None

    # --------------------------------------------------------
    # OBJECT
    # --------------------------------------------------------

    rawId = getattr(
        recommendation,
        "id",
        None,
    )

    if rawId is None:

        rawId = getattr(
            recommendation,
            "recommendationId",
            None,
        )

    if rawId is not None:

        try:

            return int(
                rawId
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

    return None


# ============================================================
# DECISION ENGINE
# ============================================================

def createDecision(
    trafficState,
    forecast=None,
    forecastWeight: float = 0.3,
):

    printHeader(
        "RUNNING DECISION ENGINE"
    )

    engine = (
        ScenarioEngine(
            sumo_binary=sumoBinary,
            sumo_config=sumoConfig,
            tls_id=tlsId,
            approach_to_phase=approachToPhase,
            run_simulation_fn=runSimulation,
        )
    )

    recommendation = (
        engine.recommend(
            state=trafficState,
            currentGreenSeconds=15,
            currentPhase="south",
            forecast=forecast,
            forecastWeight=forecastWeight,
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

    sumoPhase = (
        approachToPhase.get(
            recommendedApproach
        )
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
        f"Forecast weight       : "
        f"{forecastWeight if forecast is not None else 0.0}"
    )

    print(
        f"Reason                : "
        f"{recommendation.reason}"
    )

    # ========================================================
    # RECOMMENDATION ID
    # ========================================================

    recommendationId = (
        getRecommendationId(
            recommendation
        )
    )

    print()

    print(
        f"Recommendation ID     : "
        f"{recommendationId}"
    )

    if recommendationId is None:

        print(
            "Recommendation belum memiliki "
            "ID database. simulations."
            "recommendationId akan NULL."
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
            recommendation
            .recommendedGreenSeconds,

        "reason":
            recommendation.reason,

        "confidence":
            recommendation.confidence,

        "source":
            recommendation.source,

        "recommendationId":
            recommendationId,

        "forecastApplied":
            forecast is not None,

        "forecastWeight":
            forecastWeight if forecast is not None else 0.0,

        "forecastFallbackUsed": (
            bool(forecast.get("fallbackUsed", False))
            if forecast is not None
            else False
        ),

        "forecastSource": (
            forecast.get("forecastSource", "none")
            if forecast is not None
            else "none"
        ),
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
# TRAFFIC FORECAST
# ============================================================

def loadForecast():
    """Ambil forecast dari histori TrafficState dengan fallback aman."""

    printHeader(
        "LOADING TRAFFIC FORECAST"
    )

    enabled = os.getenv(
        "FORECAST_ENABLED",
        "true",
    ).strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }

    try:
        forecastWeight = float(
            os.getenv(
                "FORECAST_WEIGHT",
                "0.3",
            )
        )
    except ValueError:
        print(
            "FORECAST_WEIGHT tidak valid; "
            "pakai nilai konservatif 0.3."
        )
        forecastWeight = 0.3

    forecastWeight = max(
        0.0,
        min(1.0, forecastWeight),
    )

    if not enabled or forecastWeight == 0.0:
        print(
            "Forecast dinonaktifkan. ScenarioEngine akan memakai "
            "TrafficState aktual saja."
        )
        return None, 0.0

    client = ForecastClient()
    forecast = client.get_live_forecast()

    if forecast is None:
        print(
            "Forecast tidak tersedia; fallback ke TrafficState aktual."
        )
        print(
            f"Alasan                 : {client.last_error}"
        )
        return None, forecastWeight

    print(
        "Forecast berhasil dimuat."
    )
    print(
        f"Source                 : "
        f"{forecast.get('forecastSource', 'unknown')}"
    )
    print(
        f"Fallback model         : "
        f"{forecast.get('fallbackUsed', False)}"
    )
    print(
        f"Horizon                : "
        f"{len(forecast.get('approachForecasts', []))} timestep / 60 detik"
    )
    print(
        f"Decision weight        : {forecastWeight}"
    )

    return forecast, forecastWeight


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
        traci
        .trafficlight
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

    traci.trafficlight.setProgram(
        tlsId,
        "safe-yellow",
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
        f"TLS       : "
        f"{tlsId}"
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

def runSimulation(
    step_limit: int = simulationStepLimit,
):

    printHeader(
        "SIMULATION RUNNING"
    )

    steps = 0

    arrivedVehicles = 0

    departedVehicles = 0

    # Puncak jumlah kendaraan berhenti (speed < 0.1 m/s, definisi
    # "halting" bawaan SUMO) yang teramati sepanjang simulasi --
    # dipakai sebagai queueLengthVeh, konsisten dengan nama field
    # queueLengthVeh di data-contract.md.
    peakQueueLength = 0

    # Sampel accumulated-waiting-time tiap kendaraan aktif, diambil
    # tiap step -- pola sama dengan run_simulation.py, supaya
    # averageWaitingTimeSeconds di sini sepadan artinya.
    waitingTimeSamples: list[float] = []

    while (
        steps
        < step_limit
    ):

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

            # getArrivedNumber()/getDepartedNumber() itu hitungan
            # PER STEP INI SAJA (bukan kumulatif) -- sebelumnya
            # ditimpa (=) tiap step, bukan ditambah (+=), jadi nilai
            # akhirnya cuma dari step TERAKHIR, bukan total sepanjang
            # simulasi. Ditemukan 25 Agustus 2026 pas menyambungkan
            # throughputVeh -- kalau tidak diperbaiki, throughput
            # yang disimpan ke simulationMetrics nanti hampir selalu
            # 0 (step terakhir jarang ada yang datang/pergi persis).
            arrivedVehicles += (
                traci
                .simulation
                .getArrivedNumber()
            )

            departedVehicles += (
                traci
                .simulation
                .getDepartedNumber()
            )

            vehicleIds = (
                traci
                .vehicle
                .getIDList()
            )

            activeVehicles = len(
                vehicleIds
            )

            expectedVehicles = (
                traci
                .simulation
                .getMinExpectedNumber()
            )

            # Antrean & waktu tunggu dalam SATU pass yang sama atas
            # vehicleIds -- bukan loop terpisah, supaya tidak dobel
            # menelusuri seluruh kendaraan aktif tiap step.
            haltingCount = 0

            for vehicleId in vehicleIds:

                waitingTimeSamples.append(
                    traci.vehicle
                    .getAccumulatedWaitingTime(
                        vehicleId
                    )
                )

                if (
                    traci.vehicle
                    .getSpeed(vehicleId)
                    < 0.1
                ):

                    haltingCount += 1

            peakQueueLength = max(
                peakQueueLength,
                haltingCount,
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
    # FINAL ACTIVE VEHICLES
    # ========================================================

    try:

        activeVehicles = (
            traci
            .vehicle
            .getIDCount()
        )

    except Exception:

        activeVehicles = 0

    averageWaitingTimeSeconds = (
        sum(waitingTimeSamples)
        / len(waitingTimeSamples)
        if waitingTimeSamples
        else 0.0
    )

    return {

        "steps":
            steps,

        "activeVehicles":
            activeVehicles,

        "arrivedVehicles":
            arrivedVehicles,

        "departedVehicles":
            departedVehicles,

        # throughputVeh = total kendaraan yang selesai perjalanan
        # (arrived) sepanjang simulasi -- baru bermakna setelah
        # arrivedVehicles diperbaiki jadi akumulasi, bukan step
        # terakhir saja (lihat catatan di loop di atas).
        "throughputVeh":
            arrivedVehicles,

        "queueLengthVeh":
            peakQueueLength,

        "averageWaitingTimeSeconds":
            round(
                averageWaitingTimeSeconds,
                2,
            ),
    }


# ============================================================
# TLS RESULT
# ============================================================

def getTlsResult(
    phasePlan: dict[str, Any],
):

    finalPhase = (
        traci
        .trafficlight
        .getPhase(
            tlsId
        )
    )

    tlsState = (
        traci
        .trafficlight
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
# BUILD METRICS
# ============================================================

def buildSimulationMetrics(
    simulationMetrics: dict[str, Any],
    tlsResult: dict[str, Any],
):

    return {

        "steps":
            simulationMetrics[
                "steps"
            ],

        "activeVehicles":
            simulationMetrics[
                "activeVehicles"
            ],

        "arrivedVehicles":
            simulationMetrics[
                "arrivedVehicles"
            ],

        "departedVehicles":
            simulationMetrics[
                "departedVehicles"
            ],

        "throughputVeh":
            simulationMetrics[
                "throughputVeh"
            ],

        "queueLengthVeh":
            simulationMetrics[
                "queueLengthVeh"
            ],

        "averageWaitingTimeSeconds":
            simulationMetrics[
                "averageWaitingTimeSeconds"
            ],

        "finalPhase":
            tlsResult[
                "finalPhase"
            ],

        "tlsState":
            tlsResult[
                "tlsState"
            ],
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
        f"Throughput       : "
        f"{simulationMetrics['throughputVeh']} veh"
    )

    print(
        f"Queue (peak)     : "
        f"{simulationMetrics['queueLengthVeh']} veh"
    )

    print(
        f"Avg waiting time : "
        f"{simulationMetrics['averageWaitingTimeSeconds']}s"
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
# SAVE SIMULATION RESULT
# ============================================================

def saveSimulationResult(
    trafficState,
    phasePlan,
    simulationMetrics,
    tlsResult,
    startedAt: datetime,
    completedAt: datetime,
):

    printHeader(
        "SAVING SIMULATION RESULT"
    )

    if supabaseClient is None:

        raise RuntimeError(
            "Supabase client belum terhubung."
        )

    # ========================================================
    # TRAFFIC STATE ID
    # ========================================================

    trafficStateId = (
        getTrafficStateId(
            trafficState
        )
    )

    # ========================================================
    # RECOMMENDATION ID
    # ========================================================

    recommendationId = (
        phasePlan.get(
            "recommendationId"
        )
    )

    # ========================================================
    # BUILD PAYLOAD
    #
    # PERHATIKAN:
    #
    # HANYA FIELD YANG ADA DI TABLE simulations.
    #
    # ========================================================

    simulationPayload = {

        "intersectionId":
            intersectionId,

        "trafficStateId":
            trafficStateId,

        "recommendationId":
            recommendationId,

        "simulationName":
            "SmartTwin Adaptive TLS",

        "simulationType":
            "traffic_signal",

        "engine":
            "SUMO",

        "status":
            "completed",

        "startedAt":
            startedAt,

        "completedAt":
            completedAt,
    }

    # ========================================================
    # PRINT WHAT WILL BE SAVED
    # ========================================================

    print()

    print(
        "Simulation payload:"
    )

    print(
        simulationPayload
    )

    # ========================================================
    # WRITER
    # ========================================================

    resultWriter = (
        SimulationResultWriter(
            supabase=supabaseClient
        )
    )

    # ========================================================
    # SAVE
    # ========================================================

    try:

        simulation = (
            resultWriter.saveResult(
                simulationPayload
            )
        )

    except Exception as exc:

        print()

        print(
            "Gagal menyimpan hasil simulasi."
        )

        print(
            f"Error: {exc}"
        )

        raise

    # ========================================================
    # SUCCESS
    # ========================================================

    simulationId = (
        simulation.get(
            "id"
        )
    )

    print()

    print(
        "Hasil simulasi berhasil disimpan."
    )

    print(
        f"Simulation DB ID : "
        f"{simulationId}"
    )

    # ========================================================
    # SAVE METRICS (delay/queue/throughput) -- item 1.3
    #
    # TERPISAH dari insert simulations di atas, dan sengaja
    # TIDAK FATAL kalau gagal: baris `simulations` sudah tersimpan
    # duluan, jadi kegagalan simpan metrik tidak boleh membuat
    # seolah simulasinya sendiri gagal (exception di sini di-catch,
    # bukan di-raise ulang).
    # ========================================================

    try:

        resultWriter.saveMetrics(
            simulationId,
            {
                "averageWaitingTimeSeconds": (
                    simulationMetrics[
                        "averageWaitingTimeSeconds"
                    ],
                    "seconds",
                ),
                "queueLengthVeh": (
                    simulationMetrics[
                        "queueLengthVeh"
                    ],
                    "vehicles",
                ),
                "throughputVeh": (
                    simulationMetrics[
                        "throughputVeh"
                    ],
                    "vehicles",
                ),
                "forecastApplied": (
                    1.0 if phasePlan.get("forecastApplied") else 0.0,
                    "boolean",
                ),
                "forecastWeight": (
                    float(phasePlan.get("forecastWeight", 0.0)),
                    "ratio",
                ),
                "forecastFallbackUsed": (
                    1.0 if phasePlan.get("forecastFallbackUsed") else 0.0,
                    "boolean",
                ),
                "recommendedGreenSeconds": (
                    float(phasePlan.get("duration", 0.0)),
                    "seconds",
                ),
            },
        )

        print(
            "Metrics (delay/queue/throughput) berhasil disimpan."
        )

    except Exception as exc:

        print(
            "Gagal menyimpan simulationMetrics "
            f"(non-fatal, simulasi tetap tersimpan): {exc}"
        )

    return simulation


# ============================================================
# MAIN
# ============================================================

def main():

    print()

    print(
        "=" * 70
    )

    print(
        "SMARTTWIN ADAPTIVE TLS SIMULATION"
    )

    print(
        "=" * 70
    )

    # ========================================================
    # START TIME
    # ========================================================

    startedAt = (
        datetime.now(
            timezone.utc
        )
    )

    # ========================================================
    # ENVIRONMENT
    # ========================================================

    printEnvironment()

    # ========================================================
    # SUPABASE
    # ========================================================

    connectSupabase()

    # ========================================================
    # TRAFFIC STATE
    # ========================================================

    trafficState = (
        loadTrafficState()
    )

    # ========================================================
    # FORECAST DARI HISTORI TRAFFIC STATE BUILDER
    # ========================================================

    (
        forecast,
        forecastWeight,
    ) = loadForecast()

    # ========================================================
    # DECISION ENGINE
    # ========================================================

    (
        recommendation,
        phasePlan,
    ) = createDecision(
        trafficState,
        forecast=forecast,
        forecastWeight=forecastWeight,
    )

    # ========================================================
    # START SUMO
    # ========================================================

    startSumo()

    simulationResult = None

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
        # COMPLETED TIME
        # ----------------------------------------------------

        completedAt = (
            datetime.now(
                timezone.utc
            )
        )

        # ----------------------------------------------------
        # BUILD FINAL METRICS
        #
        # Sampai 25 Agustus 2026 metrics di sini CUMA buat output
        # terminal, tidak pernah disimpan -- saveSimulationResult()
        # di bawah cuma mengirim field administratif (intersectionId
        # dkk) ke tabel `simulations`. Sekarang throughputVeh/
        # queueLengthVeh/averageWaitingTimeSeconds ikut disimpan ke
        # tabel terpisah `simulationMetrics` lewat
        # SimulationResultWriter.saveMetrics() -- lihat pemanggilannya
        # di akhir saveSimulationResult().
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

        simulationResult = (
            saveSimulationResult(
                trafficState=trafficState,

                phasePlan=phasePlan,

                simulationMetrics=finalMetrics,

                tlsResult=tlsResult,

                startedAt=startedAt,

                completedAt=completedAt,
            )
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

    # ========================================================
    # FINAL
    # ========================================================

    printHeader(
        "SMARTTWIN TLS SIMULATION SELESAI"
    )

    print(
        "TrafficState"
    )

    print(
        "     |"
    )

    print(
        "LSTM Forecast (optional, fallback TrafficState)"
    )

    print(
        "     |"
    )

    print(
        "Scenario Generator + Rule-Based Decision Engine"
    )

    print(
        "     |"
    )

    print(
        "Phase Mapping"
    )

    print(
        "     |"
    )

    print(
        "TLS Controller"
    )

    print(
        "     |"
    )

    print(
        "SUMO"
    )

    print(
        "     |"
    )

    print(
        "Simulation Metrics"
    )

    print(
        "     |"
    )

    print(
        "Supabase"
    )

    print()

    print(
        "STATUS: SUCCESS"
    )

    if simulationResult:

        print()

        print(
            f"Simulation ID : "
            f"{simulationResult.get('id')}"
        )

        print(
            f"Intersection ID: "
            f"{simulationResult.get('intersectionId')}"
        )

        print(
            f"TrafficState ID: "
            f"{simulationResult.get('trafficStateId')}"
        )

        print(
            f"Recommendation : "
            f"{simulationResult.get('recommendationId')}"
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
