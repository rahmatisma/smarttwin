"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { approachLabelId } from "@/lib/dataMode";

const API = process.env.NEXT_PUBLIC_REPLAY_DEMO_API_URL ?? "http://127.0.0.1:8001";
const ARMS = ["north", "east", "south", "west"] as const;
type Arm = typeof ARMS[number];
type Approach = {
  approach: Arm; mode: "live" | "replay"; ageSeconds: number;
  dataTimestamp: string | null; offlineSince: string | null;
  liveCount: number; replayCount: number; targetCount: number;
};
type State = { running: boolean; approaches: Approach[]; simulationTimeSeconds?: number; lastError?: string | null; triggeredCount?: number; recordingStart?: string; recordingEnd?: string; recordingPosition?: string; recordingEnded?: boolean };
const formatTime = (value: string) => new Date(value).toLocaleString("id-ID", {
  timeZone: "Asia/Jakarta", day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit",
}) + " WIB";

export default function ReplayDemoPage() {
  const [state, setState] = useState<State>({ running: false, approaches: [] });
  const [age, setAge] = useState(300);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState<boolean | null>(null);
  const [frameError, setFrameError] = useState(false);
  const [frameVersion, setFrameVersion] = useState(0);
  const mutation = useRef(false);
  const requestVersion = useRef(0);

  useEffect(() => {
    let cancelled = false;
    let timer: number;
    const poll = async () => {
      try {
        if (!mutation.current) {
          const version = requestVersion.current;
          const response = await fetch(`${API}/state`, { cache: "no-store", signal: AbortSignal.timeout(5000) });
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const next: State = await response.json();
          if (!cancelled && !mutation.current && version === requestVersion.current) {
            setState(next); setConnected(true);
            const historical = next.approaches.find((arm) => arm.mode === "replay");
            if (historical) setAge(historical.ageSeconds);
          }
        }
      } catch {
        if (!cancelled) setConnected(false);
      } finally {
        if (!cancelled) timer = window.setTimeout(poll, 750);
      }
    };
    void poll();
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, []);

  useEffect(() => {
    if (!state.running || !connected) return;
    const timer = window.setInterval(() => setFrameVersion((value) => value + 1), 350);
    return () => window.clearInterval(timer);
  }, [state.running, connected]);

  const send = useCallback(async (path: string, payload?: object) => {
    if (mutation.current) return;
    mutation.current = true;
    requestVersion.current += 1;
    setBusy(true); setError(null);
    try {
      const { supabase } = await import("@/lib/supabaseClient");
      const { data } = await supabase.auth.getSession();
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (data.session?.access_token) headers.Authorization = `Bearer ${data.session.access_token}`;
      const response = await fetch(`${API}/${path}`, {
        method: "POST", headers, body: payload ? JSON.stringify(payload) : undefined,
        signal: AbortSignal.timeout(60000),
      });
      const next = await response.json();
      if (!response.ok) throw new Error(typeof next.detail === "string" ? next.detail : `Gagal memperbarui SUMO (${response.status}).`);
      setState(next); setConnected(true);
      if (path === "sources") setNotice(next.triggeredCount > 0
        ? `${next.triggeredCount} kendaraan historis dimasukkan ke SUMO. Kendaraan baru berwarna putih; tunggu hingga masuk area kamera.`
        : "Sumber diperbarui. Jika snapshot historis berisi 0 kendaraan, tidak ada kendaraan putih yang dibuat pada snapshot itu.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "SUMO demo tidak dapat dihubungi.");
    } finally { mutation.current = false; setBusy(false); }
  }, []);

  const offline = state.approaches.filter((arm) => arm.mode === "replay").map((arm) => arm.approach);
  const replayCount = state.approaches.reduce((sum, arm) => sum + arm.replayCount, 0);
  const toggle = (arm: Arm) => void send("sources", {
    offline: offline.includes(arm) ? offline.filter((item) => item !== arm) : [...offline, arm], ageSeconds: age,
  });

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-5 py-8 text-text">
      <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-accent">Uji CCTV terputus · SUMO asli</p>
          <h1 className="mt-2 text-2xl font-bold">Simulasi tetap jalan, sumber data tetap jelas</h1>
          <p className="mt-2 max-w-3xl text-sm text-text-secondary">Frame SUMO memakai CSV hasil deteksi YOLO yang tersedia. Kuning mengikuti posisi pemutaran aktif; putih berasal dari data sebelum CCTV diputus. Kamera putus dipicu manual untuk pengujian.</p>
        </div>
        <Link href="/dashboard" className="text-sm text-accent">Kembali ke Dashboard</Link>
      </header>
      {connected === false && <div role="alert" className="mb-4 rounded-lg border border-signal-amber/50 bg-signal-amber/10 p-3 text-sm text-signal-amber">
        Pengendali demo belum tersambung. Jalankan server demo dari root proyek: <code className="mt-1 block break-all">python -m uvicorn app.replay_demo:app --app-dir backend --host 127.0.0.1 --port 8001</code>
        {state.running && <p className="mt-1">Frame dan status terakhir tidak dapat dianggap terbaru sampai koneksi pulih.</p>}
      </div>}
      {error && <p role="alert" className="mb-4 rounded-lg border border-signal-red p-3 text-sm text-signal-red">{error}</p>}
      {notice && <p role="status" className="mb-4 rounded-lg border border-border p-3 text-sm">{notice}</p>}
      {state.recordingPosition && <p className="mb-4 text-sm text-text-secondary">Posisi rekaman: {formatTime(state.recordingPosition)}. Data tersedia: {state.recordingStart && formatTime(state.recordingStart)} — {state.recordingEnd && formatTime(state.recordingEnd)}. {state.recordingEnded && "Rekaman selesai: pasokan bertahan pada snapshot terakhir, bukan data langsung terbaru."}</p>}
      <div className="grid items-start gap-5 lg:grid-cols-[270px_1fr]">
        <aside className="space-y-4">
          <section className="rounded-xl border border-border bg-surface p-4">
            <h2 className="font-semibold">Kontrol pengujian</h2>
            <p className="mt-2 text-xs text-text-secondary">{state.running ? `SUMO berjalan · ${(state.simulationTimeSeconds ?? 0).toFixed(0)} detik` : "SUMO demo belum berjalan"}</p>
            <button type="button" onClick={() => void send(state.running ? "stop" : "start")} disabled={busy || !connected} className="mt-3 w-full rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-bg disabled:opacity-40">
              {busy ? "Memperbarui SUMO…" : state.running ? "Hentikan demo" : "Nyalakan SUMO demo"}
            </button>
            <label htmlFor="history-age" className="mt-5 block text-xs text-text-secondary">Sumber pengganti untuk CCTV putus</label>
            <select id="history-age" value={age} disabled={busy || !connected} onChange={(event) => {
              const next = Number(event.target.value); setAge(next);
              if (state.running && offline.length) void send("sources", { offline, ageSeconds: next });
            }} className="mt-2 w-full rounded-lg border border-border bg-bg p-2 text-sm">
              <option value={60}>1 menit terakhir sebelum putus</option>
              <option value={300}>5 menit sebelumnya</option>
              <option value={900}>15 menit sebelumnya</option>
            </select>
            <button type="button" disabled={busy || !connected || !state.running}
              onClick={() => void send("sources", { offline: Array.from(new Set([...offline, "east"])), ageSeconds: age, trigger: true })}
              className="mt-3 w-full rounded-lg border border-yellow-400 bg-yellow-400/10 px-3 py-3 text-sm font-semibold disabled:opacity-40">
              Trigger Timur: putus + masukkan history putih
            </button>
            <button type="button" disabled={busy || !connected || !state.running}
              onClick={() => void send("sources", { offline: Array.from(new Set([...offline, "east", "south"])), ageSeconds: age, trigger: true })}
              className="mt-2 w-full rounded-lg border border-border px-3 py-2 text-xs disabled:opacity-40">
              Trigger 2 CCTV: Timur + Selatan
            </button>
            <div className="mt-4 grid grid-cols-2 gap-2">
              {ARMS.map((arm) => <button key={arm} type="button" aria-pressed={offline.includes(arm)} onClick={() => toggle(arm)} disabled={busy || !state.running || !connected}
                className={`rounded-lg border p-3 text-left text-xs disabled:opacity-40 ${offline.includes(arm) ? "border-signal-amber bg-signal-amber/10" : "border-border"}`}>
                <strong className="block text-sm">{approachLabelId(arm)}</strong>
                <span className="mt-1 block">{offline.includes(arm) ? "CCTV putus" : "CCTV aktif (uji)"}</span>
                <span className="mt-1 block text-text-muted">{offline.includes(arm) ? "Klik untuk pulihkan" : "Klik untuk putuskan"}</span>
              </button>)}
            </div>
            <button type="button" disabled={busy || !connected || !state.running || !offline.length} onClick={() => void send("sources", { offline: [], ageSeconds: age })} className="mt-3 text-xs text-accent disabled:opacity-40">Pulihkan semua CCTV</button>
          </section>
          <section className="rounded-xl border border-border bg-surface p-4 text-xs leading-relaxed">
            <h2 className="mb-3 text-sm font-semibold">Warna mengikuti sumber kendaraan</h2>
            <p><span className="mr-2 inline-block h-3 w-4 rounded-sm bg-yellow-400" /> Kuning: hasil YOLO pada posisi aktif</p>
            <p className="mt-2"><span className="mr-2 inline-block h-3 w-4 rounded-sm border border-slate-500 bg-white" /> Putih: hasil YOLO sebelum putus</p>
            <p className="mt-3 text-text-secondary">Kendaraan yang sudah ada saat CCTV putus tetap berwarna asal. Setelah CCTV pulih, kendaraan putih tetap putih sampai keluar simpang.</p>
          </section>
        </aside>
        <section className="min-w-0 rounded-xl border border-border bg-surface p-4">
          <div className="mb-3 flex flex-wrap justify-between gap-2"><h2 className="font-semibold">Digital Twin · frame SUMO</h2><span className="text-xs text-text-secondary">DATA UJI · {replayCount} kendaraan historis</span></div>
          <div role="status" className={`mb-3 rounded-lg border p-3 text-sm ${offline.length ? "border-signal-amber/50 bg-signal-amber/10 text-signal-amber" : "border-border text-text-secondary"}`}>
            {offline.length ? `CCTV ${offline.map(approachLabelId).join(", ")} putus. Pasokan pengganti tetap berjalan; kendaraan baru dari data lama berwarna putih.` : replayCount ? "CCTV telah pulih. Kendaraan putih yang masih berjalan tetap membawa penanda data historis." : "Nyalakan demo, lalu putuskan CCTV Timur atau dua lengan sekaligus untuk menguji pasokan pengganti."}
          </div>
          <div className="relative aspect-video overflow-hidden rounded-lg bg-black">
            {state.running ? <>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`${API}/frame?v=${frameVersion}`} alt="Frame asli SUMO Simpang Pingit; kendaraan putih berasal dari data historis uji" className="absolute inset-0 h-full w-full object-contain" onLoad={() => setFrameError(false)} onError={() => setFrameError(true)} />
              {(frameError || !connected) && <p className="absolute inset-x-2 bottom-2 rounded bg-black/85 p-2 text-xs text-white">{connected ? "Menunggu frame SUMO berikutnya…" : "Koneksi terputus · frame terakhir"}</p>}
            </> : <div className="absolute inset-0 flex items-center justify-center px-4 text-center text-sm text-white/70">Tekan “Nyalakan SUMO demo” untuk menampilkan kendaraan di empat lengan.</div>}
          </div>
          {state.lastError && <p role="alert" className="mt-2 text-sm text-signal-red">{state.lastError}</p>}
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {ARMS.map((arm) => {
              const item = state.approaches.find((value) => value.approach === arm);
              const stale = item?.mode === "replay";
              return <div key={arm} className={`rounded-lg border p-3 text-xs ${stale ? "border-signal-amber bg-signal-amber/5" : "border-border"}`}>
                <div className="flex flex-wrap justify-between gap-1"><strong className="text-sm">{approachLabelId(arm)}</strong><span className={stale ? "text-signal-amber" : "text-text-secondary"}>{!state.running ? "Belum berjalan" : stale ? "CCTV PUTUS · DATA LAMA" : "CCTV AKTIF · DATA UJI"}</span></div>
                {item && <>
                  <p className="mt-2 text-text-secondary">Waktu sumber: {item.dataTimestamp ? formatTime(item.dataTimestamp) : "Tidak ada riwayat sebelum putus; menunggu sumber pengganti"}</p>
                  {stale && <p className="mt-1 text-signal-amber">Memutar jendela {item.ageSeconds / 60} menit sebelum putus yang tersedia</p>}
                  {item.offlineSince && <p className="mt-1 text-text-muted">CCTV putus sejak: {formatTime(item.offlineSince)}</p>}
                  <p className="mt-2"><span className="text-yellow-400">{item.liveCount} posisi aktif (kuning)</span> · {item.replayCount} historis (putih)</p>
                  <p className="mt-1 text-text-muted">Target pasokan: {item.targetCount} kendaraan</p>
                </>}
              </div>;
            })}
          </div>
          <p className="mt-4 text-xs leading-relaxed text-text-muted">Demo mulai pada menit ke-5 rekaman agar ada riwayat untuk diuji. Saat CCTV putus, jendela data sebelum putus diputar berulang tanpa mengambil data sesudah putus. Tombol trigger memasukkan satu batch historis tambahan untuk memperjelas warna; jumlah sesaat dapat melebihi target snapshot. Jika belum ada riwayat, lengan ditandai tanpa data pengganti. Prediksi pola belum diterapkan.</p>
        </section>
      </div>
    </main>
  );
}
