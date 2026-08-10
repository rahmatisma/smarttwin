# Catatan Setup — biar gak keulang masalah yang sama

Ditulis Rahmat pas setup Minggu 1, biar Melpi & Yuli gak perlu re-debug masalah yang sama pas mulai setup mereka sendiri.

## Kalau kamu di Windows

**1. Hindari spasi di nama folder proyek kalau bisa.**
Path yang ada spasi (misal "KMIPN 2026") bikin beberapa tool lama nyangkut — termasuk pas nge-set env var yang isinya path Windows lewat Git Bash. Kalau kepaksa kerja di path yang ada spasinya, dan perlu nulis path itu ke env var (misal SUMO_HOME), convert ke forward-slash dulu sebelum di-export:

```python
path.replace(chr(92), '/')  # backslash jadi forward-slash
```

Backslash mentah + spasi itu kombinasi yang paling gampang bikin quoting di shell kacau — pernah ke-detect env var-nya kepotong gara-gara ini.

**2. Smart App Control kadang mem-blokir binary yang baru pertama kali dijalankan**
(hasil pip install, dll yang belum "dikenal" Windows). Errornya kira-kira: OSError: [WinError 4551] An Application Control policy has blocked this file. Kalau ketemu ini: Windows Security → App & browser control → Smart App Control settings → matikan.

PENTING: sebelum matiin, pastikan Windows Update kamu sudah paling baru dulu (Settings → Windows Update → Check for updates, install semua yang ada). Sejak update Windows sekitar April 2026, Smart App Control bisa dinyalakan ulang lewat Settings tanpa install ulang Windows — TAPI ini cuma berlaku kalau Windows kamu sudah dapat update tersebut. Kalau Windows kamu lama belum di-update, kemungkinan masih kena versi lama yang permanen begitu dimatikan.

Sumber resmi: support.microsoft.com — cari "Smart App Control Frequently Asked Questions" (Microsoft, diupdate Juni 2026).

**3. Cek nama package sebelum install.**
Beberapa nama umum (contoh: gh) punya package PyPI lain yang gak terkait sama sekali sama tool aslinya. pip show <nama> dulu buat mastiin isinya sesuai ekspektasi, apalagi kalau baru pertama kali install sesuatu yang namanya pendek/umum.

## Kebiasaan venv

- Satu venv per folder modul (cv/.venv, simulation/.venv, dst) — jangan share satu venv buat semua, biar dependency berat (torch/ultralytics) gak nabrak yang ringan (fastapi).
- deactivate begitu pindah kerjaan ke folder lain, biar package yang barusan di-install gak nyelip duluan di PATH depan tool sistem lain.
- Sebelum jalanin command yang nyentuh isi .venv/..., cek dulu pwd — pastiin posisi kamu emang di folder modul yang bener (root repo itu beda sama folder modul).

## SUMO_HOME (khusus buat yang megang bagian simulation/)

Deteksi otomatis, aman dari masalah path spasi:

```bash
export SUMO_HOME="$(python -c "import sumo, os; print(os.path.dirname(sumo.__file__.replace(chr(92), chr(47))))")"
```

Biar otomatis ke-set tiap kali venv diaktifin:

```bash
printf "export SUMO_HOME='%s'\n" "$SUMO_HOME" >> .venv/Scripts/activate   # Windows Git Bash
# atau .venv/bin/activate kalau di Linux/Mac
```

## Kalau butuh bantuan

Chat grup aja, atau tag Rahmat,S.Tr.Kom.
