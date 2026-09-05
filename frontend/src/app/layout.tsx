import type { Metadata } from "next";
import "./globals.css";
import LanguageProvider from "@/components/LanguageProvider";
import { ScenarioProvider } from "@/context/ScenarioContext";
import { ThemeProvider } from "@/context/ThemeContext";

export const metadata: Metadata = {
  title: "SmartTwin — Dashboard Simpang",
  description:
    "Sistem Digital Twin untuk Optimasi Sinyal Lalu Lintas Adaptif Berbasis Computer Vision",
};

// Terapkan data-theme SEBELUM React hydrate. Tanpa ini, ThemeProvider baru
// menyetel atribut di useEffect (sesudah paint pertama) -- pengguna yang
// sebelumnya memilih tema terang akan melihat kedipan gelap->terang tiap
// reload.
const THEME_INIT_SCRIPT = `
(function () {
  try {
    var stored = window.localStorage.getItem("smarttwin.theme");
    if (stored === "light" || stored === "dark") {
      document.documentElement.dataset.theme = stored;
    }
  } catch (e) {}
})();
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // suppressHydrationWarning: data-theme disuntik oleh THEME_INIT_SCRIPT
  // sebelum React hydrate berdasarkan localStorage, yang server tidak tahu
  // isinya -- React akan selalu menganggap ini "mismatch" walau perilakunya
  // memang disengaja. Hanya meredam warning utk atribut di elemen <html>
  // ini, bukan children-nya.
  return (
    <html lang="id" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body
        className="font-sans antialiased bg-bg text-text"
      >
        <ThemeProvider>
          <ScenarioProvider>
            <LanguageProvider>{children}</LanguageProvider>
          </ScenarioProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
