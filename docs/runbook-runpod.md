# Runbook RunPod — Stop & Nyalakan Ulang Sistem SmartTwin

> 🔵 **Dokumen CARA KERJA (operasional).** Bukan pelacak status. Ditulis
> 2 September 2026 setelah sesi debugging pertama menjalankan sistem penuh
> (backend + SUMO-GUI + frontend + worker) di pod GPU RunPod.
>
> Rujukan terkait: [`sop-demo-end-to-end.md`](sop-demo-end-to-end.md) (urutan
> nyalakan untuk demo), [`rencana-cv-live-runpod.md`](rencana-cv-live-runpod.md)
> (rencana CV 4-kamera paralel — belum dikerjakan), `../CLAUDE.md` bagian
> "Single root venv" dan "SUMO / TraCI setup", `../scripts/runpod_setup.sh`.

---

## 1. Apa yang hilang saat "Stop Pod", apa yang aman

RunPod memisahkan **network volume** (persisten) dari **container disk**
(dihapus tiap pod dibuat ulang).

| Lokasi | Jenis | Saat Stop Pod |
|---|---|---|
| `/workspace` — repo, `.venv`, `/workspace/venv-cuda`, `.env`, `outputs/`, bobot YOLO, checkpoint | **network volume** (`mfs#…runpod.net`) | **aman, tidak hilang** |
| `/`, `/root`, `/etc`, `/tmp` | container disk (overlay) | **dihapus** |

**Yang hilang tapi otomatis dibangun ulang oleh `runpod_setup.sh`:**

- Paket apt: `xvfb`, `ffmpeg`, `libgl1`, `libglib2.0-0`, `libgl1-mesa-dri`,
  `libglx-mesa0`
- Patch `/etc/gai.conf` (paksa IPv4 untuk resolusi `localhost` — wajib untuk
  TraCI, lihat `runpod_setup.sh` bagian 1b)
- Proses Xvfb `:99`
- Node.js **tidak** hilang (sengaja dipasang di `/workspace/node-runtime`)

**Yang TIDAK dibangun ulang otomatis** (sudah ada di volume, tapi kalau belum
pernah dikirim ke pod ini harus di-`scp` manual — lihat pesan penutup
`runpod_setup.sh`):

- `.env` di `/workspace/smarttwin/.env`
- CSV CV di `cv/output/` (untuk training / replay)
- Checkpoint PPO `decision_engine/models/smarttwin_ppo.zip` (opsional)

> **Kesimpulan:** klik "Stop Pod" dengan tenang. Kerjaan di `/workspace` aman.
> Yang perlu dilakukan saat menyalakan lagi cuma **satu skrip + tiga terminal**.

---

## 2. Sebelum Stop Pod (opsional tapi disarankan)

1. **Commit + push perubahan kode** yang belum masuk git. Network volume jarang
   hilang, tapi git remote adalah cadangan sebenarnya.
   ```bash
   cd /workspace/smarttwin
   git status
   git add -A && git commit -m "..." && git push
   ```
2. Hentikan proses yang jalan (backend, worker, CV) dengan `Ctrl+C` — tidak
   wajib (Stop Pod mematikan semuanya), tapi bikin shutdown bersih.
3. Catat **Pod ID** dari URL proxy (lihat bagian 5). Kalau nanti pakai
   tombol **Start** pada pod yang sama, ID tidak berubah. Kalau bikin pod
   **baru**, ID berubah dan `frontend/.env.local` harus diperbarui.

---

## 3. Menyalakan ulang — langkah demi langkah

### 3.0 Start pod di dashboard RunPod

Pakai tombol **Start** pada pod `smarttwin` yang sama (bukan bikin baru), supaya
Pod ID / URL proxy tetap sama.

### 3.1 Bangun ulang environment container (1 skrip, ±1–2 menit)

Buka **web terminal** atau SSH ke pod, lalu:

