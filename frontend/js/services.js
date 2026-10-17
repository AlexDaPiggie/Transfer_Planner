import { escapeHtml } from "./ui.js";
import { API_BASE } from "./config.js";
import { interestChoices } from "./interest_categories.js";
import { RANGE_OPTIONS, PRIORITIES, priorityTier, filterEvents, mapGroups, isTransferEvent } from "./compass_events.js";

// Use the same host as the session cookie used by auth.js.
const apiBase = `${API_BASE}/api/compass`;

async function request(path, method = "GET", body) {
  const response = await fetch(`${apiBase}/${path}`, {
    method, credentials: "include",
    headers: { "X-Pathway-Request": "1", ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Please check your profile and try again.");
  return data;
}

const emailAction = new URLSearchParams(location.hash.slice(1));
for (const [key, endpoint, label] of [["confirm", "confirm-email", "Confirm daily campus emails"], ["unsubscribe", "unsubscribe", "Turn off daily campus emails"]]) {
  if (!emailAction.has(key)) continue;
  const token = emailAction.get(key);
  history.replaceState(null, "", location.pathname + location.search);
  const banner = document.createElement("section");
  banner.className = "card email-action";
  const button = document.createElement("button");
  button.className = "primary"; button.type = "button"; button.textContent = label;
  const message = document.createElement("p"); message.setAttribute("role", "status");
  banner.append(button, message);
  document.querySelector(".page").before(banner);
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const result = await request(endpoint, "POST", { token });
      message.textContent = result.message;
      window.dispatchEvent(new Event("pathway:email-changed"));
    } catch (error) { message.textContent = error.message; button.disabled = false; }
  });
}

export function renderServiceHome(app) {
  app.innerHTML = `
    <section class="hero home-hero" aria-labelledby="home-title">
      <h1 id="home-title">Let's make College Easier</h1>
      <p>Plan your transfer, find campus events, and get answers.</p>
    </section>
    <section class="service-grid" aria-label="De Anza Guide services">
        <article class="card service-card planner-service"><span class="service-card-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21V5.5Z"/><path d="M4 6h13M8 10h8m-8 4h6"/></svg></span><span class="service-eyebrow">Transfer Planner</span><p>Build a transfer plan with verified ASSIST courses.</p><a class="primary" href="?service=transfer">Plan your transfer <span aria-hidden="true">→</span></a></article>
        <article class="card service-card events-service"><span class="service-card-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><rect x="3.5" y="5" width="17" height="16" rx="3"/><path d="M7.5 3v4m9-4v4M4 9h16m-12 4h3m-3 4h7"/></svg></span><span class="service-eyebrow">De Anza Events</span><p>Find campus events, workshops, and key dates.</p><a class="primary" href="?service=compass">Explore events <span aria-hidden="true">→</span></a></article>
        <article class="card service-card chat-service"><span class="service-card-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M20 11.5a7.5 7.5 0 0 1-8 7.5 8.7 8.7 0 0 1-3.7-.8L4 20l1.2-3.7A7.1 7.1 0 0 1 4 12c0-4.1 3.6-7.5 8-7.5s8 3.1 8 7Z"/><path d="M8 12h.01M12 12h.01M16 12h.01"/></svg></span><span class="service-eyebrow">De Anza Chatbot</span><p>Get answers about courses, deadlines, and campus services.</p><a class="primary" href="?service=chat">Ask De Anza <span aria-hidden="true">→</span></a></article>
    </section>`;
}

export function renderChatbot(app) {
  app.classList.add("chatbot-page");
  app.innerHTML = `<section class="chatbot-service" aria-label="De Anza Chatbot"><iframe class="chatbot-frame" title="De Anza Chatbot" src="/chatbot/?embed=1"></iframe></section>`;
}

let leafletPromise;
function loadMapLibrary() {
  if (window.L) return Promise.resolve(window.L);
  if (!leafletPromise) leafletPromise = new Promise((resolve, reject) => {
    const css = document.createElement("link");
    css.rel = "stylesheet"; css.href = "vendor/leaflet/leaflet.css";
    document.head.append(css);
    const script = document.createElement("script");
    script.src = "vendor/leaflet/leaflet.js";
    script.onload = () => resolve(window.L);
    script.onerror = () => reject(new Error("The map could not load. Events are available below."));
    document.head.append(script);
  });
  return leafletPromise;
}

function safeUrl(value) {
  try { const url = new URL(value); return ["https:", "http:"].includes(url.protocol) ? url.href : null; }
  catch { return null; }
}

