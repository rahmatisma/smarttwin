"use client";

import Link from "next/link";
import {
  LayoutDashboard,
  Radar,
  Video,
  Lightbulb,
  History,
  Settings,
  User,
  HelpCircle,
} from "lucide-react";

const NAV_ITEMS = [
  { icon: LayoutDashboard, label: "Dashboard", active: true },
  { icon: Radar, label: "Digital Twin" },
  { icon: Video, label: "CCTV", href: "/cctv" },
  { icon: Lightbulb, label: "Rekomendasi" },
  { icon: History, label: "History" },
  { icon: Settings, label: "Pengaturan" },
];

export default function Sidebar() {
  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col border-r border-border bg-surface">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-signal-green/10 ring-1 ring-signal-green/30">
          <div className="h-2 w-2 rounded-full bg-signal-green" />
        </div>

        <span className="font-display text-base font-semibold tracking-tight">
          SmartTwin
        </span>
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;

          if (item.href) {
            return (
              <Link
                key={item.label}
                href={item.href}
                className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm text-text-secondary transition-colors hover:bg-surface-2 hover:text-text"
              >
                <Icon className="h-4 w-4 shrink-0" />
                {item.label}
              </Link>
            );
          }

          return (
            <button
              key={item.label}
              type="button"
              className={`flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors ${
                item.active
                  ? "bg-accent-dim text-accent"
                  : "text-text-secondary hover:bg-surface-2 hover:text-text"
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {item.label}
            </button>
          );
        })}
      </nav>

      <div className="space-y-1 border-t border-border px-3 py-3">
        <button
          type="button"
          className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm text-text-secondary transition-colors hover:bg-surface-2 hover:text-text"
        >
          <User className="h-4 w-4 shrink-0" />
          Account
        </button>

        <button
          type="button"
          className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm text-text-secondary transition-colors hover:bg-surface-2 hover:text-text"
        >
          <HelpCircle className="h-4 w-4 shrink-0" />
          Help
        </button>
      </div>
    </aside>
  );
}