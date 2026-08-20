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

import type { ForecastResponse } from "@/types/traffic";

function formatForecastData(data: ForecastResponse) {
  return data.predictions.map((prediction) => {
    const currentTime = new Date(prediction.timestamp);

    return {
      horizonMinutes: Math.round(
        (currentTime.getTime() -
          new Date(data.predictions[0].timestamp).getTime()) /
          60000
      ),
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

export default function ForecastChart({
  data,
}: {
  data?: ForecastResponse | null;
}) {
  if (!data || !data.predictions || data.predictions.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-display text-sm font-semibold text-text">
            Traffic Forecast
          </h2>

          <span className="text-xs text-text-muted">
            kendaraan / 15 menit
          </span>
        </div>

        <div className="flex h-40 items-center justify-center">
          <span className="text-xs text-text-muted">
            Data forecast belum tersedia dari backend
          </span>
        </div>
      </div>
    );
  }

  const series = formatForecastData(data);

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-display text-sm font-semibold text-text">
          Traffic Forecast
        </h2>

        <span className="text-xs text-text-muted">
          kendaraan / 15 menit
        </span>
      </div>

      <div className="h-40 w-full">
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
              dataKey="horizonMinutes"
              tickFormatter={(m) => `+${m}m`}
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
              labelFormatter={(m) => `+${m} menit`}
              formatter={(value) => [
                `${value} kendaraan`,
                "Prediksi",
              ]}
            />

            <Area
              type="monotone"
              dataKey="predictedVehicleCount"
              stroke="#38bdf8"
              strokeWidth={2}
              fill="url(#forecastFill)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}