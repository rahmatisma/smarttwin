"use client";

import {
  Bike,
  Car,
  Bus,
  Truck,
  Video,
  VideoOff,
  X,
} from "lucide-react";

import {
  useEffect,
  useCallback,
  useMemo,
  useRef,
  useState,
} from "react";

import type {
  VehicleClassCount,
  VehicleClass,
} from "@/types/traffic";

import {
  fetchCameras,
} from "@/lib/supabaseData";
import {
  ALL_INTERSECTIONS,
  APPROACH_OPTIONS,
  type ApproachSelection,
} from "@/lib/intersections";

// =====================================================
// TYPES
// =====================================================

type CameraStatus = {
  id: string;
  label: string;
  online: boolean;
};

type SourceType =
  | "file"
  | "url"
  | "rtsp";

// Timeline bersama bertahan saat panel unmount/navigasi dalam tab yang sama.
const CAMERA_TIMELINE_KEY = "smarttwin.camera-timeline";

type CameraTimeline = {
  time: number;
  paused: boolean;
  updatedAt: number;
  backendInstanceId: string | null;
};

const emptyTimeline = (backendInstanceId: string | null = null): CameraTimeline => ({
  time: 0,
  paused: false,
  updatedAt: Date.now(),
  backendInstanceId,
});

function readPersistedTimeline(): CameraTimeline {
  if (typeof window === "undefined") return emptyTimeline();
  try {
    const value = JSON.parse(sessionStorage.getItem(CAMERA_TIMELINE_KEY) ?? "null");
    return {
      time: Number.isFinite(value?.time) && value.time >= 0 ? value.time : 0,
      paused: typeof value?.paused === "boolean" ? value.paused : false,
      updatedAt: Number.isFinite(value?.updatedAt) ? value.updatedAt : Date.now(),
      backendInstanceId:
        typeof value?.backendInstanceId === "string" ? value.backendInstanceId : null,
    };
  } catch {
    return emptyTimeline();
  }
}

function persistTimeline(
  time: number,
  paused: boolean,
  updatedAt = Date.now(),
  backendInstanceId: string | null = null
) {
  if (typeof window === "undefined" || !Number.isFinite(time)) return;
  sessionStorage.setItem(CAMERA_TIMELINE_KEY, JSON.stringify({
    time,
    paused,
    updatedAt,
    backendInstanceId,
  }));
}

function currentTimelineTime(timeline: CameraTimeline) {
  if (timeline.paused) return timeline.time;
  return timeline.time + Math.max(0, Date.now() - timeline.updatedAt) / 1000;
}

function anchorTimeline(timeline: CameraTimeline, time: number) {
  timeline.time = time;
  timeline.updatedAt = Date.now();
}

type Camera = {
  id: string;
  name: string;
  intersection: string;
  direction: string;
  sourceType: SourceType;
  source: string;
  fileName?: string;
  status: "online" | "waiting";
};

// Toast lokal panel ini SENGAJA terpisah dari sistem notifikasi backend
// (useNotifications/GlobalNotifications) -- itu untuk notifikasi persisten
// (histori, tanda dibaca). Kamera offline/online itu kejadian sesaat murni
// UI, tidak perlu tersimpan/ter-poll dari backend.
type CameraAlert = {
  id: string;
  text: string;
  tone: "offline" | "online";
};

const CAMERA_ALERT_TTL_MS = 5000;

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

function resolveVideoSrc(source: string): string {
  if (source.startsWith("/api/")) {
    return `${API_BASE_URL}${source}`;
  }

  return source;
}

// =====================================================
// ICONS
// =====================================================

const ICONS: Record<
  VehicleClass,
  React.ReactNode
> = {
  motorcycle: (
    <Bike className="h-3.5 w-3.5" />
  ),

  car: (
    <Car className="h-3.5 w-3.5" />
  ),

  bus: (
    <Bus className="h-3.5 w-3.5" />
  ),

  truck: (
    <Truck className="h-3.5 w-3.5" />
  ),
};

// =====================================================
// LABELS
// =====================================================

const LABELS: Record<
  VehicleClass,
  string
> = {
  motorcycle: "Motorcycle",
  car: "Car",
  bus: "Bus",
  truck: "Truck",
};

// =====================================================
// LOAD CCTV DARI SUPABASE
// =====================================================

async function loadCamerasForIntersection(
  intersectionDbId: string
): Promise<Camera[]> {
  try {
    const rows = await fetchCameras(intersectionDbId);

    return rows.map((row) => ({
      id: String(row.id),
      name: row.name,
      intersection: intersectionDbId,
      direction: row.approach ?? "Tidak diketahui",
      sourceType:
        row.sourceType === "uploaded" ? "file" : "url",
      source: row.videoUrl ?? "",
      fileName: row.videoName ?? undefined,
      status: row.status === "active" ? "online" : "waiting",
    }));
  } catch (error) {
    console.error(
      `Gagal mengambil cameras dari Supabase untuk ${intersectionDbId}:`,
      error
    );

    return [];
  }
}

// =====================================================
// COMPONENT
// =====================================================

