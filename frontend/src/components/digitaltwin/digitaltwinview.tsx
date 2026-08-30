"use client";

import { useState, useEffect, useRef } from "react";
import {
    Play,
    Pause,
    RotateCcw,
    Zap,
    Car,
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
import { fetchSignalStatus, fetchRecommendation, fetchDigitalTwinScenarios, DigitalTwinScenarioResponse } from "@/lib/supabaseData";
import type { SignalStatus, Recommendation } from "@/types/traffic";
import RecommendationPanel from "@/components/RecommendationPanel";
import SignalStatusPanel from "@/components/SignalStatusPanel";

type SimulationStatus = "idle" | "running" | "paused";

interface VehicleData {
    id: string;
    x: number;
    y: number;
    angle: number;
    type: string;
}

export default function DigitalTwinView() {
    const { scenario, setScenario } = useScenario();
    const [status, setStatus] =
        useState<SimulationStatus>("idle");
    const [loading, setLoading] = useState(false);
    const [vehicles, setVehicles] = useState<VehicleData[]>([]);


    const [isInitialLoading, setIsInitialLoading] = useState(true);
    const [isSimStateLoaded, setIsSimStateLoaded] = useState(false);

    const [dbSignalRaw, setDbSignalRaw] = useState<SignalStatus | null>(null);
    const [dbRecRaw, setDbRecRaw] = useState<Recommendation | null>(null);
    const [scenarioData, setScenarioData] = useState<DigitalTwinScenarioResponse | null>(null);
    const [recommendationLoading, setRecommendationLoading] = useState(false);
    const [runningScenario, setRunningScenario] = useState<ScenarioType | null>("Traffic Realtime");

    const [simSharedPhase, setSimSharedPhase] = useState<string>("north");
    const [simSharedState, setSimSharedState] = useState<"GREEN" | "YELLOW" | "RED">("RED");
    const [simSharedRemaining, setSimSharedRemaining] = useState<number>(0);

    useEffect(() => {
        let cancelled = false;
        void fetchDigitalTwinScenarios()
            .then(res => {
                if (!cancelled && res) setScenarioData(res);
            })
            .finally(() => {
                if (!cancelled) setRecommendationLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [scenario]);

    useEffect(() => {
        let isSubscribed = true;
        const poll = async () => {
            try {
                const [sig, rec] = await Promise.all([
                    fetchSignalStatus("simpang4-pingit"),
                    fetchRecommendation("simpang4-pingit")
                ]);
                if (isSubscribed) {
                    if (sig) setDbSignalRaw(sig);
                    if (rec) setDbRecRaw(rec);
                }
            } catch (err) {
                console.error("Failed to fetch recommendation/signal data for Digital Twin", err);
            }
        };

        poll();
        const intervalId = setInterval(poll, 1000);
        return () => {
            isSubscribed = false;
            clearInterval(intervalId);
        };
    }, []);
    
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
        let cancelled = false;
        const pollSimulation = async () => {
            try {
                const res = await fetch(`${API_BASE_URL}/api/v1/simulation/state`);
                if (!res.ok || cancelled) return;
                const data = await res.json();
                if (cancelled) return;
                
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

                        const getState = (slice: string): "GREEN" | "YELLOW" | "RED" => {
                            if (isGreen(slice)) return "GREEN";
                            if (isYellow(slice)) return "YELLOW";
                            return "RED";
                        };

                        const slices = [
                            // Urutan link TLS SUMO: south, east, north, west.
                            { approach: "south", state: getState(rawState.substring(0, 5)) },
                            { approach: "east", state: getState(rawState.substring(5, 10)) },
                            { approach: "north", state: getState(rawState.substring(10, 15)) },
                            { approach: "west", state: getState(rawState.substring(15, 20)) }
                        ];
                        const active = slices.find(s => s.state !== "RED") || slices[0];
                        setSimSharedPhase(active.approach);
                        setSimSharedState(active.state);
                        setSimSharedRemaining(remaining);
                        
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
        };

        // Reattach segera ke sesi yang dibuat dashboard; jangan tampil idle/0
        // selama 500 ms pertama setiap pindah halaman.
        void pollSimulation();
        const interval = setInterval(pollSimulation, 500);

        return () => {
            cancelled = true;
            clearInterval(interval);
        };
    }, [API_BASE_URL]);

    async function handleStartSimulation(selectedScenario: ScenarioType = scenario) {
        setLoading(true);
        setRecommendationLoading(selectedScenario !== "Traffic Realtime");
        try {
            const scenarioKey = selectedScenario.toLowerCase();
            const selectedCandidate = selectedScenario === "Traffic Realtime"
                ? null
                : scenarioData?.candidates.find(
                    candidate => candidate.candidateId === scenarioKey
                ) ?? null;
            const selectedCyclePlan = selectedCandidate
                ? {
                    phases: selectedCandidate.phases,
                    candidateId: selectedCandidate.candidateId,
                    source: "scenario-generator",
                    totalCycleSeconds: selectedCandidate.totalCycleSeconds,
                }
                : selectedScenario === "Traffic Realtime"
                    ? dbRecRaw?.cyclePlan ?? null
                    : null;

            const response = await fetch(`${API_BASE_URL}/api/v1/simulation/run`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    intersectionId: "simpang4-pingit",
                    durationSeconds: 60,
                    gui: true,
                    guiDelayMs: 100,
                    seed: 42,
                    scenario: selectedScenario,
                    cyclePlan: selectedCyclePlan,
                }),
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || "Gagal memulai simulasi");
            }

            // Simulasi berhasil berjalan
            setStatus((currentStatus) => currentStatus === "paused" ? "paused" : "running");
            setRunningScenario(selectedScenario);
            
            // Hasil apply SUMO tidak perlu menunggu refresh kartu rekomendasi.
            // Refresh berjalan di background dan request-nya memiliki timeout.
            setRecommendationLoading(false);
            void fetchDigitalTwinScenarios().then(updatedScenarioData => {
                if (updatedScenarioData) setScenarioData(updatedScenarioData);
            });
        } catch (error) {
            console.error(error);
            alert(error instanceof Error ? error.message : "Terjadi kesalahan saat memulai simulasi");
        } finally {
            setLoading(false);
            setRecommendationLoading(false);
        }
    }

    async function handleScenarioChange(newScenario: ScenarioType) {
        setScenario(newScenario);

        if (status === "running" || status === "paused") {
            await handleStartSimulation(newScenario);
            return;
        }

        setRecommendationLoading(false);
        if (newScenario === "Traffic Realtime") {
            setRunningScenario(null);
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
            setRunningScenario(null);
            setRecommendationLoading(true);
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
            description: "Baseline +1s pada lengan tersibuk, max 60s"
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

    const isSimulating = status === "running" || status === "paused";
    const useRealtimeData = scenario === "Traffic Realtime";
    
    let mappedRec = dbRecRaw;
    
    if (!useRealtimeData && scenarioData) {
        const scenarioKey = scenario.toLowerCase() as "baseline" | "aggressive" | "balanced";
        const candidate = scenarioData.candidates.find(c => c.candidateId === scenarioKey);
        
        if (candidate) {
            mappedRec = {
                intersectionId: "simpang4-pingit",
                timestamp: scenarioData.updatedAt || new Date().toISOString(),
                recommendedPhase: candidate.phases[0]?.approach || "north",
                recommendedGreenSeconds: candidate.phases[0]?.greenSeconds || 0,
                currentGreenSeconds: 0,
                expectedDelayReductionPercent: 0,
                confidence: 1,
                reason: "Scenario Generated",
                metrics: {
                    queueLength: candidate.queueLengthVeh,
                    vehicleCount: candidate.throughputVeh,
                    averageSpeedKmh: 0,
                },
                source: "scenario-generator",
                cyclePlan: {
                    phases: candidate.phases.map(p => ({
                        approach: p.approach,
                        greenSeconds: p.greenSeconds,
                        demandScore: p.demandScore,
                        yellowSeconds: p.yellowSeconds,
                        redSeconds: p.redSeconds
                    })),
                    cycleLengthSeconds: candidate.cycleLengthSeconds,
                    currentPhase: candidate.phases[0]?.approach || "north",
                    source: "scenario-generator",
                    totalCycleSeconds: candidate.totalCycleSeconds
                },
                avgDelaySeconds: candidate.avgDelaySeconds,
                avgQueueLengthM: candidate.avgQueueLengthM,
                los: candidate.los,
                candidateId: candidate.candidateId,
            } as Recommendation;
        }
    }
    
    let mappedPhase = dbSignalRaw?.currentPhase || "north";
    let mappedState: "GREEN" | "YELLOW" | "RED" = dbSignalRaw && dbSignalRaw.remainingSeconds <= 4 ? "YELLOW" : "GREEN";
    let mappedRemaining = dbSignalRaw?.remainingSeconds || 0;
    
    if (isSimulating) {
        mappedPhase = simSharedPhase;
        mappedState = simSharedState;
        mappedRemaining = simSharedRemaining;
    } else if (!useRealtimeData && mappedRec?.cyclePlan) {
        mappedPhase = mappedRec.cyclePlan.phases[0].approach;
        mappedState = "GREEN";
        mappedRemaining = mappedRec.cyclePlan.phases[0].greenSeconds;
    }

    const recommendationSignal: SignalStatus = dbSignalRaw ?? {
        intersectionId: "simpang4-pingit",
        timestamp: new Date().toISOString(),
        currentPhase: mappedPhase,
        phaseName: `Fase ${mappedPhase}`,
        remainingSeconds: mappedRemaining,
        cycleTimeSeconds: mappedRec?.cyclePlan?.totalCycleSeconds ?? 0,
        source: "simulation",
    };

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
                                    src={`${API_BASE_URL}/api/v1/simulation/stream`}
                                    alt="Live SUMO Simulation Stream"
                                    className="absolute inset-0 h-full w-full object-cover object-center"
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

                <div className="mt-5 grid gap-5 lg:grid-cols-3">

                    {/* =============================== */}
                    {/* SIMULATION CONTROLS */}
                    {/* =============================== */}

                    <div className="lg:col-span-1 flex flex-col rounded-2xl border border-border bg-surface p-4 shadow-sm">

                        <div className="mb-3 flex items-center gap-2.5">

                            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-surface-2">
                                <Settings2 size={14} />
                            </div>

                            <div>
                                <h2 className="text-sm font-semibold">
                                    Simulation Controls
                                </h2>
                            </div>

                        </div>

                        <div>

                            {/* Scenario */}

                            <div>
                                <label className="mb-1.5 flex items-center justify-between text-[11px] font-medium text-text-secondary">
                                    <span>Traffic Scenario</span>
                                    {scenario !== "Traffic Realtime" && (
                                        <span className="text-[9px] text-accent-blue">Simulated</span>
                                    )}
                                </label>

                                <div className="relative">

                                    <select
                                        value={scenario}
                                        disabled={loading}
                                        onChange={(e) => void handleScenarioChange(
                                            e.target.value as ScenarioType
                                        )}
                                        className="w-full appearance-none rounded-lg border border-border bg-surface px-2.5 py-1.5 pr-8 text-xs outline-none transition focus:border-text-muted"
                                    >
                                        {Object.keys(SCENARIO_CONFIG).map((key) => (
                                            <option key={key} value={key}>
                                                {key}
                                            </option>
                                        ))}
                                    </select>

                                    <ChevronDown
                                        size={14}
                                        className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted"
                                    />

                                </div>

                            </div>

                        </div>

                        {/* Buttons */}

                        <div className="mt-auto flex gap-2 pt-2">

                            {status === "running" ? (
                                <button
                                    type="button"
                                    onClick={handlePause}
                                    className="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-1.5 text-[11px] font-medium text-bg transition hover:opacity-90"
                                >
                                    <Pause size={13} />
                                    Pause Simulation
                                </button>
                            ) : status === "paused" ? (
                                <button
                                    type="button"
                                    onClick={handleResume}
                                    className="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-1.5 text-[11px] font-medium text-bg transition hover:opacity-90"
                                >
                                    <Play size={13} />
                                    Resume Simulation
                                </button>
                            ) : (
                                <button
                                    type="button"
                                    onClick={() => void handleStartSimulation()}
                                    disabled={loading}
                                    className="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-1.5 text-[11px] font-medium text-bg transition hover:opacity-90 disabled:opacity-50"
                                >
                                    <Play size={13} />
                                    {loading ? "Starting..." : "Start Simulation"}
                                </button>
                            )}

                        </div>

                    </div>

                    {/* =============================== */}
                    {/* RECOMMENDATION PANEL */}
                    {/* =============================== */}

                    <div className="lg:col-span-2 flex h-full flex-col">
                        {recommendationLoading ? (
                            <div className="flex h-full flex-col items-center justify-center rounded-2xl border border-border bg-surface p-5 text-center shadow-sm">
                                <div className="mb-4 h-6 w-6 animate-spin rounded-full border-2 border-accent-blue border-t-transparent"></div>
                                <h3 className="text-sm font-semibold text-text-primary">Loading...</h3>
                                <p className="mt-1 text-[11px] text-text-muted">Fetching simulation recommendation</p>
                            </div>
                        ) : mappedRec ? (
                            <RecommendationPanel
                                recommendation={mappedRec}
                                signal={recommendationSignal}
                                sharedVisualPhase={mappedPhase}
                                sharedVisualPhaseState={mappedState === "RED" ? "GREEN" : mappedState}
                                sharedVisualRemaining={mappedRemaining}
                                layout="cross"
                            />
                        ) : (
                            <div className="flex h-full flex-col rounded-2xl border border-border bg-surface p-5 text-center shadow-sm">
                                <p className="mt-auto text-sm font-medium text-text">Rekomendasi belum tersedia</p>
                                <p className="mb-auto mt-2 text-xs text-text-muted">
                                    Data scenario belum tersedia dari backend. Coba jalankan simulasi kembali.
                                </p>
                            </div>
                        )}
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

