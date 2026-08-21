"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
    Lock,
    LogOut,
    ChevronRight,
} from "lucide-react";

import Sidebar from "@/components/Sidebar";
import AccountProfile from "@/components/account/AccountProfile";
import EditProfileModal from "@/components/account/EditProfileModal";
import ChangePasswordModal from "@/components/account/ChangePasswordModal";
import { supabase } from "@/lib/supabaseClient";

export default function AccountPage() {
    const router = useRouter();

    const [name, setName] = useState("");
    const [email, setEmail] = useState("");

    const [showEditProfile, setShowEditProfile] =
        useState(false);

    const [showChangePassword, setShowChangePassword] =
        useState(false);

    const [loggingOut, setLoggingOut] = useState(false);

    useEffect(() => {
        async function loadUser() {
            const { data, error } =
                await supabase.auth.getUser();

            if (error) {
                console.error(error);
                return;
            }

            const user = data.user;

            if (!user) {
                router.replace("/login");
                return;
            }

            const userName =
                (user.user_metadata?.name as string | undefined) ??
                user.email ??
                "";

            setName(userName);
            setEmail(user.email ?? "");
        }

        loadUser();
    }, [router]);

    async function handleLogout() {
        setLoggingOut(true);

        await supabase.auth.signOut();

        router.replace("/login");
        router.refresh();
    }

    return (
        <div className="flex h-screen overflow-hidden bg-background text-text">

            <Sidebar />

            <div className="min-w-0 flex-1 overflow-y-auto">

                <main className="min-h-full px-5 py-6 md:px-7">

                    <div className="mx-auto max-w-[1200px]">

                        {/* HEADER */}

                        <div className="mb-6">
                            <div className="flex items-center gap-2">

                                <span className="h-2.5 w-2.5 rounded-full bg-signal-green" />

                                <h1 className="font-display text-2xl font-semibold">
                                    Account
                                </h1>

                            </div>

                            <p className="mt-1 text-sm text-text-muted">
                                Kelola informasi akun dan keamanan SmartTwin.
                            </p>
                        </div>

                        {/* PROFILE */}

                        <AccountProfile
                            name={name}
                            email={email}
                            onEditProfile={() =>
                                setShowEditProfile(true)
                            }
                        />

                        {/* SECURITY */}

                        <div className="mb-5 rounded-xl border border-border bg-surface">

                            <div className="border-b border-border p-5">

                                <h2 className="font-display text-sm font-semibold">
                                    Security
                                </h2>

                                <p className="mt-1 text-xs text-text-muted">
                                    Kelola keamanan akun kamu.
                                </p>

                            </div>

                            <div className="flex items-center gap-4 p-5">

                                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-surface-2">
                                    <Lock className="h-4 w-4 text-text-secondary" />
                                </div>

                                <div className="flex-1">

                                    <p className="text-sm font-medium">
                                        Password
                                    </p>

                                    <p className="mt-1 text-xs text-text-muted">
                                        Ubah password untuk menjaga keamanan akun.
                                    </p>

                                </div>

                                <button
                                    type="button"
                                    onClick={() =>
                                        setShowChangePassword(true)
                                    }
                                    className="flex items-center gap-1 text-xs text-accent hover:text-text"
                                >
                                    Ubah Password
                                    <ChevronRight className="h-3.5 w-3.5" />
                                </button>

                            </div>

                        </div>

                        {/* SESSION */}

                        <div className="rounded-xl border border-border bg-surface">

                            <div className="border-b border-border p-5">

                                <h2 className="font-display text-sm font-semibold">
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

                                    <p className="text-sm font-medium">
                                        Sesi saat ini
                                    </p>

                                    <p className="mt-1 text-xs text-text-muted">
                                        Kamu sedang menggunakan SmartTwin.
                                    </p>

                                </div>

                                <button
                                    type="button"
                                    onClick={handleLogout}
                                    disabled={loggingOut}
                                    className="flex items-center justify-center gap-2 rounded-lg border border-red-400/30 px-4 py-2 text-xs text-red-300 hover:bg-red-400/10 disabled:opacity-60"
                                >
                                    <LogOut className="h-3.5 w-3.5" />

                                    {loggingOut
                                        ? "Logging out..."
                                        : "Logout"}
                                </button>

                            </div>

                        </div>

                    </div>

                </main>

            </div>

            {/* EDIT PROFILE */}

            <EditProfileModal
                key={showEditProfile ? `profile-${name}` : "profile-closed"}
                open={showEditProfile}
                name={name}
                email={email}
                onClose={() => setShowEditProfile(false)}
                onSaved={(updatedName) => {
                    setName(updatedName);
                }}
            />

            {/* CHANGE PASSWORD */}

            <ChangePasswordModal
                open={showChangePassword}
                email={email}
                onClose={() =>
                    setShowChangePassword(false)
                }
            />

        </div>
    );
}