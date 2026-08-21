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

import { supabase } from "@/lib/supabaseClient";

import {
  DEFAULT_INTERSECTION_ID,
  fetchTrafficState,
  fetchSignalStatus,
  fetchRecommendation,
  fetchForecast,
  fetchCameras,
} from "@/lib/supabaseData";

import type {
  TrafficState,
  SignalStatus,
  Recommendation,
  ForecastResponse,
  VehicleClassCount,
} from "@/types/traffic";

/*
 * =========================================================
 * DASHBOARD SKELETON
 * =========================================================
 */

function DashboardSkeleton() {
  return (
    <div className="flex min-h-screen bg-bg">

      {/* SIDEBAR */}
      <Sidebar />

      {/* CONTENT */}
      <div className="flex min-w-0 flex-1 flex-col">

        {/* HEADER SKELETON */}
        <div className="border-b border-border bg-surface px-6 py-4">
          <div className="flex items-center justify-between">

            <div className="space-y-2">
              <div className="h-4 w-32 animate-pulse rounded bg-surface-2" />
              <div className="h-3 w-48 animate-pulse rounded bg-surface-2" />
            </div>

            <div className="h-8 w-8 animate-pulse rounded-full bg-surface-2" />

          </div>
        </div>

        {/* MAIN */}
        <main className="flex-1 px-6 py-5">

          {/* =================================================
              STATS SKELETON
              ================================================= */}

          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">

            {[1, 2, 3, 4].map((item) => (
              <div
                key={item}
                className="rounded-lg border border-border bg-surface p-4"
              >
                <div className="h-3 w-24 animate-pulse rounded bg-surface-2" />

                <div className="mt-3 h-7 w-20 animate-pulse rounded bg-surface-2" />

                <div className="mt-2 h-2.5 w-28 animate-pulse rounded bg-surface-2" />
              </div>
            ))}

          </div>

          {/* =================================================
              DIGITAL TWIN + CAMERA
              ================================================= */}

          <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[2fr_1fr]">

            {/* DIGITAL TWIN SKELETON */}

            <div className="min-h-[400px] rounded-lg border border-border bg-surface p-4">

              <div className="flex items-center justify-between">

                <div className="h-4 w-32 animate-pulse rounded bg-surface-2" />

                <div className="h-6 w-20 animate-pulse rounded bg-surface-2" />

              </div>

              <div className="mt-4 h-[330px] animate-pulse rounded-md bg-surface-2" />

            </div>

            {/* RIGHT COLUMN */}

            <div className="flex flex-col gap-4">

              {/* CAMERA */}

              <div className="rounded-lg border border-border bg-surface p-4">

                <div className="flex items-center justify-between">

                  <div className="h-4 w-28 animate-pulse rounded bg-surface-2" />

                  <div className="h-3 w-16 animate-pulse rounded bg-surface-2" />

                </div>

                <div className="mt-4 flex gap-3">

                  <div className="aspect-square w-2/5 animate-pulse rounded-md bg-surface-2" />

                  <div className="flex flex-1 flex-col justify-between gap-3">

                    {[1, 2, 3, 4].map((item) => (
                      <div
                        key={item}
                        className="h-3 w-full animate-pulse rounded bg-surface-2"
                      />
                    ))}

                  </div>

                </div>

              </div>

              {/* SIGNAL STATUS */}

              <div className="rounded-lg border border-border bg-surface p-4">

                <div className="h-4 w-32 animate-pulse rounded bg-surface-2" />

                <div className="mt-4 space-y-3">

                  {[1, 2, 3, 4].map((item) => (
                    <div
                      key={item}
                      className="flex items-center justify-between"
                    >
                      <div className="h-3 w-20 animate-pulse rounded bg-surface-2" />

                      <div className="h-3 w-12 animate-pulse rounded bg-surface-2" />
                    </div>
                  ))}

                </div>

              </div>

            </div>

          </div>

          {/* =================================================
              RECOMMENDATION + FORECAST
              ================================================= */}

          <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">

            {/* RECOMMENDATION */}

            <div className="min-h-[220px] rounded-lg border border-border bg-surface p-4">

              <div className="h-4 w-36 animate-pulse rounded bg-surface-2" />

              <div className="mt-5 space-y-3">

                <div className="h-3 w-full animate-pulse rounded bg-surface-2" />

                <div className="h-3 w-5/6 animate-pulse rounded bg-surface-2" />

                <div className="h-3 w-2/3 animate-pulse rounded bg-surface-2" />

              </div>

              <div className="mt-6 h-10 w-32 animate-pulse rounded bg-surface-2" />

            </div>

            {/* FORECAST */}

            <div className="min-h-[220px] rounded-lg border border-border bg-surface p-4">

              <div className="flex items-center justify-between">

                <div className="h-4 w-28 animate-pulse rounded bg-surface-2" />

                <div className="h-3 w-16 animate-pulse rounded bg-surface-2" />

              </div>

              <div className="mt-5 h-[140px] animate-pulse rounded-md bg-surface-2" />

            </div>

          </div>

        </main>
      </div>
    </div>
  );
}

