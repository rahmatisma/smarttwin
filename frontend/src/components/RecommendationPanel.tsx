import type { ApproachPhase, Recommendation, SignalStatus } from "@/types/traffic";
import { APPROACH_OPTIONS, type ApproachSelection } from "@/lib/intersections";

// Harus sama dengan YELLOW_SECONDS di backend/app/services/signal_service.py
const YELLOW_SECONDS = 4;

const CYCLE_ORDER = ["north", "east", "south", "west"];

function approachLabel(approach: string): string {
  const option = APPROACH_OPTIONS.find((opt) => opt.id === approach);
  return option ? option.name : approach;
}

const APPROACH_SHORT: Record<string, string> = {
  north: "Utara",
  east: "Timur",
  south: "Selatan",
  west: "Barat",
};

// Warna kelas LOS: A-B lancar (hijau), C-D sedang (kuning), E-F buruk (merah).
const LOS_TONE: Record<string, string> = {
  A: "text-emerald-500",
  B: "text-emerald-500",
  C: "text-amber-500",
  D: "text-amber-500",
  E: "text-red-500",
  F: "text-red-500",
};

const APPROACH_NAMES = APPROACH_OPTIONS.reduce((acc, opt) => {
  if (opt.id === "all") return acc;
  const match = opt.name.match(/^(.*?)\s*\((.*?)\)$/);
  if (match) {
    acc[opt.id] = { dir: match[1], street: match[2] };
  } else {
    acc[opt.id] = { dir: opt.name, street: "" };
  }
  return acc;
}, {} as Record<string, { dir: string; street: string }>);

