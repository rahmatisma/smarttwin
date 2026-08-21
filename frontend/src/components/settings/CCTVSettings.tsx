"use client";

import { useState } from "react";
import {
    Camera,
    Box,
    LocateFixed,
    Gauge,
    RefreshCw,
} from "lucide-react";

export default function CCTVSettings() {
    const [autoReconnect, setAutoReconnect] = useState(true);
    const [boundingBox, setBoundingBox] = useState(true);
    const [trackingId, setTrackingId] = useState(false);
    const [showFps, setShowFps] = useState(false);
    const [vehicleCount, setVehicleCount] = useState(true);
    const [quality, setQuality] = useState("Auto");

    return (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="mb-8">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
                    CCTV
                </h2>

                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                    Configure CCTV display and connection preferences.
                </p>
            </div>

            <div className="space-y-6">
                {/* Video Quality */}
                <div>
                    <label className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-300">
                        <Camera size={18} />
                        Video Quality
                    </label>

                    <select
                        value={quality}
                        onChange={(e) => setQuality(e.target.value)}
                        className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none focus:border-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                    >
                        <option>Auto</option>
                        <option>1080p</option>
                        <option>720p</option>
                        <option>480p</option>
                    </select>
                </div>

                {/* Connection */}
                <div>
                    <h3 className="mb-4 text-sm font-semibold text-slate-900 dark:text-white">
                        Connection
                    </h3>

                    <ToggleItem
                        icon={<RefreshCw size={18} />}
                        title="Auto Reconnect"
                        description="Automatically reconnect when CCTV connection is lost."
                        enabled={autoReconnect}
                        onChange={() => setAutoReconnect(!autoReconnect)}
                    />
                </div>

                {/* Overlay */}
                <div className="border-t border-slate-100 pt-6 dark:border-slate-800">
                    <h3 className="mb-4 text-sm font-semibold text-slate-900 dark:text-white">
                        Detection Overlay
                    </h3>

                    <div className="space-y-4">
                        <ToggleItem
                            icon={<Box size={18} />}
                            title="Bounding Box"
                            description="Show detection bounding boxes on CCTV."
                            enabled={boundingBox}
                            onChange={() => setBoundingBox(!boundingBox)}
                        />

                        <ToggleItem
                            icon={<LocateFixed size={18} />}
                            title="Tracking ID"
                            description="Show object tracking IDs."
                            enabled={trackingId}
                            onChange={() => setTrackingId(!trackingId)}
                        />

                        <ToggleItem
                            icon={<Gauge size={18} />}
                            title="FPS Counter"
                            description="Display video processing FPS."
                            enabled={showFps}
                            onChange={() => setShowFps(!showFps)}
                        />

                        <ToggleItem
                            icon={<Camera size={18} />}
                            title="Vehicle Count"
                            description="Display detected vehicle count."
                            enabled={vehicleCount}
                            onChange={() => setVehicleCount(!vehicleCount)}
                        />
                    </div>
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

function ToggleItem({
    icon,
    title,
    description,
    enabled,
    onChange,
}: {
    icon: React.ReactNode;
    title: string;
    description: string;
    enabled: boolean;
    onChange: () => void;
}) {
    return (
        <div className="flex items-center justify-between rounded-xl border border-slate-100 p-4 dark:border-slate-800">
            <div className="flex items-center gap-3">
                <div className="text-slate-500 dark:text-slate-400">
                    {icon}
                </div>

                <div>
                    <p className="text-sm font-medium text-slate-900 dark:text-white">
                        {title}
                    </p>

                    <p className="text-xs text-slate-400">
                        {description}
                    </p>
                </div>
            </div>

            <button
                onClick={onChange}
                className={`relative h-6 w-11 rounded-full transition ${
                    enabled
                        ? "bg-slate-900 dark:bg-white"
                        : "bg-slate-300 dark:bg-slate-700"
                }`}
            >
                <span
                    className={`absolute top-1 h-4 w-4 rounded-full transition ${
                        enabled ? "left-6" : "left-1"
                    } bg-white dark:bg-slate-900`}
                />
            </button>
        </div>
    );
}