"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  LayoutDashboard, Radar, Video, History, Settings, User,
  PanelLeftClose, PanelLeftOpen, ChevronRight,
} from "lucide-react";

const NAV_ITEMS = [
  { icon: LayoutDashboard, label: "Dashboard", href: "/dashboard" },
  { icon: Radar, label: "Digital Twin", href: "/digitaltwin" },
  { icon: Video, label: "CCTV", href: "/cctv" },
  { icon: History, label: "Riwayat Keputusan", href: "/history" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const isActive = (href: string) => pathname === href || pathname.startsWith(href + "/") || (href === "/dashboard" && pathname === "/");

  return (
    <aside className={`app-sidebar sticky top-0 flex h-dvh shrink-0 flex-col ${isCollapsed ? "is-collapsed" : ""}`}>
      <div className="sidebar-brand-header">
        <Link href="/dashboard" className="sidebar-logo-link" aria-label="SmartTwin - buka dashboard">
          <Image src="/logo-dark.png" alt="SmartTwin" width={104} height={104} loading="eager" className="sidebar-logo-image" />
        </Link>
        <span className="sidebar-brand-caption">TRAFFIC MANAGEMENT</span>
        <button type="button" onClick={() => setIsCollapsed((prev) => !prev)}
          aria-expanded={!isCollapsed} aria-controls="sidebar-navigation"
          aria-label={isCollapsed ? "Perluas sidebar" : "Perkecil sidebar"}
          title={isCollapsed ? "Perluas sidebar" : "Perkecil sidebar"}
          className="sidebar-collapse-button">
          {isCollapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
        </button>
      </div>
      <nav id="sidebar-navigation" aria-label="Navigasi utama" className="sidebar-navigation">
        <p className="sidebar-section-label">RUANG KERJA</p>
        {NAV_ITEMS.map(({ icon: Icon, label, href }) => (
          <Link key={href} href={href} aria-label={label} title={label}
            aria-current={isActive(href) ? "page" : undefined} className="sidebar-nav-link">
            <span className="sidebar-nav-icon"><Icon size={19} strokeWidth={1.7} aria-hidden="true" /></span>
            <span className="sidebar-link-label">{label}</span>
            {isActive(href) && <ChevronRight size={14} className="sidebar-active-arrow" aria-hidden="true" />}
          </Link>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <p className="sidebar-section-label">PREFERENSI</p>
        <Link href="/settings" aria-label="Pengaturan" title="Pengaturan"
          aria-current={isActive("/settings") ? "page" : undefined} className="sidebar-nav-link">
          <span className="sidebar-nav-icon"><Settings size={19} strokeWidth={1.7} aria-hidden="true" /></span>
          <span className="sidebar-link-label">Pengaturan</span>
        </Link>
        <Link href="/account" aria-label="Akun saya" title="Akun saya"
          aria-current={isActive("/account") ? "page" : undefined} className="sidebar-account">
          <span className="sidebar-account-avatar"><User size={19} strokeWidth={1.7} aria-hidden="true" /></span>
          <span className="sidebar-account-copy"><strong>Akun saya</strong><span>Profil & keamanan</span></span>
          <ChevronRight size={15} className="sidebar-account-arrow" aria-hidden="true" />
        </Link>
      </div>
    </aside>
  );
}
