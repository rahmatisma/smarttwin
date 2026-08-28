# Docker Compose — belum aktif, dan itu memang sengaja

Docker Compose statusnya "kalau sempat" dan boleh dilepas kalau waktu mepet — native run satu laptop tetap sah buat demo. Lihat `docs/STATUS-DAN-SISA-KERJA.md` bagian 5 (yang TIDAK dikerjakan).

Sampai saat itu, tiap modul jalan native (Python venv per folder + `npm run dev` buat frontend). Alasannya:

- Requirements tiap modul belum stabil. Kalau Dockerfile ditulis sekarang, begitu Melpi/Yuli nambah dependency yang mereka butuhin, Dockerfile-nya harus direvisi ulang berkali-kali.
- GPU passthrough justru nambah titik gagal buat modul CV. ultralytics/PyTorch butuh akses GPU biar deteksi real-time gak lemot. Di Windows, GPU passthrough ke Docker container butuh WSL2 backend + NVIDIA Container Toolkit dikonfigurasi bener — lapisan tambahan yang bisa jadi sumber masalah baru, bukan solusi, kalau belum familiar.
- `backend/` sendiri masih kosong. Percuma nyusun compose file kalau service yang mau di-compose belum ada.

## Pas waktunya tiba (Fase 4)

Checklist sebelum mulai nulis Dockerfile beneran:

- [ ] `backend/` sudah ada isinya dan `backend/requirements.txt` sudah dibuat
- [ ] `cv/requirements.txt` dan `simulation/requirements.txt` sudah final (bukan draft lagi)
- [ ] Cek dulu Melpi butuh GPU passthrough atau nggak — kalau ya, alokasikan waktu ekstra buat setup WSL2 + NVIDIA Container Toolkit, jangan diasumsikan otomatis jalan
- [ ] Docker Desktop terinstall di semua laptop tim yang bakal jalanin compose-nya

Catatan: PPO belum dikerjakan (nol kode RL) — lihat `docs/STATUS-DAN-SISA-KERJA.md` item P-1.
