// Data dummy untuk frontend SmartTwin.
//
// Semua data traffic yang berasal dari backend harus mengikuti
// docs/data-contract.md.
//
// Jika backend sudah tersedia, data mock traffic ini nantinya
// diganti dengan hasil fetch dari FastAPI.

/* =========================================================
 * TYPES
 * ========================================================= */

import type {
  ApproachState,
  TrafficState,
} from "@/types/traffic";

/* =========================================================
 * TRAFFIC STATE
 * ========================================================= */

export const mockApproachStates: ApproachState[] = [
  {
    approach: "north",
    volume: 65,

    carCount: 18,
    motorcycleCount: 43,
    busCount: 1,
    truckCount: 3,

    queueLengthVeh: 8,
    queueLengthMEst: 32,
    densityIndex: 86,
    avgSpeedKmh: 41,
  },

  {
    approach: "south",
    volume: 60,

    carCount: 20,
    motorcycleCount: 36,
    busCount: 1,
    truckCount: 3,

    queueLengthVeh: 7,
    queueLengthMEst: 28,
    densityIndex: 82,
    avgSpeedKmh: 43,
  },

  {
    approach: "east",
    volume: 82,

    carCount: 24,
    motorcycleCount: 51,
    busCount: 2,
    truckCount: 5,

    queueLengthVeh: 12,
    queueLengthMEst: 46,
    densityIndex: 132,
    avgSpeedKmh: 18,
  },

  {
    approach: "west",
    volume: 73,

    carCount: 16,
    motorcycleCount: 54,
    busCount: 2,
    truckCount: 1,

    queueLengthVeh: 10,
    queueLengthMEst: 39,
    densityIndex: 118,
    avgSpeedKmh: 21,
  },
];

/*
 * Total volume:
 *
 * North = 65
 * South = 60
 * East  = 82
 * West  = 73
 *
 * Total = 280 kendaraan
 */

export const mockTrafficState: TrafficState = {
  intersectionId: "simpang4-pingit",
  windowStart: "2026-08-15T16:30:12",
  windowEnd: "2026-08-15T16:30:17",
  approaches: mockApproachStates,
};


/* =========================================================
 * CURRENT SIGNAL STATUS
 * ========================================================= */

export const mockSignalStatus = {
  intersectionId: "simpang4-pingit",

  timestamp: "2026-08-15T16:30:17",

  currentPhase: "phase-2",

  phaseName: "Fase 2 — Timur-Barat",

  remainingSeconds: 18,

  cycleTimeSeconds: 63,

  source: "mock",
};


/* =========================================================
 * SIGNAL RECOMMENDATION
 * ========================================================= */

export const mockRecommendation = {
  intersectionId: "simpang4-pingit",

  timestamp: "2026-08-15T16:30:17",

  recommendedPhase: "phase-2",

  recommendedGreenSeconds: 45,

  currentGreenSeconds: 35,

  expectedDelayReductionPercent: 18,

  confidence: 0.85,

  reason:
    "Approach east dan west memiliki kepadatan traffic paling tinggi.",

  source: "mock",
};


/* =========================================================
 * TRAFFIC FORECAST
 * ========================================================= */

/*
 * Forecast:
 *
 * horizon 0  = kondisi saat ini
 * horizon 3  = 3 menit ke depan
 * horizon 6  = 6 menit ke depan
 * horizon 9  = 9 menit ke depan
 * horizon 12 = 12 menit ke depan
 * horizon 15 = 15 menit ke depan
 *
 * Struktur mengikuti Forecast pada data contract.
 */

export const mockForecast = {
  intersectionId: "simpang4-pingit",

  horizonMinutes: 15,

  model: "mock",

  predictions: [
    {
      timestamp: "2026-08-15T16:30:17",

      predictedVehicleCount: 280,

      predictedQueueLengthVeh: 37,

      predictedQueueLengthMEst: 145,

      predictedDensityIndex: 104.5,

      predictedSpeedKmh: null,
    },

    {
      timestamp: "2026-08-15T16:33:17",

      predictedVehicleCount: 290,

      predictedQueueLengthVeh: 39,

      predictedQueueLengthMEst: 151,

      predictedDensityIndex: 108.2,

      predictedSpeedKmh: null,
    },

    {
      timestamp: "2026-08-15T16:36:17",

      predictedVehicleCount: 313,

      predictedQueueLengthVeh: 43,

      predictedQueueLengthMEst: 162,

      predictedDensityIndex: 114.6,

      predictedSpeedKmh: null,
    },

    {
      timestamp: "2026-08-15T16:39:17",

      predictedVehicleCount: 305,

      predictedQueueLengthVeh: 41,

      predictedQueueLengthMEst: 158,

      predictedDensityIndex: 112.1,

      predictedSpeedKmh: null,
    },

    {
      timestamp: "2026-08-15T16:42:17",

      predictedVehicleCount: 323,

      predictedQueueLengthVeh: 45,

      predictedQueueLengthMEst: 169,

      predictedDensityIndex: 118.4,

      predictedSpeedKmh: null,
    },

    {
      timestamp: "2026-08-15T16:45:17",

      predictedVehicleCount: 311,

      predictedQueueLengthVeh: 42,

      predictedQueueLengthMEst: 161,

      predictedDensityIndex: 115.3,

      predictedSpeedKmh: null,
    },
  ],
};


/* =========================================================
 * INTERSECTION
 * ========================================================= */

export const mockIntersection = {
  name: "Simpang Pingit, Yogyakarta",

  // Koordinat masih mock.
  // Ganti setelah koordinat intersection final
  // dari SUMO/OSM sudah ditentukan oleh tim.
  coords: "-7.782800, 110.360830",
};


/* =========================================================
 * DASHBOARD DISPLAY DATA
 * ========================================================= */

/*
 * Occupancy masih merupakan data mock untuk tampilan.
 *
 * Nanti dapat diganti dengan hasil perhitungan traffic
 * state dari backend.
 */
export const mockOccupancyPct = 68;


/* =========================================================
 * WEATHER
 * ========================================================= */

export const mockWeather = {
  dateLabel: "10 Juli 2026",
  condition: "Berawan",
  tempC: 25,
};


/* =========================================================
 * CAMERA STATUS
 * ========================================================= */

export const mockCameraStatus = [
  {
    label: "CAM 01 — Utara",
    online: true,
  },
  {
    label: "CAM 02 — Selatan",
    online: true,
  },
  {
    label: "CAM 03 — Timur",
    online: true,
  },
  {
    label: "CAM 04 — Barat",
    online: false,
  },
];