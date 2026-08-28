import type { SignalStatus, Recommendation } from "@/types/traffic";
import { APPROACH_OPTIONS } from "@/lib/intersections";

// Harus sama dengan YELLOW_SECONDS di backend/app/services/signal_service.py
const YELLOW_SECONDS = 4;

function approachLabel(approach: string): string {
  const option = APPROACH_OPTIONS.find((opt) => opt.id === approach);
  return option ? option.name : approach;
}

export default function SignalStatusPanel({
  signal,
  recommendation,
  sharedVisualPhase,
  sharedVisualPhaseState,
  sharedVisualRemaining,
  isLoading,
}: {
  signal: SignalStatus;
  recommendation?: Recommendation | null;
  sharedVisualPhase: string | null;
  sharedVisualPhaseState: "GREEN" | "YELLOW";
  sharedVisualRemaining: number;
  isLoading?: boolean;
}) {
  const showLoading = Boolean(isLoading && signal.source === "mock");
  const displaySignal = signal;

  if (showLoading) {
    return (
      <div className="rounded-lg border border-border bg-surface p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="flex items-center gap-2 font-display text-sm font-semibold text-text">
            Signal Status
            <span className="rounded-full bg-accent-blue/10 px-2 py-0.5 text-[10px] font-medium text-accent-blue ring-1 ring-accent-blue/20">
              Live
            </span>
          </h2>
          <span className="text-xs text-text-muted">
            Memuat...
          </span>
        </div>
        <div className="flex min-h-[320px] items-center justify-center rounded-md border border-border bg-surface-2 px-4 text-center">
          <div className="flex flex-col items-center justify-center space-y-3">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-text-muted border-t-transparent"></div>
            <p className="text-xs text-text-muted">
              Memuat status sinyal...
            </p>
          </div>
        </div>
      </div>
    );
  }

  const phases = recommendation?.cyclePlan?.phases ?? [];
  const hasRecommendation = phases.length > 0 && sharedVisualPhase !== null;

  // Calculations for Cycle Progress and Next Phase
  let totalCycleDuration = 0;
  let elapsedTime = 0;
  let nextPhaseApproach = "";
  let nextPhaseWaitTime = 0;

  if (hasRecommendation) {
    const currentIndex = phases.findIndex(p => p.approach === sharedVisualPhase);
    
    phases.forEach((p, index) => {
      totalCycleDuration += p.greenSeconds + YELLOW_SECONDS;

      if (currentIndex !== -1) {
        if (index < currentIndex) {
          elapsedTime += p.greenSeconds + YELLOW_SECONDS;
        } else if (index === currentIndex) {
          if (sharedVisualPhaseState === "GREEN") {
            elapsedTime += p.greenSeconds - sharedVisualRemaining;
          } else {
            elapsedTime += p.greenSeconds + (YELLOW_SECONDS - sharedVisualRemaining);
          }
        }
      }
    });

    if (currentIndex !== -1) {
      const nextIndex = (currentIndex + 1) % phases.length;
      nextPhaseApproach = phases[nextIndex].approach;

      nextPhaseWaitTime = sharedVisualRemaining;
      if (sharedVisualPhaseState === "GREEN") {
        nextPhaseWaitTime += YELLOW_SECONDS;
      }
    }
  }

  const progressPercent = totalCycleDuration > 0 ? Math.min(100, Math.max(0, (elapsedTime / totalCycleDuration) * 100)) : 0;
  
  // UI colors
  let statusColorClass = "text-text";
  let dotColorClass = "bg-text-muted";
  
  if (sharedVisualPhaseState === "GREEN") {
    statusColorClass = "text-signal-green";
    dotColorClass = "bg-signal-green";
  } else if (sharedVisualPhaseState === "YELLOW") {
    statusColorClass = "text-signal-amber";
    dotColorClass = "bg-signal-amber";
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      {/* HEADER */}
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 font-display text-sm font-semibold text-text">
          Signal Status
          {displaySignal.source === "mock" ? (
             <span className="rounded-full bg-signal-amber/10 px-2 py-0.5 text-[10px] font-medium text-signal-amber ring-1 ring-signal-amber/20">
               Simulated
             </span>
          ) : (
             <span className="rounded-full bg-accent-blue/10 px-2 py-0.5 text-[10px] font-medium text-accent-blue ring-1 ring-accent-blue/20">
               Live
             </span>
          )}
        </h2>
      </div>

      <div className="space-y-4">
        {hasRecommendation ? (
          <>
            {/* ROW 1: CURRENT SIGNAL & ACTIVE PHASE */}
            <div className="grid grid-cols-2 gap-3">
              {/* Current Signal */}
              <div className="rounded-md border border-border bg-surface-2 p-4 flex flex-col items-center justify-center relative">
                <div className="absolute top-3 left-3 text-[10px] uppercase tracking-wider font-semibold text-text-muted">Current Signal</div>
                <div className={`mt-4 flex items-center text-lg font-bold ${statusColorClass}`}>
                  <span className={`mr-2 inline-block h-3 w-3 rounded-full animate-pulse ${dotColorClass}`} />
                  {sharedVisualPhaseState}
                </div>
                <div className="mt-1 font-mono text-5xl font-extrabold tabular-nums tracking-tight text-text">
                  {sharedVisualRemaining}
                  <span className="ml-1 text-xl font-normal text-text-muted">s</span>
                </div>
              </div>

              {/* Active Phase */}
              <div className="rounded-md border border-border bg-surface-2 p-4 flex flex-col justify-center">
                <div className="text-[10px] uppercase tracking-wider font-semibold text-text-muted mb-2">Active Phase</div>
                <div className="font-display text-2xl font-bold text-text">
                  {approachLabel(sharedVisualPhase || "")}
                </div>
                <div className="mt-1 text-xs text-text-secondary font-mono">
                  ID: {sharedVisualPhase}
                </div>
              </div>
            </div>

            {/* ROW 2: NEXT PHASE & CYCLE PROGRESS */}
            <div className="grid grid-cols-2 gap-3">
              {/* Next Phase */}
              <div className="rounded-md border border-border bg-surface-2 p-4 flex flex-col justify-center">
                <div className="text-[10px] uppercase tracking-wider font-semibold text-text-muted mb-2">Next Phase</div>
                <div className="font-display text-lg font-semibold text-text">
                  {approachLabel(nextPhaseApproach)}
                </div>
                <div className="mt-2 flex items-center gap-4">
                  <div className="flex items-center text-xs font-semibold text-signal-red">
                    <span className="mr-1.5 inline-block h-2 w-2 rounded-full bg-signal-red" />
                    RED
                  </div>
                  <div className="font-mono text-xl font-bold tabular-nums text-text">
                    {nextPhaseWaitTime}
                    <span className="ml-1 text-xs font-normal text-text-muted">s</span>
                  </div>
                </div>
              </div>

              {/* Cycle Progress */}
              <div className="rounded-md border border-border bg-surface-2 p-4 flex flex-col justify-center">
                <div className="text-[10px] uppercase tracking-wider font-semibold text-text-muted mb-2">Cycle Progress</div>
                <div className="flex items-end justify-between">
                  <div className="font-mono text-2xl font-bold text-text tabular-nums">{Math.round(progressPercent)}<span className="text-sm text-text-muted">%</span></div>
                  <div className="text-xs text-text-secondary mb-1">{totalCycleDuration}s total</div>
                </div>
                <div className="mt-3 h-2.5 w-full overflow-hidden rounded-full bg-surface shadow-inner ring-1 ring-inset ring-border">
                  <div
                    className="h-full rounded-full bg-signal-green transition-all duration-1000 ease-linear shadow-sm"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
              </div>
            </div>

            {/* ROW 3: PHASE SEQUENCE */}
            <div className="rounded-md border border-border bg-surface-2 p-4">
              <div className="mb-3 text-[10px] uppercase tracking-wider font-semibold text-text-muted">Phase Sequence</div>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                {phases.map((p, idx) => {
                  const isActive = p.approach === sharedVisualPhase;
                  return (
                    <div key={p.approach} className="flex items-center gap-2">
                      <span className={`rounded-md px-3 py-1.5 font-semibold transition-all ${isActive ? "bg-signal-green/20 text-signal-green ring-1 ring-signal-green/50 shadow-sm" : "bg-surface text-text-muted border border-border"}`}>
                        {approachLabel(p.approach)}
                      </span>
                      {idx < phases.length - 1 && (
                        <span className="text-border font-bold">→</span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        ) : (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-md border border-border bg-surface-2 p-4 text-center">
                <div className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                  Current Signal
                </div>
                <div className={`mt-2 text-lg font-bold ${statusColorClass}`}>
                  {sharedVisualPhaseState}
                </div>
                <div className="mt-1 font-mono text-4xl font-extrabold tabular-nums text-text">
                  {sharedVisualRemaining}<span className="ml-1 text-base font-normal text-text-muted">s</span>
                </div>
              </div>
              <div className="rounded-md border border-border bg-surface-2 p-4">
                <div className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                  Active Phase
                </div>
                <div className="mt-2 font-display text-xl font-bold text-text">
                  {approachLabel(displaySignal.currentPhase)}
                </div>
                <div className="mt-1 text-xs text-text-secondary">
                  Berikutnya: {approachLabel(displaySignal.nextPhase ?? "-")}
                </div>
              </div>
            </div>
            <div className="rounded-md border border-signal-amber/30 bg-signal-amber/5 px-3 py-2 text-xs text-text-secondary">
              Rencana siklus belum tersedia; status fase langsung tetap ditampilkan dari backend.
            </div>
          </div>
        )}

        {/* METADATA */}
        <div className="border-t border-border pt-3">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-[10px] text-text-muted">Intersection</div>
              <div className="mt-0.5 font-mono text-[10px] text-text-secondary">
                {displaySignal.intersectionId}
              </div>
            </div>
            <div>
              <div className="text-[10px] text-text-muted">Last Update</div>
              <div className="mt-0.5 font-mono text-[10px] text-text-secondary">
                {new Date(displaySignal.timestamp).toLocaleString("id-ID")}
              </div>
            </div>
            <div>
              <div className="text-[10px] text-text-muted mb-1">Data Source</div>
              <div className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ${
                displaySignal.source === "scenario-generator"
                  ? "bg-signal-green/10 text-signal-green border border-signal-green/20"
                  : displaySignal.source === "mock"
                  ? "bg-signal-amber/10 text-signal-amber border border-signal-amber/20"
                  : "bg-surface-2 text-text-secondary border border-border"
              }`}>
                {displaySignal.source === "scenario-generator" ? "Diuji simulasi SUMO" : displaySignal.source === "mock" ? "Simulated" : "Estimasi langsung"}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
