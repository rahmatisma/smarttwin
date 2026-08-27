import { useState, useEffect } from "react";
import type { ApproachPhase, Recommendation, SignalStatus } from "@/types/traffic";
import { APPROACH_OPTIONS, type ApproachSelection } from "@/lib/intersections";

// Harus sama dengan YELLOW_SECONDS di backend/app/services/signal_service.py
const YELLOW_SECONDS = 4;

function approachLabel(approach: string): string {
  const option = APPROACH_OPTIONS.find((opt) => opt.id === approach);
  return option ? option.name : approach;
}

function approachShortLabel(approach: string): string {
  switch (approach) {
    case "north":
      return "Utara";
    case "south":
      return "Selatan";
    case "east":
      return "Timur";
    case "west":
      return "Barat";
    default:
      return approach;
  }
}

/*
 * =========================================================
 * KOTAK SATU LENGAN (dipakai di layout silang di bawah)
 * =========================================================
 */
function ApproachBox({
  phase,
  status,
  displaySeconds,
  liveTotalSeconds,
}: {
  phase: ApproachPhase;
  status: "GREEN" | "YELLOW" | "RED";
  displaySeconds: number;
  liveTotalSeconds?: number;
}) {
  const barPercent = status === "RED"
    ? Math.round(Math.min(1, Math.max(0, phase.demandScore)) * 100)
    : Math.round(
        Math.min(1, Math.max(0, displaySeconds / (status === "YELLOW" ? YELLOW_SECONDS : (liveTotalSeconds || phase.greenSeconds || 1)))) * 100
      );

  let ringClass = "border-border bg-surface-2";
  let dotClass = "bg-signal-red";
  let textClass = "text-signal-red";
  let progressClass = "bg-text-muted";

  if (status === "GREEN") {
    ringClass = "border-signal-green bg-surface-2 ring-1 ring-signal-green";
    dotClass = "bg-signal-green";
    textClass = "text-text";
    progressClass = "bg-signal-green";
  } else if (status === "YELLOW") {
    ringClass = "border-signal-amber bg-surface-2 ring-1 ring-signal-amber";
    dotClass = "bg-signal-amber";
    textClass = "text-text";
    progressClass = "bg-signal-amber";
  }

  return (
    <div className={`rounded-md border p-2 text-center transition-colors ${ringClass}`}>
      <div className="text-[10px] text-text-muted">
        {approachShortLabel(phase.approach)}
        <span className={`ml-1 inline-block h-1.5 w-1.5 rounded-full align-middle ${dotClass}`} />
      </div>

      <div className={`mt-0.5 font-mono text-base font-semibold ${textClass}`}>
        {displaySeconds}s
      </div>

      <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-border">
        <div
          className={`h-full rounded-full transition-all ${progressClass}`}
          style={{ width: `${barPercent}%` }}
        />
      </div>
    </div>
  );
}

