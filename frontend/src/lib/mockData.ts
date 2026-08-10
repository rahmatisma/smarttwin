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
  { approach: "north", volume: 342, queueLengthM: 48, densityVehPerKm: 62, avgSpeedKmh: 18 },
  { approach: "south", volume: 298, queueLengthM: 35, densityVehPerKm: 51, avgSpeedKmh: 22 },
  { approach: "east", volume: 189, queueLengthM: 22, densityVehPerKm: 34, avgSpeedKmh: 27 },
  { approach: "west", volume: 227, queueLengthM: 29, densityVehPerKm: 41, avgSpeedKmh: 24 },
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
  intersectionId: "simpang4-kiaracondong",
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

export const mockForecast: ForecastPoint[] = [
  { minute: 0, predictedVolume: 980 },
  { minute: 3, predictedVolume: 1040 },
  { minute: 6, predictedVolume: 1210 },
  { minute: 9, predictedVolume: 1150 },
  { minute: 12, predictedVolume: 1280 },
  { minute: 15, predictedVolume: 1190 },
];

export const mockIntersection = {
  name: "Simpang Kiaracondong (Samsat)",
  coords: "-6.945539, 107.641951",
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
