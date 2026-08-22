"use client";

import { useState } from "react";
import {
    Shield,
    Lock,
    LogOut,
    Smartphone,
    Eye,
    EyeOff,
    CheckCircle2,
    AlertCircle,
} from "lucide-react";

import { supabase } from "@/lib/supabaseClient";

export default function SecuritySettings() {
    const [showCurrentPassword, setShowCurrentPassword] =
        useState(false);

    const [showNewPassword, setShowNewPassword] =
        useState(false);

    const [showConfirmPassword, setShowConfirmPassword] =
        useState(false);

    const [currentPassword, setCurrentPassword] =
        useState("");

    const [newPassword, setNewPassword] =
        useState("");

    const [confirmPassword, setConfirmPassword] =
        useState("");

    const [updatingPassword, setUpdatingPassword] =
        useState(false);

    const [loggingOut, setLoggingOut] =
        useState(false);

    const [successMessage, setSuccessMessage] =
        useState("");

    const [errorMessage, setErrorMessage] =
        useState("");

    /*
     * ==========================================
     * UPDATE PASSWORD
     * ==========================================
     */

    async function handleUpdatePassword() {
        setSuccessMessage("");
        setErrorMessage("");

        if (!currentPassword) {
            setErrorMessage(
                "Current password wajib diisi."
            );
            return;
        }

        if (!newPassword) {
            setErrorMessage(
                "New password wajib diisi."
            );
            return;
        }

        if (!confirmPassword) {
            setErrorMessage(
                "Confirm new password wajib diisi."
            );
            return;
        }

        if (newPassword.length < 6) {
            setErrorMessage(
                "Password baru minimal 6 karakter."
            );
            return;
        }

        if (newPassword !== confirmPassword) {
            setErrorMessage(
                "Password baru dan konfirmasi password tidak sama."
            );
            return;
        }

        if (currentPassword === newPassword) {
            setErrorMessage(
                "Password baru harus berbeda dari password lama."
            );
            return;
        }

        setUpdatingPassword(true);

        try {
            /*
             * GET CURRENT USER
             */

            const {
                data: userData,
                error: userError,
            } = await supabase.auth.getUser();

            if (userError) {
                throw userError;
            }

            const user = userData.user;

            if (!user || !user.email) {
                throw new Error(
                    "User tidak ditemukan. Silakan login kembali."
                );
            }

            /*
             * VERIFY CURRENT PASSWORD
             *
             * Login ulang menggunakan password lama.
             */

            const {
                error: signInError,
            } = await supabase.auth.signInWithPassword({
                email: user.email,
                password: currentPassword,
            });

            if (signInError) {
                throw new Error(
                    "Current password salah."
                );
            }

            /*
             * UPDATE PASSWORD
             */

            const {
                error: updateError,
            } = await supabase.auth.updateUser({
                password: newPassword,
            });

            if (updateError) {
                throw updateError;
            }

            /*
             * SUCCESS
             */

            setCurrentPassword("");
            setNewPassword("");
            setConfirmPassword("");

            setSuccessMessage(
                "Password berhasil diperbarui."
            );
        } catch (error) {
            console.error(
                "Failed to update password:",
                error
            );

            setErrorMessage(
                error instanceof Error
                    ? error.message
                    : "Gagal memperbarui password."
            );
        } finally {
            setUpdatingPassword(false);
        }
    }

    /*
     * ==========================================
     * SIGN OUT ALL DEVICES
     * ==========================================
     */

    async function handleSignOutAll() {
        const confirmed = window.confirm(
            "Apakah kamu yakin ingin sign out dari semua perangkat?"
        );

        if (!confirmed) return;

        setLoggingOut(true);
        setSuccessMessage("");
        setErrorMessage("");

        try {
            const {
                error,
            } = await supabase.auth.signOut({
                scope: "global",
            });

            if (error) {
                throw error;
            }

            window.location.href = "/login";
        } catch (error) {
            console.error(
                "Failed to sign out from all devices:",
                error
            );

            setErrorMessage(
                "Gagal sign out dari semua perangkat."
            );

            setLoggingOut(false);
        }
    }

    return (
        <div className="w-full md:pl-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">

                {/* ================================= */}
                {/* HEADER */}
                {/* ================================= */}

                <div className="border-b border-slate-100 pb-6 dark:border-slate-800">

                    <div className="flex items-center gap-3">

                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 dark:bg-slate-800">

                            <Shield
                                size={20}
                                className="text-slate-600 dark:text-slate-300"
                            />

                        </div>

                        <div>

                            <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
                                Security
                            </h2>

                            <p className="text-sm text-slate-500 dark:text-slate-400">
                                Manage your account password and active sessions.
                            </p>

                        </div>

                    </div>

                </div>

                {/* ================================= */}
                {/* PASSWORD */}
                {/* ================================= */}

                <div className="border-b border-slate-100 py-6 dark:border-slate-800">

                    <div className="mb-6 flex items-center gap-3">

                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 dark:bg-slate-800">

                            <Lock
                                size={20}
                                className="text-slate-600 dark:text-slate-300"
                            />

                        </div>

                        <div>

                            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                                Password
                            </h3>

                            <p className="text-sm text-slate-500 dark:text-slate-400">
                                Update your account password.
                            </p>

                        </div>

                    </div>

                    <div className="space-y-5">

                        {/* CURRENT PASSWORD */}

                        <PasswordInput
                            label="Current Password"
                            value={currentPassword}
                            onChange={setCurrentPassword}
                            showPassword={
                                showCurrentPassword
                            }
                            onToggle={() =>
                                setShowCurrentPassword(
                                    (current) =>
                                        !current
                                )
                            }
                        />

                        {/* NEW PASSWORD */}

                        <PasswordInput
                            label="New Password"
                            value={newPassword}
                            onChange={setNewPassword}
                            showPassword={
                                showNewPassword
                            }
                            onToggle={() =>
                                setShowNewPassword(
                                    (current) =>
                                        !current
                                )
                            }
                        />

                        {/* CONFIRM PASSWORD */}

                        <PasswordInput
                            label="Confirm New Password"
                            value={confirmPassword}
                            onChange={setConfirmPassword}
                            showPassword={
                                showConfirmPassword
                            }
                            onToggle={() =>
                                setShowConfirmPassword(
                                    (current) =>
                                        !current
                                )
                            }
                        />

                    </div>

                    {/* PASSWORD REQUIREMENT */}

                    <p className="mt-3 text-xs text-slate-400">
                        Password baru minimal 6 karakter.
                    </p>

                    {/* ERROR */}

                    {errorMessage && (
                        <div className="mt-5 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-600 dark:border-red-900 dark:bg-red-950/40 dark:text-red-400">

                            <AlertCircle
                                size={17}
                                className="mt-0.5 shrink-0"
                            />

                            <span>
                                {errorMessage}
                            </span>

                        </div>
                    )}

                    {/* SUCCESS */}

                    {successMessage && (
                        <div className="mt-5 flex items-start gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-600 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-400">

                            <CheckCircle2
                                size={17}
                                className="mt-0.5 shrink-0"
                            />

                            <span>
                                {successMessage}
                            </span>

                        </div>
                    )}

                    {/* UPDATE BUTTON */}

                    <div className="mt-6 flex justify-end">

                        <button
                            type="button"
                            onClick={
                                handleUpdatePassword
                            }
                            disabled={
                                updatingPassword
                            }
                            className="rounded-xl bg-slate-900 px-5 py-3 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                        >
                            {updatingPassword
                                ? "Updating..."
                                : "Update Password"}
                        </button>

                    </div>

                </div>

                {/* ================================= */}
                {/* ACTIVE SESSION */}
                {/* ================================= */}

                <div className="pt-6">

                    <div className="mb-6">

                        <div className="flex items-center gap-3">

                            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 dark:bg-slate-800">

                                <Smartphone
                                    size={20}
                                    className="text-slate-500 dark:text-slate-300"
                                />

                            </div>

                            <div>

                                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                                    Active Session
                                </h2>

                                <p className="text-sm text-slate-500 dark:text-slate-400">
                                    Manage the current login session.
                                </p>

                            </div>

                        </div>

                    </div>

                    {/* CURRENT DEVICE */}

                    <div className="flex items-center justify-between gap-4 rounded-xl border border-slate-100 p-4 dark:border-slate-800">

                        <div className="flex min-w-0 items-center gap-3">

                            <Smartphone
                                size={20}
                                className="shrink-0 text-slate-500"
                            />

                            <div className="min-w-0">

                                <p className="text-sm font-medium text-slate-900 dark:text-white">
                                    Current Device
                                </p>

                                <p className="text-xs text-slate-400">
                                    This device • Active now
                                </p>

                            </div>

                        </div>

                        <span className="shrink-0 rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400">
                            Active
                        </span>

                    </div>

                    {/* SIGN OUT ALL */}

                    <button
                        type="button"
                        onClick={
                            handleSignOutAll
                        }
                        disabled={loggingOut}
                        className="mt-5 flex items-center gap-2 rounded-xl border border-red-200 px-4 py-3 text-sm font-medium text-red-600 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-red-900 dark:hover:bg-red-950"
                    >

                        <LogOut size={17} />

                        {loggingOut
                            ? "Signing out..."
                            : "Sign out of all devices"}

                    </button>

                </div>

            </div>
        </div>
    );
}

/*
 * ==========================================
 * PASSWORD INPUT
 * ==========================================
 */

function PasswordInput({
    label,
    value,
    onChange,
    showPassword,
    onToggle,
}: {
    label: string;
    value: string;
    onChange: (value: string) => void;
    showPassword: boolean;
    onToggle: () => void;
}) {
    return (
        <div>

            <label className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-300">
                {label}
            </label>

            <div className="relative">

                <input
                    type={
                        showPassword
                            ? "text"
                            : "password"
                    }
                    value={value}
                    onChange={(e) =>
                        onChange(
                            e.target.value
                        )
                    }
                    autoComplete="current-password"
                    className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 pr-11 text-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200 dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:focus:ring-slate-700"
                    placeholder="••••••••"
                />

                <button
                    type="button"
                    onClick={onToggle}
                    aria-label={
                        showPassword
                            ? "Hide password"
                            : "Show password"
                    }
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 transition hover:text-slate-600 dark:hover:text-slate-200"
                >
                    {showPassword ? (
                        <EyeOff size={18} />
                    ) : (
                        <Eye size={18} />
                    )}
                </button>

            </div>

        </div>
    );
}