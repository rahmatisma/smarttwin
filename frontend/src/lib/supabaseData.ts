// src/lib/supabaseData.ts
//
// Query layer Supabase untuk frontend.
//
// Membaca langsung dari tabel-tabel di docs/database.md
// (lewat anon key + RLS SELECT-only) dan membentuk ulang
// hasilnya supaya persis mengikuti contract di
// src/types/traffic.ts.

import { supabase } from "@/lib/supabaseClient";

import type {
  TrafficState,
  SignalStatus,
  Recommendation,
  ForecastResponse,
} from "@/types/traffic";

export const DEFAULT_INTERSECTION_ID = "simpang4-pingit";

/* =========================================================
 * INTERSECTION LOOKUP
 * ========================================================= */

async function getIntersectionRowId(
  intersectionId: string
): Promise<number | null> {
  const { data, error } = await supabase
    .from("intersections")
    .select("id")
    .eq("intersectionId", intersectionId)
    .maybeSingle();

  if (error) {
    throw new Error(`Gagal mengambil intersection: ${error.message}`);
  }

  return data?.id ?? null;
}

export async function fetchIntersectionCoords(
  intersectionId: string
): Promise<{ latitude: number | null; longitude: number | null } | null> {
  const { data, error } = await supabase
    .from("intersections")
    .select("latitude, longitude")
    .eq("intersectionId", intersectionId)
    .maybeSingle();

  if (error) {
    console.error(`Gagal mengambil koordinat: ${error.message}`);
    return null;
  }
  return data;
}

/* =========================================================
 * TRAFFIC STATE
 * ========================================================= */

