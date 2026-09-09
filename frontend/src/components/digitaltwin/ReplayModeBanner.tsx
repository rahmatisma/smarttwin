"use client";

import { History } from "lucide-react";
import type { DataModeInfo } from "@/lib/dataMode";
import { formatReplayDate, formatReplaySince, approachLabelId } from "@/lib/dataMode";

// Warna penanda "data lama" -- HARUS sama dengan STALE_VEHICLE_COLOR di
// backend/app/simulation/sumo/sumo_controller.py (putih) supaya kendaraan
// bertanda di SUMO-GUI dan badge di UI kebaca sebagai hal yang sama.
export const STALE_MARKER_HEX = "#ffffff";
// Kelas badge "DATA LAMA": latar putih perlu teks gelap + garis tepi.
export const STALE_BADGE_CLASS =
  "bg-white text-black ring-1 ring-black/20";

function approachPhrase(approaches: string[]): string | null {
  if (approaches.length === 0) return null;
  const labels = approaches.map(approachLabelId);
  if (labels.length === 1) return `lengan ${labels[0]}`;
  return `lengan ${labels.slice(0, -1).join(", ")} & ${labels[labels.length - 1]}`;
}

/*
 * =========================================================
 * REPLAY MODE BANNER
 * =========================================================
 *
 * Penanda visual saat panel SUMO menampilkan PEMUTARAN ULANG data lama
 * (CCTV mati -> backend memutar data hari sebelumnya) alih-alih kondisi
 * langsung. Tujuannya supaya pengelola tidak salah kira rekaman kemarin
 * sebagai lalu lintas saat ini.
 *
 * Warna sengaja amber (bukan merah) -- ini bukan error, sistem sengaja
 * jatuh ke data cadangan dan tetap berfungsi.
 *
 * Tidak me-render apa pun kalau mode === "live".
 */

function replaySentence(info: DataModeInfo): string {
  const tanggal = formatReplayDate(info.replayDataDate);
  const sejak = formatReplaySince(info.since);
  const lengan = approachPhrase(info.replayApproaches);

  const subjek = lengan ? `CCTV ${lengan} nonaktif` : "CCTV nonaktif";
  const dasar = tanggal
    ? `${subjek} — menampilkan data ${tanggal}`
    : `${subjek} — menampilkan data terakhir sebelum putus`;
  const waktu = sejak ? ` sejak ${sejak}` : "";
  const penanda = lengan
    ? " Kendaraan putih di lengan itu berasal dari data lama."
    : "";
  return `${dasar}${waktu}.${penanda}`;
}

/* Strip melayang di atas frame SUMO -- dipakai di dalam area video. */
export function ReplayModeOverlay({ info }: { info: DataModeInfo }) {
  if (info.mode !== "replay") return null;

  return (
    <div
      role="status"
      className="pointer-events-none absolute inset-x-0 top-0 z-20 flex items-start gap-2 border-b-2 border-signal-amber bg-signal-amber/90 px-3 py-1.5 text-black shadow-lg backdrop-blur-sm"
      style={{
        backgroundImage:
          "repeating-linear-gradient(45deg, rgba(0,0,0,0.12) 0 10px, transparent 10px 20px)",
      }}
    >
      <History className="mt-px h-4 w-4 shrink-0" aria-hidden="true" />
      <div className="min-w-0 text-[11px] font-semibold leading-tight">
        <span className="uppercase tracking-wide">Mode Data Rekaman</span>
        <span className="ml-1.5 font-medium">
          — bukan kondisi langsung. {replaySentence(info)}
        </span>
      </div>
    </div>
  );
}

/* Kartu blok penuh -- dipakai di atas/bawah panel, bukan menimpa video. */
export function ReplayModeCallout({
  info,
  className = "",
}: {
  info: DataModeInfo;
  className?: string;
}) {
  if (info.mode !== "replay") return null;

  return (
    <div
      role="status"
      className={`flex items-start gap-3 rounded-xl border border-signal-amber/50 bg-signal-amber/10 px-4 py-3 text-signal-amber ${className}`}
    >
      <History className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
      <div className="min-w-0 text-sm leading-snug">
        <p className="font-semibold uppercase tracking-wide">Mode Data Rekaman</p>
        <p className="mt-0.5 text-signal-amber/90">
          {replaySentence(info)}{" "}
          {info.replayApproaches.length > 0
            ? "Lengan lain tetap live."
            : "Simulasi berjalan dari data historis, bukan lalu lintas langsung."}
        </p>
        {info.replayApproaches.length > 0 && (
          <p className="mt-1 flex items-center gap-1.5 text-xs text-signal-amber/80">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm ring-1 ring-black/30"
              style={{ backgroundColor: STALE_MARKER_HEX }}
            />
            = kendaraan putih di SUMO berasal dari data lama
          </p>
        )}
      </div>
    </div>
  );
}

/* Chip kecil untuk menggantikan indikator "LIVE" di header panel. */
export function DataModeChip({ info }: { info: DataModeInfo }) {
  if (info.mode === "replay") {
    return (
      <span className="flex items-center gap-1.5 text-xs font-bold text-signal-amber">
        <span className="h-1.5 w-1.5 rounded-full bg-signal-amber" />
        <History className="h-3 w-3" aria-hidden="true" />
        REKAMAN
      </span>
    );
  }
  return null;
}
