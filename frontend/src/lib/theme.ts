export type Theme = "light" | "dark";
export type ThemePreference = Theme | "system";

export const APPEARANCE_STORAGE_KEY = "smarttwin.appearance.settings";
export const LEGACY_THEME_STORAGE_KEY = "smarttwin.theme";
export const APPEARANCE_EVENT = "smarttwin-appearance-updated";

export function isThemePreference(value: unknown): value is ThemePreference {
  return value === "light" || value === "dark" || value === "system";
}

export function readThemePreference(storage: Pick<Storage, "getItem">): ThemePreference {
  try {
    const settings = JSON.parse(storage.getItem(APPEARANCE_STORAGE_KEY) || "null");
    if (isThemePreference(settings?.theme)) return settings.theme;
  } catch { /* Invalid appearance data must not hide a valid legacy preference. */ }
  try {
    const legacy = storage.getItem(LEGACY_THEME_STORAGE_KEY);
    if (isThemePreference(legacy)) return legacy;
  } catch { /* Storage can be unavailable in private or restricted contexts. */ }
  return "light";
}

export function resolveTheme(preference: ThemePreference, prefersDark: boolean): Theme {
  return preference === "system" ? (prefersDark ? "dark" : "light") : preference;
}

export function writeThemePreference(storage: Storage, preference: ThemePreference) {
  let settings: Record<string, unknown> = {};
  try {
    const parsed = JSON.parse(storage.getItem(APPEARANCE_STORAGE_KEY) || "null");
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) settings = parsed;
  } catch { /* Replace malformed settings, preserving valid preferences otherwise. */ }
  storage.setItem(APPEARANCE_STORAGE_KEY, JSON.stringify({ ...settings, theme: preference }));
  storage.removeItem(LEGACY_THEME_STORAGE_KEY);
}

// Runs in the document head before paint. Uses the same storage precedence as
// the provider; regression tests cover both paths, including system mode.
export const THEME_INIT_SCRIPT = `
(function () {
  var preference = "light";
  var valid = function (value) { return value === "light" || value === "dark" || value === "system"; };
  var saved;
  try { saved = JSON.parse(localStorage.getItem("${APPEARANCE_STORAGE_KEY}") || "null"); } catch (e) {}
  if (saved && valid(saved.theme)) {
    preference = saved.theme;
  } else {
    try {
      var legacy = localStorage.getItem("${LEGACY_THEME_STORAGE_KEY}");
      if (valid(legacy)) preference = legacy;
    } catch (e) {}
  }
  var dark = preference === "dark" || (preference === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  document.documentElement.style.colorScheme = dark ? "dark" : "light";
})();
`;