```bash
cd /workspace
bash smarttwin/scripts/runpod_setup.sh
```

Skrip ini **idempoten** — venv, bobot YOLO, dan Node yang sudah ada akan
dilewati. Yang dikerjakan saat restart cuma: install apt, patch `gai.conf`,
nyalakan Xvfb `:99`.

Selesai kalau muncul blok `SETUP SELESAI`. Abaikan langkah "scp manual" di
pesan penutup **kalau** `.env` dan CSV sudah ada di volume (cek: `ls
/workspace/smarttwin/.env cv/output/*.csv`).

### 3.2 Verifikasi environment

```bash
cd /workspace/smarttwin
source .venv/bin/activate
echo "$DISPLAY"        # WAJIB ":99"
echo "$SUMO_HOME"      # WAJIB .../.venv/lib/python3.12/site-packages/sumo
pgrep -x Xvfb          # WAJIB ada PID
python -c "import sumolib; print(sumolib.checkBinary('sumo-gui'))"   # cek SUMO
```

`source .venv/bin/activate` **wajib tiap terminal baru** — dia yang meng-export
`SUMO_HOME`, `DISPLAY=:99`, `PROJ_DATA/PROJ_LIB`, dan PATH Node
(ditambahkan `runpod_setup.sh` ke `.venv/bin/activate`).

> Kalau `$DISPLAY` kosong padahal sudah `activate`: Xvfb belum jalan —
> ulangi 3.1, atau jalankan manual:
> `Xvfb :99 -screen 0 1280x720x24 -nolisten tcp & disown`
> (Sejak 2 Sep, backend juga auto-set `DISPLAY=:99` kalau menemukan Xvfb
> yang jalan — lihat `sumo_controller.py::_ensure_display_for_gui`.)

### 3.3 Terminal 1 — Backend (FastAPI + SUMO-GUI)

```bash
cd /workspace/smarttwin
source .venv/bin/activate
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- `--host 0.0.0.0` **wajib** supaya proxy RunPod bisa menjangkau.
- Import pertama lambat (torch dari network volume, ±30–60 detik) — tunggu
  sampai `Application startup complete`.
- SUMO-GUI **belum** start di sini. Ia start otomatis saat frontend membuka
  dashboard dan mengirim `POST /api/v1/simulation/run` (scenario "Traffic
  Realtime" → context `dashboard`, `gui:true`).

Verifikasi:
```bash
curl -s localhost:8000/api/v1/health          # {"status":"ok",...}
curl -s "localhost:8000/api/v1/simulation/state?context=dashboard" | head -c 200
```

### 3.4 Terminal 2 — Frontend (Next.js)

```bash
cd /workspace/smarttwin
source .venv/bin/activate      # untuk PATH Node
cd frontend
next dev
```

- Port 3000, bind `0.0.0.0` secara default (Next 16).
- API base dibaca dari `frontend/.env.local`:
  `NEXT_PUBLIC_API_URL=https://<POD_ID>-8000.proxy.runpod.net`.
  **Kalau Pod ID berubah** (pod baru), perbarui file ini lalu restart `next dev`.

### 3.5 Terminal 3 — Scenario worker (kotak 7–9)

```bash
cd /workspace/smarttwin
source .venv/bin/activate
cd simulation
python scenario_worker.py --replay --interval 60
```

- `--full-cycle` sudah default (uji 3 CyclePlan 4-lengan) — tidak perlu ditulis.
- `--replay` = putar ulang TrafficState historis tiap siklus. **Lepas flag ini
  kalau CV live sedang jalan** (biar pakai kondisi terbaru).
- **Butuh route file** `simulation/outputs/demo_*.rou.xml`. Kalau folder
  `outputs/` kosong (mis. volume baru), generate dulu — lihat bagian 6.
- Kalau worker mati > 120 detik, backend diam-diam kembali ke rule-based
  (kotak 7/8/9 hilang dari alur, **tanpa error**). Biarkan terminal ini hidup.

