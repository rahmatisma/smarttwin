"use client";

import {
    User,
    Mail,
    Lock,
    Pencil,
} from "lucide-react";
import Image from "next/image";

interface AccountProfileProps {
    name: string;
    email: string;
    avatarUrl?: string;
    onEditProfile: () => void;
}

export default function AccountProfile({
    name,
    email,
    avatarUrl,
    onEditProfile,
}: AccountProfileProps) {

    const initials =
        name
            .split(" ")
            .filter(Boolean)
            .slice(0, 2)
            .map((part) =>
                part[0]?.toUpperCase()
            )
            .join("") || "SM";

    return (
        <div className="mb-5 rounded-xl border border-border bg-surface">

            <div className="flex flex-col gap-5 border-b border-border p-5 sm:flex-row sm:items-center">

                <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full bg-accent-dim ring-1 ring-accent/30">

                    {avatarUrl ? (
                        <Image
                            src={avatarUrl}
                            alt="Foto profil"
                            width={80}
                            height={80}
                            unoptimized
                            className="h-full w-full rounded-full object-cover"
                        />
                    ) : (
                        <span className="font-display text-2xl font-semibold text-accent">
                            {initials}
                        </span>
                    )}

                </div>

                <div className="flex-1">

                    <h2 className="font-display text-lg font-semibold">
                        {name || "Memuat..."}
                    </h2>

                    <p className="mt-1 text-sm text-text-muted">
                        {email || "-"}
                    </p>

                    <div className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-signal-green/10 px-2.5 py-1 text-[11px] text-signal-green">

                        <span className="h-1.5 w-1.5 rounded-full bg-signal-green" />

                        Account aktif

                    </div>

                </div>

                <button
                    type="button"
                    onClick={onEditProfile}
                    className="flex items-center justify-center gap-2 rounded-lg border border-border px-3 py-2 text-xs text-text-secondary hover:bg-surface-2 hover:text-text"
                >
                    <Pencil className="h-3.5 w-3.5" />
                    Edit Profile
                </button>

            </div>

            <div className="p-5">

                <div className="mb-4">

                    <h3 className="font-display text-sm font-semibold">
                        Informasi Profile
                    </h3>

                    <p className="mt-1 text-xs text-text-muted">
                        Informasi dasar akun SmartTwin.
                    </p>

                </div>

                <div className="grid gap-4 md:grid-cols-2">

                    <div className="rounded-lg border border-border bg-surface-2 p-4">

                        <div className="flex items-center gap-2 text-text-muted">

                            <User className="h-4 w-4" />

                            <span className="text-xs">
                                Nama
                            </span>

                        </div>

                        <p className="mt-2 text-sm">
                            {name || "-"}
                        </p>

                    </div>

                    <div className="rounded-lg border border-border bg-surface-2 p-4">

                        <div className="flex items-center gap-2 text-text-muted">

                            <Mail className="h-4 w-4" />

                            <span className="text-xs">
                                Email
                            </span>

                        </div>

                        <p className="mt-2 text-sm">
                            {email || "-"}
                        </p>

                    </div>

                    <div className="rounded-lg border border-border bg-surface-2 p-4 md:col-span-2">

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
    );
}