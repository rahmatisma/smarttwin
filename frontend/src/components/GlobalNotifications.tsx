"use client";

import { AlertTriangle, Bell, X } from "lucide-react";
import { useNotifications } from "@/hooks/useNotifications";

export default function GlobalNotifications() {
  const { notifications, markAsRead } = useNotifications();
  const unreadNotifications = notifications.filter((notification) => !notification.isRead).slice(0, 3);

  if (unreadNotifications.length === 0) return null;

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(calc(100vw-2rem),20rem)] flex-col gap-2">
      {unreadNotifications.map((notification) => (
        <div
          key={notification.id}
          className="pointer-events-auto flex items-start gap-3 rounded-md border border-white/10 bg-[#171b29] px-3 py-3 text-white shadow-2xl"
        >
          {notification.type === "recommendation" ? (
            <Bell className="mt-0.5 h-4 w-4 shrink-0 text-slate-200" />
          ) : (
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-300" />
          )}
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-semibold leading-tight">{notification.title}</p>
            <p className="mt-1 text-[10px] font-medium leading-snug text-slate-300">
              {notification.message}
            </p>
          </div>
          <button
            type="button"
            onClick={() => markAsRead(notification.id)}
            className="shrink-0 rounded p-0.5 text-slate-400 transition-colors hover:bg-white/10 hover:text-white"
            aria-label="Tutup notifikasi"
            title="Tutup"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
}