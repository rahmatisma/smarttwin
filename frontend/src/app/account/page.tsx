"use client";

import Link from "next/link";
import {
    User,
    Mail,
    Shield,
    Lock,
    LogOut,
    Pencil,
    ChevronRight,
} from "lucide-react";

import Sidebar from "@/components/Sidebar";

export default function AccountPage() {
    return (
        <div className="flex h-screen overflow-hidden bg-background text-text">

            {/* =====================================================
          SIDEBAR
          ===================================================== */}
            <Sidebar />

            {/* =====================================================
          ACCOUNT CONTENT
          ===================================================== */}
            <div className="min-w-0 flex-1 overflow-y-auto">

                <main className="min-h-full px-5 py-6 md:px-7">

                    <div className="mx-auto max-w-[1200px]">

                        {/* PAGE HEADER */}
                        <div className="mb-6">
                            <div className="flex items-center gap-2">
                                <span className="h-2.5 w-2.5 rounded-full bg-signal-green" />

                                <h1 className="font-display text-2xl font-semibold text-text">
                                    Account
                                </h1>
                            </div>

                            <p className="mt-1 text-sm text-text-muted">
                                Kelola informasi akun dan keamanan SmartTwin.
                            </p>
                        </div>

                        {/* =================================================
                PROFILE CARD
            ================================================= */}
                        <div className="mb-5 rounded-xl border border-border bg-surface">

                            {/* PROFILE HEADER */}
                            <div className="flex flex-col gap-5 border-b border-border p-5 sm:flex-row sm:items-center">

                                {/* AVATAR */}
                                <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full bg-accent-dim ring-1 ring-accent/30">
                                    <span className="font-display text-2xl font-semibold text-accent">
                                        SM
                                    </span>
                                </div>

                                {/* USER INFO */}
                                <div className="flex-1">
                                    <h2 className="font-display text-lg font-semibold text-text">
                                        Santi Melvira
                                    </h2>

                                    <p className="mt-1 text-sm text-text-muted">
                                        santi@example.com
                                    </p>

                                    <div className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-signal-green/10 px-2.5 py-1 text-[11px] text-signal-green">
                                        <span className="h-1.5 w-1.5 rounded-full bg-signal-green" />
                                        Account aktif
                                    </div>
                                </div>

                                {/* EDIT */}
                                <button
                                    type="button"
                                    className="flex items-center justify-center gap-2 rounded-lg border border-border px-3 py-2 text-xs text-text-secondary transition hover:bg-surface-2 hover:text-text"
                                >
                                    <Pencil className="h-3.5 w-3.5" />
                                    Edit Profile
                                </button>

                            </div>

                            {/* PROFILE INFORMATION */}
                            <div className="p-5">

                                <div className="mb-4">
                                    <h3 className="font-display text-sm font-semibold text-text">
                                        Informasi Profile
                                    </h3>

                                    <p className="mt-1 text-xs text-text-muted">
                                        Informasi dasar akun SmartTwin.
                                    </p>
                                </div>

                                <div className="grid gap-4 md:grid-cols-2">

                                    {/* NAME */}
                                    <div className="rounded-lg border border-border bg-surface-2 p-4">
                                        <div className="flex items-center gap-2 text-text-muted">
                                            <User className="h-4 w-4" />

                                            <span className="text-xs">
                                                Nama
                                            </span>
                                        </div>

                                        <p className="mt-2 text-sm text-text">
                                            Santi Melvira
                                        </p>
                                    </div>

                                    {/* EMAIL */}
                                    <div className="rounded-lg border border-border bg-surface-2 p-4">
                                        <div className="flex items-center gap-2 text-text-muted">
                                            <Mail className="h-4 w-4" />

                                            <span className="text-xs">
                                                Email
                                            </span>
                                        </div>

                                        <p className="mt-2 text-sm text-text">
                                            santi@example.com
                                        </p>
                                    </div>

                                    {/* ROLE */}
                                    <div className="rounded-lg border border-border bg-surface-2 p-4">
                                        <div className="flex items-center gap-2 text-text-muted">
                                            <Shield className="h-4 w-4" />

                                            <span className="text-xs">
                                                Role
                                            </span>
                                        </div>

                                        <p className="mt-2 text-sm text-text">
                                            Administrator
                                        </p>
                                    </div>

                                    {/* STATUS */}
                                    <div className="rounded-lg border border-border bg-surface-2 p-4">
                                        <div className="flex items-center gap-2 text-text-muted">
                                            <Lock className="h-4 w-4" />

                                            <span className="text-xs">
                                                Status
                                            </span>
                                        </div>

                                        <p className="mt-2 text-sm text-signal-green">
                                            Aktif
                                        </p>
                                    </div>

                                </div>
                            </div>
                        </div>

                        {/* =================================================
                SECURITY
            ================================================= */}
                        <div className="mb-5 rounded-xl border border-border bg-surface">

                            <div className="border-b border-border p-5">
                                <h2 className="font-display text-sm font-semibold text-text">
                                    Security
                                </h2>

                                <p className="mt-1 text-xs text-text-muted">
                                    Kelola keamanan akun kamu.
                                </p>
                            </div>

                            <div className="divide-y divide-border">

                                {/* PASSWORD */}
                                <div className="flex items-center gap-4 p-5">

                                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-surface-2">
                                        <Lock className="h-4 w-4 text-text-secondary" />
                                    </div>

                                    <div className="flex-1">
                                        <p className="text-sm font-medium text-text">
                                            Password
                                        </p>

                                        <p className="mt-1 text-xs text-text-muted">
                                            Password terakhir diperbarui belum tersedia.
                                        </p>
                                    </div>

                                    <button
                                        type="button"
                                        className="flex items-center gap-1 text-xs text-accent transition hover:text-text"
                                    >
                                        Ubah Password

                                        <ChevronRight className="h-3.5 w-3.5" />
                                    </button>

                                </div>

                            </div>
                        </div>

                        {/* =================================================
                SESSION
            ================================================= */}
                        <div className="rounded-xl border border-border bg-surface">

                            <div className="border-b border-border p-5">
                                <h2 className="font-display text-sm font-semibold text-text">
                                    Session
                                </h2>

                                <p className="mt-1 text-xs text-text-muted">
                                    Kelola sesi login akun ini.
                                </p>
                            </div>

                            <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center">

                                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-signal-green/10">
                                    <span className="h-2.5 w-2.5 rounded-full bg-signal-green" />
                                </div>

                                <div className="flex-1">
                                    <p className="text-sm font-medium text-text">
                                        Sesi saat ini
                                    </p>

                                    <p className="mt-1 text-xs text-text-muted">
                                        Kamu sedang menggunakan SmartTwin.
                                    </p>
                                </div>

                                <button
                                    type="button"
                                    className="flex items-center justify-center gap-2 rounded-lg border border-red-400/30 px-4 py-2 text-xs text-red-300 transition hover:bg-red-400/10"
                                >
                                    <LogOut className="h-3.5 w-3.5" />

                                    Logout
                                </button>

                            </div>
                        </div>

                        {/* LOGIN LINK — sementara untuk testing */}
                        <div className="mt-5 pb-6 text-center">
                            <Link
                                href="/login"
                                className="text-xs text-text-muted transition hover:text-accent"
                            >
                                Buka halaman Login →
                            </Link>
                        </div>

                    </div>

                </main>

            </div>
        </div>
    );
}