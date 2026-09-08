"use client";

import ScenarioProjection from "./ScenarioProjection";
import type { ScenarioType } from "@/context/ScenarioContext";
import type { ForecastResponse, TrafficState } from "@/types/traffic";

const approaches = [["north", "Utara"], ["east", "Timur"], ["south", "Selatan"], ["west", "Barat"]] as const;
const format = (value: number | null | undefined) => typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "\u2014";
const time = (value: string) => new Date(value).toLocaleString("id-ID");

function TrafficForecast({ forecast, traffic }: { forecast: ForecastResponse | null; traffic: TrafficState | null }) {
    return <section className="mt-5 rounded-2xl border border-border bg-surface p-5 shadow-sm">
        <h2 className="text-base font-semibold">Prediksi Lalu Lintas Umum</h2>
        <p className="mt-2 text-sm text-text-secondary">{forecast ? "Horizon prediksi: " + forecast.horizonMinutes + " menit. " : ""}Perkiraan berdasarkan riwayat lalu lintas. Pilih Baseline, Aggressive, atau Balanced untuk melihat estimasi dampak pengaturan lampunya.</p>
        {!forecast?.predictionsByApproach ? <p className="mt-4 text-sm text-text-secondary">Prediksi per lengan belum tersedia.</p> : <>
            {forecast.fallbackUsed && <p className="mt-2 text-sm text-signal-amber">Menggunakan prediksi cadangan: {forecast.forecastSource ?? forecast.model}.</p>}
            <div className="mt-4 grid gap-4 sm:grid-cols-2 2xl:grid-cols-4">
                {approaches.map(([approach, label]) => {
                    const series = forecast.predictionsByApproach?.[approach];
                    const predicted = series?.length ? series[series.length - 1] : null;
                    const future = predicted && traffic ? new Date(predicted.timestamp).getTime() > new Date(traffic.windowEnd).getTime() : true;
                    const rows = [
                        ["Antrean (kend.)", predicted?.predictedQueueLengthVeh],
                        ["Antrean (m, estimasi)", predicted?.predictedQueueLengthMEst],
                        ["Indeks kepadatan", predicted?.predictedDensityIndex],
                    ] as const;
                    return <div key={approach} className="min-w-0 rounded-xl border border-border bg-surface-2/50 p-5">
                        <h3 className="text-lg font-semibold">{label}</h3>
                        <p className="mt-1 text-sm text-text-secondary">{predicted ? "Waktu prediksi: " + time(predicted.timestamp) : "Prediksi belum tersedia"}</p>
                        {!future && <p className="mt-1 text-sm text-signal-amber">Menunggu pembaruan prediksi.</p>}
                        <dl className="mt-4 divide-y divide-border">
                            {rows.map(([metric, next]) => <div key={metric} className="flex flex-wrap items-baseline justify-between gap-2 py-3">
                                <dt className="text-sm text-text-secondary">{metric}</dt>
                                <dd className="font-mono text-xl font-semibold">{format(future ? next : null)}</dd>
                            </div>)}
                        </dl>
                    </div>;
                })}
            </div>
        </>}
    </section>;
}
export default function ScenarioComparison({ forecast, traffic, scenario }: { forecast: ForecastResponse | null; traffic: TrafficState | null; scenario: ScenarioType }) {
    if (scenario === "Traffic Realtime") return <TrafficForecast forecast={forecast} traffic={traffic} />;
    return <ScenarioProjection scenario={scenario} trafficStateId={traffic?.trafficStateId} />;
}
