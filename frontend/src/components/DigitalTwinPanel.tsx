import { useState, useEffect, useRef } from "react";
import { Maximize2, Minimize2 } from "lucide-react";
import type {
  ApproachState,
  SignalStatus,
  Approach,
  CyclePlan,
} from "@/types/traffic";

// Instance SUMO dashboard ini TERPISAH dari instance sandbox di halaman
// /digitaltwin -- keduanya dibedakan lewat "context" supaya start/pause/
// stop/ganti-skenario di satu halaman tidak pernah menyentuh simulasi di
// halaman lain.
const SIM_CONTEXT = "dashboard";

/*
 * =========================================================
 * SIGNAL COLOR
 * =========================================================
 *
 * Warna ditentukan dari currentPhase.
 *
 * Ini hanya visualisasi frontend.
 *
 * Tidak ditambahkan ke data contract.
 */

const SIGNAL_COLOR = {
  red: "#f0483e",
  amber: "#f5a623",
  green: "#2ecc71",
} as const;

// Kalibrasi SUMO live dari pengamatan frame video CCTV anotasi yang
// diputar dashboard (video id 37-40, September 2026): antrean tiap
// lengan mencair/menumpuk + penghitung crossing ditelusuri selama 2
// putaran. Simpang Pingit fixed-time, urутan U -> T -> S -> B, video
// mulai tepat saat Utara hijau (offset ~0). Hijau ~ U/T/S/B = 40/45/
// 28/65 dtk, kuning 4 dtk, siklus ~194 dtk. Ketelitian +/- ~10 dtk --
// setel ulang di sini kalau pas demo fase SUMO masih meleset dari video.
// Nilai ini sengaja TIDAK dipakai oleh card rekomendasi/status sinyal.
const LIVE_SUMO_PHASES = [
  { approach: "north", greenSeconds: 40, yellowSeconds: 4 },
  { approach: "east", greenSeconds: 45, yellowSeconds: 4 },
  { approach: "south", greenSeconds: 28, yellowSeconds: 4 },
  { approach: "west", greenSeconds: 65, yellowSeconds: 4 },
] as const;

/*
 * =========================================================
 * QUEUE DOT
 * =========================================================
 */

function queueDotCount(volume: number) {
  /*
   * Divisor 15 disesuaikan dengan skala volume
   * hasil snapshot.
   *
   * Ini hanya representasi visual jumlah kendaraan
   * pada Digital Twin.
   */

  return Math.min(
    Math.max(Math.round(volume / 15), 1),
    7
  );
}

/*
 * =========================================================
 * SIGNAL HEAD
 * =========================================================
 */

function SignalHead({
  x,
  y,
  vertical,
  active,
}: {
  x: number;
  y: number;
  vertical: boolean;
  active: "red" | "amber" | "green";
}) {
  const dots: Array<"red" | "amber" | "green"> = [
    "red",
    "amber",
    "green",
  ];

  return (
    <g transform={`translate(${x}, ${y})`}>
      <rect
        x={vertical ? -7 : -13}
        y={vertical ? -13 : -7}
        width={vertical ? 14 : 26}
        height={vertical ? 26 : 14}
        rx={4}
        fill="#0a0e14"
        stroke="#232935"
        strokeWidth={1}
      />

      {dots.map((color, index) => {
        const isActive = color === active;

        const pos = vertical
          ? {
              cx: 0,
              cy: -8 + index * 8,
            }
          : {
              cx: -8 + index * 8,
              cy: 0,
            };

        return (
          <circle
            key={color}
            {...pos}
            r={2.6}
            fill={
              isActive
                ? SIGNAL_COLOR[color]
                : "#232935"
            }
            opacity={isActive ? 1 : 0.6}
          >
            {isActive && (
              <animate
                attributeName="opacity"
                values="1;0.55;1"
                dur="1.6s"
                repeatCount="indefinite"
              />
            )}
          </circle>
        );
      })}
    </g>
  );
}

/*
 * =========================================================
 * QUEUE DOTS
 * =========================================================
 */

