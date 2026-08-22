"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { User, Mail, Save, Camera } from "lucide-react";

import { supabase } from "@/lib/supabaseClient";

const LOCAL_AVATAR_PREFIX = "smarttwin.profile.avatar.";

function getLocalAvatar(userId: string): string {
    try {
        return localStorage.getItem(`${LOCAL_AVATAR_PREFIX}${userId}`) ?? "";
    } catch {
        return "";
    }
}

function readFileAsDataUrl(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = () => reject(new Error("Gagal membaca file foto."));
        reader.readAsDataURL(file);
    });
}

export default function ProfileSettings() {
    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const [userId, setUserId] = useState("");
    const [avatarUrl, setAvatarUrl] = useState("");
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [uploadingPhoto, setUploadingPhoto] = useState(false);
    const [message, setMessage] = useState("");
    const [error, setError] = useState("");

    useEffect(() => {
        async function loadProfile() {
            const { data, error: userError } =
                await supabase.auth.getUser();

            if (userError) {
                setError(userError.message);
                setLoading(false);
                return;
            }

            if (!data.user) {
                setError("User tidak ditemukan. Silakan login kembali.");
                setLoading(false);
                return;
            }

            setName(
                typeof data.user.user_metadata?.name === "string"
                    ? data.user.user_metadata.name
                    : ""
            );
            setEmail(data.user.email ?? "");
            setUserId(data.user.id);
            const metadataAvatar =
                typeof data.user.user_metadata?.avatar_url === "string"
                    ? data.user.user_metadata.avatar_url
                    : "";
            setAvatarUrl(metadataAvatar || getLocalAvatar(data.user.id));
            setLoading(false);
        }

        void loadProfile();
    }, []);

    async function handleSave() {
        const trimmedName = name.trim();

        if (!trimmedName) {
            setError("Nama tidak boleh kosong.");
            setMessage("");
            return;
        }

        setSaving(true);
        setError("");
        setMessage("");

        const { error: updateError } = await supabase.auth.updateUser({
            data: { name: trimmedName },
        });

        if (updateError) {
            setError(updateError.message);
        } else {
            setName(trimmedName);
            setMessage("Profile berhasil diperbarui.");
        }

        setSaving(false);
    }

    async function handlePhotoChange(
        event: React.ChangeEvent<HTMLInputElement>
    ) {
        const file = event.target.files?.[0];
        event.target.value = "";

        if (!file) {
            return;
        }

        if (!file.type.startsWith("image/")) {
            setError("File foto harus berupa gambar.");
            return;
        }

        if (file.size > 5 * 1024 * 1024) {
            setError("Ukuran foto maksimal 5 MB.");
            return;
        }

        if (!userId) {
            setError("User belum siap. Silakan coba lagi.");
            return;
        }

        setUploadingPhoto(true);
        setError("");
        setMessage("");

        const extension = file.name.split(".").pop()?.toLowerCase() || "jpg";
        const path = `${userId}/avatar.${extension}`;

        try {
            const { error: uploadError } = await supabase.storage
                .from("avatars")
                .upload(path, file, {
                    cacheControl: "3600",
                    contentType: file.type,
                    upsert: true,
                });

            let nextAvatarUrl: string;

            if (uploadError) {
                if (file.size > 1024 * 1024) {
                    throw new Error(
                        "Bucket avatars belum tersedia. Buat bucket tersebut, atau pilih foto maksimal 1 MB."
                    );
                }

                nextAvatarUrl = await readFileAsDataUrl(file);
                localStorage.setItem(
                    `${LOCAL_AVATAR_PREFIX}${userId}`,
                    nextAvatarUrl
                );
            } else {
                const { data } = supabase.storage
                    .from("avatars")
                    .getPublicUrl(path);
                nextAvatarUrl = `${data.publicUrl}?v=${Date.now()}`;

                const { error: metadataError } =
                    await supabase.auth.updateUser({
                        data: { avatar_url: nextAvatarUrl },
                    });

                if (metadataError) {
                    throw metadataError;
                }
            }

            setAvatarUrl(nextAvatarUrl);
            setMessage("Foto profil berhasil diperbarui.");
        } catch (photoError) {
            setError(
                photoError instanceof Error
                    ? photoError.message
                    : "Gagal mengunggah foto profil."
            );
        } finally {
            setUploadingPhoto(false);
        }
    }

    const initials =
        name
            .split(" ")
            .filter(Boolean)
            .slice(0, 2)
            .map((part) => part[0]?.toUpperCase())
            .join("") || "SM";

    return (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">

            <div className="mb-6">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
                    Profile
                </h2>

                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                    Manage your personal information.
                </p>
            </div>

            {/* Avatar */}
            <div className="mb-8 flex items-center gap-4">
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-slate-200 dark:bg-slate-700">
                    {avatarUrl ? (
                        <Image
                            src={avatarUrl}
                            alt="Foto profil"
                            width={64}
                            height={64}
                            unoptimized
                            className="h-full w-full rounded-full object-cover"
                        />
                    ) : (
                        <span className="text-lg font-semibold text-slate-500 dark:text-slate-300">
                            {initials}
                        </span>
                    )}
                </div>

                <div>
                    <p className="font-medium text-slate-900 dark:text-white">
                        Foto Profil
                    </p>

                    <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                        {avatarUrl
                            ? "Foto profil akun Anda."
                            : "Avatar menggunakan inisial nama."}
                    </p>

                    <label className="mt-2 inline-flex cursor-pointer items-center gap-2 text-sm font-medium text-blue-600 hover:text-blue-700">
                        <Camera size={15} />
                        {uploadingPhoto ? "Mengunggah..." : "Ganti foto"}
                        <input
                            type="file"
                            accept="image/*"
                            onChange={handlePhotoChange}
                            disabled={loading || uploadingPhoto}
                            className="hidden"
                        />
                    </label>
                </div>
            </div>

            {/* Name */}
            <div className="mb-5">
                <label className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-300">
                    Full Name
                </label>

                <div className="relative">
                    <User
                        size={18}
                        className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                    />

                    <input
                        type="text"
                        value={name}
                        onChange={(event) => setName(event.target.value)}
                        disabled={loading || saving}
                        placeholder="Nama Anda"
                        className="w-full rounded-xl border border-slate-200 bg-white px-10 py-3 text-sm outline-none transition focus:border-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                    />
                </div>
            </div>

            {/* Email */}
            <div className="mb-8">
                <label className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-300">
                    Email
                </label>

                <div className="relative">
                    <Mail
                        size={18}
                        className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                    />

                    <input
                        type="email"
                        value={email}
                        readOnly
                        disabled={loading}
                        placeholder="email@anda.com"
                        className="w-full rounded-xl border border-slate-200 bg-white px-10 py-3 text-sm outline-none transition focus:border-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                    />
                </div>
            </div>

            {error && (
                <p className="mb-4 text-sm text-red-600">{error}</p>
            )}

            {message && (
                <p className="mb-4 text-sm text-emerald-600">{message}</p>
            )}

            <div className="flex justify-end">
                <button
                    type="button"
                    onClick={handleSave}
                    disabled={loading || saving}
                    className="flex items-center gap-2 rounded-xl bg-slate-900 px-5 py-3 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                >
                    <Save size={16} />
                    {saving ? "Menyimpan..." : "Simpan Perubahan"}
                </button>
            </div>
        </div>
    );
}