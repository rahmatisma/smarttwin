"use client";

import { useState } from "react";
import {
    Scan,
    TrendingUp,
    Lightbulb,
    Timer,
} from "lucide-react";

export default function AISettings() {
    const [vehicleDetection, setVehicleDetection] = useState(true);
    const [tracking, setTracking] = useState(true);
    const [forecasting, setForecasting] = useState(true);
    const [recommendation, setRecommendation] = useState(true);
    const [automaticOptimization, setAutomaticOptimization] = useState(false);

    const [forecastHorizon, setForecastHorizon] = useState("15");

    return (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="mb-8">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
                    AI & Prediction
                </h2>

                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                    Configure computer vision, forecasting, and traffic optimization.
                </p>
            </div>

            <div className="space-y-6">
                {/* Computer Vision */}
                <div>
                    <div className="mb-4 flex items-center gap-2">
                        <Scan size={19} className="text-slate-500" />

                        <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                            Computer Vision
                        </h3>
                    </div>

                    <div className="space-y-4">
                        <ToggleItem
                            title="Vehicle Detection"
                            description="Use YOLO for vehicle detection."
                            enabled={vehicleDetection}
                            onChange={() =>
                                setVehicleDetection(!vehicleDetection)
                            }
                        />

                        <ToggleItem
                            title="Object Tracking"
                            description="Track detected vehicles across frames."
                            enabled={tracking}
                            onChange={() => setTracking(!tracking)}
                        />
                    </div>
                </div>

                {/* Forecast */}
                <div className="border-t border-slate-100 pt-6 dark:border-slate-800">
                    <div className="mb-4 flex items-center gap-2">
                        <TrendingUp size={19} className="text-slate-500" />

                        <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                            Traffic Forecast
                        </h3>
                    </div>

                    <ToggleItem
                        title="Traffic Forecasting"
                        description="Enable LSTM-based traffic prediction."
                        enabled={forecasting}
                        onChange={() => setForecasting(!forecasting)}
                    />

                    <div className="mt-4">
                        <label className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-300">
                            <Timer size={18} />
                            Forecast Horizon
                        </label>

                        <select
                            value={forecastHorizon}
                            onChange={(e) =>
                                setForecastHorizon(e.target.value)
                            }
                            className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                        >
                            <option value="5">5 minutes</option>
                            <option value="15">15 minutes</option>
                            <option value="30">30 minutes</option>
                            <option value="60">60 minutes</option>
                        </select>
                    </div>
                </div>

                {/* Recommendation */}
                <div className="border-t border-slate-100 pt-6 dark:border-slate-800">
                    <div className="mb-4 flex items-center gap-2">
                        <Lightbulb size={19} className="text-slate-500" />

                        <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                            Signal Optimization
                        </h3>
                    </div>

                    <div className="space-y-4">
                        <ToggleItem
                            title="AI Recommendation"
                            description="Generate adaptive traffic signal recommendations."
                            enabled={recommendation}
                            onChange={() =>
                                setRecommendation(!recommendation)
                            }
                        />

                        <ToggleItem
                            title="Automatic Optimization"
                            description="Automatically apply AI signal recommendations."
                            enabled={automaticOptimization}
                            onChange={() =>
                                setAutomaticOptimization(
                                    !automaticOptimization
                                )
                            }
                        />
                    </div>

                    <div className="mt-4 rounded-xl bg-slate-50 p-4 dark:bg-slate-800">
                        <p className="text-xs leading-5 text-slate-500 dark:text-slate-400">
                            Automatic optimization is disabled by default.
                            Enable it only when the traffic signal control
                            system is ready for automated operation.
                        </p>
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
    title,
    description,
    enabled,
    onChange,
}: {
    title: string;
    description: string;
    enabled: boolean;
    onChange: () => void;
}) {
    return (
        <div className="flex items-center justify-between rounded-xl border border-slate-100 p-4 dark:border-slate-800">
            <div>
                <p className="text-sm font-medium text-slate-900 dark:text-white">
                    {title}
                </p>

                <p className="mt-1 text-xs text-slate-400">
                    {description}
                </p>
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