import { useEffect, useState } from "react";
import type { ApproachPhase, Recommendation } from "@/types/traffic";
import { APPROACH_OPTIONS, type ApproachSelection } from "@/lib/intersections";

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
  isSelected,
  liveRemainingSeconds,
  liveTotalSeconds,
}: {
  phase: ApproachPhase;
  isSelected: boolean;
  // Kalau isSelected true DAN dua nilai ini ada, kotak ini
  // menampilkan hitung mundur LIVE (sama sumbernya dengan panel
  // Status Sinyal) -- bukan angka rekomendasi statis lagi, supaya
  // tidak ada dua angka berbeda untuk lengan yang sama.
  liveRemainingSeconds?: number;
  liveTotalSeconds?: number;
}) {
  const isLive =
    isSelected &&
    liveRemainingSeconds !== undefined &&
    liveTotalSeconds !== undefined &&
    liveTotalSeconds > 0;

  const displaySeconds = isLive
    ? liveRemainingSeconds
    : phase.greenSeconds;

  const barPercent = isLive
    ? Math.round(
        Math.min(1, Math.max(0, liveRemainingSeconds! / liveTotalSeconds!)) *
          100
      )
    : Math.round(Math.min(1, Math.max(0, phase.demandScore)) * 100);

  return (
    <div
      className={`rounded-md border p-2 text-center transition-colors ${
        isSelected
          ? "border-signal-green bg-surface-2 ring-1 ring-signal-green"
          : "border-border bg-surface-2"
      }`}
    >
      <div className="text-[10px] text-text-muted">
        {approachShortLabel(phase.approach)}
        {isLive && (
          <span className="ml-1 inline-block h-1.5 w-1.5 rounded-full bg-signal-green align-middle" />
        )}
      </div>

      <div className="mt-0.5 font-mono text-base font-semibold text-text">
        {displaySeconds}s
      </div>

      <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-border">
        <div
          className="h-full rounded-full bg-signal-green transition-all"
          style={{ width: `${barPercent}%` }}
        />
      </div>
    </div>
  );
}

export default function RecommendationPanel({
  recommendation,
  selectedApproach,
  activePhase,
  activeRemainingSeconds,
  activeCycleSeconds,
}: {
  recommendation?: Recommendation | null;
  selectedApproach?: ApproachSelection;
  // Lengan yang BENAR-BENAR hijau sekarang (live, dari
  // activeSignal.currentPhase di page.tsx -- sinkron dengan panel
  // Status Sinyal). Ini yang menentukan kotak mana disorot, BUKAN
  // selectedApproach (itu cuma menentukan label di kotak tengah).
  activePhase?: string;
  // activeSignal.remainingSeconds/cycleTimeSeconds -- dipakai supaya
  // kotak yang aktif menampilkan hitung mundur LIVE yang SAMA dengan
  // panel Status Sinyal, bukan angka rekomendasi statis.
  activeRemainingSeconds?: number;
  activeCycleSeconds?: number;
}) {
  /*
   * =========================================================
   * COUNTDOWN LOKAL utk kotak yang sedang aktif
   * =========================================================
   *
   * Pola sama seperti SignalStatusPanel -- turunkan sendiri tiap 1
   * detik, resync ke nilai backend tiap kali activeRemainingSeconds
   * berubah (poll 5 detik). Hook ini HARUS dipanggil sebelum early
   * return di bawah (aturan React: hooks tidak boleh kondisional).
   */
  const [displayActiveRemaining, setDisplayActiveRemaining] = useState(
    activeRemainingSeconds ?? 0
  );

  useEffect(() => {
    setDisplayActiveRemaining(activeRemainingSeconds ?? 0);
  }, [activeRemainingSeconds, activePhase]);

  useEffect(() => {
    const interval = setInterval(() => {
      setDisplayActiveRemaining((current) => Math.max(0, current - 1));
    }, 1000);

    return () => clearInterval(interval);
  }, []);

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

  const cyclePlan = recommendation.cyclePlan;

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
                  isSelected={activePhase === "north"}
                  liveRemainingSeconds={displayActiveRemaining}
                  liveTotalSeconds={activeCycleSeconds}
                />
              )}
              <div />

              {phaseByApproach.west && (
                <ApproachBox
                  phase={phaseByApproach.west}
                  isSelected={activePhase === "west"}
                  liveRemainingSeconds={displayActiveRemaining}
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
                  isSelected={activePhase === "east"}
                  liveRemainingSeconds={displayActiveRemaining}
                  liveTotalSeconds={activeCycleSeconds}
                />
              )}

              <div />
              {phaseByApproach.south && (
                <ApproachBox
                  phase={phaseByApproach.south}
                  isSelected={activePhase === "south"}
                  liveRemainingSeconds={displayActiveRemaining}
                  liveTotalSeconds={activeCycleSeconds}
                />
              )}
              <div />
            </div>
          </div>
        )}

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
