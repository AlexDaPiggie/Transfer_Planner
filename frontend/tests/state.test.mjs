import test from "node:test";
import assert from "node:assert/strict";

const store = new Map();
globalThis.localStorage = {
  getItem: (key) => store.get(key) ?? null,
  setItem: (key, value) => store.set(key, value),
  removeItem: (key) => store.delete(key),
};

const state = await import("../js/state.js");

test("uses the system preference when there is no saved theme", () => {
  store.clear();
  assert.equal(state.getTheme(false), "light");
  assert.equal(state.getTheme(true), "dark");
});

test("persists only valid theme values", () => {
  store.clear();
  state.setTheme("dark");
  assert.equal(state.getTheme(false), "dark");
  assert.throws(() => state.setTheme("purple"), /Theme/);
});

test("creates and appends messages to local sessions", () => {
  store.clear();
  const session = state.createSession("My plan");
  state.appendMessage(session.id, { role: "user", content: "What transfers?" });
  const saved = state.getAppState();
  assert.equal(saved.sessions[0].messages[0].content, "What transfers?");
});
