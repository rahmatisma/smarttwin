// src/types/traffic.ts
//
// SmartTwin frontend types.
// Source of truth:
// docs/data-contract.md
//
// Semua nama field menggunakan camelCase.

export type Approach =
  | "north"
  | "south"
  | "east"
  | "west";

export type VehicleClass =
  | "motorcycle"
  | "car"
  | "bus"
  | "truck";


/* =========================================================
 * TRAFFIC STATE
 * ========================================================= */

export interface ApproachState {
  approach: Approach;

  // Total kendaraan yang melewati counting line
  // selama window observasi.
  volume: number;

  // Jumlah kendaraan berdasarkan kelas.
  carCount: number;
  motorcycleCount: number;
  busCount: number;
  truckCount: number;

  // Antrean.
  queueLengthVeh: number;
  queueLengthMEst: number;

  // Proxy lane occupancy / kepadatan.
  // BUKAN vehicles/km.
  densityIndex: number;

  // null berarti data speed belum tersedia.
  avgSpeedKmh: number | null;
}


export interface TrafficState {
  intersectionId: string;

  windowStart: string;
  windowEnd: string;

  matchedCvTime?: number;

  approaches: ApproachState[];
}


/* =========================================================
 * VEHICLE CLASSIFICATION
 * ========================================================= */

export interface VehicleClassCount {
  vehicleClass: VehicleClass;
  count: number;
}


/* =========================================================
 * FORECAST
 * ========================================================= */

export interface ForecastPrediction {
  timestamp: string;

  predictedVehicleCount: number;

  predictedQueueLengthVeh: number;

  predictedQueueLengthMEst: number;

  predictedDensityIndex: number;

  predictedSpeedKmh: number | null;
}


export interface ForecastResponse {
  intersectionId: string;

  horizonMinutes: number;

  model: string;

  predictions: ForecastPrediction[];

  // Diisi oleh endpoint forecast per-approach. `predictions` tetap
  // tersedia sebagai agregat supaya komponen lama tetap kompatibel.
  predictionsByApproach?: Partial<Record<Approach, ForecastPrediction[]>>;

  forecastSource?: string;

  fallbackUsed?: boolean;
}


/* =========================================================
 * SIGNAL STATUS
 * ========================================================= */

export interface SignalPhaseStatus {
  phaseId: string;

  state: string;

  durationSeconds: number;

  remainingSeconds: number;
}

export interface SignalStatus {
  intersectionId: string;

  timestamp: string;

  currentPhase: string;

  // Diisi oleh live SUMO agar UI tidak menebak kuning dari countdown.
  state?: "GREEN" | "YELLOW";

  phaseName: string;

  remainingSeconds: number;

  cycleTimeSeconds: number;

  phases?: Record<string, SignalPhaseStatus>;

  nextPhase?: string;

  nextPhaseName?: string;

  source: string;
}


/* =========================================================
 * RECOMMENDATION
 * ========================================================= */

// Rekomendasi durasi hijau utk SATU lengan (rotasi tetap
// utara-timur-selatan-barat). Lihat RuleBasedEngine.recommend_cycle()
// di decision_engine/rule_based_engine.py.
export interface ApproachPhase {
  approach: string;

  greenSeconds: number;

  yellowSeconds?: number;

  redSeconds?: number;

  demandScore: number;
}

export interface CyclePlan {
  phases: ApproachPhase[];

  cycleLengthSeconds: number;

  currentPhase: string;

  source: string;

  totalCycleSeconds?: number;
}

export interface Recommendation {
  intersectionId: string;

  timestamp: string;

  recommendedPhase: string;

  recommendedGreenSeconds: number;

  currentGreenSeconds: number;

  expectedDelayReductionPercent: number;

  confidence: number;

  reason: string;

  source: string;

  // null kalau belum ada TrafficState (fallback) -- lihat
  // recommendation_service.py.
  cyclePlan?: CyclePlan | null;

  candidateId?: string | null;

  avgDelaySeconds?: number | null;

  avgQueueLengthM?: number | null;

  los?: string | null;
}
