"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Bell, MapPin } from "lucide-react";
import {
  INTERSECTION_OPTIONS,
  type IntersectionSelection,
} from "@/lib/intersections";

export default function Header({
  locationName,
  coords,
  selectedIntersection,
  onIntersectionChange,
}: {
  locationName: string;
  coords: string;
  selectedIntersection?: IntersectionSelection;
  onIntersectionChange?: (selection: IntersectionSelection) => void;
}) {
  const router = useRouter();
  const [time, setTime] = useState<string>("");

  useEffect(() => {
    const tick = () => {
      setTime(
        new Date().toLocaleTimeString("id-ID", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        })
      );
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <header className="flex items-center justify-between gap-6 border-b border-border px-6 py-4">
      <div className="flex items-center gap-1.5 text-sm">
        <MapPin className="h-4 w-4 text-text-secondary" />
        <span className="font-medium text-text">{locationName}</span>
        <span className="text-text-muted">· {coords}</span>
      </div>

      <div className="hidden max-w-md flex-1 md:flex">
        {selectedIntersection && onIntersectionChange ? (
          <select
            value={selectedIntersection}
            onChange={(event) =>
              onIntersectionChange(
                event.target.value as IntersectionSelection
              )
            }
            className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus:border-accent"
            aria-label="Pilih persimpangan"
          >
            {INTERSECTION_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.name}
              </option>
            ))}
          </select>
        ) : (
          <div className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-muted">
            Pilih persimpangan...
          </div>
        )}
      </div>

      <div className="flex items-center gap-4">
        <span className="font-mono text-sm tabular-nums text-text-secondary">
          {time || "--:--:--"}
        </span>
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
