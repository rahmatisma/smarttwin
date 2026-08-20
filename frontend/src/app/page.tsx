"use client";

import { useEffect, useState } from "react";

import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";
import StatsRow from "@/components/StatsRow";
import DigitalTwinPanel from "@/components/DigitalTwinPanel";
import CameraFeedPanel from "@/components/CameraFeedPanel";
import SignalStatusPanel from "@/components/SignalStatusPanel";
import RecommendationPanel from "@/components/RecommendationPanel";
import ForecastChart from "@/components/ForecastChart";

import { useTrafficSimulation } from "@/hooks/useTrafficSimulaton";

import type {
  TrafficState,
  VehicleClassCount,
} from "@/types/traffic";

/*
 * =========================================================
 * BACKEND API
 * =========================================================
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

export default function DashboardPage() {
  /*
   * =========================================================
   * SIGNAL SIMULATION
   * =========================================================
   */

  const signal = useTrafficSimulation();

  /*
   * =========================================================
   * TRAFFIC STATE
   * =========================================================
   */

  const [trafficState, setTrafficState] =
    useState<TrafficState | null>(null);

  const [loading, setLoading] = useState(true);

  const [error, setError] =
    useState<string | null>(null);

  /*
   * =========================================================
   * FETCH TRAFFIC STATE
   * =========================================================
   *
   * Sumber data:
   *
   * CSV / State Builder
   *        ↓
   * FastAPI
   *        ↓
   * /api/v1/traffic/state
   *        ↓
   * Dashboard
   *
   * Tidak menggunakan mockData.
   */

  useEffect(() => {
    async function loadTrafficState() {
      try {
        setLoading(true);
        setError(null);

        const response = await fetch(
          `${API_BASE_URL}/api/v1/traffic/state`,
          {
            method: "GET",
            cache: "no-store",
          }
        );

        if (!response.ok) {
          throw new Error(
            `HTTP ${response.status}: ${response.statusText}`
          );
        }

        const data: TrafficState =
          await response.json();

        setTrafficState(data);
      } catch (err) {
        console.error(
          "Gagal mengambil traffic state:",
          err
        );

        setError(
          err instanceof Error
            ? err.message
            : "Gagal mengambil data traffic."
        );
      } finally {
        setLoading(false);
      }
    }

    loadTrafficState();
  }, []);

  /*
   * =========================================================
   * LOADING
   * =========================================================
   */

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg">
        <div className="text-sm text-text-secondary">
          Mengambil data traffic dari backend...
        </div>
      </div>
    );
  }

  /*
   * =========================================================
   * ERROR
   * =========================================================
   */

  if (error || !trafficState) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg">
        <div className="rounded-lg border border-border bg-surface p-6">
          <div className="text-sm font-semibold text-text">
            Gagal mengambil data traffic
          </div>

          <div className="mt-2 text-xs text-text-secondary">
            {error ?? "Traffic state tidak tersedia."}
          </div>

          <div className="mt-4 text-xs text-text-muted">
            Pastikan backend FastAPI sedang berjalan dan
            endpoint /api/v1/traffic/state tersedia.
          </div>
        </div>
      </div>
    );
  }

  /*
   * =========================================================
   * VEHICLE CLASS COUNTS
   * =========================================================
   *
   * Data dibentuk langsung dari TrafficState backend.
   *
   * Tidak ada angka dummy.
   */

  const vehicleClassCounts: VehicleClassCount[] = [
    {
      vehicleClass: "motorcycle",
      count: trafficState.approaches.reduce(
        (sum, approach) =>
          sum + approach.motorcycleCount,
        0
      ),
    },

    {
      vehicleClass: "car",
      count: trafficState.approaches.reduce(
        (sum, approach) =>
          sum + approach.carCount,
        0
      ),
    },

    {
      vehicleClass: "bus",
      count: trafficState.approaches.reduce(
        (sum, approach) =>
          sum + approach.busCount,
        0
      ),
    },

    {
      vehicleClass: "truck",
      count: trafficState.approaches.reduce(
        (sum, approach) =>
          sum + approach.truckCount,
        0
      ),
    },
  ];

  /*
   * =========================================================
   * INTERSECTION
   * =========================================================
   *
   * Menggunakan intersectionId dari backend.
   */

  const intersectionName =
    trafficState.intersectionId;

  /*
   * =========================================================
   * WEATHER
   * =========================================================
   *
   * Weather belum tersedia di TrafficState contract.
   *
   * Jangan membuat angka suhu atau kondisi cuaca palsu.
   */

  const weather = {
    dateLabel: new Date(
      trafficState.windowEnd
    ).toLocaleDateString("id-ID"),

    condition: "Data tidak tersedia",

    tempC: null,
  };

  /*
   * =========================================================
   * DASHBOARD
   * =========================================================
   */

  return (
    <div className="flex min-h-screen bg-bg">
      <Sidebar />

      <div className="flex-1">
        {/* ===================================================
            HEADER
            =================================================== */}

        <Header
          locationName={intersectionName}
          coords="Koordinat belum tersedia"
        />

        {/* ===================================================
            STATISTICS
            =================================================== */}

        <StatsRow
          approaches={trafficState.approaches}
          weather={weather}
        />

        <div className="flex flex-col gap-4 px-6 pb-6">

          {/* =================================================
              DIGITAL TWIN + CAMERA
              ================================================= */}

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[2fr_1fr]">

            {/* DIGITAL TWIN */}

            <DigitalTwinPanel
              approaches={trafficState.approaches}
              signal={signal}
            />

            {/* RIGHT COLUMN */}

            <div className="flex flex-col gap-4">

              {/* CAMERA */}

              <CameraFeedPanel
                counts={vehicleClassCounts}
                cameraStatus={[]}
              />

              {/* SIGNAL STATUS */}

              <SignalStatusPanel
                signal={signal}
              />

            </div>
          </div>

          {/* =================================================
              RECOMMENDATION + FORECAST
              ================================================= */}

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">

            {/* RECOMMENDATION */}

            <RecommendationPanel
              recommendation={null}
            />

            {/* FORECAST */}

            <ForecastChart
              data={null}
            />

          </div>
        </div>
      </div>
    </div>
  );
}