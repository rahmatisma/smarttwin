import type { SignalStatus } from "@/types/traffic";

export default function SignalStatusPanel({
  signal,
}: {
  signal: SignalStatus;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      {/* =====================================================
          HEADER
          ===================================================== */}

      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-display text-sm font-semibold text-text">
          Signal Status
        </h2>

        <span
          className={
            signal.source === "mock"
              ? "text-xs text-signal-amber"
              : "text-xs text-signal-green"
          }
        >
          {signal.source === "mock" ? "Simulated" : "Connected"}
        </span>
      </div>

      {/* =====================================================
          SIGNAL INFORMATION
          ===================================================== */}

      <div className="space-y-4">
        {/* Current Phase */}

        <div className="rounded-md border border-border bg-surface-2 p-3">
          <div className="text-xs text-text-muted">
            Current Phase
          </div>

          <div className="mt-1 font-display text-sm font-semibold text-text">
            {signal.phaseName}
          </div>

          <div className="mt-1 text-xs text-text-secondary">
            Phase ID: {signal.currentPhase}
          </div>
        </div>

        {/* =================================================
            REMAINING TIME
            ================================================= */}

        <div className="flex items-end justify-between gap-4">
          <div>
            <div className="text-xs text-text-muted">
              Remaining Time
            </div>

            <div className="mt-1 font-mono text-3xl font-bold tabular-nums text-text">
              {signal.remainingSeconds}

              <span className="ml-1 text-sm font-normal text-text-muted">
                detik
              </span>
            </div>
          </div>

          {/* =================================================
              CYCLE TIME
              ================================================= */}

          <div className="text-right">
            <div className="text-xs text-text-muted">
              Cycle Time
            </div>

            <div className="mt-1 font-mono text-lg font-semibold tabular-nums text-text">
              {signal.cycleTimeSeconds}

              <span className="ml-1 text-xs font-normal text-text-muted">
                detik
              </span>
            </div>
          </div>
        </div>

        {/* =================================================
            INTERSECTION
            ================================================= */}

        <div className="border-t border-border pt-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-text-muted">
              Intersection
            </span>

            <span className="font-mono text-xs text-text-secondary">
              {signal.intersectionId}
            </span>
          </div>
        </div>

        {/* =================================================
            TIMESTAMP
            ================================================= */}

        <div>
          <div className="text-xs text-text-muted">
            Last Update
          </div>

          <div className="mt-1 text-xs text-text-secondary">
            {new Date(signal.timestamp).toLocaleString("id-ID")}
          </div>
        </div>

        {/* =================================================
            SOURCE
            ================================================= */}

        <div>
          <div className="text-xs text-text-muted">
            Data Source
          </div>

          <div className="mt-1 text-xs font-medium text-text-secondary">
            {signal.source}
          </div>
        </div>
      </div>
    </div>
  );
}