export default function DashboardPage() {

  /*
   * =========================================================
   * SIGNAL SIMULATION (fallback)
   * =========================================================
   *
   * Dipakai hanya kalau signalStatuses di Supabase kosong.
   */

  const simulatedSignal = useTrafficSimulation();

  /*
   * =========================================================
   * STATE
   * =========================================================
   */

  const [trafficState, setTrafficState] =
    useState<TrafficState | null>(null);

  const [signalStatus, setSignalStatus] =
    useState<SignalStatus | null>(null);

  const [recommendation, setRecommendation] =
    useState<Recommendation | null>(null);

  const [forecast, setForecast] =
    useState<ForecastResponse | null>(null);

  const [cameraStatus, setCameraStatus] =
    useState<{ id: string; label: string; online: boolean }[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

  /*
   * =========================================================
   * FETCH DARI SUPABASE
   * =========================================================
   *
   * trafficStates + trafficApproachStates
   * signalStatuses
   * recommendations
   * forecasts + forecastPredictions
   * cameras
   *        ↓
   * Dashboard
   */

  useEffect(() => {

    async function loadDashboardData() {

      try {

        setLoading(true);
        setError(null);

        const [
          trafficStateResult,
          signalStatusResult,
          recommendationResult,
          forecastResult,
          camerasResult,
        ] = await Promise.all([
          fetchTrafficState(DEFAULT_INTERSECTION_ID),
          fetchSignalStatus(DEFAULT_INTERSECTION_ID),
          fetchRecommendation(DEFAULT_INTERSECTION_ID),
          fetchForecast(DEFAULT_INTERSECTION_ID),
          fetchCameras(DEFAULT_INTERSECTION_ID),
        ]);

        setTrafficState(trafficStateResult);
        setSignalStatus(signalStatusResult);
        setRecommendation(recommendationResult);
        setForecast(forecastResult);

        setCameraStatus(
          camerasResult.map((camera) => ({
            id: String(camera.id),
            label: camera.name,
            online: camera.status === "active",
          }))
        );

      } catch (err) {

        console.error(
          "Gagal mengambil data dashboard dari Supabase:",
          err
        );

        setError(
          err instanceof Error
            ? err.message
            : "Gagal mengambil data dari Supabase."
        );

      } finally {

        setLoading(false);

      }
    }

    loadDashboardData();

    /*
     * Realtime: begitu process_uploaded_video.py (cv/) meng-upsert
     * baris trafficApproachStates baru, tarik ulang trafficState
     * terbaru supaya angka di dashboard berubah tanpa refresh
     * manual. Butuh trafficStates/trafficApproachStates didaftarkan
     * ke publication supabase_realtime lebih dulu (lihat docs).
     */
    const channel = supabase
      .channel("traffic-state-changes")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "trafficApproachStates" },
        () => {
          fetchTrafficState(DEFAULT_INTERSECTION_ID).then(setTrafficState);
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };

  }, []);

  const signal = signalStatus ?? simulatedSignal;

  /*
   * =========================================================
   * LOADING
   * =========================================================
   */

  if (loading) {
    return <DashboardSkeleton />;
  }

  /*
   * =========================================================
   * ERROR
   * =========================================================
   */

  if (error || !trafficState) {

    return (
      <div className="flex min-h-screen bg-bg">

        <Sidebar />

        <div className="flex min-w-0 flex-1 flex-col">

          <Header
            locationName="simpang4-pingit"
            coords="Koordinat belum tersedia"
          />

          <main className="flex flex-1 items-center justify-center px-6">

            <div className="rounded-lg border border-border bg-surface p-6">

              <div className="text-sm font-semibold text-text">
                Gagal mengambil data traffic
              </div>

              <div className="mt-2 text-xs text-text-secondary">
                {error ??
                  "Traffic state tidak tersedia."}
              </div>

              <div className="mt-4 text-xs text-text-muted">
                Pastikan koneksi ke Supabase aktif dan
                tabel trafficStates/trafficApproachStates
                sudah terisi untuk simpang4-pingit.
              </div>

            </div>

          </main>

        </div>

      </div>
    );
  }

  /*
   * =========================================================
   * VEHICLE CLASS COUNTS
   * =========================================================
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
   */

  const intersectionName =
    trafficState.intersectionId;

  /*
   * =========================================================
   * WEATHER
   * =========================================================
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

      <div className="flex min-w-0 flex-1 flex-col">

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
                cameraStatus={cameraStatus}
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
              recommendation={recommendation}
            />

            {/* FORECAST */}

            <ForecastChart
              data={forecast}
            />

          </div>

        </div>

      </div>

    </div>

  );
}