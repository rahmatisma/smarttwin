// Data dummy — nanti diganti hasil fetch ke FastAPI (Minggu 4).
// Bentuknya sengaja sudah persis mengikuti tipe di types/traffic.ts,
// supaya swap ke data asli tidak butuh ubah struktur, cukup ganti sumbernya.

import type {
  ApproachState,
  VehicleClassCount,
  SignalRecommendation,
  ForecastPoint,
  SignalStatus,
} from "@/types/traffic";

export const mockApproachStates: ApproachState[] = [
  { approach: "north", volume: 59, queueLengthM: 42, densityVehPerKm: 93.8, avgSpeedKmh: 52.9 },
  { approach: "south", volume: 62, queueLengthM: 28, densityVehPerKm: 128.9, avgSpeedKmh: 49.8 },
  { approach: "east", volume: 90, queueLengthM: 42, densityVehPerKm: 158.0, avgSpeedKmh: 15.9 },
  { approach: "west", volume: 59, queueLengthM: 35, densityVehPerKm: 130.6, avgSpeedKmh: 16.5 },
];

export const mockVehicleClassCounts: VehicleClassCount[] = [
  { vehicleClass: "motorcycle", count: 812 },
  { vehicleClass: "car", count: 196 },
  { vehicleClass: "bus", count: 14 },
  { vehicleClass: "truck", count: 34 },
];

export const mockSignalStatus: SignalStatus = {
  activePhase: ["north", "south"],
  phaseName: "Fase 1 — Utara-Selatan",
  color: "green",
  secondsRemaining: 23,
  cycleBreakdown: { greenS: 25, yellowS: 3, redS: 14 },
};

export const mockRecommendation: SignalRecommendation = {
  intersectionId: "simpang4-pingit",
  generatedAt: new Date().toISOString(),
  engine: "rule-based",
  chosenScenario: {
    scenarioId: "scn-04",
    phases: [
      { phaseName: "Fase 1 (Utara-Selatan)", greenDurationS: 45 },
      { phaseName: "Fase 2 (Timur-Barat)", greenDurationS: 35 },
      { phaseName: "Fase 3 (Belok Kanan)", greenDurationS: 20 },
      { phaseName: "Fase 4 (Pejalan Kaki)", greenDurationS: 15 },
    ],
    cycleLengthS: 90,
    avgDelayS: 41,
    avgQueueLengthM: 33,
    throughputVeh: 1180,
  },
  expectedImprovementPct: 23,
};

// Forecast dipecah per lengan sesuai docs/data-contract.md (ForecastPoint
// punya field approach). ForecastChart menjumlahkannya kembali per horizon
// supaya grafiknya tetap satu garis total.
export const mockForecast: ForecastPoint[] = [
  { approach: "north", horizonMinutes: 0, predictedVolume: 214 },
  { approach: "south", horizonMinutes: 0, predictedVolume: 225 },
  { approach: "east", horizonMinutes: 0, predictedVolume: 327 },
  { approach: "west", horizonMinutes: 0, predictedVolume: 214 },

  { approach: "north", horizonMinutes: 3, predictedVolume: 227 },
  { approach: "south", horizonMinutes: 3, predictedVolume: 239 },
  { approach: "east", horizonMinutes: 3, predictedVolume: 347 },
  { approach: "west", horizonMinutes: 3, predictedVolume: 227 },

  { approach: "north", horizonMinutes: 6, predictedVolume: 264 },
  { approach: "south", horizonMinutes: 6, predictedVolume: 278 },
  { approach: "east", horizonMinutes: 6, predictedVolume: 404 },
  { approach: "west", horizonMinutes: 6, predictedVolume: 264 },

  { approach: "north", horizonMinutes: 9, predictedVolume: 251 },
  { approach: "south", horizonMinutes: 9, predictedVolume: 264 },
  { approach: "east", horizonMinutes: 9, predictedVolume: 384 },
  { approach: "west", horizonMinutes: 9, predictedVolume: 251 },

  { approach: "north", horizonMinutes: 12, predictedVolume: 280 },
  { approach: "south", horizonMinutes: 12, predictedVolume: 294 },
  { approach: "east", horizonMinutes: 12, predictedVolume: 426 },
  { approach: "west", horizonMinutes: 12, predictedVolume: 280 },

  { approach: "north", horizonMinutes: 15, predictedVolume: 260 },
  { approach: "south", horizonMinutes: 15, predictedVolume: 273 },
  { approach: "east", horizonMinutes: 15, predictedVolume: 397 },
  { approach: "west", horizonMinutes: 15, predictedVolume: 260 },
];

export const mockIntersection = {
  name: "Simpang Pingit, Yogyakarta",
  // TODO(Rahmat): ganti dengan koordinat presisi hasil "Position" search
  // di osmWebWizard.py — ini masih koordinat umum Kota Yogyakarta, bukan
  // titik simpang yang sebenarnya (sama seperti Kiaracondong dulu, sumber
  // paling akurat itu langsung dari wizard, bukan pencarian manual).
  coords: "-7.782800, 110.360830",
};

// Dua nilai ini murni tampilan (bukan bagian data-contract.md) — occupancy
// bisa dihubungkan ke perhitungan riil nanti, cuaca/tanggal sekadar chrome
// visual dan tidak masuk skema domain.
export const mockOccupancyPct = 68;

export const mockWeather = {
  dateLabel: "10 Juli 2026",
  condition: "Berawan",
  tempC: 25,
};

export const mockCameraStatus = [
  { label: "CAM 01 — Utara", online: true },
  { label: "CAM 02 — Selatan", online: true },
  { label: "CAM 03 — Timur", online: true },
  { label: "CAM 04 — Barat", online: false },
];