function QueueDots({
  count,
  axis,
  from,
  step,
  fixed,
}: {
  count: number;
  axis: "x" | "y";
  from: number;
  step: number;
  fixed: number;
}) {
  return (
    <>
      {Array.from({ length: count }).map((_, index) => {
        const moving = from + step * index;

        const cx =
          axis === "x"
            ? moving
            : fixed;

        const cy =
          axis === "x"
            ? fixed
            : moving;

        return (
          <circle
            key={index}
            cx={cx}
            cy={cy}
            r={4}
            fill="#8b93a1"
            opacity={0.85}
          />
        );
      })}
    </>
  );
}

/*
 * =========================================================
 * SIGNAL STATE → VISUAL COLOR
 * =========================================================
 *
 * Contract hanya memberikan currentPhase.
 *
 * Kita tidak menambahkan activePhase/color ke object signal.
 * Warna visual dihitung di sini.
 */

function getSignalColor(
  currentPhase: string,
  approach: Approach
): "red" | "amber" | "green" {
  const phase = currentPhase.toLowerCase();

  const isNorthSouth =
    phase === "ns" ||
    phase.includes("north") ||
    phase.includes("south");

  const isEastWest =
    phase === "ew" ||
    phase.includes("east") ||
    phase.includes("west");

  const isAmber =
    phase.includes("amber") ||
    phase.includes("yellow");

  if (isNorthSouth) {
    if (
      approach === "north" ||
      approach === "south"
    ) {
      return isAmber ? "amber" : "green";
    }

    return "red";
  }

  if (isEastWest) {
    if (
      approach === "east" ||
      approach === "west"
    ) {
      return isAmber ? "amber" : "green";
    }

    return "red";
  }

  return "red";
}

type LiveSumoSignal = {
  state: "GREEN" | "YELLOW";
  activeApproach?: Approach;
  remainingSeconds: number;
  rawState?: string;
};

function normalizeLiveSignal(signal: LiveSumoSignal | undefined): LiveSumoSignal | null {
  if (!signal) return null;
  if (signal.activeApproach) return signal;

  const rawState = signal.rawState;
  if (!rawState) return null;
  const groups: Array<[Approach, string]> = [
    ["south", rawState.slice(0, 5)],
    ["east", rawState.slice(5, 10)],
    ["north", rawState.slice(10, 15)],
    ["west", rawState.slice(15, 20)],
  ];
  const active = groups.find(([, state]) => /[GgyY]/.test(state));
  if (!active) return null;

  return {
    ...signal,
    activeApproach: active[0],
    state: /[yY]/.test(active[1]) ? "YELLOW" : "GREEN",
  };
}

/*
 * =========================================================
 * DIGITAL TWIN PANEL
 * =========================================================
 */

