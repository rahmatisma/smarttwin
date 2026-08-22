"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "smarttwin.appearance.settings";
const LANGUAGE_EVENT = "smarttwin-language-updated";
const APPEARANCE_EVENT = "smarttwin-appearance-updated";

type Language = "id" | "en";

type AppearanceSettings = {
    theme: "light" | "dark" | "system";
    language: Language;
    compactMode: boolean;
};

const TRANSLATIONS: Record<Language, Record<string, string>> = {
    id: {
        Dashboard: "Dashboard",
        "Digital Twin": "Kembar Digital",
        CCTV: "CCTV",
        History: "Riwayat",
        Pengaturan: "Pengaturan",
        Account: "Akun",
        Help: "Bantuan",
        Profile: "Profil",
        Notifications: "Notifikasi",
        Security: "Keamanan",
        "Manage your personal information": "Kelola informasi pribadi",
        "Collapse sidebar": "Ciutkan sidebar",
        "Expand sidebar": "Perluas sidebar",
        "Camera Feed": "Feed Kamera",
        "Signal Status": "Status Sinyal",
        Recommendation: "Rekomendasi",
        Forecast: "Prakiraan",
        "Vehicle Detection": "Deteksi Kendaraan",
        "Total Kendaraan": "Total Kendaraan",
        "Kecepatan Rata-rata": "Kecepatan Rata-rata",
        "Antrean Terpanjang": "Antrean Terpanjang",
        "Indeks Kepadatan": "Indeks Kepadatan",
        "Tingkat Kepadatan": "Tingkat Kepadatan",
        Tinggi: "Tinggi",
        Sedang: "Sedang",
        Rendah: "Rendah",
        "Current Phase": "Fase Saat Ini",
        "Remaining Time": "Waktu Tersisa",
        "Cycle Time": "Waktu Siklus",
        Intersection: "Persimpangan",
        "Last Update": "Pembaruan Terakhir",
        "Data Source": "Sumber Data",
        Simulated: "Disimulasikan",
        Connected: "Terhubung",
        "Signal Recommendation": "Rekomendasi Sinyal",
        "Belum tersedia": "Belum tersedia",
        "Recommended Phase": "Fase yang Direkomendasikan",
        "Recommended Green": "Hijau yang Direkomendasikan",
        "Current Green": "Hijau Saat Ini",
        "Expected Delay Reduction": "Perkiraan Pengurangan Tundaan",
        Confidence: "Tingkat Keyakinan",
        Reason: "Alasan",
        Available: "Tersedia",
        Source: "Sumber",
        "Data tidak tersedia": "Data tidak tersedia",
        "Data kendaraan belum tersedia.": "Data kendaraan belum tersedia.",
        "Belum ada CCTV": "Belum ada CCTV",
        "Video belum tersedia": "Video belum tersedia",
        "RTSP Camera": "Kamera RTSP",
        "Backend diperlukan": "Backend required",
        ONLINE: "ONLINE",
        WAITING: "WAITING",
        "CCTV Monitoring": "Monitoring CCTV",
        "Tambah CCTV": "Tambah CCTV",
        "Belum ada akun?": "Don't have an account?",
        "Buat akun baru →": "Create a new account →",
        "Nama Lengkap": "Full Name",
        "Konfirmasi Password": "Confirm Password",
        "Password dan konfirmasi password tidak sama.":
            "Password and confirmation do not match.",
        "Nama CCTV wajib diisi.": "CCTV name is required.",
        "Silakan pilih video.": "Please choose a video.",
        "Silakan masukkan URL CCTV.": "Please enter a CCTV URL.",
        Appearance: "Tampilan",
        "Customize how SmartTwin looks and behaves.":
            "Sesuaikan tampilan dan perilaku SmartTwin.",
        Theme: "Tema",
        Light: "Terang",
        Dark: "Gelap",
        System: "Sistem",
        "Follow device settings": "Ikuti pengaturan perangkat",
        "Use light mode": "Gunakan mode terang",
        "Use dark mode": "Gunakan mode gelap",
        Language: "Bahasa",
        "Bahasa Indonesia": "Bahasa Indonesia",
        English: "English",
        "Compact Mode": "Mode Ringkas",
        "Reduce spacing across the dashboard.":
            "Kurangi jarak pada seluruh dashboard.",
        "Save Changes": "Simpan Perubahan",
        "Changes Saved": "Perubahan Tersimpan",
        Settings: "Pengaturan",
        "Manage your SmartTwin preferences and system configuration.":
            "Kelola preferensi dan konfigurasi sistem SmartTwin.",
        "Sign in to your SmartTwin account":
            "Masuk ke akun SmartTwin Anda",
        "Welcome back": "Selamat datang kembali",
        "Sign In": "Masuk",
        "Signing in...": "Sedang masuk...",
        "Create your SmartTwin account": "Buat akun SmartTwin Anda",
        "Create Account": "Buat Akun",
        "Daftarkan akun baru untuk menggunakan SmartTwin.":
            "Register a new account to use SmartTwin.",
        "Account aktif": "Account aktif",
        "Informasi akun dan sesi SmartTwin.":
            "Informasi akun dan sesi SmartTwin.",
        Session: "Sesi",
        "Kelola sesi login akun ini.": "Manage this account's login session.",
        "Sesi saat ini": "Sesi saat ini",
        "Kamu sedang menggunakan SmartTwin.":
            "Kamu sedang menggunakan SmartTwin.",
        Logout: "Keluar",
        "Logging out...": "Sedang keluar...",
        "Email atau password salah.": "Incorrect email or password.",
        "Manage your personal information.": "Kelola informasi pribadi Anda.",
        "Manage system notifications": "Kelola notifikasi sistem",
        "Customize application appearance": "Sesuaikan tampilan aplikasi",
        "Manage account security": "Kelola keamanan akun",
        "Profile Photo": "Foto Profil",
        "Change photo": "Ubah foto",
        "Your name": "Nama Anda",
        "your@email.com": "email@anda.com",
        "Manage your SmartTwin notifications.":
            "Kelola notifikasi SmartTwin Anda.",
        Password: "Kata Sandi",
        "Update your account password.": "Perbarui kata sandi akun Anda.",
        "Current Password": "Kata Sandi Saat Ini",
        "New Password": "Kata Sandi Baru",
        "Confirm New Password": "Konfirmasi Kata Sandi Baru",
        "Update Password": "Perbarui Kata Sandi",
        "Active Sessions": "Sesi Aktif",
        "Manage devices currently signed into your account.":
            "Kelola perangkat yang sedang masuk ke akun Anda.",
        "Current Device": "Perangkat Saat Ini",
        "This device • Active now": "Perangkat ini • Aktif sekarang",
        Active: "Aktif",
        "Sign out of all devices": "Keluar dari semua perangkat",
        "Traffic Forecast": "Prakiraan Lalu Lintas",
        "kendaraan / 15 menit": "vehicles / 15 minutes",
        "Data forecast belum tersedia dari backend":
            "Data forecast belum tersedia dari backend",
        "Gagal mengambil data traffic": "Gagal mengambil data traffic",
        "Traffic state tidak tersedia.": "Traffic state tidak tersedia.",
        "Cari persimpangan…": "Cari persimpangan…",
        "Koordinat belum tersedia": "Koordinat belum tersedia",
        "Tidak diketahui": "Tidak diketahui",
        "Muat...": "Muat...",
        "Memuat...": "Memuat...",
        "Hapus": "Hapus",
        "Menghapus...": "Menghapus...",
        Batal: "Batal",
        Tutup: "Tutup",
        "Simpan CCTV": "Simpan CCTV",
        "Mulai Upload": "Mulai Upload",
        "Jenis Sumber": "Source Type",
        "Nama CCTV": "CCTV Name",
        "Arah Kamera": "Camera Direction",
        "File Video": "Video File",
        "HTTP / HLS": "HTTP / HLS",
        "RTSP": "RTSP",
    },
    en: {
        Dashboard: "Dashboard",
        "Digital Twin": "Digital Twin",
        CCTV: "CCTV",
        History: "History",
        Pengaturan: "Settings",
        Account: "Account",
        Help: "Help",
        Profil: "Profile",
        Notifikasi: "Notifications",
        Keamanan: "Security",
        "Kelola informasi pribadi": "Manage your personal information",
        "Ciutkan sidebar": "Collapse sidebar",
        "Perluas sidebar": "Expand sidebar",
        "Feed Kamera": "Camera Feed",
        "Status Sinyal": "Signal Status",
        Rekomendasi: "Recommendation",
        Prakiraan: "Forecast",
        "Deteksi Kendaraan": "Vehicle Detection",
        "Vehicle data unavailable.": "Vehicle data unavailable.",
        "Total Kendaraan": "Total Vehicles",
        "Kecepatan Rata-rata": "Average Speed",
        "Antrean Terpanjang": "Longest Queue",
        "Indeks Kepadatan": "Density Index",
        "Tingkat Kepadatan": "Congestion Level",
        Tinggi: "High",
        Sedang: "Moderate",
        Rendah: "Low",
        "Fase Saat Ini": "Current Phase",
        "Waktu Tersisa": "Remaining Time",
        "Waktu Siklus": "Cycle Time",
        Persimpangan: "Intersection",
        "Pembaruan Terakhir": "Last Update",
        "Sumber Data": "Data Source",
        Disimulasikan: "Simulated",
        Terhubung: "Connected",
        "Rekomendasi Sinyal": "Signal Recommendation",
        "Not available": "Not available",
        "Belum tersedia": "Not available",
        "Fase yang Direkomendasikan": "Recommended Phase",
        "Hijau yang Direkomendasikan": "Recommended Green",
        "Hijau Saat Ini": "Current Green",
        "Perkiraan Pengurangan Tundaan": "Expected Delay Reduction",
        "Tingkat Keyakinan": "Confidence",
        Alasan: "Reason",
        Tersedia: "Available",
        Sumber: "Source",
        "Data unavailable": "Data unavailable",
        "Data tidak tersedia": "Data unavailable",
        "No CCTV cameras": "No CCTV cameras",
        "Belum ada CCTV": "No CCTV cameras",
        "Video unavailable": "Video unavailable",
        "Video belum tersedia": "Video unavailable",
        "Kamera RTSP": "Kamera RTSP",
        "Backend required": "Backend required",
        "Backend diperlukan": "Backend required",
        MENUNGGU: "MENUNGGU",
        "Monitoring CCTV": "CCTV Monitoring",
        "Add CCTV": "Add CCTV",
        "Tambah CCTV": "Add CCTV",
        "Don't have an account?": "Don't have an account?",
        "Create a new account →": "Create a new account →",
        "Full Name": "Full Name",
        "Confirm Password": "Confirm Password",
        "Password and confirmation do not match.":
            "Password and confirmation do not match.",
        "CCTV name is required.": "CCTV name is required.",
        "Please choose a video.": "Please choose a video.",
        "Please enter a CCTV URL.": "Please enter a CCTV URL.",
        Tampilan: "Appearance",
        "Sesuaikan tampilan dan perilaku SmartTwin.":
            "Customize how SmartTwin looks and behaves.",
        Tema: "Theme",
        Terang: "Light",
        Gelap: "Dark",
        Sistem: "System",
        "Ikuti pengaturan perangkat": "Follow device settings",
        "Gunakan mode terang": "Use light mode",
        "Gunakan mode gelap": "Use dark mode",
        Bahasa: "Language",
        "Mode Ringkas": "Compact Mode",
        "Kurangi jarak pada seluruh dashboard.":
            "Reduce spacing across the dashboard.",
        "Simpan Perubahan": "Save Changes",
        "Perubahan Tersimpan": "Changes Saved",
        "Kelola preferensi dan konfigurasi sistem SmartTwin.":
            "Manage your SmartTwin preferences and system configuration.",
        "Masuk ke akun SmartTwin Anda":
            "Sign in to your SmartTwin account",
        "Selamat datang kembali": "Welcome back",
        Masuk: "Sign In",
        "Sedang masuk...": "Signing in...",
        "Buat akun SmartTwin Anda": "Create your SmartTwin account",
        "Buat Akun": "Create Account",
        "Register a new account to use SmartTwin.":
            "Daftarkan akun baru untuk menggunakan SmartTwin.",
        "Akun aktif": "Active account",
        "SmartTwin account and session information.":
            "SmartTwin account and session information.",
        Sesi: "Session",
        "Manage this account's login session.":
            "Kelola sesi login akun ini.",
        "Current session": "Current session",
        "You are currently using SmartTwin.":
            "You are currently using SmartTwin.",
        Keluar: "Logout",
        "Sedang keluar...": "Logging out...",
        "Incorrect email or password.": "Email atau password salah.",
        "Kelola informasi pribadi Anda.": "Manage your personal information.",
        "Kelola notifikasi sistem": "Manage system notifications",
        "Sesuaikan tampilan aplikasi": "Customize application appearance",
        "Kelola keamanan akun": "Manage account security",
        "Foto Profil": "Profile Photo",
        "Ubah foto": "Change photo",
        "Nama Anda": "Your name",
        "email@anda.com": "your@email.com",
        "Kelola notifikasi SmartTwin Anda.":
            "Manage your SmartTwin notifications.",
        "Kata Sandi": "Password",
        "Perbarui kata sandi akun Anda.": "Update your account password.",
        "Kata Sandi Saat Ini": "Current Password",
        "Kata Sandi Baru": "New Password",
        "Konfirmasi Kata Sandi Baru": "Confirm New Password",
        "Perbarui Kata Sandi": "Update Password",
        "Sesi Aktif": "Active Sessions",
        "Kelola perangkat yang sedang masuk ke akun Anda.":
            "Manage devices currently signed into your account.",
        "Perangkat Saat Ini": "Current Device",
        "Perangkat ini • Aktif sekarang": "This device • Active now",
        Aktif: "Active",
        "Keluar dari semua perangkat": "Sign out of all devices",
        "Prakiraan Lalu Lintas": "Traffic Forecast",
        "vehicles / 15 minutes": "kendaraan / 15 menit",
        "Data forecast belum tersedia dari backend":
            "Forecast data is unavailable from the backend",
        "Failed to load traffic data": "Gagal mengambil data traffic",
        "Traffic state is unavailable.": "Traffic state tidak tersedia.",
        "Vehicle data is unavailable.": "Data kendaraan belum tersedia.",
        "Search intersections…": "Cari persimpangan…",
        "Coordinates unavailable": "Coordinates unavailable",
        Unknown: "Unknown",
        Loading: "Loading...",
        Delete: "Delete",
        Deleting: "Deleting...",
        Cancel: "Cancel",
        Close: "Close",
        "Save CCTV": "Simpan CCTV",
        "Start Upload": "Mulai Upload",
        "Source Type": "Jenis Sumber",
        "CCTV Name": "Nama CCTV",
        "Camera Direction": "Arah Kamera",
    },
};

