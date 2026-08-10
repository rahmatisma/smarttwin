import type { ApproachState, SignalStatus, Approach } from "@/types/traffic";

const SIGNAL_COLOR = {
  red: "#f0483e",
  amber: "#f5a623",
  green: "#2ecc71",
} as const;

function queueDotCount(volume: number) {
  return Math.min(Math.max(Math.round(volume / 45), 1), 7);
}

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
  const dots: Array<"red" | "amber" | "green"> = ["red", "amber", "green"];
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
      {dots.map((c, i) => {
        const isActive = c === active;
        const pos = vertical ? { cx: 0, cy: -8 + i * 8 } : { cx: -8 + i * 8, cy: 0 };
        return (
          <circle
            key={c}
            {...pos}
            r={2.6}
            fill={isActive ? SIGNAL_COLOR[c] : "#232935"}
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
      {Array.from({ length: count }).map((_, i) => {
        const moving = from + step * i;
        const cx = axis === "x" ? moving : fixed;
        const cy = axis === "x" ? fixed : moving;
        return <circle key={i} cx={cx} cy={cy} r={4} fill="#8b93a1" opacity={0.85} />;
      })}
    </>
  );
}

export default function DigitalTwinPanel({
  approaches,
  signal,
}: {
  approaches: ApproachState[];
  signal: SignalStatus;
}) {
  const byApproach = Object.fromEntries(
    approaches.map((a) => [a.approach, a])
  ) as Record<Approach, ApproachState>;

  const colorFor = (dir: Approach): "red" | "amber" | "green" =>
    signal.activePhase.includes(dir) ? signal.color : "red";

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-display text-sm font-semibold text-text">Digital Twin</h2>
        <span className="flex items-center gap-1.5 text-xs text-signal-green">
          <span className="h-1.5 w-1.5 rounded-full bg-signal-green" />
          Synced — TraCI Connected
        </span>
      </div>

      <svg viewBox="0 0 400 400" width={400} height={400} className="aspect-square w-full">
        <rect x={165} y={0} width={70} height={165} fill="#171c27" />
        <rect x={165} y={235} width={70} height={165} fill="#171c27" />
        <rect x={0} y={165} width={165} height={70} fill="#171c27" />
        <rect x={235} y={165} width={165} height={70} fill="#171c27" />
        <rect x={165} y={165} width={70} height={70} fill="#1c212d" />

        <line x1={200} y1={0} x2={200} y2={165} stroke="#2c3340" strokeWidth={2} strokeDasharray="10 8" />
        <line x1={200} y1={235} x2={200} y2={400} stroke="#2c3340" strokeWidth={2} strokeDasharray="10 8" />
        <line x1={0} y1={200} x2={165} y2={200} stroke="#2c3340" strokeWidth={2} strokeDasharray="10 8" />
        <line x1={235} y1={200} x2={400} y2={200} stroke="#2c3340" strokeWidth={2} strokeDasharray="10 8" />

        <text x={200} y={18} textAnchor="middle" fill="#5b6472" fontSize={11} fontFamily="var(--font-sans)">UTARA</text>
        <text x={200} y={392} textAnchor="middle" fill="#5b6472" fontSize={11} fontFamily="var(--font-sans)">SELATAN</text>
        <text x={382} y={205} textAnchor="middle" fill="#5b6472" fontSize={11} fontFamily="var(--font-sans)">TIMUR</text>
        <text x={18} y={205} textAnchor="middle" fill="#5b6472" fontSize={11} fontFamily="var(--font-sans)">BARAT</text>

        {byApproach.north && (
          <QueueDots count={queueDotCount(byApproach.north.volume)} axis="y" from={150} step={-16} fixed={200} />
        )}
        {byApproach.south && (
          <QueueDots count={queueDotCount(byApproach.south.volume)} axis="y" from={250} step={16} fixed={200} />
        )}
        {byApproach.east && (
          <QueueDots count={queueDotCount(byApproach.east.volume)} axis="x" from={250} step={16} fixed={200} />
        )}
        {byApproach.west && (
          <QueueDots count={queueDotCount(byApproach.west.volume)} axis="x" from={150} step={-16} fixed={200} />
        )}

        <SignalHead x={200} y={152} vertical active={colorFor("north")} />
        <SignalHead x={200} y={248} vertical active={colorFor("south")} />
        <SignalHead x={248} y={200} vertical={false} active={colorFor("east")} />
        <SignalHead x={152} y={200} vertical={false} active={colorFor("west")} />
      </svg>

      <p className="mt-2 text-center text-xs text-text-muted">
        Simulasi SUMO — posisi kendaraan indikatif, bukan video langsung
      </p>
    </div>
  );
}
