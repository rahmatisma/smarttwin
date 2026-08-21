"use client";

import {
    ChangeEvent,
    FormEvent,
    useCallback,
    useEffect,
    useMemo,
    useState,
} from "react";

import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";

import { fetchCameras, DEFAULT_INTERSECTION_ID } from "@/lib/supabaseData";

type SourceType = "file" | "url" | "rtsp";
type Approach = "north" | "south" | "east" | "west";

type Camera = {
    id: string;
    name: string;
    intersection: string;
    approach: Approach;
    sourceType: SourceType;
    source: string;
    fileName?: string;
    status: "online" | "waiting";
};

const APPROACH_LABELS: Record<Approach, string> = {
    north: "Utara",
    south: "Selatan",
    east: "Timur",
    west: "Barat",
};

const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const EMPTY_FORM = {
    name: "",
    approach: "north" as Approach,
    sourceType: "file" as SourceType,
    source: "",
    fileName: "",
};

/*
 * "uploaded" (docs/database.md) -> tampilan frontend.
 * File video sungguhan disimpan di Hugging Face Hub lewat
 * backend FastAPI (POST /api/v1/cctv/upload), diputar balik
 * lewat proxy stream backend.
 */
function toFrontendSourceType(dbSourceType: string): SourceType {
    if (dbSourceType === "uploaded") return "file";
    return "url";
}

function resolveVideoSrc(source: string): string {
    if (source.startsWith("/api/")) {
        return `${API_BASE_URL}${source}`;
    }

    return source;
}

/*
 * fetch() tidak expose progress upload, jadi pakai XHR
 * supaya xhr.upload.onprogress bisa dipantau untuk file
 * video CCTV yang bisa berukuran besar (GB-an).
 *
 * PENTING: xhr.upload.onprogress cuma ngukur fase browser -> backend
 * (localhost, biasanya cepat/instan). xhr.upload.onload menandai fase
 * itu SELESAI -- tapi response HTTP-nya (xhr.onload) baru datang
 * setelah backend selesai upload ulang ke Hugging Face, yang bisa
 * jauh lebih lama untuk video besar. Tanpa membedakan dua fase ini,
 * UI kelihatan "macet di 100%" padahal backend masih kerja.
 */
function uploadCctvFileWithProgress(
    body: FormData,
    onProgress: (percent: number) => void,
    onSendComplete: () => void
): Promise<{ ok: boolean; status: number; payload: Record<string, unknown> }> {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();

        xhr.open("POST", `${API_BASE_URL}/api/v1/cctv/upload`);

        xhr.upload.onprogress = (event) => {
            if (event.lengthComputable) {
                onProgress(Math.round((event.loaded / event.total) * 100));
            }
        };

        xhr.upload.onload = () => {
            onSendComplete();
        };

        xhr.onload = () => {
            let payload: Record<string, unknown> = {};

            try {
                payload = JSON.parse(xhr.responseText);
            } catch {
                // respons non-JSON, biarkan payload kosong
            }

            resolve({ ok: xhr.status >= 200 && xhr.status < 300, status: xhr.status, payload });
        };

        xhr.onerror = () => reject(new Error("Gagal mengupload video."));

        xhr.send(body);
    });
}

/*
 * Satu upload video yang sedang berjalan di background -- lepas
 * dari modal. Ditampilkan sebagai kartu tersendiri di grid CCTV
 * (di depan kartu kamera asli) supaya user bisa nutup modal dan
 * lanjut kerja lain, tapi tetap kelihatan progresnya.
 */
type UploadTask = {
    id: string;
    fileName: string;
    approach: Approach;
    status: "sending" | "processing" | "error";
    progress: number;
    error?: string;
};

