import {
  Car,
  Milestone,
  PieChart,
  CloudSun,
  Sun,
  Cloud,
  CloudRain,
  CloudLightning,
  CloudFog,
} from "lucide-react";

import type { ApproachState } from "@/types/traffic";

import DonutRing from "./DonutRing";

/*
 * =========================================================
 * CONGESTION CLASSIFICATION
 * =========================================================
 *
 * densityIndex merupakan proxy lane occupancy/kepadatan.
 *
 * BUKAN:
 * - vehicles/km
 * - occupancy fisik terkalibrasi
 * - LOS resmi PKJI
 *
 * Threshold ini hanya digunakan untuk indikator visual
 * dashboard.
 *
 * Dikalibrasi ulang 25 Agustus 2026 ke skala densityIndex yang
 * SEBENARNYA (rata-rata kendaraan di zona per window, dari
 * snapshot_zona.csv -- lihat cv_csv_bridge.py). Threshold lama
 * (90/130) dirancang untuk skala yang jauh lebih besar dari data
 * asli: seluruh dataset 15 Agustus cuma berkisar 0-13,4 (median 4,
 * p90 9,4, p95 10,6) -- dengan threshold lama, Congestion Level
 * SELALU "Rendah" apa pun kondisinya, tidak pernah kelihatan
 * "Sedang"/"Tinggi" walau simpang penuh sesak. Threshold baru
 * mengikuti distribusi nyata: >=10 (sekitar p90 ke atas) = Tinggi,
 * >=5 (sekitar median ke atas) = Sedang.
 */

function congestionFromDensity(avgDensity: number): {
  label: string;
  color: "red" | "amber" | "green";
} {
  if (avgDensity >= 10) {
    return {
      label: "Tinggi",
      color: "red",
    };
  }

  if (avgDensity >= 5) {
    return {
      label: "Sedang",
      color: "amber",
    };
  }

  return {
    label: "Rendah",
    color: "green",
  };
}

/*
 * =========================================================
 * WEATHER ICON CLASSIFICATION
 * =========================================================
 */

function getWeatherIcon(condition: string) {
  const c = condition.toLowerCase();
  if (c.includes("petir")) return <CloudLightning className="h-4 w-4" />;
  if (c.includes("hujan")) return <CloudRain className="h-4 w-4" />;
  if (c.includes("kabut") || c.includes("asap")) return <CloudFog className="h-4 w-4" />;
  if (c.includes("cerah berawan")) return <CloudSun className="h-4 w-4" />;
  if (c.includes("berawan")) return <Cloud className="h-4 w-4" />;
  if (c.includes("cerah")) return <Sun className="h-4 w-4" />;
  return <CloudSun className="h-4 w-4" />;
}

/*
 * =========================================================
 * CONGESTION COLORS
 * =========================================================
 */

const colorClasses: Record<
  "red" | "amber" | "green",
  {
    text: string;
    bg: string;
    ring: string;
    hex: string;
  }
> = {
  red: {
    text: "text-signal-red",
    bg: "bg-signal-red-dim",
    ring: "ring-signal-red/30",
    hex: "#f0483e",
  },

  amber: {
    text: "text-signal-amber",
    bg: "bg-signal-amber-dim",
    ring: "ring-signal-amber/30",
    hex: "#f5a623",
  },

  green: {
    text: "text-signal-green",
    bg: "bg-signal-green-dim",
    ring: "ring-signal-green/30",
    hex: "#2ecc71",
  },
};

/*
 * =========================================================
 * STAT CARD
 * =========================================================
 */