export default function CameraFeedPanel({
  counts,
  selectedApproach = "all",
  onApproachChange,
  onTimeUpdate,
  onOfflineApproachesChange,
}: {
  counts: VehicleClassCount[];
  cameraStatus?: CameraStatus[];
  selectedApproach?: ApproachSelection;
  onApproachChange?: (selection: ApproachSelection) => void;
  onTimeUpdate?: (time: number, duration?: number) => void;
  // Dipanggil setiap kali daftar lengan yang "CCTV mati" (simulasi manual)
  // berubah -- dipakai page.tsx buat mengosongkan panel "Vehicle Detection"
  // untuk lengan itu (Step 4, rencana-fallback-cctv-per-lengan.md).
  onOfflineApproachesChange?: (approaches: Set<string>) => void;
}) {

  // ===================================================
  // CAMERA STATE
  // ===================================================

  const [cameras, setCameras] =
    useState<Camera[]>([]);
  // Kamera yang di-pause MANUAL oleh user (simulasi CCTV berhenti/mati),
  // bukan pause yang dipicu syncVideos() sendiri. Kamera di sini
  // dikeluarkan sementara dari paksaan sinkron -- lihat syncVideos() dan
  // getMasterCameraId() di bawah.
  const [offlineCameraIds, setOfflineCameraIds] =
    useState<Set<string>>(new Set());
  const [cameraAlerts, setCameraAlerts] =
    useState<CameraAlert[]>([]);
  const cameraAlertTimers = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  const videoRefs = useRef(new Map<string, HTMLVideoElement>());
  const timelineRef = useRef<CameraTimeline>({
    time: 0,
    paused: false,
    updatedAt: 0,
    backendInstanceId: null,
  });
  const timelineRestoredRef = useRef(false);

  // Filter approach itu SEKARANG murni soal LAYOUT (kamera mana yang
  // dibesarkan), BUKAN soal mount/unmount atau sembunyi-sembunyian lewat
  // CSS. SEMUA kamera SELALU dimount, dirender, dan main normal --
  // sama seperti mode "Semua Lengan" yang sudah terbukti stabil -- kalau
  // salah satu approach dipilih, cuma tata letaknya yang berubah (satu
  // kartu dibesarkan, 3 lainnya jadi strip kecil di samping), tetap
  // sama-sama tampil & tetap ikut mekanisme jam bersama/offline-tracking
  // yang sama persis.
  //
  // Percobaan sebelumnya (unmount 3 kamera non-visible / sembunyikan lewat
  // display:none / render di wrapper off-screen terpisah) semuanya berakhir
  // dengan video play/pause bolak-balik terus-menerus (10 Sept 2026) --
  // ternyata akar masalahnya BUKAN soal cara menyembunyikan elemennya,
  // tapi soal MENYEMBUNYIKAN SAMA SEKALI itu sendiri yang berisiko.
  // Solusinya: jangan pernah sembunyikan/unmount video kamera manapun --
  // cukup ubah UKURAN & POSISI kartunya lewat CSS.
  const focusedCamera =
    selectedApproach !== "all"
      ? cameras.find((camera) => camera.direction === selectedApproach)
      : undefined;

  const getSharedTimelineTime = useCallback(() => {
    return currentTimelineTime(timelineRef.current);
  }, []);

  const dismissCameraAlert = useCallback((id: string) => {
    const timer = cameraAlertTimers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      cameraAlertTimers.current.delete(id);
    }
    setCameraAlerts((prev) => prev.filter((alert) => alert.id !== id));
  }, []);

  const pushCameraAlert = useCallback((text: string, tone: CameraAlert["tone"]) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    // Maksimal 3 toast sekaligus supaya tidak menumpuk kalau user pause 4
    // kamera cepat-cepat -- sama seperti pola stack di GlobalNotifications.
    setCameraAlerts((prev) => [...prev, { id, text, tone }].slice(-3));
    const timer = setTimeout(() => dismissCameraAlert(id), CAMERA_ALERT_TTL_MS);
    cameraAlertTimers.current.set(id, timer);
  }, [dismissCameraAlert]);

  useEffect(() => {
    const timers = cameraAlertTimers.current;
    return () => {
      timers.forEach((timer) => clearTimeout(timer));
      timers.clear();
    };
  }, []);

  // Kamera acuan -- SEKARANG cuma dipakai untuk melaporkan "durasi acuan"
  // (masterDuration) ke onTimeUpdate/backend, BUKAN lagi untuk menentukan
  // waktu jam bersama. Lihat catatan panjang di syncVideos() soal kenapa
  // membaca currentTime video manapun sebagai sumber jam itu berbahaya.
  const getMasterCameraId = useCallback(() => {
    const liveCamera = cameras.find(
      (camera) => !offlineCameraIds.has(camera.id)
    );
    return (liveCamera ?? cameras[0])?.id;
  }, [cameras, offlineCameraIds]);

  // Cuma MELAPORKAN posisi jam bersama (buat onTimeUpdate -> progress bar +
  // POST /sync-clock ke backend) -- SAMA SEKALI TIDAK menyentuh currentTime
  // atau play/pause video manapun. Aman dipanggil sesering apapun (tiap
  // 700ms lewat heartbeat, tiap native timeupdate), karena tidak melakukan
  // apa pun ke elemen <video>.
  const reportSharedTime = useCallback(() => {
    const masterCameraId = getMasterCameraId();
    const masterVideo = masterCameraId ? videoRefs.current.get(masterCameraId) : undefined;
    const masterDuration =
      masterVideo && Number.isFinite(masterVideo.duration) && masterVideo.duration > 0
        ? masterVideo.duration
        : undefined;
    const targetTime = Math.max(0, getSharedTimelineTime());
    onTimeUpdate?.(targetTime, masterDuration);
  }, [getMasterCameraId, getSharedTimelineTime, onTimeUpdate]);

  // Memaksa posisi & play/pause SEMUA video ke jam bersama -- BEDA dari
  // reportSharedTime(), ini BENERAN menyentuh currentTime/play/pause video.
  //
  // SENGAJA cuma dipanggil di momen-momen diskret (mount/restore, video
  // baru selesai load metadata, kamera baru resume dari offline) -- BUKAN
  // di loop berulang (heartbeat/timeupdate). Sebelumnya dipanggil terus-
  // menerus tiap 700ms DAN tiap native timeupdate; video-video ini file
  // besar yang di-stream (preload="auto"), jadi seek ke posisi yang belum
  // ke-buffer butuh waktu. Kalau target terus berubah sebelum seek
  // sebelumnya sempat selesai, video tidak pernah "mendarat" -- selalu
  // dikejar target baru, terlihat sebagai stutter/play-pause berulang
  // terus-menerus (bug ditemukan 10 Sept 2026, SAMA SEKALI tidak terkait
  // hide/show kamera seperti yang tadinya dikira). Video yang sudah main
  // normal TIDAK PERLU dipaksa-paksa terus -- playback native browser
  // sudah cukup akurat sendiri; paksaan cuma dibutuhkan di titik
  // transisi (baru resume / baru dimuat), persis sesuai Step 1 & 2 di
  // rencana-fallback-cctv-per-lengan.md.
  const syncVideos = useCallback(() => {
    const masterCameraId = getMasterCameraId();
    const masterVideo = masterCameraId ? videoRefs.current.get(masterCameraId) : undefined;

    // Durasi acuan HANYA dipakai untuk pelaporan (onTimeUpdate/backend),
    // TIDAK untuk menentukan posisi kamera manapun.
    const masterDuration =
      masterVideo && Number.isFinite(masterVideo.duration) && masterVideo.duration > 0
        ? masterVideo.duration
        : undefined;

    // Cari currentTime PALING BESAR di antara kamera yang masih hidup --
    // itu bukti paling akurat untuk instan dunia nyata sekarang, jauh
    // lebih dipercaya daripada tebakan wall-clock (getSharedTimelineTime())
    // yang bisa basi/drift. Wall-clock cuma dipakai kalau BENAR-BENAR
    // belum ada satupun video hidup yang siap (mis. baru pertama mount).
    //
    // Diambil yang PALING BESAR (bukan sekadar "kamera hidup pertama")
    // supaya kalau kebetulan ada kamera berdurasi lebih pendek yang sudah
    // sempat loop balik ke angka kecil, dia tidak salah kepilih jadi
    // acuan dan menarik kamera lain ikut mundur -- itu justru bug yang
    // sempat terjadi sebelumnya waktu fungsi ini masih murni wall-clock:
    // begitu terpicu tanpa sengaja (mis. efek samping event durationchange
    // saat kamera lain baru di-seek), dia menarik SEMUA kamera termasuk
    // yang online dari awal ke tebakan yang basi (bug "kamera online malah
    // ikut mundur", ditemukan 10 Sept 2026).
    let liveReferenceTime: number | undefined;
    for (const liveCamera of cameras) {
      if (offlineCameraIds.has(liveCamera.id)) continue;
      const liveVideo = videoRefs.current.get(liveCamera.id);
      if (liveVideo && Number.isFinite(liveVideo.currentTime)) {
        liveReferenceTime =
          liveReferenceTime === undefined
            ? liveVideo.currentTime
            : Math.max(liveReferenceTime, liveVideo.currentTime);
      }
    }

    const targetTime = liveReferenceTime ?? Math.max(0, getSharedTimelineTime());
    anchorTimeline(timelineRef.current, targetTime);
    persistTimeline(
      targetTime,
      timelineRef.current.paused,
      timelineRef.current.updatedAt,
      timelineRef.current.backendInstanceId
    );

    for (const camera of cameras) {
      // Kamera yang lagi ditandai offline (di-toggle manual lewat tombol,
      // simulasi CCTV mati) SENGAJA dilewati -- dia tidak boleh dipaksa
      // ikut jam acuan selama masih offline. Lihat catatan getMasterCameraId()
      // di atas.
      if (offlineCameraIds.has(camera.id)) continue;

      const video = videoRefs.current.get(camera.id);
      if (!video || !Number.isFinite(video.duration) || video.duration <= 0) continue;

      // Modulo durasi video INI SENDIRI, bukan cuma di-clamp ke ujung --
      // kamera yang file videonya lebih pendek dari kamera lain (durasi
      // tiap kamera bisa beda) harus looping dari 0 lagi, bukan macet
      // mepet di 0.05 detik sebelum akhir.
      const wrappedTarget = targetTime % video.duration;

      if (Math.abs(video.currentTime - wrappedTarget) > 0.35) {
        video.currentTime = Math.min(wrappedTarget, Math.max(0, video.duration - 0.05));
      }
      if (timelineRef.current.paused) {
        if (!video.paused) video.pause();
      } else if (video.paused) {
        void video.play().catch(() => undefined);
      }
    }

    onTimeUpdate?.(targetTime, masterDuration);
  }, [cameras, getMasterCameraId, getSharedTimelineTime, offlineCameraIds, onTimeUpdate]);

  // Simulasi "CCTV mati" -- SATU-SATUNYA cara kamera ditandai offline
  // sekarang, lewat tombol eksplisit di kartu (lihat renderCameraTile()).
  // SENGAJA tidak lagi bereaksi ke event pause/play native browser --
  // itu ambigu (bisa dari klik user, buffering, video tamat sendiri, dll)
  // dan itu akar SEMUA bug play-pause berulang/loncat-meleset yang
  // dikejar berjam-jam 10 Sept 2026. Sekarang KITA yang memutuskan kapan
  // video benar-benar di-pause/dimainkan lagi, bukan bereaksi ke browser.
  function toggleCameraOffline(camera: Camera) {
    const video = videoRefs.current.get(camera.id);
    const wasOffline = offlineCameraIds.has(camera.id);

    if (wasOffline) {
      // BALIK ONLINE -- loncat ke posisi kamera lain yang masih hidup &
      // tidak pernah disentuh (bukti paling akurat instan dunia nyata
      // yang sama, lihat jam yang kebakar di gambar CCTV), baru mainkan.
      pushCameraAlert(
        `CCTV ${camera.name} (${camera.direction}) online lagi.`,
        "online"
      );

      const referenceCamera = cameras.find(
        (other) => other.id !== camera.id && !offlineCameraIds.has(other.id)
      );
      const referenceVideo = referenceCamera
        ? videoRefs.current.get(referenceCamera.id)
        : undefined;

      if (video) {
        const duration = video.duration;
        const target =
          referenceVideo &&
          Number.isFinite(referenceVideo.currentTime) &&
          Number.isFinite(duration) &&
          duration > 0
            ? referenceVideo.currentTime % duration
            : undefined;

        if (target !== undefined) {
          // Tunggu event 'seeked' BENERAN selesai sebelum play() -- kalau
          // currentTime & play() dipanggil bersamaan/terlalu cepat, video
          // besar yang di-stream ini bisa keburu main dari posisi LAMA
          // (sebelum loncatnya kelar) alih-alih posisi baru. Diduga ini
          // penyebab bug "malah mundur ke posisi lama" (10 Sept 2026).
          let settled = false;
          const playOnce = () => {
            if (settled) return;
            settled = true;
            video.removeEventListener("seeked", playOnce);
            void video.play().catch(() => undefined);
          };
          video.addEventListener("seeked", playOnce);
          video.currentTime = target;
          // Guard: kalau 'seeked' entah kenapa tidak pernah datang (jarang,
          // tapi bisa kejadian), tetap coba main setelah jeda singkat --
          // jangan sampai kamera ini macet selamanya diam padahal statusnya
          // sudah "online".
          window.setTimeout(playOnce, 1500);
        } else {
          void video.play().catch(() => undefined);
        }
      }

      setOfflineCameraIds((prev) => {
        const next = new Set(prev);
        next.delete(camera.id);
        return next;
      });

      timelineRef.current.paused = false;
      anchorTimeline(timelineRef.current, timelineRef.current.time);
      persistTimeline(
        timelineRef.current.time,
        false,
        timelineRef.current.updatedAt,
        timelineRef.current.backendInstanceId
      );
    } else {
      // MATIKAN -- kamera lain SENGAJA tidak disentuh sama sekali, tetap
      // main apa adanya.
      pushCameraAlert(
        `CCTV ${camera.name} (${camera.direction}) berhenti -- data lengan ini kosong sementara.`,
        "offline"
      );

      if (video && !video.paused) video.pause();

      setOfflineCameraIds((prev) => {
        const next = new Set(prev);
        next.add(camera.id);

        if (next.size >= cameras.length) {
          timelineRef.current.paused = true;
          anchorTimeline(timelineRef.current, timelineRef.current.time);
          persistTimeline(
            timelineRef.current.time,
            true,
            timelineRef.current.updatedAt,
            timelineRef.current.backendInstanceId
          );
        }

        return next;
      });
    }
  }

  // Laporkan lengan (approach) mana yang lagi "CCTV mati" ke parent
  // (page.tsx) -- Step 4: dipakai buat mengosongkan panel "Vehicle
  // Detection" untuk lengan itu. Dikonversi dari id kamera ke nama
  // approach di sini karena page.tsx cuma kenal approach, bukan id kamera.
  useEffect(() => {
    if (!onOfflineApproachesChange) return;
    const approaches = new Set(
      cameras
        .filter((camera) => offlineCameraIds.has(camera.id))
        .map((camera) => camera.direction)
    );
    onOfflineApproachesChange(approaches);
  }, [cameras, offlineCameraIds, onOfflineApproachesChange]);

  useEffect(() => {
    let cancelled = false;

    async function restoreTimeline() {
      const persisted = readPersistedTimeline();
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/simulation/state?context=dashboard`, {
          cache: "no-store",
        });
        if (!response.ok) throw new Error("Backend tidak tersedia");
        const state = await response.json();
        if (cancelled) return;
        const instanceId =
          typeof state.backendInstanceId === "string" ? state.backendInstanceId : null;
        const sameBackend =
          instanceId !== null && persisted.backendInstanceId === instanceId;
        timelineRef.current = sameBackend ? persisted : emptyTimeline(instanceId);
        if (state.running && Number.isFinite(state.simulationTimeSeconds)) {
          anchorTimeline(timelineRef.current, state.simulationTimeSeconds);
          timelineRef.current.paused = Boolean(state.paused);
        }
      } catch {
        // Pertahankan posisi sampai backend mengonfirmasi instance baru.
        if (cancelled) return;
        timelineRef.current = persisted;
      }

      if (cancelled) return;
      persistTimeline(
        timelineRef.current.time,
        timelineRef.current.paused,
        timelineRef.current.updatedAt,
        timelineRef.current.backendInstanceId
      );
      timelineRestoredRef.current = true;
      syncVideos();
    }

    void restoreTimeline();
    return () => {
      cancelled = true;
    };
  }, [syncVideos]);

  useEffect(() => {
    let cancelled = false;

    function resetTimeline(instanceId: string | null) {
      timelineRef.current = emptyTimeline(instanceId);
      persistTimeline(0, false, timelineRef.current.updatedAt, instanceId);
      if (timelineRestoredRef.current) syncVideos();
    }

    async function checkBackendSession() {
      if (!timelineRestoredRef.current) return;
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/simulation/state?context=dashboard`, {
          cache: "no-store",
        });
        if (!response.ok) throw new Error("Backend tidak tersedia");
        const state = await response.json();
        if (cancelled) return;

        const instanceId =
          typeof state.backendInstanceId === "string" ? state.backendInstanceId : null;
        const backendChanged =
          instanceId !== null &&
          timelineRef.current.backendInstanceId !== null &&
          timelineRef.current.backendInstanceId !== instanceId;

        // Navigasi/idle bukan sesi baru. Reset hanya ketika backend restart.
        if (backendChanged) {
          resetTimeline(instanceId);
        } else if (timelineRef.current.backendInstanceId === null && instanceId !== null) {
          timelineRef.current.backendInstanceId = instanceId;
          persistTimeline(
            timelineRef.current.time,
            timelineRef.current.paused,
            timelineRef.current.updatedAt,
            instanceId
          );
        }

      } catch {
        if (cancelled) return;
        // Gangguan jaringan bukan bukti backend restart. Tunggu instance ID baru.
      }
    }

    const interval = window.setInterval(checkBackendSession, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [syncVideos]);

  useEffect(() => () => {
    // Jam bersama itu wall-clock murni (lihat syncVideos()) -- tidak perlu
    // "membaca" video manapun lagi sebelum unmount, .time/.updatedAt yang
    // sudah tersimpan sudah cukup akurat lewat getSharedTimelineTime().
    persistTimeline(
      timelineRef.current.time,
      timelineRef.current.paused,
      timelineRef.current.updatedAt,
      timelineRef.current.backendInstanceId
    );
  }, []);

  /*
   * Heartbeat 700ms: dorong reportSharedTime() supaya onTimeUpdate terus
   * dapat nilai segar (buat progress bar + POST /sync-clock ke backend) --
   * bukan cuma menunggu event DOM `timeupdate` satu video tertentu (kalau
   * video itu nge-buffer/pause, event itu berhenti).
   *
   * SENGAJA panggil reportSharedTime() (BUKAN syncVideos()) -- heartbeat
   * ini tidak boleh menyentuh currentTime/play/pause video manapun. Lihat
   * catatan panjang di syncVideos() soal bug stutter/play-pause berulang
   * yang ditemukan 10 Sept 2026 gara-gara video dipaksa seek terus-menerus
   * di sini.
   */
  useEffect(() => {
    const interval = window.setInterval(() => {
      if (!timelineRestoredRef.current) return;
      reportSharedTime();
    }, 700);
    return () => window.clearInterval(interval);
  }, [reportSharedTime]);

  useEffect(() => {
    let cancelled = false;

    // Load SEMUA kamera dari semua kemungkinan ID simpang di database,
    // SEKALI saja -- tidak lagi bergantung/difilter oleh selectedApproach.
    // Filter approach cuma soal layout (lihat focusedCamera di atas),
    // bukan soal kamera mana yang dimuat/dimount.
    Promise.all(
      ALL_INTERSECTIONS.map((inter) => loadCamerasForIntersection(inter.databaseId))
    ).then((results) => {
      if (cancelled) return;
      setCameras(results.flat());
    });

    return () => {
      cancelled = true;
    };
  }, []);

  // resolveVideoSrc() nambah cache-buster (?t=Date.now()) supaya browser
  // tidak pakai response korup dari cache. Tapi kalau dipanggil LANGSUNG
  // di JSX (bukan di-memoize), dia recompute tiap render -- termasuk
  // render yang dipicu prop `counts` yang update tiap beberapa detik dari
  // WebSocket/polling di page.tsx. Src video jadi berubah tiap render,
  // browser terus-menerus reload videonya dari awal -> buffering selamanya,
  // walau `cameras` sendiri (isi videonya) tidak berubah. Di-memoize di
  // sini, key-nya `cameras` (cuma berubah kalau ada kamera baru -- SEKARANG
  // TIDAK LAGI berubah gara-gara ganti filter approach), supaya src stabil
  // lintas render live-update DAN lintas ganti filter.
  const resolvedSrcByCamera = useMemo(() => {
    const map = new Map<string, string>();

    for (const camera of cameras) {
      if (camera.source) {
        map.set(camera.id, resolveVideoSrc(camera.source));
      }
    }

    return map;
  }, [cameras]);

  // Dipakai untuk SEMUA kamera, baik lagi dibesarkan (fokus) maupun jadi
  // strip kecil -- SATU sumber logika supaya handler-nya tidak bisa
  // diam-diam beda antara dua ukuran tampilan itu.
  function renderVideoElement(camera: Camera) {
    return (
      <video
        key={camera.id}
        ref={(element) => {
          if (element) videoRefs.current.set(camera.id, element);
          else videoRefs.current.delete(camera.id);
        }}
        src={resolvedSrcByCamera.get(camera.id)}
        muted
        autoPlay
        playsInline
        preload="auto"
        className="h-full w-full object-contain"
        onLoadedMetadata={() => {
          // Saat remount, currentTime elemen baru masih 0. Jangan
          // jadikan angka itu master karena akan menimpa timeline
          // yang disimpan sebelum pindah halaman.
          if (timelineRestoredRef.current) {
            syncVideos();
          }
        }}
        onDurationChange={(event) => {
          const duration = event.currentTarget.duration;
          if (timelineRestoredRef.current && Number.isFinite(duration) && duration > 0) {
            syncVideos();
          }
        }}
        onTimeUpdate={(e) => {
          // HANYA melapor (reportSharedTime), TIDAK memanggil syncVideos().
          // Ini native timeupdate video BIASA (playback normal), bukan momen
          // transisi -- tidak boleh ikut memicu paksaan currentTime/seek.
          // Lihat catatan panjang di syncVideos() soal bug stutter yang
          // ditemukan gara-gara ini dulu memanggil syncVideos() di sini.
          if (
            timelineRestoredRef.current &&
            !e.currentTarget.seeking &&
            e.currentTarget.readyState >= 2 &&
            camera.id === getMasterCameraId()
          ) {
            reportSharedTime();
          }
        }}
        onEnded={(event) => {
          // Rekaman demo adalah sumber realtime terbatas. Setelah
          // master habis, mulai sesi 42 menit berikutnya dari awal;
          // videoTime=0 juga membuat fetchTrafficState() kembali
          // memilih window pertama batch Supabase.
          if (camera.id !== getMasterCameraId()) return;
          timelineRef.current.paused = false;
          anchorTimeline(timelineRef.current, 0);
          persistTimeline(
            0,
            false,
            timelineRef.current.updatedAt,
            timelineRef.current.backendInstanceId
          );
          // Kamera yang lagi offline (di-pause manual) SENGAJA
          // tidak ikut di-reset ke 0 -- dia masih "mati", bukan
          // ikut restart sesi bareng kamera yang hidup.
          videoRefs.current.forEach((video, id) => {
            if (offlineCameraIds.has(id)) return;
            video.currentTime = 0;
            void video.play().catch(() => undefined);
          });
          onTimeUpdate?.(0, event.currentTarget.duration);
        }}
      />
    );
  }

  // Satu kartu kamera lengkap (video + badge status/tipe/info) -- dipakai
  // baik saat jadi kartu besar (fokus) maupun strip kecil. `h-full w-full`
  // supaya dia mengisi kontainer apapun yang membungkusnya (grid cell ATAU
  // flex child), lihat pemakaiannya di CAMERA GRID di bawah.
  function renderCameraTile(camera: Camera) {
    const isOffline = offlineCameraIds.has(camera.id);

    return (
      <div
        key={camera.id}
        className="group relative h-full w-full overflow-hidden rounded-md border border-border bg-black"
      >
        {/* =========================================
            VIDEO
        ========================================= */}

        <div className="h-full w-full">
          {camera.sourceType === "rtsp" ? (

            <div className="flex h-full flex-col items-center justify-center bg-surface-2 px-3 text-center">
              <Video className="mb-1 h-5 w-5 text-text-muted" />
              <span className="text-[9px] text-text-muted">RTSP Camera</span>
              <span className="mt-0.5 text-[8px] text-text-muted">
                Backend diperlukan
              </span>
            </div>

          ) : !camera.source ? (

            <div className="flex h-full flex-col items-center justify-center bg-surface-2 px-3 text-center">
              <Video className="mb-1 h-5 w-5 text-text-muted" />
              <span className="text-[9px] text-text-muted">
                Video belum tersedia
              </span>
            </div>

          ) : (

            renderVideoElement(camera)

          )}
        </div>

        {/* =========================================
            OVERLAY "CCTV MATI" (simulasi manual)
            Video di bawahnya SENGAJA tetap ada/di-pause diam-diam --
            overlay ini cuma penutup visual, tidak ada logika play/pause
            browser yang perlu ditebak-tebak lagi.
        ========================================= */}

        {isOffline && camera.sourceType !== "rtsp" && camera.source && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 bg-black/80">
            <VideoOff className="h-6 w-6 text-signal-red" />
            <span className="text-[10px] font-semibold uppercase tracking-wide text-signal-red">
              Offline
            </span>
          </div>
        )}

        {/* =========================================
            TOMBOL SIMULASI MATI/NYALA
        ========================================= */}

        {camera.sourceType !== "rtsp" && camera.source && (
          <button
            type="button"
            onClick={() => toggleCameraOffline(camera)}
            className="absolute bottom-1.5 right-1.5 z-10 rounded bg-black/70 p-1 text-white backdrop-blur-sm transition-colors hover:bg-black/90"
            title={isOffline ? "Nyalakan lagi" : "Simulasikan CCTV mati"}
            aria-label={isOffline ? "Nyalakan CCTV" : "Matikan CCTV (simulasi)"}
          >
            {isOffline ? (
              <Video className="h-3 w-3" />
            ) : (
              <VideoOff className="h-3 w-3" />
            )}
          </button>
        )}

        {/* =========================================
            STATUS
        ========================================= */}

        <div className="absolute left-1.5 top-1.5 flex items-center gap-1 rounded bg-black/70 px-1.5 py-0.5 backdrop-blur-sm">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              camera.status === "online" ? "bg-signal-green" : "bg-signal-red"
            }`}
          />
          <span className="text-[8px] font-medium text-white">
            {camera.status === "online" ? "ONLINE" : "WAITING"}
          </span>
        </div>

        {/* =========================================
            SOURCE TYPE
        ========================================= */}

        <div className="absolute right-1.5 top-1.5 rounded bg-black/70 px-1.5 py-0.5 text-[8px] uppercase text-gray-300 backdrop-blur-sm">
          {camera.sourceType}
        </div>

        {/* =========================================
            CAMERA INFO
        ========================================= */}

        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 to-transparent px-2 pb-1.5 pt-5">
          <div className="truncate text-[10px] font-medium text-white">
            {camera.name}
          </div>
          <div className="truncate text-[8px] text-gray-300">
            {camera.direction}
          </div>
        </div>
      </div>
    );
  }

  // ===================================================
  // RETURN
  // ===================================================

  return (
    <div className="flex h-full flex-col dashboard-card rounded-lg border border-border bg-surface p-4">

      {/* =================================================
          HEADER
      ================================================= */}

      <div className="dashboard-card-header mb-3 flex items-center justify-between">

        <h2 className="font-display text-sm font-semibold text-text">
          Camera Feed
        </h2>

        <div className="flex items-center gap-2">
          {onApproachChange && (
            <select
              value={selectedApproach}
              onChange={(event) =>
                onApproachChange(
                  event.target.value as ApproachSelection
                )
              }
              className="max-w-32 rounded border border-border bg-surface-2 px-1.5 py-1 text-[10px] text-text outline-none"
              aria-label="Filter kamera berdasarkan persimpangan"
            >
              {APPROACH_OPTIONS.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.name}
                </option>
              ))}
            </select>
          )}
          <span className="text-xs text-text-muted">
            {cameras.length}/4 CAMERA
          </span>
        </div>

      </div>

      {/* =================================================
          CAMERA GRID
          SEMUA kamera SELALU mount & main normal di sini -- tidak pernah
          disembunyikan/dilepas. Filter approach cuma mengubah TATA LETAK:
          kartu yang dipilih dibesarkan, 3 lainnya jadi strip kecil di
          samping (tetap tampil & tetap jalan, cuma lebih kecil). Ini
          sengaja dipilih ketimbang mount/unmount atau CSS-hide setelah
          tiga percobaan sebelumnya (unmount, display:none, wrapper
          off-screen terpisah) semuanya berujung video play/pause
          bolak-balik terus-menerus (10 Sept 2026).
      ================================================= */}

      {cameras.length === 0 ? (

        /* =============================================
           EMPTY STATE
        ============================================= */

        <div className="dashboard-detail-card flex flex-1 aspect-video flex-col items-center justify-center rounded-md border border-dashed border-border bg-surface-2">

          <Video className="h-6 w-6 text-text-muted" />

          <span className="mt-2 text-xs text-text-muted">
            Belum ada CCTV
          </span>

          <span className="mt-1 text-center text-[10px] text-text-muted">
            Tambahkan CCTV melalui
            halaman CCTV
          </span>

        </div>

      ) : focusedCamera ? (

        /* =============================================
           FOKUS: 1 kartu besar + strip kecil 3 lainnya
        ============================================= */

        <div className="flex flex-1 min-h-0 gap-2">

          <div className="min-w-0 flex-1">
            {renderCameraTile(focusedCamera)}
          </div>

          <div className="flex w-20 flex-col gap-2 sm:w-24">
            {cameras
              .filter((camera) => camera.id !== focusedCamera.id)
              .map((camera) => (
                <div key={camera.id} className="min-h-0 flex-1">
                  {renderCameraTile(camera)}
                </div>
              ))}
          </div>

        </div>

      ) : (

        /* =============================================
           SEMUA LENGAN: grid 2x2 rata
        ============================================= */

        <div className="grid flex-1 grid-cols-2 grid-rows-2 gap-2 min-h-0">
          {cameras.map((camera) => renderCameraTile(camera))}
        </div>

      )}

      {/* =================================================
          VEHICLE COUNTS
      ================================================= */}

      <div className="mt-4 border-t border-border pt-4">

        <div className="mb-3 text-[10px] uppercase tracking-wider font-semibold text-text-muted">
          Vehicle Detection
        </div>

        {counts.length > 0 ? (
          <div className="flex flex-col gap-3">
            {/* TOTAL */}
            <div className="dashboard-detail-card flex items-center justify-between rounded-md border border-border bg-surface-2 p-3">
              <span className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Total Vehicles
              </span>
              <span className="font-mono text-3xl font-extrabold tracking-tight text-text">
                {counts.reduce((acc, c) => acc + c.count, 0).toLocaleString("id-ID")}
              </span>
            </div>

            {/* BREAKDOWN */}
            <div className="grid grid-cols-2 gap-3">
              {counts.map((c) => (
                <div
                  key={c.vehicleClass}
                  className="dashboard-detail-card flex flex-col justify-center rounded-md border border-border bg-surface-2 p-3"
                >
                  <div className="mb-1 flex items-center gap-2">
                    <span className="text-text-muted">
                      {ICONS[c.vehicleClass]}
                    </span>
                    <span className="text-[10px] font-medium uppercase text-text-muted">
                      {LABELS[c.vehicleClass]}
                    </span>
                  </div>
                  <span className="font-mono text-xl font-bold text-text">
                    {c.count.toLocaleString("id-ID")}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="dashboard-detail-card rounded-md border border-dashed border-border bg-surface-2 p-4 text-center text-xs text-text-muted">
            Data kendaraan belum tersedia.
          </div>
        )}

      </div>

      {/* =================================================
          CAMERA STATUS
      ================================================= */}

      <div className="mt-3 space-y-1 border-t border-border pt-2">

        {cameras.length > 0 ? (

          cameras.map((cam) => (

            <div
              key={cam.id}
              className="flex items-center gap-1.5 text-[10px]"
            >

              <span className="truncate text-text-secondary">
                {cam.name}
              </span>

              <span
                className={`ml-auto h-1.5 w-1.5 shrink-0 rounded-full ${
                  cam.status === "online"
                    ? "bg-signal-green"
                    : "bg-signal-red"
                }`}
              />

            </div>

          ))

        ) : (

          <div className="text-[10px] text-text-muted">
            Status kamera belum tersedia
          </div>

        )}

      </div>

      {/* =================================================
          TOAST STATUS KAMERA (offline/online)
          Terpisah dari GlobalNotifications (backend, bottom-right) --
          ini murni event UI sesaat, tidak perlu tersimpan di backend.
      ================================================= */}

      {cameraAlerts.length > 0 && (
        <div className="pointer-events-none fixed bottom-4 left-4 z-[60] flex w-[min(calc(100vw-2rem),20rem)] flex-col gap-2">
          {cameraAlerts.map((alert) => (
            <div
              key={alert.id}
              className="pointer-events-auto flex items-start gap-3 rounded-md border border-white/10 bg-[#171b29] px-3 py-3 text-white shadow-2xl"
            >
              <VideoOff
                className={`mt-0.5 h-4 w-4 shrink-0 ${
                  alert.tone === "offline" ? "text-red-300" : "text-signal-green"
                }`}
              />
              <p className="min-w-0 flex-1 text-[11px] font-medium leading-snug">
                {alert.text}
              </p>
              <button
                type="button"
                onClick={() => dismissCameraAlert(alert.id)}
                className="shrink-0 rounded p-0.5 text-slate-400 transition-colors hover:bg-white/10 hover:text-white"
                aria-label="Tutup notifikasi"
                title="Tutup"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

    </div>
  );
}
