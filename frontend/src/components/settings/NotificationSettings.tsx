"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useNotifications } from "@/hooks/useNotifications";
import { Bell, AlertTriangle, CheckCircle, Trash2, CheckCheck } from "lucide-react";

export default function NotificationSettings() {
    const { notifications, isLoading, markAsRead, markAllAsRead, deleteAll, deleteNotification } = useNotifications();
    const searchParams = useSearchParams();
    const notificationId = searchParams.get("notificationId");
    const itemRefs = useRef<Map<string, HTMLDivElement>>(new Map());
    const [showDeleteAllConfirm, setShowDeleteAllConfirm] = useState(false);

    useEffect(() => {
        if (!isLoading && notificationId && notifications.length > 0) {
            const targetElement = itemRefs.current.get(notificationId);
            if (targetElement) {
                targetElement.scrollIntoView({ behavior: "smooth", block: "center" });
            }
        }
    }, [isLoading, notificationId, notifications]);

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

            {notifications.length > 0 && (
                <div className="mt-4 flex flex-wrap items-center gap-3 border-b border-slate-100 pb-4 dark:border-slate-800">
                    <button
                        onClick={markAllAsRead}
                        className="flex items-center gap-2 rounded-lg bg-slate-100 px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
                    >
                        <CheckCheck className="h-4 w-4" />
                        Tandai semua dibaca
                    </button>
                    <button
                        onClick={() => setShowDeleteAllConfirm(true)}
                        className="flex items-center gap-2 rounded-lg bg-red-50 text-red-600 px-3 py-2 text-sm font-medium transition-colors hover:bg-red-100 dark:bg-red-900/20 dark:text-red-400 dark:hover:bg-red-900/40"
                    >
                        <Trash2 className="h-4 w-4" />
                        Hapus semua
                    </button>
                </div>
            )}

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
                            ref={(el) => {
                                if (el) itemRefs.current.set(notif.id, el);
                                else itemRefs.current.delete(notif.id);
                            }}
                            className={`flex flex-col sm:flex-row sm:items-center gap-4 rounded-xl border p-4 transition-all duration-500 ${
                                notif.id === notificationId
                                    ? "ring-2 ring-blue-500 border-blue-500 bg-blue-50/30 dark:ring-blue-500 dark:border-blue-500 dark:bg-blue-900/10 scale-[1.01]"
                                    : notif.isRead
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
                                {(() => {
                                    const createdAt = new Date(notif.createdAt);
                                    return (
                                        <span className="mt-2 block text-xs text-slate-400">
                                            {Number.isNaN(createdAt.getTime())
                                                ? "Waktu tidak tersedia"
                                                : createdAt.toLocaleString("id-ID")}
                                        </span>
                                    );
                                })()}
                            </div>

                            <div className="flex shrink-0 items-center gap-2">
                                {!notif.isRead && (
                                    <button
                                        onClick={() => markAsRead(notif.id)}
                                        className="flex items-center gap-2 rounded-lg bg-slate-100 px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-200 dark:hover:bg-slate-600"
                                        title="Mark as read"
                                    >
                                        <CheckCircle className="h-4 w-4" />
                                        Mark as read
                                    </button>
                                )}
                                <button
                                    onClick={() => deleteNotification(notif.id)}
                                    className="flex items-center justify-center rounded-lg bg-slate-100 p-2 text-slate-500 transition-colors hover:bg-red-50 hover:text-red-600 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-red-900/20 dark:hover:text-red-400"
                                    title="Hapus notifikasi"
                                >
                                    <Trash2 className="h-4 w-4" />
                                </button>
                            </div>
                        </div>
                    ))
                )}
            </div>

            {/* Modal Konfirmasi Delete All */}
            {showDeleteAllConfirm && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
                    <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                        <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                            Hapus semua notifikasi?
                        </h3>
                        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                            Apakah kamu yakin ingin menghapus seluruh notifikasi? Tindakan ini tidak dapat dibatalkan.
                        </p>
                        <div className="mt-6 flex justify-end gap-3">
                            <button
                                onClick={() => setShowDeleteAllConfirm(false)}
                                className="rounded-lg px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800 transition-colors"
                            >
                                Batal
                            </button>
                            <button
                                onClick={async () => {
                                    await deleteAll();
                                    setShowDeleteAllConfirm(false);
                                }}
                                className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 transition-colors shadow-sm"
                            >
                                <Trash2 className="h-4 w-4" />
                                Hapus semua
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}