import assert from "node:assert/strict";
import test from "node:test";
import {
  formatReplayClock,
  readDataModeFromState,
} from "../src/lib/dataMode.ts";

test("simulation replay state preserves each arm's historical timestamp", () => {
  const mode = readDataModeFromState({
    dataMode: "replay",
    replayApproaches: ["east", "south"],
    replayDataDate: "2026-08-15T16:30:00+07:00",
    replaySince: "2026-09-10T10:00:00+07:00",
    replaySources: {
      east: "2026-08-15T16:30:00+07:00",
      south: "2026-08-15T16:31:00+07:00",
    },
  });

  assert.equal(mode.mode, "replay");
  assert.deepEqual(mode.replayApproaches, ["east", "south"]);
  assert.deepEqual(mode.replaySources, {
    east: "2026-08-15T16:30:00+07:00",
    south: "2026-08-15T16:31:00+07:00",
  });
  assert.equal(formatReplayClock(mode.replaySources.east), "16.30");
});

test("staleApproaches mapping is accepted as the replay source contract", () => {
  const mode = readDataModeFromState({
    staleApproaches: { west: "2026-08-15T16:32:00+07:00" },
  });

  assert.equal(mode.mode, "replay");
  assert.deepEqual(mode.replayApproaches, ["west"]);
  assert.equal(mode.replaySources.west, "2026-08-15T16:32:00+07:00");
});

test("live state contains no historical sources", () => {
  const mode = readDataModeFromState({ dataMode: "timestamped-observation" });
  assert.equal(mode.mode, "live");
  assert.deepEqual(mode.replaySources, {});
});
