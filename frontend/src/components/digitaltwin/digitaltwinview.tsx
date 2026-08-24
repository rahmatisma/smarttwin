"use client";

import { useState, useEffect, useRef } from "react";
import {
    Play,
    Pause,
    RotateCcw,
    Zap,
    Car,
    Gauge,
    List,
    Clock3,
    Activity,
    Map,
    Settings2,
    ChevronDown,
    Circle,
} from "lucide-react";

import Sidebar from "@/components/Sidebar";

type SimulationStatus = "idle" | "running" | "paused";

interface VehicleData {
    id: string;
    x: number;
    y: number;
    angle: number;
    type: string;
}

export default function DigitalTwinView() {
    const [status, setStatus] =
        useState<SimulationStatus>("idle");
    const [loading, setLoading] = useState(false);
    const [vehicles, setVehicles] = useState<VehicleData[]>([]);
    
    // Auto-calibration bounds
    const boundsRef = useRef({ minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity });

    const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

    useEffect(() => {
        if (status !== "running") return;

        const interval = setInterval(async () => {
            try {
                const res = await fetch(`${API_BASE_URL}/api/v1/simulation/positions`);
                if (!res.ok) return;
                const data: VehicleData[] = await res.json();
                
                // Update bounds
                let { minX, maxX, minY, maxY } = boundsRef.current;
                let changed = false;
                data.forEach(v => {
                    if (v.x < minX) { minX = v.x; changed = true; }
                    if (v.x > maxX) { maxX = v.x; changed = true; }
                    if (v.y < minY) { minY = v.y; changed = true; }
                    if (v.y > maxY) { maxY = v.y; changed = true; }
                });
                
                // Add some padding to bounds so cars don't hit the absolute edge
                if (changed && minX !== Infinity) {
                    boundsRef.current = { minX, maxX, minY, maxY };
                }

                setVehicles(data);
            } catch (err) {
                console.error("Failed to fetch positions:", err);
            }
        }, 500);

        return () => clearInterval(interval);
    }, [status, API_BASE_URL]);

    async function handleStartSimulation() {
        setLoading(true);
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/simulation/run`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    intersectionId: "simpang4-pingit",
                    durationSeconds: 60,
                    gui: false,
                    guiDelayMs: 100,
                    seed: 42
                }),
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || "Gagal memulai simulasi");
            }

            // Simulasi berhasil berjalan
            setStatus("running");
        } catch (error) {
            console.error(error);
            alert(error instanceof Error ? error.message : "Terjadi kesalahan saat memulai simulasi");
        } finally {
            setLoading(false);
        }
    }

    const [speed, setSpeed] = useState("1x");

    const [scenario, setScenario] =
        useState("Adaptive Signal");

    return (
        <div className="flex min-h-screen bg-background text-text">
            <Sidebar />

            <main className="min-w-0 flex-1 bg-background px-5 py-6 md:px-7">
                <div className="mx-auto w-full max-w-[1400px]">

                {/* ================================================= */}
                {/* HEADER */}
                {/* ================================================= */}

                <div className="mb-6 flex flex-col justify-between gap-4 md:flex-row md:items-end">

                    <div>
                        <div className="mb-2 flex items-center gap-2">

                            <span className="h-2.5 w-2.5 rounded-full bg-signal-green" />

                            <h1 className="font-display text-2xl font-semibold">
                                Digital Twin
                            </h1>

                        </div>

                        <p className="text-sm text-text-muted">
                            Simulasi digital persimpangan dan optimasi traffic signal.
                        </p>
                    </div>

                    {/* Simulation status */}

                    <div className="flex items-center gap-2 rounded-xl border border-border bg-surface px-4 py-2.5">

                        <span
                            className={`h-2 w-2 rounded-full ${
                                status === "running"
                                    ? "bg-signal-green"
                                    : status === "paused"
                                    ? "bg-yellow-400"
                                    : "bg-text-muted"
                            }`}
                        />

                        <span className="text-xs font-medium">
                            {status === "running"
                                ? "Simulation Running"
                                : status === "paused"
                                ? "Simulation Paused"
                                : "Simulation Ready"}
                        </span>

                    </div>

                </div>

                {/* ================================================= */}
                {/* MAIN SIMULATION */}
                {/* ================================================= */}

                <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">

                    {/* =============================== */}
                    {/* DIGITAL TWIN CANVAS */}
                    {/* =============================== */}

                    <div className="overflow-hidden rounded-2xl border border-border bg-surface shadow-sm">

                        {/* Canvas header */}

                        <div className="flex items-center justify-between border-b border-border px-5 py-4">

                            <div className="flex items-center gap-3">

                                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-2">
                                    <Map
                                        size={18}
                                        className="text-text-secondary"
                                    />
                                </div>

                                <div>
                                    <h2 className="text-sm font-semibold">
                                        Intersection Simulation
                                    </h2>

                                    <p className="text-xs text-text-muted">
                                        Simpang 4 Pingit
                                    </p>
                                </div>

                            </div>

                            <button
                                type="button"
                                className="rounded-lg border border-border p-2 text-text-secondary transition hover:bg-surface-2"
                            >
                                <Settings2 size={17} />
                            </button>

                        </div>

                        {/* Simulation area */}

                        <div className="relative h-[460px] overflow-hidden bg-[var(--color-canvas)]">

                            {/* Grid */}

                            <div
                                className="absolute inset-0 opacity-30"
                                style={{
                                    backgroundImage:
                                        "linear-gradient(var(--color-canvas-grid) 1px, transparent 1px), linear-gradient(90deg, var(--color-canvas-grid) 1px, transparent 1px)",
                                    backgroundSize: "32px 32px",
                                }}
                            />

                            {/* Road horizontal */}

                            <div className="absolute left-0 right-0 top-1/2 h-40 -translate-y-1/2 bg-[var(--color-road)]" />

                            {/* Road vertical */}

                            <div className="absolute bottom-0 left-1/2 top-0 w-40 -translate-x-1/2 bg-[var(--color-road)]" />

                            {/* Horizontal road markings */}

                            <div className="absolute left-0 right-0 top-[calc(50%-1px)] border-t-2 border-dashed border-white/30" />

                            <div className="absolute left-0 right-0 top-[calc(50%+1px)] border-t-2 border-dashed border-white/30" />

                            {/* Vertical road markings */}

                            <div className="absolute bottom-0 left-[calc(50%-1px)] top-0 border-l-2 border-dashed border-white/30" />

                            <div className="absolute bottom-0 left-[calc(50%+1px)] top-0 border-l-2 border-dashed border-white/30" />

                            {/* Intersection center */}

                            <div className="absolute left-1/2 top-1/2 h-40 w-40 -translate-x-1/2 -translate-y-1/2 bg-[var(--color-road-center)]" />

                            {/* Traffic lights */}

                            <TrafficLight
                                position="top"
                                color="green"
                            />

                            <TrafficLight
                                position="right"
                                color="red"
                            />

                            <TrafficLight
                                position="bottom"
                                color="green"
                            />

                            <TrafficLight
                                position="left"
                                color="red"
                            />

                            {/* Dynamic Vehicles */}
                            
                            {vehicles.map((v) => {
                                const { minX, maxX, minY, maxY } = boundsRef.current;
                                
                                // Default to center if bounds not established
                                let left = 50;
                                let top = 50;
                                
                                if (minX !== Infinity && maxX > minX && maxY > minY) {
                                    // Calculate percentage with 5% padding so they stay in view
                                    left = ((v.x - minX) / (maxX - minX)) * 90 + 5;
                                    // SUMO Y is bottom-to-top, CSS top is top-to-bottom
                                    top = (1 - (v.y - minY) / (maxY - minY)) * 90 + 5;
                                }

                                return (
                                    <DynamicVehicle
                                        key={v.id}
                                        left={left}
                                        top={top}
                                        angle={v.angle}
                                        type={v.type}
                                    />
                                );
                            })}

                            {/* Simulation label */}

                            <div className="absolute left-5 top-5 rounded-lg border border-white/10 bg-black/50 px-3 py-2 backdrop-blur-sm">

                                <p className="text-[10px] uppercase tracking-wider text-white/50">
                                    Scenario
                                </p>

                                <p className="mt-0.5 text-xs font-medium text-white">
                                    {scenario}
                                </p>

                            </div>

                            {/* Simulation time */}

                            <div className="absolute bottom-5 right-5 rounded-lg border border-white/10 bg-black/50 px-3 py-2 backdrop-blur-sm">

                                <p className="text-[10px] uppercase tracking-wider text-white/50">
                                    Simulation Time
                                </p>

                                <p className="mt-0.5 font-mono text-sm font-medium text-white">
                                    00:02:34
                                </p>

                            </div>

                        </div>

                    </div>

                    {/* =============================== */}
                    {/* SIMULATION STATUS */}
                    {/* =============================== */}

                    <div className="space-y-5">

                        {/* Status */}

                        <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">

                            <div className="mb-5 flex items-center gap-3">

                                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-2">
                                    <Activity
                                        size={18}
                                        className="text-text-secondary"
                                    />
                                </div>

                                <div>
                                    <h2 className="text-sm font-semibold">
                                        Simulation Status
                                    </h2>

                                    <p className="text-xs text-text-muted">
                                        Real-time simulation metrics
                                    </p>
                                </div>

                            </div>

                            <div className="space-y-4">

                                <MetricRow
                                    label="Simulation Time"
                                    value="02:34"
                                    icon={<Clock3 size={15} />}
                                />

                                <MetricRow
                                    label="Vehicles"
                                    value="128"
                                    icon={<Car size={15} />}
                                />

                                <MetricRow
                                    label="Average Speed"
                                    value="32 km/h"
                                    icon={<Gauge size={15} />}
                                />

                                <MetricRow
                                    label="Queue Length"
                                    value="14"
                                    icon={<List size={15} />}
                                />

                            </div>

                        </div>

                        {/* Current phase */}

                        <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">

                            <div className="mb-4 flex items-center justify-between">

                                <div>
                                    <h2 className="text-sm font-semibold">
                                        Current Phase
                                    </h2>

                                    <p className="mt-1 text-xs text-text-muted">
                                        North — South
                                    </p>
                                </div>

                                <span className="flex items-center gap-1.5 rounded-full bg-signal-green/10 px-2.5 py-1 text-[10px] font-medium text-signal-green">
                                    <Circle
                                        size={7}
                                        fill="currentColor"
                                    />
                                    GREEN
                                </span>

                            </div>

                            <div className="h-2 overflow-hidden rounded-full bg-surface-2">

                                <div className="h-full w-[64%] rounded-full bg-signal-green" />

                            </div>

                            <div className="mt-2 flex justify-between text-[10px] text-text-muted">

                                <span>00:32</span>

                                <span>Remaining</span>

                            </div>

                        </div>

                    </div>

                </div>

                {/* ================================================= */}
                {/* METRICS */}
                {/* ================================================= */}

                <div className="mt-5 grid grid-cols-2 gap-4 lg:grid-cols-4">

                    <StatCard
                        label="Vehicles"
                        value="128"
                        change="+12%"
                        icon={<Car size={18} />}
                    />

                    <StatCard
                        label="Average Speed"
                        value="32 km/h"
                        change="+8.4%"
                        icon={<Gauge size={18} />}
                    />

                    <StatCard
                        label="Queue Length"
                        value="14"
                        change="-18%"
                        icon={<List size={18} />}
                    />

                    <StatCard
                        label="Traffic Flow"
                        value="1,284 veh/h"
                        change="+6.2%"
                        icon={<Zap size={18} />}
                    />

                </div>

                {/* ================================================= */}
                {/* BOTTOM SECTION */}
                {/* ================================================= */}

                <div className="mt-5 grid gap-5 lg:grid-cols-2">

                    {/* =============================== */}
                    {/* SIMULATION CONTROLS */}
                    {/* =============================== */}

                    <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">

                        <div className="mb-5 flex items-center gap-3">

                            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-2">
                                <Settings2 size={18} />
                            </div>

                            <div>
                                <h2 className="text-sm font-semibold">
                                    Simulation Controls
                                </h2>

                                <p className="text-xs text-text-muted">
                                    Configure simulation parameters
                                </p>
                            </div>

                        </div>

                        <div className="grid gap-5 sm:grid-cols-2">

                            {/* Scenario */}

                            <div>

                                <label className="mb-2 block text-xs font-medium text-text-secondary">
                                    Scenario
                                </label>

                                <div className="relative">

                                    <select
                                        value={scenario}
                                        onChange={(e) =>
                                            setScenario(
                                                e.target.value
                                            )
                                        }
                                        className="w-full appearance-none rounded-xl border border-border bg-surface px-3 py-2.5 pr-9 text-sm outline-none transition focus:border-text-muted"
                                    >
                                        <option>
                                            Adaptive Signal
                                        </option>

                                        <option>
                                            Fixed Time
                                        </option>

                                        <option>
                                            High Traffic
                                        </option>

                                        <option>
                                            Low Traffic
                                        </option>
                                    </select>

                                    <ChevronDown
                                        size={15}
                                        className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-text-muted"
                                    />

                                </div>

                            </div>

                            {/* Speed */}

                            <div>

                                <label className="mb-2 block text-xs font-medium text-text-secondary">
                                    Simulation Speed
                                </label>

                                <div className="flex gap-2">

                                    {["1x", "2x", "4x"].map(
                                        (item) => (
                                            <button
                                                key={item}
                                                type="button"
                                                onClick={() =>
                                                    setSpeed(
                                                        item
                                                    )
                                                }
                                                className={`flex-1 rounded-xl border px-3 py-2.5 text-xs font-medium transition ${
                                                    speed ===
                                                    item
                                                        ? "border-accent bg-accent text-bg"
                                                        : "border-border text-text-secondary hover:bg-surface-2"
                                                }`}
                                            >
                                                {item}
                                            </button>
                                        )
                                    )}

                                </div>

                            </div>

                        </div>

                        {/* Buttons */}

                        <div className="mt-6 flex gap-3">

                            {status === "running" ? (
                                <button
                                    type="button"
                                    onClick={() =>
                                        setStatus(
                                            "paused"
                                        )
                                    }
                                    className="flex items-center gap-2 rounded-xl bg-accent px-5 py-2.5 text-xs font-medium text-bg transition hover:opacity-90"
                                >
                                    <Pause size={15} />
                                    Pause Simulation
                                </button>
                            ) : (
                                <button
                                    type="button"
                                    onClick={handleStartSimulation}
                                    disabled={loading}
                                    className="flex items-center gap-2 rounded-xl bg-accent px-5 py-2.5 text-xs font-medium text-bg transition hover:opacity-90 disabled:opacity-50"
                                >
                                    <Play size={15} />
                                    {loading ? "Starting..." : "Start Simulation"}
                                </button>
                            )}

                            <button
                                type="button"
                                onClick={() =>
                                    setStatus("idle")
                                }
                                className="flex items-center gap-2 rounded-xl border border-border px-5 py-2.5 text-xs font-medium text-text-secondary transition hover:bg-surface-2"
                            >
                                <RotateCcw size={15} />
                                Reset
                            </button>

                        </div>

                    </div>

                    {/* =============================== */}
                    {/* SIGNAL STATUS */}
                    {/* =============================== */}

                    <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">

                        <div className="mb-5 flex items-center gap-3">

                            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-2">
                                <Zap size={18} />
                            </div>

                            <div>
                                <h2 className="text-sm font-semibold">
                                    Signal Status
                                </h2>

                                <p className="text-xs text-text-muted">
                                    Traffic signal state
                                </p>
                            </div>

                        </div>

                        <div className="space-y-3">

                            <SignalRow
                                direction="North"
                                state="GREEN"
                                time="32s"
                            />

                            <SignalRow
                                direction="East"
                                state="RED"
                                time="18s"
                            />

                            <SignalRow
                                direction="South"
                                state="GREEN"
                                time="32s"
                            />

                            <SignalRow
                                direction="West"
                                state="RED"
                                time="18s"
                            />

                        </div>

                    </div>

                </div>

                </div>
            </main>
        </div>
    );
}

/* ========================================================= */
/* COMPONENTS */
/* ========================================================= */

function MetricRow({
    label,
    value,
    icon,
}: {
    label: string;
    value: string;
    icon: React.ReactNode;
}) {
    return (
        <div className="flex items-center justify-between">

            <div className="flex items-center gap-2 text-text-muted">

                {icon}

                <span className="text-xs">
                    {label}
                </span>

            </div>

            <span className="font-mono text-xs font-medium">
                {value}
            </span>

        </div>
    );
}

function StatCard({
    label,
    value,
    change,
    icon,
}: {
    label: string;
    value: string;
    change: string;
    icon: React.ReactNode;
}) {
    return (
        <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">

            <div className="flex items-start justify-between">

                <div>
                    <p className="text-xs text-text-muted">
                        {label}
                    </p>

                    <p className="mt-2 font-display text-xl font-semibold">
                        {value}
                    </p>
                </div>

                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-2 text-text-secondary">
                    {icon}
                </div>

            </div>

            <p className="mt-3 text-[10px] text-signal-green">
                {change} from previous
            </p>

        </div>
    );
}

function SignalRow({
    direction,
    state,
    time,
}: {
    direction: string;
    state: "GREEN" | "RED" | "YELLOW";
    time: string;
}) {
    const stateColor =
        state === "GREEN"
            ? "bg-signal-green"
            : state === "YELLOW"
            ? "bg-yellow-400"
            : "bg-red-400";

    return (
        <div className="flex items-center justify-between rounded-xl border border-border p-3">

            <div className="flex items-center gap-3">

                <span
                    className={`h-2.5 w-2.5 rounded-full ${stateColor}`}
                />

                <span className="text-xs font-medium">
                    {direction}
                </span>

            </div>

            <div className="flex items-center gap-3">

                <span className="text-[10px] text-text-muted">
                    {time}
                </span>

                <span className="text-[10px] font-semibold">
                    {state}
                </span>

            </div>

        </div>
    );
}

function TrafficLight({
    position,
    color,
}: {
    position: "top" | "right" | "bottom" | "left";
    color: "red" | "yellow" | "green";
}) {
    const positionClass = {
        top: "left-1/2 top-[calc(50%-115px)] -translate-x-1/2",
        right: "right-[calc(50%-115px)] top-1/2 -translate-y-1/2",
        bottom: "bottom-[calc(50%-115px)] left-1/2 -translate-x-1/2",
        left: "left-[calc(50%-115px)] top-1/2 -translate-y-1/2",
    }[position];

    const colorClass = {
        red: "bg-red-500",
        yellow: "bg-yellow-400",
        green: "bg-signal-green",
    }[color];

    return (
        <div
            className={`absolute z-20 ${positionClass} flex h-10 w-5 items-center justify-center rounded-full bg-black p-1`}
        >
            <span
                className={`h-3 w-3 rounded-full ${colorClass} shadow-sm`}
            />
        </div>
    );
}

function DynamicVehicle({
    left,
    top,
    angle,
    type,
}: {
    left: number;
    top: number;
    angle: number;
    type: string;
}) {
    // SUMO angle is clockwise from North (0 = UP)
    // CSS rotate is clockwise from element's natural orientation (which we can set as UP)
    const cssRotation = angle;
    
    // Customize color based on type
    let colorClass = "bg-blue-500";
    if (type === "motorcycle") colorClass = "bg-purple-500";
    if (type === "bus" || type === "truck") colorClass = "bg-orange-500";

    return (
        <div
            className={`absolute z-10 flex h-5 w-9 items-center justify-center rounded-md ${colorClass} shadow-sm transition-all duration-500 ease-linear`}
            style={{
                left: `${left}%`,
                top: `${top}%`,
                transform: `translate(-50%, -50%) rotate(${cssRotation}deg)`
            }}
        >
            <Car
                size={13}
                className="text-white"
                fill="currentColor"
                // Counter-rotate the icon so it faces the direction of travel
                style={{ transform: "rotate(-90deg)" }}
            />
        </div>
    );
}