function getStoredAppearance(): AppearanceSettings {
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        const parsed: unknown = stored ? JSON.parse(stored) : null;
        const values =
            typeof parsed === "object" && parsed !== null
                ? (parsed as Record<string, unknown>)
                : {};

        return {
            theme:
                values.theme === "light" ||
                values.theme === "dark" ||
                values.theme === "system"
                    ? values.theme
                    : "system",
            language: values.language === "en" ? "en" : "id",
            compactMode:
                typeof values.compactMode === "boolean"
                    ? values.compactMode
                    : false,
        };
    } catch {
        return {
            theme: "system",
            language: "id",
            compactMode: false,
        };
    }
}

function applyAppearance(settings: AppearanceSettings) {
    const prefersDark = window.matchMedia(
        "(prefers-color-scheme: dark)"
    ).matches;
    const isDark =
        settings.theme === "dark" ||
        (settings.theme === "system" && prefersDark);

    document.documentElement.dataset.theme = isDark ? "dark" : "light";
    document.documentElement.lang = settings.language;
    document.body.classList.toggle("compact-mode", settings.compactMode);
}

function translateText(text: string, language: Language): string {
    const trimmed = text.trim();
    const translation = TRANSLATIONS[language][trimmed];

    if (!translation) {
        return text;
    }

    return text.replace(trimmed, translation);
}

