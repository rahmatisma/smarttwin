import assert from "node:assert/strict";
import test from "node:test";
import { createScenarioPoller } from "../src/lib/scenarioPolling.ts";

test("overlapping scenario requests share one fetch, then refresh after five seconds", async () => {
    let clock = 0;
    let calls = 0;
    let finish!: (response: Response) => void;
    const poll = createScenarioPoller({ baseUrl: "http://backend", now: () => clock,
        fetcher: async () => { calls++; return new Promise<Response>(resolve => { finish = resolve; }); } });
    const first = poll("pingit");
    assert.equal(poll("pingit"), first);
    finish(Response.json({ status: "unavailable", candidates: [] }));
    await first;
    await poll("pingit");
    assert.equal(calls, 1);
    clock = 5001;
    const next = poll("pingit");
    finish(Response.json({ status: "completed", candidates: [] }));
    assert.equal((await next)?.status, "completed");
    assert.equal(calls, 2);
});

test("network failure backs off and automatically recovers without serving an old result", async () => {
    let clock = 0;
    let calls = 0;
    let warnings = 0;
    const poll = createScenarioPoller({ baseUrl: "http://backend", now: () => clock,
        onUnavailable: () => warnings++, fetcher: async () => {
            calls++;
            if (calls === 2) throw new TypeError("Failed to fetch");
            return Response.json({ status: "completed", candidates: [] });
        } });
    assert.equal((await poll("pingit"))?.status, "completed");
    clock = 5001;
    assert.equal(await poll("pingit"), null);
    clock = 10_001;
    assert.equal(await poll("pingit"), null);
    assert.equal(calls, 2);
    assert.equal(warnings, 1);
    clock = 20_002;
    assert.equal((await poll("pingit"))?.status, "completed");
    assert.equal(calls, 3);
});

test("timeout aborts the actual HTTP request and clears the in-flight entry", async () => {
    let aborted = false;
    let clock = 0;
    let calls = 0;
    const poll = createScenarioPoller({ baseUrl: "http://backend", timeoutMs: 5, now: () => clock,
        onUnavailable: () => {}, fetcher: async (_url, options) => {
            calls++;
            if (calls > 1) return Response.json({ status: "unavailable", candidates: [] });
            return new Promise<Response>((_resolve, reject) => {
                options!.signal!.addEventListener("abort", () => {
                    aborted = true;
                    reject(new DOMException("Aborted", "AbortError"));
                }, { once: true });
            });
        } });
    assert.equal(await poll("pingit"), null);
    assert.equal(aborted, true);
    clock = 15_001;
    assert.equal((await poll("pingit"))?.status, "unavailable");
    assert.equal(calls, 2);
});

test("an unavailable backend backs off independently for each intersection", async () => {
    let calls = 0;
    const poll = createScenarioPoller({ baseUrl: "http://backend", onUnavailable: () => {},
        fetcher: async () => { calls++; return new Response(null, { status: 503 }); } });
    assert.equal(await poll("pingit"), null);
    assert.equal(await poll("pingit"), null);
    assert.equal(await poll("other"), null);
    assert.equal(calls, 2);
});
