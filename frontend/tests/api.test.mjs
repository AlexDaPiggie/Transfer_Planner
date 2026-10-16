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
