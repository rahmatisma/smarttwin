// Data dummy untuk frontend SmartTwin.
// Nanti sumber data ini diganti dengan hasil fetch dari FastAPI.
// Struktur object sengaja mengikuti types/traffic.ts agar component
// tidak perlu diubah ketika backend sudah tersedia.

import type {
  ApproachState,
  VehicleClassCount,
  SignalRecommendation,
  ForecastPoint,
  SignalStatus,
} from "@/types/traffic";

/* =========================================================
 * TRAFFIC STATE
 * ========================================================= */

export const mockApproachStates: ApproachState[] = [
  {
    approach: "north",
    volume: 65,
    queueLengthM: 32,
    densityVehPerKm: 86,
    avgSpeedKmh: 41,
  },
  {
    approach: "south",
    volume: 60,
    queueLengthM: 28,
    densityVehPerKm: 82,
    avgSpeedKmh: 43,
  },
  {
    approach: "east",
    volume: 82,
    queueLengthM: 46,
    densityVehPerKm: 132,
    avgSpeedKmh: 18,
  },
  {
    approach: "west",
    volume: 73,
    queueLengthM: 39,
    densityVehPerKm: 118,
    avgSpeedKmh: 21,
  },
];

/*
 * Total volume:
 * North = 65
 * South = 60
 * East  = 82
 * West  = 73
 *
 * Total = 280 kendaraan
 *
 * Kondisi:
 * - Utara   : relatif lancar
 * - Selatan : relatif lancar
 * - Timur   : padat
 * - Barat   : sedang-padat
 */


/* =========================================================
 * VEHICLE CLASSIFICATION
 * ========================================================= */

/*
 * Total kendaraan disamakan dengan total volume pada
 * mockApproachStates:
 *
 * 280 kendaraan
 */

export const mockVehicleClassCounts: VehicleClassCount[] = [
  {
    vehicleClass: "motorcycle",
    count: 184,
  },
  {
    vehicleClass: "car",
    count: 78,
  },
  {
    vehicleClass: "bus",
    count: 6,
  },
  {
    vehicleClass: "truck",
    count: 12,
  },
];

// Total = 280 kendaraan


/* =========================================================
 * CURRENT SIGNAL STATUS
 * ========================================================= */

export const mockSignalStatus: SignalStatus = {
  // Timur-Barat sedang mendapatkan lampu hijau karena
  // kedua approach tersebut memiliki kondisi traffic
  // paling padat.
  activePhase: ["east", "west"],

  phaseName: "Fase 2 — Timur-Barat",

  color: "green",

  secondsRemaining: 18,

  cycleBreakdown: {
    greenS: 35,
    yellowS: 3,
    redS: 25,
  },
};


/* =========================================================
 * SIGNAL RECOMMENDATION
 * ========================================================= */

export const mockRecommendation: SignalRecommendation = {
  intersectionId: "simpang4-pingit",

  generatedAt: new Date().toISOString(),

  // Untuk sementara recommendation engine masih rule-based.
  // Nanti dapat diganti menjadi "ppo" ketika model RL sudah siap.
  engine: "rule-based",

  chosenScenario: {
    scenarioId: "scn-04",

    phases: [
      {
        phaseName: "Fase 1 (Utara-Selatan)",
        greenDurationS: 30,
      },
      {
        phaseName: "Fase 2 (Timur-Barat)",
        greenDurationS: 45,
      },
      {
        phaseName: "Fase 3 (Belok Kanan)",
        greenDurationS: 20,
      },
      {
        phaseName: "Fase 4 (Pejalan Kaki)",
        greenDurationS: 15,
      },
    ],

    cycleLengthS: 110,

    // Nilai simulasi untuk tampilan frontend.
    avgDelayS: 34,

    avgQueueLengthM: 29,

    throughputVeh: 1240,
  },

  // Nilai simulasi untuk frontend.
  expectedImprovementPct: 18,
};


/* =========================================================
 * TRAFFIC FORECAST
 * ========================================================= */

