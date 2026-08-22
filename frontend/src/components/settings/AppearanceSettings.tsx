"use client";

import {
    startTransition,
    useEffect,
    useState,
} from "react";
import { Sun, Moon, Monitor, Languages, Layout } from "lucide-react";
import { APPEARANCE_EVENT } from "@/components/LanguageProvider";

const STORAGE_KEY = "smarttwin.appearance.settings";
const DEFAULT_SETTINGS = {
    theme: "system",
    language: "id",
    compactMode: false,
} as const;

type AppearanceSettingsData = {
    theme: "light" | "dark" | "system";
    language: "id" | "en";
    compactMode: boolean;
};

function readSettings(): AppearanceSettingsData {
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        const parsed: unknown = stored ? JSON.parse(stored) : null;

        if (typeof parsed !== "object" || parsed === null) {
            return { ...DEFAULT_SETTINGS };
        }

        const values = parsed as Record<string, unknown>;

        return {
            theme:
                values.theme === "light" ||
                values.theme === "dark" ||
                values.theme === "system"
                    ? values.theme
                    : DEFAULT_SETTINGS.theme,
            language:
                values.language === "en" || values.language === "id"
                    ? values.language
                    : DEFAULT_SETTINGS.language,
            compactMode:
                typeof values.compactMode === "boolean"
                    ? values.compactMode
                    : DEFAULT_SETTINGS.compactMode,
        };
    } catch {
        return { ...DEFAULT_SETTINGS };
    }
}

function applySettings(settings: AppearanceSettingsData) {
    const root = document.documentElement;
    const prefersDark = window.matchMedia(
        "(prefers-color-scheme: dark)"
    ).matches;
    const isDark =
        settings.theme === "dark" ||
        (settings.theme === "system" && prefersDark);

    root.dataset.theme = isDark ? "dark" : "light";
    root.lang = settings.language;
    document.body.classList.toggle(
        "compact-mode",
        settings.compactMode
    );
}

export default function AppearanceSettings() {
    const [settings, setSettings] = useState<AppearanceSettingsData>(
        DEFAULT_SETTINGS
    );
    const [saved, setSaved] = useState(false);

    useEffect(() => {
        startTransition(() => {
            const loadedSettings = readSettings();
            setSettings(loadedSettings);
            applySettings(loadedSettings);
        });
    }, []);

    useEffect(() => {
        applySettings(settings);
    }, [settings]);

    function updateSetting<K extends keyof AppearanceSettingsData>(
        key: K,
        value: AppearanceSettingsData[K]
    ) {
        setSettings((current) => ({
            ...current,
            [key]: value,
        }));
        setSaved(false);
    }

    function handleSave() {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
        window.dispatchEvent(new CustomEvent(APPEARANCE_EVENT));
        setSaved(true);
    }

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
                        selected={settings.theme === "light"}
                        onClick={() => updateSetting("theme", "light")}
                    />

                    <ThemeOption
                        icon={<Moon size={20} />}
                        label="Dark"
                        value="dark"
                        selected={settings.theme === "dark"}
                        onClick={() => updateSetting("theme", "dark")}
                    />

                    <ThemeOption
                        icon={<Monitor size={20} />}
                        label="System"
                        value="system"
                        selected={settings.theme === "system"}
                        onClick={() => updateSetting("theme", "system")}
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
                    value={settings.language}
                    onChange={(e) =>
                        updateSetting(
                            "language",
                            e.target.value as AppearanceSettingsData["language"]
                        )
                    }
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
                        onClick={() =>
                            updateSetting(
                                "compactMode",
                                !settings.compactMode
                            )
                        }
                        className={`relative h-6 w-11 rounded-full transition ${
                            settings.compactMode
                                ? "bg-slate-900 dark:bg-white"
                                : "bg-slate-300 dark:bg-slate-700"
                        }`}
                    >
                        <span
                            className={`absolute top-1 h-4 w-4 rounded-full transition ${
                                settings.compactMode ? "left-6" : "left-1"
                            } bg-white dark:bg-slate-900`}
                        />
                    </button>
                </div>
            </div>

            <div className="mt-8 flex justify-end">
                <button
                    type="button"
                    onClick={handleSave}
                    className="rounded-xl bg-slate-900 px-5 py-3 text-sm font-medium text-white hover:bg-slate-800 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                >
                    {saved ? "Changes Saved" : "Save Changes"}
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