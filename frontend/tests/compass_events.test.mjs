import test from "node:test";
import assert from "node:assert/strict";
import { campusToday, filterEvents, mapGroups, priorityTier, isTransferEvent } from "../js/compass_events.js";

test("transfer checkbox recognizes transfer information without hiding unrelated events", () => {
  assert.equal(isTransferEvent({ title: "Transfer workshop" }), true);
  assert.equal(isTransferEvent({ title: "UC application help" }), true);
  assert.equal(isTransferEvent({ category: "Transfer University Representative" }), true);
  assert.equal(isTransferEvent({ title: "TAG workshop" }), true);
  assert.equal(isTransferEvent({ title: "Heritage photography club" }), false);
  assert.equal(isTransferEvent({ title: "Financial aid deadline" }), false);
  assert.equal(isTransferEvent({ title: "Library workshop", description: "Study skills" }), false);
});

test("date presets include the last day, exclude past events, and keep undated events", () => {
  const dates = ["2026-10-15", "2026-10-16", "2026-10-22", "2026-10-23", "2026-10-29", "2026-10-30", "2026-11-14", "2026-11-15", null];
  const events = dates.map(date => ({ date }));
  const inRange = range => filterEvents(events, range, "2026-10-16").map(event => event.date);
  assert.deepEqual(inRange("1"), ["2026-10-16", null]);
  assert.deepEqual(inRange("7"), ["2026-10-16", "2026-10-22", null]);
  assert.deepEqual(inRange("14"), ["2026-10-16", "2026-10-22", "2026-10-23", "2026-10-29", null]);
  assert.equal(inRange("30").includes("2026-11-14"), true);
  assert.equal(inRange("30").includes("2026-11-15"), false);
  assert.equal(inRange("all").includes("2026-10-15"), false);
  assert.equal(inRange("all").includes("2026-11-15"), true);
});

test("campus calendar day and range boundaries handle UTC offsets and year rollover", () => {
  assert.equal(campusToday(new Date("2026-10-17T01:00:00Z")), "2026-10-16");
  const events = [{ date: "2026-12-31" }, { date: "2027-01-06" }, { date: "2027-01-07" }];
  assert.equal(filterEvents(events, "7", "2026-12-31").length, 2);
});

test("map groups share the highest AI tier, exclude invalid coordinates and keep counts", () => {
  const events = [
    { title: "Low", tier: "low", latitude: 37.32, longitude: -122.04 },
    { title: "High", tier: "high", latitude: 37.32, longitude: -122.04 },
    { title: "Medium", tier: "medium", latitude: 37.31, longitude: -122.03 },
    { title: "Online", tier: "high", is_virtual: true, latitude: 37.32, longitude: -122.04 },
    { latitude: 999, longitude: 999 }, { latitude: null, longitude: null },
  ];
  const groups = mapGroups(events);
  assert.equal(groups.length, 2);
  assert.equal(groups[0].tier, "high");
  assert.equal(groups[0].events.length, 2);
  assert.equal(groups[1].tier, "medium");
  assert.equal(priorityTier({ tier: "<unsafe>" }), "ranking");
});

test("filtering retains AI colors and sorts priority before date without mutating input", () => {
  const events = [{ title: "Low", tier: "low", date: "2026-10-16" }, { title: "High", tier: "high", date: "2026-10-20" }];
  assert.deepEqual(filterEvents(events, "7", "2026-10-16").map(event => event.tier), ["high", "low"]);
  assert.equal(events[0].title, "Low");
});
