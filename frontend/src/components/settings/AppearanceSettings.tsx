"use client";

import { useState } from "react";
import { Sun, Moon, Monitor, Languages, Layout } from "lucide-react";

export default function AppearanceSettings() {
    const [theme, setTheme] = useState("system");
    const [language, setLanguage] = useState("id");
    const [compactMode, setCompactMode] = useState(false);

    return (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="mb-8">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
                    Appearance
                </h2>

                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                    Customize how SmartTwin looks and behaves.
                </p>
            </div>

            {/* Theme */}
            <div>
                <div className="mb-4 flex items-center gap-2">
                    <Monitor size={19} className="text-slate-500" />

                    <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                        Theme
                    </h3>
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                    <ThemeOption
                        icon={<Sun size={20} />}
                        label="Light"
                        value="light"
                        selected={theme === "light"}
                        onClick={() => setTheme("light")}
                    />

                    <ThemeOption
                        icon={<Moon size={20} />}
                        label="Dark"
                        value="dark"
                        selected={theme === "dark"}
                        onClick={() => setTheme("dark")}
                    />

                    <ThemeOption
                        icon={<Monitor size={20} />}
                        label="System"
                        value="system"
                        selected={theme === "system"}
                        onClick={() => setTheme("system")}
                    />
                </div>
            </div>

            {/* Language */}
            <div className="mt-8 border-t border-slate-100 pt-6 dark:border-slate-800">
                <label className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-300">
                    <Languages size={18} />
                    Language
                </label>

                <select
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                >
                    <option value="id">Bahasa Indonesia</option>
                    <option value="en">English</option>
                </select>
            </div>

            {/* Compact Mode */}
            <div className="mt-6">
                <div className="flex items-center justify-between rounded-xl border border-slate-100 p-4 dark:border-slate-800">
                    <div className="flex items-center gap-3">
                        <Layout
                            size={19}
                            className="text-slate-500 dark:text-slate-400"
                        />

                        <div>
                            <p className="text-sm font-medium text-slate-900 dark:text-white">
                                Compact Mode
                            </p>

                            <p className="text-xs text-slate-400">
                                Reduce spacing across the dashboard.
                            </p>
                        </div>
                    </div>

                    <button
                        onClick={() => setCompactMode(!compactMode)}
                        className={`relative h-6 w-11 rounded-full transition ${
                            compactMode
                                ? "bg-slate-900 dark:bg-white"
                                : "bg-slate-300 dark:bg-slate-700"
                        }`}
                    >
                        <span
                            className={`absolute top-1 h-4 w-4 rounded-full transition ${
                                compactMode ? "left-6" : "left-1"
                            } bg-white dark:bg-slate-900`}
                        />
                    </button>
                </div>
            </div>

            <div className="mt-8 flex justify-end">
                <button className="rounded-xl bg-slate-900 px-5 py-3 text-sm font-medium text-white hover:bg-slate-800 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200">
                    Save Changes
                </button>
            </div>
        </div>
    );
}

function ThemeOption({
    icon,
    label,
    value,
    selected,
    onClick,
}: {
    icon: React.ReactNode;
    label: string;
    value: string;
    selected: boolean;
    onClick: () => void;
}) {
    return (
        <button
            onClick={onClick}
            className={`rounded-xl border p-4 text-left transition ${
                selected
                    ? "border-slate-900 bg-slate-50 dark:border-white dark:bg-slate-800"
                    : "border-slate-200 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800"
            }`}
        >
            <div className="mb-3 text-slate-600 dark:text-slate-300">
                {icon}
            </div>

            <p className="text-sm font-medium text-slate-900 dark:text-white">
                {label}
            </p>

            <p className="mt-1 text-xs text-slate-400">
                {value === "system"
                    ? "Follow device settings"
                    : `Use ${label.toLowerCase()} mode`}
            </p>
        </button>
    );
}