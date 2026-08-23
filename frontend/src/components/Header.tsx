"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Bell, MapPin } from "lucide-react";
import {
  APPROACH_OPTIONS,
  type ApproachSelection,
} from "@/lib/intersections";

export default function Header({
  locationName,
  coords,
  selectedApproach,
  onApproachChange,
  lastUpdated,
}: {
  locationName: string;
  coords: string;
  selectedApproach?: ApproachSelection;
  onApproachChange?: (selection: ApproachSelection) => void;
  lastUpdated?: string | number;
}) {
  const router = useRouter();

  // Local clock removed in favor of CV data Last Updated timestamp

  return (
    <header className="flex items-center justify-between gap-6 border-b border-border px-6 py-4">
      <div className="flex items-center gap-1.5 text-sm">
        <MapPin className="h-4 w-4 text-text-secondary" />
        <span className="font-medium text-text">{locationName}</span>
        <span className="text-text-muted">· {coords}</span>
      </div>

      <div className="hidden max-w-md flex-1 md:flex">
        {selectedApproach && onApproachChange ? (
          <select
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
          <div className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-muted">
            Pilih lengan...
          </div>
        )}
      </div>

      <div className="flex items-center gap-4">
        {lastUpdated !== undefined ? (
          <span className="font-mono text-sm tabular-nums text-text-secondary">
            {typeof lastUpdated === "number" ? (
              `Last Updated: ${Math.floor(lastUpdated / 60).toString().padStart(2, "0")}:${(lastUpdated % 60).toFixed(2).padStart(5, "0")}`
            ) : (
              `Last Updated: ${new Date(lastUpdated).toLocaleTimeString("id-ID", {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}`
            )}
          </span>
        ) : (
          <span className="font-mono text-sm tabular-nums text-text-secondary">
            Data belum tersedia
          </span>
        )}
        <button
          type="button"
          onClick={() => router.push("/settings?section=notifications")}
          className="relative flex h-8 w-8 items-center justify-center rounded-md border border-border text-text-secondary hover:text-text"
          aria-label="Notifikasi"
          title="Notifikasi"
        >
          <Bell className="h-4 w-4" />
          <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-signal-amber" />
        </button>
      </div>
    </header>
  );
}