export default function CCTVPage() {
    const [cameras, setCameras] = useState<Camera[]>([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [search, setSearch] = useState("");
    const [form, setForm] = useState(EMPTY_FORM);
    const [saving, setSaving] = useState(false);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [formError, setFormError] = useState<string | null>(null);

    /*
     * File asli untuk diupload ke backend saat submit. Blob URL
     * di form.source hanya dipakai untuk preview di dalam modal.
     */
    const [fileObject, setFileObject] = useState<File | null>(null);

    /*
     * Upload video yang sedang berjalan di background, lepas dari
     * modal (lihat komentar UploadTask di atas). Modal bisa ditutup
     * kapan pun setelah submit -- upload tetap lanjut, progresnya
     * muncul sebagai kartu di grid.
     */
    const [uploadTasks, setUploadTasks] = useState<UploadTask[]>([]);

    // =====================================================
    // LOAD DATA DARI SUPABASE
    // =====================================================

    const loadCameras = useCallback(async () => {
        try {
            const rows = await fetchCameras(DEFAULT_INTERSECTION_ID);

            setCameras(
                rows.map((row) => ({
                    id: String(row.id),
                    name: row.name,
                    intersection: DEFAULT_INTERSECTION_ID,
                    approach: (row.approach as Approach) ?? "north",
                    sourceType: toFrontendSourceType(row.sourceType),
                    source: row.videoUrl ?? "",
                    fileName: row.videoName ?? undefined,
                    status: row.status === "active" ? "online" : "waiting",
                }))
            );
        } catch (error) {
            console.error("Gagal mengambil cameras dari Supabase:", error);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        let cancelled = false;

        (async () => {
            if (!cancelled) {
                await loadCameras();
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [loadCameras]);

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
                APPROACH_LABELS[camera.approach],
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

    function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
        const file = event.target.files?.[0];

        if (!file) {
            return;
        }

        if (!file.type.startsWith("video/")) {
            alert("File yang dipilih harus berupa video.");

            event.target.value = "";

            return;
        }

        if (form.source.startsWith("blob:")) {
            URL.revokeObjectURL(form.source);
        }

        const videoUrl = URL.createObjectURL(file);

        setFileObject(file);

        setForm((current) => ({
            ...current,
            source: videoUrl,
            fileName: file.name,
        }));
    }

    // =====================================================
    // RESET / CLOSE MODAL
    // =====================================================

    function resetForm() {
        if (form.source.startsWith("blob:")) {
            URL.revokeObjectURL(form.source);
        }

        setForm(EMPTY_FORM);
        setFileObject(null);
        setFormError(null);
    }

    function closeModal() {
        resetForm();
        setShowModal(false);
    }

    // =====================================================
    // UPLOAD VIDEO DI BACKGROUND
    // =====================================================
    //
    // Sengaja TIDAK di-await oleh saveCamera -- dipanggil lalu
    // dilepas begitu saja (fire-and-forget dari sisi modal), supaya
    // modal bisa langsung ditutup sementara upload jalan sendiri.
    // Progresnya dilacak lewat state uploadTasks, dibaca oleh kartu
    // di grid, bukan oleh modal.

    async function startFileUpload(
        file: File,
        name: string,
        approach: Approach
    ) {
        const taskId = crypto.randomUUID();

        setUploadTasks((current) => [
            ...current,
            {
                id: taskId,
                fileName: name,
                approach,
                status: "sending",
                progress: 0,
            },
        ]);

        const updateTask = (patch: Partial<UploadTask>) => {
            setUploadTasks((current) =>
                current.map((task) =>
                    task.id === taskId ? { ...task, ...patch } : task
                )
            );
        };

        try {
            const body = new FormData();
            body.append("file", file);
            body.append("name", name);
            body.append("approach", approach);
            body.append("intersection_id", DEFAULT_INTERSECTION_ID);

            const { ok, payload } = await uploadCctvFileWithProgress(
                body,
                (percent) => updateTask({ progress: percent }),
                () => updateTask({ status: "processing" })
            );

            if (!ok) {
                throw new Error(
                    (payload.detail as string) ?? "Gagal mengupload video."
                );
            }

            // Sukses -> hapus kartu task, kamera aslinya muncul lewat loadCameras().
            setUploadTasks((current) =>
                current.filter((task) => task.id !== taskId)
            );

            await loadCameras();
        } catch (error) {
            updateTask({
                status: "error",
                error:
                    error instanceof Error
                        ? error.message
                        : "Gagal mengupload video.",
            });
        }
    }

    function dismissUploadTask(taskId: string) {
        setUploadTasks((current) =>
            current.filter((task) => task.id !== taskId)
        );
    }

    // =====================================================
    // SAVE CAMERA
    // =====================================================
    //
    // file        -> startFileUpload() di background (lihat di atas),
    //                modal langsung ditutup tanpa menunggu selesai
    // url / rtsp  -> POST /api/cameras (Next.js, metadata saja,
    //                instan, tidak ada file untuk diupload)

    async function saveCamera(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();

        if (!form.name.trim()) {
            setFormError("Nama CCTV wajib diisi.");
            return;
        }

        if (form.sourceType !== "file" && !form.source.trim()) {
            setFormError("Silakan masukkan URL CCTV.");
            return;
        }

        if (form.sourceType === "file" && !fileObject) {
            setFormError("Silakan pilih video.");
            return;
        }

        setFormError(null);

        if (form.sourceType === "file" && fileObject) {
            void startFileUpload(fileObject, form.name.trim(), form.approach);

            setShowModal(false);
            resetForm();
            return;
        }

        setSaving(true);

        try {
            const response = await fetch("/api/cameras", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    name: form.name.trim(),
                    approach: form.approach,
                    sourceType: form.sourceType,
                    source: form.source,
                }),
            });

            const payload = await response.json();

            if (!response.ok) {
                throw new Error(payload.error ?? "Gagal menyimpan CCTV.");
            }

            await loadCameras();

            setShowModal(false);
            resetForm();
        } catch (error) {
            setFormError(
                error instanceof Error
                    ? error.message
                    : "Gagal menyimpan CCTV."
            );
        } finally {
            setSaving(false);
        }
    }

    // =====================================================
    // DELETE CAMERA -> DELETE /api/cameras/[id]
    // =====================================================

    async function deleteCamera(id: string) {
        setDeletingId(id);

        try {
            const response = await fetch(`/api/cameras/${id}`, {
                method: "DELETE",
            });

            if (!response.ok) {
                const payload = await response.json();
                throw new Error(payload.error ?? "Gagal menghapus CCTV.");
            }

            await loadCameras();
        } catch (error) {
            alert(
                error instanceof Error
                    ? error.message
                    : "Gagal menghapus CCTV."
            );
        } finally {
            setDeletingId(null);
        }
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
                                    Data tersimpan di Supabase.
                                </p>
                            </div>

                            <button
                                type="button"
                                onClick={() => setShowModal(true)}
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
                                    setSearch(event.target.value)
                                }
                                placeholder="Cari CCTV, persimpangan, atau arah..."
                                className="w-full max-w-xl rounded-lg border border-[#29313e] bg-[#0c1118] px-3 py-2.5 text-sm text-white outline-none placeholder:text-[#596375] focus:border-[#268bc0]"
                            />

                            <span className="text-sm text-[#788397]">
                                {loading
                                    ? "Memuat..."
                                    : `${filteredCameras.length} kamera`}
                            </span>

                        </div>

                        {/* CAMERA CONTENT */}
                        {!loading &&
                        filteredCameras.length === 0 &&
                        uploadTasks.length === 0 ? (

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
                                    onClick={() => setShowModal(true)}
                                    className="mt-5 rounded-lg bg-[#173747] px-4 py-2.5 text-sm font-semibold text-[#38bdf8] transition hover:bg-[#1d4659]"
                                >
                                    Tambahkan CCTV pertama
                                </button>

                            </div>

                        ) : (

                            /* CAMERA GRID */
                            <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">

                                {/* KARTU UPLOAD SEDANG BERJALAN */}
                                {uploadTasks.map((task) => (

                                    <div
                                        key={task.id}
                                        className="overflow-hidden rounded-xl border border-[#268bc0]/40 bg-[#11161f]"
                                    >

                                        <div className="relative flex aspect-video flex-col items-center justify-center bg-black px-8 text-center">

                                            {task.status === "error" ? (
                                                <>
                                                    <div className="text-4xl">
                                                        ⚠️
                                                    </div>
                                                    <p className="mt-3 text-sm font-medium text-red-300">
                                                        Upload gagal
                                                    </p>
                                                    <p className="mt-2 max-w-md text-xs leading-5 text-[#a3a9b3]">
                                                        {task.error}
                                                    </p>
                                                </>
                                            ) : (
                                                <>
                                                    <span className="h-8 w-8 animate-spin rounded-full border-2 border-[#1b7ea9] border-t-transparent" />
                                                    <p className="mt-3 text-sm font-medium">
                                                        {task.status ===
                                                        "sending"
                                                            ? `Mengirim... ${task.progress}%`
                                                            : "Menyimpan ke Hugging Face..."}
                                                    </p>
                                                    {task.status ===
                                                        "processing" && (
                                                        <p className="mt-2 max-w-md text-xs leading-5 text-[#6f7a8c]">
                                                            Video besar bisa
                                                            makan waktu
                                                            beberapa menit —
                                                            halaman ini boleh
                                                            kamu tinggal.
                                                        </p>
                                                    )}
                                                </>
                                            )}

                                        </div>

                                        {/* PROGRESS BAR */}
                                        {task.status !== "error" && (
                                            <div className="h-1 w-full overflow-hidden bg-[#0c1118]">
                                                <div
                                                    className={
                                                        task.status ===
                                                        "sending"
                                                            ? "h-full rounded-full bg-[#1b7ea9] transition-all"
                                                            : "h-full w-1/3 animate-[pulse_1.2s_ease-in-out_infinite] rounded-full bg-[#1b7ea9]"
                                                    }
                                                    style={
                                                        task.status ===
                                                        "sending"
                                                            ? {
                                                                  width: `${task.progress}%`,
                                                              }
                                                            : undefined
                                                    }
                                                />
                                            </div>
                                        )}

                                        <div className="p-4">

                                            <div className="flex items-start justify-between gap-4">

                                                <div className="min-w-0">
                                                    <h2 className="truncate font-semibold">
                                                        {task.fileName}
                                                    </h2>

                                                    <p className="mt-1 text-xs text-[#7b8698]">
                                                        {DEFAULT_INTERSECTION_ID}
                                                        {" · "}
                                                        {
                                                            APPROACH_LABELS[
                                                                task.approach
                                                            ]
                                                        }
                                                    </p>
                                                </div>

                                                {task.status ===
                                                    "error" && (
                                                    <button
                                                        type="button"
                                                        onClick={() =>
                                                            dismissUploadTask(
                                                                task.id
                                                            )
                                                        }
                                                        className="shrink-0 rounded-md border border-[#303846] px-3 py-2 text-xs text-[#9aa5b5] transition hover:border-red-400/50 hover:text-red-300"
                                                    >
                                                        Tutup
                                                    </button>
                                                )}

                                            </div>

                                        </div>

                                    </div>

                                ))}

                                {filteredCameras.map((camera) => {

                                    const videoSource = resolveVideoSrc(
                                        camera.source
                                    );

                                    return (
                                        <div
                                            key={camera.id}
                                            className="overflow-hidden rounded-xl border border-[#202735] bg-[#11161f]"
                                        >

                                            {/* VIDEO */}
                                            <div className="relative aspect-video bg-black">

                                                {!videoSource ? (

                                                    <div className="flex h-full flex-col items-center justify-center px-8 text-center">

                                                        <div className="text-4xl">
                                                            🎥
                                                        </div>

                                                        <p className="mt-3 text-sm font-medium">
                                                            {camera.fileName ||
                                                                "Video belum tersedia"}
                                                        </p>

                                                    </div>

                                                ) : videoSource.startsWith(
                                                      "rtsp"
                                                  ) ? (

                                                    <div className="flex h-full flex-col items-center justify-center px-8 text-center">

                                                        <div className="text-4xl">
                                                            📡
                                                        </div>

                                                        <p className="mt-3 text-sm font-medium">
                                                            RTSP Camera
                                                        </p>

                                                        <p className="mt-2 max-w-md text-xs leading-5 text-[#6f7a8c]">
                                                            RTSP tidak dapat
                                                            diputar langsung
                                                            oleh browser.
                                                            Gunakan backend
                                                            untuk mengubahnya
                                                            menjadi HLS atau
                                                            WebRTC.
                                                        </p>

                                                    </div>

                                                ) : (

                                                    <video
                                                        key={videoSource}
                                                        src={videoSource}
                                                        controls
                                                        muted
                                                        playsInline
                                                        preload="metadata"
                                                        className="h-full w-full object-cover"
                                                        onError={(event) => {
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
                                                    {camera.sourceType}
                                                </div>

                                            </div>

                                            {/* CAMERA INFO */}
                                            <div className="p-4">

                                                <div className="flex items-start justify-between gap-4">

                                                    <div className="min-w-0">

                                                        <h2 className="font-semibold">
                                                            {camera.name}
                                                        </h2>

                                                        <p className="mt-1 text-xs text-[#7b8698]">
                                                            {
                                                                camera.intersection
                                                            }
                                                            {" · "}
                                                            {
                                                                APPROACH_LABELS[
                                                                    camera
                                                                        .approach
                                                                ]
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
                                                                APPROACH_LABELS[
                                                                    camera
                                                                        .approach
                                                                ]
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
                                                        disabled={
                                                            deletingId ===
                                                            camera.id
                                                        }
                                                        className="rounded-md border border-[#303846] px-3 py-2 text-xs text-[#9aa5b5] transition hover:border-red-400/50 hover:text-red-300 disabled:opacity-50"
                                                    >
                                                        {deletingId ===
                                                        camera.id
                                                            ? "Menghapus..."
                                                            : "Hapus"}
                                                    </button>

                                                </div>

                                            </div>

                                        </div>
                                    );
                                })}

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
                                        setForm((current) => ({
                                            ...current,
                                            name: event.target.value,
                                        }))
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
                                        value={DEFAULT_INTERSECTION_ID}
                                        readOnly
                                        className="w-full cursor-not-allowed rounded-lg border border-[#29313e] bg-[#0c1118] px-3 py-2.5 text-sm text-[#8390a2] outline-none"
                                    />

                                </div>

                                <div>

                                    <label className="mb-2 block text-xs text-[#8390a2]">
                                        Arah Kamera
                                    </label>

                                    <select
                                        value={form.approach}
                                        onChange={(event) =>
                                            setForm((current) => ({
                                                ...current,
                                                approach: event.target
                                                    .value as Approach,
                                            }))
                                        }
                                        className="w-full rounded-lg border border-[#29313e] bg-[#0c1118] px-3 py-2.5 text-sm text-white outline-none focus:border-[#268bc0]"
                                    >

                                        {(
                                            Object.keys(
                                                APPROACH_LABELS
                                            ) as Approach[]
                                        ).map((approach) => (
                                            <option
                                                key={approach}
                                                value={approach}
                                            >
                                                {
                                                    APPROACH_LABELS[
                                                        approach
                                                    ]
                                                }
                                            </option>
                                        ))}

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
                                    ].map((item) => (

                                        <button
                                            key={item.value}
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

                                                setForm((current) => ({
                                                    ...current,
                                                    sourceType: item.value,
                                                    source: "",
                                                    fileName: "",
                                                }));
                                            }}
                                            className={`rounded-lg border px-3 py-2.5 text-xs transition ${
                                                form.sourceType ===
                                                item.value
                                                    ? "border-[#268bc0] bg-[#173747] text-[#52c7ff]"
                                                    : "border-[#29313e] bg-[#0c1118] text-[#8792a3]"
                                            }`}
                                        >
                                            {item.label}
                                        </button>

                                    ))}

                                </div>

                            </div>

                            {/* FILE VIDEO */}
                            {form.sourceType === "file" && (

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
                                            browser lainnya.
                                            Video diupload ke
                                            Hugging Face Hub,
                                            metadata disimpan
                                            di Supabase.
                                        </span>

                                        <input
                                            type="file"
                                            accept="video/*"
                                            onChange={handleFileChange}
                                            className="hidden"
                                        />

                                    </label>

                                    {/* PREVIEW VIDEO */}
                                    {form.source && (

                                        <div className="mt-4 overflow-hidden rounded-lg border border-[#29313e] bg-black">

                                            <video
                                                src={form.source}
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
                            {form.sourceType === "url" && (

                                <div>

                                    <label className="mb-2 block text-xs text-[#8390a2]">
                                        Stream URL
                                    </label>

                                    <input
                                        type="text"
                                        value={form.source}
                                        onChange={(event) =>
                                            setForm((current) => ({
                                                ...current,
                                                source: event.target.value,
                                            }))
                                        }
                                        placeholder="https://example.com/live/stream.m3u8"
                                        className="w-full rounded-lg border border-[#29313e] bg-[#0c1118] px-3 py-2.5 text-sm text-white outline-none focus:border-[#268bc0]"
                                    />

                                </div>
                            )}

                            {/* RTSP */}
                            {form.sourceType === "rtsp" && (

                                <div>

                                    <label className="mb-2 block text-xs text-[#8390a2]">
                                        RTSP URL
                                    </label>

                                    <input
                                        type="text"
                                        value={form.source}
                                        onChange={(event) =>
                                            setForm((current) => ({
                                                ...current,
                                                source: event.target.value,
                                            }))
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

                            {form.sourceType === "file" && (
                                <p className="text-[11px] leading-4 text-[#647083]">
                                    Begitu disimpan, modal ini langsung
                                    tertutup dan upload jalan di
                                    background — progresnya muncul
                                    sebagai kartu di grid CCTV, kamu
                                    bebas buka modal ini lagi buat
                                    upload video lain sambil menunggu.
                                </p>
                            )}

                            {/* ERROR */}
                            {formError && (
                                <p className="text-xs text-red-400">
                                    {formError}
                                </p>
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
                                    disabled={saving}
                                    className="rounded-lg bg-[#1b7ea9] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#2090bd] disabled:opacity-60"
                                >
                                    {saving
                                        ? "Menyimpan..."
                                        : form.sourceType === "file"
                                        ? "Mulai Upload"
                                        : "Simpan CCTV"}
                                </button>

                            </div>

                        </form>

                    </div>
                </div>
            )}
        </div>
    );
}
