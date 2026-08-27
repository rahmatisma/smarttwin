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
        const response = await fetch(`${API_BASE_URL}/api/v1/simulation/state`);
        if (!response.ok) return setSignal(null);
        const data = await response.json();
        const liveSignal = data.signals?.[0];
        if (!data.running || !liveSignal?.activeApproach) return setSignal(null);

        const currentPhase = liveSignal.activeApproach;
        const isYellow = liveSignal.state === "YELLOW";
        setSignal({
          intersectionId: INTERSECTION_ID,
          timestamp: new Date().toISOString(),
          currentPhase,
          phaseName: `Fase ${currentPhase}${isYellow ? " — Kuning" : " — Hijau"}`,
          remainingSeconds: Math.floor(liveSignal.remainingSeconds),
          cycleTimeSeconds: data.cyclePlan?.totalCycleSeconds ?? 0,
          source: data.cyclePlan?.source ?? "sumo-live",
        });
      } catch {
        setSignal(null);
      }
    }, 500);
    return () => clearInterval(interval);
  }, []);

  return signal;
}
