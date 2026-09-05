"use client";

import { createContext, useContext, useSyncExternalStore, type ReactNode } from "react";
import {
  APPEARANCE_EVENT, readThemePreference, resolveTheme, writeThemePreference,
  type Theme, type ThemePreference,
} from "@/lib/theme";

export type { Theme } from "@/lib/theme";

interface ThemeContextType {
  theme: Theme;
  preference: ThemePreference;
  setTheme: (preference: ThemePreference) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);
const MEDIA_QUERY = "(prefers-color-scheme: dark)";
let sessionPreference: ThemePreference | null = null;

function getPreference(): ThemePreference {
  if (sessionPreference) return sessionPreference;
  try { return readThemePreference(window.localStorage); } catch { return "light"; }
}

function getSnapshot() {
  const preference = getPreference();
  return preference + ":" + resolveTheme(preference, window.matchMedia(MEDIA_QUERY).matches);
}

function applyTheme() {
  const theme = resolveTheme(getPreference(), window.matchMedia(MEDIA_QUERY).matches);
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
}

function subscribe(onChange: () => void) {
  const media = window.matchMedia(MEDIA_QUERY);
  const update = () => { applyTheme(); onChange(); };
  window.addEventListener(APPEARANCE_EVENT, update);
  window.addEventListener("storage", update);
  media.addEventListener("change", update);
  // Read persisted settings directly, never write the SSR fallback to storage.
  applyTheme();
  return () => {
    window.removeEventListener(APPEARANCE_EVENT, update);
    window.removeEventListener("storage", update);
    media.removeEventListener("change", update);
  };
}

function setTheme(preference: ThemePreference) {
  try {
    writeThemePreference(window.localStorage, preference);
    sessionPreference = null;
  } catch { sessionPreference = preference; }
  applyTheme();
  window.dispatchEvent(new Event(APPEARANCE_EVENT));
}

function toggleTheme() {
  const current = resolveTheme(getPreference(), window.matchMedia(MEDIA_QUERY).matches);
  setTheme(current === "dark" ? "light" : "dark");
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const snapshot = useSyncExternalStore(subscribe, getSnapshot, () => "light:light");
  const [preference, theme] = snapshot.split(":") as [ThemePreference, Theme];
  return <ThemeContext.Provider value={{ theme, preference, setTheme, toggleTheme }}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used within ThemeProvider");
  return context;
}
