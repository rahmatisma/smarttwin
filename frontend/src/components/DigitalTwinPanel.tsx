import type {
  ApproachState,
  SignalStatus,
  Approach,
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

/*
 * =========================================================
 * DIGITAL TWIN PANEL
 * =========================================================
 */

export default function DigitalTwinPanel({
  approaches,
  signal,
}: {
  approaches: ApproachState[];
  signal: SignalStatus;
}) {
  /*
   * Mapping approach berdasarkan arah.
   */

  const byApproach = Object.fromEntries(
    approaches.map((approach) => [
      approach.approach,
      approach,
    ])
  ) as Record<Approach, ApproachState>;

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
    <div className="rounded-lg border border-border bg-surface p-4">
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
              signal.source === "mock"
                ? "bg-signal-amber"
                : "bg-signal-green"
            }`}
          />

          <span
            className={
              signal.source === "mock"
                ? "text-signal-amber"
                : "text-signal-green"
            }
          >
            {signal.source === "mock"
              ? "Simulated"
              : "Synced"}
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
          SVG INTERSECTION
          ===================================================== */}

      <svg
        viewBox="0 0 400 400"
        width={400}
        height={400}
        className="aspect-square w-full"
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
          x={382}
          y={205}
          textAnchor="middle"
          fill="#5b6472"
          fontSize={11}
          fontFamily="var(--font-sans)"
        >
          TIMUR
        </text>

        <text
          x={18}
          y={205}
          textAnchor="middle"
          fill="#5b6472"
          fontSize={11}
          fontFamily="var(--font-sans)"
        >
          BARAT
        </text>

        {/* =================================================
            QUEUE VISUALIZATION
            ================================================= */}

        {byApproach.north && (
          <QueueDots
            count={queueDotCount(
              byApproach.north.volume
            )}
            axis="y"
            from={150}
            step={-16}
            fixed={200}
          />
        )}

        {byApproach.south && (
          <QueueDots
            count={queueDotCount(
              byApproach.south.volume
            )}
            axis="y"
            from={250}
            step={16}
            fixed={200}
          />
        )}

        {byApproach.east && (
          <QueueDots
            count={queueDotCount(
              byApproach.east.volume
            )}
            axis="x"
            from={250}
            step={16}
            fixed={200}
          />
        )}

        {byApproach.west && (
          <QueueDots
            count={queueDotCount(
              byApproach.west.volume
            )}
            axis="x"
            from={150}
            step={-16}
            fixed={200}
          />
        )}

        {/* =================================================
            SIGNAL HEADS
            ================================================= */}

        <SignalHead
          x={200}
          y={152}
          vertical
          active={northColor}
        />

        <SignalHead
          x={200}
          y={248}
          vertical
          active={southColor}
        />

        <SignalHead
          x={248}
          y={200}
          vertical={false}
          active={eastColor}
        />

        <SignalHead
          x={152}
          y={200}
          vertical={false}
          active={westColor}
        />
      </svg>

      {/* =====================================================
          FOOTER
          ===================================================== */}

      <div className="mt-2 text-center">
        <p className="text-xs text-text-muted">
          Simulasi SUMO — posisi kendaraan indikatif,
          bukan video langsung
        </p>

        <p className="mt-1 text-[10px] text-text-muted">
          Fase: {signal.phaseName} · Sisa{" "}
          {signal.remainingSeconds} detik
        </p>
      </div>
    </div>
  );
}