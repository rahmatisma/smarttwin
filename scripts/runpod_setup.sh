#!/usr/bin/env bash
#
# Setup pertama kali SmartTwin di pod RunPod (GPU, Ubuntu 24.04, Python 3.12).
#
# Menyiapkan SELURUH sistem untuk dijalankan di pod -- backend + SUMO +
# decision engine + CV realtime. Training PPO TIDAK dijalankan di sini
# (tetap di PC), tapi environment-nya ikut terpasang supaya sewaktu-waktu
# bisa.
#
# Semua yang penting ditaruh di /workspace (network volume persisten).
# Container disk terhapus tiap pod di-stop, jadi TIDAK ADA yang disimpan di
# /root atau /.
#
# Aman dijalankan ulang: langkah yang sudah selesai akan dilewati.
#
# PEMAKAIAN (di web terminal atau SSH pod):
#     cd /workspace
#     git clone https://github.com/rahmatisma/smarttwin.git
#     bash smarttwin/scripts/runpod_setup.sh
#
# Setelah selesai, lihat pesan penutup untuk langkah manual (scp data + .env).

set -euo pipefail

# ---------------------------------------------------------------------------
# Konfigurasi
# ---------------------------------------------------------------------------
REPO_DIR="/workspace/smarttwin"
VENV_ROOT="${REPO_DIR}/.venv"           # CPU: backend, SUMO, decision engine
VENV_CV="/workspace/venv-cuda"          # CUDA: YOLO + ByteTrack
PYTHON_BIN="python3"                    # Ubuntu 24.04 -> 3.12

# Channel CUDA untuk torch di venv CV. Driver pod = CUDA 13.0 (cek nvidia-smi).
# Kalau instalasi cu130 gagal (wheel belum ada untuk versi torch tertentu),
# ganti ke cu128 -- keduanya jalan di Blackwell lewat forward-compat.
TORCH_CUDA_CHANNEL="cu130"
TORCH_CPU_CHANNEL="cpu"

YOLO_WEIGHT_URL="https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26s.pt"
YOLO_WEIGHT_SHA256="646f8bc3fe0a656803d95c294f7852321748cb29d13466a1af8862e2db384a1b"

