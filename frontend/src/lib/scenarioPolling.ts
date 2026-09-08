import type { DigitalTwinScenarioResponse } from "./supabaseData";

export function createScenarioPoller({
    baseUrl,
    fetcher = fetch,
    now = Date.now,
    timeoutMs = 8000,
    onUnavailable = () => console.warn("Layanan skenario belum merespons. Mencoba lagi dalam 15 detik."),
}: {
    baseUrl: string;
    fetcher?: typeof fetch;
    now?: () => number;
    timeoutMs?: number;
    onUnavailable?: () => void;
}) {
    const pending = new Map<string, Promise<DigitalTwinScenarioResponse | null>>();
    const recent = new Map<string, { retryAt: number; value: DigitalTwinScenarioResponse | null }>();

    return function poll(intersectionId: string): Promise<DigitalTwinScenarioResponse | null> {
        const active = pending.get(intersectionId);
        if (active) return active;
        const cached = recent.get(intersectionId);
        if (cached && now() < cached.retryAt) return Promise.resolve(cached.value);

        const request = (async () => {
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), timeoutMs);
            let value: DigitalTwinScenarioResponse | null = null;
            let retryIn = 15_000;
            try {
                const response = await fetcher(`${baseUrl}/api/v1/digital-twin/scenarios/latest?intersectionId=${encodeURIComponent(intersectionId)}`, {
                    signal: controller.signal,
                });
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                value = await response.json() as DigitalTwinScenarioResponse;
                retryIn = 5000;
            } catch {
                onUnavailable();
            } finally {
                clearTimeout(timer);
            }
            recent.set(intersectionId, { value, retryAt: now() + retryIn });
            if (recent.size > 16) recent.delete(recent.keys().next().value!);
            return value;
        })().finally(() => pending.delete(intersectionId));
        pending.set(intersectionId, request);
        return request;
    };
}
