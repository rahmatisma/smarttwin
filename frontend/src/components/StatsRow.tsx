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
  featured = false,
}: {
  icon: React.ReactNode;
  // bg + text tetap (bukan token tema) -- dipakai sebagai aksen warna kartu,
  // bukan warna semantik status, jadi sengaja sama di tema gelap/terang.
  iconClassName?: string;
  featured?: boolean;
  label: string;
  value: string;
  unit?: string;
  // Info tambahan yang REAL (mis. lengan mana yang jadi sumber angka ini),
  // bukan angka rekaan -- lihat progress di bawah soal kenapa kartu ini
  // tidak selalu punya progress bar.
  caption?: string;
  // 0-100. Cuma diisi kalau ada basis yang sudah dipercaya di tempat lain
  // (mis. congestionPct dipakai juga oleh gauge) -- tidak dibikin-bikin
  // dari "kapasitas" yang tidak pernah didefinisikan mana pun di codebase.
  progress?: { value: number; colorHex: string };
}) {
  return (
    <div className={`stat-card ${featured ? "stat-card-featured" : ""} flex flex-1 flex-col gap-3 rounded-xl border border-border bg-surface p-5`}>
      <div className="stat-heading">
        <div className="stat-label">{label}</div>
        <div
          className={`stat-icon flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
            iconClassName ?? "bg-surface-2 text-text-secondary"
          }`}
        >
          {icon}
        </div>

      </div>
      <div className="stat-value text-text">
        {value}

        {unit && (
          <span className="ml-1 text-xs font-normal text-text-muted">
            {unit}
          </span>
        )}
      </div>

      {progress && (
        <div className="stat-progress w-full overflow-hidden rounded-lg bg-surface-2">
          <div
            className="stat-progress-fill h-full rounded-lg transition-all duration-500"
            style={{
              width: `${Math.min(100, Math.max(0, progress.value))}%`,
              backgroundColor: progress.colorHex,
            }}
          />
        </div>
      )}

      {caption && (
        <div className="stat-caption text-text-muted">
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
   * Ini hanya normalisasi visual untuk gauge kepadatan.
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
    <div className="dashboard-stats grid grid-cols-1 gap-4 px-6 py-5 sm:grid-cols-2 xl:grid-cols-5">

      {/* =====================================================
          TOTAL VEHICLES
          ===================================================== */}

      <StatCard
        featured
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
        iconClassName="bg-cyan-500/10 text-cyan-600"
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
        iconClassName="bg-teal-500/10 text-teal-600"
        label="Indeks Kepadatan"
        value={hasData ? avgDensity.toFixed(1) : "No data"}
        progress={hasData ? { value: congestionPct, colorHex: "#34c7c4" } : undefined}
        caption={hasData ? `Status: ${congestion.label}` : undefined}
      />

      {/* =====================================================
          WEATHER
          ===================================================== */}

      <div className="stat-card stat-weather flex flex-1 flex-col gap-3 rounded-xl border border-border bg-surface p-5">
        <div className="stat-heading">
          <div className="stat-label">Cuaca</div>
          <div className="stat-icon flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-cyan-500/10 text-cyan-600">
          {getWeatherIcon(weather.condition)}
          </div>
        </div>

        <div className="min-w-0">
          <div className="stat-value text-text">
            {weather.tempC !== null
              ? `${weather.tempC}°C`
              : "N/A"}

          </div>
          <div className="stat-weather-condition text-text-secondary">{weather.condition}</div>
        </div>
        <div className="stat-caption text-text-muted">{weather.dateLabel} · BMKG</div>
      </div>

      {/* =====================================================
          CONGESTION
          ===================================================== */}

      <div
        className="stat-card stat-congestion flex flex-1 flex-col gap-3 rounded-xl border border-border bg-surface p-5"
      >
        <div className="stat-label">Tingkat Kepadatan</div>
        <div className="stat-gauge">
          <svg viewBox="0 0 200 110" aria-hidden="true">
            {Array.from({ length: 24 }, (_, index) => {
              const angle = Math.PI - (index / 23) * Math.PI;
              const active = hasData && index < Math.round(congestionPct * 24 / 100);
              return <line key={index}
                x1={100 + 72 * Math.cos(angle)} y1={99 - 72 * Math.sin(angle)}
                x2={100 + 91 * Math.cos(angle)} y2={99 - 91 * Math.sin(angle)}
                stroke={active ? (congestion.color === "green" ? `hsl(${185 - index * 1.8} 58% 65%)` : c.hex) : "var(--color-surface-2)"}
                strokeWidth={8} strokeLinecap="round" />;
            })}
          </svg>
          <div className="stat-gauge-value text-text">{hasData ? `${congestionPct}%` : "N/A"}</div>
        </div>
          <div
            className={`stat-gauge-status text-xs font-semibold ${c.text}`}
          >
            {congestion.label}
          </div>
      </div>
    </div>
  );
}
