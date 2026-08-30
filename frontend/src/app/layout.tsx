import type { Metadata } from "next";
import { Inter, Space_Grotesk, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import LanguageProvider from "@/components/LanguageProvider";
import { ScenarioProvider } from "@/context/ScenarioContext";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  preload: false,
});

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space-grotesk",
  preload: false,
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
  preload: false,
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
    <html lang="id" translate="no" className="notranslate">
      <head>
        <meta name="google" content="notranslate" />
      </head>
      <body
        translate="no"
        className={`${inter.variable} ${spaceGrotesk.variable} ${jetbrainsMono.variable} notranslate font-sans antialiased bg-bg text-text`}
      >
        <ScenarioProvider>
          <LanguageProvider>{children}</LanguageProvider>
        </ScenarioProvider>
      </body>
    </html>
  );
}
