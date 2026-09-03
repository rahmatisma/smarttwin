"use client";

import { useCallback, useEffect, useState } from "react";
import {
    Activity,
    ChevronDown,
    ChevronLeft,
    ChevronRight,
    Clock3,
    Eye,
    Filter,
    History as HistoryIcon,
    Layers,
    Minus,
    Search,
    TrafficCone,
    TrendingDown,
    TrendingUp,
    X,
} from "lucide-react";

import {
    CartesianGrid,
    Legend,
    Line,
    LineChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";

import Sidebar from "@/components/Sidebar";
import ForecastChart from "@/components/ForecastChart";
import { fetchForecast, DEFAULT_INTERSECTION_ID } from "@/lib/supabaseData";
import type { ForecastResponse } from "@/types/traffic";

/*
 * =========================================================
 * RIWAYAT KEPUTUSAN
 * =========================================================
 *
 * Halaman ini sebelumnya memakai data contoh (HISTORY_DATA yang
 * di-hardcode). Sekarang membaca riwayat asli dari
 * GET /api/v1/history/recommendations -- yaitu keputusan yang benar-benar
 * dikeluarkan sistem, ditulis tiap siklus oleh simulation/scenario_worker.py.
 *
 * Satu baris = satu SIKLUS keputusan (satu timestamp), berisi durasi hijau
 * untuk keempat lengan sekaligus -- bukan satu keputusan per lengan.
 */

const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const PAGE_SIZE = 20;

// Nama lengan disimpan dalam bahasa Inggris di database (kontrak
// docs/data-contract.md). Penerjemahan ke bahasa Indonesia SENGAJA cuma di
// lapisan tampilan ini, supaya kontrak antar-modul tidak ikut berubah.
const LABEL_LENGAN: Record<string, string> = {
    north: "Utara",
    south: "Selatan",
    east: "Timur",
    west: "Barat",
    // Data lama sempat memakai bahasa Indonesia + proxy "simpang_tengah"
    // untuk lengan utara (kamera CCTV_2 memantau tengah simpang).
    utara: "Utara",
    selatan: "Selatan",
    timur: "Timur",
    barat: "Barat",
    simpang_tengah: "Utara*",
};

const URUTAN_LENGAN = ["north", "east", "south", "west"];

/*
 * Warna 4 lengan. Diambil dari palet yang sudah lolos uji:
 * pita terang, ambang chroma, keterpisahan buta warna (ΔE terburuk 8,4
 * protan / 24,4 tritan), dan kontras >= 3:1 terhadap latar gelap.
 * Jangan diganti asal -- urutannya bagian dari jaminan keterbacaan itu.
 */
const WARNA_LENGAN: Record<string, string> = {
    north: "#3987e5",
    east: "#d95926",
    south: "#199e70",
    west: "#c98500",
};

// Ambang penanda "berubah". Dihitung di sini, BUKAN disimpan di database --
// supaya angkanya bisa diubah kapan saja tanpa menyentuh data yang sudah ada.
const AMBANG_BERUBAH_DETIK = 2;

interface Fase {
    approach: string;
    greenSeconds: number | null;
    currentGreenSeconds: number | null;
    confidence: number | null;
    expectedDelayReductionPercent: number | null;
}

interface Kandidat {
    candidateId: string;
    isWinner: boolean;
    avgDelaySeconds: number | null;
    avgQueueLengthM: number | null;
    throughputVeh: number | null;
    los: string | null;
}

interface MetrikBeforeAfter {
    metric: string;
    label: string;
    unit: string;
    before: number;
    after: number;
    changePercent: number | null;
    // true = membaik, false = memburuk, null = tidak ada perubahan
    // (baseline yang menang -- keputusan yang sah, bukan kegagalan sistem).
    improved: boolean | null;
}

interface BeforeAfter {
    baselineCandidateId: string;
    winnerCandidateId: string;
    changed: boolean;
    metrics: MetrikBeforeAfter[];
}

interface KondisiLengan {
    approach: string;
    volume: number | null;
    queueLengthVeh: number | null;
    queueLengthMEst: number | null;
    densityIndex: number | null;
}

interface Siklus {
    timestamp: string;
    source: string | null;
    phases: Fase[];
    candidates: Kandidat[];
    trafficConditions: KondisiLengan[];
    winner: Kandidat | null;
    // Identitas kondisi lalu lintas yang dievaluasi. Kalau nilainya sama
    // dengan siklus sebelumnya, berarti sistem mengevaluasi ULANG kondisi
    // yang sama -- bukan merespons situasi baru. Dibedakan di tabel supaya
    // baris identik tidak salah dibaca sebagai keputusan yang berbeda-beda.
    trafficStateId: number | null;
    beforeAfter: BeforeAfter | null;
}

interface ResponRiwayat {
    page: number;
    pageSize: number;
    totalCycles: number;
    items: Siklus[];
}

function labelLengan(approach: string): string {
    return LABEL_LENGAN[approach?.toLowerCase()] ?? approach;
}

function urutkanFase(phases: Fase[]): Fase[] {
    return [...phases].sort((a, b) => {
        const indeksA = URUTAN_LENGAN.indexOf(a.approach?.toLowerCase());
        const indeksB = URUTAN_LENGAN.indexOf(b.approach?.toLowerCase());
        return (indeksA === -1 ? 99 : indeksA) - (indeksB === -1 ? 99 : indeksB);
    });
}

function formatWaktu(timestamp: string): string {
    const waktu = new Date(timestamp);
    if (Number.isNaN(waktu.getTime())) return timestamp;
    return waktu.toLocaleString("id-ID", {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    });
}

/*
 * Penanda "berubah": siklus dibandingkan dengan siklus SEBELUMNYA (yang di
 * daftar ini berarti item berikutnya, karena urutannya terbaru dulu).
 * Dianggap berubah kalau kandidat pemenangnya ganti ATAU ada lengan yang
 * durasinya bergeser >= AMBANG_BERUBAH_DETIK. Tanpa ambang, selisih 1 detik
 * akibat fluktuasi kecil akan menyalakan penanda hampir di semua baris dan
 * penanda itu jadi tidak berguna.
 */
function apakahBerubah(sekarang: Siklus, sebelumnya: Siklus | undefined): boolean {
    if (!sebelumnya) return false;

    if (sekarang.winner?.candidateId !== sebelumnya.winner?.candidateId) {
        return true;
    }

    const durasiSebelumnya = new Map(
        sebelumnya.phases.map((fase) => [fase.approach, fase.greenSeconds ?? 0])
    );

    return sekarang.phases.some((fase) => {
        const lama = durasiSebelumnya.get(fase.approach);
        if (lama === undefined) return true;
        return Math.abs((fase.greenSeconds ?? 0) - lama) >= AMBANG_BERUBAH_DETIK;
    });
}

interface TitikGrafik {
    waktu: string;
    [kunci: string]: string | number | null;
}

/*
 * Menyiapkan data untuk dua grafik bertumpuk.
 *
 * Daftar dari API urut TERBARU DULU; grafik waktu harus dibaca kiri->kanan
 * secara kronologis, jadi urutannya dibalik dulu di sini.
 */
function siapkanDataGrafik(items: Siklus[]): TitikGrafik[] {
    return [...items].reverse().map((siklus) => {
        const titik: TitikGrafik = { waktu: formatJam(siklus.timestamp) };

        for (const fase of siklus.phases) {
            const lengan = fase.approach?.toLowerCase();
            if (URUTAN_LENGAN.includes(lengan)) {
                titik[`hijau_${lengan}`] = fase.greenSeconds;
            }
        }

        for (const kondisi of siklus.trafficConditions) {
            const lengan = kondisi.approach?.toLowerCase();
            if (URUTAN_LENGAN.includes(lengan)) {
                titik[`antrean_${lengan}`] = kondisi.queueLengthVeh;
            }
        }

        return titik;
    });
}

function formatJam(timestamp: string): string {
    const waktu = new Date(timestamp);
    if (Number.isNaN(waktu.getTime())) return timestamp;
    return waktu.toLocaleTimeString("id-ID", {
        hour: "2-digit",
        minute: "2-digit",
    });
}

function GrafikLengan({
    judul,
    keterangan,
    data,
    prefiks,
    satuan,
    kosong,
}: {
    judul: string;
    keterangan: string;
    data: TitikGrafik[];
    prefiks: "hijau" | "antrean";
    satuan: string;
    kosong: boolean;
}) {
    return (
        <div>
            <div className="mb-1 flex items-baseline justify-between">
                <h3 className="text-xs font-medium">{judul}</h3>
                <span className="text-[10px] text-text-muted">{keterangan}</span>
            </div>

            <div className="h-[150px] w-full">
                {kosong ? (
                    <div className="flex h-full items-center justify-center rounded-lg border border-dashed border-border">
                        <span className="text-[11px] text-text-muted">
                            Data belum tersedia untuk siklus di halaman ini
                        </span>
                    </div>
                ) : (
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart
                            data={data}
                            margin={{ top: 6, right: 8, left: -18, bottom: 0 }}
                        >
                            <CartesianGrid stroke="#232935" vertical={false} />
                            <XAxis
                                dataKey="waktu"
                                tick={{ fill: "#5b6472", fontSize: 10 }}
                                axisLine={{ stroke: "#232935" }}
                                tickLine={false}
                                minTickGap={24}
                            />
                            <YAxis
                                tick={{ fill: "#5b6472", fontSize: 10 }}
                                axisLine={false}
                                tickLine={false}
                                width={34}
                            />
                            <Tooltip
                                contentStyle={{
                                    background: "#171c27",
                                    border: "1px solid #232935",
                                    borderRadius: 8,
                                    fontSize: 11,
                                }}
                                formatter={(value, name) => [
                                    `${value}${satuan}`,
                                    labelLengan(String(name).replace(`${prefiks}_`, "")),
                                ]}
                            />
                            <Legend
                                formatter={(value) =>
                                    labelLengan(String(value).replace(`${prefiks}_`, ""))
                                }
                                wrapperStyle={{ fontSize: 11 }}
                                iconType="plainline"
                            />
                            {URUTAN_LENGAN.map((lengan) => (
                                <Line
                                    key={lengan}
                                    type="monotone"
                                    dataKey={`${prefiks}_${lengan}`}
                                    name={`${prefiks}_${lengan}`}
                                    stroke={WARNA_LENGAN[lengan]}
                                    strokeWidth={2}
                                    dot={false}
                                    activeDot={{ r: 4 }}
                                    isAnimationActive={false}
                                    connectNulls
                                />
                            ))}
                        </LineChart>
                    </ResponsiveContainer>
                )}
            </div>
        </div>
    );
}

/*
 * Ambang kepadatan SAMA PERSIS dengan StatsRow.tsx (dashboard) --
 * dikalibrasi ulang 25 Agustus 2026 ke skala densityIndex sebenarnya
 * (rata-rata kendaraan per zona per window, bukan vehicles/km atau LOS
 * PKJI resmi). Threshold lama (90/130) dirancang untuk skala yang jauh
 * lebih besar dari data asli (0-13,4 di seluruh dataset), jadi tidak
 * ditulis ulang di sini -- kalau ambang dashboard berubah, ini ikut basi.
 */
function tingkatKepadatan(kondisi: KondisiLengan[]): {
    label: string;
    warna: string;
} {
    const nilai = kondisi
        .map((k) => k.densityIndex)
        .filter((v): v is number => v != null);

    if (nilai.length === 0) {
        return { label: "—", warna: "bg-surface-2 text-text-muted" };
    }

    const rata = nilai.reduce((a, b) => a + b, 0) / nilai.length;

    if (rata >= 10) return { label: "Tinggi", warna: "bg-signal-red/10 text-signal-red" };
    if (rata >= 5) return { label: "Sedang", warna: "bg-signal-amber/10 text-signal-amber" };
    return { label: "Rendah", warna: "bg-signal-green/10 text-signal-green" };
}

function warnaLos(los: string | null): string {
    if (!los) return "bg-surface-2 text-text-muted";
    if (los === "A" || los === "B") return "bg-signal-green/10 text-signal-green";
    if (los === "C" || los === "D") return "bg-signal-amber/10 text-signal-amber";
    return "bg-signal-red/10 text-signal-red";
}

export default function HistoryPage() {
    const [data, setData] = useState<ResponRiwayat | null>(null);
    const [halaman, setHalaman] = useState(1);
    const [memuat, setMemuat] = useState(true);
    const [galat, setGalat] = useState<string | null>(null);
    const [dipilih, setDipilih] = useState<Siklus | null>(null);
    const [forecastData, setForecastData] = useState<ForecastResponse | null>(null);

    useEffect(() => {
        if (dipilih) {
            fetchForecast(DEFAULT_INTERSECTION_ID).then((res) => {
                setForecastData(res);
            });
        } else {
            setForecastData(null);
        }
    }, [dipilih]);

    // Filter cuma menyaring siklus yang SUDAH dimuat di halaman ini (client-
    // side) -- backend tidak diminta ulang. Tidak ada dropdown "Persimpangan"
    // seperti mockup: sistem ini cuma punya satu simpang (Pingit), jadi
    // dropdown begitu cuma akan berisi 1 opsi yang selalu terpilih --
    // elemen UI tanpa fungsi nyata.
    const [cari, setCari] = useState("");
    const [filterSumber, setFilterSumber] = useState("Semua Sumber");
    const [filterStatus, setFilterStatus] = useState("Semua Status");

    const ambilData = useCallback(async (nomorHalaman: number) => {
        setMemuat(true);
        setGalat(null);
        try {
            const res = await fetch(
                `${API_BASE_URL}/api/v1/history/recommendations` +
                    `?page=${nomorHalaman}&pageSize=${PAGE_SIZE}`
            );
            if (!res.ok) {
                throw new Error(`Backend menjawab ${res.status}`);
            }
            setData(await res.json());
        } catch (err) {
            setGalat(
                err instanceof Error
                    ? err.message
                    : "Tidak dapat menghubungi backend."
            );
            setData(null);
        } finally {
            setMemuat(false);
        }
    }, []);

    useEffect(() => {
        // Ditunda lewat microtask supaya setMemuat/setGalat di awal ambilData()
        // (sebelum await pertama) tidak dianggap "setState sinkron di dalam
        // efek" oleh react-hooks/set-state-in-effect -- perilaku sama,
        // cuma pemicunya tidak lagi sinkron dari body efek.
        queueMicrotask(() => {
            void ambilData(halaman);
        });
    }, [ambilData, halaman]);

    const totalHalaman = data
        ? Math.max(1, Math.ceil(data.totalCycles / PAGE_SIZE))
        : 1;

    // Grafik menampilkan siklus pada HALAMAN INI saja (maksimal 20), bukan
    // seluruh riwayat -- supaya yang terlihat selalu sama dengan tabel di
    // bawahnya dan tidak perlu menarik ribuan baris sekaligus.
    const dataGrafik = data ? siapkanDataGrafik(data.items) : [];

    // Data lama (hasil impor batch) tidak punya kondisi lalu lintas terkait.
    // Dibedakan supaya grafik atas menampilkan keterangan jujur, bukan
    // kotak kosong tanpa penjelasan.
    const adaDataAntrean = dataGrafik.some((titik) =>
        URUTAN_LENGAN.some((lengan) => titik[`antrean_${lengan}`] != null)
    );

    const jumlahKondisiUnik = data
        ? new Set(
              data.items
                  .map((siklus) => siklus.trafficStateId)
                  .filter((id): id is number => id != null)
          ).size
        : 0;

    // Dipakai isi dropdown "Sumber" -- daftar sumber yang BENAR-BENAR ada
    // di halaman ini, bukan daftar yang dikarang di muka.
    const daftarSumber = data
        ? Array.from(
              new Set(data.items.map((s) => s.source).filter((s): s is string => !!s))
          )
        : [];

    const itemDenganStatus = (data?.items ?? []).map((siklus, indeks) => ({
        siklus,
        berubah: apakahBerubah((data?.items ?? [])[indeks], (data?.items ?? [])[indeks + 1]),
    }));

    const itemTersaring = itemDenganStatus.filter(({ siklus, berubah }) => {
        if (
            cari.trim() &&
            !siklus.winner?.candidateId?.toLowerCase().includes(cari.trim().toLowerCase()) &&
            !siklus.source?.toLowerCase().includes(cari.trim().toLowerCase())
        ) {
            return false;
        }
        if (filterSumber !== "Semua Sumber" && siklus.source !== filterSumber) {
            return false;
        }
        if (filterStatus === "Berubah" && !berubah) return false;
        if (filterStatus === "Tetap" && berubah) return false;
        return true;
    });

    // Ringkasan dihitung dari siklus BERUBAH di halaman ini saja -- rata-rata
    // dampak siklus yang "tetap" akan selalu 0% dan menenggelamkan angka
    // sebenarnya. Tidak ada skor komposit ("Overall Performance") seperti
    // mockup awal -- itu angka tanpa rumus jelas, tidak bisa dipertanggung-
    // jawabkan kalau ditanya "12,4% itu dari mana?".
    const siklusBerubah = itemDenganStatus.filter((x) => x.berubah);
    const rataRataPerbaikanDelay = (() => {
        const nilai = siklusBerubah
            .map((x) => x.siklus.beforeAfter?.metrics.find((m) => m.metric === "avgDelaySeconds")?.changePercent)
            .filter((v): v is number => v != null);
        if (nilai.length === 0) return null;
        return nilai.reduce((a, b) => a + b, 0) / nilai.length;
    })();

    return (
        <div className="flex min-h-screen bg-bg text-text">
            <Sidebar />

            <main className="min-w-0 flex-1 px-6 py-6">
                <div className="mx-auto max-w-[1600px] space-y-6">

                    {/* HEADER */}
                    <div>
                        <div className="mb-2 flex items-center gap-2">
                            <HistoryIcon className="h-6 w-6 text-text" />
                            <h1 className="text-2xl font-bold tracking-tight">
                                Riwayat Keputusan
                            </h1>
                        </div>
                        <p className="text-sm text-text-muted">
                            Rekomendasi durasi lampu yang pernah dikeluarkan sistem,
                            beserta kondisi lalu lintas yang memicunya.
                        </p>
                    </div>

                    {/* RINGKASAN */}
                    {/*
                        4 kartu gaya "header dashboard". Semua angka nyata dari
                        data yang sedang tampil -- TIDAK ada skor komposit
                        seperti "Overall Performance +12,4%" (mockup awal),
                        karena rumusnya tidak jelas dan tidak bisa dijawab
                        kalau ditanya "12,4% itu dari mana?".
                    */}
                    {data && !memuat && (
                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                            <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
                                <div className="flex items-start justify-between">
                                    <div>
                                        <p className="text-xs text-text-muted">Total Siklus</p>
                                        <p className="mt-2 font-display text-xl font-semibold">
                                            {data.totalCycles}
                                        </p>
                                    </div>
                                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-2 text-text-secondary">
                                        <Activity size={18} />
                                    </div>
                                </div>
                                <p className="mt-3 text-[10px] text-text-muted">
                                    Halaman {data.page} dari {totalHalaman}
                                </p>
                            </div>

                            {/*
                                Angka paling jujur di halaman ini: banyak siklus
                                TIDAK sama dengan banyak kondisi yang direspons.
                                Kalau CV tidak berjalan, puluhan siklus bisa
                                mengevaluasi satu kondisi yang sama berulang kali.
                            */}
                            <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
                                <div className="flex items-start justify-between">
                                    <div>
                                        <p className="text-xs text-text-muted">Kondisi Unik</p>
                                        <p className="mt-2 font-display text-xl font-semibold">
                                            {jumlahKondisiUnik}
                                            <span className="text-sm font-normal text-text-muted">
                                                {" "}
                                                / {data.items.length}
                                            </span>
                                        </p>
                                    </div>
                                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-2 text-text-secondary">
                                        <Layers size={18} />
                                    </div>
                                </div>
                                <p
                                    className={`mt-3 text-[10px] ${
                                        jumlahKondisiUnik === 1 && data.items.length > 1
                                            ? "text-signal-amber"
                                            : "text-text-muted"
                                    }`}
                                >
                                    {jumlahKondisiUnik === 1 && data.items.length > 1
                                        ? "CV tidak sedang memasok data baru"
                                        : "kondisi lalu lintas berbeda"}
                                </p>
                            </div>

                            <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
                                <div className="flex items-start justify-between">
                                    <div>
                                        <p className="text-xs text-text-muted">Skenario Berubah</p>
                                        <p className="mt-2 font-display text-xl font-semibold">
                                            {siklusBerubah.length}
                                            <span className="text-sm font-normal text-text-muted">
                                                {" "}
                                                / {data.items.length}
                                            </span>
                                        </p>
                                    </div>
                                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-2 text-text-secondary">
                                        <TrendingUp size={18} />
                                    </div>
                                </div>
                                <p className="mt-3 text-[10px] text-text-muted">
                                    sistem menyimpang dari baseline
                                </p>
                            </div>

                            <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
                                <div className="flex items-start justify-between">
                                    <div>
                                        <p className="text-xs text-text-muted">
                                            Rata-rata Perbaikan Delay
                                        </p>
                                        <p className="mt-2 font-display text-xl font-semibold">
                                            {rataRataPerbaikanDelay != null
                                                ? `${rataRataPerbaikanDelay > 0 ? "+" : ""}${rataRataPerbaikanDelay.toFixed(1)}%`
                                                : "—"}
                                        </p>
                                    </div>
                                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-2 text-text-secondary">
                                        <TrendingDown size={18} />
                                    </div>
                                </div>
                                <p
                                    className={`mt-3 text-[10px] ${
                                        rataRataPerbaikanDelay == null
                                            ? "text-text-muted"
                                            : rataRataPerbaikanDelay < 0
                                              ? "text-signal-green"
                                              : "text-signal-amber"
                                    }`}
                                >
                                    {rataRataPerbaikanDelay != null
                                        ? `dari ${siklusBerubah.length} siklus yang berubah`
                                        : "belum ada siklus yang berubah"}
                                </p>
                            </div>
                        </div>
                    )}

                    {/* GRAFIK: INPUT vs OUTPUT */}
                    {/*
                        Dua grafik BERTUMPUK dengan sumbu waktu sejajar, bukan
                        satu grafik gabungan: satuannya beda (kendaraan vs
                        detik), dan menggabungkannya butuh dua sumbu-Y yang
                        membuat skalanya gampang salah dibaca. Ditumpuk begini
                        korelasinya tetap terbaca -- kalau antrean sebuah lengan
                        naik dan durasi hijaunya ikut naik, sistemnya terbukti
                        merespons, bukan mengeluarkan angka statis.
                    */}
                    {data && !memuat && data.items.length > 0 && (
                        <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
                            <div className="mb-4">
                                <h2 className="text-sm font-semibold">
                                    Apakah Sistem Merespons Lalu Lintas?
                                </h2>
                                <p className="text-xs text-text-muted">
                                    Bandingkan kedua grafik pada waktu yang sama: antrean naik
                                    di suatu lengan seharusnya diikuti durasi hijau lengan itu.
                                </p>
                            </div>

                            {dataGrafik.length < 2 ? (
                                <div className="rounded-lg border border-dashed border-border py-8 text-center">
                                    <p className="text-xs text-text-muted">
                                        Butuh minimal 2 siklus untuk membentuk garis — baru ada{" "}
                                        {dataGrafik.length}.
                                    </p>
                                    <p className="mt-1 text-[10px] text-text-muted">
                                        Grafik terisi otomatis selama <code>scenario_worker.py</code>{" "}
                                        berjalan (1 siklus per menit).
                                    </p>
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    <GrafikLengan
                                        judul="1. Antrean per Lengan  (kondisi lapangan)"
                                        keterangan="masukan sistem"
                                        data={dataGrafik}
                                        prefiks="antrean"
                                        satuan=" kend"
                                        kosong={!adaDataAntrean}
                                    />
                                    <GrafikLengan
                                        judul="2. Durasi Hijau per Lengan  (keputusan sistem)"
                                        keterangan="keluaran sistem"
                                        data={dataGrafik}
                                        prefiks="hijau"
                                        satuan="s"
                                        kosong={false}
                                    />
                                </div>
                            )}
                        </div>
                    )}

                    {/* FILTER */}
                    {/*
                        Tidak ada dropdown "Persimpangan" seperti mockup awal --
                        sistem ini cuma punya SATU simpang (Pingit). Dropdown
                        dengan 1 opsi yang selalu terpilih bukan filter, itu
                        elemen dekoratif -- jadi sengaja tidak dibuat.
                    */}
                    {data && data.items.length > 0 && (
                        <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
                            <div className="mb-3 flex items-center gap-2">
                                <Filter size={15} className="text-text-secondary" />
                                <h2 className="text-xs font-medium">Filter Riwayat</h2>
                            </div>
                            <div className="flex flex-col gap-3 sm:flex-row">
                                <div className="relative flex-1">
                                    <Search
                                        size={14}
                                        className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
                                    />
                                    <input
                                        type="text"
                                        value={cari}
                                        onChange={(e) => setCari(e.target.value)}
                                        placeholder="Cari kandidat atau sumber…"
                                        className="w-full rounded-lg border border-border bg-surface-2 py-2 pl-9 pr-3 text-xs outline-none transition focus:border-text-muted"
                                    />
                                </div>

                                <div className="relative">
                                    <select
                                        value={filterSumber}
                                        onChange={(e) => setFilterSumber(e.target.value)}
                                        className="w-full appearance-none rounded-lg border border-border bg-surface-2 py-2 pl-3 pr-8 text-xs outline-none transition focus:border-text-muted sm:w-48"
                                    >
                                        <option>Semua Sumber</option>
                                        {daftarSumber.map((sumber) => (
                                            <option key={sumber} value={sumber}>
                                                {sumber}
                                            </option>
                                        ))}
                                    </select>
                                    <ChevronDown
                                        size={13}
                                        className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted"
                                    />
                                </div>

                                <div className="relative">
                                    <select
                                        value={filterStatus}
                                        onChange={(e) => setFilterStatus(e.target.value)}
                                        className="w-full appearance-none rounded-lg border border-border bg-surface-2 py-2 pl-3 pr-8 text-xs outline-none transition focus:border-text-muted sm:w-40"
                                    >
                                        <option>Semua Status</option>
                                        <option>Berubah</option>
                                        <option>Tetap</option>
                                    </select>
                                    <ChevronDown
                                        size={13}
                                        className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted"
                                    />
                                </div>
                            </div>
                        </div>
                    )}

                    {/* TABEL */}
                    <div className="overflow-hidden rounded-2xl border border-border bg-surface shadow-sm">

                        {data && !memuat && data.items.length > 0 && (
                            <div className="flex items-center justify-between border-b border-border px-5 py-3">
                                <div>
                                    <h2 className="text-sm font-semibold">Riwayat Siklus</h2>
                                    <p className="text-xs text-text-muted">
                                        Menampilkan {itemTersaring.length} dari {data.items.length}{" "}
                                        siklus di halaman ini
                                    </p>
                                </div>
                            </div>
                        )}

                        {memuat ? (
                            <div className="p-10 text-center">
                                <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-text-muted border-t-transparent" />
                                <p className="mt-3 text-xs text-text-muted">Memuat riwayat…</p>
                            </div>
                        ) : galat ? (
                            <div className="p-10 text-center">
                                <p className="text-sm text-signal-red">Gagal memuat riwayat</p>
                                <p className="mt-1 text-xs text-text-muted">{galat}</p>
                            </div>
                        ) : !data || data.items.length === 0 ? (
                            <div className="p-10 text-center">
                                <p className="text-sm text-text">Belum ada riwayat</p>
                                <p className="mt-1 text-xs text-text-muted">
                                    Riwayat terisi otomatis saat <code>scenario_worker.py</code> berjalan.
                                </p>
                            </div>
                        ) : itemTersaring.length === 0 ? (
                            <div className="p-10 text-center">
                                <p className="text-sm text-text">Tidak ada siklus yang cocok</p>
                                <p className="mt-1 text-xs text-text-muted">
                                    Coba ubah kata kunci pencarian atau filter di atas.
                                </p>
                            </div>
                        ) : (
                            <div className="overflow-x-auto">
                                <table className="w-full text-left text-sm">
                                    <thead className="border-b border-border text-xs text-text-muted">
                                        <tr>
                                            <th className="px-5 py-3 font-medium">Waktu</th>
                                            <th className="px-5 py-3 font-medium">Persimpangan</th>
                                            <th className="px-5 py-3 font-medium">Kepadatan</th>
                                            <th className="px-5 py-3 font-medium">Durasi Hijau per Lengan</th>
                                            <th className="px-5 py-3 font-medium">Dampak (vs Baseline)</th>
                                            <th className="px-5 py-3 font-medium">LOS</th>
                                            <th className="px-5 py-3 font-medium">Sumber</th>
                                            <th className="px-5 py-3 font-medium">Status</th>
                                            <th className="px-5 py-3 font-medium"></th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {itemTersaring.map(({ siklus, berubah }, indeks) => {
                                            const sebelumnya = itemTersaring[indeks + 1]?.siklus;
                                            const kondisiSama =
                                                sebelumnya != null &&
                                                siklus.trafficStateId != null &&
                                                siklus.trafficStateId === sebelumnya.trafficStateId;
                                            const kepadatan = tingkatKepadatan(siklus.trafficConditions);
                                            const dampakDelay = siklus.beforeAfter?.metrics.find(
                                                (m) => m.metric === "avgDelaySeconds"
                                            );

                                            return (
                                                <tr
                                                    key={siklus.timestamp}
                                                    onClick={() => setDipilih(siklus)}
                                                    className="cursor-pointer border-b border-border/50 transition hover:bg-surface-2"
                                                >
                                                    <td className="whitespace-nowrap px-5 py-3 font-mono text-xs">
                                                        {formatWaktu(siklus.timestamp)}
                                                        <div className="mt-0.5">
                                                            {siklus.trafficStateId == null ? (
                                                                <span className="text-[10px] text-text-muted">—</span>
                                                            ) : kondisiSama ? (
                                                                <span
                                                                    className="text-[10px] text-signal-amber"
                                                                    title="Kondisi lalu lintas identik dengan siklus sebelumnya — sistem mengevaluasi ulang kondisi yang sama."
                                                                >
                                                                    kondisi sama
                                                                </span>
                                                            ) : (
                                                                <span className="text-[10px] text-signal-green">
                                                                    kondisi baru
                                                                </span>
                                                            )}
                                                        </div>
                                                    </td>
                                                    <td className="whitespace-nowrap px-5 py-3 text-xs text-text-secondary">
                                                        <div className="flex items-center gap-1.5">
                                                            <TrafficCone size={12} className="text-text-muted" />
                                                            Simpang 4 Pingit
                                                        </div>
                                                    </td>
                                                    <td className="px-5 py-3">
                                                        <span
                                                            className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${kepadatan.warna}`}
                                                        >
                                                            {kepadatan.label}
                                                        </span>
                                                    </td>
                                                    <td className="px-5 py-3">
                                                        <div className="flex flex-wrap gap-2">
                                                            {urutkanFase(siklus.phases).map((fase) => (
                                                                <span
                                                                    key={fase.approach}
                                                                    className="rounded-md bg-surface-2 px-2 py-0.5 text-[11px]"
                                                                >
                                                                    {labelLengan(fase.approach)}{" "}
                                                                    <span className="font-mono font-medium">
                                                                        {fase.greenSeconds}s
                                                                    </span>
                                                                </span>
                                                            ))}
                                                        </div>
                                                    </td>
                                                    <td className="whitespace-nowrap px-5 py-3">
                                                        {dampakDelay && dampakDelay.improved !== null ? (
                                                            <span
                                                                className={`flex items-center gap-1 text-xs font-medium ${
                                                                    dampakDelay.improved
                                                                        ? "text-signal-green"
                                                                        : "text-signal-red"
                                                                }`}
                                                            >
                                                                {dampakDelay.improved ? (
                                                                    <TrendingDown size={13} />
                                                                ) : (
                                                                    <TrendingUp size={13} />
                                                                )}
                                                                Delay {dampakDelay.changePercent}%
                                                            </span>
                                                        ) : siklus.beforeAfter ? (
                                                            <span className="flex items-center gap-1 text-xs text-text-muted">
                                                                <Minus size={12} />
                                                                Tetap (baseline menang)
                                                            </span>
                                                        ) : (
                                                            <span className="text-xs text-text-muted">—</span>
                                                        )}
                                                    </td>
                                                    <td className="px-5 py-3">
                                                        {siklus.winner?.los ? (
                                                            <span
                                                                className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${warnaLos(
                                                                    siklus.winner.los
                                                                )}`}
                                                            >
                                                                {siklus.winner.los}
                                                            </span>
                                                        ) : (
                                                            <span className="text-xs text-text-muted">—</span>
                                                        )}
                                                    </td>
                                                    <td className="px-5 py-3">
                                                        <span className="rounded-md bg-surface-2 px-2 py-0.5 text-[11px] text-text-secondary">
                                                            {siklus.source ?? "—"}
                                                        </span>
                                                    </td>
                                                    <td className="px-5 py-3">
                                                        {berubah ? (
                                                            <span className="rounded-full bg-accent-blue/15 px-2 py-0.5 text-[11px] text-accent-blue">
                                                                berubah
                                                            </span>
                                                        ) : (
                                                            <span className="text-[11px] text-text-muted">tetap</span>
                                                        )}
                                                    </td>
                                                    <td className="whitespace-nowrap px-5 py-3">
                                                        <button
                                                            type="button"
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                setDipilih(siklus);
                                                            }}
                                                            className="flex items-center gap-1 rounded-lg border border-border px-2.5 py-1 text-[11px] transition hover:bg-surface-2"
                                                        >
                                                            <Eye size={12} />
                                                            Lihat
                                                        </button>
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        )}

                        {/* PAGINASI */}
                        {data && data.items.length > 0 && (
                            <div className="flex items-center justify-between border-t border-border px-5 py-3">
                                <p className="text-xs text-text-muted">
                                    Halaman {data.page} dari {totalHalaman}
                                </p>
                                <div className="flex gap-2">
                                    <button
                                        type="button"
                                        disabled={halaman <= 1}
                                        onClick={() => setHalaman((n) => Math.max(1, n - 1))}
                                        className="flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-xs transition hover:bg-surface-2 disabled:opacity-40"
                                    >
                                        <ChevronLeft size={14} />
                                        Sebelumnya
                                    </button>
                                    <button
                                        type="button"
                                        disabled={halaman >= totalHalaman}
                                        onClick={() => setHalaman((n) => n + 1)}
                                        className="flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-xs transition hover:bg-surface-2 disabled:opacity-40"
                                    >
                                        Berikutnya
                                        <ChevronRight size={14} />
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </main>

            {/* DETAIL */}
            {dipilih && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
                    onClick={() => setDipilih(null)}
                >
                    <div
                        className="max-h-[85vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-border bg-surface p-6 shadow-xl"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="mb-5 flex items-start justify-between">
                            <div>
                                <h2 className="text-sm font-semibold">Detail Keputusan</h2>
                                <p className="mt-0.5 font-mono text-xs text-text-muted">
                                    {formatWaktu(dipilih.timestamp)} · {dipilih.source ?? "—"}
                                </p>
                            </div>
                            <button
                                type="button"
                                onClick={() => setDipilih(null)}
                                className="flex h-9 w-9 items-center justify-center rounded-lg text-text-muted transition hover:bg-surface-2 hover:text-text"
                            >
                                <X className="h-5 w-5" />
                            </button>
                        </div>

                        {/* KONDISI PEMICU */}
                        <div className="mb-5">
                            <div className="mb-2 flex items-center gap-2">
                                <Clock3 size={15} className="text-text-secondary" />
                                <h3 className="text-xs font-medium">
                                    Kondisi Lalu Lintas Saat Itu
                                </h3>
                            </div>
                            {dipilih.trafficConditions.length === 0 ? (
                                <p className="text-xs text-text-muted">
                                    Tidak ada data kondisi untuk keputusan ini.
                                </p>
                            ) : (
                                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                                    {dipilih.trafficConditions.map((kondisi) => (
                                        <div
                                            key={kondisi.approach}
                                            className="rounded-lg border border-border bg-surface-2 p-3"
                                        >
                                            <p className="text-[11px] text-text-muted">
                                                {labelLengan(kondisi.approach)}
                                            </p>
                                            <p className="mt-1 font-mono text-xs">
                                                {kondisi.volume ?? "—"} kendaraan
                                            </p>
                                            <p className="text-[10px] text-text-muted">
                                                antrean {kondisi.queueLengthVeh ?? "—"} kend ·{" "}
                                                {kondisi.queueLengthMEst ?? "—"}m
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                        {/* TRAFFIC FORECAST */}
                        <div className="mb-5">
                            <ForecastChart data={forecastData} />
                        </div>

                        {/* KANDIDAT */}
                        <div className="mb-5">
                            <div className="mb-2 flex items-center gap-2">
                                <Layers size={15} className="text-text-secondary" />
                                <h3 className="text-xs font-medium">Kandidat yang Diuji di SUMO</h3>
                            </div>
                            {dipilih.candidates.length === 0 ? (
                                <p className="text-xs text-text-muted">
                                    Tidak ada data kandidat — keputusan ini tidak melalui
                                    Scenario Generator.
                                </p>
                            ) : (
                                <div className="overflow-hidden rounded-lg border border-border">
                                    <table className="w-full text-left text-xs">
                                        <thead className="bg-surface-2 text-text-muted">
                                            <tr>
                                                <th className="px-3 py-2 font-medium">Kandidat</th>
                                                <th className="px-3 py-2 font-medium">Delay</th>
                                                <th className="px-3 py-2 font-medium">Antrean</th>
                                                <th className="px-3 py-2 font-medium">Throughput</th>
                                                <th className="px-3 py-2 font-medium">LOS</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {dipilih.candidates.map((kandidat) => (
                                                <tr
                                                    key={kandidat.candidateId}
                                                    className={`border-t border-border ${
                                                        kandidat.isWinner ? "bg-signal-green/5" : ""
                                                    }`}
                                                >
                                                    <td className="px-3 py-2">
                                                        {kandidat.candidateId}
                                                        {kandidat.isWinner && (
                                                            <span className="ml-2 text-signal-green">
                                                                ✓ terpilih
                                                            </span>
                                                        )}
                                                    </td>
                                                    <td className="px-3 py-2 font-mono">
                                                        {kandidat.avgDelaySeconds ?? "—"}s
                                                    </td>
                                                    <td className="px-3 py-2 font-mono">
                                                        {kandidat.avgQueueLengthM ?? "—"}m
                                                    </td>
                                                    <td className="px-3 py-2 font-mono">
                                                        {kandidat.throughputVeh ?? "—"}
                                                    </td>
                                                    <td className="px-3 py-2">{kandidat.los ?? "—"}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>

                        {/* DAMPAK: BEFORE / AFTER */}
                        {/*
                            Panel ini yang paling langsung menjawab "apa gunanya
                            program ini" -- baseline (before) dan pemenang (after)
                            SAMA-SAMA disimulasikan sungguhan di SUMO, bukan
                            diperkirakan, jadi selisihnya angka yang bisa
                            dipertanggungjawabkan.
                        */}
                        {dipilih.beforeAfter && (
                            <div className="mb-5">
                                <div className="mb-2 flex items-center gap-2">
                                    <TrendingUp size={15} className="text-text-secondary" />
                                    <h3 className="text-xs font-medium">
                                        Dampak: Baseline vs Rekomendasi
                                    </h3>
                                </div>

                                {!dipilih.beforeAfter.changed && (
                                    <p className="mb-3 rounded-lg border border-border bg-surface-2 px-3 py-2 text-[11px] text-text-muted">
                                        Sistem menyimpulkan pengaturan{" "}
                                        <strong>baseline</strong> sudah paling baik untuk
                                        kondisi ini — bukan kegagalan sistem, ini keputusan
                                        yang sah.
                                    </p>
                                )}

                                <div className="overflow-hidden rounded-lg border border-border">
                                    <table className="w-full text-left text-xs">
                                        <thead className="bg-surface-2 text-text-muted">
                                            <tr>
                                                <th className="px-3 py-2 font-medium">Metrik</th>
                                                <th className="px-3 py-2 font-medium">
                                                    Before ({dipilih.beforeAfter.baselineCandidateId})
                                                </th>
                                                <th className="px-3 py-2 font-medium">
                                                    After ({dipilih.beforeAfter.winnerCandidateId})
                                                </th>
                                                <th className="px-3 py-2 font-medium">Change</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {dipilih.beforeAfter.metrics.map((metrik) => (
                                                <tr
                                                    key={metrik.metric}
                                                    className="border-t border-border"
                                                >
                                                    <td className="px-3 py-2">{metrik.label}</td>
                                                    <td className="px-3 py-2 font-mono text-text-muted">
                                                        {metrik.before}
                                                        {metrik.unit}
                                                    </td>
                                                    <td className="px-3 py-2 font-mono">
                                                        {metrik.after}
                                                        {metrik.unit}
                                                    </td>
                                                    <td className="px-3 py-2">
                                                        {metrik.improved === null ? (
                                                            <span className="flex items-center gap-1 text-text-muted">
                                                                <Minus size={12} />
                                                                tetap
                                                            </span>
                                                        ) : (
                                                            <span
                                                                className={`flex items-center gap-1 font-medium ${
                                                                    metrik.improved
                                                                        ? "text-signal-green"
                                                                        : "text-signal-red"
                                                                }`}
                                                            >
                                                                {metrik.improved ? (
                                                                    <TrendingDown size={12} />
                                                                ) : (
                                                                    <TrendingUp size={12} />
                                                                )}
                                                                {metrik.changePercent != null &&
                                                                    `${metrik.changePercent > 0 ? "+" : ""}${metrik.changePercent}%`}
                                                            </span>
                                                        )}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        )}

                        {/* DURASI DIREKOMENDASIKAN */}
                        <div>
                            <div className="mb-2 flex items-center gap-2">
                                <TrafficCone size={15} className="text-text-secondary" />
                                <h3 className="text-xs font-medium">Durasi Hijau Direkomendasikan</h3>
                            </div>
                            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                                {urutkanFase(dipilih.phases).map((fase) => (
                                    <div
                                        key={fase.approach}
                                        className="rounded-lg border border-border bg-surface-2 p-3"
                                    >
                                        <p className="text-[11px] text-text-muted">
                                            {labelLengan(fase.approach)}
                                        </p>
                                        <p className="mt-1 font-mono text-sm font-semibold">
                                            {fase.greenSeconds}s
                                        </p>
                                        {fase.currentGreenSeconds != null && (
                                            <p className="mt-0.5 text-[10px] text-text-muted">
                                                eksisting {fase.currentGreenSeconds}s
                                            </p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>

                    </div>
                </div>
            )}
        </div>
    );
}
