"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, Bell, MapPin } from "lucide-react";

export default function Header({
  locationName,
  coords,
}: {
  locationName: string;
  coords: string;
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

      <div className="hidden max-w-md flex-1 items-center gap-2 rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-muted md:flex">
        <Search className="h-4 w-4" />
        <span>Cari persimpangan…</span>
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
