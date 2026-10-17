// Shared event presentation rules for the agenda and map.
export const RANGE_OPTIONS = [["1", "Today"], ["7", "1 week"], ["14", "2 weeks"], ["30", "1 month"], ["all", "All"]];
export const PRIORITIES = Object.freeze({
  high: { label: "high priority", color: "#E85A4F", size: 38, order: 0 },
  medium: { label: "medium priority", color: "#D9922F", size: 30, order: 1 },
  low: { label: "low priority", color: "#5C7A93", size: 24, order: 2 },
  ranking: { label: "Not ranked yet", color: "#9AA3AD", size: 30, order: 3 },
});

export function priorityTier(event) {
  return Object.hasOwn(PRIORITIES, event.tier) ? event.tier : "ranking";
}

export function campusToday(now = new Date()) {
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: "America/Los_Angeles", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(now);
  const value = type => parts.find(part => part.type === type).value;
  return `${value("year")}-${value("month")}-${value("day")}`;
}

export function filterEvents(events, range = "14", today = campusToday()) {
  const end = new Date(`${today}T00:00:00Z`);
  const days = RANGE_OPTIONS.some(([key]) => key === range) ? range : "14";
  if (days !== "all") end.setUTCDate(end.getUTCDate() + Number(days) - 1);
  const endIso = end.toISOString().slice(0, 10);
  return events.filter(event => {
    // Undated events remain visible, matching the original Campus Compass.
    if (!event.date) return true;
    const date = String(event.date).slice(0, 10);
    return date >= today && (days === "all" || date <= endIso);
  }).sort((a, b) => PRIORITIES[priorityTier(a)].order - PRIORITIES[priorityTier(b)].order || String(a.date || "9999").localeCompare(String(b.date || "9999")));
}

export function mapGroups(events) {
  const groups = new Map();
  for (const event of events) {
    if (event.is_virtual || event.latitude == null || event.longitude == null) continue;
    const lat = Number(event.latitude), lng = Number(event.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) continue;
    const key = `${lat.toFixed(6)},${lng.toFixed(6)}`;
    if (!groups.has(key)) groups.set(key, { position: [lat, lng], events: [], tier: "ranking" });
    const group = groups.get(key);
    group.events.push(event);
    if (PRIORITIES[priorityTier(event)].order < PRIORITIES[group.tier].order) group.tier = priorityTier(event);
  }
  return [...groups.values()];
}

export function isTransferEvent(event) {
  const text = [event.title, event.category, event.description].filter(Boolean).join(" ");
  return /\btransfer\b|\b(?:UC|CSU|university|college)\s+(?:application|admission|representative)|\b(?:TAG|TAP)\s+(?:workshop|application|admission)|transfer admission guarantee/i.test(text);
}
