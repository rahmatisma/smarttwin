"use client";

import { useEffect, useState, useMemo, useRef } from "react";

import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";
import StatsRow from "@/components/StatsRow";
import DigitalTwinPanel from "@/components/DigitalTwinPanel";
import CameraFeedPanel from "@/components/CameraFeedPanel";
import SignalStatusPanel from "@/components/SignalStatusPanel";
import RecommendationPanel from "@/components/RecommendationPanel";
import ForecastChart from "@/components/ForecastChart";

import { useTrafficSimulation } from "@/hooks/useTrafficSimulaton";

import {
  fetchTrafficState,
  fetchSignalStatus,
  fetchRecommendation,
  fetchForecast,
  fetchIntersectionCoords,
} from "@/lib/supabaseData";

import {
  ALL_INTERSECTIONS,
  type IntersectionSelection,
  type ApproachSelection,
} from "@/lib/intersections";

import type {
  TrafficState,
  SignalStatus,
  Recommendation,
  ForecastResponse,
  VehicleClassCount,
  ForecastPrediction,
} from "@/types/traffic";

/*
 * =========================================================
 * AGGREGATION HELPERS
 * =========================================================
 */

function getAggregatedSignal(signals: SignalStatus[]): SignalStatus {
  const activeSignals = signals.filter(Boolean);
  if (activeSignals.length === 0) {
    return {
      intersectionId: "Semua Simpang",
      timestamp: new Date().toISOString(),
      currentPhase: "ALL",
      phaseName: "Semua Fase",
      remainingSeconds: 0,
      cycleTimeSeconds: 0,
      source: "mock",
    };
  }
  const latestTimestamp = new Date(
    Math.max(...activeSignals.map((s) => new Date(s.timestamp).getTime()))
  ).toISOString();
  const avgRemaining = Math.round(
    activeSignals.reduce((sum, s) => sum + s.remainingSeconds, 0) /
      activeSignals.length
  );
  const avgCycle = Math.round(
    activeSignals.reduce((sum, s) => sum + s.cycleTimeSeconds, 0) /
      activeSignals.length
  );
  const anySynced = activeSignals.some((s) => s.source !== "mock");

  return {
    intersectionId: "Semua Simpang",
    timestamp: latestTimestamp,
    currentPhase: "ALL",
    phaseName: "Semua Fase",
    remainingSeconds: avgRemaining,
    cycleTimeSeconds: avgCycle,
    source: anySynced ? "synced" : "mock",
  };
}

function getAggregatedRecommendation(
  recs: Recommendation[]
): Recommendation | null {
  const activeRecs = recs.filter(Boolean);
  if (activeRecs.length === 0) return null;
  const avgImprovement =
    activeRecs.reduce(
      (sum, r) => sum + r.expectedDelayReductionPercent,
      0
    ) / activeRecs.length;
  const avgConfidence =
    activeRecs.reduce((sum, r) => sum + r.confidence, 0) / activeRecs.length;

  return {
    intersectionId: "Semua Simpang",
    timestamp: new Date().toISOString(),
    recommendedPhase: "N/A",
    recommendedGreenSeconds: 0,
    currentGreenSeconds: 0,
    expectedDelayReductionPercent: avgImprovement,
    confidence: avgConfidence,
    reason:
      "Pilih salah satu persimpangan spesifik pada menu di atas untuk melihat detail rekomendasi optimasi fase lampu lalu lintas.",
    source: "SmartTwin AI",
  };
}

