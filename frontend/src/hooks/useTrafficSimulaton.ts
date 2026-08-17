"use client";

import { useEffect, useState } from "react";
import type { SignalStatus } from "@/types/traffic";

const CYCLE = [
    {
        activePhase: ["north", "south"] as const,
        phaseName: "Fase 1 — Utara-Selatan",
        color: "green" as const,
        duration: 25,
    },
    {
        activePhase: ["north", "south"] as const,
        phaseName: "Fase 1 — Utara-Selatan",
        color: "amber" as const,
        duration: 3,
    },
    {
        activePhase: ["east", "west"] as const,
        phaseName: "Fase 2 — Timur-Barat",
        color: "green" as const,
        duration: 45,
    },
    {
        activePhase: ["east", "west"] as const,
        phaseName: "Fase 2 — Timur-Barat",
        color: "amber" as const,
        duration: 3,
    },
];

export function useTrafficSimulation(): SignalStatus {
    const [elapsed, setElapsed] = useState(0);

    useEffect(() => {
        const interval = setInterval(() => {
            setElapsed((value) => value + 1);
        }, 1000);

        return () => clearInterval(interval);
    }, []);

    const cycleLength = CYCLE.reduce(
        (total, phase) => total + phase.duration,
        0
    );

    const position = elapsed % cycleLength;

    let accumulated = 0;

    for (const phase of CYCLE) {
        const phaseEnd = accumulated + phase.duration;

        if (position < phaseEnd) {
            return {
                activePhase: [...phase.activePhase],
                phaseName: phase.phaseName,
                color: phase.color,
                secondsRemaining: phaseEnd - position,
                cycleBreakdown: {
                    greenS: 25,
                    yellowS: 3,
                    redS: 45,
                },
            };
        }

        accumulated = phaseEnd;
    }

    return {
        activePhase: ["north", "south"],
        phaseName: "Fase 1 — Utara-Selatan",
        color: "green",
        secondsRemaining: 25,
        cycleBreakdown: {
            greenS: 25,
            yellowS: 3,
            redS: 45,
        },
    };
}