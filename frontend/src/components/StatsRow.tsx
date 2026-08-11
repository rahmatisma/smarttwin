import { Car, Gauge, Milestone, PieChart, CloudSun } from "lucide-react";
import type { ApproachState } from "@/types/traffic";
import DonutRing from "./DonutRing";

// Threshold ini kasar (di-eyeball dari range density hasil snapshot SUMO
// nyata — sudah dibagi jumlah lajur per approach — bukan dari perhitungan
// PKJI 2023) — cukup buat demo, tapi ganti dengan klasifikasi Level of
// Service resmi begitu validasi PKJI (Minggu 4) selesai.
function congestionFromDensity(avgDensity: number): {
  label: string;
  color: "red" | "amber" | "green";
} {
  if (avgDensity >= 130) return { label: "Tinggi", color: "red" };
  if (avgDensity >= 90) return { label: "Sedang", color: "amber" };
  return { label: "Rendah", color: "green" };
}

const colorClasses: Record<
  "red" | "amber" | "green",
  { text: string; bg: string; ring: string; hex: string }
> = {
  red: { text: "text-signal-red", bg: "bg-signal-red-dim", ring: "ring-signal-red/30", hex: "#f0483e" },
  amber: { text: "text-signal-amber", bg: "bg-signal-amber-dim", ring: "ring-signal-amber/30", hex: "#f5a623" },
  green: { text: "text-signal-green", bg: "bg-signal-green-dim", ring: "ring-signal-green/30", hex: "#2ecc71" },
};

function StatCard({
  icon,
  label,
  value,
  unit,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  unit?: string;
}) {
  return (
    <div className="flex flex-1 items-center gap-3 rounded-lg border border-border bg-surface px-4 py-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-surface-2 text-text-secondary">
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-xs text-text-secondary">{label}</div>
        <div className="font-mono text-lg font-semibold tabular-nums text-text">
          {value}
          {unit && <span className="ml-1 text-xs font-normal text-text-muted">{unit}</span>}
        </div>
      </div>
    </div>
  );
}

export default function StatsRow({
  approaches,
  occupancyPct,
  weather,
}: {
  approaches: ApproachState[];
  occupancyPct: number;
  weather: { dateLabel: string; condition: string; tempC: number };
}) {
  const totalVolume = approaches.reduce((sum, a) => sum + a.volume, 0);
  const avgSpeed =
    approaches.reduce((sum, a) => sum + a.avgSpeedKmh, 0) / approaches.length;
  const maxQueue = Math.max(...approaches.map((a) => a.queueLengthM));
  const avgDensity =
    approaches.reduce((sum, a) => sum + a.densityVehPerKm, 0) / approaches.length;
  const congestion = congestionFromDensity(avgDensity);
  const c = colorClasses[congestion.color];
  const congestionPct = Math.min(Math.round((avgDensity / 180) * 100), 100);

  return (
    <div className="grid grid-cols-2 gap-3 px-6 py-4 md:grid-cols-3 xl:grid-cols-6">
      <StatCard
        icon={<Car className="h-4 w-4" />}
        label="Total Kendaraan"
        value={totalVolume.toLocaleString("id-ID")}
      />
      <StatCard
        icon={<Gauge className="h-4 w-4" />}
        label="Kecepatan Rata-rata"
        value={avgSpeed.toFixed(0)}
        unit="km/jam"
      />
      <StatCard
        icon={<Milestone className="h-4 w-4" />}
        label="Antrean Terpanjang"
        value={maxQueue.toFixed(0)}
        unit="m"
      />
      <StatCard
        icon={<PieChart className="h-4 w-4" />}
        label="Occupancy"
        value={occupancyPct.toString()}
        unit="%"
      />
      <div className="flex flex-1 items-center gap-3 rounded-lg border border-border bg-surface px-4 py-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-surface-2 text-text-secondary">
          <CloudSun className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <div className="truncate text-xs text-text-secondary">{weather.dateLabel}</div>
          <div className="text-sm font-medium text-text">
            {weather.tempC}°C
            <span className="ml-1 text-xs font-normal text-text-muted">{weather.condition}</span>
          </div>
        </div>
      </div>
      <div
        className={`flex flex-1 items-center gap-3 rounded-lg border border-border ${c.bg} px-4 py-3 ring-1 ${c.ring}`}
      >
        <div className="relative shrink-0">
          <DonutRing
            size={40}
            thickness={5}
            segments={[
              { value: congestionPct, color: c.hex },
              { value: 100 - congestionPct, color: "#232935" },
            ]}
          />
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center font-mono text-[9px] font-semibold text-text">
            {congestionPct}%
          </div>
        </div>
        <div>
          <div className="text-xs text-text-secondary">Tingkat Kepadatan</div>
          <div className={`font-display text-sm font-semibold ${c.text}`}>
            {congestion.label}
          </div>
        </div>
      </div>
    </div>
  );
}
