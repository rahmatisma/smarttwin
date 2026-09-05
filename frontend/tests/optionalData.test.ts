import assert from "node:assert/strict";
import test from "node:test";
import { fetchOptionalWithin } from "../src/lib/optionalData.ts";

test("a recommendation arriving after the render deadline is still delivered", async () => {
  let resolve!: (value: { phases: string[] }) => void;
  const request = new Promise<{ phases: string[] }>((done) => { resolve = done; });
  const lateResults: { phases: string[] }[] = [];
  assert.equal(await fetchOptionalWithin("Recommendation", request, 5, (value) => lateResults.push(value)), null);
  const recommendation = { phases: ["north", "east", "south", "west"] };
  resolve(recommendation);
  await new Promise<void>((done) => setImmediate(done));
  assert.deepEqual(lateResults, [recommendation]);
});

test("a fast response is returned once without a late update", async () => {
  let lateCalls = 0;
  assert.equal(await fetchOptionalWithin("Recommendation", Promise.resolve("ready"), 50, () => lateCalls++), "ready");
  assert.equal(lateCalls, 0);
});

test("an empty response after the deadline does not overwrite existing data", async () => {
  let resolve!: (value: null) => void;
  let lateCalls = 0;
  const request = new Promise<null>((done) => { resolve = done; });
  assert.equal(await fetchOptionalWithin("Recommendation", request, 5, () => lateCalls++), null);
  resolve(null);
  await new Promise<void>((done) => setImmediate(done));
  assert.equal(lateCalls, 0);
});