export default function RecommendationPanel({
  recommendation,
  signal,
  selectedApproach,
  activeCycleSeconds,
  sharedVisualPhase,
  sharedVisualPhaseState,
  sharedVisualRemaining,
  isLoading,
}: {
  recommendation?: Recommendation | null;
  signal?: SignalStatus;
  selectedApproach?: ApproachSelection;
  activeCycleSeconds?: number;
  sharedVisualPhase: string | null;
  sharedVisualPhaseState: "GREEN" | "YELLOW";
  sharedVisualRemaining: number;
  isLoading?: boolean;
}) {
  const [hasReceivedData, setHasReceivedData] = useState(false);
  const [lastValidRec, setLastValidRec] = useState<Recommendation | null>(null);

  useEffect(() => {
    if (recommendation && !isLoading) {
      setHasReceivedData(true);
      setLastValidRec(recommendation);
    }
  }, [recommendation, isLoading]);

  const displayRec = recommendation || lastValidRec;
  const showLoading = (isLoading || !displayRec) && !hasReceivedData;

  const phases = displayRec?.cyclePlan?.phases ?? [];

  const getStatus = (approach: string): "GREEN" | "YELLOW" | "RED" => {
    if (sharedVisualPhase === approach) return sharedVisualPhaseState;
    return "RED";
  };

  const getDisplaySeconds = (approach: string) => {
    if (!phases.length || !sharedVisualPhase) return phaseByApproach[approach]?.greenSeconds ?? 0;
    
    const currentIndex = phases.findIndex(p => p.approach === sharedVisualPhase);
    const targetIndex = phases.findIndex(p => p.approach === approach);
    
    if (currentIndex === -1 || targetIndex === -1) return phaseByApproach[approach]?.greenSeconds ?? 0;
    if (currentIndex === targetIndex) return sharedVisualRemaining;

    let waitTime = sharedVisualRemaining;
    if (sharedVisualPhaseState === "GREEN") {
      waitTime += YELLOW_SECONDS; // Upcoming yellow phase for current active approach
    }

    let i = (currentIndex + 1) % phases.length;
    while (i !== targetIndex) {
      waitTime += phases[i].greenSeconds + YELLOW_SECONDS; // Green + Yellow
      i = (i + 1) % phases.length;
    }
    return waitTime;
  };

  if (showLoading || !displayRec) {
    return (
      <div className="rounded-lg border border-border bg-surface p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-display text-sm font-semibold text-text">
            Signal Recommendation
          </h2>

          <span className="text-xs text-text-muted">
            Memuat...
          </span>
        </div>

        <div className="flex min-h-[320px] items-center justify-center rounded-md border border-border bg-surface-2 px-4 text-center">
          <div className="flex flex-col items-center justify-center space-y-3">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-text-muted border-t-transparent"></div>
            <p className="text-xs text-text-muted">
              Mengambil data rekomendasi...
            </p>
          </div>
        </div>
      </div>
    );
  }

  const cyclePlan = displayRec.cyclePlan;

  const phaseByApproach: Record<string, ApproachPhase> = {};
  for (const phase of cyclePlan?.phases ?? []) {
    phaseByApproach[phase.approach] = phase;
  }

  /*
   * =========================================================
   * RECOMMENDATION DATA
   * =========================================================
   *
   * Semua data di bawah berasal dari backend.
   * Tidak ada nilai dummy.
   */

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-display text-sm font-semibold text-text">
          Signal Recommendation
        </h2>

        <span className="text-xs text-signal-green">
          Available
        </span>
      </div>

      <div className="space-y-3">
        {/* ===================================================
            DURASI 4 LENGAN (layout silang, meniru bentuk simpang)
            Cuma tampil kalau backend sudah kirim cyclePlan --
            kalau belum (mis. fallback tanpa TrafficState),
            section ini disembunyikan, info di bawah tetap tampil.
           =================================================== */}
        {cyclePlan && (
          <div className="rounded-md border border-border bg-surface-2 p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs text-text-muted">
                Durasi Hijau per Lengan
              </span>

              <span className="font-mono text-[10px] text-text-muted">
                siklus {cyclePlan.cycleLengthSeconds}s
              </span>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div />
              {phaseByApproach.north && (
                <ApproachBox
                  phase={phaseByApproach.north}
                  status={getStatus("north")}
                  displaySeconds={getDisplaySeconds("north")}
                  liveTotalSeconds={activeCycleSeconds}
                />
              )}
              <div />

              {phaseByApproach.west && (
                <ApproachBox
                  phase={phaseByApproach.west}
                  status={getStatus("west")}
                  displaySeconds={getDisplaySeconds("west")}
                  liveTotalSeconds={activeCycleSeconds}
                />
              )}

              <div className="flex items-center justify-center text-[10px] text-text-muted">
                {selectedApproach && selectedApproach !== "all"
                  ? approachLabel(selectedApproach)
                  : "Simpang Pingit"}
              </div>

              {phaseByApproach.east && (
                <ApproachBox
                  phase={phaseByApproach.east}
                  status={getStatus("east")}
                  displaySeconds={getDisplaySeconds("east")}
                  liveTotalSeconds={activeCycleSeconds}
                />
              )}

              <div />
              {phaseByApproach.south && (
                <ApproachBox
                  phase={phaseByApproach.south}
                  status={getStatus("south")}
                  displaySeconds={getDisplaySeconds("south")}
                  liveTotalSeconds={activeCycleSeconds}
                />
              )}
              <div />
            </div>
          </div>
        )}


        {/* Green Time */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-md border border-border bg-surface-2 p-3">
            <div className="text-xs text-text-muted">
              Recommendation Green
            </div>

            <div className="mt-1 font-mono text-sm font-semibold text-text">
              {sharedVisualPhase 
                ? `${phases.find(p => p.approach === sharedVisualPhase)?.greenSeconds ?? "-"}s` 
                : "Memuat..."}
            </div>
          </div>

          <div className="rounded-md border border-border bg-surface-2 p-3">
            <div className="text-xs text-text-muted">
              Current Green Phase
            </div>

            <div className="mt-1 font-mono text-sm font-semibold text-text">
              {sharedVisualPhase && signal?.phases?.[sharedVisualPhase]
                ? `${signal.phases[sharedVisualPhase].durationSeconds}s`
                : "Memuat..."}
            </div>
          </div>
        </div>

        {/* Expected Improvement */}
        <div className="rounded-md border border-border bg-surface-2 p-3">
          <div className="text-xs text-text-muted">
            Expected Delay Reduction
          </div>

          <div className="mt-1 font-mono text-sm font-semibold text-signal-green">
            {displayRec.expectedDelayReductionPercent.toFixed(1)}%
          </div>
        </div>

        {/* Confidence */}
        <div className="rounded-md border border-border bg-surface-2 p-3">
          <div className="text-xs text-text-muted">
            Confidence
          </div>

          <div className="mt-1 font-mono text-sm font-semibold text-text">
            {(displayRec.confidence * 100).toFixed(1)}%
          </div>
        </div>



        {/* Source */}
        <div className="flex flex-col gap-2 border-t border-border pt-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase tracking-wider font-semibold text-text-muted">
              Source
            </span>
            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ${
              displayRec.source === "scenario-generator"
                ? "bg-signal-green/10 text-signal-green border border-signal-green/20"
                : "bg-signal-amber/10 text-signal-amber border border-signal-amber/20"
            }`}>
              {displayRec.source === "scenario-generator" ? "Diuji simulasi SUMO" : "Estimasi langsung"}
              <span className="ml-1 opacity-70">({displayRec.source})</span>
            </span>
          </div>
          
          {typeof displayRec.avgDelaySeconds === 'number' && (
            <div className="mt-2 grid grid-cols-3 gap-2">
              <div className="rounded border border-border bg-surface-2 p-2 text-center">
                <div className="text-[9px] uppercase tracking-wider text-text-muted">LOS</div>
                <div className="mt-1 font-mono text-xs font-bold text-text">{displayRec.los ?? "-"}</div>
              </div>
              <div className="rounded border border-border bg-surface-2 p-2 text-center">
                <div className="text-[9px] uppercase tracking-wider text-text-muted">Delay</div>
                <div className="mt-1 font-mono text-xs font-bold text-text">{displayRec.avgDelaySeconds.toFixed(1)}s</div>
              </div>
              <div className="rounded border border-border bg-surface-2 p-2 text-center">
                <div className="text-[9px] uppercase tracking-wider text-text-muted">Antrean</div>
                <div className="mt-1 font-mono text-xs font-bold text-text">{displayRec.avgQueueLengthM?.toFixed(1) ?? "-"}m</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
