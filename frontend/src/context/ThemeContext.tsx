"use client";

import React, { createContext, useContext, useEffect, useState, ReactNode } from "react";

export type Theme = "dark" | "light";

const THEME_STORAGE_KEY = "smarttwin.theme";

interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

// Default gelap dipertahankan (tampilan yang sudah dipakai selama ini) --
// terang cuma opsi tambahan lewat toggle, bukan pengganti default. Skrip
// inline di layout.tsx sudah menerapkan data-theme sebelum React hydrate,
// jadi state awal di sini disamakan lewat baca DOM, bukan selalu "dark",
// supaya tidak ada flash balik ke gelap sesaat sebelum effect jalan.
function readInitialTheme(): Theme {
  if (typeof document === "undefined") return "dark";
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(readInitialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    return { theme: "dark" as Theme, toggleTheme: () => {} };
  }
  return context;
}
