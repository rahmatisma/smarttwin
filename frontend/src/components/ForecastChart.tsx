"use client";

import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

import type { ForecastResponse, TrafficState } from "@/types/traffic";

function formatForecastData(data: ForecastResponse) {
  return data.predictions.map((prediction, index) => {
    return {
      // Endpoint menghasilkan 12 horizon berinterval lima detik.
      // Memakai menit yang dibulatkan membuat hampir semua titik punya
      // nilai X sama (0 atau 1), sehingga grafik tampak kosong/menumpuk.
      horizonSeconds: (index + 1) * 5,
      predictedVehicleCount: prediction.predictedVehicleCount,
      predictedQueueLengthVeh:
        prediction.predictedQueueLengthVeh,
      predictedQueueLengthMEst:
        prediction.predictedQueueLengthMEst,
      predictedDensityIndex:
        prediction.predictedDensityIndex,
      predictedSpeedKmh:
        prediction.predictedSpeedKmh,
    };
  });
}

/*
 * Titik pada grafik = hasil formatForecastData DITAMBAH dua field
 * yang cuma ada di sisi grafik, bukan di kontrak ForecastPrediction:
 *
 *   actualVehicleCount -> dataKey garis "aktual" (lihat <Line> di
 *                         bawah). Hanya terisi di titik horizon 0.
 *   isActual           -> penanda titik aktual vs prediksi.
 *
 * Sebelumnya tipe ini tidak pernah dideklarasikan, jadi TypeScript
 * menyimpulkan bentuk deret dari formatForecastData saja dan
 * menolak kedua field itu sebagai properti asing -- `npm run build`
 * gagal total di sini.
 */
type TitikDeret = ReturnType<typeof formatForecastData>[number] & {
  isActual: boolean;
  actualVehicleCount?: number;
};

export default function ForecastChart({
  data,
  current,
}: {
  data?: ForecastResponse | null;
  current?: TrafficState | null;
}) {
  if (!data || !data.predictions || data.predictions.length === 0) {
    return (
      <div className="flex flex-col rounded-lg border border-border bg-surface p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-display text-sm font-semibold text-text">
            Traffic Forecast
          </h2>

          <span className="text-xs text-text-muted">60 detik ke depan</span>
        </div>

        <div className="flex min-h-[160px] flex-1 items-center justify-center">
          <span className="text-xs text-text-muted">
            Data forecast belum tersedia dari backend
          </span>
        </div>
      </div>
    );
  }

  const forecastSeries = formatForecastData(data);

  let series: TitikDeret[] = forecastSeries.map((s) => ({
    ...s,
    isActual: false,
  }));

  if (current && current.approaches) {
    const currentVolume = current.approaches.reduce((sum, app) => sum + app.volume, 0);
    // Prepend the actual point at horizon 0
    // To make a continuous line, the actual point is also the start of the prediction
    series = [
      {
        horizonSeconds: 0,
        actualVehicleCount: currentVolume,
        predictedVehicleCount: currentVolume,
        predictedQueueLengthVeh: 0,
        predictedQueueLengthMEst: 0,
        predictedDensityIndex: 0,
        predictedSpeedKmh: null,
        isActual: true,
      },
      ...forecastSeries.map((s) => ({ ...s, isActual: false })),
    ];
  }

  const maxVehicle = Math.max(...series.map((s) => s.predictedVehicleCount));
  const peakTime = series.find((s) => s.predictedVehicleCount === maxVehicle)?.horizonSeconds ?? 0;
  const maxQueue = Math.max(...series.map((s) => s.predictedQueueLengthMEst));
  const avgDensity = series.reduce((sum, s) => sum + s.predictedDensityIndex, 0) / (series.length || 1);

  return (
    <div className="flex flex-col rounded-lg border border-border bg-surface p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-display text-sm font-semibold text-text">
          Traffic Forecast
        </h2>

          <span className="text-xs text-text-muted">
            {data.model} · 60 detik ke depan
          </span>
      </div>

      <div className="h-[220px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={series}
            margin={{
              top: 4,
              right: 8,
              left: -20,
              bottom: 0,
            }}
          >
            <defs>
              <linearGradient
                id="forecastFill"
                x1="0"
                y1="0"
                x2="0"
                y2="1"
              >
                <stop
                  offset="0%"
                  stopColor="#38bdf8"
                  stopOpacity={0.35}
                />

                <stop
                  offset="100%"
                  stopColor="#38bdf8"
                  stopOpacity={0}
                />
              </linearGradient>
            </defs>

            <CartesianGrid
              stroke="#232935"
              vertical={false}
            />

            <XAxis
              dataKey="horizonSeconds"
              type="number"
              domain={[0, 60]}
              ticks={[0, 10, 20, 30, 40, 50, 60]}
              tickFormatter={(seconds) => `+${seconds}s`}
              tick={{
                fill: "#5b6472",
                fontSize: 11,
              }}
              axisLine={{
                stroke: "#232935",
              }}
              tickLine={false}
            />

            <YAxis
              tick={{
                fill: "#5b6472",
                fontSize: 11,
              }}
              axisLine={false}
              tickLine={false}
              width={40}
            />

            <Tooltip
              contentStyle={{
                background: "#171c27",
                border: "1px solid #232935",
                borderRadius: 8,
                fontSize: 12,
              }}
              labelFormatter={(seconds) => `+${seconds} detik`}
              formatter={(value, name) => [
                `${value} kendaraan`,
                name,
              ]}
            />

              <Area
                type="monotone"
                dataKey="predictedVehicleCount"
                stroke="#38bdf8"
                strokeWidth={2}
                strokeDasharray="5 5"
                fill="url(#forecastFill)"
                name="Prediksi"
              />
              {current && (
                <Area
                  type="monotone"
                  dataKey="actualVehicleCount"
                  stroke="#2ecc71"
                  strokeWidth={2}
                  fill="none"
                  name="Aktual"
                  dot={{ r: 4, fill: "#2ecc71" }}
                  activeDot={{ r: 6, fill: "#2ecc71" }}
                />
              )}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* ADDITIONAL DETAILS TO FILL SPACE */}
      <div className="mt-4 shrink-0">
        <div className="rounded-md border border-border bg-surface-2 p-3 text-xs">
          <div className="mb-2 font-medium text-text">Ringkasan Prediksi</div>
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between text-text-secondary">
              <span>Puncak Volume</span>
              <span className="font-mono text-text">{maxVehicle.toFixed(1)} <span className="text-text-muted">(+{peakTime}s)</span></span>
            </div>
            <div className="flex items-center justify-between text-text-secondary">
              <span>Antrean Terpanjang</span>
              <span className="font-mono text-text">{maxQueue.toFixed(1)}m</span>
            </div>
            <div className="flex items-center justify-between text-text-secondary">
              <span>Rata-rata Kepadatan</span>
              <span className="font-mono text-text">{avgDensity.toFixed(1)}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