export async function fetchTrafficState(
  intersectionId: string = DEFAULT_INTERSECTION_ID,
  videoTime?: number
): Promise<TrafficState | null> {
  const rowId = await getIntersectionRowId(intersectionId);

  if (rowId === null) {
    return null;
  }

  // [HACK] Bypass Supabase for traffic state to read directly from CSV via Backend API
  try {
    const url = new URL("http://127.0.0.1:8000/api/v1/traffic/live-csv");
    if (videoTime !== undefined) {
      url.searchParams.append("video_time", videoTime.toString());
    }
    const res = await fetch(url.toString(), { cache: "no-store" });
    if (res.ok) {
      const json = await res.json();
      if (json.success && json.data) {
        // Development logging as requested
        const totalVehicles = json.data.approaches?.reduce((sum: number, a: any) => sum + a.volume, 0) ?? 0;
        console.log("CV:", {
          requestedVideoTime: videoTime,
          matchedCvTime: json.timestamp,
          vehicleCount: totalVehicles
        });

        return {
          intersectionId,
          windowStart: json.data.windowStart,
          windowEnd: json.data.windowEnd,
          matchedCvTime: json.timestamp,
          approaches: json.data.approaches ?? [],
        };
      }
    }
  } catch (e) {
    console.warn("Gagal fetch live-csv:", e);
  }

  const { data: state, error: stateError } = await supabase
    .from("trafficStates")
    .select("id, windowStart, windowEnd")
    .eq("intersectionId", rowId)
    .order("windowEnd", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (stateError) {
    throw new Error(`Gagal mengambil traffic state: ${stateError.message}`);
  }

  if (!state) {
    return null;
  }

  const { data: approaches, error: approachError } = await supabase
    .from("trafficApproachStates")
    .select(
      "approach, volume, carCount, motorcycleCount, busCount, truckCount, queueLengthVeh, queueLengthMEst, densityIndex, avgSpeedKmh"
    )
    .eq("trafficStateId", state.id);

  if (approachError) {
    throw new Error(
      `Gagal mengambil traffic approach state: ${approachError.message}`
    );
  }

  return {
    intersectionId,
    windowStart: state.windowStart,
    windowEnd: state.windowEnd,
    approaches: approaches ?? [],
  };
}

/* =========================================================
 * SIGNAL STATUS
 * ========================================================= */

export async function fetchSignalStatus(
  intersectionId: string = DEFAULT_INTERSECTION_ID
): Promise<SignalStatus | null> {
  const rowId = await getIntersectionRowId(intersectionId);

  if (rowId === null) {
    return null;
  }

  const { data, error } = await supabase
    .from("signalStatuses")
    .select(
      "timestamp, currentPhase, phaseName, remainingSeconds, cycleTimeSeconds, source"
    )
    .eq("intersectionId", rowId)
    .order("timestamp", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (error) {
    throw new Error(`Gagal mengambil signal status: ${error.message}`);
  }

  if (!data) {
    return null;
  }

  return {
    intersectionId,
    ...data,
  };
}

/* =========================================================
 * RECOMMENDATION
 * ========================================================= */

export async function fetchRecommendation(
  intersectionId: string = DEFAULT_INTERSECTION_ID
): Promise<Recommendation | null> {
  const rowId = await getIntersectionRowId(intersectionId);

  if (rowId === null) {
    return null;
  }

  const { data, error } = await supabase
    .from("recommendations")
    .select(
      "timestamp, recommendedPhase, recommendedGreenSeconds, currentGreenSeconds, expectedDelayReductionPercent, confidence, reason, source"
    )
    .eq("intersectionId", rowId)
    .order("timestamp", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (error) {
    throw new Error(`Gagal mengambil recommendation: ${error.message}`);
  }

  if (!data) {
    return null;
  }

  return {
    intersectionId,
    ...data,
  };
}

/* =========================================================
 * FORECAST
 * ========================================================= */

export async function fetchForecast(
  intersectionId: string = DEFAULT_INTERSECTION_ID
): Promise<ForecastResponse | null> {
  const rowId = await getIntersectionRowId(intersectionId);

  if (rowId === null) {
    return null;
  }

  const { data: forecast, error: forecastError } = await supabase
    .from("forecasts")
    .select("id, horizonMinutes, model")
    .eq("intersectionId", rowId)
    .order("createdAt", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (forecastError) {
    throw new Error(`Gagal mengambil forecast: ${forecastError.message}`);
  }

  if (!forecast) {
    return null;
  }

  const { data: predictions, error: predictionError } = await supabase
    .from("forecastPredictions")
    .select(
      "timestamp, predictedVehicleCount, predictedQueueLengthVeh, predictedQueueLengthMEst, predictedDensityIndex, predictedSpeedKmh"
    )
    .eq("forecastId", forecast.id)
    .order("timestamp", { ascending: true });

  if (predictionError) {
    throw new Error(
      `Gagal mengambil forecast prediction: ${predictionError.message}`
    );
  }

  return {
    intersectionId,
    horizonMinutes: forecast.horizonMinutes,
    model: forecast.model,
    predictions: predictions ?? [],
  };
}

/* =========================================================
 * CAMERAS (halaman CCTV)
 * ========================================================= */

export interface DbCamera {
  id: number;
  cameraId: string;
  name: string;
  approach: string | null;
  intersectionId: string | null;
  intersectionName: string | null;
  sourceType: string;
  sourceUrl: string | null;
  status: string;
  videoUrl: string | null;
  videoName: string | null;
}

export async function fetchCameras(
  intersectionId: string = "all"
): Promise<DbCamera[]> {
  let query = supabase
    .from("cameras")
    .select("id, cameraId, name, approachId, intersectionId, sourceType, sourceUrl, status");

  if (intersectionId !== "all") {
    const rowId = await getIntersectionRowId(intersectionId);
    if (rowId === null) {
      return [];
    }
    query = query.eq("intersectionId", rowId);
  }

  const { data: cameras, error: cameraError } = await query;

  if (cameraError) {
    throw new Error(`Gagal mengambil cameras: ${cameraError.message}`);
  }

  if (!cameras || cameras.length === 0) {
    return [];
  }

  const { data: intersections } = await supabase
    .from("intersections")
    .select("id, intersectionId, name");
  const intersectionIdMap = new Map(
    (intersections ?? []).map((i) => [i.id, i.intersectionId])
  );
  const intersectionNameMap = new Map(
    (intersections ?? []).map((i) => [i.id, i.name])
  );

  const approachIds = [
    ...new Set(
      cameras
        .map((camera) => camera.approachId)
        .filter((id): id is number => id !== null)
    ),
  ];

  const { data: approaches, error: approachError } =
    approachIds.length > 0
      ? await supabase
          .from("approaches")
          .select("id, approach")
          .in("id", approachIds)
      : { data: [], error: null };

  if (approachError) {
    throw new Error(`Gagal mengambil approaches: ${approachError.message}`);
  }

  const approachById = new Map(
    (approaches ?? []).map((a) => [a.id, a.approach])
  );

  const cameraIds = cameras.map((camera) => camera.id);

  const { data: videos, error: videoError } = await supabase
    .from("cameraVideos")
    .select("cameraId, fileUrl, videoName, uploadedAt")
    .in("cameraId", cameraIds)
    .order("uploadedAt", { ascending: false });

  if (videoError) {
    throw new Error(`Gagal mengambil camera videos: ${videoError.message}`);
  }

  const latestVideoByCamera = new Map<
    number,
    { fileUrl: string | null; videoName: string | null }
  >();

  for (const video of videos ?? []) {
    if (!latestVideoByCamera.has(video.cameraId)) {
      latestVideoByCamera.set(video.cameraId, {
        fileUrl: video.fileUrl,
        videoName: video.videoName,
      });
    }
  }

  return cameras.map((camera) => {
    const video = latestVideoByCamera.get(camera.id);

    return {
      id: camera.id,
      cameraId: camera.cameraId,
      name: camera.name,
      approach: camera.approachId
        ? approachById.get(camera.approachId) ?? null
        : null,
      intersectionId: camera.intersectionId
        ? intersectionIdMap.get(camera.intersectionId) ?? null
        : null,
      intersectionName: camera.intersectionId
        ? intersectionNameMap.get(camera.intersectionId) ?? null
        : null,
      sourceType: camera.sourceType,
      sourceUrl: camera.sourceUrl,
      status: camera.status,
      videoUrl: video?.fileUrl ?? camera.sourceUrl ?? null,
      videoName: video?.videoName ?? null,
    };
  });
}