function StatCard({
  icon,
  iconClassName,
  label,
  value,
  unit,
  caption,
  progress,
}: {
  icon: React.ReactNode;
  // bg + text tetap (bukan token tema) -- dipakai sebagai aksen warna kartu,
  // bukan warna semantik status, jadi sengaja sama di tema gelap/terang.
  iconClassName?: string;
  label: string;
  value: string;
  unit?: string;
  // Info tambahan yang REAL (mis. lengan mana yang jadi sumber angka ini),
  // bukan angka rekaan -- lihat progress di bawah soal kenapa kartu ini
  // tidak selalu punya progress bar.
  caption?: string;
  // 0-100. Cuma diisi kalau ada basis yang sudah dipercaya di tempat lain
  // (mis. congestionPct dipakai juga oleh DonutRing) -- tidak dibikin-bikin
  // dari "kapasitas" yang tidak pernah didefinisikan mana pun di codebase.
  progress?: { value: number; colorHex: string };
}) {
  return (
    <div className="flex flex-1 flex-col gap-2.5 rounded-lg border border-border bg-surface px-4 py-3">
      <div className="flex items-center gap-3">
        <div
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
            iconClassName ?? "bg-surface-2 text-text-secondary"
          }`}
        >
          {icon}
        </div>

        <div className="min-w-0">
          <div className="text-xs text-text-secondary">
            {label}
          </div>

          <div className="font-mono text-lg font-semibold tabular-nums text-text">
            {value}

            {unit && (
              <span className="ml-1 text-xs font-normal text-text-muted">
                {unit}
              </span>
            )}
          </div>
        </div>
      </div>

      {progress && (
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${Math.min(100, Math.max(0, progress.value))}%`,
              backgroundColor: progress.colorHex,
            }}
          />
        </div>
      )}

      {caption && (
        <div className="truncate text-[10px] text-text-muted">
          {caption}
        </div>
      )}
    </div>
  );
}

/*
 * =========================================================
 * STATS ROW
 * =========================================================
 *
 * Semua traffic metric berasal dari ApproachState.
 *
 * Contract:
 *
 * volume
 * queueLengthVeh
 * queueLengthMEst
 * densityIndex
 * Tidak menggunakan mock data.
 * Tidak membutuhkan occupancyPct dari page.tsx.
 */

