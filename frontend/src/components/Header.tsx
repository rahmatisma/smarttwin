"use client";

import { useRouter, usePathname } from "next/navigation";
import { Bell, MapPin, Sun, Moon } from "lucide-react";
import { useNotifications } from "@/hooks/useNotifications";
import {
  APPROACH_OPTIONS,
  type ApproachSelection,
} from "@/lib/intersections";
import { useTheme } from "@/context/ThemeContext";

export default function Header({
  locationName,
  coords,
  selectedApproach,
  onApproachChange,
  lastUpdated,
  hideApproachFilter = false,
  hideLastUpdated = false,
}: {
  locationName: string;
  coords: string;
  selectedApproach?: ApproachSelection;
  onApproachChange?: (selection: ApproachSelection) => void;
  lastUpdated?: string | number;
  hideApproachFilter?: boolean;
  hideLastUpdated?: boolean;
}) {
  const router = useRouter();
  const { unreadCount } = useNotifications();
  const pathname = usePathname();
  const pageTitle = pathname === "/" || pathname.startsWith("/dashboard") ? "Dashboard" : pathname.startsWith("/digitaltwin") ? "Digital Twin" : pathname.startsWith("/cctv") ? "Pemantauan CCTV" : pathname.startsWith("/history") ? "Riwayat Keputusan" : "SmartTwin";
  const { theme, toggleTheme } = useTheme();

  // Local clock removed in favor of CV data Last Updated timestamp

  return (
    <header className="app-header flex items-center justify-between gap-6 border-b border-border px-6 py-4">
      <div className="header-identity min-w-0">
        <span className="header-eyebrow">SMARTTWIN / PUSAT PEMANTAUAN</span>
        <h2 className="header-title">{pageTitle}</h2>
        <div className="header-location">
          <span className="header-location-badge"><MapPin size={15} aria-hidden="true" /><span>Lokasi: <strong>{locationName}</strong></span></span>
          <span className="header-coordinates">{coords}</span>
        </div>
      </div>

      {!hideApproachFilter && (
        <div className="header-filter">
          <label htmlFor="header-approach">Lengan simpang</label>
          {selectedApproach && onApproachChange ? (
            <select
              id="header-approach"
              value={selectedApproach}
              onChange={(event) =>
                onApproachChange(
                  event.target.value as ApproachSelection
                )
              }
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus:border-accent"
              aria-label="Pilih lengan simpang"
            >
              {APPROACH_OPTIONS.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.name}
                </option>
              ))}
            </select>
          ) : (
            <select id="header-approach" disabled className="w-full rounded-md border border-border px-3 py-2 text-sm">
              <option>Semua lengan</option>
            </select>
          )}
        </div>
      )}

      <div className="header-actions flex shrink-0 items-center gap-3">
        {!hideLastUpdated && (
          lastUpdated !== undefined ? (
            <span className="header-timestamp text-xs tabular-nums text-text-secondary">
              {typeof lastUpdated === "number" ? (
                `Diperbarui: ${Math.floor(lastUpdated / 60).toString().padStart(2, "0")}:${(lastUpdated % 60).toFixed(2).padStart(5, "0")}`
              ) : (
                `Diperbarui: ${new Date(lastUpdated).toLocaleTimeString("id-ID", {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                })}`
              )}
            </span>
          ) : (
            <span className="header-timestamp text-xs tabular-nums text-text-secondary">
              Data belum tersedia
            </span>
          )
        )}
        <button
          type="button"
          onClick={toggleTheme}
          className="flex h-8 w-8 items-center justify-center rounded-md border border-border text-text-secondary hover:text-text"
          aria-label={theme === "dark" ? "Aktifkan tema terang" : "Aktifkan tema gelap"}
          title={theme === "dark" ? "Tema terang" : "Tema gelap"}
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
        <button
          type="button"
          onClick={() => router.push("/settings?section=notifications")}
          className="relative flex h-8 w-8 items-center justify-center rounded-md border border-border text-text-secondary hover:text-text"
          aria-label="Notifikasi"
          title="Notifikasi"
        >
          <Bell className="h-4 w-4" />
          {unreadCount > 0 && (
            <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-signal-red text-[10px] font-bold text-white">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </button>
      </div>
    </header>
  );
}
