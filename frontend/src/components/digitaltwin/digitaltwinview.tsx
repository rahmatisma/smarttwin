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
import { useScenario, ScenarioType } from "@/context/ScenarioContext";
import { fetchSignalStatus } from "@/lib/supabaseData";

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

    interface SignalStatusData {
        direction: string;
        state: "GREEN" | "RED" | "YELLOW";
        time: number;
    }
    const [signalStatuses, setSignalStatuses] = useState<SignalStatusData[]>([
        { direction: "North", state: "GREEN", time: 32 },
        { direction: "East", state: "RED", time: 18 },
        { direction: "South", state: "GREEN", time: 32 },
        { direction: "West", state: "RED", time: 18 },
    ]);
    const [isInitialLoading, setIsInitialLoading] = useState(true);
    const [isSimStateLoaded, setIsSimStateLoaded] = useState(false);
    
    // Auto-calibration bounds
    const boundsRef = useRef({ minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity });

    const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

    interface SignalData {
        trafficLightId: string;
        state: "GREEN" | "RED" | "YELLOW";
        phase: number;
        remainingSeconds: number;
        rawState: string;
    }

    const [simulationTime, setSimulationTime] = useState(0);
    const [signals, setSignals] = useState<SignalData[]>([]);

    useEffect(() => {
        const interval = setInterval(async () => {
            try {
                const res = await fetch(`${API_BASE_URL}/api/v1/simulation/state`);
                if (!res.ok) return;
                const data = await res.json();
                
                setIsSimStateLoaded(true);

                if (data.running) {
                    if (data.paused) {
                        setStatus("paused");
                    } else {
                        setStatus("running");
                    }
                } else {
                    setStatus("idle");
                }

                if (!data.running) {
                    // SSOT: Use Supabase when simulation is idle
                    try {
                        const dbSignal = await fetchSignalStatus("simpang4-pingit");
                        if (dbSignal) {
                            const phase = dbSignal.currentPhase.toLowerCase();
                            const isNS = phase.includes("ns") || phase.includes("north") || phase.includes("south");
                            const isEW = phase.includes("ew") || phase.includes("east") || phase.includes("west");
                            const isAmber = phase.includes("amber") || phase.includes("yellow");
                            const activeColor = isAmber ? "YELLOW" : "GREEN";

                            setSignalStatuses([
                                { direction: "North", state: isNS ? activeColor : "RED", time: dbSignal.remainingSeconds },
                                { direction: "East",  state: isEW ? activeColor : "RED", time: dbSignal.remainingSeconds },
                                { direction: "South", state: isNS ? activeColor : "RED", time: dbSignal.remainingSeconds },
                                { direction: "West",  state: isEW ? activeColor : "RED", time: dbSignal.remainingSeconds }
                            ]);
                            setIsInitialLoading(false);
                        }
                    } catch (dbErr) {
                        console.error("Failed to fetch Supabase signal:", dbErr);
                    }
                    return;
                }

                if (data.vehicles) {
                    setVehicles(data.vehicles);
                }
                if (data.signals && data.signals.length > 0) {
                    setSignals(data.signals);

                    // Parse rawState for the 4 directions (assuming simpang4-pingit layout)
                    const rawState = data.signals[0].rawState;
                    if (rawState && rawState.length === 20) {
                        const remaining = Math.floor(data.signals[0].remainingSeconds);
                        const isGreen = (slice: string) => slice.includes('G') || slice.includes('g');
                        const isYellow = (slice: string) => slice.includes('y') || slice.includes('Y');

                        const getState = (slice: string) => {
                            if (isGreen(slice)) return "GREEN";
                            if (isYellow(slice)) return "YELLOW";
                            return "RED";
                        };

                        setSignalStatuses([
                            { direction: "North", state: getState(rawState.slice(10, 15)), time: remaining },
                            { direction: "East",  state: getState(rawState.slice(5, 10)),  time: remaining },
                            { direction: "South", state: getState(rawState.slice(0, 5)),   time: remaining },
                            { direction: "West",  state: getState(rawState.slice(15, 20)), time: remaining }
                        ]);
                        setIsInitialLoading(false);
                    }
                }
                if (data.simulationTimeSeconds !== undefined) {
                    setSimulationTime(data.simulationTimeSeconds);
                }
                
                // Update bounds
                let { minX, maxX, minY, maxY } = boundsRef.current;
                let changed = false;
                (data.vehicles || []).forEach((v: VehicleData) => {
                    if (v.x < minX) { minX = v.x; changed = true; }
                    if (v.x > maxX) { maxX = v.x; changed = true; }
                    if (v.y < minY) { minY = v.y; changed = true; }
                    if (v.y > maxY) { maxY = v.y; changed = true; }
                });
                
                // Add some padding to bounds so cars don't hit the absolute edge
                if (changed && minX !== Infinity) {
                    boundsRef.current = { minX, maxX, minY, maxY };
                }

            } catch (err) {
                console.error("Failed to fetch positions:", err);
            }
        }, 500);

        return () => clearInterval(interval);
    }, [API_BASE_URL]);

    async function handleStartSimulation() {
        setLoading(true);
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/simulation/run`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    intersectionId: "simpang4-pingit",
                    durationSeconds: 60,
                    gui: true,
                    guiDelayMs: 100,
                    seed: 42,
                    scenario: scenario
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

    async function handleReset() {
        setLoading(true);
        try {
            await fetch(`${API_BASE_URL}/api/v1/simulation/stop`, {
                method: "POST"
            });
            setStatus("idle");
            setVehicles([]);
            setSignals([]);
            setSimulationTime(0);
            setScenario("Baseline");
        } catch (error) {
            console.error("Failed to stop simulation", error);
        } finally {
            setLoading(false);
        }
    }

    async function handlePause() {
        try {
            await fetch(`${API_BASE_URL}/api/v1/simulation/pause`, {
                method: "POST"
            });
            setStatus("paused");
        } catch (error) {
            console.error("Failed to pause simulation", error);
        }
    }

    async function handleResume() {
        try {
            await fetch(`${API_BASE_URL}/api/v1/simulation/resume`, {
                method: "POST"
            });
            setStatus("running");
        } catch (error) {
            console.error("Failed to resume simulation", error);
        }
    }

    const SCENARIO_CONFIG: Record<ScenarioType, { level: string; flow: string; queue: string; policy: string; description: string }> = {
        "Traffic Realtime": {
            level: "Live",
            flow: "Live Data",
            queue: "Live Data",
            policy: "Actuated / RuleBasedEngine",
            description: "Data sinkron dengan lalu lintas aktual di lapangan"
        },
        "Baseline": {
            level: "Normal",
            flow: "Measured",
            queue: "Real-time",
            policy: "RuleBasedEngine",
            description: "Original RuleBasedEngine duration"
        },
        "Aggressive": {
            level: "High",
            flow: "Heavy",
            queue: "Increased",
            policy: "Aggressive Clearing",
            description: "Baseline +20%, max 60s"
        },
        "Balanced": {
            level: "Low",
            flow: "Smooth",
            queue: "Minimal",
            policy: "Energy Saving",
            description: "Between baseline and 15s"
        }
    };

    const [speed, setSpeed] = useState("1x");

    const { scenario, setScenario } = useScenario();

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

                            {/* SUMO-GUI Live Stream */}
                            {status === "running" ? (
                                <img
                                    src={`${API_BASE_URL}/api/v1/simulation/stream?t=${Date.now()}`}
                                    alt="Live SUMO Simulation Stream"
                                    className="absolute inset-0 h-full w-full object-contain"
                                />
                            ) : (
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <p className="text-sm text-text-muted">Simulation Not Running</p>
                                </div>
                            )}

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
                                    {Math.floor(simulationTime / 60).toString().padStart(2, '0')}:{(Math.floor(simulationTime) % 60).toString().padStart(2, '0')}
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

                            {!isSimStateLoaded ? (
                                <div className="py-6 text-center">
                                    <div className="mx-auto h-5 w-5 animate-spin rounded-full border-2 border-text-muted border-t-transparent"></div>
                                    <p className="mt-3 text-xs text-text-muted">Memuat status simulasi...</p>
                                </div>
                            ) : status === "idle" ? (
                                <div className="py-6 text-center">
                                    <p className="text-xs font-medium text-text">Stopped / Ready</p>
                                    <p className="mt-1 text-[10px] text-text-muted">Mulai simulasi untuk melihat metrik.</p>
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    <MetricRow
                                        label="Current State"
                                        value={status === "paused" ? "Paused" : "Running"}
                                        icon={<Activity size={15} />}
                                    />
                                    <MetricRow
                                        label="Simulation Time"
                                        value={`${Math.floor(simulationTime / 60).toString().padStart(2, '0')}:${(Math.floor(simulationTime) % 60).toString().padStart(2, '0')}`}
                                        icon={<Clock3 size={15} />}
                                    />
                                    <MetricRow
                                        label="Current Vehicles"
                                        value={vehicles.length.toString()}
                                        icon={<Car size={15} />}
                                    />
                                </div>
                            )}

                        </div>

                        {/* Current phase */}

                        {signals.length > 0 && (
                            <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
                                <div className="mb-4 flex items-center justify-between">
                                    <div>
                                        <h2 className="text-sm font-semibold">
                                            Phase {signals[0].phase}
                                        </h2>
                                        <p className="mt-1 text-xs text-text-muted">
                                            Traffic Light: {signals[0].trafficLightId}
                                        </p>
                                    </div>
                                    <span className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-medium ${signals[0].state === 'GREEN' ? 'bg-signal-green/10 text-signal-green' : 'bg-signal-red/10 text-signal-red'}`}>
                                        <Circle
                                            size={7}
                                            fill="currentColor"
                                        />
                                        {signals[0].state}
                                    </span>
                                </div>
                                <div className="h-2 overflow-hidden rounded-full bg-surface-2">
                                    <div className={`h-full rounded-full transition-all duration-500 ${signals[0].state === 'GREEN' ? 'bg-signal-green' : 'bg-signal-red'}`} style={{width: `${Math.min(100, Math.max(0, (signals[0].remainingSeconds / 60) * 100))}%`}} />
                                </div>
                                <div className="mt-2 flex justify-between text-[10px] text-text-muted">
                                    <span className="font-mono">{Math.floor(signals[0].remainingSeconds)}s</span>
                                    <span>Remaining</span>
                                </div>
                            </div>
                        )}

                    </div>

                </div>

                {/* ================================================= */}
                {/* VEHICLE INFORMATION / METRICS */}
                {/* ================================================= */}

                <div className="mt-5 grid grid-cols-2 gap-4 lg:grid-cols-4">

                    {!isSimStateLoaded ? (
                        <div className="col-span-full rounded-2xl border border-border bg-surface p-8 text-center shadow-sm">
                            <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-text-muted border-t-transparent"></div>
                            <p className="mt-3 text-xs text-text-muted">Memuat informasi kendaraan...</p>
                        </div>
                    ) : (
                        <>
                            <StatCard
                                label="Current Vehicles"
                                value={status === "idle" ? "0" : vehicles.length.toString()}
                                change={status === "idle" ? "" : "Live snapshot"}
                                icon={<Car size={18} />}
                            />

                            <StatCard
                                label="Average Speed"
                                value="-"
                                change="Data belum tersedia"
                                icon={<Gauge size={18} />}
                            />

                            <StatCard
                                label="Queue Length"
                                value="-"
                                change="Data belum tersedia"
                                icon={<List size={18} />}
                            />

                            <StatCard
                                label="Traffic Flow"
                                value="-"
                                change="Data belum tersedia"
                                icon={<Zap size={18} />}
                            />
                        </>
                    )}

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
                                <label className="mb-2 flex items-center justify-between text-xs font-medium text-text-secondary">
                                    <span>Traffic Scenario</span>
                                    {scenario !== "Traffic Realtime" && (
                                        <span className="text-[10px] text-accent-blue">Simulated</span>
                                    )}
                                </label>

                                <div className="relative">

                                    <select
                                        value={scenario}
                                        onChange={(e) =>
                                            setScenario(
                                                e.target.value as ScenarioType
                                            )
                                        }
                                        className="w-full appearance-none rounded-xl border border-border bg-surface px-3 py-2.5 pr-9 text-sm outline-none transition focus:border-text-muted"
                                    >
                                        {Object.keys(SCENARIO_CONFIG).map((key) => (
                                            <option key={key} value={key}>
                                                {key}
                                            </option>
                                        ))}
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
                                    onClick={handlePause}
                                    className="flex items-center gap-2 rounded-xl bg-accent px-5 py-2.5 text-xs font-medium text-bg transition hover:opacity-90"
                                >
                                    <Pause size={15} />
                                    Pause Simulation
                                </button>
                            ) : status === "paused" ? (
                                <button
                                    type="button"
                                    onClick={handleResume}
                                    className="flex items-center gap-2 rounded-xl bg-accent px-5 py-2.5 text-xs font-medium text-bg transition hover:opacity-90"
                                >
                                    <Play size={15} />
                                    Resume Simulation
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
                                onClick={handleReset}
                                disabled={loading}
                                className={`flex items-center gap-2 rounded-xl border border-border px-5 py-2.5 text-xs font-medium text-text-secondary transition hover:bg-surface-2 ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
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

                        <div className="space-y-2">
                            {signalStatuses.map((s, i) => (
                                isInitialLoading ? (
                                    <div key={i} className="flex items-center justify-between rounded-xl border border-border p-3">
                                        <div className="flex items-center gap-3">
                                            <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-surface-2" />
                                            <span className="text-xs font-medium text-text-muted">
                                                {s.direction}
                                            </span>
                                        </div>
                                        <div className="flex items-center gap-3">
                                            <span className="h-2.5 w-6 animate-pulse rounded bg-surface-2" />
                                            <span className="h-2.5 w-10 animate-pulse rounded bg-surface-2" />
                                        </div>
                                    </div>
                                ) : (
                                    <SignalRow
                                        key={i}
                                        direction={s.direction}
                                        state={s.state}
                                        time={status === "running" ? `${s.time}s` : "--"}
                                    />
                                )
                            ))}
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

            {change && (
                <p className={`mt-3 text-[10px] ${change.includes("Data belum tersedia") ? "text-text-muted" : "text-signal-green"}`}>
                    {change}
                </p>
            )}

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