export default function DigitalTwinPanel({
  approaches,
  signal,
  cyclePlan,
  trafficTimestamp,
  candidateId,
}: {
  approaches: ApproachState[];
  signal: SignalStatus;
  cyclePlan?: CyclePlan | null;
  trafficTimestamp?: string;
  candidateId?: string | null;
}) {
  const [simRunning, setSimRunning] = useState(false);
  const [simTime, setSimTime] = useState(0);
  const [vehiclesCount, setVehiclesCount] = useState(0);
  const [visibleVehicleCount, setVisibleVehicleCount] = useState(0);
  const [detectedVehicles, setDetectedVehicles] = useState(0);
  // Berapa kendaraan GAGAL disisipkan TraCI pada sinkronisasi demand
  // terakhir (mis. ruas masuk terlalu padat) -- kalau ini > 0, itu
  // penjelasan konkret kenapa "Total jaringan" bisa lebih kecil dari
  // "Deteksi", bukan cuma dugaan drift alami.
  const [lastSyncFailedInsertions, setLastSyncFailedInsertions] = useState(0);
  const [liveSignal, setLiveSignal] = useState<LiveSumoSignal | null>(null);
  const [frameVersion, setFrameVersion] = useState(0);
  const [simError, setSimError] = useState<string | null>(null);
  const [recoveryNonce, setRecoveryNonce] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const simulationViewRef = useRef<HTMLDivElement>(null);
  const fullscreenViewWasRequestedRef = useRef(false);
  const wasRunningRef = useRef(false);
  const runRequestInFlightRef = useRef(false);

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(document.fullscreenElement === simulationViewRef.current);
    };

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

  const toggleFullscreen = async () => {
    if (document.fullscreenElement === simulationViewRef.current) {
      await document.exitFullscreen();
      return;
    }

    await simulationViewRef.current?.requestFullscreen();
  };

  useEffect(() => {
    if (!simRunning) return;
    if (!isFullscreen && !fullscreenViewWasRequestedRef.current) return;

    fullscreenViewWasRequestedRef.current = isFullscreen;
    void fetch(
      `${API_BASE_URL}/api/v1/simulation/view?context=${SIM_CONTEXT}&mode=${isFullscreen ? "wide" : "compact"}`,
      { method: "POST" }
    ).then(async (response) => {
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? "Gagal mengubah cakupan kamera SUMO.");
      }
    }).catch((error) => {
      setSimError(error instanceof Error ? error.message : "Gagal mengubah cakupan kamera SUMO.");
    });

    return () => {
      if (isFullscreen) {
        void fetch(
          `${API_BASE_URL}/api/v1/simulation/view?context=${SIM_CONTEXT}&mode=compact`,
          { method: "POST" }
        );
      }
    };
  }, [API_BASE_URL, isFullscreen, simRunning]);

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/simulation/state?context=${SIM_CONTEXT}`);
        if (!res.ok) return;
        const data = await res.json();
        
        setSimRunning(data.running);
        if (data.running) {
          wasRunningRef.current = true;
          setSimError(null);
          setSimTime(data.simulationTimeSeconds ?? 0);
          setVehiclesCount(data.vehicles?.length ?? 0);
          setVisibleVehicleCount(data.visibleVehicleCount ?? 0);
          setDetectedVehicles(data.detectedVehicles ?? 0);
          setLastSyncFailedInsertions(data.lastSyncFailedInsertions ?? 0);
          setLiveSignal(normalizeLiveSignal(data.signals?.[0]));
        } else if (wasRunningRef.current) {
          // SUMO-GUI ditutup/crash di luar dashboard. Picu start ulang satu
          // kali; controller backend akan dibangun ulang tanpa reload halaman.
          wasRunningRef.current = false;
          setSimError("Renderer SUMO terputus. Mencoba menyambungkan kembali…");
          setRecoveryNonce((value) => value + 1);
        }
      } catch {
        setSimRunning(false);
        setSimError("Backend simulasi tidak dapat dihubungi.");
      }
    }, 500);
    return () => clearInterval(interval);
  }, [API_BASE_URL]);

  useEffect(() => {
    if (!simRunning) return;
    // Backend menulis gambar SUMO baru tiap 0,25 detik (4 gambar/detik).
    // Ambil gambar dengan irama yang sama supaya video tidak patah-patah;
    // sebelumnya 500 ms (2 gambar/detik) -- separuh dari yang tersedia.
    const interval = window.setInterval(
      () => setFrameVersion((version) => version + 1),
      250
    );
    return () => window.clearInterval(interval);
  }, [simRunning]);

  const livePayloadSignature = JSON.stringify({
    trafficTimestamp,
    approaches: approaches.map((approach) => ({
      approach: approach.approach,
      targetVehicleCount: Math.max(0, Math.round(approach.densityIndex)),
      motorcycleCount: approach.motorcycleCount,
      carCount: approach.carCount,
      busCount: approach.busCount,
      truckCount: approach.truckCount,
    })),
    cyclePlan,
    candidateId,
  });
  const canStartSimulation = approaches.length === 4 && Boolean(cyclePlan?.phases?.length);

  useEffect(() => {
    if (!canStartSimulation) return;
    if (runRequestInFlightRef.current) return;

    const payload = JSON.parse(livePayloadSignature);
    let cancelled = false;
    const abortController = new AbortController();
    const timeout = window.setTimeout(() => abortController.abort(), 20_000);
    runRequestInFlightRef.current = true;
    void fetch(`${API_BASE_URL}/api/v1/simulation/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: abortController.signal,
      body: JSON.stringify({
        context: SIM_CONTEXT,
        intersectionId: "simpang4-pingit",
        durationSeconds: 3600,
        gui: true,
        guiDelayMs: 0,
        seed: 42,
        trafficTimestamp: payload.trafficTimestamp,
        approaches: payload.approaches,
        cyclePlan: {
          phases: LIVE_SUMO_PHASES,
          candidateId: "observed-cctv-live",
          source: "observed-cctv",
          totalCycleSeconds: 194,
        },
      }),
    })
      .then(async (response) => {
        if (!response.ok) {
          const payload = await response.json().catch(() => null);
          throw new Error(payload?.detail ?? "Gagal memulai SUMO");
        }
        if (!cancelled) {
          wasRunningRef.current = true;
          setSimRunning(true);
          setSimError(null);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          const message = error instanceof DOMException && error.name === "AbortError"
            ? "SUMO tidak merespons dalam 20 detik. Periksa backend/SUMO."
            : error instanceof Error ? error.message : "SUMO tidak tersedia.";
          setSimError(message);
        }
      })
      .finally(() => {
        window.clearTimeout(timeout);
        runRequestInFlightRef.current = false;
      });

    return () => {
      cancelled = true;
    };
  }, [API_BASE_URL, canStartSimulation, livePayloadSignature, recoveryNonce]);
  /*
   * Mapping approach berdasarkan arah.
   */

  /*
   * Partial, BUKAN Record penuh. Sebelumnya di-cast paksa jadi
   * Record<Approach, ApproachState> -- itu janji palsu ke
   * TypeScript: isinya bergantung data, jadi arah yang tidak ada
   * bernilai undefined saat runtime sementara compiler diam.
   * Akibatnya `byApproach.north.queueLengthVeh` crash begitu
   * salah satu arah absen (render awal sebelum data masuk, atau
   * dulu waktu panel ini masih diberi daftar hasil filter lengan).
   */
  const byApproach = Object.fromEntries(
    approaches.map((approach) => [
      approach.approach,
      approach,
    ])
  ) as Partial<Record<Approach, ApproachState>>;

  /*
   * Arah yang belum ada datanya dianggap antrean kosong, bukan
   * bikin komponen mati -- denah simpang tetap tergambar utuh.
   */
  const queueOf = (arah: Approach) =>
    byApproach[arah]?.queueLengthVeh ?? 0;

  /*
   * Warna signal dihitung dari currentPhase.
   */

  const northColor = getSignalColor(
    signal.currentPhase,
    "north"
  );

  const southColor = getSignalColor(
    signal.currentPhase,
    "south"
  );

  const eastColor = getSignalColor(
    signal.currentPhase,
    "east"
  );

  const westColor = getSignalColor(
    signal.currentPhase,
    "west"
  );

  return (
    <div className="flex h-full flex-col rounded-lg border border-border bg-surface p-4">
      {/* =====================================================
          HEADER
          ===================================================== */}

      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-display text-sm font-semibold text-text">
          Digital Twin
        </h2>

        <span className="flex items-center gap-1.5 text-xs">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              simRunning
                ? "bg-signal-green"
                : signal.source === "mock"
                ? "bg-signal-amber"
                : "bg-signal-green"
            }`}
          />

          <span
            className={
              simRunning
                ? "text-signal-green font-bold"
                : signal.source === "mock"
                ? "text-signal-amber"
                : "text-signal-green"
            }
          >
            {simRunning ? "LIVE ●" : signal.source === "mock" ? "Simulated" : "Synced"}
          </span>
        </span>
      </div>

      {/* =====================================================
          INTERSECTION
          ===================================================== */}

      <div className="mb-3 flex items-center justify-between text-xs">
        <span className="text-text-muted">
          Intersection
        </span>

        <span className="font-mono text-text-secondary">
          {signal.intersectionId}
        </span>
      </div>

      {simError && (
        <div role="status" className="mb-3 rounded-md border border-signal-amber/40 bg-signal-amber/10 px-3 py-2 text-xs text-signal-amber">
          {simError}
        </div>
      )}

      {/* =====================================================
          SVG INTERSECTION OR LIVE STREAM
          ===================================================== */}

      <div
        ref={simulationViewRef}
        className={`relative w-full overflow-hidden bg-[var(--color-canvas)] ${
          isFullscreen ? "h-screen" : "aspect-[16/11] rounded-md"
        }`}
      >
        {simRunning ? (
          <>
            {/* Frame berubah terus dan tidak boleh masuk cache/optimizer Next Image. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={`${API_BASE_URL}/api/v1/simulation/frame?context=${SIM_CONTEXT}&v=${frameVersion}`}
              alt="Live SUMO Simpang Pingit"
              className="absolute inset-0 h-full w-full object-cover object-center"
            />
            {([
              ["north", "UTARA · Jl. Magelang", "left-1/2 top-1 -translate-x-1/2"],
              ["east", "TIMUR · Jl. Diponegoro", "right-1 top-1/2 -translate-y-1/2"],
              ["south", "SELATAN · Jl. Tentara Pelajar", "bottom-1 left-1/2 -translate-x-1/2"],
              ["west", "BARAT · Jl. Kyai Mojo", "left-1 top-1/2 -translate-y-1/2"],
            ] as const).map(([approach, label, position]) => {
              const isActive = liveSignal?.activeApproach === approach;
              const lampClass = !isActive
                ? "bg-signal-red"
                : liveSignal.state === "YELLOW"
                  ? "bg-signal-amber"
                  : "bg-signal-green";
              return (
                <div key={approach} className={`absolute ${position} flex items-center gap-1 rounded bg-black/75 px-1.5 py-0.5 text-[9px] font-semibold text-white`}>
                  <i className={`h-2.5 w-2.5 shrink-0 rounded-full border border-white/40 ${lampClass}`} />
                  {label}
                </div>
              );
            })}
            <div className="absolute left-2 top-2 flex gap-2 rounded-md border border-white/10 bg-black/55 px-2 py-1 text-[10px] text-white backdrop-blur-sm">
              <span className="flex items-center gap-1"><i className="h-2 w-2 rounded-full bg-signal-red" />Merah</span>
              <span className="flex items-center gap-1"><i className="h-2 w-2 rounded-full bg-signal-amber" />Kuning</span>
              <span className="flex items-center gap-1"><i className="h-2 w-2 rounded-full bg-signal-green" />Hijau</span>
            </div>
            <button
              type="button"
              onClick={() => void toggleFullscreen()}
              className="absolute right-2 top-2 z-10 flex h-9 w-9 items-center justify-center rounded-lg border border-white/20 bg-black/60 text-white shadow-sm backdrop-blur-sm transition hover:bg-black/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
              aria-label={isFullscreen ? "Keluar dari layar penuh" : "Tampilkan SUMO dalam layar penuh"}
              title={isFullscreen ? "Keluar dari layar penuh (Esc)" : "Layar penuh"}
            >
              {isFullscreen ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
            </button>
            <div className="absolute bottom-2 right-2 rounded-lg border border-white/10 bg-black/50 px-2 py-1 backdrop-blur-sm">
              <p className="font-mono text-xs font-medium text-white">
                {Math.floor(simTime / 60).toString().padStart(2, '0')}:{(Math.floor(simTime) % 60).toString().padStart(2, '0')}
              </p>
            </div>
            {/* max-w FIXED (bukan persentase) supaya lebar box gak ikut lebar
                panel -- lebar label lengan SELATAN itu tetap (font-size tetap),
                jadi cuma batas lebar tetap yang menjamin box ini tidak pernah
                menembus area SELATAN (bottom-center) di panel sempit maupun lebar. */}
            <div className="absolute bottom-2 left-2 max-w-[130px] rounded-lg border border-white/10 bg-black/50 px-2 py-1 backdrop-blur-sm">
              <p className="font-mono text-[10px] font-medium leading-snug text-white">
                Deteksi: {detectedVehicles} · Terlihat: {visibleVehicleCount} · Total jaringan: {vehiclesCount}
                {lastSyncFailedInsertions > 0 && (
                  <span className="text-signal-amber"> · Gagal sisip: {lastSyncFailedInsertions}</span>
                )}
              </p>
            </div>
          </>
        ) : (
          <svg
            viewBox="0 0 400 400"
            className="absolute inset-0 h-full w-full"
          >
            {/* North road */}

            <rect
              x={165}
              y={0}
              width={70}
              height={165}
              fill="#171c27"
            />

            {/* South road */}

            <rect
              x={165}
              y={235}
              width={70}
              height={165}
              fill="#171c27"
            />

            {/* West road */}

            <rect
              x={0}
              y={165}
              width={165}
              height={70}
              fill="#171c27"
            />

            {/* East road */}

            <rect
              x={235}
              y={165}
              width={165}
              height={70}
              fill="#171c27"
            />

            {/* Intersection */}

            <rect
              x={165}
              y={165}
              width={70}
              height={70}
              fill="#1c212d"
            />

            {/* Lane markings */}

            <line
              x1={200}
              y1={0}
              x2={200}
              y2={165}
              stroke="#2c3340"
              strokeWidth={2}
              strokeDasharray="10 8"
            />

            <line
              x1={200}
              y1={235}
              x2={200}
              y2={400}
              stroke="#2c3340"
              strokeWidth={2}
              strokeDasharray="10 8"
            />

            <line
              x1={0}
              y1={200}
              x2={165}
              y2={200}
              stroke="#2c3340"
              strokeWidth={2}
              strokeDasharray="10 8"
            />

            <line
              x1={235}
              y1={200}
              x2={400}
              y2={200}
              stroke="#2c3340"
              strokeWidth={2}
              strokeDasharray="10 8"
            />

            {/* =================================================
                DIRECTION LABELS
                ================================================= */}

            <text
              x={200}
              y={18}
              textAnchor="middle"
              fill="#5b6472"
              fontSize={11}
              fontFamily="var(--font-sans)"
            >
              UTARA
            </text>

            <text
              x={200}
              y={392}
              textAnchor="middle"
              fill="#5b6472"
              fontSize={11}
              fontFamily="var(--font-sans)"
            >
              SELATAN
            </text>

            <text
              x={375}
              y={204}
              textAnchor="middle"
              fill="#5b6472"
              fontSize={11}
              fontFamily="var(--font-sans)"
            >
              TIMUR
            </text>

            <text
              x={25}
              y={204}
              textAnchor="middle"
              fill="#5b6472"
              fontSize={11}
              fontFamily="var(--font-sans)"
            >
              BARAT
            </text>

            {/* =================================================
                QUEUE DOTS
                ================================================= */}

            <QueueDots
              count={queueDotCount(queueOf("north"))}
              axis="y"
              fixed={180}
              from={150}
              step={-10}
            />

            <QueueDots
              count={queueDotCount(queueOf("south"))}
              axis="y"
              fixed={220}
              from={250}
              step={10}
            />

            <QueueDots
              count={queueDotCount(queueOf("east"))}
              axis="x"
              fixed={180}
              from={250}
              step={10}
            />

            <QueueDots
              count={queueDotCount(queueOf("west"))}
              axis="x"
              fixed={220}
              from={150}
              step={-10}
            />

            {/* =================================================
                SIGNAL HEADS
                ================================================= */}

            {/* North */}
            <SignalHead
              x={152}
              y={150}
              vertical={false}
              active={northColor}
            />

            {/* South */}
            <SignalHead
              x={248}
              y={250}
              vertical={false}
              active={southColor}
            />

            {/* East */}
            <SignalHead
              x={248}
              y={150}
              vertical={true}
              active={eastColor}
            />

            {/* West */}
            <SignalHead
              x={152}
              y={200}
              vertical={true}
              active={westColor}
            />
          </svg>
        )}
      </div>

      {/* =====================================================
          FOOTER
          ===================================================== */}

      <div className="mt-2 text-center">
        <p className="text-xs text-text-muted">
          SUMO live · demand dari TrafficState dashboard
        </p>

        <p className="mt-1 text-[10px] text-text-muted">
          Fase: {signal.phaseName} · Sisa{" "}
          {signal.remainingSeconds} detik
        </p>
      </div>
    </div>
  );
}
