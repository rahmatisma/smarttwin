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
  Approach,
  TrafficState,
  SignalStatus,
  Recommendation,
  ForecastResponse,
} from "@/types/traffic";

export const DEFAULT_INTERSECTION_ID = "simpang4-pingit";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const FORECAST_ZONE_CAPACITY = 33;
const FORECAST_REFRESH_INTERVAL_MS = 15_000;
const FORECAST_FAILURE_COOLDOWN_MS = 60_000;

let forecastCache: ForecastResponse | null = null;
let forecastCacheTime = 0;
let forecastRequestInFlight: Promise<ForecastResponse | null> | null = null;
let forecastRetryAfter = 0;
let signalStatusCache: SignalStatus | null = null;
let signalStatusRequestInFlight: Promise<SignalStatus | null> | null = null;
let recommendationCache: Recommendation | null = null;
let recommendationRequestInFlight: Promise<Recommendation | null> | null = null;
const intersectionRowIdCache = new Map<string, number | null>();
const intersectionRowIdRequests = new Map<string, Promise<number | null>>();

/* =========================================================
 * INTERSECTION LOOKUP
 * ========================================================= */

async function getIntersectionRowId(
  intersectionId: string
): Promise<number | null> {
  if (intersectionRowIdCache.has(intersectionId)) {
    return intersectionRowIdCache.get(intersectionId) ?? null;
  }

  const activeRequest = intersectionRowIdRequests.get(intersectionId);
  if (activeRequest) return activeRequest;

  const request = (async () => {
    const { data, error } = await supabase
      .from("intersections")
      .select("id")
      .eq("intersectionId", intersectionId)
      .order("id", { ascending: true })
      .limit(1)
      .maybeSingle();

    if (error) {
      // Gangguan Supabase sesaat tidak boleh menjatuhkan seluruh dashboard.
      // Nilai yang pernah berhasil dibaca tetap dapat dipakai saat reconnect.
      console.warn(`Gagal mengambil intersection ${intersectionId}: ${error.message}`);
      return intersectionRowIdCache.get(intersectionId) ?? null;
    }

    const rowId = data?.id ?? null;
    intersectionRowIdCache.set(intersectionId, rowId);
    return rowId;
  })().finally(() => {
    intersectionRowIdRequests.delete(intersectionId);
  });

  intersectionRowIdRequests.set(intersectionId, request);
  return request;
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
  if (intersectionId !== DEFAULT_INTERSECTION_ID) return null;
  if (signalStatusRequestInFlight) return signalStatusRequestInFlight;

  signalStatusRequestInFlight = fetch(`${API_BASE_URL}/signal/status`)
    .then(async (response) => {
      if (!response.ok) return signalStatusCache;
      signalStatusCache = (await response.json()) as SignalStatus;
      return signalStatusCache;
    })
    .catch(() => signalStatusCache)
    .finally(() => {
      signalStatusRequestInFlight = null;
    });

  return signalStatusRequestInFlight;
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
  if (intersectionId !== DEFAULT_INTERSECTION_ID) return null;
  if (recommendationRequestInFlight) return recommendationRequestInFlight;

  recommendationRequestInFlight = fetch(`${API_BASE_URL}/recommendation`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ intersectionId }),
  })
    .then(async (response) => {
      if (!response.ok) return recommendationCache;

      const body = await response.json();
      if (!body.success || !body.recommendation) return recommendationCache;

      recommendationCache = body.recommendation as Recommendation;
      return recommendationCache;
    })
    .catch(() => recommendationCache)
    .finally(() => {
      recommendationRequestInFlight = null;
    });

  return recommendationRequestInFlight;
}

/* =========================================================
 * FORECAST
 * ========================================================= */

