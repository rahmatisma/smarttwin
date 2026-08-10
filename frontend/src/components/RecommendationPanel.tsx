import { TrendingDown, TrendingUp } from "lucide-react";
import type { SignalRecommendation } from "@/types/traffic";

export default function RecommendationPanel({
  recommendation,
}: {
  recommendation: SignalRecommendation;
}) {
  const s = recommendation.chosenScenario;

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-display text-sm font-semibold text-text">Rekomendasi</h2>
        <span className="rounded-full bg-accent-dim px-2 py-0.5 text-[10px] font-medium text-accent">
          {recommendation.engine === "ppo" ? "PPO" : "Rule-based"}
        </span>
      </div>

      <div className="mb-3 flex items-center gap-4">
        <div>
          <div className="text-xs text-text-secondary">Skor</div>
          <div className="font-mono text-2xl font-bold tabular-nums text-signal-green">
            {Math.round(s.avgDelayS > 0 ? 100 - s.avgDelayS : 0)}
          </div>
        </div>
        <div className="flex items-center gap-1 text-signal-green">
          <TrendingUp className="h-4 w-4" />
          <span className="font-mono text-sm tabular-nums">
            +{recommendation.expectedImprovementPct}%
          </span>
        </div>
        <div className="flex items-center gap-1 text-text-secondary">
          <TrendingDown className="h-4 w-4" />
          <span className="font-mono text-sm tabular-nums">{s.avgDelayS}s delay</span>
        </div>
      </div>

      <div className="mb-3 space-y-1.5">
        {s.phases.map((p) => (
          <div key={p.phaseName} className="flex items-center gap-2">
            <span className="w-32 shrink-0 truncate text-xs text-text-secondary">
              {p.phaseName}
            </span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2">
              <div
                className="h-full rounded-full bg-accent"
                style={{ width: `${(p.greenDurationS / s.cycleLengthS) * 100}%` }}
              />
            </div>
            <span className="w-8 shrink-0 text-right font-mono text-xs tabular-nums text-text-muted">
              {p.greenDurationS}s
            </span>
          </div>
        ))}
      </div>

      <button className="w-full rounded-md bg-accent py-2 text-sm font-semibold text-bg transition-opacity hover:opacity-90">
        Terapkan Rekomendasi
      </button>
    </div>
  );
}
