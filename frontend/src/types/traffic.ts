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
}


/* =========================================================
 * SIGNAL STATUS
 * ========================================================= */

export interface SignalStatus {
  intersectionId: string;

  timestamp: string;

  currentPhase: string;

  phaseName: string;

  remainingSeconds: number;

  cycleTimeSeconds: number;

  source: string;
}


/* =========================================================
 * RECOMMENDATION
 * ========================================================= */

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
}