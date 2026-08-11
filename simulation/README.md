# Cara Menjalankan Simulasi SmartTwin

Tutorial ini nyakup: setup environment, tes cepat, lihat simulasi secara
visual, script utilitas yang tersedia, dan troubleshooting error yang
paling sering ketemu. Semua command di sini dijalankan dari dalam folder
simulation/ (bukan root repo), dengan venv aktif.

## 1. Setup Environment (sekali saja per laptop)

```bash
cd simulation
python -m venv .venv
source .venv/Scripts/activate    # Windows Git Bash. Linux/Mac: .venv/bin/activate
pip install -r requirements.txt
```

Deteksi dan set SUMO_HOME (aman dari masalah path yang ada spasi):

```bash
export SUMO_HOME="$(python -c "import sumo, os; print(os.path.dirname(sumo.__file__.replace(chr(92), chr(47))))")"
```

**Penting — bukan cuma SUMO_HOME.** PATH juga harus menyertakan folder
`bin` di dalam SUMO_HOME (tempat `sumo.exe`, `netconvert.exe`, dll berada).
Tanpa ini, `traci.start()` dan pemanggilan binary SUMO lewat subprocess
akan gagal dengan `WinError 2` meski SUMO_HOME sendiri sudah benar:

```bash
export PATH="$SUMO_HOME/bin:$PATH"
```

Supaya otomatis ke-set tiap kali venv ini diaktifkan (tidak perlu diketik
ulang tiap sesi terminal baru):

```bash
printf "export SUMO_HOME='%s'\n" "$SUMO_HOME" >> .venv/Scripts/activate
printf 'export PATH="$SUMO_HOME/bin:$PATH"\n' >> .venv/Scripts/activate
deactivate && source .venv/Scripts/activate
```

Verifikasi instalasi:

```bash
netconvert --version
```

## 2. Tes Cepat — Verifikasi Environment Jalan

Sebelum coba network Pingit, cek dulu environment-nya sendiri sehat pakai
`test_traci.py` — ini pakai network "cross" bawaan SUMO (bukan network
proyek kita), jadi kalau ini gagal, masalahnya di instalasi, bukan di
network:

```bash
python test_traci.py
```

Harus keluar sampai baris terakhir: `OK — koneksi TraCI, step simulasi,
dan kontrol fase manual semua jalan`.

Baru setelah itu, tes network Pingit yang sebenarnya:

```bash
python run_intersection.py
```

## 3. Menjalankan Simulasi Visual (sumo-gui)

Network sendiri tidak otomatis punya kendaraan — perlu di-generate dulu.
Kita pakai 4 kelas kendaraan terpisah (motor/mobil/truk/bus) dengan
periode kemunculan berbeda, supaya proporsinya mirip data dummy di
dashboard (motor paling padat, bus paling jarang):

```bash
python "$SUMO_HOME/tools/randomTrips.py" -n network/simpang4_pingit.net.xml.gz -r outputs/demo_motor.rou.xml -e 600 -p 1 --vehicle-class motorcycle --prefix m --validate
python "$SUMO_HOME/tools/randomTrips.py" -n network/simpang4_pingit.net.xml.gz -r outputs/demo_mobil.rou.xml -e 600 -p 4 --vehicle-class passenger --prefix c --validate
python "$SUMO_HOME/tools/randomTrips.py" -n network/simpang4_pingit.net.xml.gz -r outputs/demo_truk.rou.xml -e 600 -p 24 --vehicle-class truck --prefix t --validate
python "$SUMO_HOME/tools/randomTrips.py" -n network/simpang4_pingit.net.xml.gz -r outputs/demo_bus.rou.xml -e 600 -p 60 --vehicle-class bus --prefix b --validate
```

**Kenapa ada `--prefix`:** tanpa ini, tiap file mulai ID kendaraan dari 0
secara independen — begitu 4 file dibuka bersamaan, ID-nya bentrok
(`Error: A vehicle with id 'X' already exists`). Prefix bikin tiap kelas
punya awalan huruf unik (`m0`, `c0`, `t0`, `b0`, ...).

Buka GUI-nya, keempat file dipisah koma:

```bash
sumo-gui -n network/simpang4_pingit.net.xml.gz -r outputs/demo_motor.rou.xml,outputs/demo_mobil.rou.xml,outputs/demo_truk.rou.xml,outputs/demo_bus.rou.xml
```

Klik ▶️ (play) di toolbar buat mulai. Bentuk kendaraan otomatis beda
sesuai `--vehicle-class` (motor, mobil, truk, bus tampil beda tanpa
setting tambahan). Kalau mau visual lebih detail (bukan cuma warna beda),
buka View Settings (ikon gerigi) → tab Vehicles → naikkan level detail.

Angka `-p` (periode kemunculan, dalam detik) bisa disesuaikan — makin
kecil angkanya, makin padat lalu lintasnya.

## 4. Script Utilitas yang Tersedia

| Script | Fungsi | Kapan dipakai |
|---|---|---|
| `test_traci.py` | Tes environment pakai network dummy bawaan SUMO | Diagnosa awal — isolasi masalah instalasi vs masalah network |
| `run_intersection.py` | Tes TraCI ke network Pingit asli | Verifikasi network project jalan |
| `check_tls_coverage.py` | Cek berapa persen koneksi fisik di sebuah junction yang benar-benar dikontrol lampu | Setelah edit TLS manual, pastikan tidak ada jalur yang "jalan liar" tanpa sinyal |
| `flatten_roundabout.py` | Deteksi otomatis dan ratakan roundabout artifak dari data OSM jadi 1 junction tunggal | Kalau network dari lokasi baru ternyata ke-detect sebagai roundabout padahal lokasi aslinya simpang bersinyal biasa |

## 5. Troubleshooting

**`IndexError: tuple index out of range` di `trafficlight.getIDList()[0]`**
Network belum punya lampu lalu lintas sama sekali. Cek dengan netedit
(mode Traffic Lights, klik junction pusat) atau paksa lewat command:
`netconvert --sumo-net-file <net> -o <net> --tls.set <ID_JUNCTION>`.

**`Warning: Building a tl-logic for junction 'X' twice is not possible`
lalu proses gagal (file tidak berubah)**
`--tls.set` tidak bisa dipakai untuk node yang sudah punya tl-logic.
Kalau mau gabungkan beberapa node yang sebagian sudah TLS individual jadi
satu TLS gabungan: keluarkan node yang sudah-TLS dari daftar `--tls.set`,
biarkan `--tls.join` yang menariknya ikut gabung. Kalau SEMUA node sudah
masing-masing TLS individual, `--tls.set` bisa dikosongkan sama sekali —
cukup `--tls.join` saja.

**Kendaraan macet/saling serobot di tengah simpang padahal TLS coverage
sudah 100%**
Kemungkinan network ke-detect sebagai roundabout oleh netconvert (umum
terjadi kalau OSM menandai pulau/median di tengah simpang sebagai
`junction=roundabout`, walau lokasi aslinya bukan bundaran). Cek dengan
`net.getRoundabouts()` di sumolib — kalau hasilnya tidak kosong, pakai
`flatten_roundabout.py`.

**`OSError: [WinError 4551] An Application Control policy has blocked
this file`**
Smart App Control Windows memblokir binary baru. Lihat
`docs/onboarding-notes.md` untuk cara mengatasinya.

**`OSError: [WinError 2]` saat `traci.start()` atau pemanggilan binary
SUMO, padahal SUMO_HOME sudah benar**
PATH belum menyertakan `$SUMO_HOME/bin`. Lihat bagian Setup Environment
di atas.
