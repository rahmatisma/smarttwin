"use client";

import { useEffect, useState } from "react";
import { fetchDigitalTwinScenarios, type DigitalTwinScenarioResponse } from "@/lib/supabaseData";
import type { ScenarioType } from "@/context/ScenarioContext";
import type { ForecastResponse, TrafficState } from "@/types/traffic";

const approaches = [["north", "Utara"], ["east", "Timur"], ["south", "Selatan"], ["west", "Barat"]] as const;
const format = (value: number | null | undefined) => typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "\u2014";
const time = (value: string) => new Date(value).toLocaleString("id-ID");

function TrafficForecast({ forecast, traffic }: { forecast: ForecastResponse | null; traffic: TrafficState | null }) {
    return <section className="mt-5 rounded-2xl border border-border bg-surface p-5 shadow-sm">
        <h2 className="text-base font-semibold">Prediksi per Lengan</h2>
        <p className="mt-2 text-sm text-text-secondary">{forecast ? "Horizon prediksi: " + forecast.horizonMinutes + " menit. " : ""}Prediksi lalu lintas belum memperhitungkan perubahan sinyal skenario.</p>
        {forecast?.inputTimestamp && <p className="mt-2 text-sm text-text-secondary">Acuan data: {time(forecast.inputTimestamp)} - model {forecast.model}</p>}
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
                        ["Kecepatan (km/jam)", predicted?.predictedSpeedKmh],
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
type LiveResult = { scenario: string; time: number; paused: boolean; delay: Record<string, number | null>; queue: Record<string, number>; throughput: Record<string, number>; los: Record<string, string | null> };

export default function ScenarioComparison({ forecast, traffic, scenario, live }: { forecast: ForecastResponse | null; traffic: TrafficState | null; scenario: ScenarioType; live: LiveResult | null }) {
    if (scenario === "Traffic Realtime") return <TrafficForecast forecast={forecast} traffic={traffic} />;
    return <><ScenarioEvaluation key={scenario} scenario={scenario} live={live} trafficStateId={traffic?.trafficStateId} />
        <TrafficForecast forecast={forecast} traffic={traffic} /></>;
}

function ScenarioEvaluation({ scenario, live, trafficStateId }: { scenario: ScenarioType; live: LiveResult | null; trafficStateId?: number }) {
    const [evaluation, setEvaluation] = useState<DigitalTwinScenarioResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [evaluating, setEvaluating] = useState(false);
    const [evaluationError, setEvaluationError] = useState<string | null>(null);
    async function evaluate() {
        if (!trafficStateId) return;
        setEvaluating(true); setEvaluationError(null);
        try {
            const response = await fetch((process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000") + "/api/v1/digital-twin/evaluate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ trafficStateId }) });
            const result = await response.json();
            if (!response.ok) throw new Error(result.detail ?? "Evaluasi gagal.");
            setEvaluation(result); setEvaluationUnavailable(false);
        } catch (error) { setEvaluationError(error instanceof Error ? error.message : "Evaluasi gagal."); }
        finally { setEvaluating(false); setLoading(false); }
    }
    const [lastLive, setLastLive] = useState<LiveResult | null>(null);
    const [evaluationUnavailable, setEvaluationUnavailable] = useState(false);
    const validLive = live?.scenario === scenario && approaches.some(([approach]) => live.delay[approach] != null || live.queue[approach] != null);
    if (validLive && lastLive !== live) setLastLive(live);
    const displayedLive = validLive ? live : lastLive;
    useEffect(() => {
        let cancelled = false;
        let timer: ReturnType<typeof setTimeout>;
        async function poll() {
            const result = await fetchDigitalTwinScenarios();
            if (cancelled) return;
            const available = result?.status === "completed" && result.candidates.some(candidate => candidate.candidateId === scenario.toLowerCase() && candidate.evaluation?.trafficStateId === trafficStateId && candidate.evaluation?.demandSource === "traffic-state-snapshot" && approaches.some(([approach]) => candidate.delayByApproachSeconds?.[approach] != null || candidate.queueLengthVehByApproach?.[approach] != null));
            if (available) setEvaluation(result);
            setEvaluationUnavailable(!available);
            setLoading(false);
            timer = setTimeout(poll, 5000);
        }
        void poll();
        return () => { cancelled = true; clearTimeout(timer); };
    }, [scenario, trafficStateId]);
    const candidate = evaluation?.candidates.find(item => item.candidateId === scenario.toLowerCase());
    const hasResults = candidate && approaches.some(([approach]) =>
        candidate.delayByApproachSeconds?.[approach] != null || candidate.queueLengthVehByApproach?.[approach] != null || candidate.throughputVehByApproach?.[approach] != null);
    const useLive = !hasResults && displayedLive !== null;
    const result = useLive ? { delayByApproachSeconds: displayedLive.delay, queueLengthVehByApproach: displayedLive.queue, throughputVehByApproach: displayedLive.throughput, losByApproach: displayedLive.los } : candidate;
    const hasDisplay = useLive || hasResults;
    return <section className="mt-5 rounded-2xl border border-border bg-surface p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-semibold">{useLive ? "Hasil Simulasi" : "Hasil Evaluasi"} {scenario} per Lengan</h2>
            {!useLive && hasResults && evaluation?.updatedAt && <span className="text-sm text-text-secondary">Evaluasi: {time(evaluation.updatedAt)}</span>}
        </div>
        <p className="mt-2 text-sm text-text-secondary">{useLive && displayedLive ? (validLive ? "Sesi SUMO" : "Hasil SUMO terakhir - menunggu pembaruan") + " - " + Math.floor(displayedLive.time) + " detik" + (displayedLive.paused ? " (dijeda)" : "") : "Evaluasi " + scenario + (evaluationUnavailable && hasResults ? " terakhir - menunggu pembaruan." : ".")}</p>
        <div className="my-4 flex flex-wrap items-center gap-3">
            <button type="button" disabled={!trafficStateId || evaluating} onClick={() => void evaluate()} className="rounded-lg border border-border bg-surface-2 px-4 py-2 text-sm font-medium disabled:opacity-50">{evaluating ? "Mengevaluasi tiga skenario..." : "Evaluasi 3 skenario pada kondisi ini"}</button>
            {evaluationError && <p role="alert" className="text-sm text-signal-amber">{evaluationError}</p>}
        </div>
        {candidate?.evaluation && !useLive && <p className="mb-4 text-sm text-text-secondary">Kondisi #{candidate.evaluation.trafficStateId} - durasi {candidate.evaluation.durationSeconds} s - seed {candidate.evaluation.seed}. ID evaluasi: {candidate.evaluation.id}</p>}
        {!hasDisplay ? <p role="status" className="mt-4 text-sm text-text-secondary">{loading ? "Memuat evaluasi " + scenario + "..." : "Hasil evaluasi per lengan untuk " + scenario + " belum tersedia."}</p> :
            <div className="mt-4 grid gap-4 sm:grid-cols-2 2xl:grid-cols-4">
                {approaches.map(([approach, label]) => <div key={approach} className="min-w-0 rounded-xl border border-border bg-surface-2/50 p-5">
                    <div className="flex items-center justify-between gap-2"><h3 className="text-lg font-semibold">{label}</h3><span className="font-mono text-xl font-semibold">LOS {result?.losByApproach?.[approach] ?? "\u2014"}</span></div>
                    <dl className="mt-4 divide-y divide-border">
                        {[
                            ["Delay (s)", result?.delayByApproachSeconds?.[approach]],
                            [useLive ? "Antrean (kend.)" : "Puncak antrean (kend.)", result?.queueLengthVehByApproach?.[approach]],
                            [useLive ? "Arus (kend./menit)" : "Lewat selama evaluasi (kend.)", result?.throughputVehByApproach?.[approach]],
                        ].map(([metric, value]) => <div key={String(metric)} className="flex flex-wrap items-baseline justify-between gap-2 py-3"><dt className="text-sm text-text-secondary">{metric}</dt><dd className="font-mono text-xl font-semibold">{format(typeof value === "number" ? value : null)}</dd></div>)}
                    </dl>
                </div>)}
            </div>}
    </section>;
}