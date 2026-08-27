import type { Metadata } from "next";
import { Inter, Space_Grotesk, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import LanguageProvider from "@/components/LanguageProvider";
import { ScenarioProvider } from "@/context/ScenarioContext";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space-grotesk",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
});

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
        className={`${inter.variable} ${spaceGrotesk.variable} ${jetbrainsMono.variable} font-sans antialiased bg-bg text-text`}
      >
        <ScenarioProvider>
          <LanguageProvider>{children}</LanguageProvider>
        </ScenarioProvider>
      </body>
    </html>
  );
}
