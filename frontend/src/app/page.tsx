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

import type { TrafficState } from "@/types/traffic";

import {
  mockVehicleClassCounts,
  mockRecommendation,
  mockForecast,
  mockIntersection,
  mockOccupancyPct,
  mockWeather,
  mockCameraStatus,
} from "@/lib/mockData";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export default function DashboardPage() {
  const signal = useTrafficSimulation();

  const [trafficState, setTrafficState] =
    useState<TrafficState | null>(null);

  const [trafficLoading, setTrafficLoading] =
    useState(true);

  const [trafficError, setTrafficError] =
    useState<string | null>(null);

  useEffect(() => {
    async function fetchTrafficState() {
      try {
        setTrafficLoading(true);
        setTrafficError(null);

        const response = await fetch(
          `${API_BASE_URL}/api/v1/traffic/state`,
          {
            cache: "no-store",
          }
        );

        if (!response.ok) {
          throw new Error(
            `Traffic API returned ${response.status}`
          );
        }

        const data: TrafficState = await response.json();

        setTrafficState(data);
      } catch (error) {
        console.error(
          "Failed to fetch traffic state:",
          error
        );

        setTrafficError(
          "Data traffic dari backend tidak tersedia."
        );
      } finally {
        setTrafficLoading(false);
      }
    }

    fetchTrafficState();

    const interval = setInterval(
      fetchTrafficState,
      5000
    );

    return () => clearInterval(interval);
  }, []);

  /*
   * Selama backend belum berhasil mengirim data,
   * dashboard tetap menggunakan mock sebagai fallback.
   *
   * Begitu API berhasil:
   *
   * Backend TrafficState
   *        ↓
   * trafficState
   *        ↓
   * Dashboard components
   */
  const approaches =
    trafficState?.approaches ?? [];

  const intersectionName =
    trafficState?.intersectionId ??
    mockIntersection.name;

  return (
    <div className="flex min-h-screen bg-bg">
      <Sidebar />

      <div className="flex-1">
        <Header
          locationName={intersectionName}
          coords={mockIntersection.coords}
        />

        {/* =====================================================
            TRAFFIC STATUS
            ===================================================== */}

        {trafficLoading && !trafficState && (
          <div className="px-6 pt-4 text-sm text-text-secondary">
            Mengambil data traffic dari backend...
          </div>
        )}

        {trafficError && !trafficState && (
          <div className="px-6 pt-4 text-sm text-signal-amber">
            {trafficError}
          </div>
        )}

        <StatsRow
          approaches={approaches}
          occupancyPct={mockOccupancyPct}
          weather={mockWeather}
        />

        {/* =====================================================
            MAIN DASHBOARD
            ===================================================== */}

        <div className="flex flex-col gap-4 px-6 pb-6">
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[2fr_1fr]">
            {/* =================================================
                DIGITAL TWIN
                ================================================= */}

            <DigitalTwinPanel
              approaches={approaches}
              signal={signal}
            />

            <div className="flex flex-col gap-4">
              {/* ===============================================
                  CAMERA
                  =============================================== */}

              <CameraFeedPanel
                counts={mockVehicleClassCounts}
                cameraStatus={mockCameraStatus}
              />

              {/* ===============================================
                  SIGNAL
                  =============================================== */}

              <SignalStatusPanel signal={signal} />
            </div>
          </div>

          {/* ===================================================
              RECOMMENDATION + FORECAST
              =================================================== */}

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <RecommendationPanel
              recommendation={mockRecommendation}
            />

            <ForecastChart data={mockForecast} />
          </div>
        </div>
      </div>
    </div>
  );
}