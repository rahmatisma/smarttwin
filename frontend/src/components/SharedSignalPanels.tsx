import { useEffect, useState, useRef } from "react";
import RecommendationPanel from "@/components/RecommendationPanel";
import SignalStatusPanel from "@/components/SignalStatusPanel";
import type { SignalStatus, Recommendation } from "@/types/traffic";
import type { ApproachSelection } from "@/lib/intersections";

export default function SharedSignalPanels({
  activeRecommendation,
  activeSignal,
  selectedApproach,
}: {
  activeRecommendation: Recommendation | null;
  activeSignal: SignalStatus;
  selectedApproach?: ApproachSelection;
}) {
  const activePhase = activeSignal.currentPhase;
  const activeRemainingSeconds = activeSignal.remainingSeconds;
  
  const [visualPhase, setVisualPhase] = useState<string | null>(null);
  const [visualPhaseState, setVisualPhaseState] = useState<"GREEN" | "YELLOW">("GREEN");
  const [visualRemaining, setVisualRemaining] = useState<number>(0);

  const syncedPhaseRef = useRef<string | null>(null);
  const phases = activeRecommendation?.cyclePlan?.phases ?? [];

  useEffect(() => {
    if (!phases.length) return;
    
    if (activePhase && activePhase !== syncedPhaseRef.current) {
      const match = phases.find(p => p.approach === activePhase);
      if (match) {
        syncedPhaseRef.current = activePhase;
        setVisualPhase(match.approach);
        setVisualPhaseState("GREEN");
        setVisualRemaining(activeRemainingSeconds ?? match.greenSeconds);
        return;
      }
    }

    if (!visualPhase) {
      setVisualPhase(phases[0].approach);
      setVisualPhaseState("GREEN");
      setVisualRemaining(phases[0].greenSeconds);
    }
  }, [activePhase, activeRemainingSeconds, phases, visualPhase]);

  useEffect(() => {
    if (!phases.length || !visualPhase) return;

    const interval = setInterval(() => {
      setVisualRemaining((current) => Math.max(0, current - 1));
    }, 1000);

    return () => clearInterval(interval);
  }, [phases, visualPhase]);

  useEffect(() => {
    if (visualRemaining === 0 && phases.length > 0 && visualPhase) {
      const currentIndex = phases.findIndex(p => p.approach === visualPhase);
      if (currentIndex !== -1) {
        if (visualPhaseState === "GREEN") {
          setVisualPhaseState("YELLOW");
          setVisualRemaining(5);
        } else {
          const nextIndex = (currentIndex + 1) % phases.length;
          const nextPhase = phases[nextIndex];
          setVisualPhase(nextPhase.approach);
          setVisualPhaseState("GREEN");
          setVisualRemaining(nextPhase.greenSeconds);
        }
      }
    }
  }, [visualRemaining, phases, visualPhase, visualPhaseState]);

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
      />

      <SignalStatusPanel
        signal={activeSignal}
        recommendation={activeRecommendation}
        sharedVisualPhase={visualPhase}
        sharedVisualPhaseState={visualPhaseState}
        sharedVisualRemaining={visualRemaining}
      />
    </div>
  );
}