export async function renderCompass(app) {
  app.classList.add("compass-page");
  app.closest(".content")?.classList.add("compass-content");
  app.innerHTML = `<div class="hero"><p class="service-eyebrow">DE ANZA EVENTS</p><h1>Find your next opportunity</h1><p>De Anza events and deadlines, shaped around you.</p></div><div class="compass-layout"><form class="card compass-profile" id="compass-profile"><h2>Your student profile</h2><label>Major<select name="major" aria-label="Major"></select></label><fieldset class="compass-interests"><legend>What are you looking for?</legend><div class="compass-interest-options" id="compass-interest-options"></div></fieldset><button class="primary" type="submit" disabled>Save and recommend</button><p id="compass-profile-status" class="compass-status" role="status">Log in to save your profile and personalize events.</p></form><section aria-label="De Anza events"><div id="compass-map" class="compass-map" aria-label="Map of De Anza events"></div><p id="compass-status" class="compass-status" role="status">Loading campus events…</p><div id="compass-events" class="compass-events"></div></section></div>`;
  const form = app.querySelector("form");
  const sidebar = document.createElement("div");
  form.replaceWith(sidebar); sidebar.append(form);
  sidebar.insertAdjacentHTML("beforeend", `<section class="card compass-profile email-settings"><h2>Stay in the loop</h2><label class="email-opt-in"><input id="compass-email-toggle" type="checkbox" disabled> Daily campus event emails</label><p id="compass-email-status" class="compass-status" role="status">Log in to manage event emails.</p></section>`);
  const emailToggle = app.querySelector("#compass-email-toggle");
  const emailStatus = app.querySelector("#compass-email-status");
  const submit = form.querySelector("button");
  function renderInterests(saved = []) {
    form.querySelector("#compass-interest-options").innerHTML = interestChoices(saved).map(item => `<button type="button" class="compass-interest-chip" data-interest="${escapeHtml(item.value)}" aria-pressed="${item.selected}">${escapeHtml(item.label)}</button>`).join("");
  }
  renderInterests(["transfer"]);
  const selectedInterests = () => [...form.querySelectorAll('button[data-interest][aria-pressed="true"]')].map(button => button.dataset.interest);
  form.querySelector("#compass-interest-options").addEventListener("click", event => {
    const button = event.target.closest("button[data-interest]");
    if (!button) return;
    button.setAttribute("aria-pressed", String(button.getAttribute("aria-pressed") !== "true"));
    noteProfileChange();
    if (eventsLoaded) drawEvents(displayedEvents);
  });

  const majorSelect = form.elements.major;
  const clearMajor = document.createElement("button");
  clearMajor.type = "button";
  clearMajor.className = "compass-clear-major";
  clearMajor.textContent = "Clear major";
  clearMajor.disabled = true;
  majorSelect.after(clearMajor);
  const updateMajorClear = () => { clearMajor.disabled = !majorSelect.value; };
  majorSelect.addEventListener("change", updateMajorClear);
  clearMajor.addEventListener("click", () => {
    majorSelect.value = "";
    majorSelect.dispatchEvent(new Event("change", { bubbles: true }));
    majorSelect.focus();
  });
  const profileStatus = app.querySelector("#compass-profile-status");
  const status = app.querySelector("#compass-status");
  let accountVersion = 0, loggedIn = false, optionsReady = false, busy = false;
  let map, markers, mapLibrary, displayedEvents = [], rawEvents = [], eventsLoaded = false, rankingReady = false;
  let selectedRange = "14", selectedLocation = null, profileRevision = 0;
  const updateButton = () => {
    submit.disabled = !loggedIn || !optionsReady || busy;
    updateMajorClear();
  };

  const rangeControls = document.createElement("div");
  rangeControls.className = "compass-range-controls";
  rangeControls.innerHTML = `<div class="compass-range" role="group" aria-label="Event date range">${RANGE_OPTIONS.map(([value, label]) => `<button type="button" data-range="${value}" aria-pressed="${value === selectedRange}">${label}</button>`).join("")}</div><div class="compass-legend" aria-label="AI priority legend">${Object.entries(PRIORITIES).map(([tier, info]) => `<span><i class="priority-dot priority-${tier}" aria-hidden="true"></i>${escapeHtml(info.label)}</span>`).join("")}</div>`;
  const mapElement = app.querySelector("#compass-map");
  const explorer = document.createElement("div");
  explorer.className = "compass-explorer";
  mapElement.before(rangeControls, explorer);
  explorer.append(mapElement);
  const resultsPanel = document.createElement("section");
  resultsPanel.className = "compass-results";
  resultsPanel.setAttribute("aria-label", "Events at selected location");
  const selectionBar = document.createElement("div");
  selectionBar.className = "compass-location-selection";
  selectionBar.hidden = true;
  const selectionLabel = document.createElement("strong");
  const clearLocation = document.createElement("button");
  clearLocation.type = "button";
  clearLocation.textContent = "Show all locations";
  selectionBar.append(selectionLabel, clearLocation);
  resultsPanel.append(selectionBar, status, app.querySelector("#compass-events"));
  explorer.append(resultsPanel);
  clearLocation.addEventListener("click", () => { selectedLocation = null; drawEvents(displayedEvents, false); });
  const locationKey = group => group.position.map(value => value.toFixed(6)).join(",");

  rangeControls.addEventListener("click", event => {
    const button = event.target.closest("button[data-range]");
    if (!button) return;
    selectedRange = button.dataset.range;
    rangeControls.querySelectorAll("button").forEach(item => item.setAttribute("aria-pressed", String(item === button)));
    if (eventsLoaded) drawEvents(displayedEvents);
  });

  function drawEvents(events, fitMap = true) {
    displayedEvents = events;
    const inRange = filterEvents(events, selectedRange).filter(event => selectedInterests().includes("transfer") || !isTransferEvent(event));
    const groups = mapGroups(inRange);
    const selectedGroup = groups.find(group => locationKey(group) === selectedLocation);
    if (!selectedGroup) selectedLocation = null;
    const visible = selectedGroup ? selectedGroup.events : inRange;
    selectionBar.hidden = !selectedGroup;
    selectionLabel.textContent = selectedGroup ? [...new Set(selectedGroup.events.map(event => event.location || "Selected location"))].join(" / ") : "";
    app.querySelector("#compass-events").innerHTML = visible.map(event => {
      const url = safeUrl(event.url);
      const tier = priorityTier(event);
      return `<article class="card compass-event priority-${tier}" data-priority="${tier}"><span class="compass-event-meta">${escapeHtml([event.date, event.time, event.location].filter(Boolean).join(" | "))}</span><h3>${escapeHtml(event.title)}</h3><strong class="compass-priority-badge">${PRIORITIES[tier].label}</strong><p>${escapeHtml(event.reason || event.description || "")}</p>${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Event details &rarr;</a>` : ""}</article>`;
    }).join("");
    if (markers) {
      markers.clearLayers();
      const positions = [];
      for (const group of groups) {
        const info = PRIORITIES[group.tier];
        const icon = mapLibrary.divIcon({
          className: `compass-marker${locationKey(group) === selectedLocation ? " is-selected" : ""}`,
          html: `<div class="compass-pin priority-${group.tier}" style="width:${info.size}px;height:${info.size}px"><span>${group.events.length > 1 ? group.events.length : "&#9679;"}</span></div>`,
          iconSize: [info.size, info.size], iconAnchor: [info.size / 2, info.size], popupAnchor: [0, -info.size],
        });
        const marker = mapLibrary.marker(group.position, { icon, title: `${group.events.length} event(s), ${info.label}` }).addTo(markers);
        marker.on("click", () => {
          selectedLocation = locationKey(group);
          drawEvents(displayedEvents, false);
          if (window.matchMedia("(max-width: 1099px)").matches) resultsPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
        });
        positions.push(group.position);
      }
      if (fitMap && positions.length) map.fitBounds(positions, { padding: [25, 25], maxZoom: 17, animate: false });
    }
    const highCount = visible.filter(event => priorityTier(event) === "high").length;
    status.textContent = visible.length ? `${visible.length} events ${selectedGroup ? "at this location" : "in this range"} | ${highCount} high priority | ${inRange.length} in selected range` : "No events in this range. Try a wider range above.";
  }

  async function accountChanged() {
    const version = ++accountVersion;
    loggedIn = false; busy = false; rankingReady = false; selectedLocation = null; form.reset(); renderInterests(["transfer"]); updateButton();
    if (eventsLoaded) drawEvents(rawEvents);
    updateMajorClear();
    emailToggle.checked = false; emailToggle.disabled = true;
    emailStatus.textContent = "Log in to manage event emails.";
    profileStatus.textContent = "Log in to save your profile and personalize events.";
    try {
      const me = await fetch(`${API_BASE}/api/auth/me`, { credentials: "include" }).then(r => { if (!r.ok) throw new Error("Account unavailable"); return r.json(); });
      if (version !== accountVersion || !me.logged_in) return;
      loggedIn = true;
      const data = await request("profile");
      if (version !== accountVersion) return;
      form.elements.major.value = data.profile.major;
      updateMajorClear();
      renderInterests(data.profile.interests);
      if (eventsLoaded) drawEvents(displayedEvents, false);
      profileStatus.textContent = "Your profile is linked to your Pathway account.";
      await loadEmailPreferences(version);
      if (version !== accountVersion) return;
      if (data.profile.major || data.profile.interests.length) {
        busy = true; updateButton();
        profileStatus.textContent = "Preparing recommendations for your saved profile...";
        const revision = profileRevision;
        const result = await request("rerank", "POST");
        if (version !== accountVersion) return;
        if (revision !== profileRevision) { profileStatus.textContent = "Profile changed. Select Save and recommend to update your AI priorities."; return; }
        rankingReady = true; eventsLoaded = true;
        drawEvents(result.events);
        profileStatus.textContent = "Your saved profile and recommendations are ready.";
      }
    } catch { if (version === accountVersion) profileStatus.textContent = busy ? "Your profile is loaded, but recommendations are unavailable. Try Save and recommend again." : "Your profile could not load. Please try again."; }
    finally { if (version === accountVersion) { busy = false; updateButton(); } }
  }

  async function loadEmailPreferences(version = accountVersion) {
    try {
      const preferences = await request("email-preferences");
      if (version !== accountVersion) return;
      emailToggle.checked = preferences.enabled;
      emailToggle.disabled = !loggedIn || (!preferences.available && !preferences.enabled);
      emailStatus.textContent = preferences.enabled ? "Daily emails are on. Turn this off at any time." : preferences.available ? "Turn on daily emails to receive personalized campus events." : "Daily event emails are not available yet.";
    } catch (error) { if (version === accountVersion) emailStatus.textContent = error.message; }
  }

  window.addEventListener("pathway:email-changed", () => { if (loggedIn) loadEmailPreferences(); });
  emailToggle.addEventListener("change", async () => {
    const version = accountVersion;
    emailToggle.disabled = true;
    try {
      await request("email-preferences", "PUT", { enabled: emailToggle.checked });
      if (version === accountVersion) await loadEmailPreferences(version);
    } catch (error) {
      if (version === accountVersion) { emailToggle.checked = !emailToggle.checked; emailStatus.textContent = error.message; emailToggle.disabled = !loggedIn; }
    }
  });

  function noteProfileChange() {
    profileRevision += 1;
    if (loggedIn) profileStatus.textContent = "Profile changed. Select Save and recommend to update your AI priorities.";
  }
  form.addEventListener("input", noteProfileChange);
  form.addEventListener("change", noteProfileChange);

  window.addEventListener("pathway:auth-changed", () => {
    // Remove personalized results when the active account changes.
    accountChanged();
  });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (submit.disabled) return;
    const version = accountVersion;
    const revision = profileRevision;
    busy = true; updateButton();
    profileStatus.textContent = "Saving profile and preparing recommendations…";
    try {
      await request("profile", "PUT", { transfer_stage: "", major: form.elements.major.value, interests: selectedInterests() });
      if (version !== accountVersion) return;
      profileStatus.textContent = "Profile saved. Preparing recommendations…";
      const result = await request("rerank", "POST");
      if (version !== accountVersion) return;
      if (revision !== profileRevision) { profileStatus.textContent = "Profile changed. Select Save and recommend to update your AI priorities."; return; }
      rankingReady = true; eventsLoaded = true;
      drawEvents(result.events);
      profileStatus.textContent = "Profile saved. Your recommendations are ready.";
    } catch (error) { if (version === accountVersion) profileStatus.textContent = error.message; }
    finally { if (version === accountVersion) { busy = false; updateButton(); } }
  });

  loadMapLibrary().then(L => {
    mapLibrary = L;
    map = L.map("compass-map").setView([37.31928, -122.04479], 16);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' }).addTo(map);
    markers = L.layerGroup().addTo(map);
    if (eventsLoaded) drawEvents(displayedEvents);
  }).catch(error => { app.querySelector("#compass-map").textContent = error.message; });
  request("events").then(data => { rawEvents = data.events; eventsLoaded = true; if (!rankingReady) drawEvents(rawEvents); }).catch(error => { if (!rankingReady) status.textContent = error.message; });
  try {
    const options = await request("profile-options");
    form.elements.major.innerHTML = `<option value="">No major selected</option>` + options.majors.map(major => `<option>${escapeHtml(major)}</option>`).join("");
    optionsReady = true;
    await accountChanged();
  } catch (error) { profileStatus.textContent = error.message; }
}
