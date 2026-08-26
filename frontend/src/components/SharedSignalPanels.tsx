import { useEffect, useState } from "react";
import RecommendationPanel from "@/components/RecommendationPanel";
import SignalStatusPanel from "@/components/SignalStatusPanel";
import type { SignalStatus, Recommendation } from "@/types/traffic";
import type { ApproachSelection } from "@/lib/intersections";

// Harus sama dengan YELLOW_SECONDS di backend/app/services/signal_service.py
const YELLOW_SECONDS = 4;

/*
 * =========================================================
 * SUMBER KEBENARAN: SERVER, BUKAN SIMULASI DI BROWSER
 * =========================================================
 *
 * activeSignal.currentPhase/remainingSeconds itu hasil hitungan
 * "lazy tick" SignalService di backend (lihat CLAUDE.md/item 1.7) --
 * kapan fase pindah, berapa lama tiap lengan, itu semua diputuskan
 * SERVER, dipoll tiap 5 detik dari page.tsx.
 *
 * Di sini CUMA diturunkan jadi countdown per-detik yang halus di
 * antara dua poll (resync ke angka server tiap poll baru), TIDAK
 * boleh menyimulasikan sendiri kapan fase pindah -- kalau tidak,
 * dua browser bisa menampilkan fase yang berbeda dari kenyataan di
 * server, dan drift makin lama makin lebar.
 */
export default function SharedSignalPanels({
  activeRecommendation,
  activeSignal,
  selectedApproach,
}: {
  activeRecommendation: Recommendation | null;
  activeSignal: SignalStatus;
  selectedApproach?: ApproachSelection;
}) {
  const [displayRemaining, setDisplayRemaining] = useState(
    activeSignal.remainingSeconds
  );

  useEffect(() => {
    setDisplayRemaining(activeSignal.remainingSeconds);
  }, [activeSignal.remainingSeconds, activeSignal.currentPhase]);

  useEffect(() => {
    const interval = setInterval(() => {
      setDisplayRemaining((current) => Math.max(0, current - 1));
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  const visualPhase = activeSignal.currentPhase || null;
  const visualPhaseState: "GREEN" | "YELLOW" =
    displayRemaining <= YELLOW_SECONDS ? "YELLOW" : "GREEN";
  const visualRemaining = displayRemaining;

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
