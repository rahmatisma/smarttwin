"use client";

import { useState } from "react";
import {
    Shield,
    Lock,
    LogOut,
    Smartphone,
    Eye,
    EyeOff,
} from "lucide-react";

export default function SecuritySettings() {
    const [showPassword, setShowPassword] = useState(false);

    const [currentPassword, setCurrentPassword] = useState("");
    const [newPassword, setNewPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");

    return (
        <div className="space-y-6">
            {/* Password */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <div className="mb-6 flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 dark:bg-slate-800">
                        <Lock
                            size={20}
                            className="text-slate-600 dark:text-slate-300"
                        />
                    </div>

                    <div>
                        <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
                            Password
                        </h2>

                        <p className="text-sm text-slate-500 dark:text-slate-400">
                            Update your account password.
                        </p>
                    </div>
                </div>

                <div className="space-y-5">
                    {/* Current Password */}
                    <PasswordInput
                        label="Current Password"
                        value={currentPassword}
                        onChange={setCurrentPassword}
                        showPassword={showPassword}
                        onToggle={() =>
                            setShowPassword(!showPassword)
                        }
                    />

                    {/* New Password */}
                    <PasswordInput
                        label="New Password"
                        value={newPassword}
                        onChange={setNewPassword}
                        showPassword={showPassword}
                        onToggle={() =>
                            setShowPassword(!showPassword)
                        }
                    />

                    {/* Confirm Password */}
                    <PasswordInput
                        label="Confirm New Password"
                        value={confirmPassword}
                        onChange={setConfirmPassword}
                        showPassword={showPassword}
                        onToggle={() =>
                            setShowPassword(!showPassword)
                        }
                    />
                </div>

                <div className="mt-6 flex justify-end">
                    <button className="rounded-xl bg-slate-900 px-5 py-3 text-sm font-medium text-white hover:bg-slate-800 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200">
                        Update Password
                    </button>
                </div>
            </div>

            {/* Sessions */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <div className="mb-6">
                    <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 dark:bg-slate-800">
                            <Shield
                                size={20}
                                className="text-slate-600 dark:text-slate-300"
                            />
                        </div>

                        <div>
                            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                                Active Sessions
                            </h2>

                            <p className="text-sm text-slate-500 dark:text-slate-400">
                                Manage devices currently signed into your account.
                            </p>
                        </div>
                    </div>
                </div>

                <div className="flex items-center justify-between rounded-xl border border-slate-100 p-4 dark:border-slate-800">
                    <div className="flex items-center gap-3">
                        <Smartphone
                            size={20}
                            className="text-slate-500"
                        />

                        <div>
                            <p className="text-sm font-medium text-slate-900 dark:text-white">
                                Current Device
                            </p>

                            <p className="text-xs text-slate-400">
                                This device • Active now
                            </p>
                        </div>
                    </div>

                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                        Active
                    </span>
                </div>

                <button className="mt-5 flex items-center gap-2 rounded-xl border border-red-200 px-4 py-3 text-sm font-medium text-red-600 hover:bg-red-50 dark:border-red-900 dark:hover:bg-red-950">
                    <LogOut size={17} />
                    Sign out of all devices
                </button>
            </div>
        </div>
    );
}

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
                    type={showPassword ? "text" : "password"}
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 pr-11 text-sm outline-none focus:border-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                    placeholder="••••••••"
                />

                <button
                    type="button"
                    onClick={onToggle}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
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