Smoke test dulu (opsional): `python scenario_worker.py --once --replay` →
harus berakhir `Cache diperbarui …` dan `exit: 0`.

### 3.6 (Opsional) Ingest CV / CV live

Sistem saat ini masih pakai **CSV + ingest manual** (rencana CV 4-kamera live
belum dikerjakan — lihat `rencana-cv-live-runpod.md`):

```bash
cd /workspace/smarttwin
source .venv/bin/activate
python run_ingest.py           # baca cv/output/*.csv -> Supabase (upsert, aman diulang)
```

CV detector (`cv/`) pakai venv CUDA terpisah `/workspace/venv-cuda`
(`SMARTTWIN_CV_PYTHON` di `.env`). Jalankan hanya kalau memang memproses
rekaman/stream baru.

### 3.7 Buka dashboard

```
https://<POD_ID>-3000.proxy.runpod.net/dashboard
```

Refresh sekali setelah backend + worker hidup. Yang harus terlihat: peta SUMO
dengan kendaraan bergerak, lampu lalu lintas berganti fase, panel rekomendasi
dengan `source = scenario-generator`.

---

## 4. Menjalankan proses agar tahan tutup terminal (tmux)

Web terminal RunPod putus kalau tab ditutup. Pakai `tmux` (sudah terpasang):

```bash
tmux new -s smarttwin           # buat sesi
# Ctrl+B lalu C  -> window baru       (backend / frontend / worker per window)
# Ctrl+B lalu D  -> detach (proses tetap jalan)
tmux attach -t smarttwin        # sambung lagi nanti
```

Alternatif cepat per proses: `nohup <perintah> > /workspace/smarttwin/<nama>.log 2>&1 &`

---

## 5. Pod ID & URL proxy

URL proxy RunPod berbentuk `https://<POD_ID>-<PORT>.proxy.runpod.net`.
Contoh sesi ini: Pod ID `nxgsvuizgxrzm8` → dashboard di
`https://nxgsvuizgxrzm8-3000.proxy.runpod.net`, backend di `…-8000…`.

| Aksi di RunPod | Pod ID | Yang perlu disesuaikan |
|---|---|---|
| **Stop** lalu **Start** pod yang sama | tetap | tidak ada |
| Bikin pod **baru** | **berubah** | `frontend/.env.local` → `NEXT_PUBLIC_API_URL`; expose port 3000 & 8000 di setting pod |

Port yang harus di-expose (HTTP) di konfigurasi pod: **3000** (frontend) dan
**8000** (backend). `CORS_ORIGINS=*` di `.env` sudah mengizinkan semua origin.

---

## 6. Regenerasi route file SUMO (kalau `simulation/outputs/` kosong)

`simulation/network/simpang4_pingit.sumocfg` menunjuk
`../outputs/demo_mobil.rou.xml`. File `outputs/` gitignored (scratch), jadi bisa
hilang di volume yang bersih. Generate ulang (dari `simulation/`, venv aktif):

```bash
mkdir -p outputs
python "$SUMO_HOME/tools/randomTrips.py" -n network/simpang4_pingit.net.xml.gz -r outputs/demo_motor.rou.xml -e 600 -p 1  --vehicle-class motorcycle --prefix m --validate
python "$SUMO_HOME/tools/randomTrips.py" -n network/simpang4_pingit.net.xml.gz -r outputs/demo_mobil.rou.xml -e 600 -p 4  --vehicle-class passenger  --prefix c --validate
python "$SUMO_HOME/tools/randomTrips.py" -n network/simpang4_pingit.net.xml.gz -r outputs/demo_truk.rou.xml  -e 600 -p 24 --vehicle-class truck      --prefix t --validate
python "$SUMO_HOME/tools/randomTrips.py" -n network/simpang4_pingit.net.xml.gz -r outputs/demo_bus.rou.xml   -e 600 -p 60 --vehicle-class bus        --prefix b --validate
rm -f trips.trips.xml     # sisa randomTrips, jangan sampai ikut ter-commit
```