async function requestForecast(
  intersectionId: string = DEFAULT_INTERSECTION_ID
): Promise<ForecastResponse | null> {
  // Saat ini hanya simpang Pingit yang mempunyai TrafficState nyata.
  // Tiga ID lain tetap ada untuk konfigurasi kamera lama, tetapi jangan
  // dipanggil ke endpoint forecast karena backend memang akan menjawab 404.
  if (intersectionId !== DEFAULT_INTERSECTION_ID) return null;

  type TrafficHistoryRow = {
    trafficState: { windowStart: string; windowEnd: string };
    approaches: Array<{
      approach: Approach;
      volume: number;
      queueLengthVeh: number;
      queueLengthMEst: number;
      densityIndex: number;
    }>;
  };

  type ApproachForecast = {
    timestamp: string;
    approaches: Array<{
      approach: Approach;
      vehicleCount: number;
      queueLengthVeh: number;
      queueLengthMEst: number;
      densityIndex: number;
    }>;
  };

  type ApproachForecastResponse = {
    model?: { name?: string };
    approachForecasts?: ApproachForecast[];
    forecastSource?: string;
    fallbackUsed?: boolean;
  };

  // Endpoint LSTM memerlukan 12 TrafficState lengkap sebagai input.
  const historyResponse = await fetch(
    `${API_BASE_URL}/api/v1/traffic/${encodeURIComponent(intersectionId)}?limit=12`
  );

  // Intersection yang belum memiliki data tidak boleh menggagalkan panel lain.
  if (!historyResponse.ok) {
    forecastRetryAfter = Date.now() + FORECAST_FAILURE_COOLDOWN_MS;
    return null;
  }

  const historyBody = (await historyResponse.json()) as {
    data?: TrafficHistoryRow[];
  };
  const history = [...(historyBody.data ?? [])]
    .sort(
      (a, b) =>
        new Date(a.trafficState.windowStart).getTime() -
        new Date(b.trafficState.windowStart).getTime()
    )
    .slice(-12);

  if (history.length < 12) return null;

  const forecastResponse = await fetch(`${API_BASE_URL}/api/forecast/approaches`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      records: history.map(({ trafficState, approaches }) => ({
        timestamp: trafficState.windowEnd,
        approaches: approaches.map((approach) => ({
          approach: approach.approach,
          vehicleCount: approach.volume,
          queueLengthVeh: approach.queueLengthVeh,
          queueLengthMEst: approach.queueLengthMEst,
          // Nilai TrafficState adalah okupansi zona (0..33), sedangkan
          // kontrak input model memakai nilai ternormalisasi 0..1.
          densityIndex: Math.min(
            1,
            Math.max(0, approach.densityIndex / FORECAST_ZONE_CAPACITY)
          ),
        })),
      })),
    }),
  });

  if (!forecastResponse.ok) return null;

  const result = (await forecastResponse.json()) as ApproachForecastResponse;
  const rows = result.approachForecasts ?? [];
  if (rows.length === 0) return null;

  const toPrediction = (
    timestamp: string,
    approaches: ApproachForecast["approaches"]
  ) => ({
    timestamp,
    predictedVehicleCount: approaches.reduce((sum, item) => sum + item.vehicleCount, 0),
    predictedQueueLengthVeh: approaches.reduce((sum, item) => sum + item.queueLengthVeh, 0),
    predictedQueueLengthMEst: approaches.reduce((sum, item) => sum + item.queueLengthMEst, 0),
    predictedDensityIndex:
      approaches.reduce((sum, item) => sum + item.densityIndex, 0) /
      Math.max(approaches.length, 1),
    predictedSpeedKmh: null,
  });

  const approachNames: Approach[] = ["north", "south", "east", "west"];
  const predictionsByApproach = Object.fromEntries(
    approachNames.map((approach) => [
      approach,
      rows.map((row) =>
        toPrediction(
          row.timestamp,
          row.approaches.filter((item) => item.approach === approach)
        )
      ),
    ])
  ) as Record<Approach, ForecastResponse["predictions"]>;

  return {
    intersectionId,
    horizonMinutes: 1,
    model: result.model?.name ?? "Traffic LSTM",
    predictions: rows.map((row) => toPrediction(row.timestamp, row.approaches)),
    predictionsByApproach,
    forecastSource: result.forecastSource,
    fallbackUsed: result.fallbackUsed,
  };
}

export async function fetchForecast(
  intersectionId: string = DEFAULT_INTERSECTION_ID
): Promise<ForecastResponse | null> {
  if (intersectionId !== DEFAULT_INTERSECTION_ID) return null;
  if (Date.now() < forecastRetryAfter) return forecastCache;

  // Forecast memiliki horizon 60 detik. Tidak perlu menembak dua endpoint
  // backend pada setiap poll dashboard 5 detik atau event WebSocket.
  if (
    forecastCache &&
    Date.now() - forecastCacheTime < FORECAST_REFRESH_INTERVAL_MS
  ) {
    return forecastCache;
  }

  // Initial load, poll, dan WebSocket dapat terjadi bersamaan. Semua pemanggil
  // menunggu request yang sama agar koneksi Supabase tidak dibanjiri.
  if (forecastRequestInFlight) return forecastRequestInFlight;

  forecastRequestInFlight = requestForecast(intersectionId)
    .then((forecast) => {
      if (forecast) {
        forecastCache = forecast;
        forecastCacheTime = Date.now();
      }
      return forecast ?? forecastCache;
    })
    .catch(() => {
      // Gangguan backend/Supabase sesaat adalah kondisi fallback, bukan error
      // dashboard. Pertahankan hasil terakhir dan jangan reject Promise.all.
      return forecastCache;
    })
    .finally(() => {
      forecastRequestInFlight = null;
    });

  return forecastRequestInFlight;
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

/* =========================================================
 * DIGITAL TWIN SCENARIOS
 * ========================================================= */

export interface DigitalTwinPhase {
  approach: "north" | "east" | "south" | "west";
  greenSeconds: number;
  yellowSeconds: number;
  redSeconds: number;
  demandScore: number;
}

export interface DigitalTwinCandidate {
  candidateId: "baseline" | "aggressive" | "balanced";
  phases: DigitalTwinPhase[];
  cycleLengthSeconds: number;
  totalCycleSeconds: number;
  busiestApproach: string | null;
  avgDelaySeconds: number;
  avgQueueLengthM: number;
  queueLengthVeh: number;
  throughputVeh: number;
  los: "A" | "B" | "C" | "D" | "E" | "F";
  isWinner: boolean;
}

export interface DigitalTwinScenarioResponse {
  intersectionId: string;
  status: "completed" | "unavailable";
  updatedAt: string | null;
  winnerId: "baseline" | "aggressive" | "balanced" | null;
  candidates: DigitalTwinCandidate[];
  message: string | null;
}

export async function fetchDigitalTwinScenarios(
  intersectionId: string = DEFAULT_INTERSECTION_ID
): Promise<DigitalTwinScenarioResponse | null> {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/v1/digital-twin/scenarios/latest?intersectionId=${encodeURIComponent(
        intersectionId
      )}`
    );
    if (!response.ok) return null;
    return await response.json();
  } catch (err) {
    console.error("Failed to fetch scenarios:", err);
    return null;
  }
}