# ---------------------------------------------------------------------------
# Util
# ---------------------------------------------------------------------------
log()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m!!  %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31mXX  %s\033[0m\n' "$*" >&2; exit 1; }

[ -d "$REPO_DIR" ] || die "Repo belum di-clone. Jalankan: cd /workspace && git clone https://github.com/rahmatisma/smarttwin.git"
cd "$REPO_DIR"

# ---------------------------------------------------------------------------
# 1. Paket sistem yang mungkin belum ada
# ---------------------------------------------------------------------------
log "Cek paket sistem (venv, ffmpeg, libGL untuk OpenCV, Xvfb untuk sumo-gui)"
MISSING_APT=()
"$PYTHON_BIN" -m venv --help >/dev/null 2>&1 || MISSING_APT+=("python3.12-venv")
command -v ffmpeg >/dev/null 2>&1 || MISSING_APT+=("ffmpeg")
# OpenCV headless butuh libGL + libglib walau tanpa GUI
ldconfig -p 2>/dev/null | grep -q libGL.so.1 || MISSING_APT+=("libgl1")
ldconfig -p 2>/dev/null | grep -q libglib-2.0 || MISSING_APT+=("libglib2.0-0")
# Xvfb + Mesa software rendering (llvmpipe) -- dipakai sumo-gui buat
# screenshot digital twin. Pod ini tidak punya display fisik ataupun setup
# GLX/EGL untuk GPU compute, jadi pakai virtual display + software
# rendering. CATATAN: llvmpipe jauh lebih lambat dari GPU asli -- screenshot
# butuh belasan detik, bukan 0,25 detik yang diasumsikan kode live-view.
# Fitur inti (rekomendasi sinyal) tidak kena karena itu jalan headless.
command -v Xvfb >/dev/null 2>&1 || MISSING_APT+=("xvfb")
dpkg -s libgl1-mesa-dri >/dev/null 2>&1 || MISSING_APT+=("libgl1-mesa-dri")
dpkg -s libglx-mesa0 >/dev/null 2>&1 || MISSING_APT+=("libglx-mesa0")
if [ "${#MISSING_APT[@]}" -gt 0 ]; then
    log "apt-get install: ${MISSING_APT[*]}"
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${MISSING_APT[@]}"
else
    echo "  semua sudah ada"
fi

# ---------------------------------------------------------------------------
# 1b. Perbaikan IPv4/IPv6 untuk TraCI
# ---------------------------------------------------------------------------
# BUG BESAR (ditemukan 2 September 2026): traci.start() di pustaka SUMO
# hardcode connect ke host "localhost". Di container Linux, getaddrinfo()
# default mengembalikan IPv6 (::1) lebih dulu daripada IPv4 (127.0.0.1) --
# tapi SUMO cuma listen di 0.0.0.0 (IPv4). Akibatnya SEMUA koneksi TraCI
# gagal/timeout, bukan cuma sumo-gui: headless sumo (dipakai PPO env,
# Scenario Generator) ikut terkena. /etc ada di container disk (bukan
# /workspace), jadi hilang tiap container dibuat ulang -- makanya masuk
# skrip setup, bukan cukup dijalankan sekali manual.
log "Paksa IPv4 diutamakan untuk resolusi 'localhost' (bug TraCI)"
if ! grep -q "precedence ::ffff:0:0/96" /etc/gai.conf 2>/dev/null; then
    echo "precedence ::ffff:0:0/96  100" >> /etc/gai.conf
    echo "  ditambahkan ke /etc/gai.conf"
else
    echo "  sudah ada"
fi

# ---------------------------------------------------------------------------
# 1c. Display virtual (Xvfb) untuk sumo-gui
# ---------------------------------------------------------------------------
log "Pastikan Xvfb jalan di :99"
if ! pgrep -x Xvfb >/dev/null 2>&1; then
    Xvfb :99 -screen 0 1280x720x24 -nolisten tcp &
    disown
    sleep 2
    echo "  Xvfb dimulai"
else
    echo "  sudah jalan"
fi

# ---------------------------------------------------------------------------
# 1d. Node.js -- persisten di /workspace (bukan sistem) supaya tidak hilang
#     tiap container dibuat ulang (mis. saat expose port diedit di RunPod)
# ---------------------------------------------------------------------------
NODE_VERSION="v24.13.0"
NODE_DIR="/workspace/node-runtime"
log "Pastikan Node.js ${NODE_VERSION} ada di ${NODE_DIR}"
if [ ! -x "${NODE_DIR}/bin/node" ]; then
    curl -fsSL -o /tmp/node.tar.xz \
        "https://nodejs.org/dist/${NODE_VERSION}/node-${NODE_VERSION}-linux-x64.tar.xz"
    mkdir -p "$NODE_DIR"
    # --no-same-owner: network volume (MooseFS) menolak chown ke uid/gid
    # asli dari tarball walau dijalankan sebagai root -- bukan bug, cuma
    # beda kebijakan filesystem network volume RunPod.
    tar --no-same-owner -xJf /tmp/node.tar.xz -C "$NODE_DIR" --strip-components=1
    rm /tmp/node.tar.xz
    echo "  terpasang: $("${NODE_DIR}/bin/node" --version)"
else
    echo "  sudah ada: $("${NODE_DIR}/bin/node" --version)"
fi

# ---------------------------------------------------------------------------
# 2. Venv root (CPU) -- backend + SUMO + decision engine
# ---------------------------------------------------------------------------
if [ ! -x "${VENV_ROOT}/bin/python" ]; then
    log "Buat venv root: ${VENV_ROOT}"
    "$PYTHON_BIN" -m venv "$VENV_ROOT"
else
    log "Venv root sudah ada, lewati pembuatan"
fi

# shellcheck disable=SC1091
source "${VENV_ROOT}/bin/activate"
pip install --upgrade pip -q

log "Install torch CPU (${TORCH_CPU_CHANNEL}) -- SEBELUM requirements supaya tidak menarik build CUDA"
pip install -q "torch==2.13.0" --index-url "https://download.pytorch.org/whl/${TORCH_CPU_CHANNEL}"

log "Install requirements.txt (fastapi, SUMO, SB3, gymnasium, dll.)"
pip install -q -r requirements.txt

# SUMO_HOME: wheel eclipse-sumo menaruh SUMO di site-packages/sumo
SUMO_HOME_DETECTED="$("${VENV_ROOT}/bin/python" - <<'PY'
import pathlib, sumo  # type: ignore
print(pathlib.Path(sumo.__file__).parent)
PY
)"
[ -d "$SUMO_HOME_DETECTED" ] || die "SUMO_HOME tidak terdeteksi setelah install eclipse-sumo"

# Suntik export ke activate script supaya `source .venv/bin/activate` cukup
# buat SEMUA env yang dibutuhkan: SUMO_HOME (traci/sumolib), Node.js
# (frontend), DISPLAY + PROJ_DATA/PROJ_LIB (sumo-gui lewat Xvfb -- lihat
# bagian 1b/1c di atas soal kenapa keduanya wajib).
if ! grep -q "SUMO_HOME" "${VENV_ROOT}/bin/activate"; then
    log "Tambah SUMO_HOME + Node PATH + DISPLAY/PROJ ke ${VENV_ROOT}/bin/activate"
    cat >> "${VENV_ROOT}/bin/activate" <<EOF

# --- ditambahkan runpod_setup.sh ---
export SUMO_HOME="${SUMO_HOME_DETECTED}"
export PATH="\$SUMO_HOME/bin:${NODE_DIR}/bin:\$PATH"
export DISPLAY=:99
export PROJ_DATA="\$SUMO_HOME/data/proj"
export PROJ_LIB="\$SUMO_HOME/data/proj"
EOF
fi
export SUMO_HOME="$SUMO_HOME_DETECTED"

