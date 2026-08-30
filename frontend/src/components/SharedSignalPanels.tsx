import { useEffect, useState } from "react";
import RecommendationPanel from "@/components/RecommendationPanel";
import SignalStatusPanel from "@/components/SignalStatusPanel";
import type { SignalStatus, Recommendation } from "@/types/traffic";
import type { ApproachSelection } from "@/lib/intersections";
import { useScenario } from "@/context/ScenarioContext";

// Harus sama dengan YELLOW_SECONDS di backend/app/services/signal_service.py
const YELLOW_SECONDS = 4;

export default function SharedSignalPanels({
  activeRecommendation,
  activeSignal,
  selectedApproach,
}: {
  activeRecommendation: Recommendation | null;
  activeSignal: SignalStatus;
  selectedApproach?: ApproachSelection;
}) {
  const { scenario } = useScenario();

  const isInitialLoading = activeSignal.source === "mock" && scenario === "Traffic Realtime" && !activeRecommendation;

  const visualPhase = activeSignal.currentPhase || null;
  const [now, setNow] = useState(Date.now());

  // Force re-render setiap 1 detik untuk menghitung ulang elapsedSeconds
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const elapsedSeconds = Math.max(0, Math.floor((now - new Date(activeSignal.timestamp).getTime()) / 1000));
  const visualRemaining = Math.max(0, activeSignal.remainingSeconds - elapsedSeconds);

  const visualPhaseState: "GREEN" | "YELLOW" = activeSignal.state ??
    (visualRemaining <= YELLOW_SECONDS ? "YELLOW" : "GREEN");

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <RecommendationPanel
        recommendation={activeRecommendation}
        signal={activeSignal}
        selectedApproach={selectedApproach}
        activeCycleSeconds={activeSignal.cycleTimeSeconds}
        sharedVisualPhase={visualPhase}
        sharedVisualPhaseState={visualPhaseState}
        sharedVisualRemaining={visualRemaining}
        elapsedSeconds={elapsedSeconds}
        isLoading={isInitialLoading}
      />

      <SignalStatusPanel
        signal={activeSignal}
        recommendation={activeRecommendation}
        sharedVisualPhase={visualPhase}
        sharedVisualPhaseState={visualPhaseState}
        sharedVisualRemaining={visualRemaining}
        elapsedSeconds={elapsedSeconds}
        isLoading={isInitialLoading}
      />
    </div>
  );
}
