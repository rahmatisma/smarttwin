"use client";

import { useState } from "react";
import { Lock, Save, X, Eye, EyeOff } from "lucide-react";

import { supabase } from "@/lib/supabaseClient";

interface ChangePasswordModalProps {
    open: boolean;
    email: string;
    onClose: () => void;
}

export default function ChangePasswordModal({
    open,
    email,
    onClose,
}: ChangePasswordModalProps) {
    const [currentPassword, setCurrentPassword] = useState("");
    const [password, setPassword] = useState("");
    const [confirmation, setConfirmation] = useState("");

    const [showCurrentPassword, setShowCurrentPassword] =
        useState(false);

    const [showPassword, setShowPassword] =
        useState(false);

    const [showConfirmation, setShowConfirmation] =
        useState(false);

    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState("");
    const [error, setError] = useState("");

    if (!open) {
        return null;
    }

    async function handleSave() {
        // =====================================================
        // VALIDASI
        // =====================================================

        if (!currentPassword) {
            setError("Masukkan password sebelumnya.");
            return;
        }

        if (!password) {
            setError("Masukkan password baru.");
            return;
        }

        if (password.length < 6) {
            setError(
                "Password baru minimal terdiri dari 6 karakter."
            );
            return;
        }

        if (password === currentPassword) {
            setError(
                "Password baru harus berbeda dari password sebelumnya."
            );
            return;
        }

        if (password !== confirmation) {
            setError(
                "Konfirmasi password tidak cocok."
            );
            return;
        }

        if (!email) {
            setError("Email akun tidak ditemukan.");
            return;
        }

        try {
            setSaving(true);
            setError("");
            setMessage("");

            // =================================================
            // 1. VERIFIKASI PASSWORD SEBELUMNYA
            // =================================================

            const { error: loginError } =
                await supabase.auth.signInWithPassword({
                    email,
                    password: currentPassword,
                });

            if (loginError) {
                setError(
                    "Password sebelumnya salah."
                );
                return;
            }

            // =================================================
            // 2. UPDATE PASSWORD BARU
            // =================================================

            const { error: updateError } =
                await supabase.auth.updateUser({
                    password: password,
                });

            if (updateError) {
                throw updateError;
            }

            // =================================================
            // 3. BERHASIL
            // =================================================

            setCurrentPassword("");
            setPassword("");
            setConfirmation("");

            setMessage(
                "Password berhasil diperbarui."
            );

            // Tutup modal setelah berhasil
            setTimeout(() => {
                onClose();
                setMessage("");
            }, 1000);

        } catch (updateError) {
            console.error(
                "Gagal memperbarui password:",
                updateError
            );

            setError(
                updateError instanceof Error
                    ? updateError.message
                    : "Gagal memperbarui password."
            );
        } finally {
            setSaving(false);
        }
    }

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
            onMouseDown={(event) => {
                if (
                    event.target === event.currentTarget &&
                    !saving
                ) {
                    onClose();
                }
            }}
        >
            <div className="w-full max-w-md overflow-hidden rounded-xl border border-border bg-surface shadow-2xl">

                {/* =================================================
                    HEADER
                ================================================= */}

                <div className="flex items-center justify-between border-b border-border px-5 py-4">

                    <div>
                        <h2 className="font-display text-sm font-semibold text-text">
                            Ubah Password
                        </h2>

                        <p className="mt-1 text-xs text-text-muted">
                            Perbarui password untuk akun {email}.
                        </p>
                    </div>

                    <button
                        type="button"
                        onClick={onClose}
                        disabled={saving}
                        className="rounded-md p-1.5 text-text-muted transition hover:bg-surface-2 hover:text-text disabled:opacity-50"
                        aria-label="Tutup"
                    >
                        <X className="h-4 w-4" />
                    </button>

                </div>

                {/* =================================================
                    BODY
                ================================================= */}

                <div className="space-y-4 p-5">

                    {/* INFO */}

                    <div className="rounded-lg border border-accent/20 bg-accent/5 px-3 py-2.5">

                        <p className="text-xs leading-relaxed text-text-secondary">
                            Masukkan password sebelumnya untuk
                            memverifikasi akun sebelum membuat
                            password baru.
                        </p>

                    </div>

                    {/* =================================================
                        CURRENT PASSWORD
                    ================================================= */}

                    <div>

                        <label className="mb-2 block text-xs text-text-muted">
                            Password Sebelumnya
                        </label>

                        <div className="relative">

                            <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />

                            <input
                                type={
                                    showCurrentPassword
                                        ? "text"
                                        : "password"
                                }
                                value={currentPassword}
                                onChange={(event) => {
                                    setCurrentPassword(
                                        event.target.value
                                    );
                                    setError("");
                                }}
                                placeholder="Masukkan password sebelumnya"
                                disabled={saving}
                                autoComplete="current-password"
                                className="w-full rounded-lg border border-border bg-surface-2 py-2.5 pl-10 pr-10 text-sm text-text outline-none transition placeholder:text-text-muted focus:border-accent disabled:opacity-60"
                            />

                            <button
                                type="button"
                                onClick={() =>
                                    setShowCurrentPassword(
                                        (value) => !value
                                    )
                                }
                                disabled={saving}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text"
                            >
                                {showCurrentPassword ? (
                                    <EyeOff className="h-4 w-4" />
                                ) : (
                                    <Eye className="h-4 w-4" />
                                )}
                            </button>

                        </div>

                    </div>

                    {/* =================================================
                        NEW PASSWORD
                    ================================================= */}

                    <div>

                        <label className="mb-2 block text-xs text-text-muted">
                            Password Baru
                        </label>

                        <div className="relative">

                            <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />

                            <input
                                type={
                                    showPassword
                                        ? "text"
                                        : "password"
                                }
                                value={password}
                                onChange={(event) => {
                                    setPassword(
                                        event.target.value
                                    );
                                    setError("");
                                }}
                                placeholder="Minimal 6 karakter"
                                disabled={saving}
                                autoComplete="new-password"
                                className="w-full rounded-lg border border-border bg-surface-2 py-2.5 pl-10 pr-10 text-sm text-text outline-none transition placeholder:text-text-muted focus:border-accent disabled:opacity-60"
                            />

                            <button
                                type="button"
                                onClick={() =>
                                    setShowPassword(
                                        (value) => !value
                                    )
                                }
                                disabled={saving}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text"
                            >
                                {showPassword ? (
                                    <EyeOff className="h-4 w-4" />
                                ) : (
                                    <Eye className="h-4 w-4" />
                                )}
                            </button>

                        </div>

                    </div>

                    {/* =================================================
                        CONFIRM PASSWORD
                    ================================================= */}

                    <div>

                        <label className="mb-2 block text-xs text-text-muted">
                            Konfirmasi Password Baru
                        </label>

                        <div className="relative">

                            <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />

                            <input
                                type={
                                    showConfirmation
                                        ? "text"
                                        : "password"
                                }
                                value={confirmation}
                                onChange={(event) => {
                                    setConfirmation(
                                        event.target.value
                                    );
                                    setError("");
                                }}
                                placeholder="Ulangi password baru"
                                disabled={saving}
                                autoComplete="new-password"
                                className="w-full rounded-lg border border-border bg-surface-2 py-2.5 pl-10 pr-10 text-sm text-text outline-none transition placeholder:text-text-muted focus:border-accent disabled:opacity-60"
                            />

                            <button
                                type="button"
                                onClick={() =>
                                    setShowConfirmation(
                                        (value) => !value
                                    )
                                }
                                disabled={saving}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text"
                            >
                                {showConfirmation ? (
                                    <EyeOff className="h-4 w-4" />
                                ) : (
                                    <Eye className="h-4 w-4" />
                                )}
                            </button>

                        </div>

                    </div>

                    {/* =================================================
                        ERROR
                    ================================================= */}

                    {error && (
                        <div className="rounded-lg border border-red-400/30 bg-red-400/10 px-3 py-2.5 text-xs text-red-300">
                            {error}
                        </div>
                    )}

                    {/* =================================================
                        SUCCESS
                    ================================================= */}

                    {message && (
                        <div className="rounded-lg border border-signal-green/30 bg-signal-green/10 px-3 py-2.5 text-xs text-signal-green">
                            {message}
                        </div>
                    )}

                </div>

                {/* =================================================
                    FOOTER
                ================================================= */}

                <div className="flex justify-end gap-2 border-t border-border px-5 py-4">

                    <button
                        type="button"
                        onClick={onClose}
                        disabled={saving}
                        className="rounded-lg border border-border px-4 py-2.5 text-xs text-text-secondary transition hover:bg-surface-2 hover:text-text disabled:opacity-50"
                    >
                        Batal
                    </button>

                    <button
                        type="button"
                        onClick={handleSave}
                        disabled={
                            saving ||
                            !currentPassword ||
                            !password ||
                            !confirmation
                        }
                        className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                    >

                        <Save className="h-3.5 w-3.5" />

                        {saving
                            ? "Memverifikasi..."
                            : "Simpan Password"}

                    </button>

                </div>

            </div>
        </div>
    );
}