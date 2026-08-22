"use client";

import {
    User,
    Bell,
    Palette,
    Shield,
} from "lucide-react";

interface SettingsSidebarProps {
    activeMenu: string;
    onMenuChange: (menu: string) => void;
}

const menuItems = [
    {
        id: "profile",
        label: "Profile",
        description: "Personal information",
        icon: User,
    },
    {
        id: "notifications",
        label: "Notifications",
        description: "System alerts",
        icon: Bell,
    },
    {
        id: "appearance",
        label: "Appearance",
        description: "Display preferences",
        icon: Palette,
    },
    {
        id: "security",
        label: "Security",
        description: "Account security",
        icon: Shield,
    },
];

export default function SettingsSidebar({
    activeMenu,
    onMenuChange,
}: SettingsSidebarProps) {
    return (
        <aside className="self-start lg:sticky lg:top-6 lg:max-h-[calc(100vh-3rem)]">
            <div className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900">

                <div className="space-y-1">
                    {menuItems.map((item) => {
                        const Icon = item.icon;
                        const isActive =
                            activeMenu === item.id;

                        return (
                            <button
                                key={item.id}
                                type="button"
                                onClick={() =>
                                    onMenuChange(item.id)
                                }
                                className={`group flex w-full items-center gap-3 rounded-xl px-4 py-3 text-left transition-all duration-200 ${
                                    isActive
                                        ? "bg-slate-900 text-white shadow-sm dark:bg-white dark:text-slate-900"
                                        : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                                }`}
                            >
                                {/* Icon */}

                                <div
                                    className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
                                        isActive
                                            ? "bg-white/10 dark:bg-slate-900/10"
                                            : "bg-slate-100 dark:bg-slate-800"
                                    }`}
                                >
                                    <Icon
                                        size={18}
                                        strokeWidth={
                                            isActive
                                                ? 2.2
                                                : 1.8
                                        }
                                    />
                                </div>

                                {/* Text */}

                                <div className="min-w-0">
                                    <p
                                        className={`truncate text-sm font-medium ${
                                            isActive
                                                ? "text-white dark:text-slate-900"
                                                : "text-slate-800 dark:text-slate-200"
                                        }`}
                                    >
                                        {item.label}
                                    </p>

                                    <p
                                        className={`truncate text-xs ${
                                            isActive
                                                ? "text-slate-300 dark:text-slate-500"
                                                : "text-slate-400"
                                        }`}
                                    >
                                        {item.description}
                                    </p>
                                </div>
                            </button>
                        );
                    })}
                </div>

            </div>
        </aside>
    );
}