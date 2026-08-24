"use client";

import { useEffect, useState } from "react";
import type { SignalStatus } from "@/types/traffic";

const INTERSECTION_ID = "simpang4-pingit";
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export function useTrafficSimulation(): SignalStatus | null {
    const [signal, setSignal] = useState<SignalStatus | null>(null);

    useEffect(() => {
        const interval = setInterval(async () => {
            try {
                const res = await fetch(`${API_BASE_URL}/api/v1/simulation/state`);
                if (!res.ok) {
                    setSignal(null);
                    return;
                }
                const data = await res.json();
                
                if (!data.running || !data.signals || data.signals.length === 0) {
                    setSignal(null);
                    return;
                }

                const remaining = Math.floor(data.signals[0].remainingSeconds);
                const phaseIndex = data.signals[0].phase;
                
                let currentPhase = "NS";
                let phaseName = "Fase Utara-Selatan";
                
                if (phaseIndex === 0) {
                    currentPhase = "NS";
                    phaseName = "Fase Utara-Selatan";
                } else if (phaseIndex === 1) {
                    currentPhase = "NS_AMBER";
                    phaseName = "Fase Utara-Selatan — Amber";
                } else if (phaseIndex === 2) {
                    currentPhase = "EW";
                    phaseName = "Fase Timur-Barat";
                } else if (phaseIndex === 3) {
                    currentPhase = "EW_AMBER";
                    phaseName = "Fase Timur-Barat — Amber";
                }

                setSignal({
                    intersectionId: INTERSECTION_ID,
                    timestamp: new Date().toISOString(),
                    currentPhase,
                    phaseName,
                    remainingSeconds: remaining,
                    cycleTimeSeconds: 76,
                    source: "mock",
                });
            } catch (err) {
                setSignal(null);
            }
        }, 500);

        return () => clearInterval(interval);
    }, []);

    return signal;
}