deactivate

# ---------------------------------------------------------------------------
# 3. Venv CV (CUDA) -- YOLO26 + ByteTrack
# ---------------------------------------------------------------------------
if [ ! -x "${VENV_CV}/bin/python" ]; then
    log "Buat venv CV: ${VENV_CV}"
    "$PYTHON_BIN" -m venv "$VENV_CV"
else
    log "Venv CV sudah ada, lewati pembuatan"
fi

# shellcheck disable=SC1091
source "${VENV_CV}/bin/activate"
pip install --upgrade pip -q

log "Install torch CUDA (${TORCH_CUDA_CHANNEL}) -- SEBELUM ultralytics"
if ! pip install -q torch torchvision --index-url "https://download.pytorch.org/whl/${TORCH_CUDA_CHANNEL}"; then
    warn "Instalasi ${TORCH_CUDA_CHANNEL} gagal -- coba cu128"
    pip install -q torch torchvision --index-url "https://download.pytorch.org/whl/cu128"
fi

log "Install cv/requirements.txt (ultralytics, lap, imageio-ffmpeg, dll.)"
pip install -q -r cv/requirements.txt

CUDA_OK="$("${VENV_CV}/bin/python" -c 'import torch; print(torch.cuda.is_available())')"
[ "$CUDA_OK" = "True" ] || warn "torch.cuda.is_available() = ${CUDA_OK} -- YOLO akan fallback ke CPU. Cek channel CUDA."

deactivate

# ---------------------------------------------------------------------------
# 4. Bobot YOLO
# ---------------------------------------------------------------------------
mkdir -p cv/models
if [ ! -f cv/models/yolo26s.pt ]; then
    log "Unduh yolo26s.pt"
    curl -fL --retry 3 -o cv/models/yolo26s.pt "$YOLO_WEIGHT_URL"
fi
ACTUAL_SHA="$(sha256sum cv/models/yolo26s.pt | cut -d' ' -f1)"
if [ "$ACTUAL_SHA" != "$YOLO_WEIGHT_SHA256" ]; then
    warn "sha256 yolo26s.pt tidak cocok (dapat ${ACTUAL_SHA}). Hapus & unduh ulang kalau YOLO error."
else
    echo "  sha256 cocok"
fi

# ---------------------------------------------------------------------------
# 5. Struktur folder output (gitignored, tidak ikut clone)
# ---------------------------------------------------------------------------
log "Siapkan folder output"
mkdir -p cv/output simulation/outputs decision_engine/models/checkpoints backend/cache

# ---------------------------------------------------------------------------
# 6. Verifikasi
# ---------------------------------------------------------------------------
log "Verifikasi"
"${VENV_ROOT}/bin/python" - <<PY
import os
os.environ["SUMO_HOME"] = "${SUMO_HOME_DETECTED}"
import traci, sumolib, stable_baselines3, gymnasium, fastapi  # noqa
print("  root venv  : traci", traci.__version__, "| SB3", stable_baselines3.__version__, "| OK")
PY
"${VENV_CV}/bin/python" - <<'PY'
import torch, ultralytics  # noqa
print(f"  cv venv    : torch {torch.__version__} | cuda {torch.cuda.is_available()} | ultralytics {ultralytics.__version__}")
PY
"${SUMO_HOME_DETECTED}/bin/sumo" --version 2>/dev/null | head -1 | sed 's/^/  SUMO       : /' || warn "binary sumo tidak jalan"

# ---------------------------------------------------------------------------
# 7. Langkah manual yang tersisa
# ---------------------------------------------------------------------------
cat <<'EOF'

===========================================================================
SETUP SELESAI. Langkah manual yang tersisa (file gitignored, harus dikirim
dari PC/laptop pakai scp):

1. Data CV (untuk training PPO / replay):
     scp -P <port> cv/output/crossing_simpang.csv  root@<ip>:/workspace/smarttwin/cv/output/
     scp -P <port> cv/output/snapshot_zona.csv     root@<ip>:/workspace/smarttwin/cv/output/

2. File .env di /workspace/smarttwin/.env -- salin dari .env.example lalu isi:
     SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, HF_TOKEN
     CORS_ORIGINS  -> URL proxy dashboard RunPod (nanti)
   (SMARTTWIN_DECISION_ENGINE biarkan rule-based)

3. Checkpoint PPO (opsional, kalau mau engine PPO aktif):
     scp -P <port> decision_engine/models/smarttwin_ppo.zip root@<ip>:/workspace/smarttwin/decision_engine/models/

Menjalankan sistem: aktifkan venv root, lalu uvicorn --
     source /workspace/smarttwin/.venv/bin/activate
     cd /workspace/smarttwin/backend
     uvicorn app.main:app --host 0.0.0.0 --port 8000
===========================================================================
EOF
