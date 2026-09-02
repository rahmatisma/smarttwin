import base64
import json
from datetime import datetime

import pytest

from app.repositories.traffic_state_repository import TrafficStateRepository
from app.core.config import settings
from app.services.supabase_client import get_supabase
from app.schemas.traffic import (
    ApproachState,
    TrafficState,
)


pytestmark = pytest.mark.integration


def test_save_traffic_state():
    try:
        payload = settings.supabase_service_role_key.split(".")[1]
        payload_data = json.loads(
            base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        )
    except (IndexError, ValueError, json.JSONDecodeError):
        pytest.skip("SUPABASE_SERVICE_ROLE_KEY bukan JWT yang valid")

    if payload_data.get("role") != "service_role":
        pytest.skip(
            "Test write membutuhkan SUPABASE_SERVICE_ROLE_KEY dengan role service_role"
        )

    state = TrafficState(
            intersectionId="simpang4-pingit",
            windowStart=datetime(
                2026,
                8,
                15,
                16,
                30,
                10,
            ),
            windowEnd=datetime(
                2026,
                8,
                15,
                16,
                30,
                15,
            ),
            approaches=[
                ApproachState(
                    approach="north",
                    volume=10,
                    carCount=5,
                    motorcycleCount=3,
                    busCount=1,
                    truckCount=1,
                    queueLengthVeh=5,
                    queueLengthMEst=12.5,
                    densityIndex=25.0,
                    avgSpeedKmh=None,
                ),
                ApproachState(
                    approach="south",
                    volume=0,
                    carCount=0,
                    motorcycleCount=0,
                    busCount=0,
                    truckCount=0,
                    queueLengthVeh=0,
                    queueLengthMEst=0,
                    densityIndex=0,
                    avgSpeedKmh=None,
                ),
                ApproachState(
                    approach="east",
                    volume=0,
                    carCount=0,
                    motorcycleCount=0,
                    busCount=0,
                    truckCount=0,
                    queueLengthVeh=0,
                    queueLengthMEst=0,
                    densityIndex=0,
                    avgSpeedKmh=None,
                ),
                ApproachState(
                    approach="west",
                    volume=0,
                    carCount=0,
                    motorcycleCount=0,
                    busCount=0,
                    truckCount=0,
                    queueLengthVeh=0,
                    queueLengthMEst=0,
                    densityIndex=0,
                    avgSpeedKmh=None,
                ),
            ],
        )

    saved = TrafficStateRepository().save_state(state)
    assert saved["id"] is not None

    children = get_supabase().table("trafficApproachStates").select("id").eq(
        "trafficStateId", saved["id"]
    ).execute()
    assert len(children.data or []) == 4
