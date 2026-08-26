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

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

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

  // Dulu di sini ada bypass yang baca langsung dari CSV via backend
  // (GET /api/v1/traffic/live-csv), yang mencocokkan baris CSV ke
  // posisi <video>.currentTime -- jadi angkanya berubah mengikuti
  // video yang sedang diputar. Sekarang datanya diisi ke Supabase
  // lewat run_ingest.py, tapi perilaku "ikut posisi video" itu tetap
  // dipertahankan, cuma sumbernya diganti ke database.
  //
  // 1. Cari batch ingest PALING BARU (createdAt) -- run_ingest.py
  //    menulis ratusan baris sekaligus dengan createdAt yang identik
  //    (satu bulk upsert), jadi createdAt ini menandai "batch mana
  //    yang sedang aktif ditonton", bukan sekadar satu baris.
  const { data: latest, error: latestError } = await supabase
    .from("trafficStates")
    .select("createdAt")
    .eq("intersectionId", rowId)
    .order("createdAt", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (latestError) {
    throw new Error(`Gagal mengambil traffic state: ${latestError.message}`);
  }

  if (!latest) {
    return null;
  }

  let state: { id: number; windowStart: string; windowEnd: string } | null =
    null;

  if (videoTime !== undefined) {
    // 2. Cari window PERTAMA batch ini -- jadi acuan "detik ke-0"
    //    video, sama seperti frame_number=0 di CSV lama.
    const { data: origin, error: originError } = await supabase
      .from("trafficStates")
      .select("windowStart")
      .eq("intersectionId", rowId)
      .eq("createdAt", latest.createdAt)
      .order("windowStart", { ascending: true })
      .limit(1)
      .maybeSingle();

    if (originError) {
      throw new Error(
        `Gagal mengambil awal batch traffic state: ${originError.message}`
      );
    }

    if (origin) {
      // 3. Jam target = jam mulai batch + posisi video sekarang.
      //    Ambil window yang MELIPUTI jam itu (windowStart <= target,
      //    diurutkan descending supaya yang paling dekat menang).
      //    Kalau video sudah lewat durasi data yang ada, ini otomatis
      //    jatuh ke window TERAKHIR batch (graceful, tidak error).
      const targetTime = new Date(
        new Date(origin.windowStart).getTime() + videoTime * 1000
      ).toISOString();

      const { data: matched, error: matchedError } = await supabase
        .from("trafficStates")
        .select("id, windowStart, windowEnd")
        .eq("intersectionId", rowId)
        .eq("createdAt", latest.createdAt)
        .lte("windowStart", targetTime)
        .order("windowStart", { ascending: false })
        .limit(1)
        .maybeSingle();

      if (matchedError) {
        throw new Error(
          `Gagal mencocokkan traffic state ke posisi video: ${matchedError.message}`
        );
      }

      state = matched;
    }
  }

  if (!state) {
    // Tidak ada videoTime (pemanggil tidak sedang menonton video
    // tertentu), atau batch-nya kosong -- jatuh balik ke window
    // TERAKHIR batch paling baru.
    const { data: fallback, error: fallbackError } = await supabase
      .from("trafficStates")
      .select("id, windowStart, windowEnd")
      .eq("intersectionId", rowId)
      .eq("createdAt", latest.createdAt)
      .order("windowEnd", { ascending: false })
      .limit(1)
      .maybeSingle();

    if (fallbackError) {
      throw new Error(`Gagal mengambil traffic state: ${fallbackError.message}`);
    }

    state = fallback;
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
 *
 * Sengaja BUKAN baca tabel `signalStatuses` Supabase langsung --
 * tabel itu cuma diisi tabel beku dari batch lama, tidak pernah
 * diperbarui (pola sama seperti masalah lama fetchRecommendation()).
 * GET /signal/status baca SignalService yang "hidup" -- lengan aktif
 * & sisa waktunya benar-benar berputar/berjalan di server. Endpoint
 * ini cuma untuk simpang4-pingit (satu-satunya intersection nyata),
 * jadi intersectionId di sini tidak dikirim ke backend, cuma buat
 * konsistensi signature dengan fetch* lain.
 * ========================================================= */

export async function fetchSignalStatus(
  intersectionId: string = DEFAULT_INTERSECTION_ID
): Promise<SignalStatus | null> {
  void intersectionId;

  const response = await fetch(`${API_BASE_URL}/signal/status`);

  if (!response.ok) {
    throw new Error(`Gagal mengambil signal status: ${response.status}`);
  }

  return (await response.json()) as SignalStatus;
}

/* =========================================================
 * RECOMMENDATION
 *
 * Sengaja BUKAN baca tabel `recommendations` Supabase langsung.
 * Tabel itu diisi lewat decision_engine/run_decision.py + feed_to_supabase.py,
 * skrip batch offline yang harus dijalankan manual dan gampang basi.
 *
 * POST /recommendation baca TrafficState Supabase yang sama (live,
 * diisi terus oleh ingest CV) lalu jalankan RuleBasedEngine saat itu
 * juga -- jadi selalu segar, termasuk queueLengthVeh/queueLengthMEst
 * asli, tanpa perlu proses batch terpisah. Lihat RecommendationService
 * di backend/app/services/recommendation_service.py.
 * ========================================================= */

export async function fetchRecommendation(
  intersectionId: string = DEFAULT_INTERSECTION_ID
): Promise<Recommendation | null> {
  const response = await fetch(`${API_BASE_URL}/recommendation`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ intersectionId }),
  });

  if (!response.ok) {
    throw new Error(
      `Gagal mengambil recommendation: ${response.status}`
    );
  }

  const body = await response.json();

  if (!body.success || !body.recommendation) {
    return null;
  }

  return body.recommendation as Recommendation;
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
