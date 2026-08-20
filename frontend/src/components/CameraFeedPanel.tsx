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
  useState,
} from "react";

import type {
  VehicleClassCount,
  VehicleClass,
} from "@/types/traffic";

// =====================================================
// TYPES
// =====================================================

type CameraStatus = {
  label: string;
  online: boolean;
};

type SourceType =
  | "file"
  | "url"
  | "rtsp";

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

// =====================================================
// CONSTANTS
// =====================================================

const STORAGE_KEY =
  "smarttwin.cctv.cameras";

const CCTV_UPDATE_EVENT =
  "smarttwin:cctv-updated";

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
// LOAD CCTV
// =====================================================

function loadCameras(): Camera[] {
  // Server / SSR
  if (
    typeof window === "undefined"
  ) {
    return [];
  }

  try {
    const saved =
      window.localStorage.getItem(
        STORAGE_KEY
      );

    if (!saved) {
      return [];
    }

    const parsed: Camera[] =
      JSON.parse(saved);

    if (!Array.isArray(parsed)) {
      return [];
    }

    // Maksimal 4 CCTV
    return parsed.slice(0, 4);

  } catch (error) {
    console.error(
      "Gagal membaca data CCTV:",
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
  cameraStatus = [],
}: {
  counts: VehicleClassCount[];
  cameraStatus?: CameraStatus[];
}) {

  // ===================================================
  // CAMERA STATE
  // ===================================================

  const [cameras, setCameras] =
    useState<Camera[]>(loadCameras);

  // ===================================================
  // UPDATE CAMERA
  // ===================================================

  useEffect(() => {

    if (
      typeof window === "undefined"
    ) {
      return;
    }

    // -----------------------------------------------
    // Ketika CCTV berubah dari tab/window lain
    // -----------------------------------------------

    const handleStorageChange = (
      event: StorageEvent
    ) => {

      if (
        event.key !== STORAGE_KEY
      ) {
        return;
      }

      setCameras(
        loadCameras()
      );
    };

    // -----------------------------------------------
    // Ketika CCTV berubah dari halaman yang sama
    // -----------------------------------------------

    const handleCCTVUpdate = () => {
      setCameras(
        loadCameras()
      );
    };

    window.addEventListener(
      "storage",
      handleStorageChange
    );

    window.addEventListener(
      CCTV_UPDATE_EVENT,
      handleCCTVUpdate
    );

    // -----------------------------------------------
    // CLEANUP
    // -----------------------------------------------

    return () => {

      window.removeEventListener(
        "storage",
        handleStorageChange
      );

      window.removeEventListener(
        CCTV_UPDATE_EVENT,
        handleCCTVUpdate
      );

    };

  }, []);

  // ===================================================
  // RETURN
  // ===================================================

  return (
    <div className="rounded-lg border border-border bg-surface p-4">

      {/* =================================================
          HEADER
      ================================================= */}

      <div className="mb-3 flex items-center justify-between">

        <h2 className="font-display text-sm font-semibold text-text">
          Camera Feed
        </h2>

        <span className="text-xs text-text-muted">
          {cameras.length}/4 CAMERA
        </span>

      </div>

      {/* =================================================
          CAMERA GRID
      ================================================= */}

      <div className="grid grid-cols-2 gap-2">

        {cameras.length > 0 ? (

          cameras.map((camera) => (

            <div
              key={camera.id}
              className="group relative overflow-hidden rounded-md border border-border bg-black"
            >

              {/* =========================================
                  VIDEO
              ========================================= */}

              <div className="aspect-video">

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

                ) : (

                  /* -------------------------------------
                     FILE / URL
                  ------------------------------------- */

                  <video
                    src={camera.source}
                    muted
                    controls
                    playsInline
                    preload="metadata"
                    className="h-full w-full object-cover"
                    onError={(event) => {

                      console.error(
                        `Video CCTV ${camera.name} gagal diputar:`,
                        event
                          .currentTarget
                          .error
                      );

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

      <div className="mt-3 border-t border-border pt-3">

        <div className="mb-2 text-[10px] uppercase tracking-wide text-text-muted">
          Vehicle Detection
        </div>

        <div className="grid grid-cols-2 gap-x-4 gap-y-1">

          {counts.length > 0 ? (

            counts.map((c) => (

              <div
                key={c.vehicleClass}
                className="flex items-center gap-1.5 text-xs"
              >

                <span className="text-text-secondary">
                  {ICONS[c.vehicleClass]}
                </span>

                <span className="text-text-secondary">
                  {LABELS[c.vehicleClass]}
                </span>

                <span className="ml-auto font-mono tabular-nums text-text">

                  {c.count.toLocaleString(
                    "id-ID"
                  )}

                </span>

              </div>

            ))

          ) : (

            <div className="col-span-2 text-xs text-text-muted">
              Data kendaraan belum tersedia.
            </div>

          )}

        </div>

      </div>

      {/* =================================================
          CAMERA STATUS
      ================================================= */}

      <div className="mt-3 space-y-1 border-t border-border pt-2">

        {cameraStatus.length > 0 ? (

          cameraStatus.map((cam) => (

            <div
              key={cam.label}
              className="flex items-center gap-1.5 text-[10px]"
            >

              <span className="truncate text-text-secondary">
                {cam.label}
              </span>

              <span
                className={`ml-auto h-1.5 w-1.5 shrink-0 rounded-full ${
                  cam.online
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