function getAggregatedForecast(
  forecasts: ForecastResponse[]
): ForecastResponse | null {
  const activeForecasts = forecasts.filter(
    (f) => f && f.predictions && f.predictions.length > 0
  );
  if (activeForecasts.length === 0) return null;

  const numPredictions = Math.min(
    ...activeForecasts.map((f) => f.predictions.length)
  );
  const aggregatedPredictions: ForecastPrediction[] = [];

  for (let i = 0; i < numPredictions; i++) {
    const timestamp = activeForecasts[0].predictions[i].timestamp;
    const sumCount = activeForecasts.reduce(
      (sum, f) => sum + f.predictions[i].predictedVehicleCount,
      0
    );
    const sumQueueVeh = activeForecasts.reduce(
      (sum, f) => sum + f.predictions[i].predictedQueueLengthVeh,
      0
    );
    const sumQueueM = activeForecasts.reduce(
      (sum, f) => sum + f.predictions[i].predictedQueueLengthMEst,
      0
    );
    const avgDensity =
      activeForecasts.reduce(
        (sum, f) => sum + f.predictions[i].predictedDensityIndex,
        0
      ) / activeForecasts.length;
    const speeds = activeForecasts
      .map((f) => f.predictions[i].predictedSpeedKmh)
      .filter((s): s is number => s !== null);
    const avgSpeed =
      speeds.length > 0
        ? speeds.reduce((sum, s) => sum + s, 0) / speeds.length
        : null;

    aggregatedPredictions.push({
      timestamp,
      predictedVehicleCount: sumCount,
      predictedQueueLengthVeh: sumQueueVeh,
      predictedQueueLengthMEst: sumQueueM,
      predictedDensityIndex: avgDensity,
      predictedSpeedKmh: avgSpeed,
    });
  }

  return {
    intersectionId: "Semua Simpang",
    horizonMinutes: activeForecasts[0].horizonMinutes,
    model: "Aggregated LSTM",
    predictions: aggregatedPredictions,
  };
}

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

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const WS_URL = `${API_BASE_URL.replace(/^http/, "ws")}/api/v1/traffic/ws`;

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

  const selectedIntersection: IntersectionSelection = "all";
  
  const videoTimeRef = useRef<number>(0);
  const requestIdRef = useRef<number>(0);

  /*
   * simpang4-pingit adalah SATU simpang 4 lengan, bukan 4 simpang
   * terpisah — dropdown utama di Header memfilter lengan (approach),
   * bukan intersectionId. selectedIntersection di atas tetap
   * dipertahankan apa adanya untuk CameraFeedPanel.
   */
  const [selectedApproach, setSelectedApproach] =
    useState<ApproachSelection>("all");

  const [allTrafficStates, setAllTrafficStates] =
    useState<Record<string, TrafficState | null>>({});

  const [allSignalStatuses, setAllSignalStatuses] =
    useState<Record<string, SignalStatus | null>>({});

  const [allRecommendations, setAllRecommendations] =
    useState<Record<string, Recommendation | null>>({});

  const [allForecasts, setAllForecasts] =
    useState<Record<string, ForecastResponse | null>>({});

  const [allCoords, setAllCoords] =
    useState<Record<string, { latitude: number | null; longitude: number | null } | null>>({});

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

  const [weatherData, setWeatherData] = useState<{
    condition: string;
    tempC: number | null;
  }>({
    condition: "Data tidak tersedia",
    tempC: null,
  });

  useEffect(() => {
    async function fetchWeather() {
      try {
        const response = await fetch("https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4=34.71.13.1001");
        if (!response.ok) return;

        const json = await response.json();
        // Mengambil prakiraan cuaca paling awal untuk hari ini
        const cuacaLokal = json.data?.[0]?.cuaca?.[0]?.[0];

        if (cuacaLokal) {
          setWeatherData({
            condition: cuacaLokal.weather_desc ?? "Data tidak tersedia",
            tempC: cuacaLokal.t ?? null,
          });
        }
      } catch (err) {
        console.error("Gagal mengambil data BMKG:", err);
      }
    }

    fetchWeather();
    // Refresh tiap 1 jam
    const intervalId = setInterval(fetchWeather, 3600000);
    return () => clearInterval(intervalId);
  }, []);

  /*
   * =========================================================
   * FETCH DARI SUPABASE
   * =========================================================
   */

  useEffect(() => {

    async function loadDashboardData() {

      try {

        setLoading(true);
        setError(null);

        const results = await Promise.all(
          ALL_INTERSECTIONS.map(async (inter) => {
            try {
                const [
                  trafficState,
                  signalStatus,
                  recommendation,
                  forecast,
                  coords,
                ] = await Promise.all([
                  fetchTrafficState(inter.databaseId, videoTimeRef.current),
                  fetchSignalStatus(inter.databaseId),
                  fetchRecommendation(inter.databaseId),
                  fetchForecast(inter.databaseId),
                  fetchIntersectionCoords(inter.databaseId),
                ]);
                return {
                  id: inter.id,
                  trafficState,
                  signalStatus,
                  recommendation,
                  forecast,
                  coords,
                };
            } catch (err) {
              console.error(`Gagal mengambil data untuk ${inter.name}:`, err);
              return {
                id: inter.id,
                trafficState: null,
                signalStatus: null,
                recommendation: null,
                forecast: null,
                coords: null,
              };
            }
          })
        );

        const newTrafficStates: Record<string, TrafficState | null> = {};
        const newSignalStatuses: Record<string, SignalStatus | null> = {};
        const newRecommendations: Record<string, Recommendation | null> = {};
        const newForecasts: Record<string, ForecastResponse | null> = {};
        const newCoords: Record<string, { latitude: number | null; longitude: number | null } | null> = {};

        results.forEach((res) => {
          newTrafficStates[res.id] = res.trafficState;
          newSignalStatuses[res.id] = res.signalStatus;
          newRecommendations[res.id] = res.recommendation;
          newForecasts[res.id] = res.forecast;
          newCoords[res.id] = res.coords;
        });

        setAllTrafficStates(newTrafficStates);
        setAllSignalStatuses(newSignalStatuses);
        setAllRecommendations(newRecommendations);
        setAllForecasts(newForecasts);
        setAllCoords(newCoords);

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

    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;
    const currentRequestId = ++requestIdRef.current;

    async function refetchAllData() {
      if (cancelled) return;
      const fetchId = ++requestIdRef.current;
      
      try {
        const results = await Promise.all(
          ALL_INTERSECTIONS.map(async (inter) => {
            try {
              const [
                trafficState,
                signalStatus,
                recommendation,
                forecast,
              ] = await Promise.all([
                fetchTrafficState(inter.databaseId, videoTimeRef.current),
                fetchSignalStatus(inter.databaseId),
                fetchRecommendation(inter.databaseId),
                fetchForecast(inter.databaseId),
              ]);
              return {
                id: inter.id,
                trafficState,
                signalStatus,
                recommendation,
                forecast,
              };
            } catch (err) {
              console.error(`Gagal mengambil data untuk ${inter.name}:`, err);
              return null;
            }
          })
        );

        if (cancelled || fetchId !== requestIdRef.current) return;

        setAllTrafficStates((prev) => {
          const next = { ...prev };
          results.forEach((res) => {
            if (res) next[res.id] = res.trafficState;
          });
          return next;
        });

        setAllSignalStatuses((prev) => {
          const next = { ...prev };
          results.forEach((res) => {
            if (res) next[res.id] = res.signalStatus;
          });
          return next;
        });

        setAllRecommendations((prev) => {
          const next = { ...prev };
          results.forEach((res) => {
            if (res) next[res.id] = res.recommendation;
          });
          return next;
        });

        setAllForecasts((prev) => {
          const next = { ...prev };
          results.forEach((res) => {
            if (res) next[res.id] = res.forecast;
          });
          return next;
        });
      } catch (err) {
        console.error("Gagal melakukan update realtime:", err);
      }
    }

    function connect() {
      if (cancelled) return;

      socket = new WebSocket(WS_URL);

      socket.onmessage = () => {
        refetchAllData();
      };

      socket.onclose = () => {
        if (cancelled) return;
        reconnectTimer = setTimeout(connect, 3000);
      };
    }

    connect();

    const pollInterval = setInterval(() => {
      if (!cancelled) refetchAllData();
    }, 1000);

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      clearInterval(pollInterval);
      socket?.close();
    };

  }, []);

  /*
   * =========================================================
   * MEMOIZED AGGREGATED / FILTERED DATA
   * =========================================================
   */

  const activeTrafficState = useMemo(() => {
    if (selectedIntersection !== "all") {
      return allTrafficStates[selectedIntersection] ?? {
        intersectionId: selectedIntersection,
        windowStart: new Date().toISOString(),
        windowEnd: new Date().toISOString(),
        approaches: [],
      };
    }

    const states = ALL_INTERSECTIONS.map(
      (inter) => allTrafficStates[inter.id]
    ).filter((s): s is TrafficState => s != null);

    if (states.length === 0) {
      return {
        intersectionId: "Semua Simpang",
        windowStart: new Date().toISOString(),
        windowEnd: new Date().toISOString(),
        approaches: [],
      };
    }

    const combinedApproaches = states.flatMap((s) => s.approaches);

    return {
      intersectionId: "Semua Simpang",
      windowStart: states[0].windowStart,
      windowEnd: states[0].windowEnd,
      approaches: combinedApproaches,
    };
  }, [selectedIntersection, allTrafficStates]);

  const activeSignal = useMemo(() => {
    // 1. Single Source of Truth: LIVE SIMULATION
    if (simulatedSignal) {
      return simulatedSignal;
    }

    // 2. Fallback: Supabase Decision Engine Database
    if (selectedIntersection !== "all") {
      const dbSignal = allSignalStatuses[selectedIntersection];
      if (dbSignal) return dbSignal;
    } else {
      const signals = ALL_INTERSECTIONS.map(
        (inter) => allSignalStatuses[inter.id]
      ).filter((s): s is SignalStatus => s != null);

      if (signals.length > 0) {
        return getAggregatedSignal(signals);
      }
    }

    // 3. Fallback: Offline state
    return {
      intersectionId: "simpang4-pingit",
      timestamp: new Date().toISOString(),
      currentPhase: "NS",
      phaseName: "Sistem Offline",
      remainingSeconds: 0,
      cycleTimeSeconds: 0,
      source: "mock",
    } as SignalStatus;
  }, [selectedIntersection, allSignalStatuses, simulatedSignal]);

  const activeRecommendation = useMemo(() => {
    if (selectedIntersection !== "all") {
      return allRecommendations[selectedIntersection] ?? null;
    }

    const recs = ALL_INTERSECTIONS.map(
      (inter) => allRecommendations[inter.id]
    ).filter((r): r is Recommendation => r != null);

    return getAggregatedRecommendation(recs);
  }, [selectedIntersection, allRecommendations]);

  const activeForecast = useMemo(() => {
    if (selectedIntersection !== "all") {
      return allForecasts[selectedIntersection] ?? null;
    }

    const fcst = ALL_INTERSECTIONS.map(
      (inter) => allForecasts[inter.id]
    ).filter((f): f is ForecastResponse => f != null);

    return getAggregatedForecast(fcst);
  }, [selectedIntersection, allForecasts]);

  /*
   * Approaches dari simpang4-pingit (satu-satunya intersection nyata
   * di database saat ini), difilter berdasarkan lengan yang dipilih
   * di dropdown Header — bukan berdasarkan selectedIntersection.
   * Dipakai oleh StatsRow dan DigitalTwinPanel.
   */
  const lenganFilteredApproaches = useMemo(() => {
    const approaches = allTrafficStates["intersection4"]?.approaches ?? [];
    if (selectedApproach === "all") return approaches;
    return approaches.filter((a) => a.approach === selectedApproach);
  }, [selectedApproach, allTrafficStates]);

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
   * ERROR / EMPTY STATE CHECK
   * =========================================================
   */

  const hasLoadedAnyData = Object.values(allTrafficStates).some((state) => state !== null);

  if (error || !hasLoadedAnyData) {

    return (
      <div className="flex min-h-screen bg-bg">

        <Sidebar />

        <div className="flex min-w-0 flex-1 flex-col">

          <Header
            locationName="Semua Simpang"
            coords="Koordinat belum tersedia"
          />

          <main className="flex flex-1 items-center justify-center px-6">

            <div className="rounded-lg border border-border bg-surface p-6">

              <div className="text-sm font-semibold text-text">
                Gagal mengambil data traffic
              </div>

              <div className="mt-2 text-xs text-text-secondary">
                {error ??
                  "Traffic state tidak tersedia untuk persimpangan yang dipilih."}
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

  const hasTrafficData = lenganFilteredApproaches.length > 0;

  const vehicleClassCounts: VehicleClassCount[] = [

    {
      vehicleClass: "motorcycle",

      count: lenganFilteredApproaches.reduce(
        (sum, approach) =>
          sum + approach.motorcycleCount,
        0
      ),
    },

    {
      vehicleClass: "car",

      count: lenganFilteredApproaches.reduce(
        (sum, approach) =>
          sum + approach.carCount,
        0
      ),
    },

    {
      vehicleClass: "bus",

      count: lenganFilteredApproaches.reduce(
        (sum, approach) =>
          sum + approach.busCount,
        0
      ),
    },

    {
      vehicleClass: "truck",

      count: lenganFilteredApproaches.reduce(
        (sum, approach) =>
          sum + approach.truckCount,
        0
      ),
    },

  ];

  /*
   * =========================================================
   * WEATHER
   * =========================================================
   */

  const weather = {
    dateLabel: new Date(activeTrafficState.windowEnd).toLocaleDateString("id-ID"),
    condition: weatherData.condition,
    tempC: weatherData.tempC,
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
          selectedApproach={selectedApproach}
          onApproachChange={setSelectedApproach}
          locationName="simpang4-pingit"
          coords={(() => {
            const c = allCoords["intersection4"];
            if (c?.latitude && c?.longitude) {
              return `${c.latitude}, ${c.longitude}`;
            }
            return "Koordinat belum tersedia";
          })()}
          lastUpdated={
            hasTrafficData 
              ? (activeTrafficState.matchedCvTime ?? activeTrafficState.windowEnd) 
              : undefined
          }
        />

        {/* ===================================================
            STATISTICS
            =================================================== */}

        <StatsRow
          approaches={lenganFilteredApproaches}
          weather={weather}
        />

        <div className="flex flex-col gap-4 px-6 pb-6">

          {/* =================================================
              DIGITAL TWIN + CAMERA
              ================================================= */}

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">

            {/* DIGITAL TWIN */}

            <div className="xl:col-span-2">
              <DigitalTwinPanel
                approaches={lenganFilteredApproaches}
                signal={activeSignal}
              />
            </div>

            {/* CAMERA */}

            <div className="xl:col-span-1">
              <CameraFeedPanel
                counts={hasTrafficData ? vehicleClassCounts : []}
                selectedApproach={selectedApproach}
                onApproachChange={setSelectedApproach}
                onTimeUpdate={(time) => {
                  videoTimeRef.current = time;
                }}
              />
            </div>

          </div>

          {/* =================================================
              RECOMMENDATION + SIGNAL STATUS
              ================================================= */}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">

            {/* RECOMMENDATION */}

            <RecommendationPanel
              recommendation={activeRecommendation}
            />

            {/* SIGNAL STATUS */}

            <SignalStatusPanel
              signal={activeSignal}
            />

          </div>

          {/* =================================================
              FORECAST
              ================================================= */}

          <div className="w-full">
            <ForecastChart
              data={activeForecast}
              current={activeTrafficState}
            />
          </div>

        </div>

      </div>

    </div>

  );
}