// Tipe-tipe ini mirror docs/data-contract.md (schema Pydantic yang sudah
// disepakati tim). Field ditulis camelCase mengikuti konvensi TS/JS —
// begitu wiring ke API asli (Minggu 4), tinggal sesuaikan penamaan di titik
// fetch-nya saja, bukan di seluruh komponen.

export type Approach = "north" | "south" | "east" | "west";
export type VehicleClass = "motorcycle" | "car" | "bus" | "truck";

export interface ApproachState {
  approach: Approach;
  volume: number;
  queueLengthM: number;
  densityVehPerKm: number;
  avgSpeedKmh: number;
}

export interface TrafficState {
  intersectionId: string;
  windowStart: string;
  windowEnd: string;
  approaches: ApproachState[];
}

export interface VehicleClassCount {
  vehicleClass: VehicleClass;
  count: number;
}

export interface SignalPhase {
  phaseName: string;
  greenDurationS: number;
}

export interface ScenarioResult {
  scenarioId: string;
  phases: SignalPhase[];
  cycleLengthS: number;
  avgDelayS: number;
  avgQueueLengthM: number;
  throughputVeh: number;
}

export interface SignalRecommendation {
  intersectionId: string;
  generatedAt: string;
  engine: "rule-based" | "ppo";
  chosenScenario: ScenarioResult;
  expectedImprovementPct: number;
}

export interface ForecastPoint {
  minute: number; // menit ke depan, mis. 0, 3, 6, 9...
  predictedVolume: number;
}

export interface SignalStatus {
  activePhase: Approach[]; // arah mana yang lagi hijau, mis. ["north","south"]
  phaseName: string;
  color: "red" | "amber" | "green";
  secondsRemaining: number;
  cycleBreakdown: { greenS: number; yellowS: number; redS: number };
}
