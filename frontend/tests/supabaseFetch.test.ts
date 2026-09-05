import assert from "node:assert/strict";
import test from "node:test";
import { createSupabaseFetch } from "../src/lib/supabaseFetch.ts";

const base = "https://example.supabase.co";
const skew = () => Response.json(
  { code: "PGRST303", message: "JWT issued at future" }, { status: 401 },
);

test("retries clock skew with identical credentials and preserves the response", async () => {
  const delays: number[] = [];
  const init = { headers: { Authorization: "Bearer test-token" } };
  let calls = 0;
  const request = createSupabaseFetch(base, async (_input, options) => {
    assert.equal(options, init);
    return ++calls === 1 ? skew() : Response.json([{ latitude: -7.8 }]);
  }, async (ms) => { delays.push(ms); });
  assert.deepEqual(await (await request(`${base}/rest/v1/intersections`, init)).json(), [{ latitude: -7.8 }]);
  assert.deepEqual(delays, [300]);
  assert.equal(calls, 2);
});

test("persistent skew stops after two retries and keeps the error body readable", async () => {
  let calls = 0;
  const request = createSupabaseFetch(base, async () => { calls++; return skew(); }, async () => {});
  const response = await request(`${base}/rest/v1/intersections`);
  assert.equal(calls, 3);
  assert.equal((await response.json()).message, "JWT issued at future");
});

test("does not retry writes, Auth, other origins, or unrelated errors", async () => {
  for (const [url, method, response] of [
    [`${base}/rest/v1/intersections`, "POST", skew()],
    [`${base}/auth/v1/token`, "GET", skew()],
    ["https://other.example/rest/v1/intersections", "GET", skew()],
    [`${base}/rest/v1/intersections`, "GET", Response.json({ code: "PGRST303", message: "JWT expired" }, { status: 401 })],
    [`${base}/rest/v1/intersections`, "GET", new Response("unavailable", { status: 401 })],
  ] as const) {
    let calls = 0;
    const request = createSupabaseFetch(base, async () => { calls++; return response; }, async () => {});
    assert.equal(await request(url, { method }), response);
    assert.equal(calls, 1);
  }
});

test("abort during backoff prevents another request", async () => {
  const controller = new AbortController();
  let calls = 0;
  const request = createSupabaseFetch(base, async () => { calls++; return skew(); }, async () => { controller.abort(); });
  await request(new Request(`${base}/rest/v1/intersections`, { signal: controller.signal }));
  assert.equal(calls, 1);
});
