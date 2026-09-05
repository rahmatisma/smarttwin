"use client";

import { useNotifications } from "@/hooks/useNotifications";
import { Bell, AlertTriangle, CheckCircle } from "lucide-react";

export default function NotificationSettings() {
    const { notifications, isLoading, markAsRead } = useNotifications();

    if (isLoading) {
        return (
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Notifications</h2>
                <div className="mt-6 space-y-4">
                    {[1, 2, 3].map(i => (
                        <div key={i} className="h-20 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />
                    ))}
                </div>
            </div>
        );
    }

    return (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
                Notifications
            </h2>

            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Manage your SmartTwin notifications. All system events are recorded here.
            </p>

            <div className="mt-6 flex flex-col gap-4">
                {notifications.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-12 text-slate-500">
                        <Bell className="mb-2 h-8 w-8 opacity-20" />
                        <p>No notifications yet.</p>
                    </div>
                ) : (
                    notifications.map((notif) => (
                        <div
                            key={notif.id}
                            className={`flex flex-col sm:flex-row sm:items-center gap-4 rounded-xl border p-4 transition-colors ${
                                notif.isRead
                                    ? "border-slate-100 bg-slate-50 opacity-70 dark:border-slate-800 dark:bg-slate-800/50"
                                    : "border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800"
                            }`}
                        >
                            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-100 dark:bg-slate-700">
                                {notif.type === "recommendation" ? (
                                    <Bell className="h-5 w-5 text-accent-blue" />
                                ) : (
                                    <AlertTriangle className="h-5 w-5 text-signal-red" />
                                )}
                            </div>
                            
                            <div className="flex-1">
                                <h3 className={`font-medium ${notif.isRead ? "text-slate-600 dark:text-slate-400" : "text-slate-900 dark:text-white"}`}>
                                    {notif.title}
                                </h3>
                                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                                    {notif.message}
                                </p>
                                <span className="mt-2 block text-xs text-slate-400">
                                    {new Date(notif.createdAt).toLocaleString("id-ID")}
                                </span>
                            </div>

                            {!notif.isRead && (
                                <button
                                    onClick={() => markAsRead(notif.id)}
                                    className="flex shrink-0 items-center gap-2 rounded-lg bg-slate-100 px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-200 dark:hover:bg-slate-600"
                                >
                                    <CheckCircle className="h-4 w-4" />
                                    Mark as read
                                </button>
                            )}
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}