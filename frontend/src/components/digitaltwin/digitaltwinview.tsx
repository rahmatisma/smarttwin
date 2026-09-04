"use client";

import { useState, useEffect, useRef } from "react";
import {
    Play,
    Pause,
    Zap,
    Car,
    List,
    Clock3,
    Activity,
    Map,
    Settings2,
    ChevronDown,
    Circle,
    TrafficCone,
    Maximize2,
    Minimize2,
} from "lucide-react";
import {
    ResponsiveContainer,
    LineChart,
    Line,
    XAxis,
    YAxis,
    Tooltip,
    CartesianGrid,
} from "recharts";

import Sidebar from "@/components/Sidebar";
import { useScenario, ScenarioType } from "@/context/ScenarioContext";
import { fetchSignalStatus } from "@/lib/supabaseData";
import SignalStatusPanel from "@/components/SignalStatusPanel";

// "Traffic Realtime" BUKAN instance terpisah -- itu adalah instance SUMO
// yang SAMA persis dengan dashboard (context "dashboard"), supaya SUMO
// tidak pernah terbuka dobel untuk hal yang sebenarnya sama. Skenario lain
// (Baseline/Aggressive/Balanced) adalah sandbox terpisah (context
// "digitaltwin") yang tidak pernah menyentuh simulasi dashboard.
function contextForScenario(target: ScenarioType): "dashboard" | "digitaltwin" {
    return target === "Traffic Realtime" ? "dashboard" : "digitaltwin";
}

type SimulationStatus = "idle" | "running" | "paused";

interface VehicleData {
    id: string;
    x: number;
    y: number;
    angle: number;
    type: string;
}

interface CyclePhase {
    approach: string;
    greenSeconds: number;
    yellowSeconds: number;
    redSeconds?: number;
}

interface CyclePlanData {
    candidateId?: string;
    totalCycleSeconds?: number;
    phases: CyclePhase[];
}

interface SimHistoryPoint {
    t: number;
    delay: number;
    queue: number;
    throughput: number;
}

