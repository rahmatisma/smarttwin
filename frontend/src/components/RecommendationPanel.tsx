import type { Recommendation } from "@/types/traffic";

export default function RecommendationPanel({
  recommendation,
}: {
  recommendation?: Recommendation | null;
}) {
  /*
   * =========================================================
   * NO RECOMMENDATION DATA
   * =========================================================
   *
   * Backend belum menyediakan recommendation.
   *
   * Jangan menggunakan data dummy.
   */
  if (!recommendation) {
    return (
      <div className="rounded-lg border border-border bg-surface p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-display text-sm font-semibold text-text">
            Signal Recommendation
          </h2>

          <span className="text-xs text-text-muted">
            Belum tersedia
          </span>
        </div>

        <div className="flex min-h-32 items-center justify-center rounded-md border border-border bg-surface-2 px-4 text-center">
          <p className="text-xs text-text-muted">
            Rekomendasi pengaturan lampu lalu lintas
            belum tersedia dari backend.
          </p>
        </div>
      </div>
    );
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
        {/* Recommended Phase */}
        <div className="rounded-md border border-border bg-surface-2 p-3">
          <div className="text-xs text-text-muted">
            Recommended Phase
          </div>

          <div className="mt-1 font-display text-sm font-semibold text-text">
            {recommendation.recommendedPhase}
          </div>
        </div>

        {/* Green Time */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-md border border-border bg-surface-2 p-3">
            <div className="text-xs text-text-muted">
              Recommended Green
            </div>

            <div className="mt-1 font-mono text-sm font-semibold text-text">
              {recommendation.recommendedGreenSeconds}s
            </div>
          </div>

          <div className="rounded-md border border-border bg-surface-2 p-3">
            <div className="text-xs text-text-muted">
              Current Green
            </div>

            <div className="mt-1 font-mono text-sm font-semibold text-text">
              {recommendation.currentGreenSeconds}s
            </div>
          </div>
        </div>

        {/* Expected Improvement */}
        <div className="rounded-md border border-border bg-surface-2 p-3">
          <div className="text-xs text-text-muted">
            Expected Delay Reduction
          </div>

          <div className="mt-1 font-mono text-sm font-semibold text-signal-green">
            {recommendation.expectedDelayReductionPercent.toFixed(1)}%
          </div>
        </div>

        {/* Confidence */}
        <div className="rounded-md border border-border bg-surface-2 p-3">
          <div className="text-xs text-text-muted">
            Confidence
          </div>

          <div className="mt-1 font-mono text-sm font-semibold text-text">
            {(recommendation.confidence * 100).toFixed(1)}%
          </div>
        </div>



        {/* Source */}
        <div className="flex items-center justify-between border-t border-border pt-2">
          <span className="text-[10px] text-text-muted">
            Source
          </span>

          <span className="text-[10px] text-text-secondary">
            {recommendation.source}
          </span>
        </div>
      </div>
    </div>
  );
}