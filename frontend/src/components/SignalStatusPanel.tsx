import type { SignalStatus } from "@/types/traffic";
import DonutRing from "./DonutRing";

const COLOR_MAP = {
  red: { text: "text-signal-red", hex: "#f0483e" },
  amber: { text: "text-signal-amber", hex: "#f5a623" },
  green: { text: "text-signal-green", hex: "#2ecc71" },
} as const;

export default function SignalStatusPanel({ signal }: { signal: SignalStatus }) {
  const c = COLOR_MAP[signal.color];
  const { greenS, yellowS, redS } = signal.cycleBreakdown;

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <h2 className="mb-3 font-display text-sm font-semibold text-text">Signal Status</h2>

      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="truncate text-sm text-text-secondary">{signal.phaseName}</div>
          <div className="font-mono text-3xl font-bold tabular-nums text-text">
            {signal.secondsRemaining}
            <span className="ml-1 text-sm font-normal text-text-muted">detik</span>
          </div>

          <div className="mt-3 space-y-1 text-xs">
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-signal-green" />
              <span className="text-text-secondary">Green</span>
              <span className="ml-auto font-mono tabular-nums text-text">{greenS}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-signal-amber" />
              <span className="text-text-secondary">Yellow</span>
              <span className="ml-auto font-mono tabular-nums text-text">{yellowS}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-signal-red" />
              <span className="text-text-secondary">Red</span>
              <span className="ml-auto font-mono tabular-nums text-text">{redS}</span>
            </div>
          </div>
        </div>

        <div className="relative shrink-0">
          <DonutRing
            size={92}
            thickness={11}
            segments={[
              { value: greenS, color: COLOR_MAP.green.hex },
              { value: yellowS, color: COLOR_MAP.amber.hex },
              { value: redS, color: COLOR_MAP.red.hex },
            ]}
          />
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <span className={`h-3 w-3 rounded-full ${c.text}`} style={{ backgroundColor: c.hex }} />
          </div>
        </div>
      </div>
    </div>
  );
}
