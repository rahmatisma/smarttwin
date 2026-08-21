"use client";

import { useState } from "react";
import {
    User,
    Mail,
    X,
    Save,
} from "lucide-react";

import { supabase } from "@/lib/supabaseClient";

interface EditProfileModalProps {
    open: boolean;
    name: string;
    email: string;
    onClose: () => void;
    onSaved: (name: string) => void;
}

export default function EditProfileModal({
    open,
    name,
    email,
    onClose,
    onSaved,
}: EditProfileModalProps) {

    const [editName, setEditName] = useState(name);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState("");

    if (!open) {
        return null;
    }

    async function handleSave() {

        const trimmedName = editName.trim();

        if (!trimmedName) {
            setMessage("Nama tidak boleh kosong.");
            return;
        }

        try {

            setSaving(true);
            setMessage("");

            const { data, error } =
                await supabase.auth.updateUser({
                    data: {
                        name: trimmedName,
                    },
                });

            if (error) {
                throw error;
            }

            const updatedName =
                (data.user?.user_metadata?.name as string) ??
                trimmedName;

            onSaved(updatedName);

            setMessage(
                "Profile berhasil diperbarui."
            );

            setTimeout(() => {
                onClose();
            }, 800);

        } catch (error) {

            console.error(error);

            setMessage(
                error instanceof Error
                    ? error.message
                    : "Gagal memperbarui profile."
            );

        } finally {
            setSaving(false);
        }
    }

    const initials =
        editName
            .split(" ")
            .filter(Boolean)
            .slice(0, 2)
            .map((part) =>
                part[0]?.toUpperCase()
            )
            .join("") || "SM";

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
            onMouseDown={(event) => {
                if (
                    event.target ===
                    event.currentTarget &&
                    !saving
                ) {
                    onClose();
                }
            }}
        >

            <div className="w-full max-w-md overflow-hidden rounded-xl border border-border bg-surface shadow-2xl">

                <div className="flex items-center justify-between border-b border-border px-5 py-4">

                    <div>

                        <h2 className="font-display text-sm font-semibold">
                            Edit Profile
                        </h2>

                        <p className="mt-1 text-xs text-text-muted">
                            Perbarui informasi profile kamu.
                        </p>

                    </div>

                    <button
                        type="button"
                        onClick={onClose}
                        disabled={saving}
                        className="rounded-md p-1.5 text-text-muted hover:bg-surface-2 hover:text-text"
                    >
                        <X className="h-4 w-4" />
                    </button>

                </div>

                <div className="space-y-4 p-5">

                    {/* AVATAR */}

                    <div className="flex items-center gap-3 rounded-lg border border-border bg-surface-2 p-4">

                        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent-dim ring-1 ring-accent/30">

                            <span className="font-display font-semibold text-accent">
                                {initials}
                            </span>

                        </div>

                        <div>

                            <p className="text-sm font-medium">
                                Foto Profile
                            </p>

                            <p className="mt-1 text-xs text-text-muted">
                                Avatar menggunakan inisial nama.
                            </p>

                        </div>

                    </div>

                    {/* NAME */}

                    <div>

                        <label className="mb-2 block text-xs text-text-muted">
                            Nama
                        </label>

                        <div className="relative">

                            <User className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />

                            <input
                                type="text"
                                value={editName}
                                onChange={(e) =>
                                    setEditName(e.target.value)
                                }
                                disabled={saving}
                                className="w-full rounded-lg border border-border bg-surface-2 py-2.5 pl-10 pr-3 text-sm outline-none focus:border-accent"
                            />

                        </div>

                    </div>

                    {/* EMAIL */}

                    <div>

                        <label className="mb-2 block text-xs text-text-muted">
                            Email
                        </label>

                        <div className="relative">

                            <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />

                            <input
                                type="email"
                                value={email}
                                disabled
                                className="w-full rounded-lg border border-border bg-surface-2 py-2.5 pl-10 text-sm text-text-muted"
                            />

                        </div>

                    </div>

                    {message && (
                        <div className="rounded-lg border border-signal-green/30 bg-signal-green/10 px-3 py-2.5 text-xs text-signal-green">
                            {message}
                        </div>
                    )}

                </div>

                <div className="flex justify-end gap-2 border-t border-border px-5 py-4">

                    <button
                        type="button"
                        onClick={onClose}
                        disabled={saving}
                        className="rounded-lg border border-border px-4 py-2.5 text-xs"
                    >
                        Batal
                    </button>

                    <button
                        type="button"
                        onClick={handleSave}
                        disabled={
                            saving ||
                            !editName.trim()
                        }
                        className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-50"
                    >

                        <Save className="h-3.5 w-3.5" />

                        {saving
                            ? "Menyimpan..."
                            : "Simpan Perubahan"}

                    </button>

                </div>

            </div>

        </div>
    );
}