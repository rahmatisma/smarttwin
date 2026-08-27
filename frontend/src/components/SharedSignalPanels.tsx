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

  let transformedRecommendation = activeRecommendation;
  let transformedSignal = activeSignal;

  if (scenario !== "Traffic Realtime" && activeRecommendation && activeRecommendation.cyclePlan) {
    const newPhases = activeRecommendation.cyclePlan.phases.map(p => {
        const originalGreen = p.greenSeconds;
        let newGreen = originalGreen;
        if (scenario === "Aggressive") {
            newGreen = Math.min(60, Math.round(originalGreen * 1.2));
        } else if (scenario === "Balanced") {
            newGreen = Math.round((originalGreen + 15) / 2);
        }
        return { ...p, greenSeconds: newGreen };
    });
    
    const newCycleLength = newPhases.reduce((acc, p) => acc + p.greenSeconds + YELLOW_SECONDS, 0);
    
    transformedRecommendation = {
        ...activeRecommendation,
        cyclePlan: {
            ...activeRecommendation.cyclePlan,
            cycleLengthSeconds: newCycleLength,
            phases: newPhases
        }
    };

    const newSignalPhases = { ...activeSignal.phases };
    Object.keys(newSignalPhases).forEach(key => {
        const phase = newSignalPhases[key];
        const recPhase = newPhases.find(rp => rp.approach === key);
        if (recPhase) {
            newSignalPhases[key] = {
                ...phase,
                durationSeconds: recPhase.greenSeconds + YELLOW_SECONDS,
            };
        }
    });

    let newRemaining = activeSignal.remainingSeconds;
    const currentRecPhase = activeRecommendation.cyclePlan.phases.find(p => p.approach === activeSignal.currentPhase);
    const newRecPhase = newPhases.find(p => p.approach === activeSignal.currentPhase);
    
    if (currentRecPhase && newRecPhase) {
        const originalPhaseDuration = currentRecPhase.greenSeconds + YELLOW_SECONDS;
        const newPhaseDuration = newRecPhase.greenSeconds + YELLOW_SECONDS;
        if (originalPhaseDuration > 0) {
            const progress = activeSignal.remainingSeconds / originalPhaseDuration;
            newRemaining = Math.max(0, Math.round(progress * newPhaseDuration));
        }
    }

    transformedSignal = {
        ...activeSignal,
        cycleTimeSeconds: newCycleLength,
        phases: newSignalPhases,
        remainingSeconds: newRemaining,
        // Optional: flag it so SignalStatusPanel knows it's simulated visually
        source: "mock"
    };
  }

  const isInitialLoading = transformedSignal.source === "mock" && scenario === "Traffic Realtime" && !transformedRecommendation;

  const visualPhase = transformedSignal.currentPhase || null;
  const visualPhaseState: "GREEN" | "YELLOW" =
    transformedSignal.remainingSeconds <= YELLOW_SECONDS ? "YELLOW" : "GREEN";
  const visualRemaining = transformedSignal.remainingSeconds;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <RecommendationPanel
        recommendation={transformedRecommendation}
        signal={transformedSignal}
        selectedApproach={selectedApproach}
        activeCycleSeconds={transformedSignal.cycleTimeSeconds}
        sharedVisualPhase={visualPhase}
        sharedVisualPhaseState={visualPhaseState}
        sharedVisualRemaining={visualRemaining}
        isLoading={isInitialLoading}
      />

      <SignalStatusPanel
        signal={transformedSignal}
        recommendation={transformedRecommendation}
        sharedVisualPhase={visualPhase}
        sharedVisualPhaseState={visualPhaseState}
        sharedVisualRemaining={visualRemaining}
        isLoading={isInitialLoading}
      />
    </div>
  );
}
