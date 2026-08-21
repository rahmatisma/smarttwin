"use client";

import { useState } from "react";
import { TrafficCone, Clock3, Car, Users, Gauge } from "lucide-react";

export default function TrafficSettings() {
    const [vehicleDetection, setVehicleDetection] = useState(true);
    const [pedestrianDetection, setPedestrianDetection] = useState(true);
    const [queueLength, setQueueLength] = useState(true);
    const [trafficDensity, setTrafficDensity] = useState(true);
    const [refreshInterval, setRefreshInterval] = useState("5");
    const [defaultIntersection, setDefaultIntersection] = useState("Simpang 1");

    return (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="mb-8">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
                    Traffic Monitoring
                </h2>

                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                    Configure how traffic data is monitored and displayed.
                </p>
            </div>

            <div className="space-y-6">
                {/* Default Intersection */}
                <div>
                    <label className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-300">
                        <TrafficCone size={18} />
                        Default Intersection
                    </label>

                    <select
                        value={defaultIntersection}
                        onChange={(e) => setDefaultIntersection(e.target.value)}
                        className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none focus:border-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                    >
                        <option>Simpang 1</option>
                        <option>Simpang 2</option>
                        <option>Simpang 3</option>
                        <option>Simpang 4</option>
                    </select>

                    <p className="mt-1 text-xs text-slate-400">
                        Intersection shown by default on the monitoring dashboard.
                    </p>
                </div>

                {/* Refresh Interval */}
                <div>
                    <label className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-300">
                        <Clock3 size={18} />
                        Data Refresh Interval
                    </label>

                    <select
                        value={refreshInterval}
                        onChange={(e) => setRefreshInterval(e.target.value)}
                        className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none focus:border-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                    >
                        <option value="1">1 second</option>
                        <option value="5">5 seconds</option>
                        <option value="10">10 seconds</option>
                        <option value="30">30 seconds</option>
                    </select>
                </div>

                {/* Detection */}
                <div className="border-t border-slate-100 pt-6 dark:border-slate-800">
                    <h3 className="mb-4 text-sm font-semibold text-slate-900 dark:text-white">
                        Detection & Analytics
                    </h3>

                    <div className="space-y-4">
                        <ToggleItem
                            icon={<Car size={18} />}
                            title="Vehicle Detection"
                            description="Detect vehicles using computer vision."
                            enabled={vehicleDetection}
                            onChange={() =>
                                setVehicleDetection(!vehicleDetection)
                            }
                        />

                        <ToggleItem
                            icon={<Users size={18} />}
                            title="Pedestrian Detection"
                            description="Detect pedestrians around the intersection."
                            enabled={pedestrianDetection}
                            onChange={() =>
                                setPedestrianDetection(!pedestrianDetection)
                            }
                        />

                        <ToggleItem
                            icon={<Gauge size={18} />}
                            title="Queue Length"
                            description="Display estimated vehicle queue length."
                            enabled={queueLength}
                            onChange={() => setQueueLength(!queueLength)}
                        />

                        <ToggleItem
                            icon={<TrafficCone size={18} />}
                            title="Traffic Density"
                            description="Display real-time traffic density."
                            enabled={trafficDensity}
                            onChange={() =>
                                setTrafficDensity(!trafficDensity)
                            }
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
                    className={`absolute top-1 h-4 w-4 rounded-full bg-white transition ${
                        enabled ? "left-6" : "left-1"
                    } dark:bg-slate-900`}
                />
            </button>
        </div>
    );
}