// src/lib/mockData.ts
//
// Traffic data TIDAK lagi disimpan sebagai mock.
//
// Source of truth:
//
// CSV
//   ↓
// traffic_state_builder.py
//   ↓
// FastAPI
//   ↓
// /api/v1/traffic/state
//   ↓
// Frontend
//
// File ini dipertahankan sementara agar struktur project tidak
// perlu langsung dirombak terlalu banyak.
// Data traffic asli diambil melalui fetchTrafficState().

import type {
  TrafficState,
} from "@/types/traffic";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

/**
 * Mengambil traffic state terbaru dari backend.
 *
 * Backend:
 * GET /api/v1/traffic/state
 *
 * Data berasal dari:
 * cv/output/smarttwin_traffic_data.csv
 * melalui traffic_state_builder.py
 */
export async function fetchTrafficState(): Promise<TrafficState> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/traffic/state`,
    {
      method: "GET",
      cache: "no-store",
    }
  );

  if (!response.ok) {
    throw new Error(
      `Gagal mengambil traffic state: ${response.status} ${response.statusText}`
    );
  }

  const data: TrafficState = await response.json();

  return data;
}