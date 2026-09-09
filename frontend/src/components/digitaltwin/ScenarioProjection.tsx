"use client";

import { useEffect, useState } from "react";
import type { ScenarioType } from "@/context/ScenarioContext";
import { fetchScenarioForecast, type ScenarioForecastResponse } from "@/lib/scenarioForecast";

const approaches = [["north", "Utara"], ["east", "Timur"], ["south", "Selatan"], ["west", "Barat"]] as const;
const format = (value: number | null | undefined) => typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "—";


export default function ScenarioProjection({ scenario, trafficStateId }: { scenario: ScenarioType; trafficStateId?: number }) {
    const [result, setResult] = useState<ScenarioForecastResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [attempt, setAttempt] = useState(0);
    useEffect(() => {
        if (!trafficStateId) return;
        let cancelled = false;
        fetchScenarioForecast(trafficStateId).then(value => {
            if (!cancelled) setResult(value);
        }).catch(reason => {
            if (!cancelled) setError(reason instanceof Error ? reason.message : "Prediksi belum dapat dihitung.");
        });
        return () => { cancelled = true; };
    }, [trafficStateId, attempt]);

    const projection = result?.trafficStateId === trafficStateId ? result : null;
    const candidate = projection?.candidates.find(item => item.candidateId === scenario.toLowerCase());

    return <section className="mt-5 rounded-2xl border border-border bg-surface p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-base font-semibold">Prediksi 1 Menit — {scenario}</h2>
            <span className="rounded-full bg-surface-2 px-3 py-1 text-xs font-medium text-text-primary">Estimasi dampak pengaturan lampu</span>
        </div>
        {!trafficStateId ? <p role="status" className="mt-4 text-sm text-text-secondary">Pilih kondisi lalu lintas untuk menghitung prediksi skenario.</p>
            : error ? <div role="alert" className="mt-4 rounded-xl border border-border p-4">
                <p className="text-sm text-signal-amber">{error}</p>
                <button type="button" className="mt-3 rounded-lg border border-border px-4 py-2 text-sm font-medium" onClick={() => { setError(null); setAttempt(value => value + 1); }}>Coba hitung lagi</button>
            </div>
            : !candidate ? <p role="status" aria-live="polite" className="mt-4 text-sm text-text-secondary">Menghitung prediksi 60 detik untuk Baseline, Aggressive, dan Balanced dari kondisi yang sama…</p>
            : <>
                <div className="mt-4 grid gap-4 sm:grid-cols-2 2xl:grid-cols-4">
                    {approaches.map(([arm, label]) => <div key={arm} className="min-w-0 rounded-xl border border-border bg-surface-2/50 p-5">
                        <h3 className="text-lg font-semibold">{label}</h3>
                        <dl className="mt-4 divide-y divide-border">
                            {[
                                ["Antrean akhir (kend.)", candidate.finalQueueLengthVehByApproach?.[arm]],
                                ...(typeof candidate.finalSpeedKmhByApproach?.[arm] === "number"
                                    && Number.isFinite(candidate.finalSpeedKmhByApproach[arm])
                                    ? [["Kecepatan akhir simulasi (km/jam)", candidate.finalSpeedKmhByApproach[arm]]]
                                    : []),
                                ["Rata-rata waktu tunggu (s)", candidate.delayByApproachSeconds?.[arm]],
                                ["Puncak antrean (kend.)", candidate.queueLengthVehByApproach?.[arm]],
                            ].map(([metric, value]) => <div key={String(metric)} className="flex items-baseline justify-between gap-3 py-3">
                                <dt className="text-sm text-text-secondary">{metric}</dt>
                                <dd className="shrink-0 font-mono text-xl font-semibold">{format(typeof value === "number" ? value : null)}</dd>
                            </div>)}
                        </dl>
                    </div>)}
                </div>
            </>}

    </section>;
}
