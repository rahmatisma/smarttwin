import type { SignalStatus, Recommendation } from "@/types/traffic";
import { APPROACH_OPTIONS } from "@/lib/intersections";

// Harus sama dengan YELLOW_SECONDS di backend/app/services/signal_service.py
const YELLOW_SECONDS = 4;

const CYCLE_ORDER = ["north", "east", "south", "west"];

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

function CrossApproachCard({
  data,
}: {
  data: {
    approach: string;
    name: { dir: string; street: string };
    currentState: "GREEN" | "YELLOW" | "RED";
    displayTime: number;
  };
}) {
  let borderColor = "border-signal-red ring-signal-red bg-signal-red/5";
  let textColor = "text-signal-red";
  let displayState = "🔴 RED";

  if (data.currentState === "GREEN") {
    borderColor = "border-signal-green ring-signal-green bg-signal-green/5";
    textColor = "text-signal-green";
    displayState = "🟢 GREEN";
  } else if (data.currentState === "YELLOW") {
    borderColor = "border-signal-amber ring-signal-amber bg-signal-amber/5";
    textColor = "text-signal-amber";
    displayState = "🟡 YELLOW";
  }

  return (
    <div className={`rounded-md border p-3 text-center transition-colors ring-1 ${borderColor}`}>
      <div className="mb-1 font-display font-bold text-text">{data.name.dir}</div>
      <div className="text-xs text-text-muted">{data.name.street}</div>
      
      <div className="mt-4 flex flex-col items-center justify-center">
        <div className={`text-sm font-bold ${textColor}`}>
          {displayState}
        </div>
        <div className="mt-1 font-mono text-2xl font-bold text-text">
          {data.displayTime}s
        </div>
      </div>
    </div>
  );
}

export default function SignalStatusPanel({
  signal,
  recommendation,
  sharedVisualPhase,
  sharedVisualPhaseState,
  sharedVisualRemaining,
  elapsedSeconds,
  isLoading,
  layout = "list",
}: {
  signal: SignalStatus;
  recommendation?: Recommendation | null;
  sharedVisualPhase: string | null;
  sharedVisualPhaseState: "GREEN" | "YELLOW";
  sharedVisualRemaining: number;
  elapsedSeconds?: number;
  isLoading?: boolean;
  layout?: "list" | "cross";
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
          <span className="text-xs text-text-muted">Memuat...</span>
        </div>
        <div className="flex min-h-[320px] items-center justify-center rounded-md border border-border bg-surface-2 px-4 text-center">
          <div className="flex flex-col items-center justify-center space-y-3">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-text-muted border-t-transparent"></div>
            <p className="text-xs text-text-muted">Memuat status sinyal...</p>
          </div>
        </div>
      </div>
    );
  }

  const getRealtimeMetrics = (approach: string) => {
    let currentState: "GREEN" | "YELLOW" | "RED" = "RED";
    let displayTime = 0;

    const signalPhases = signal?.phases || {};

    if (sharedVisualPhase === approach) {
      if (sharedVisualPhaseState === "GREEN") {
        currentState = "GREEN";
        displayTime = Math.max(0, sharedVisualRemaining - YELLOW_SECONDS);
      } else {
        currentState = "YELLOW";
        displayTime = sharedVisualRemaining;
      }
    } else {
      currentState = "RED";
      const baseRemaining = signalPhases[approach]?.remainingSeconds ?? 0;
      displayTime = Math.max(0, baseRemaining - (elapsedSeconds ?? 0));
    }

    return { currentState, displayTime };
  };

  const approachData = CYCLE_ORDER.map((approach) => {
    const { currentState, displayTime } = getRealtimeMetrics(approach);
    return {
      approach,
      name: APPROACH_NAMES[approach] || { dir: approach, street: "" },
      currentState,
      displayTime,
    };
  });

  return (
    <div className="flex h-full flex-col rounded-lg border border-border bg-surface p-4">
      {/* HEADER */}
      <div className="mb-4 flex items-center justify-between">
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

      <div className="flex-1 space-y-3">
        {layout === "cross" ? (
          <div className="flex w-full flex-col items-center gap-4 py-4 lg:px-8">
            {/* UTARA (Top) */}
            <div className="w-full sm:w-2/3 lg:w-1/2">
              {(() => {
                const data = approachData.find(d => d.approach === "north");
                return data ? <CrossApproachCard data={data} /> : null;
              })()}
            </div>
            
            {/* BARAT & TIMUR (Middle) */}
            <div className="flex w-full flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="w-full sm:w-1/2 lg:w-2/5">
                {(() => {
                  const data = approachData.find(d => d.approach === "west");
                  return data ? <CrossApproachCard data={data} /> : null;
                })()}
              </div>
              <div className="hidden shrink-0 flex-col items-center justify-center rounded-full border border-border bg-surface-2 p-6 text-xs font-bold tracking-widest text-text-muted shadow-inner sm:flex">
                SIMPANG
              </div>
              <div className="w-full sm:w-1/2 lg:w-2/5">
                {(() => {
                  const data = approachData.find(d => d.approach === "east");
                  return data ? <CrossApproachCard data={data} /> : null;
                })()}
              </div>
            </div>

            {/* SELATAN (Bottom) */}
            <div className="w-full sm:w-2/3 lg:w-1/2">
              {(() => {
                const data = approachData.find(d => d.approach === "south");
                return data ? <CrossApproachCard data={data} /> : null;
              })()}
            </div>
          </div>
        ) : (
          approachData.map((data) => {
            let statusColorClass = "text-signal-red";
            let dotColorClass = "bg-signal-red";

            if (data.currentState === "GREEN") {
              statusColorClass = "text-signal-green";
              dotColorClass = "bg-signal-green";
            } else if (data.currentState === "YELLOW") {
              statusColorClass = "text-signal-amber";
              dotColorClass = "bg-signal-amber";
            }

            return (
              <div
                key={data.approach}
                className="flex items-center justify-between rounded-md border border-border bg-surface-2 px-4 py-3"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`inline-block h-3 w-3 rounded-full ${dotColorClass} ${
                      data.currentState !== "RED" ? "animate-pulse" : ""
                    }`}
                  />
                  <span className="font-display text-sm font-semibold text-text">
                    {data.name.dir}
                  </span>
                </div>

                <div className="flex items-center gap-6">
                  <div className="w-12 text-right font-mono text-xl font-bold tabular-nums text-text">
                    {data.displayTime}
                    <span className="ml-0.5 text-xs font-normal text-text-muted">s</span>
                  </div>
                  <div className={`w-16 text-right text-xs font-bold ${statusColorClass}`}>
                    {data.currentState}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* METADATA */}
      <div className="mt-4 border-t border-border pt-3">
        <div className="flex justify-between">
          <div>
            <div className="text-[10px] text-text-muted">Intersection</div>
            <div className="mt-0.5 font-mono text-[10px] text-text-secondary">
              {displaySignal.intersectionId}
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] text-text-muted">Last Update</div>
            <div className="mt-0.5 font-mono text-[10px] text-text-secondary">
              {new Date(displaySignal.timestamp).toLocaleString("id-ID")}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