/*
 * Forecast dibuat berdasarkan kondisi traffic saat ini.
 *
 * Horizon:
 * 0  = kondisi saat ini
 * 3  = 3 menit ke depan
 * 6  = 6 menit ke depan
 * 9  = 9 menit ke depan
 * 12 = 12 menit ke depan
 * 15 = 15 menit ke depan
 *
 * ForecastPoint tetap dibuat per approach sesuai data contract.
 * ForecastChart kemudian menjumlahkannya untuk membentuk
 * satu garis total traffic.
 */

export const mockForecast: ForecastPoint[] = [
  // -------------------------------------------------------
  // 0 MINUTES — CURRENT
  // -------------------------------------------------------

  {
    approach: "north",
    horizonMinutes: 0,
    predictedVolume: 65,
  },
  {
    approach: "south",
    horizonMinutes: 0,
    predictedVolume: 60,
  },
  {
    approach: "east",
    horizonMinutes: 0,
    predictedVolume: 82,
  },
  {
    approach: "west",
    horizonMinutes: 0,
    predictedVolume: 73,
  },

  // -------------------------------------------------------
  // 3 MINUTES
  // -------------------------------------------------------

  {
    approach: "north",
    horizonMinutes: 3,
    predictedVolume: 68,
  },
  {
    approach: "south",
    horizonMinutes: 3,
    predictedVolume: 63,
  },
  {
    approach: "east",
    horizonMinutes: 3,
    predictedVolume: 88,
  },
  {
    approach: "west",
    horizonMinutes: 3,
    predictedVolume: 76,
  },

  // -------------------------------------------------------
  // 6 MINUTES
  // -------------------------------------------------------

  {
    approach: "north",
    horizonMinutes: 6,
    predictedVolume: 72,
  },
  {
    approach: "south",
    horizonMinutes: 6,
    predictedVolume: 66,
  },
  {
    approach: "east",
    horizonMinutes: 6,
    predictedVolume: 94,
  },
  {
    approach: "west",
    horizonMinutes: 6,
    predictedVolume: 81,
  },

  // -------------------------------------------------------
  // 9 MINUTES
  // -------------------------------------------------------

  {
    approach: "north",
    horizonMinutes: 9,
    predictedVolume: 70,
  },
  {
    approach: "south",
    horizonMinutes: 9,
    predictedVolume: 65,
  },
  {
    approach: "east",
    horizonMinutes: 9,
    predictedVolume: 91,
  },
  {
    approach: "west",
    horizonMinutes: 9,
    predictedVolume: 79,
  },

  // -------------------------------------------------------
  // 12 MINUTES
  // -------------------------------------------------------

  {
    approach: "north",
    horizonMinutes: 12,
    predictedVolume: 74,
  },
  {
    approach: "south",
    horizonMinutes: 12,
    predictedVolume: 69,
  },
  {
    approach: "east",
    horizonMinutes: 12,
    predictedVolume: 97,
  },
  {
    approach: "west",
    horizonMinutes: 12,
    predictedVolume: 83,
  },

  // -------------------------------------------------------
  // 15 MINUTES
  // -------------------------------------------------------

  {
    approach: "north",
    horizonMinutes: 15,
    predictedVolume: 71,
  },
  {
    approach: "south",
    horizonMinutes: 15,
    predictedVolume: 67,
  },
  {
    approach: "east",
    horizonMinutes: 15,
    predictedVolume: 93,
  },
  {
    approach: "west",
    horizonMinutes: 15,
    predictedVolume: 80,
  },
];


/* =========================================================
 * INTERSECTION
 * ========================================================= */

export const mockIntersection = {
  name: "Simpang Pingit, Yogyakarta",

  // Koordinat masih menggunakan koordinat mock.
  // Ganti setelah koordinat intersection final dari SUMO/OSM
  // sudah ditentukan oleh tim.
  coords: "-7.782800, 110.360830",
};


/* =========================================================
 * DASHBOARD DISPLAY DATA
 * ========================================================= */

/*
 * Occupancy masih merupakan data mock untuk tampilan.
 * Nanti dapat diganti dengan hasil perhitungan traffic state
 * dari backend.
 */
export const mockOccupancyPct = 68;


/*
 * Informasi cuaca hanya digunakan sebagai elemen pendukung
 * pada dashboard.
 */
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