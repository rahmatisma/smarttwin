"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  LayoutDashboard,
  Radar,
  Video,
  History,
  Settings,
  User,
  HelpCircle,
  Menu,
  X,
} from "lucide-react";

const NAV_ITEMS = [
  { icon: LayoutDashboard, label: "Dashboard", href: "/dashboard" },
  { icon: Radar, label: "Digital Twin", href: "/digitaltwin" },
  { icon: Video, label: "CCTV", href: "/cctv" },
  { icon: History, label: "History",  href: "/history" },
  { icon: Settings, label: "Pengaturan", href: "/settings" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(false);

  return (
    <aside
      className={`sticky top-0 flex h-dvh shrink-0 flex-col border-r border-border bg-surface transition-all duration-300 ${
        isCollapsed ? "w-16" : "w-56"
      }`}
    >
      {/* HEADER / LOGO */}
      <div
        className={`flex h-[73px] shrink-0 items-center border-b border-border ${
          isCollapsed ? "justify-center px-2" : "justify-between px-5"
        }`}
      >
        {/* LOGO */}
        {!isCollapsed && (
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-signal-green/10 ring-1 ring-signal-green/30">
              <div className="h-2 w-2 rounded-full bg-signal-green" />
            </div>

            <span className="font-display text-base font-semibold tracking-tight">
              SmartTwin
            </span>
          </div>
        )}

        {/* COLLAPSE BUTTON */}
        <button
          type="button"
          onClick={() => setIsCollapsed((prev) => !prev)}
          aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-text-secondary transition-colors hover:bg-surface-2 hover:text-text"
        >
          {isCollapsed ? (
            <Menu className="h-4 w-4" />
          ) : (
            <X className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* NAVIGATION */}
      <nav className="flex min-h-0 flex-1 flex-col space-y-1 overflow-y-auto px-2 py-3">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;

          if (item.href) {
            const isActive = pathname.startsWith(item.href);

            return (
              <Link
                key={item.label}
                href={item.href}
                title={isCollapsed ? item.label : undefined}
                className={`flex w-full shrink-0 items-center rounded-md py-2 text-left text-sm transition-all duration-200 ${
                  isCollapsed
                    ? "justify-center px-2"
                    : "gap-3 px-3"
                } ${
                  isActive
                    ? "bg-accent-dim text-accent"
                    : "text-text-secondary hover:bg-surface-2 hover:text-text"
                }`}
              >
                <Icon className="h-4 w-4 shrink-0" />

                {!isCollapsed && (
                  <span className="truncate">{item.label}</span>
                )}
              </Link>
            );
          }

          return (
            <button
              key={item.label}
              type="button"
              title={isCollapsed ? item.label : undefined}
              className={`flex w-full shrink-0 items-center rounded-md py-2 text-left text-sm text-text-secondary transition-all duration-200 hover:bg-surface-2 hover:text-text ${
                isCollapsed
                  ? "justify-center px-2"
                  : "gap-3 px-3"
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />

              {!isCollapsed && (
                <span className="truncate">{item.label}</span>
              )}
            </button>
          );
        })}
      </nav>

      {/* BOTTOM MENU */}
      <div className="shrink-0 space-y-1 border-t border-border px-2 py-3">

        {/* ACCOUNT */}
        <Link
          href="/account"
          title={isCollapsed ? "Account" : undefined}
          className={`flex w-full items-center rounded-md py-2 text-left text-sm transition-all duration-200 ${
            isCollapsed
              ? "justify-center px-2"
              : "gap-3 px-3"
          } ${
            pathname.startsWith("/account")
              ? "bg-accent-dim text-accent"
              : "text-text-secondary hover:bg-surface-2 hover:text-text"
          }`}
        >
          <User className="h-4 w-4 shrink-0" />

          {!isCollapsed && (
            <span className="truncate">Account</span>
          )}
        </Link>

        {/* HELP */}
        <button
          type="button"
          title={isCollapsed ? "Help" : undefined}
          className={`flex w-full items-center rounded-md py-2 text-left text-sm text-text-secondary transition-all duration-200 hover:bg-surface-2 hover:text-text ${
            isCollapsed
              ? "justify-center px-2"
              : "gap-3 px-3"
          }`}
        >
          <HelpCircle className="h-4 w-4 shrink-0" />

          {!isCollapsed && (
            <span className="truncate">Help</span>
          )}
        </button>
      </div>
    </aside>
  );
}