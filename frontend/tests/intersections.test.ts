import assert from "node:assert/strict";
import test from "node:test";

import {
  ALL_INTERSECTIONS,
  APPROACH_OPTIONS,
  getIntersectionDatabaseIds,
  getIntersectionName,
} from "../src/lib/intersections.ts";


test("semua pilihan simpang memetakan seluruh database ID", () => {
  assert.deepEqual(
    getIntersectionDatabaseIds("all"),
    ALL_INTERSECTIONS.map(({ databaseId }) => databaseId),
  );
});


test("pilihan simpang tunggal memiliki nama dan satu database ID", () => {
  assert.equal(getIntersectionName("intersection4"), "Simpang Pingit");
  assert.deepEqual(getIntersectionDatabaseIds("intersection4"), ["simpang4-pingit"]);
});


test("kontrak lengan selalu berisi all dan empat arah", () => {
  assert.deepEqual(
    APPROACH_OPTIONS.map(({ id }) => id),
    ["all", "south", "west", "east", "north"],
  );
});
