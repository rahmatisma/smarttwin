"use client";

import Sidebar from "./Sidebar";
import Header from "./Header";

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="flex h-screen overflow-hidden bg-background text-text">
            <Sidebar />

            <div className="flex min-w-0 flex-1 flex-col">
                <Header
                    locationName="simpang4-pingit"
                    coords="Koordinat belum tersedia"
                />

                <main className="min-h-0 flex-1 overflow-y-auto">
                    {children}
                </main>
            </div>
        </div>
    );
}