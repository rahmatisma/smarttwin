import type { DigitalTwinScenarioResponse } from "./supabaseData";

export interface ScenarioForecastResponse extends DigitalTwinScenarioResponse {
    trafficStateId: number;
    inputTimestamp: string;
    predictionTimestamp: string;
    horizonSeconds: 60;
    initialPhase: "north";
    assumptions: string[];
}

export function isScenarioForecastForState(result: ScenarioForecastResponse, stateId: number): boolean {
    const arms = ["north", "east", "south", "west"];
    return result.status === "completed" && result.trafficStateId === stateId && result.horizonSeconds === 60
        && Date.parse(result.predictionTimestamp) - Date.parse(result.inputTimestamp) === 60_000
        && ["baseline", "aggressive", "balanced"].every(id => {
            const candidate = result.candidates?.find(item => item.candidateId === id);
            return candidate?.evaluation?.trafficStateId === stateId
                && candidate.evaluation.durationSeconds === 60
                && candidate.evaluation.completedSteps === 60
                && candidate.evaluation.demandSource === "traffic-state-snapshot"
                && arms.every(arm => {
                    const value = candidate.finalQueueLengthVehByApproach?.[arm];
                    return typeof value === "number" && Number.isFinite(value) && value >= 0;
                });
        });
}

const completed = new Map<number, ScenarioForecastResponse>();
const pending = new Map<number, Promise<ScenarioForecastResponse>>();

export function fetchScenarioForecast(stateId: number): Promise<ScenarioForecastResponse> {
    const cached = completed.get(stateId);
    if (cached) return Promise.resolve(cached);
    const active = pending.get(stateId);
    if (active) return active;
    const request = (async () => {
        const { supabase } = await import("./supabaseClient");
        const { data } = await supabase.auth.getSession();
        const headers: Record<string, string> = { "Content-Type": "application/json" };
        if (data.session?.access_token) headers.Authorization = `Bearer ${data.session.access_token}`;
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"}/api/v1/digital-twin/forecast`, {
            method: "POST", headers, body: JSON.stringify({ trafficStateId: stateId }),
            signal: AbortSignal.timeout(185_000),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Prediksi skenario belum dapat dihitung.");
        if (!isScenarioForecastForState(result, stateId)) throw new Error("Prediksi belum sesuai dengan kondisi terpilih. Silakan coba lagi.");
        completed.set(stateId, result);
        if (completed.size > 16) completed.delete(completed.keys().next().value!);
        return result as ScenarioForecastResponse;
    })().finally(() => pending.delete(stateId));
    pending.set(stateId, request);
    return request;
}