function ApproachCard({
  data,
  isCompact = false,
}: {
  data: {
    approach: string;
    isActive: boolean;
    currentState: "GREEN" | "YELLOW" | "RED";
    rtGreen: number;
    rtYellow: number;
    rtRed: number;
    bsGreen: number;
    bsYellow: number;
    bsRed: number;
  };
  isCompact?: boolean;
}) {
  const nameInfo = APPROACH_NAMES[data.approach] || { dir: data.approach, street: "" };

  return (
    <div
      className={`rounded-md border transition-colors ${isCompact ? "p-2" : "p-3"} ${
        data.isActive
          ? "border-signal-green bg-signal-green/5 ring-1 ring-signal-green"
          : "border-border bg-surface-2"
      }`}
    >
      <div className="mb-3 border-b border-border/50 pb-2">
        <div className="flex items-center justify-between">
          <div className="font-display font-bold text-text">{nameInfo.dir}</div>
          {isCompact ? (
            <div className="flex gap-1 rounded-full border border-border/50 bg-surface-2 p-1">
              <div className={`h-2 w-2 rounded-full ${data.currentState === "RED" ? "bg-signal-red shadow-[0_0_6px_rgba(239,68,68,0.8)]" : "bg-surface/50 opacity-40"}`} />
              <div className={`h-2 w-2 rounded-full ${data.currentState === "YELLOW" ? "bg-signal-amber shadow-[0_0_6px_rgba(245,158,11,0.8)]" : "bg-surface/50 opacity-40"}`} />
              <div className={`h-2 w-2 rounded-full ${data.currentState === "GREEN" ? "bg-signal-green shadow-[0_0_6px_rgba(16,185,129,0.8)]" : "bg-surface/50 opacity-40"}`} />
            </div>
          ) : (
            data.isActive && (
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-signal-green opacity-75"></span>
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-signal-green"></span>
              </span>
            )
          )}
        </div>
        <div className="mt-0.5 text-xs text-text-muted">{nameInfo.street}</div>
      </div>

      {isCompact ? (
        <div className="space-y-1 text-xs">
          <div className="mb-1 flex items-center justify-between border-b border-border/30 pb-1 text-[9px] uppercase tracking-wider text-text-muted">
            <span>Phase</span>
            <span className="w-9 text-right">Real</span>
            <span className="w-9 text-right">Scen</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="font-semibold text-signal-green">GREEN</span>
            <span className="w-9 text-right font-mono text-[10px]">{data.rtGreen}s</span>
            <span className="w-9 text-right font-mono text-[10px] font-bold text-signal-green">{data.bsGreen}s</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="font-semibold text-signal-amber">YELLOW</span>
            <span className="w-9 text-right font-mono text-[10px]">{data.rtYellow}s</span>
            <span className="w-9 text-right font-mono text-[10px]">{data.bsYellow}s</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="font-semibold text-signal-red">RED</span>
            <span className="w-9 text-right font-mono text-[10px]">{data.rtRed}s</span>
            <span className="w-9 text-right font-mono text-[10px] font-bold text-signal-red">{data.bsRed}s</span>
          </div>
        </div>
      ) : (
        <div className="space-y-2 text-xs">
          {/* GREEN */}
          <div className="flex flex-col rounded border border-border/50 bg-surface p-2">
            <div className="mb-1.5 font-semibold text-signal-green">GREEN</div>
            <div className="mb-0.5 flex items-center justify-between">
              <span className="text-[10px] text-text-muted">Realtime</span>
              <span className="font-mono font-medium text-text">{data.rtGreen}s</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-text-muted">Best Scenario</span>
              <span className="font-mono font-medium text-text">{data.bsGreen}s</span>
            </div>
          </div>

          {/* YELLOW */}
          <div className="flex flex-col rounded border border-border/50 bg-surface p-2">
            <div className="mb-1.5 font-semibold text-signal-amber">YELLOW</div>
            <div className="mb-0.5 flex items-center justify-between">
              <span className="text-[10px] text-text-muted">Realtime</span>
              <span className="font-mono font-medium text-text">{data.rtYellow}s</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-text-muted">Best Scenario</span>
              <span className="font-mono font-medium text-text">{data.bsYellow}s</span>
            </div>
          </div>

          {/* RED */}
          <div className="flex flex-col rounded border border-border/50 bg-surface p-2">
            <div className="mb-1.5 font-semibold text-signal-red">RED</div>
            <div className="mb-0.5 flex items-center justify-between">
              <span className="text-[10px] text-text-muted">Realtime</span>
              <span className="font-mono font-medium text-text">{data.rtRed}s</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-text-muted">Best Scenario</span>
              <span className="font-mono font-medium text-text">{data.bsRed}s</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function RecommendationPanel({
  recommendation,
  signal,
  sharedVisualPhase,
  sharedVisualPhaseState,
  sharedVisualRemaining,
  elapsedSeconds,
  isLoading,
  layout = "grid",
}: {
  recommendation?: Recommendation | null;
  signal?: SignalStatus;
  selectedApproach?: ApproachSelection;
  activeCycleSeconds?: number;
  sharedVisualPhase: string | null;
  sharedVisualPhaseState: "GREEN" | "YELLOW";
  sharedVisualRemaining: number;
  elapsedSeconds?: number;
  isLoading?: boolean;
  layout?: "grid" | "cross";
}) {
  const displayRec = recommendation ?? null;
  const showLoading = Boolean(isLoading);

  if (showLoading) {
    return (
      <div className="rounded-lg border border-border bg-surface p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-display text-sm font-semibold text-text">
            Signal Recommendation
          </h2>
          <span className="text-xs text-text-muted">Memuat...</span>
        </div>
        <div className="flex min-h-[320px] items-center justify-center rounded-md border border-border bg-surface-2 px-4 text-center">
          <div className="flex flex-col items-center justify-center space-y-3">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-text-muted border-t-transparent"></div>
            <p className="text-xs text-text-muted">Mengambil data rekomendasi...</p>
          </div>
        </div>
      </div>
    );
  }

  // Loading sudah selesai tapi backend belum mengirim rekomendasi apa pun.
  // Tampilkan status eksplisit, jangan spinner tanpa batas -- dashboard
  // tetap bisa dipakai dan data akan menyusul otomatis saat poll berikutnya.
  if (!displayRec) {
    return (
      <div className="rounded-lg border border-border bg-surface p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-display text-sm font-semibold text-text">
            Signal Recommendation
          </h2>
          <span className="text-xs text-amber-500">Menunggu backend</span>
        </div>
        <div className="flex min-h-[320px] items-center justify-center rounded-md border border-border bg-surface-2 px-6 text-center">
          <div>
            <p className="text-sm font-medium text-text">Rekomendasi belum tersedia</p>
            <p className="mt-2 text-xs text-text-muted">
              Dashboard tetap dapat digunakan. Data akan diperbarui otomatis saat backend kembali merespons.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const cyclePlan = displayRec.cyclePlan;
  const phases = cyclePlan?.phases ?? [];

  // Parse best scenario
  const phaseByApproach: Record<string, ApproachPhase> = {};
  for (const phase of phases) {
    const yellowSeconds = phase.yellowSeconds ?? YELLOW_SECONDS;
    const totalCycleSeconds =
      cyclePlan?.totalCycleSeconds ||
      (cyclePlan?.cycleLengthSeconds ?? 0) + (cyclePlan?.phases.length ?? 0) * YELLOW_SECONDS;
    
    phaseByApproach[phase.approach] = {
      ...phase,
      yellowSeconds,
      redSeconds:
        phase.redSeconds && phase.redSeconds > 0
          ? phase.redSeconds
          : Math.max(0, totalCycleSeconds - phase.greenSeconds - yellowSeconds),
    };
  }

  const getRealtimeMetrics = (approach: string) => {
    let rtGreen = 0;
    let rtYellow = 0;
    let rtRed = 0;

    const signalPhases = signal?.phases || {};

    if (sharedVisualPhase === approach) {
      if (sharedVisualPhaseState === "GREEN") {
        rtGreen = Math.max(0, sharedVisualRemaining - YELLOW_SECONDS);
        rtYellow = YELLOW_SECONDS;
      } else {
        rtGreen = 0;
        rtYellow = sharedVisualRemaining;
      }
      rtRed = 0;
    } else {
      rtGreen = 0;
      rtYellow = 0;
      const baseRemaining = signalPhases[approach]?.remainingSeconds ?? 0;
      rtRed = Math.max(0, baseRemaining - (elapsedSeconds ?? 0));
    }

    return { rtGreen, rtYellow, rtRed };
  };

  const getBestScenarioMetrics = (approach: string) => {
    const p = phaseByApproach[approach];
    if (!p) return { bsGreen: 0, bsYellow: 0, bsRed: 0 };
    return {
      bsGreen: p.greenSeconds,
      bsYellow: p.yellowSeconds ?? YELLOW_SECONDS,
      bsRed: p.redSeconds ?? 0,
    };
  };

  const approachData = CYCLE_ORDER.map((approach) => {
    const metrics = getRealtimeMetrics(approach);
    const best = getBestScenarioMetrics(approach);
    const isActive = sharedVisualPhase === approach;
    let currentState: "GREEN" | "YELLOW" | "RED" = "RED";
    if (isActive) {
      currentState = sharedVisualPhaseState;
    }
    return { approach, isActive, currentState, ...metrics, ...best };
  });

  return (
    <div className="flex h-full flex-col rounded-lg border border-border bg-surface p-4 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-display text-sm font-semibold text-text">Signal Recommendation</h2>
        <span className="text-xs text-signal-green">Available</span>
      </div>

      <div className="space-y-4">
        {/* ===================================================
            DURASI 4 LENGAN (urutan Utara -> Timur -> Selatan -> Barat)
           =================================================== */}
        {cyclePlan ? (
          layout === "cross" ? (
            <div className="flex flex-col">
              <div className="mb-4 text-sm font-semibold text-text">
                Rekomendasi Durasi per Lengan{" "}
                <span className="ml-2 font-normal text-text-muted">
                  siklus {cyclePlan.totalCycleSeconds ?? cyclePlan.cycleLengthSeconds ?? 0}s
                </span>
              </div>
              <div className="flex w-full flex-col items-center gap-4 lg:px-8">
                {/* UTARA (Top) */}
                <div className="w-full sm:w-2/3 lg:w-1/2">
                  {(() => {
                    const data = approachData.find(d => d.approach === "north");
                    return data ? <ApproachCard data={data} isCompact={true} /> : null;
                  })()}
                </div>
                
                {/* BARAT & TIMUR (Middle) */}
                <div className="flex w-full flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="w-full sm:w-1/2 lg:w-2/5">
                    {(() => {
                      const data = approachData.find(d => d.approach === "west");
                      return data ? <ApproachCard data={data} isCompact={true} /> : null;
                    })()}
                  </div>
                  <div className="hidden shrink-0 flex-col items-center justify-center rounded-full border border-border bg-surface-2 p-6 text-xs font-bold tracking-widest text-text-muted shadow-inner sm:flex">
                    Simpang 4 Pingit
                  </div>
                  <div className="w-full sm:w-1/2 lg:w-2/5">
                    {(() => {
                      const data = approachData.find(d => d.approach === "east");
                      return data ? <ApproachCard data={data} isCompact={true} /> : null;
                    })()}
                  </div>
                </div>

                {/* SELATAN (Bottom) */}
                <div className="w-full sm:w-2/3 lg:w-1/2">
                  {(() => {
                    const data = approachData.find(d => d.approach === "south");
                    return data ? <ApproachCard data={data} isCompact={true} /> : null;
                  })()}
                </div>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {approachData.map((data) => (
                <ApproachCard key={data.approach} data={data} />
              ))}
            </div>
          )
        ) : (
          <div className="rounded-md border border-border bg-surface-2 p-3 text-center text-xs text-text-muted">
            Data Cycle Plan belum tersedia
          </div>
        )}

        {/* METRICS & SOURCE */}
        <div className="flex flex-col gap-3 border-t border-border pt-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-4">
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                  Expected Delay Reduction
                </div>
                <div className="mt-0.5 font-mono text-sm font-semibold text-signal-green">
                  {displayRec.expectedDelayReductionPercent.toFixed(1)}%
                </div>
              </div>
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                  Confidence
                </div>
                <div className="mt-0.5 font-mono text-sm font-semibold text-text">
                  {(displayRec.confidence * 100).toFixed(1)}%
                </div>
              </div>
            </div>

            <div className="flex flex-col items-end gap-2 text-right">
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                  Source
                </div>
                <div className="mt-1">
                  <span
                    className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium ${
                      displayRec.source === "scenario-generator"
                        ? "border-signal-green/20 bg-signal-green/10 text-signal-green"
                        : "border-signal-amber/20 bg-signal-amber/10 text-signal-amber"
                    }`}
                  >
                    {displayRec.source === "scenario-generator"
                      ? "Diuji simulasi SUMO"
                      : "Estimasi langsung"}
                    <span className="ml-1 opacity-70">({displayRec.source})</span>
                  </span>
                </div>
              </div>
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                  Green Time
                </div>
                <div className="mt-1 font-mono text-sm font-semibold text-text">
                  {phases.length && sharedVisualPhase
                    ? `${phases.find(p => p.approach === sharedVisualPhase)?.greenSeconds ?? "-"}s`
                    : `${displayRec.recommendedGreenSeconds}s`}
                </div>
              </div>
            </div>

            {!cyclePlan && (
              <div className="mt-1 text-[10px] text-text-muted">
                {approachLabel(displayRec.recommendedPhase)}
              </div>
            )}
          </div>

          {typeof displayRec.avgDelaySeconds === "number" && (
            <div className="mt-1 grid grid-cols-3 gap-2">
              <div className="rounded border border-border bg-surface-2 p-2 text-center">
                <div className="text-[9px] uppercase tracking-wider text-text-muted">LOS</div>
                <div className="mt-1 font-mono text-xs font-bold text-text">
                  {displayRec.los ?? "-"}
                </div>
              </div>
              <div className="rounded border border-border bg-surface-2 p-2 text-center">
                <div className="text-[9px] uppercase tracking-wider text-text-muted">Delay</div>
                <div className="mt-1 font-mono text-xs font-bold text-text">
                  {displayRec.avgDelaySeconds.toFixed(1)}s
                </div>
              </div>
              <div className="rounded border border-border bg-surface-2 p-2 text-center">
                <div className="text-[9px] uppercase tracking-wider text-text-muted">Antrean</div>
                <div className="mt-1 font-mono text-xs font-bold text-text">
                  {displayRec.avgQueueLengthM?.toFixed(1) ?? "-"}m
                </div>
              </div>
            </div>
          )}

          {displayRec.losByApproach &&
            Object.keys(displayRec.losByApproach).length > 0 && (
            <div className="mt-2">
              <div className="mb-1 text-[9px] uppercase tracking-wider text-text-muted">
                LOS per lengan (HCM)
              </div>
              <div className="grid grid-cols-4 gap-1">
                {CYCLE_ORDER.map((approach) => {
                  const grade = displayRec.losByApproach?.[approach] ?? null;
                  const delay =
                    displayRec.delayByApproachSeconds?.[approach] ?? null;
                  return (
                    <div
                      key={approach}
                      className="rounded border border-border bg-surface-2 p-1.5 text-center"
                      title={
                        typeof delay === "number"
                          ? `${approachLabel(approach)} — delay ${delay.toFixed(1)}s`
                          : `${approachLabel(approach)} — tidak ada data`
                      }
                    >
                      <div className="text-[8px] uppercase tracking-wider text-text-muted">
                        {APPROACH_SHORT[approach] ?? approach}
                      </div>
                      <div
                        className={`mt-0.5 font-mono text-xs font-bold ${
                          grade ? LOS_TONE[grade] ?? "text-text" : "text-text-muted"
                        }`}
                      >
                        {grade ?? "–"}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
