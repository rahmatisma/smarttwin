from pydantic import BaseModel
from typing import Literal
from datetime import datetime

Approach = Literal["north", "south", "east", "west"]
VehicleClass = Literal["motorcycle", "car", "bus", "truck"]

# 1) Output CV (Melpi) — per kendaraan per frame
class VehicleDetection(BaseModel):
    track_id: int
    vehicle_class: VehicleClass
    bbox: tuple[float, float, float, float]   # x1, y1, x2, y2 (pixel)
    approach: Approach
    frame_timestamp: datetime

# 2) Output Traffic State Builder (Rahmat, agregasi dari VehicleDetection)
class ApproachState(BaseModel):
    approach: Approach
    volume: int
    queue_length_m: float
    density_veh_per_km: float
    avg_speed_kmh: float

class TrafficState(BaseModel):
    intersection_id: str
    window_start: datetime
    window_end: datetime
    approaches: list[ApproachState]

# 3) Output Traffic Forecast (Yuli, LSTM — aktif kalau lolos checkpoint Minggu 3)
class ForecastPoint(BaseModel):
    approach: Approach
    horizon_minutes: int
    predicted_volume: int

# 4) Output Scenario Generator + Performance Analysis (Rahmat, dari SUMO)
class SignalPhase(BaseModel):
    phase_name: str
    green_duration_s: int

class ScenarioResult(BaseModel):
    scenario_id: str
    phases: list[SignalPhase]
    cycle_length_s: int
    avg_delay_s: float
    avg_queue_length_m: float
    throughput_veh: int

# 5) Output Decision Engine (rule-based dulu, PPO nanti)
class SignalRecommendation(BaseModel):
    intersection_id: str
    generated_at: datetime
    engine: Literal["rule-based", "ppo"]
    chosen_scenario: ScenarioResult
    expected_improvement_pct: float