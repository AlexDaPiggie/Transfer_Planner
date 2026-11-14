import test from "node:test";
import assert from "node:assert/strict";

const api = await import("../js/api.js");

test("demo plan avoids network calls", async () => {
  const previousFetch = globalThis.fetch;
  globalThis.fetch = () => { throw new Error("network must not be used"); };
  const result = await api.generatePlan({ source_ids: [113], targets: [] }, { useDemoData: true });
  assert.equal(result.isDemo, true);
  globalThis.fetch = previousFetch;
});

test("live plan uses the documented FastAPI route", async () => {
  let request;
  globalThis.fetch = async (url, options) => {
    request = { url, options };
    return { ok: true, json: async () => ({ matrix: [], summary: "Ready" }) };
  };
  await api.generatePlan({ source_ids: [113], targets: [] }, { useDemoData: false, apiBaseUrl: "http://localhost:8000" });
  assert.equal(request.url, "http://localhost:8000/api/generate-plan");
  assert.equal(request.options.method, "POST");
});

test("an HTML or plain-text server error is reported as unavailable, not offline", async (t) => {
  t.mock.method(globalThis, "fetch", async () => ({
    ok: false, status: 500,
    json: async () => { throw new SyntaxError("Not JSON"); },
  }));
  await assert.rejects(api.getSources({ apiBaseUrl: "https://example.invalid" }), /service is temporarily unavailable/);
});

test("database service errors retain the public retry message", async (t) => {
  t.mock.method(globalThis, "fetch", async () => ({
    ok: false, status: 503,
    json: async () => ({ detail: "School data is temporarily unavailable. Please try again." }),
  }));
  await assert.rejects(api.getSources({ apiBaseUrl: "https://example.invalid" }), /School data is temporarily unavailable/);
});

test("a failed network request gives a message suitable for deployed users", async (t) => {
  t.mock.method(globalThis, "fetch", async () => { throw new TypeError("Failed to fetch"); });
  await assert.rejects(api.getSources({ apiBaseUrl: "https://example.invalid" }), /Could not reach the service/);
});