export default function DigitalTwinView() {
    const simulationViewRef = useRef<HTMLDivElement>(null);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const fullscreenViewWasRequestedRef = useRef(false);

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
    const [status, setStatus] =
        useState<SimulationStatus>("idle");
    const [loading, setLoading] = useState(false);
    const [vehicles, setVehicles] = useState<VehicleData[]>([]);
    // vehicles.length = SEMUA kendaraan di network (633x1020m). Video cuma
    // menampilkan crop kamera (~140x79m) -- jadi ini hitungan yang benar-
    // benar cocok dengan yang terlihat di layar.
    const [visibleVehicleCount, setVisibleVehicleCount] = useState(0);
    // Target kendaraan hasil deteksi CV (snapshot demand terakhir) -- angka
    // yang SEHARUSNYA ada di jaringan. Bandingkan dengan vehicles.length.
    const [detectedVehicles, setDetectedVehicles] = useState(0);
    // Berapa kendaraan GAGAL disisipkan TraCI pada sinkronisasi demand
    // terakhir -- kalau > 0, itu penjelasan konkret kenapa "Total jaringan"
    // bisa lebih kecil dari target, bukan cuma dugaan drift alami.
    const [lastSyncFailedInsertions, setLastSyncFailedInsertions] = useState(0);


    const [isSimStateLoaded, setIsSimStateLoaded] = useState(false);

    const [recommendationLoading, setRecommendationLoading] = useState(false);
    const [runningScenario, setRunningScenario] = useState<ScenarioType | null>("Traffic Realtime");

    const { scenario, setScenario } = useScenario();

    const [simSharedPhase, setSimSharedPhase] = useState<string>("north");
    const [simSharedState, setSimSharedState] = useState<"GREEN" | "YELLOW" | "RED">("RED");
    const [simSharedRemaining, setSimSharedRemaining] = useState<number>(0);
    
    // Auto-calibration bounds
    const boundsRef = useRef({ minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity });

    const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

    useEffect(() => {
        if (status === "idle") return;
        if (!isFullscreen && !fullscreenViewWasRequestedRef.current) return;

        const context = contextForScenario(scenario);
        fullscreenViewWasRequestedRef.current = isFullscreen;
        void fetch(
            `${API_BASE_URL}/api/v1/simulation/view?context=${context}&mode=${isFullscreen ? "wide" : "compact"}`,
            { method: "POST" }
        );

        return () => {
            if (isFullscreen) {
                void fetch(
                    `${API_BASE_URL}/api/v1/simulation/view?context=${context}&mode=compact`,
                    { method: "POST" }
                );
            }
        };
    }, [API_BASE_URL, isFullscreen, scenario, status]);

    interface SignalData {
        trafficLightId: string;
        state: "GREEN" | "RED" | "YELLOW";
        phase: number;
        remainingSeconds: number;
        rawState: string;
    }

    const [simulationTime, setSimulationTime] = useState(0);
    const [signals, setSignals] = useState<SignalData[]>([]);
    const [queueLengthVeh, setQueueLengthVeh] = useState(0);
    const [queueBusiestApproach, setQueueBusiestApproach] = useState<string | null>(null);
    const [throughputVehPerMin, setThroughputVehPerMin] = useState(0);

    // Metrik simpang keseluruhan untuk panel "Hasil Simulasi" -- dihitung
    // LANGSUNG dari SUMO yang sedang jalan di halaman ini (bukan dari
    // liveScenarioCache produksi), jadi beda skenario benar-benar
    // menghasilkan angka berbeda, bukan angka cache yang sama untuk semua.
    const [avgDelaySeconds, setAvgDelaySeconds] = useState(0);
    const [avgQueueLengthVeh, setAvgQueueLengthVeh] = useState(0);
    const [avgQueueLengthM, setAvgQueueLengthM] = useState(0);
    const [los, setLos] = useState<string | null>(null);

    // Durasi lampu per lengan untuk skenario yang SEDANG diterapkan --
    // inilah satu-satunya hal yang benar-benar beda antar skenario, jadi
    // ditampilkan eksplisit sebagai angka, bukan cuma tersirat dari video.
    const [cyclePlan, setCyclePlan] = useState<CyclePlanData | null>(null);

    // Riwayat singkat buat 3 grafik tren (Delay/Queue/Throughput). Direset
    // tiap kali skenario baru diterapkan atau simulasi dihentikan -- grafik
    // ini menunjukkan "bagaimana skenario yang SEDANG jalan berkembang",
    // bukan log seumur hidup yang bakal mencampur beberapa skenario.
    const [simHistory, setSimHistory] = useState<SimHistoryPoint[]>([]);
    const SIM_HISTORY_MAX_POINTS = 120;

    const APPROACH_SHORT_LABEL: Record<string, string> = {
        north: "Utara",
        south: "Selatan",
        east: "Timur",
        west: "Barat",
    };

    useEffect(() => {
        const context = contextForScenario(scenario);
        const interval = setInterval(async () => {
            try {
                const res = await fetch(`${API_BASE_URL}/api/v1/simulation/state?context=${context}`);
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
                        await fetchSignalStatus("simpang4-pingit");
                    } catch (dbErr) {
                        console.error("Failed to fetch Supabase signal:", dbErr);
                    }
                    return;
                }

                if (data.vehicles) {
                    setVehicles(data.vehicles);
                }
                if (data.visibleVehicleCount !== undefined) {
                    setVisibleVehicleCount(data.visibleVehicleCount);
                }
                if (data.detectedVehicles !== undefined) {
                    setDetectedVehicles(data.detectedVehicles);
                }
                if (data.lastSyncFailedInsertions !== undefined) {
                    setLastSyncFailedInsertions(data.lastSyncFailedInsertions);
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
                        
                    }
                }
                if (data.simulationTimeSeconds !== undefined) {
                    setSimulationTime(data.simulationTimeSeconds);
                }
                if (data.queueLengthVeh !== undefined) {
                    setQueueLengthVeh(data.queueLengthVeh);
                }
                if (data.queueBusiestApproach !== undefined) {
                    setQueueBusiestApproach(data.queueBusiestApproach);
                }
                if (data.throughputVehPerMin !== undefined) {
                    setThroughputVehPerMin(data.throughputVehPerMin);
                }
                if (data.avgDelaySeconds !== undefined) {
                    setAvgDelaySeconds(data.avgDelaySeconds);
                }
                if (data.avgQueueLengthVeh !== undefined) {
                    setAvgQueueLengthVeh(data.avgQueueLengthVeh);
                }
                if (data.avgQueueLengthM !== undefined) {
                    setAvgQueueLengthM(data.avgQueueLengthM);
                }
                if (data.los !== undefined) {
                    setLos(data.los);
                }
                if (data.cyclePlan) {
                    setCyclePlan(data.cyclePlan);
                }
                if (
                    data.running &&
                    data.simulationTimeSeconds !== undefined &&
                    data.avgDelaySeconds !== undefined
                ) {
                    setSimHistory((prev) => {
                        // Polling tiap 500ms, tapi step SUMO bisa 1 detik --
                        // jangan tambah titik kalau simulationTimeSeconds
                        // belum maju sama sekali, nanti kapasitas buffer
                        // kepakai duplikat dan jendela waktu efektifnya jadi
                        // lebih pendek dari yang terlihat.
                        if (prev.length > 0 && prev[prev.length - 1].t === data.simulationTimeSeconds) {
                            return prev;
                        }
                        const next = [
                            ...prev,
                            {
                                t: data.simulationTimeSeconds,
                                delay: data.avgDelaySeconds,
                                queue: data.avgQueueLengthM ?? 0,
                                throughput: data.throughputVehPerMin ?? 0,
                            },
                        ];
                        return next.length > SIM_HISTORY_MAX_POINTS
                            ? next.slice(-SIM_HISTORY_MAX_POINTS)
                            : next;
                    });
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
    }, [API_BASE_URL, scenario]);

    async function handleStartSimulation(targetScenario?: ScenarioType) {
        // Parameter opsional -- WAJIB dipakai (bukan baca `scenario` dari
        // closure) saat dipanggil tepat setelah setScenario(), karena
        // setState di React async: closure di sini masih lihat nilai lama.
        const effectiveScenario = targetScenario ?? scenario;
        const context = contextForScenario(effectiveScenario);

        setLoading(true);
        try {
            const abortController = new AbortController();
            const timeout = window.setTimeout(() => abortController.abort(), 20_000);
            const response = await fetch(`${API_BASE_URL}/api/v1/simulation/run`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                signal: abortController.signal,
                body: JSON.stringify({
                    context,
                    intersectionId: "simpang4-pingit",
                    durationSeconds: 60,
                    gui: true,
                    guiDelayMs: 100,
                    seed: 42,
                    scenario: effectiveScenario
                }),
            }).finally(() => window.clearTimeout(timeout));

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || "Gagal memulai simulasi");
            }

            // Simulasi berhasil berjalan -- riwayat grafik direset supaya
            // tren yang tampil murni punya skenario ini, tidak mencampur
            // dengan sisa titik dari skenario sebelumnya.
            setStatus("running");
            setRunningScenario(effectiveScenario);
            setSimHistory([]);
            setRecommendationLoading(false);
        } catch (error) {
            console.error(error);
            const message = error instanceof DOMException && error.name === "AbortError"
                ? "SUMO tidak merespons dalam 20 detik. Periksa backend/SUMO."
                : error instanceof Error
                    ? error.message
                    : "Terjadi kesalahan saat memulai simulasi";
            alert(message);
        } finally {
            setLoading(false);
        }
    }

    async function handleReset() {
        setLoading(true);
        try {
            await fetch(`${API_BASE_URL}/api/v1/simulation/stop?context=${contextForScenario(scenario)}`, {
                method: "POST"
            });
            setStatus("idle");
            setVehicles([]);
            setSignals([]);
            setSimulationTime(0);
            setQueueLengthVeh(0);
            setQueueBusiestApproach(null);
            setThroughputVehPerMin(0);
            setAvgDelaySeconds(0);
            setAvgQueueLengthVeh(0);
            setAvgQueueLengthM(0);
            setLos(null);
            setCyclePlan(null);
            setSimHistory([]);
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
            await fetch(`${API_BASE_URL}/api/v1/simulation/pause?context=${contextForScenario(scenario)}`, {
                method: "POST"
            });
            setStatus("paused");
        } catch (error) {
            console.error("Failed to pause simulation", error);
        }
    }

    async function handleResume() {
        try {
            await fetch(`${API_BASE_URL}/api/v1/simulation/resume?context=${contextForScenario(scenario)}`, {
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

    // Fase aktif untuk panel "Hasil Simulasi" -- SELALU dari SUMO yang
    // sedang jalan di halaman ini (simSharedPhase/State/Remaining, diisi
    // langsung dari rawState TLS lewat polling /state), tidak pernah dari
    // cache produksi.
    const mappedPhase = isSimulating ? simSharedPhase : null;
    const mappedState: "GREEN" | "YELLOW" | "RED" = simSharedState;
    const mappedRemaining = isSimulating ? simSharedRemaining : 0;

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

                    <div
                        ref={simulationViewRef}
                        className={`overflow-hidden border border-border bg-surface shadow-sm ${
                            isFullscreen ? "flex h-screen flex-col" : "flex flex-col h-full rounded-2xl"
                        }`}
                    >

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
                                onClick={() => void toggleFullscreen()}
                                className="rounded-lg border border-border p-2 text-text-secondary transition hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-text-secondary"
                                aria-label={isFullscreen ? "Keluar dari layar penuh" : "Tampilkan SUMO dalam layar penuh"}
                                title={isFullscreen ? "Keluar dari layar penuh (Esc)" : "Layar penuh"}
                            >
                                {isFullscreen ? <Minimize2 size={17} /> : <Maximize2 size={17} />}
                            </button>

                        </div>

                        {/* Simulation area */}

                        <div className={`relative w-full overflow-hidden bg-[var(--color-canvas)] ${
                            isFullscreen ? "min-h-0 flex-1" : "aspect-[16/11]"
                        }`}>

                            {/* SUMO-GUI Live Stream */}
                            {status === "running" ? (
                                // Frame berubah terus dan tidak boleh masuk cache/optimizer Next Image.
                                // eslint-disable-next-line @next/next/no-img-element
                                <img
                                    src={`${API_BASE_URL}/api/v1/simulation/frame?context=${contextForScenario(scenario)}&v=${Math.floor(simulationTime)}`}
                                    alt="Live SUMO Simulation Stream"
                                    className="absolute inset-0 h-full w-full object-cover object-center"
                                />
                            ) : (
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <p className="text-sm text-text-muted">Simulation Not Running</p>
                                </div>
                            )}

                            {/* Label lengan + lampu per arah (sama seperti dashboard) */}
                            {status === "running" && ([
                                ["north", "UTARA · Jl. Magelang", "left-1/2 top-2 -translate-x-1/2"],
                                ["east", "TIMUR · Jl. Diponegoro", "right-2 top-1/2 -translate-y-1/2"],
                                ["south", "SELATAN · Jl. Tentara Pelajar", "bottom-2 left-1/2 -translate-x-1/2"],
                                ["west", "BARAT · Jl. Kyai Mojo", "left-2 top-1/2 -translate-y-1/2"],
                            ] as const).map(([approach, label, position]) => {
                                const isActive = simSharedPhase === approach;
                                const lampClass = !isActive
                                    ? "bg-signal-red"
                                    : simSharedState === "YELLOW"
                                        ? "bg-signal-amber"
                                        : "bg-signal-green";
                                return (
                                    <div key={approach} className={`absolute ${position} flex items-center gap-1 rounded bg-black/75 px-1.5 py-0.5 text-[9px] font-semibold text-white`}>
                                        <i className={`h-2.5 w-2.5 shrink-0 rounded-full border border-white/40 ${lampClass}`} />
                                        {label}
                                    </div>
                                );
                            })}

                            {/* Legenda warna lampu */}
                            {status === "running" && (
                                <div className="absolute right-3 top-3 flex gap-2 rounded-md border border-white/10 bg-black/55 px-2 py-1 text-[10px] text-white backdrop-blur-sm">
                                    <span className="flex items-center gap-1"><i className="h-2 w-2 rounded-full bg-signal-red" />Merah</span>
                                    <span className="flex items-center gap-1"><i className="h-2 w-2 rounded-full bg-signal-amber" />Kuning</span>
                                    <span className="flex items-center gap-1"><i className="h-2 w-2 rounded-full bg-signal-green" />Hijau</span>
                                </div>
                            )}

                            {/* Hitungan kendaraan (sama seperti dashboard). max-w FIXED (bukan
                                persentase) supaya lebar box gak ikut lebar kartu -- lebar
                                label lengan SELATAN itu tetap (font-size tetap), jadi cuma
                                batas lebar tetap yang menjamin box ini tidak pernah menembus
                                area SELATAN (bottom-center) di kartu sempit maupun lebar. */}
                            {status === "running" && (
                                <div className="absolute bottom-2 left-2 max-w-[130px] rounded-lg border border-white/10 bg-black/50 px-2 py-1 backdrop-blur-sm">
                                    <p className="font-mono text-[10px] font-medium leading-snug text-white">
                                        Deteksi: {detectedVehicles} · Terlihat: {visibleVehicleCount} · Total jaringan: {vehicles.length}
                                        {lastSyncFailedInsertions > 0 && (
                                            <span className="text-signal-amber"> · Gagal sisip: {lastSyncFailedInsertions}</span>
                                        )}
                                    </p>
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

                    <div className="flex flex-col gap-5 h-full">

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
                                        label="Kendaraan Terlihat"
                                        value={`${visibleVehicleCount} (${vehicles.length} di jaringan)`}
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
                                    <span className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-medium ${signals[0].state === 'GREEN' ? 'bg-signal-green/10 text-signal-green' : signals[0].state === 'YELLOW' ? 'bg-signal-amber/10 text-signal-amber' : 'bg-signal-red/10 text-signal-red'}`}>
                                        <Circle
                                            size={7}
                                            fill="currentColor"
                                        />
                                        {signals[0].state}
                                    </span>
                                </div>
                                <div className="h-2 overflow-hidden rounded-full bg-surface-2">
                                    <div className={`h-full rounded-full transition-all duration-500 ${signals[0].state === 'GREEN' ? 'bg-signal-green' : signals[0].state === 'YELLOW' ? 'bg-signal-amber' : 'bg-signal-red'}`} style={{width: `${Math.min(100, Math.max(0, (signals[0].remainingSeconds / 60) * 100))}%`}} />
                                </div>
                                <div className="mt-2 flex justify-between text-[10px] text-text-muted">
                                    <span className="font-mono">{Math.floor(signals[0].remainingSeconds)}s</span>
                                    <span>Remaining</span>
                                </div>
                            </div>
                        )}

                        {/* =============================== */}
                        {/* SIMULATION CONTROLS */}
                        {/* =============================== */}

                        <div className="flex flex-col flex-1 rounded-2xl border border-border bg-surface p-5 shadow-sm">

                            <div className="mb-5 flex items-center gap-3">

                                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-2">
                                    <Settings2
                                        size={18}
                                        className="text-text-secondary"
                                    />
                                </div>

                                <div>
                                    <h2 className="text-sm font-semibold">
                                        Simulation Controls
                                    </h2>
                                </div>

                            </div>

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
                                        onChange={async (e) => {
                                            const newScenario = e.target.value as ScenarioType;
                                            const oldContext = contextForScenario(scenario);
                                            const newContext = contextForScenario(newScenario);
                                            setScenario(newScenario);

                                            if (newScenario === runningScenario) {
                                                // Sudah ini yang aktif -- tidak ada yang perlu diterapkan.
                                                setRecommendationLoading(false);
                                                return;
                                            }

                                            if (status === "idle") {
                                                // Belum ada simulasi jalan -- tombol "Start Simulation"
                                                // yang akan memicu, sesuai perilaku lama.
                                                setRecommendationLoading(true);
                                                return;
                                            }

                                            // Simulasi lagi jalan/paused dan skenario benar-benar
                                            // ganti -- terapkan sekarang juga, jangan nyangkut loading
                                            // selamanya menunggu tombol yang sudah tidak dirender.
                                            setRecommendationLoading(true);

                                            if (oldContext !== newContext && oldContext === "digitaltwin") {
                                                // Sandbox lama ditinggal -- matikan supaya tidak nganggur
                                                // nyala sia-sia. TIDAK PERNAH mematikan context "dashboard"
                                                // dari sini -- itu bukan milik halaman ini.
                                                await fetch(
                                                    `${API_BASE_URL}/api/v1/simulation/stop?context=digitaltwin`,
                                                    { method: "POST" }
                                                ).catch(() => undefined);
                                            }

                                            await handleStartSimulation(newScenario);
                                        }}
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

                                <p className="mt-1.5 text-[10px] text-text-muted">
                                    {loading
                                        ? `Menerapkan skenario ${scenario} ke SUMO…`
                                        : status === "idle"
                                          ? `Dipilih: ${scenario} · tekan Start Simulation`
                                        : runningScenario
                                          ? `Aktif di SUMO: ${runningScenario}`
                                          : "Pilih skenario untuk menjalankan SUMO."}
                                </p>

                            </div>

                            {/* Buttons */}

                            <div className="mt-4 flex gap-2">

                                {scenario === "Traffic Realtime" && status !== "idle" ? (
                                    // Ini instance SUMO yang SAMA dengan dashboard -- Pause/Stop
                                    // dari sini akan ikut menghentikan tampilan live di dashboard
                                    // (bukan bug, memang instance-nya sama). Supaya tidak tidak
                                    // sengaja mematikan demo live orang lain, kendali pause/stop
                                    // sengaja tidak ditawarkan di sini untuk skenario ini.
                                    <div className="rounded-lg border border-border bg-surface-2 px-4 py-1.5 text-[11px] text-text-muted">
                                        Live dari dashboard -- kendalikan dari halaman Dashboard
                                    </div>
                                ) : status === "running" ? (
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
                                        onClick={() => handleStartSimulation()}
                                        disabled={loading}
                                        className="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-1.5 text-[11px] font-medium text-bg transition hover:opacity-90 disabled:opacity-50"
                                    >
                                        <Play size={13} />
                                        {loading ? "Starting..." : "Start Simulation"}
                                    </button>
                                )}

                            </div>

                        </div>

                    </div>

                </div>

                {/* ================================================= */}
                {/* VEHICLE INFORMATION / METRICS */}
                {/* ================================================= */}

                <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-3">

                    {!isSimStateLoaded ? (
                        <div className="col-span-full rounded-2xl border border-border bg-surface p-8 text-center shadow-sm">
                            <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-text-muted border-t-transparent"></div>
                            <p className="mt-3 text-xs text-text-muted">Memuat informasi kendaraan...</p>
                        </div>
                    ) : (
                        <>
                            <StatCard
                                label="Kendaraan Terlihat"
                                value={status === "idle" ? "0" : visibleVehicleCount.toString()}
                                change={status === "idle" ? "" : `${vehicles.length} total di jaringan`}
                                warning={
                                    lastSyncFailedInsertions > 0
                                        ? `${lastSyncFailedInsertions} gagal disisipkan (ruas padat)`
                                        : undefined
                                }
                                icon={<Car size={18} />}
                            />

                            <StatCard
                                label="Queue Length"
                                value={
                                    status === "idle"
                                        ? "0"
                                        : queueBusiestApproach
                                          ? `${APPROACH_SHORT_LABEL[queueBusiestApproach] ?? queueBusiestApproach}: ${queueLengthVeh}`
                                          : `${queueLengthVeh}`
                                }
                                change={status === "idle" ? "" : "Lengan terpadat"}
                                icon={<List size={18} />}
                            />

                            <StatCard
                                label="Traffic Flow"
                                value={status === "idle" ? "0" : `${throughputVehPerMin}/menit`}
                                change={status === "idle" ? "" : "Live snapshot"}
                                icon={<Zap size={18} />}
                            />
                        </>
                    )}

                </div>

                {/* ================================================= */}
                {/* BOTTOM SECTION */}
                {/* ================================================= */}

                <div className="mt-5">

                    {/* =============================== */}
                    {/* HASIL SIMULASI */}
                    {/* =============================== */}
                    {/* Dihitung LANGSUNG dari SUMO yang sedang jalan di
                        halaman ini (get_metrics()/get_simulation_state()),
                        BUKAN dari liveScenarioCache produksi -- supaya beda
                        skenario (Baseline/Aggressive/Balanced/Traffic
                        Realtime) benar-benar menghasilkan angka berbeda. */}

                    <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">

                        <div className="mb-5 flex items-center justify-between">

                            <div className="flex items-center gap-3">

                                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-2">
                                    <Activity
                                        size={18}
                                        className="text-text-secondary"
                                    />
                                </div>

                                <div>
                                    <h2 className="text-sm font-semibold">
                                        Hasil Simulasi
                                    </h2>
                                    <p className="text-xs text-text-muted">
                                        {isSimulating
                                            ? `Skenario aktif: ${runningScenario ?? scenario}`
                                            : "Belum ada simulasi jalan"}
                                    </p>
                                </div>

                            </div>

                            {isSimulating && los && (
                                <span
                                    className={`rounded-full px-3 py-1 text-xs font-semibold ${
                                        los === "A" || los === "B"
                                            ? "bg-signal-green/10 text-signal-green"
                                            : los === "C" || los === "D"
                                              ? "bg-signal-amber/10 text-signal-amber"
                                              : "bg-signal-red/10 text-signal-red"
                                    }`}
                                >
                                    LOS {los}
                                </span>
                            )}

                        </div>

                        {!isSimulating ? (
                            <div className="py-8 text-center">
                                <p className="text-xs text-text-muted">
                                    Mulai simulasi untuk melihat delay, antrean, dan LOS simpang.
                                </p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
                                <MetricRow
                                    label="Avg Delay"
                                    value={`${avgDelaySeconds}s`}
                                    icon={<Clock3 size={15} />}
                                />
                                <MetricRow
                                    label="Avg Queue"
                                    value={`${avgQueueLengthM}m (${avgQueueLengthVeh} kend.)`}
                                    icon={<List size={15} />}
                                />
                                <MetricRow
                                    label="Throughput"
                                    value={`${throughputVehPerMin}/menit`}
                                    icon={<Zap size={15} />}
                                />
                                <MetricRow
                                    label="Fase Aktif"
                                    value={
                                        mappedPhase
                                            ? `${APPROACH_SHORT_LABEL[mappedPhase] ?? mappedPhase} · ${mappedState} · ${Math.floor(mappedRemaining)}s`
                                            : "-"
                                    }
                                    icon={<Circle size={15} />}
                                />
                            </div>
                        )}

                    </div>

                    {/* =============================== */}
                    {/* DURASI SINYAL PER LENGAN */}
                    {/* =============================== */}
                    {/* Ini satu-satunya hal yang benar-benar beda antar
                        skenario (Baseline/Aggressive/Balanced cuma beda di
                        detik hijau per lengan, demand-nya sama) -- ditulis
                        eksplisit sebagai angka supaya beda skenario kerasa,
                        tidak cuma tersirat dari video yang jalan. */}

                    {isSimulating && cyclePlan && cyclePlan.phases.length > 0 && (
                        <div className="mt-5 rounded-2xl border border-border bg-surface p-5 shadow-sm">

                            <div className="mb-4 flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-2">
                                        <TrafficCone size={18} className="text-text-secondary" />
                                    </div>
                                    <div>
                                        <h2 className="text-sm font-semibold">Durasi Sinyal Per Lengan</h2>
                                        <p className="text-xs text-text-muted">
                                            {cyclePlan.candidateId ? `Skenario: ${cyclePlan.candidateId}` : "Program TLS aktif"}
                                        </p>
                                    </div>
                                </div>
                                {cyclePlan.totalCycleSeconds !== undefined && (
                                    <span className="text-xs text-text-muted">
                                        Total siklus: <span className="font-mono text-text">{cyclePlan.totalCycleSeconds}s</span>
                                    </span>
                                )}
                            </div>

                            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                                {cyclePlan.phases.map((phase) => (
                                    <div
                                        key={phase.approach}
                                        className="rounded-lg border border-border bg-surface-2 p-3"
                                    >
                                        <p className="mb-2 text-xs font-medium text-text">
                                            {APPROACH_SHORT_LABEL[phase.approach] ?? phase.approach}
                                        </p>
                                        <div className="space-y-1 text-[11px]">
                                            <div className="flex items-center justify-between">
                                                <span className="flex items-center gap-1.5 text-text-muted">
                                                    <Circle size={7} fill="currentColor" className="text-signal-green" />
                                                    Hijau
                                                </span>
                                                <span className="font-mono text-text">{phase.greenSeconds}s</span>
                                            </div>
                                            <div className="flex items-center justify-between">
                                                <span className="flex items-center gap-1.5 text-text-muted">
                                                    <Circle size={7} fill="currentColor" className="text-signal-amber" />
                                                    Kuning
                                                </span>
                                                <span className="font-mono text-text">{phase.yellowSeconds}s</span>
                                            </div>
                                            {phase.redSeconds !== undefined && (
                                                <div className="flex items-center justify-between">
                                                    <span className="flex items-center gap-1.5 text-text-muted">
                                                        <Circle size={7} fill="currentColor" className="text-signal-red" />
                                                        Merah
                                                    </span>
                                                    <span className="font-mono text-text">{phase.redSeconds}s</span>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>

                        </div>
                    )}

                    {/* =============================== */}
                    {/* TREN SIMULASI */}
                    {/* =============================== */}

                    {isSimulating && (
                        <div className="mt-5 rounded-2xl border border-border bg-surface p-5 shadow-sm">

                            <div className="mb-4">
                                <h2 className="text-sm font-semibold">Tren Simulasi</h2>
                                <p className="text-xs text-text-muted">
                                    {simHistory.length < 2
                                        ? "Mengumpulkan data…"
                                        : `${simHistory.length} titik sejak skenario ini diterapkan`}
                                </p>
                            </div>

                            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
                                <MiniTrendChart
                                    title="Avg Delay"
                                    unit="s"
                                    data={simHistory}
                                    dataKey="delay"
                                    color="#3987e5"
                                />
                                <MiniTrendChart
                                    title="Avg Queue"
                                    unit="m"
                                    data={simHistory}
                                    dataKey="queue"
                                    color="#d95926"
                                />
                                <MiniTrendChart
                                    title="Throughput"
                                    unit="/menit"
                                    data={simHistory}
                                    dataKey="throughput"
                                    color="#199e70"
                                />
                            </div>

                        </div>
                    )}

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
    warning,
    icon,
}: {
    label: string;
    value: string;
    change: string;
    warning?: string;
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

            {warning && (
                <p className="mt-1 text-[10px] text-signal-amber">
                    {warning}
                </p>
            )}

        </div>
    );
}

function MiniTrendChart({
    title,
    unit,
    data,
    dataKey,
    color,
}: {
    title: string;
    unit: string;
    data: SimHistoryPoint[];
    dataKey: "delay" | "queue" | "throughput";
    color: string;
}) {
    const latest = data.length > 0 ? data[data.length - 1][dataKey] : null;

    return (
        <div className="rounded-lg border border-border bg-surface-2 p-3">

            <div className="mb-1 flex items-center justify-between">
                <span className="text-xs text-text-muted">{title}</span>
                <span className="font-mono text-xs font-medium text-text">
                    {latest !== null ? `${latest}${unit}` : "-"}
                </span>
            </div>

            <div className="h-[90px] w-full">
                {data.length < 2 ? (
                    <div className="flex h-full items-center justify-center">
                        <span className="text-[10px] text-text-muted">Mengumpulkan data…</span>
                    </div>
                ) : (
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={data} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
                            <CartesianGrid stroke="#232935" vertical={false} />
                            <XAxis dataKey="t" hide />
                            <YAxis
                                tick={{ fill: "#5b6472", fontSize: 10 }}
                                axisLine={false}
                                tickLine={false}
                                width={28}
                            />
                            <Tooltip
                                contentStyle={{
                                    background: "#171c27",
                                    border: "1px solid #232935",
                                    borderRadius: 8,
                                    fontSize: 11,
                                }}
                                labelFormatter={(t) => `Detik simulasi ${t}`}
                                formatter={(value) => [`${value}${unit}`, title]}
                            />
                            <Line
                                type="monotone"
                                dataKey={dataKey}
                                stroke={color}
                                strokeWidth={2}
                                dot={false}
                                activeDot={{ r: 4 }}
                                isAnimationActive={false}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                )}
            </div>

        </div>
    );
}

