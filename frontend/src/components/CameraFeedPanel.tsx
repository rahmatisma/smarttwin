"use client";

import {
  Bike,
  Car,
  Bus,
  Truck,
  Video,
} from "lucide-react";

import {
  useEffect,
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

// Posisi disimpan PER rekaman. Menggeser satu CCTV tidak boleh menyeret CCTV
// lain ke timestamp yang sama; masing-masing melanjutkan waktu naturalnya.
const persistedCameraTimes = new Map<string, number>();
const CAMERA_TIME_SESSION_KEY = "smarttwin.camera.currentTimes";

function restoreCameraTime(cameraId: string): number {
  const memoryValue = persistedCameraTimes.get(cameraId);
  if (memoryValue !== undefined) return memoryValue;
  if (typeof window === "undefined") return 0;
  try {
    const stored = JSON.parse(
      window.sessionStorage.getItem(CAMERA_TIME_SESSION_KEY) ?? "{}"
    ) as Record<string, number>;
    const value = Number(stored[cameraId]);
    if (Number.isFinite(value) && value >= 0) {
      persistedCameraTimes.set(cameraId, value);
      return value;
    }
  } catch {
    // Storage lama/rusak tidak boleh mencegah video diputar.
  }
  return 0;
}

function persistCameraTime(cameraId: string, time: number): void {
  const safeTime = Math.max(0, time);
  persistedCameraTimes.set(cameraId, safeTime);
  if (typeof window !== "undefined") {
    window.sessionStorage.setItem(CAMERA_TIME_SESSION_KEY, JSON.stringify(
      Object.fromEntries(persistedCameraTimes)
    ));
  }
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
  onPlaybackChange,
}: {
  counts: VehicleClassCount[];
  cameraStatus?: CameraStatus[];
  selectedApproach?: ApproachSelection;
  onApproachChange?: (selection: ApproachSelection) => void;
  onTimeUpdate?: (time: number) => void;
  onPlaybackChange?: (playing: boolean) => void;
}) {

  // ===================================================
  // CAMERA STATE
  // ===================================================

  const [cameras, setCameras] =
    useState<Camera[]>([]);
  const videoRefs = useRef(new Map<string, HTMLVideoElement>());
  const restoredCameraIds = useRef(new Set<string>());

  useEffect(() => {
    let cancelled = false;
    onPlaybackChange?.(false);

    // Load semua kamera dari semua kemungkinan ID simpang di database
    Promise.all(
      ALL_INTERSECTIONS.map((inter) => loadCamerasForIntersection(inter.databaseId))
    ).then((results) => {
      if (cancelled) return;
      
      const allCams = results.flat();

      if (selectedApproach === "all") {
        setCameras(allCams);
      } else {
        const filtered = allCams.filter((cam) =>
          cam.direction === selectedApproach
        );
        setCameras(filtered);
      }
      if (allCams.length === 0) onPlaybackChange?.(false);
    });

    return () => {
      cancelled = true;
    };
  }, [onPlaybackChange, selectedApproach]);

  // resolveVideoSrc() nambah cache-buster (?t=Date.now()) supaya browser
  // tidak pakai response korup dari cache. Tapi kalau dipanggil LANGSUNG
  // di JSX (bukan di-memoize), dia recompute tiap render -- termasuk
  // render yang dipicu prop `counts` yang update tiap beberapa detik dari
  // WebSocket/polling di page.tsx. Src video jadi berubah tiap render,
  // browser terus-menerus reload videonya dari awal -> buffering selamanya,
  // walau `cameras` sendiri (isi videonya) tidak berubah. Di-memoize di
  // sini, key-nya `cameras` (cuma berubah kalau selectedApproach berubah
  // atau ada kamera baru), supaya src stabil lintas render live-update.
  const resolvedSrcByCamera = useMemo(() => {
    const map = new Map<string, string>();

    for (const camera of cameras) {
      if (camera.source) {
        map.set(camera.id, resolveVideoSrc(camera.source));
      }
    }

    return map;
  }, [cameras]);

  // ===================================================
  // RETURN
  // ===================================================

  return (
    <div className="flex h-full flex-col rounded-lg border border-border bg-surface p-4">

      {/* =================================================
          HEADER
      ================================================= */}

      <div className="mb-3 flex items-center justify-between">

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
            {cameras.length}/{selectedApproach === "all" ? 4 : 1} CAMERA
          </span>
        </div>

      </div>

      {/* =================================================
          CAMERA GRID
      ================================================= */}

      <div className={`grid gap-2 flex-1 min-h-0 ${
        cameras.length === 1 ? "grid-cols-1 grid-rows-1" :
        cameras.length === 2 ? "grid-cols-2 grid-rows-1" :
        "grid-cols-2 grid-rows-2"
      }`}>

        {cameras.length > 0 ? (

          cameras.map((camera) => (

            <div
              key={camera.id}
              className="group relative overflow-hidden rounded-md border border-border bg-black"
            >

              {/* =========================================
                  VIDEO
              ========================================= */}

              <div className="h-full w-full">

                {/* ---------------------------------------
                    RTSP
                --------------------------------------- */}

                {camera.sourceType ===
                "rtsp" ? (

                  <div className="flex h-full flex-col items-center justify-center bg-surface-2 px-3 text-center">

                    <Video className="mb-1 h-5 w-5 text-text-muted" />

                    <span className="text-[9px] text-text-muted">
                      RTSP Camera
                    </span>

                    <span className="mt-0.5 text-[8px] text-text-muted">
                      Backend diperlukan
                    </span>

                  </div>

                ) : !camera.source ? (

                  /* -------------------------------------
                     BELUM ADA VIDEO
                  ------------------------------------- */

                  <div className="flex h-full flex-col items-center justify-center bg-surface-2 px-3 text-center">

                    <Video className="mb-1 h-5 w-5 text-text-muted" />

                    <span className="text-[9px] text-text-muted">
                      Video belum tersedia
                    </span>

                  </div>

                ) : (

                  /* -------------------------------------
                     FILE / URL
                  ------------------------------------- */

                  <video
                    ref={(element) => {
                      if (element) videoRefs.current.set(camera.id, element);
                      else {
                        videoRefs.current.delete(camera.id);
                        restoredCameraIds.current.delete(camera.id);
                      }
                    }}
                    src={resolvedSrcByCamera.get(camera.id)}
                    controls
                    muted
                    autoPlay
                    loop
                    playsInline
                    preload="auto"
                    className="h-full w-full object-contain"
                    onLoadedMetadata={(event) => {
                      const savedTime = restoreCameraTime(camera.id);
                      // Tandai siap SEBELUM seek karena browser dapat langsung
                      // mengirim timeupdate/seeked secara sinkron setelah
                      // currentTime diubah.
                      restoredCameraIds.current.add(camera.id);
                      if (savedTime > 0 && event.currentTarget.duration > 0) {
                        event.currentTarget.currentTime = Math.min(
                          savedTime,
                          Math.max(0, event.currentTarget.duration - 0.05)
                        );
                      }
                      void event.currentTarget.play().catch(() => undefined);
                    }}
                    onTimeUpdate={(e) => {
                      // Event currentTime=0 dapat muncul ketika src baru
                      // dipasang atau elemen sedang dibongkar. Jangan sampai
                      // event lifecycle itu menimpa posisi rekaman terakhir.
                      if (!restoredCameraIds.current.has(camera.id)) return;
                      persistCameraTime(camera.id, e.currentTarget.currentTime);
                      if (camera.id === cameras[0]?.id) {
                        onTimeUpdate?.(e.currentTarget.currentTime);
                      }
                    }}
                    onPause={() => {
                      if (camera.id === cameras[0]?.id) {
                        onPlaybackChange?.(false);
                      }
                    }}
                    onPlay={() => {
                      if (camera.id === cameras[0]?.id) {
                        onPlaybackChange?.(true);
                      }
                    }}
                    onPlaying={() => {
                      if (camera.id === cameras[0]?.id) {
                        onPlaybackChange?.(true);
                      }
                    }}
                    onEnded={() => {
                      if (camera.id === cameras[0]?.id) {
                        onPlaybackChange?.(false);
                      }
                    }}
                  />

                )}

              </div>

              {/* =========================================
                  STATUS
              ========================================= */}

              <div className="absolute left-1.5 top-1.5 flex items-center gap-1 rounded bg-black/70 px-1.5 py-0.5 backdrop-blur-sm">

                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    camera.status ===
                    "online"
                      ? "bg-signal-green"
                      : "bg-signal-red"
                  }`}
                />

                <span className="text-[8px] font-medium text-white">

                  {camera.status ===
                  "online"
                    ? "ONLINE"
                    : "WAITING"}

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

          ))

        ) : (

          /* =============================================
             EMPTY STATE
          ============================================= */

          <div className="col-span-2 flex aspect-video flex-col items-center justify-center rounded-md border border-dashed border-border bg-surface-2">

            <Video className="h-6 w-6 text-text-muted" />

            <span className="mt-2 text-xs text-text-muted">
              Belum ada CCTV
            </span>

            <span className="mt-1 text-center text-[10px] text-text-muted">
              Tambahkan CCTV melalui
              halaman CCTV
            </span>

          </div>

        )}

      </div>

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
            <div className="flex items-center justify-between rounded-md border border-border bg-surface-2 p-3">
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
                  className="flex flex-col justify-center rounded-md border border-border bg-surface-2 p-3"
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
          <div className="rounded-md border border-dashed border-border bg-surface-2 p-4 text-center text-xs text-text-muted">
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

    </div>
  );
}