export default function StatsRow({
  approaches,
  weather,
}: {
  approaches: ApproachState[];

  weather: {
    dateLabel: string;
    condition: string;
    tempC: number | null;
  };
}) {
  /*
   * =========================================================
   * TOTAL VEHICLES (di zona, KEHADIRAN -- bukan crossing)
   * =========================================================
   *
   * SENGAJA pakai densityIndex (dari snapshot_zona.csv, dibulatkan),
   * BUKAN volume (dari crossing_simpang.csv). volume = berapa
   * kendaraan MELINTASI garis hitung dalam window 5 detik itu (bisa
   * kecil walau jalan padat, misal cuma 2 kalau macet/kendaraan
   * banyak yang diam). densityIndex = rata-rata kendaraan yang benar-
   * benar ADA di zona saat itu -- ini yang dimaksud pengguna dashboard
   * saat baca "Total Vehicles", dikonfirmasi langsung 25 Agustus 2026
   * setelah dibandingkan ke overlay debug CV (vehicle_counter_copy.py)
   * yang nunjukin angka zona, bukan crossing.
   */

  const totalVolume = Math.round(
    approaches.reduce(
      (sum, approach) => sum + approach.densityIndex,
      0
    )
  );

  /*
   * =========================================================
   * MAX QUEUE
   * =========================================================
   *
   * queueLengthMEst = estimasi panjang antrean dalam meter.
   */

  const maxQueue =
    approaches.length > 0
      ? Math.max(
        ...approaches.map(
          (approach) => approach.queueLengthMEst
        )
      )
      : 0;

  /*
   * =========================================================
   * LENGAN TERSIBUK (utk caption StatCard)
   * =========================================================
   *
   * Bukan angka baru -- cuma menunjuk approach mana yang jadi sumber
   * totalVolume/maxQueue di atas, dari data yang sama.
   */

  const APPROACH_LABEL: Record<string, string> = {
    north: "Utara",
    south: "Selatan",
    east: "Timur",
    west: "Barat",
  };

  const busiestByDensity =
    approaches.length > 0
      ? approaches.reduce((a, b) => (b.densityIndex > a.densityIndex ? b : a))
      : null;

  const busiestByQueue =
    approaches.length > 0
      ? approaches.reduce((a, b) => (b.queueLengthMEst > a.queueLengthMEst ? b : a))
      : null;

  /*
   * =========================================================
   * AVERAGE DENSITY INDEX
   * =========================================================
   *
   * densityIndex adalah proxy lane occupancy/kepadatan.
   *
   * BUKAN vehicles/km.
   */

  const avgDensity =
    approaches.length > 0
      ? approaches.reduce(
        (sum, approach) =>
          sum + approach.densityIndex,
        0
      ) / approaches.length
      : 0;

  /*
   * =========================================================
   * CONGESTION
   * =========================================================
   */
  const hasData = approaches.length > 0;

  const congestion = hasData
    ? congestionFromDensity(avgDensity)
    : { label: "N/A", color: "green" as const };

  const c = colorClasses[congestion.color];

  /*
   * =========================================================
   * VISUAL DENSITY PERCENTAGE
   * =========================================================
   *
   * Ini hanya normalisasi visual untuk DonutRing.
   *
   * BUKAN occupancy fisik.
   *
   * Dibagi 15 (bukan 180 seperti sebelumnya) -- dikalibrasi ke skala
   * densityIndex asli (maks observasi 13,4 di seluruh dataset 15
   * Agustus). /180 bikin ring selalu kelihatan nyaris kosong (maks
   * ~7%) apa pun kondisinya; /15 bikin density tinggi (~10 ke atas,
   * sama seperti threshold "Tinggi" di atas) kelihatan mendekati
   * penuh di ring.
   */

  const congestionPct = hasData ? Math.min(
    Math.max(
      Math.round((avgDensity / 15) * 100),
      0
    ),
    100
  ) : 0;

  return (
    <div className="grid grid-cols-2 gap-3 px-6 py-4 md:grid-cols-3 xl:grid-cols-5">

      {/* =====================================================
          TOTAL VEHICLES
          ===================================================== */}

      <StatCard
        icon={<Car className="h-4 w-4" />}
        iconClassName="bg-blue-500/15 text-blue-500"
        label="Total Kendaraan"
        value={hasData ? totalVolume.toLocaleString("id-ID") : "No data"}
        caption={
          hasData && busiestByDensity
            ? `Terpadat: ${APPROACH_LABEL[busiestByDensity.approach] ?? busiestByDensity.approach}`
            : undefined
        }
      />

      {/* =====================================================
          MAX QUEUE
          ===================================================== */}

      <StatCard
        icon={<Milestone className="h-4 w-4" />}
        iconClassName="bg-orange-500/15 text-orange-500"
        label="Antrean Terpanjang"
        value={hasData ? maxQueue.toFixed(1) : "No data"}
        unit={hasData ? "m" : undefined}
        caption={
          hasData && busiestByQueue
            ? `Lengan: ${APPROACH_LABEL[busiestByQueue.approach] ?? busiestByQueue.approach}`
            : undefined
        }
      />

      {/* =====================================================
          DENSITY INDEX
          ===================================================== */}

      <StatCard
        icon={<PieChart className="h-4 w-4" />}
        iconClassName="bg-purple-500/15 text-purple-500"
        label="Indeks Kepadatan"
        value={hasData ? avgDensity.toFixed(1) : "No data"}
        progress={hasData ? { value: congestionPct, colorHex: c.hex } : undefined}
        caption={hasData ? `Status: ${congestion.label}` : undefined}
      />

      {/* =====================================================
          WEATHER
          ===================================================== */}

      <div className="flex flex-1 items-center gap-3 rounded-lg border border-border bg-surface px-4 py-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-surface-2 text-text-secondary">
          {getWeatherIcon(weather.condition)}
        </div>

        <div className="min-w-0">
          <div className="truncate text-xs text-text-secondary">
            {weather.dateLabel}
          </div>

          <div className="text-sm font-medium text-text">
            {weather.tempC !== null
              ? `${weather.tempC}°C`
              : "N/A"}

            <span className="ml-1 text-xs font-normal text-text-muted">
              {weather.condition}
            </span>
          </div>

          <div className="text-[10px] text-text-muted opacity-70">
            Sumber: BMKG
          </div>
        </div>
      </div>

      {/* =====================================================
          CONGESTION
          ===================================================== */}

      <div
        className="flex flex-1 items-center gap-3 rounded-lg border border-border bg-surface px-4 py-3"
      >
        <div className="relative shrink-0">
          <DonutRing
            size={40}
            thickness={5}
            segments={[
              {
                value: congestionPct,
                color: c.hex,
              },
              {
                value: 100 - congestionPct,
                color: "#232935",
              },
            ]}
          />

          <div className="pointer-events-none absolute inset-0 flex items-center justify-center font-mono text-[9px] font-semibold text-text">
            {congestionPct}%
          </div>
        </div>

        <div>
          <div className="text-xs text-text-secondary">
            Tingkat Kepadatan
          </div>

          <div
            className={`font-display text-sm font-semibold ${c.text}`}
          >
            {congestion.label}
          </div>
        </div>
      </div>
    </div>
  );
}
