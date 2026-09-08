"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { AlertTriangle, Bell, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useNotifications, type Notification } from "@/hooks/useNotifications";

export default function GlobalNotifications() {
  const { notifications } = useNotifications();
  const router = useRouter();

  const [visible, setVisible] = useState<Notification[]>([]);
  const isInitialized = useRef(false);
  const seenIds = useRef<Set<string>>(new Set());
  const timers = useRef<Map<string, NodeJS.Timeout>>(new Map());

  const dismissPopup = useCallback((id: string) => {
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
    setVisible((prev) => prev.filter((n) => n.id !== id));
  }, []);

  useEffect(() => {
    if (!notifications || notifications.length === 0) return;

    // Initial mount: record all currently existing notifications so old history doesn't trigger popups
    if (!isInitialized.current) {
      isInitialized.current = true;
      notifications.forEach((n) => seenIds.current.add(n.id));
      return;
    }

    // Identify newly arrived notifications
    const newNotifications = notifications.filter((n) => !seenIds.current.has(n.id));
    if (newNotifications.length === 0) return;

    newNotifications.forEach((n) => {
      seenIds.current.add(n.id);

      // Start independent 5-second auto-dismiss timer per notification
      const timer = setTimeout(() => {
        dismissPopup(n.id);
      }, 5000);
      timers.current.set(n.id, timer);
    });

    // Stack popups (keep at most 3 active popups simultaneously)
    setVisible((prev) => [...prev, ...newNotifications].slice(-3));
  }, [notifications, dismissPopup]);

  // Clean up all active timers on component unmount
  useEffect(() => {
    return () => {
      timers.current.forEach((t) => clearTimeout(t));
      timers.current.clear();
    };
  }, []);

  if (visible.length === 0) return null;

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(calc(100vw-2rem),20rem)] flex-col gap-2">
      {visible.map((notification) => (
        <div
          key={notification.id}
          onClick={() => {
            dismissPopup(notification.id);
            router.push(`/settings?section=notifications&notificationId=${notification.id}`);
          }}
          className="pointer-events-auto flex cursor-pointer items-start gap-3 rounded-md border border-white/10 bg-[#171b29] px-3 py-3 text-white shadow-2xl transition-transform hover:scale-[1.02]"
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
            onClick={(e) => {
              e.stopPropagation();
              dismissPopup(notification.id);
            }}
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