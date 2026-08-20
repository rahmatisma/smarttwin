"use client";

import {
    ChangeEvent,
    FormEvent,
    useEffect,
    useMemo,
    useState,
} from "react";

import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";

type SourceType = "file" | "url" | "rtsp";

type Camera = {
    id: string;
    name: string;
    intersection: string;
    direction: string;
    sourceType: SourceType;
    source: string;
    fileName?: string;
    status: "online" | "waiting";
};

const STORAGE_KEY = "smarttwin.cctv.cameras";

const EMPTY_FORM = {
    name: "",
    intersection: "simpang4-pingit",
    direction: "Utara",
    sourceType: "file" as SourceType,
    source: "",
    fileName: "",
};

export default function CCTVPage() {
    const [cameras, setCameras] = useState<Camera[]>([]);
    const [showModal, setShowModal] = useState(false);
    const [search, setSearch] = useState("");
    const [form, setForm] = useState(EMPTY_FORM);
    const [previewUrls, setPreviewUrls] = useState<
        Record<string, string>
    >({});

    // =====================================================
    // LOAD DATA
    // =====================================================

    useEffect(() => {
        try {
            const saved = localStorage.getItem(STORAGE_KEY);

            if (!saved) return;

            const parsed: Camera[] = JSON.parse(saved);

            // Blob URL tidak bisa bertahan setelah refresh.
            // Jadi file video tidak dimuat kembali dari localStorage.
            const validCameras = parsed.filter(
                (camera) => camera.sourceType !== "file"
            );

            setCameras(validCameras);
        } catch (error) {
            console.error("Gagal membaca CCTV:", error);
            localStorage.removeItem(STORAGE_KEY);
        }
    }, []);

    // =====================================================
    // SAVE DATA
    // =====================================================

    useEffect(() => {
        try {
            const camerasToSave = cameras.filter(
                (camera) => camera.sourceType !== "file"
            );

            localStorage.setItem(
                STORAGE_KEY,
                JSON.stringify(camerasToSave)
            );
        } catch (error) {
            console.error("Gagal menyimpan CCTV:", error);
        }
    }, [cameras]);

    // =====================================================
    // CLEANUP BLOB URL
    // =====================================================

    useEffect(() => {
        return () => {
            Object.values(previewUrls).forEach((url) => {
                if (url.startsWith("blob:")) {
                    URL.revokeObjectURL(url);
                }
            });
        };
    }, [previewUrls]);

    // =====================================================
    // SEARCH
    // =====================================================

    const filteredCameras = useMemo(() => {
        const keyword = search.trim().toLowerCase();

        if (!keyword) {
            return cameras;
        }

        return cameras.filter((camera) => {
            const data = [
                camera.name,
                camera.intersection,
                camera.direction,
                camera.sourceType,
            ]
                .join(" ")
                .toLowerCase();

            return data.includes(keyword);
        });
    }, [cameras, search]);

    // =====================================================
    // FILE UPLOAD
    // =====================================================

    function handleFileChange(
        event: ChangeEvent<HTMLInputElement>
    ) {
        const file = event.target.files?.[0];

        if (!file) {
            return;
        }

        if (!file.type.startsWith("video/")) {
            alert("File yang dipilih harus berupa video.");
            event.target.value = "";
            return;
        }

        // Hapus blob URL sebelumnya
        if (form.source.startsWith("blob:")) {
            URL.revokeObjectURL(form.source);
        }

        const videoUrl = URL.createObjectURL(file);

        setForm((current) => ({
            ...current,
            source: videoUrl,
            fileName: file.name,
        }));
    }

    // =====================================================
    // RESET FORM
    // =====================================================

    function resetForm() {
        setForm({
            name: "",
            intersection: "simpang4-pingit",
            direction: "Utara",
            sourceType: "file",
            source: "",
            fileName: "",
        });
    }

    // =====================================================
    // CLOSE MODAL
    // =====================================================

    function closeModal() {
        if (form.source.startsWith("blob:")) {
            URL.revokeObjectURL(form.source);
        }

        resetForm();
        setShowModal(false);
    }

    // =====================================================
    // SAVE CAMERA
    // =====================================================

    function saveCamera(
        event: FormEvent<HTMLFormElement>
    ) {
        event.preventDefault();

        if (!form.name.trim()) {
            alert("Nama CCTV wajib diisi.");
            return;
        }

        if (!form.source.trim()) {
            alert("Silakan pilih video atau masukkan URL CCTV.");
            return;
        }

        const id = crypto.randomUUID();

        const newCamera: Camera = {
            id,
            name: form.name.trim(),
            intersection:
                form.intersection.trim() ||
                "Tidak diketahui",
            direction: form.direction,
            sourceType: form.sourceType,
            source: form.source,
            fileName: form.fileName,
            status:
                form.sourceType === "rtsp"
                    ? "waiting"
                    : "online",
        };

        setCameras((current) => [
            newCamera,
            ...current,
        ]);

        // Kalau file berupa blob URL,
        // simpan URL tersebut agar video tetap bisa diputar.
        if (form.source.startsWith("blob:")) {
            setPreviewUrls((current) => ({
                ...current,
                [id]: form.source,
            }));
        }

        setShowModal(false);

        // Jangan revoke blob URL di sini
        // karena masih digunakan oleh video.
        resetForm();
    }

    // =====================================================
    // DELETE CAMERA
    // =====================================================

    function deleteCamera(id: string) {
        const preview = previewUrls[id];

        if (preview?.startsWith("blob:")) {
            URL.revokeObjectURL(preview);
        }

        setPreviewUrls((current) => {
            const next = { ...current };
            delete next[id];
            return next;
        });

        setCameras((current) =>
            current.filter(
                (camera) => camera.id !== id
            )
        );
    }

    // =====================================================
    // RETURN
    // =====================================================

    return (
        <div className="flex min-h-screen bg-[#090d13] text-white">

            {/* SIDEBAR */}
            <Sidebar />

            {/* CONTENT AREA */}
            <div className="flex min-w-0 flex-1 flex-col">

                {/* HEADER */}
                <Header
                    locationName="simpang4-pingit"
                    coords="Koordinat belum tersedia"
                />

                {/* MAIN CONTENT */}
                <main className="flex-1 overflow-y-auto px-5 py-6 md:px-7">

                    <div className="mx-auto max-w-[1500px]">

                        {/* PAGE HEADER */}
                        <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">

                            <div>
                                <div className="mb-1 flex items-center gap-2">
                                    <span className="h-2.5 w-2.5 rounded-full bg-[#2ecc71]" />

                                    <h1 className="text-2xl font-semibold">
                                        CCTV Monitoring
                                    </h1>
                                </div>

                                <p className="text-sm text-[#748095]">
                                    Tambahkan dan pantau sumber CCTV
                                    pada setiap arah persimpangan.
                                </p>
                            </div>

                            <button
                                type="button"
                                onClick={() =>
                                    setShowModal(true)
                                }
                                className="rounded-lg bg-[#173747] px-4 py-2.5 text-sm font-semibold text-[#38bdf8] transition hover:bg-[#1d4659]"
                            >
                                + Tambah CCTV
                            </button>
                        </div>

                        {/* SEARCH */}
                        <div className="mb-6 flex flex-col gap-3 rounded-xl border border-[#202735] bg-[#11161f] p-4 md:flex-row md:items-center md:justify-between">

                            <input
                                type="text"
                                value={search}
                                onChange={(event) =>
                                    setSearch(
                                        event.target.value
                                    )
                                }
                                placeholder="Cari CCTV, persimpangan, atau arah..."
                                className="w-full max-w-xl rounded-lg border border-[#29313e] bg-[#0c1118] px-3 py-2.5 text-sm text-white outline-none placeholder:text-[#596375] focus:border-[#268bc0]"
                            />

                            <span className="text-sm text-[#788397]">
                                {filteredCameras.length} kamera
                            </span>
                        </div>

                        {/* CAMERA CONTENT */}
                        {filteredCameras.length === 0 ? (

                            /* EMPTY STATE */
                            <div className="rounded-xl border border-dashed border-[#2b3340] bg-[#11161f] px-6 py-20 text-center">

                                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-xl bg-[#171e29] text-3xl">
                                    📹
                                </div>

                                <h2 className="text-lg font-semibold">
                                    Belum ada CCTV
                                </h2>

                                <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-[#748095]">
                                    Tambahkan video rekaman,
                                    URL HTTP/HLS, atau RTSP
                                    untuk mulai memantau CCTV.
                                </p>

                                <button
                                    type="button"
                                    onClick={() =>
                                        setShowModal(true)
                                    }
                                    className="mt-5 rounded-lg bg-[#173747] px-4 py-2.5 text-sm font-semibold text-[#38bdf8] transition hover:bg-[#1d4659]"
                                >
                                    Tambahkan CCTV pertama
                                </button>

                            </div>

                        ) : (

                            /* CAMERA GRID */
                            <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">

                                {filteredCameras.map(
                                    (camera) => {

                                        const videoSource =
                                            previewUrls[
                                                camera.id
                                            ] ||
                                            camera.source;

                                        return (
                                            <div
                                                key={
                                                    camera.id
                                                }
                                                className="overflow-hidden rounded-xl border border-[#202735] bg-[#11161f]"
                                            >

                                                {/* VIDEO */}
                                                <div className="relative aspect-video bg-black">

                                                    {camera.sourceType ===
                                                    "rtsp" ? (

                                                        <div className="flex h-full flex-col items-center justify-center px-8 text-center">

                                                            <div className="text-4xl">
                                                                📡
                                                            </div>

                                                            <p className="mt-3 text-sm font-medium">
                                                                RTSP Camera
                                                            </p>

                                                            <p className="mt-2 max-w-md text-xs leading-5 text-[#6f7a8c]">
                                                                RTSP tidak
                                                                dapat
                                                                diputar
                                                                langsung
                                                                oleh
                                                                browser.
                                                                Gunakan
                                                                backend
                                                                untuk
                                                                mengubahnya
                                                                menjadi
                                                                HLS atau
                                                                WebRTC.
                                                            </p>

                                                        </div>

                                                    ) : (

                                                        <video
                                                            key={
                                                                videoSource
                                                            }
                                                            src={
                                                                videoSource
                                                            }
                                                            controls
                                                            muted
                                                            playsInline
                                                            preload="metadata"
                                                            className="h-full w-full object-cover"
                                                            onError={(
                                                                event
                                                            ) => {
                                                                console.error(
                                                                    "Video gagal diputar:",
                                                                    event
                                                                        .currentTarget
                                                                        .error
                                                                );
                                                            }}
                                                        />

                                                    )}

                                                    {/* STATUS */}
                                                    <div className="absolute left-3 top-3 flex items-center gap-2 rounded-full bg-black/70 px-2.5 py-1 text-xs backdrop-blur">

                                                        <span
                                                            className={`h-2 w-2 rounded-full ${
                                                                camera.status ===
                                                                "online"
                                                                    ? "bg-[#2ecc71]"
                                                                    : "bg-[#f5a623]"
                                                            }`}
                                                        />

                                                        {camera.status ===
                                                        "online"
                                                            ? "ONLINE"
                                                            : "WAITING"}

                                                    </div>

                                                    {/* SOURCE TYPE */}
                                                    <div className="absolute right-3 top-3 rounded bg-black/70 px-2.5 py-1 text-[11px] uppercase tracking-wide text-[#c4ccd8] backdrop-blur">
                                                        {
                                                            camera.sourceType
                                                        }
                                                    </div>

                                                </div>

                                                {/* CAMERA INFO */}
                                                <div className="p-4">

                                                    <div className="flex items-start justify-between gap-4">

                                                        <div className="min-w-0">

                                                            <h2 className="font-semibold">
                                                                {
                                                                    camera.name
                                                                }
                                                            </h2>

                                                            <p className="mt-1 text-xs text-[#7b8698]">
                                                                {
                                                                    camera.intersection
                                                                }
                                                                {" · "}
                                                                {
                                                                    camera.direction
                                                                }
                                                            </p>

                                                            {camera.fileName && (
                                                                <p className="mt-2 truncate text-xs text-[#566175]">
                                                                    {
                                                                        camera.fileName
                                                                    }
                                                                </p>
                                                            )}

                                                        </div>

                                                    </div>

                                                    {/* CAMERA DATA */}
                                                    <div className="mt-4 grid grid-cols-2 gap-3">

                                                        <div className="rounded-lg bg-[#0c1118] p-3">

                                                            <p className="text-[11px] text-[#667284]">
                                                                Persimpangan
                                                            </p>

                                                            <p className="mt-1 text-sm text-[#dce3ec]">
                                                                {
                                                                    camera.intersection
                                                                }
                                                            </p>

                                                        </div>

                                                        <div className="rounded-lg bg-[#0c1118] p-3">

                                                            <p className="text-[11px] text-[#667284]">
                                                                Arah
                                                            </p>

                                                            <p className="mt-1 text-sm text-[#dce3ec]">
                                                                {
                                                                    camera.direction
                                                                }
                                                            </p>

                                                        </div>

                                                    </div>

                                                    {/* DELETE */}
                                                    <div className="mt-4 flex justify-end">

                                                        <button
                                                            type="button"
                                                            onClick={() =>
                                                                deleteCamera(
                                                                    camera.id
                                                                )
                                                            }
                                                            className="rounded-md border border-[#303846] px-3 py-2 text-xs text-[#9aa5b5] transition hover:border-red-400/50 hover:text-red-300"
                                                        >
                                                            Hapus
                                                        </button>

                                                    </div>

                                                </div>

                                            </div>
                                        );
                                    }
                                )}

                            </div>
                        )}

                    </div>

                </main>
            </div>

            {/* =================================================
                MODAL TAMBAH CCTV
            ================================================= */}
            {showModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">

                    <div className="max-h-[92vh] w-full max-w-xl overflow-y-auto rounded-2xl border border-[#252d3a] bg-[#11161f]">

                        {/* MODAL HEADER */}
                        <div className="flex items-center justify-between border-b border-[#222a36] px-5 py-4">

                            <div>
                                <h2 className="font-semibold">
                                    Tambah CCTV
                                </h2>

                                <p className="mt-1 text-xs text-[#707b8d]">
                                    Daftarkan kamera baru ke
                                    SmartTwin.
                                </p>
                            </div>

                            <button
                                type="button"
                                onClick={closeModal}
                                className="text-xl text-[#7e8898] hover:text-white"
                            >
                                ×
                            </button>

                        </div>

                        {/* FORM */}
                        <form
                            onSubmit={saveCamera}
                            className="space-y-4 p-5"
                        >

                            {/* NAMA CCTV */}
                            <div>

                                <label className="mb-2 block text-xs text-[#8390a2]">
                                    Nama CCTV
                                </label>

                                <input
                                    type="text"
                                    value={form.name}
                                    onChange={(event) =>
                                        setForm(
                                            (current) => ({
                                                ...current,
                                                name: event
                                                    .target
                                                    .value,
                                            })
                                        )
                                    }
                                    placeholder="CCTV Utara"
                                    className="w-full rounded-lg border border-[#29313e] bg-[#0c1118] px-3 py-2.5 text-sm text-white outline-none focus:border-[#268bc0]"
                                />

                            </div>

                            {/* PERSIMPANGAN + ARAH */}
                            <div className="grid gap-4 md:grid-cols-2">

                                <div>

                                    <label className="mb-2 block text-xs text-[#8390a2]">
                                        Persimpangan
                                    </label>

                                    <input
                                        type="text"
                                        value={
                                            form.intersection
                                        }
                                        onChange={(event) =>
                                            setForm(
                                                (current) => ({
                                                    ...current,
                                                    intersection:
                                                        event
                                                            .target
                                                            .value,
                                                })
                                            )
                                        }
                                        className="w-full rounded-lg border border-[#29313e] bg-[#0c1118] px-3 py-2.5 text-sm text-white outline-none focus:border-[#268bc0]"
                                    />

                                </div>

                                <div>

                                    <label className="mb-2 block text-xs text-[#8390a2]">
                                        Arah Kamera
                                    </label>

                                    <select
                                        value={
                                            form.direction
                                        }
                                        onChange={(event) =>
                                            setForm(
                                                (current) => ({
                                                    ...current,
                                                    direction:
                                                        event
                                                            .target
                                                            .value,
                                                })
                                            )
                                        }
                                        className="w-full rounded-lg border border-[#29313e] bg-[#0c1118] px-3 py-2.5 text-sm text-white outline-none focus:border-[#268bc0]"
                                    >
                                        <option value="Utara">
                                            Utara
                                        </option>

                                        <option value="Selatan">
                                            Selatan
                                        </option>

                                        <option value="Timur">
                                            Timur
                                        </option>

                                        <option value="Barat">
                                            Barat
                                        </option>
                                    </select>

                                </div>

                            </div>

                            {/* JENIS SUMBER */}
                            <div>

                                <label className="mb-2 block text-xs text-[#8390a2]">
                                    Jenis Sumber
                                </label>

                                <div className="grid grid-cols-3 gap-2">

                                    {[
                                        {
                                            value: "file" as SourceType,
                                            label: "Video File",
                                        },
                                        {
                                            value: "url" as SourceType,
                                            label: "HTTP / HLS",
                                        },
                                        {
                                            value: "rtsp" as SourceType,
                                            label: "RTSP",
                                        },
                                    ].map(
                                        (item) => (
                                            <button
                                                key={
                                                    item.value
                                                }
                                                type="button"
                                                onClick={() => {

                                                    if (
                                                        form.source.startsWith(
                                                            "blob:"
                                                        )
                                                    ) {
                                                        URL.revokeObjectURL(
                                                            form.source
                                                        );
                                                    }

                                                    setForm(
                                                        (
                                                            current
                                                        ) => ({
                                                            ...current,
                                                            sourceType:
                                                                item.value,
                                                            source: "",
                                                            fileName:
                                                                "",
                                                        })
                                                    );
                                                }}
                                                className={`rounded-lg border px-3 py-2.5 text-xs transition ${
                                                    form.sourceType ===
                                                    item.value
                                                        ? "border-[#268bc0] bg-[#173747] text-[#52c7ff]"
                                                        : "border-[#29313e] bg-[#0c1118] text-[#8792a3]"
                                                }`}
                                            >
                                                {
                                                    item.label
                                                }
                                            </button>
                                        )
                                    )}

                                </div>

                            </div>

                            {/* FILE VIDEO */}
                            {form.sourceType ===
                            "file" && (
                                <div>

                                    <label className="mb-2 block text-xs text-[#8390a2]">
                                        File Video
                                    </label>

                                    <label className="flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-[#344050] bg-[#0c1118] px-4 py-8 text-center transition hover:border-[#268bc0]">

                                        <span className="text-3xl">
                                            🎥
                                        </span>

                                        <span className="mt-3 text-sm text-[#d5dce6]">
                                            {form.fileName ||
                                                "Pilih video CCTV"}
                                        </span>

                                        <span className="mt-1 text-xs text-[#647083]">
                                            MP4, WebM, MOV,
                                            dan format video
                                            browser lainnya
                                        </span>

                                        <input
                                            type="file"
                                            accept="video/*"
                                            onChange={
                                                handleFileChange
                                            }
                                            className="hidden"
                                        />

                                    </label>

                                    {/* PREVIEW VIDEO */}
                                    {form.source && (
                                        <div className="mt-4 overflow-hidden rounded-lg border border-[#29313e] bg-black">

                                            <video
                                                src={
                                                    form.source
                                                }
                                                controls
                                                muted
                                                playsInline
                                                preload="metadata"
                                                className="max-h-64 w-full object-contain"
                                            />

                                        </div>
                                    )}

                                </div>
                            )}

                            {/* URL */}
                            {form.sourceType ===
                                "url" && (
                                <div>

                                    <label className="mb-2 block text-xs text-[#8390a2]">
                                        Stream URL
                                    </label>

                                    <input
                                        type="text"
                                        value={
                                            form.source
                                        }
                                        onChange={(event) =>
                                            setForm(
                                                (current) => ({
                                                    ...current,
                                                    source: event
                                                        .target
                                                        .value,
                                                })
                                            )
                                        }
                                        placeholder="https://example.com/live/stream.m3u8"
                                        className="w-full rounded-lg border border-[#29313e] bg-[#0c1118] px-3 py-2.5 text-sm text-white outline-none focus:border-[#268bc0]"
                                    />

                                </div>
                            )}

                            {/* RTSP */}
                            {form.sourceType ===
                                "rtsp" && (
                                <div>

                                    <label className="mb-2 block text-xs text-[#8390a2]">
                                        RTSP URL
                                    </label>

                                    <input
                                        type="text"
                                        value={
                                            form.source
                                        }
                                        onChange={(event) =>
                                            setForm(
                                                (current) => ({
                                                    ...current,
                                                    source: event
                                                        .target
                                                        .value,
                                                })
                                            )
                                        }
                                        placeholder="rtsp://192.168.1.10:554/stream"
                                        className="w-full rounded-lg border border-[#29313e] bg-[#0c1118] px-3 py-2.5 text-sm text-white outline-none focus:border-[#268bc0]"
                                    />

                                    <p className="mt-2 text-xs leading-5 text-[#687486]">
                                        RTSP tidak dapat
                                        diputar langsung
                                        oleh browser.
                                        Nantinya dapat
                                        dihubungkan ke
                                        backend untuk
                                        HLS/WebRTC.
                                    </p>

                                </div>
                            )}

                            {/* BUTTON */}
                            <div className="flex justify-end gap-2 border-t border-[#222a36] pt-4">

                                <button
                                    type="button"
                                    onClick={closeModal}
                                    className="rounded-lg border border-[#2c3442] px-4 py-2.5 text-sm text-[#9aa5b5] transition hover:bg-[#171e29]"
                                >
                                    Batal
                                </button>

                                <button
                                    type="submit"
                                    className="rounded-lg bg-[#1b7ea9] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#2090bd]"
                                >
                                    Simpan CCTV
                                </button>

                            </div>

                        </form>

                    </div>
                </div>
            )}
        </div>
    );
}