type TranslatedValue = {
    original: string;
    rendered: string;
};

const translatedTextNodes = new WeakMap<Text, TranslatedValue>();
const translatedAttributes = new WeakMap<HTMLElement, Map<string, TranslatedValue>>();

function translateNodeText(textNode: Text, language: Language) {
    const current = textNode.nodeValue ?? "";
    const previous = translatedTextNodes.get(textNode);
    const original = previous && current === previous.rendered
        ? previous.original
        : current;
    const rendered = translateText(original, language);

    translatedTextNodes.set(textNode, { original, rendered });
    textNode.nodeValue = rendered;
}

function translateAttribute(
    element: HTMLElement,
    attribute: string,
    language: Language
) {
    const current = element.getAttribute(attribute);
    if (!current) {
        return;
    }

    const values = translatedAttributes.get(element) ?? new Map();
    const previous = values.get(attribute);
    const original = previous && current === previous.rendered
        ? previous.original
        : current;
    const rendered = translateText(original, language);

    values.set(attribute, { original, rendered });
    translatedAttributes.set(element, values);
    element.setAttribute(attribute, rendered);
}

function translateDocument(language: Language) {
    const walker = document.createTreeWalker(
        document.body,
        NodeFilter.SHOW_TEXT
    );
    const nodes: Text[] = [];
    let node: Node | null;

    while ((node = walker.nextNode())) {
        if (node.parentElement?.closest("script, style")) {
            continue;
        }
        nodes.push(node as Text);
    }

    nodes.forEach((textNode) => translateNodeText(textNode, language));

    document.querySelectorAll<HTMLElement>("input, textarea").forEach((element) => {
        const placeholder = element.getAttribute("placeholder");
        if (placeholder) {
            translateAttribute(element, "placeholder", language);
        }
    });

    document.querySelectorAll<HTMLElement>("[title], [aria-label]").forEach(
        (element) => {
            ["title", "aria-label"].forEach((attribute) => {
                const value = element.getAttribute(attribute);
                if (value) {
                    translateAttribute(element, attribute, language);
                }
            });
        }
    );
}

export default function LanguageProvider({
    children,
}: {
    children: React.ReactNode;
}) {
    const [language, setLanguage] = useState<Language>("id");

    useEffect(() => {
        const updateAppearance = () => {
            const settings = getStoredAppearance();
            setLanguage(settings.language);
            applyAppearance(settings);
        };

        updateAppearance();
        window.addEventListener(LANGUAGE_EVENT, updateAppearance);
        window.addEventListener(APPEARANCE_EVENT, updateAppearance);
        window.addEventListener("storage", updateAppearance);

        return () => {
            window.removeEventListener(LANGUAGE_EVENT, updateAppearance);
            window.removeEventListener(APPEARANCE_EVENT, updateAppearance);
            window.removeEventListener("storage", updateAppearance);
        };
    }, []);

    useEffect(() => {
        document.documentElement.lang = language;
        translateDocument(language);

        const observer = new MutationObserver(() => {
            translateDocument(language);
        });
        observer.observe(document.body, { childList: true, subtree: true });

        return () => observer.disconnect();
    }, [language]);

    return children;
}

export { APPEARANCE_EVENT, LANGUAGE_EVENT };
