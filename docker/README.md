# Docker Compose — belum aktif, dan itu memang sengaja

Sesuai SmartTwin_Roadmap_Pengembangan.md, Docker Compose dipakai serius mulai Minggu 4, dan bahkan di rencana kontingensi jadi item nomor 1 yang boleh disederhanain kalau waktu mepet ("demo boleh dari native run di satu laptop").

Sampai saat itu, tiap modul jalan native (Python venv per folder + npm run dev buat frontend). Alasannya:

- Requirements tiap modul belum stabil. Kalau Dockerfile ditulis sekarang, begitu Melpi/Yuli nambah dependency yang mereka butuhin, Dockerfile-nya harus direvisi ulang berkali-kali.
- GPU passthrough justru nambah titik gagal buat modul CV. ultralytics/PyTorch butuh akses GPU biar deteksi real-time gak lemot. Di Windows, GPU passthrough ke Docker container butuh WSL2 backend + NVIDIA Container Toolkit dikonfigurasi bener — lapisan tambahan yang bisa jadi sumber masalah baru, bukan solusi, kalau belum familiar.
- Bottleneck Yuli (akses server kampus) gak kesentuh Docker sama sekali — training-nya jalan di server itu sendiri, bukan di laptop lokal.

## Pas waktunya tiba (Minggu 4)

Checklist sebelum mulai nulis Dockerfile beneran:

- [ ] cv/requirements.txt, simulation/requirements.txt, simulation/requirements-rl.txt, dan backend/requirements.txt semuanya udah final (bukan draft lagi)
- [ ] Cek dulu Melpi butuh GPU passthrough atau nggak — kalau ya, alokasikan waktu ekstra buat setup WSL2 + NVIDIA Container Toolkit, jangan diasumsikan otomatis jalan
- [ ] Docker Desktop terinstall di semua laptop tim yang bakal jalanin compose-nya