(Detail parameter: `simulation/README.md` bagian 3.)

---

## 7. Troubleshooting — temuan sesi 2 September

### `TraCI server already finished` / `Could not connect in 1 tries` saat SUMO start

`sumo-gui` mati seketika karena tidak ada X display.

- **Penyebab:** backend dijalankan tanpa `source .venv/bin/activate` → `DISPLAY`
  kosong → `sumo-gui` exit dengan `FXApp::openDisplay: unable to open display
  :0.0`.
- **Beda dari retry normal:** pesan `Connection refused … Retrying` itu **wajar**
  (sumo-gui lambat boot di software-GL llvmpipe). Yang bahaya adalah
  `already finished` (proses mati).
- **Perbaikan:** `source .venv/bin/activate` sebelum `uvicorn`, pastikan
  `echo $DISPLAY` → `:99`. Pastikan `pgrep -x Xvfb` ada.
- Sejak 2 Sep, `sumo_controller.py::_ensure_display_for_gui()` mendeteksi Xvfb
  yang jalan dan set `DISPLAY` sendiri + warning; kalau Xvfb benar-benar tidak
  ada, ia melempar pesan jelas alih-alih traceback TraCI.
- Bersihkan zombie: `pkill -f sumo-gui` sebelum restart backend.

### `RuntimeError: SUMO tidak ditemukan` (scenario_worker / run_tls_simulation)

`run_tls_simulation.py::findSumo()` dulu hanya cari `sumo.exe` + command
Windows `where`. Diperbaiki 2 Sep jadi lintas platform (`sumo` tanpa `.exe`,
`shutil.which`). Pastikan repo sudah di-`git pull` versi terbaru dan
`SUMO_HOME` ter-export (`source .venv/bin/activate`).

### `route file '…/outputs/demo_mobil.rou.xml' is not accessible`

`outputs/` kosong. Lihat bagian 6.

### Backend gagal start / port 8000 dipakai

```bash
pgrep -af "uvicorn app.main"        # cari instance lama
kill <PID>                          # atau: pkill -f "uvicorn app.main"
ss -tlnp | grep :8000               # pastikan sudah kosong
```

Juga cek nilai boolean `DEBUG` di `.env` (`true`/`false`, bukan kosong).

### Frontend tampil tapi data kosong / CORS error

- Pod ID di `frontend/.env.local` tidak cocok dengan URL yang dibuka →
  perbarui, restart `next dev`.
- Backend belum hidup atau belum selesai import torch → tunggu
  `Application startup complete`.

### `pytest` di `backend/` melaporkan 1 failure

Checkpoint PPO `decision_engine/models/smarttwin_ppo.zip` tidak ada di repo
(`.gitignore` `*.zip`). Ini **ekspektasi** — PPO fallback ke rule-based dan
demo tidak terpengaruh. Commit dengan `git add -f` kalau memang perlu.

### `.env` — catatan

`HF_REPO_ID` harus `rahmatisma/smarttwin-cctv` (sempat tergabung dengan baris
`SMARTTWIN_CV_PYTHON` karena kurang newline — diperbaiki 2 Sep).

---

## 8. Urutan singkat (cheat sheet)

```bash
# 0. RunPod: Start pod smarttwin
# 1. bangun container
cd /workspace && bash smarttwin/scripts/runpod_setup.sh

# 2. tiap terminal:
cd /workspace/smarttwin && source .venv/bin/activate

# T1 backend
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000

# T2 frontend
cd frontend && next dev

# T3 worker  (generate outputs/demo_*.rou.xml dulu kalau kosong — bagian 6)
cd simulation && python scenario_worker.py --replay --interval 60

# 3. buka  https://<POD_ID>-3000.proxy.runpod.net/dashboard
```
