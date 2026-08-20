"use client";

import { useEffect, useState } from "react";

import type { SignalStatus } from "@/types/traffic";

/*
 * =========================================================
 * LOCAL SIGNAL SIMULATION
 * =========================================================
 *
 * Sementara backend signal belum tersedia, kita simulasi
 * pergantian fase di frontend.
 *
 * PENTING:
 * Output hook tetap mengikuti SignalStatus dari
 * data-contract.md.
 *
 * Tidak menggunakan:
 * - activePhase
 * - color
 * - secondsRemaining
 * - cycleBreakdown
 *
 * karena field-field tersebut tidak ada di contract.
 *
 * Jika backend /api/signal/status sudah tersedia,
 * hook ini nanti bisa diganti menjadi fetch API.
 */

const CYCLE = [
    {
        currentPhase: "NS",
        phaseName: "Fase Utara-Selatan",
        duration: 25,
    },
    {
        currentPhase: "NS_AMBER",
        phaseName: "Fase Utara-Selatan — Amber",
        duration: 3,
    },
    {
        currentPhase: "EW",
        phaseName: "Fase Timur-Barat",
        duration: 45,
    },
    {
        currentPhase: "EW_AMBER",
        phaseName: "Fase Timur-Barat — Amber",
        duration: 3,
    },
] as const;

const INTERSECTION_ID = "simpang4-pingit";

export function useTrafficSimulation(): SignalStatus {
    const [elapsed, setElapsed] = useState(0);

    useEffect(() => {
        const interval = setInterval(() => {
            setElapsed((value) => value + 1);
        }, 1000);

        return () => clearInterval(interval);
    }, []);

    const cycleTimeSeconds = CYCLE.reduce(
        (total, phase) => total + phase.duration,
        0
    );

    const position = elapsed % cycleTimeSeconds;

    let accumulated = 0;

    for (const phase of CYCLE) {
        const phaseEnd = accumulated + phase.duration;

        if (position < phaseEnd) {
            return {
                intersectionId: INTERSECTION_ID,

                timestamp: new Date().toISOString(),

                currentPhase: phase.currentPhase,

                phaseName: phase.phaseName,

                remainingSeconds: phaseEnd - position,

                cycleTimeSeconds,

                source: "mock",
            };
        }

        accumulated = phaseEnd;
    }

    /*
     * Fallback.
     *
     * Seharusnya hampir tidak pernah dipanggil karena
     * position selalu berada di dalam cycle.
     */
    return {
        intersectionId: INTERSECTION_ID,

        timestamp: new Date().toISOString(),

        currentPhase: "NS",

        phaseName: "Fase Utara-Selatan",

        remainingSeconds: CYCLE[0].duration,

        cycleTimeSeconds,

        source: "mock",
    };
}