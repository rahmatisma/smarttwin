// SmartTwin frontend types.
// Source of truth: docs/data-contract.md
// Semua nama field mengikuti contract dan menggunakan camelCase.

export type Approach = "north" | "south" | "east" | "west";

export interface ApproachState {
  approach: Approach;

  // Total kendaraan yang melewati counting line selama window.
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
  // Bukan vehicles/km.
  densityIndex: number;

  // null = data speed belum tersedia.
  avgSpeedKmh: number | null;
}

export interface TrafficState {
  intersectionId: string;
  windowStart: string;
  windowEnd: string;
  approaches: ApproachState[];
}