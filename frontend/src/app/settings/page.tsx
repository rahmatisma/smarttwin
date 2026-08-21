"use client";

import { useState } from "react";
import {
    User,
    Bell,
    TrafficCone,
    Camera,
    Brain,
    Palette,
    Shield,
} from "lucide-react";

import ProfileSettings from "@/components/settings/ProfileSettings";
import NotificationSettings from "@/components/settings/NotificationSettings";
import TrafficSettings from "@/components/settings/TrafficSettings";
import CCTVSettings from "@/components/settings/CCTVSettings";
import AISettings from "@/components/settings/AISettings";
import AppearanceSettings from "@/components/settings/AppearanceSettings";
import SecuritySettings from "@/components/settings/SecuritySetttings";
import Sidebar from "@/components/Sidebar";

const menuItems = [
    {
        id: "profile",
        label: "Profile",
        description: "Manage your personal information",
        icon: User,
    },
    {
        id: "notifications",
        label: "Notifications",
        description: "Manage system notifications",
        icon: Bell,
    },
    {
        id: "traffic",
        label: "Traffic Monitoring",
        description: "Configure traffic monitoring",
        icon: TrafficCone,
    },
    {
        id: "cctv",
        label: "CCTV",
        description: "Manage CCTV preferences",
        icon: Camera,
    },
    {
        id: "ai",
        label: "AI & Prediction",
        description: "Configure AI and forecasting",
        icon: Brain,
    },
    {
        id: "appearance",
        label: "Appearance",
        description: "Customize application appearance",
        icon: Palette,
    },
    {
        id: "security",
        label: "Security",
        description: "Manage account security",
        icon: Shield,
    },
];

export default function SettingsPage() {
    const [activeMenu, setActiveMenu] = useState("profile");

    const renderContent = () => {
        switch (activeMenu) {
            case "profile":
                return <ProfileSettings />;

            case "notifications":
                return <NotificationSettings />;

            case "traffic":
                return <TrafficSettings />;

            case "cctv":
                return <CCTVSettings />;

            case "ai":
                return <AISettings />;

            case "appearance":
                return <AppearanceSettings />;

            case "security":
                return <SecuritySettings />;

            default:
                return <ProfileSettings />;
        }
    };

    return (
        <div className="settings-page flex h-screen overflow-hidden bg-background text-text">
            <Sidebar />

            <div className="min-w-0 flex-1 overflow-y-auto">
                <main className="min-h-full bg-slate-50 p-6 dark:bg-slate-950">
                    <div className="mx-auto max-w-7xl">

                        {/* Header */}
                        <div className="mb-8">
                            <h1 className="text-3xl font-bold text-slate-900 dark:text-white">
                                Settings
                            </h1>

                            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                                Manage your SmartTwin preferences and system configuration.
                            </p>
                        </div>

                        {/* Settings Layout */}
                        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[280px_1fr]">

                            {/* Sidebar */}
                            <aside className="h-fit rounded-2xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900">

                                <div className="space-y-1">
                                    {menuItems.map((item) => {
                                        const Icon = item.icon;
                                        const active = activeMenu === item.id;

                                        return (
                                            <button
                                                key={item.id}
                                                onClick={() => setActiveMenu(item.id)}
                                                className={`flex w-full items-center gap-3 rounded-xl px-4 py-3 text-left transition ${
                                                    active
                                                        ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900"
                                                        : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                                                }`}
                                            >
                                                <Icon size={19} />

                                                <div>
                                                    <p className="text-sm font-medium">
                                                        {item.label}
                                                    </p>

                                                    <p
                                                        className={`text-xs ${
                                                            active
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
                            </aside>

                            {/* Content */}
                            <section>
                                {renderContent()}
                            </section>

                        </div>
                    </div>
                </main>
            </div>
        </div>
    );
}