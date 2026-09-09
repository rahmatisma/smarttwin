// src/lib/dataMode.ts
//
// Mode sumber data untuk panel SUMO (Dashboard + Digital Twin).
//
// Latar: kalau CCTV mati, YOLO berhenti mengirim TrafficState baru. Backend
// (bagian logic tim) otomatis memutar ulang data hari sebelumnya supaya SUMO
// tetap jalan. Frontend HANYA perlu tahu "ini live atau rekaman lama" supaya
// tampilan bisa dibedakan -- pengelola tidak boleh salah kira rekaman kemarin
// sebagai kondisi jalan saat ini.
//
// ── KONTRAK YANG DIISI BACKEND ──────────────────────────────────────────────
// Endpoint GET /api/v1/simulation/state?context=dashboard menambahkan field
// opsional berikut pada response-nya (semuanya boleh tidak ada = anggap live):
//
//   dataMode          : "live" | "replay"     -- status sumber saat ini
//   replayDataDate    : string (ISO date/te)  -- tanggal data yang diputar ulang
//   replaySince       : string (ISO datetime) -- kapan CCTV terdeteksi mati
//   cctvOnline        : boolean               -- alternatif: false => replay
//
// Alias nama field lain ikut dibaca di bawah supaya frontend tidak patah kalau
// backend memakai penamaan sedikit berbeda.
// ───────────────────────────────────────────────────────────────────────────

export type DataMode = "live" | "replay";

export interface DataModeInfo {
  mode: DataMode;
  /** Label tanggal data yang sedang diputar ulang. null saat live / tidak diketahui. */
  replayDataDate: string | null;
  /** ISO datetime saat CCTV terdeteksi mati. null kalau backend tidak mengirim. */
  since: string | null;
  /**
   * Lengan yang CCTV-nya mati -> demand-nya data lama yang diputar ulang
   * (mis. ["east"]). Kosong = tidak spesifik / seluruh simpang. Dipakai untuk
   * menandai lengan tsb: badge "DATA LAMA" + kendaraan biru di SUMO-GUI.
   */
  replayApproaches: string[];
}

export const LIVE_DATA_MODE: DataModeInfo = {
  mode: "live",
  replayDataDate: null,
  since: null,
  replayApproaches: [],
};

const APPROACH_KEYS = ["north", "south", "east", "west"] as const;

const APPROACH_LABEL_ID: Record<string, string> = {
  north: "Utara",
  south: "Selatan",
  east: "Timur",
  west: "Barat",
};

/** "Timur" dari "east"; kalau tak dikenal, kembalikan apa adanya (kapital awal). */
export function approachLabelId(approach: string): string {
  return (
    APPROACH_LABEL_ID[approach.toLowerCase()] ??
    approach.charAt(0).toUpperCase() + approach.slice(1)
  );
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : null;
}

function readApproachList(value: unknown): string[] {
  const raw: unknown[] = Array.isArray(value)
    ? value
    : value && typeof value === "object"
      ? Object.keys(value as Record<string, unknown>)
      : [];
  return raw
    .map((item) => String(item).toLowerCase().trim())
    .filter((item): item is string => (APPROACH_KEYS as readonly string[]).includes(item));
}

/**
 * Baca mode data dari payload /api/v1/simulation/state.
 *
 * Toleran: menerima beberapa kemungkinan nama field, dan default ke "live"
 * bila tidak ada satupun -- jadi aman dipakai sebelum backend selesai
 * menambahkan field-nya.
 */
export function readDataModeFromState(state: unknown): DataModeInfo {
  if (!state || typeof state !== "object") return LIVE_DATA_MODE;
  const s = state as Record<string, unknown>;

  const explicitMode = asString(s.dataMode ?? s.data_mode ?? s.sourceMode ?? s.source_mode);
  const replayApproaches = readApproachList(
    s.replayApproaches ?? s.replay_approaches ?? s.staleApproaches ?? s.stale_approaches
  );
  const replayFlag =
    s.replay === true ||
    s.isReplay === true ||
    s.replayActive === true ||
    s.cctvOnline === false ||
    s.cctv_online === false ||
    replayApproaches.length > 0;

  const isReplay = explicitMode === "replay" || (explicitMode === null && replayFlag);
  if (!isReplay) return LIVE_DATA_MODE;

  return {
    mode: "replay",
    replayDataDate: asString(
      s.replayDataDate ??
        s.replay_data_date ??
        s.replayDate ??
        s.replay_date ??
        s.dataDate ??
        s.data_date
    ),
    since: asString(
      s.replaySince ?? s.replay_since ?? s.cctvOfflineSince ?? s.cctv_offline_since
    ),
    replayApproaches,
  };
}

/**
 * Override manual untuk demo / rekaman video -- dipakai kalau logic backend
 * belum siap tapi kita tetap ingin memperlihatkan tampilan mode rekaman.
 *
 *   ?datamode=replay
 *   ?datamode=replay&replaydate=2026-09-08
 *   ?replayapproaches=east            (lengan Timur pakai data lama)
 *   ?replayapproaches=east,north
 *   ?datamode=live                    (paksa live walau backend bilang replay)
 *
 * atau lewat console:
 *   localStorage.setItem("smarttwin.forceDataMode", "replay")
 *   localStorage.removeItem("smarttwin.forceDataMode")
 */
function readDemoOverride(): DataModeInfo | null {
  if (typeof window === "undefined") return null;

  let raw: string | null = null;
  let dateParam: string | null = null;
  let approachParam: string | null = null;
  try {
    const params = new URLSearchParams(window.location.search);
    raw = params.get("datamode") ?? params.get("dataMode");
    dateParam = params.get("replaydate") ?? params.get("replayDate");
    approachParam = params.get("replayapproaches") ?? params.get("replayApproaches");
  } catch {
    /* URL tidak bisa diparse -- abaikan */
  }

  if (!raw && !approachParam) {
    try {
      raw = window.localStorage.getItem("smarttwin.forceDataMode");
    } catch {
      /* localStorage diblokir -- abaikan */
    }
  }

  const approaches = readApproachList(approachParam ? approachParam.split(",") : []);

  if (!raw && approaches.length === 0) return null;
  const normalized = (raw ?? "replay").trim().toLowerCase();
  if (normalized === "live") return LIVE_DATA_MODE;
  if (normalized === "replay" || approaches.length > 0) {
    return {
      mode: "replay",
      replayDataDate: dateParam,
      since: null,
      replayApproaches: approaches,
    };
  }
  return null;
}

/**
 * Resolusi akhir: override demo menang, kalau tidak ada baru baca dari state
 * backend.
 */
export function resolveDataMode(state: unknown): DataModeInfo {
  return readDemoOverride() ?? readDataModeFromState(state);
}

/** "8 September 2026" dari berbagai bentuk input; fallback ke string apa adanya. */
export function formatReplayDate(value: string | null): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString("id-ID", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

/** "sejak 14:32" dari ISO datetime; null kalau tidak ada / tidak valid. */
export function formatReplaySince(value: string | null): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
}
