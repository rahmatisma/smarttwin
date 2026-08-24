from datetime import datetime, timezone

from app.schemas.traffic import (
    ApproachState,
    TrafficState,
)
import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from decision_engine.rule_based_engine import (
    RuleBasedEngine,
)


def test_rule_based_engine():

    state = TrafficState(
        intersectionId="intersection_01",
        windowStart=datetime.now(
            timezone.utc
        ),
        windowEnd=datetime.now(
            timezone.utc
        ),
        approaches=[
            ApproachState(
                approach="north",
                volume=25,
                carCount=12,
                motorcycleCount=10,
                busCount=1,
                truckCount=2,
                queueLengthVeh=15,
                queueLengthMEst=75.0,
                densityIndex=0.80,
                avgSpeedKmh=None,
            ),
            ApproachState(
                approach="south",
                volume=8,
                carCount=4,
                motorcycleCount=3,
                busCount=0,
                truckCount=1,
                queueLengthVeh=2,
                queueLengthMEst=11.0,
                densityIndex=0.25,
                avgSpeedKmh=None,
            ),
            ApproachState(
                approach="east",
                volume=5,
                carCount=2,
                motorcycleCount=2,
                busCount=0,
                truckCount=1,
                queueLengthVeh=1,
                queueLengthMEst=4.5,
                densityIndex=0.15,
                avgSpeedKmh=None,
            ),
            ApproachState(
                approach="west",
                volume=6,
                carCount=3,
                motorcycleCount=2,
                busCount=0,
                truckCount=1,
                queueLengthVeh=2,
                queueLengthMEst=11.0,
                densityIndex=0.20,
                avgSpeedKmh=None,
            ),
        ],
    )

    engine = RuleBasedEngine()

    recommendation = engine.recommend(
        state=state,
        currentGreenSeconds=30,
        currentPhase="northSouth",
    )

    # Recommendation dari RuleBasedEngine sengaja tidak membawa
    # intersectionId -- itu ditempel oleh caller (lihat
    # recommendation_service.py) dari TrafficState yang dikirim.

    assert (
        recommendation.recommendedPhase
        == "north"
    )

    assert (
        recommendation.recommendedGreenSeconds
        >= 15
    )

    assert (
        recommendation.recommendedGreenSeconds
        <= 60
    )

    assert (
        recommendation.confidence
        >= 0
    )

    assert (
        recommendation.confidence
        <= 1
    )

    assert (
        recommendation.source
        == "rule-based"
    )

    print(
        "\nRecommendation:"
    )

    print(
        recommendation
    )