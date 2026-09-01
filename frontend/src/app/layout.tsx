import type { Metadata } from "next";
import "./globals.css";
import LanguageProvider from "@/components/LanguageProvider";
import { ScenarioProvider } from "@/context/ScenarioContext";

export const metadata: Metadata = {
  title: "SmartTwin — Dashboard Simpang",
  description:
    "Sistem Digital Twin untuk Optimasi Sinyal Lalu Lintas Adaptif Berbasis Computer Vision",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="id">
      <body
        className="font-sans antialiased bg-bg text-text"
      >
        <ScenarioProvider>
          <LanguageProvider>{children}</LanguageProvider>
        </ScenarioProvider>
      </body>
    </html>
  );
}
