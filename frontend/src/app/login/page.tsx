"use client";

import Link from "next/link";
import { Lock, Mail } from "lucide-react";

export default function LoginPage() {
    function handleSubmit(
        event: React.FormEvent<HTMLFormElement>
    ) {
        event.preventDefault();

        alert(
            "Login sementara. Nanti akan dihubungkan ke backend."
        );
    }

    return (
        <main className="flex min-h-screen items-center justify-center bg-background px-4">

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
                        Sign in to your SmartTwin account
                    </p>

                </div>

                {/* CARD */}
                <div className="rounded-xl border border-border bg-surface p-6">

                    <div className="mb-6">
                        <h2 className="font-display text-lg font-semibold text-text">
                            Welcome back
                        </h2>

                        <p className="mt-1 text-xs text-text-muted">
                            Masuk untuk mengakses dashboard SmartTwin.
                        </p>
                    </div>

                    <form
                        onSubmit={handleSubmit}
                        className="space-y-4"
                    >

                        {/* EMAIL */}
                        <div>

                            <label className="mb-2 block text-xs text-text-secondary">
                                Email
                            </label>

                            <div className="relative">

                                <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />

                                <input
                                    type="email"
                                    placeholder="nama@email.com"
                                    required
                                    className="w-full rounded-lg border border-border bg-surface-2 py-2.5 pl-10 pr-3 text-sm text-text outline-none placeholder:text-text-muted focus:border-accent"
                                />

                            </div>
                        </div>

                        {/* PASSWORD */}
                        <div>

                            <div className="mb-2 flex items-center justify-between">

                                <label className="text-xs text-text-secondary">
                                    Password
                                </label>

                                <button
                                    type="button"
                                    className="text-[11px] text-accent hover:text-text"
                                >
                                    Lupa password?
                                </button>

                            </div>

                            <div className="relative">

                                <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />

                                <input
                                    type="password"
                                    placeholder="••••••••"
                                    required
                                    className="w-full rounded-lg border border-border bg-surface-2 py-2.5 pl-10 pr-3 text-sm text-text outline-none placeholder:text-text-muted focus:border-accent"
                                />

                            </div>

                        </div>

                        {/* LOGIN */}
                        <button
                            type="submit"
                            className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-background transition hover:opacity-90"
                        >
                            Sign In
                        </button>

                    </form>

                    {/* REGISTER */}
                    <div className="mt-6 border-t border-border pt-5 text-center">

                        <p className="text-xs text-text-muted">
                            Belum punya akun?
                        </p>

                        <Link
                            href="/register"
                            className="mt-1 inline-block text-xs font-medium text-accent hover:text-text"
                        >
                            Buat akun baru →
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