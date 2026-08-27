import { useState, useEffect } from "react";
import type {
  ApproachState,
  SignalStatus,
  Approach,
  CyclePlan,
} from "@/types/traffic";

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

// Kalibrasi khusus SUMO live dari observasi durasi merah CCTV:
// Selatan 177 dtk, Barat 180 dtk, Timur 163 dtk. Dengan kuning 4 dtk
// dan siklus 227 dtk diperoleh hijau U/T/S/B = 62/60/46/43 dtk.
// Nilai ini sengaja TIDAK dipakai oleh card rekomendasi/status sinyal.
const LIVE_SUMO_PHASES = [
  { approach: "north", greenSeconds: 62, yellowSeconds: 4 },
  { approach: "east", greenSeconds: 60, yellowSeconds: 4 },
  { approach: "south", greenSeconds: 46, yellowSeconds: 4 },
  { approach: "west", greenSeconds: 43, yellowSeconds: 4 },
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
  activeApproach: Approach;
  remainingSeconds: number;
};

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
  const [detectedVehicles, setDetectedVehicles] = useState(0);
  const [liveSignal, setLiveSignal] = useState<LiveSumoSignal | null>(null);
  const [frameVersion, setFrameVersion] = useState(0);

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/simulation/state`);
        if (!res.ok) return;
        const data = await res.json();
        
        setSimRunning(data.running);
        if (data.running) {
          setSimTime(data.simulationTimeSeconds ?? 0);
          setVehiclesCount(data.vehicles?.length ?? 0);
          setDetectedVehicles(data.detectedVehicles ?? 0);
          setLiveSignal(data.signals?.[0] ?? null);
        }
      } catch {
        setSimRunning(false);
      }
    }, 500);
    return () => clearInterval(interval);
  }, [API_BASE_URL]);

  useEffect(() => {
    if (!simRunning) return;
    const interval = window.setInterval(
      () => setFrameVersion((version) => version + 1),
      500
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

    const payload = JSON.parse(livePayloadSignature);
    let cancelled = false;
    void fetch(`${API_BASE_URL}/api/v1/simulation/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        intersectionId: "simpang4-pingit",
        durationSeconds: 86400,
        gui: true,
        guiDelayMs: 0,
        seed: 42,
        trafficTimestamp: payload.trafficTimestamp,
        approaches: payload.approaches,
        cyclePlan: {
          phases: LIVE_SUMO_PHASES,
          candidateId: "observed-cctv-live",
          source: "observed-cctv",
          totalCycleSeconds: 227,
        },
      }),
    })
      .then((response) => {
        if (!cancelled && response.ok) setSimRunning(true);
      })
      .catch(() => {
        // Polling state menampilkan denah fallback jika backend/SUMO mati.
      });

    return () => {
      cancelled = true;
    };
  }, [API_BASE_URL, canStartSimulation, livePayloadSignature]);
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

      {/* =====================================================
          SVG INTERSECTION OR LIVE STREAM
          ===================================================== */}

      <div className="relative aspect-video w-full overflow-hidden rounded-md bg-[var(--color-canvas)]">
        {simRunning ? (
          <>
            <img
              src={`${API_BASE_URL}/api/v1/simulation/frame?v=${frameVersion}`}
              alt="Live SUMO Simpang Pingit"
              className="absolute inset-0 h-full w-full object-contain"
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
            <div className="absolute bottom-2 right-2 rounded-lg border border-white/10 bg-black/50 px-2 py-1 backdrop-blur-sm">
              <p className="font-mono text-xs font-medium text-white">
                {Math.floor(simTime / 60).toString().padStart(2, '0')}:{(Math.floor(simTime) % 60).toString().padStart(2, '0')}
              </p>
            </div>
            <div className="absolute bottom-2 left-2 rounded-lg border border-white/10 bg-black/50 px-2 py-1 backdrop-blur-sm">
              <p className="font-mono text-xs font-medium text-white">
                Deteksi: {detectedVehicles} · Aktif SUMO: {vehiclesCount}
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
