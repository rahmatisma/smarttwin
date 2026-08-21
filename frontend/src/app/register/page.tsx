"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
    User,
    Mail,
    Lock,
} from "lucide-react";

import { supabase } from "@/lib/supabaseClient";

export default function RegisterPage() {
    const router = useRouter();

    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [info, setInfo] = useState<string | null>(null);

    async function handleSubmit(
        event: React.FormEvent<HTMLFormElement>
    ) {
        event.preventDefault();

        setError(null);
        setInfo(null);

        if (password !== confirmPassword) {
            setError("Password dan konfirmasi password tidak sama.");
            return;
        }

        setLoading(true);

        const { data, error: signUpError } = await supabase.auth.signUp({
            email,
            password,
            options: {
                data: {
                    name,
                },
            },
        });

        setLoading(false);

        if (signUpError) {
            setError(signUpError.message);
            return;
        }

        /*
         * Kalau project Supabase mewajibkan konfirmasi email,
         * signUp tidak langsung mengembalikan session.
         */
        if (!data.session) {
            setInfo(
                "Akun berhasil dibuat. Silakan cek email untuk konfirmasi sebelum masuk."
            );
            return;
        }

        router.replace("/dashboard");
        router.refresh();
    }

    return (
        <main className="flex min-h-screen items-center justify-center bg-background px-4 py-8">

            <div className="w-full max-w-md">

                {/* LOGO */}
                <div className="mb-8 text-center">

                    <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-signal-green/10 ring-1 ring-signal-green/30">
                        <div className="h-3 w-3 rounded-full bg-signal-green" />
                    </div>

                    <h1 className="font-display text-2xl font-semibold text-text">
                        SmartTwin
                    </h1>

                    <p className="mt-2 text-sm text-text-muted">
                        Create your SmartTwin account
                    </p>

                </div>

                {/* CARD */}
                <div className="rounded-xl border border-border bg-surface p-6">

                    <div className="mb-6">
                        <h2 className="font-display text-lg font-semibold text-text">
                            Create Account
                        </h2>

                        <p className="mt-1 text-xs text-text-muted">
                            Daftarkan akun baru untuk menggunakan SmartTwin.
                        </p>
                    </div>

                    <form
                        onSubmit={handleSubmit}
                        className="space-y-4"
                    >

                        {/* NAME */}
                        <div>

                            <label className="mb-2 block text-xs text-text-secondary">
                                Nama Lengkap
                            </label>

                            <div className="relative">

                                <User className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />

                                <input
                                    type="text"
                                    value={name}
                                    onChange={(event) =>
                                        setName(event.target.value)
                                    }
                                    placeholder="Nama lengkap"
                                    required
                                    className="w-full rounded-lg border border-border bg-surface-2 py-2.5 pl-10 pr-3 text-sm text-text outline-none placeholder:text-text-muted focus:border-accent"
                                />

                            </div>
                        </div>

                        {/* EMAIL */}
                        <div>

                            <label className="mb-2 block text-xs text-text-secondary">
                                Email
                            </label>

                            <div className="relative">

                                <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />

                                <input
                                    type="email"
                                    value={email}
                                    onChange={(event) =>
                                        setEmail(event.target.value)
                                    }
                                    placeholder="nama@email.com"
                                    required
                                    className="w-full rounded-lg border border-border bg-surface-2 py-2.5 pl-10 pr-3 text-sm text-text outline-none placeholder:text-text-muted focus:border-accent"
                                />

                            </div>
                        </div>

                        {/* PASSWORD */}
                        <div>

                            <label className="mb-2 block text-xs text-text-secondary">
                                Password
                            </label>

                            <div className="relative">

                                <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />

                                <input
                                    type="password"
                                    value={password}
                                    onChange={(event) =>
                                        setPassword(event.target.value)
                                    }
                                    placeholder="Minimal 8 karakter"
                                    minLength={8}
                                    required
                                    className="w-full rounded-lg border border-border bg-surface-2 py-2.5 pl-10 pr-3 text-sm text-text outline-none placeholder:text-text-muted focus:border-accent"
                                />

                            </div>

                        </div>

                        {/* CONFIRM PASSWORD */}
                        <div>

                            <label className="mb-2 block text-xs text-text-secondary">
                                Konfirmasi Password
                            </label>

                            <div className="relative">

                                <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />

                                <input
                                    type="password"
                                    value={confirmPassword}
                                    onChange={(event) =>
                                        setConfirmPassword(event.target.value)
                                    }
                                    placeholder="Ulangi password"
                                    minLength={8}
                                    required
                                    className="w-full rounded-lg border border-border bg-surface-2 py-2.5 pl-10 pr-3 text-sm text-text outline-none placeholder:text-text-muted focus:border-accent"
                                />

                            </div>

                        </div>

                        {/* ERROR / INFO */}
                        {error && (
                            <p className="text-xs text-red-400">
                                {error}
                            </p>
                        )}

                        {info && (
                            <p className="text-xs text-signal-green">
                                {info}
                            </p>
                        )}

                        {/* REGISTER */}
                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-background transition hover:opacity-90 disabled:opacity-60"
                        >
                            {loading ? "Creating account..." : "Create Account"}
                        </button>

                    </form>

                    {/* LOGIN */}
                    <div className="mt-6 border-t border-border pt-5 text-center">

                        <p className="text-xs text-text-muted">
                            Sudah punya akun?
                        </p>

                        <Link
                            href="/login"
                            className="mt-1 inline-block text-xs font-medium text-accent hover:text-text"
                        >
                            Sign in →
                        </Link>

                    </div>

                </div>

                <p className="mt-6 text-center text-[10px] text-text-muted">
                    SmartTwin Traffic Management System
                </p>

            </div>

        </main>
    );
}
