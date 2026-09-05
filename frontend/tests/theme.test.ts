import assert from "node:assert/strict";
import test from "node:test";
import { runInNewContext } from "node:vm";
import {
  APPEARANCE_STORAGE_KEY, LEGACY_THEME_STORAGE_KEY, THEME_INIT_SCRIPT,
  readThemePreference, resolveTheme, writeThemePreference,
} from "../src/lib/theme.ts";

function memoryStorage(initial: Record<string, string> = {}): Storage {
  const values = new Map(Object.entries(initial));
  return {
    get length() { return values.size; },
    key: (index) => [...values.keys()][index] ?? null,
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => { values.set(key, value); },
    removeItem: (key) => { values.delete(key); },
    clear: () => values.clear(),
  };
}

test("saved appearance wins over conflicting legacy header preference, including before paint", () => {
  for (const preference of ["light", "dark", "system"] as const) {
    for (const prefersDark of [true, false]) {
      const storage = memoryStorage({
        [APPEARANCE_STORAGE_KEY]: JSON.stringify({ theme: preference }),
        [LEGACY_THEME_STORAGE_KEY]: preference === "dark" ? "light" : "dark",
      });
      const root = { dataset: { theme: "light" }, style: { colorScheme: "light" } };
      runInNewContext(THEME_INIT_SCRIPT, {
        localStorage: storage,
        document: { documentElement: root },
        window: { matchMedia: () => ({ matches: prefersDark }) },
      });
      assert.equal(readThemePreference(storage), preference);
      assert.equal(root.dataset.theme, resolveTheme(preference, prefersDark));
      assert.equal(root.style.colorScheme, root.dataset.theme);
    }
  }
});

test("changing theme persists through a new read and preserves language and compact mode", () => {
  const storage = memoryStorage({
    [APPEARANCE_STORAGE_KEY]: JSON.stringify({ theme: "dark", language: "en", compactMode: true }),
    [LEGACY_THEME_STORAGE_KEY]: "dark",
  });
  writeThemePreference(storage, "light");
  assert.equal(readThemePreference(storage), "light");
  assert.deepEqual(JSON.parse(storage.getItem(APPEARANCE_STORAGE_KEY)!), { theme: "light", language: "en", compactMode: true });
  assert.equal(storage.getItem(LEGACY_THEME_STORAGE_KEY), null);
  writeThemePreference(storage, "system");
  assert.equal(readThemePreference(storage), "system");
  assert.equal(resolveTheme(readThemePreference(storage), true), "dark");
  assert.equal(resolveTheme(readThemePreference(storage), false), "light");
  assert.equal(readThemePreference(storage), "system");
});

test("old header preferences survive migration and malformed appearance JSON", () => {
  const storage = memoryStorage({ [APPEARANCE_STORAGE_KEY]: "invalid", [LEGACY_THEME_STORAGE_KEY]: "light" });
  assert.equal(readThemePreference(storage), "light");
  writeThemePreference(storage, "dark");
  assert.equal(readThemePreference(storage), "dark");
});

test("unavailable storage leaves the page usable with the light default", () => {
  const storage = { getItem() { throw new Error("Storage blocked"); } };
  assert.equal(readThemePreference(storage), "light");
  const root = { dataset: { theme: "dark" }, style: { colorScheme: "dark" } };
  runInNewContext(THEME_INIT_SCRIPT, { localStorage: storage, document: { documentElement: root } });
  assert.equal(root.dataset.theme, "light");
});
