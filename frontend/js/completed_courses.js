// UI and account-scoped storage for community-college classes students have completed.
// A plan is just a view: account records are fetched again after sign-in/out.
import { API_BASE } from "./config.js";
const apiBase = API_BASE;
let activeBoard = null;
const wiredBoards = new WeakSet();
let completed = new Set();
let user = null;
let ready = false;
let loadVersion = 0;
let saving = false;

const style = document.createElement("link");
style.rel = "stylesheet";
style.href = new URL("../css/completed_courses.css", import.meta.url).href;
document.head.append(style);

function normalCode(value) {
  return String(value || "").trim().replace(/\s+/g, " ").toUpperCase();
}
function courseKey(sourceId, code) {
  return JSON.stringify([Number(sourceId), normalCode(code)]);
}
function variantsOf(card) {
  // ASSIST shows regular/honors alternatives as "CIS 22C or CIS 22CH".
  return (card.dataset.courseCode || "").split(/\s+or\s+/i).map((part) => part.trim()).filter(Boolean);
}
function cardVariants(card) {
  return variantsOf(card).map((code) => ({ code, key: courseKey(card.dataset.sourceId, code) }));
}
function make(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}
function showStatus(column, text, isError = false) {
  const status = column.querySelector(".course-completion-status");
  if (!status) return;
  status.textContent = text;
  status.classList.toggle("is-error", isError);
}

function prepareColumn(column) {
  if (column.querySelector(".course-completed-section")) return;
  const finished = make("section", "course-completed-section");
  finished.hidden = true;
  finished.setAttribute("aria-label", "Completed courses");
  finished.append(make("h4", "course-completed-heading", "Completed"));
  finished.append(make("div", "course-completed-list"));
  column.append(finished);
  const status = make("p", "course-completion-status");
  status.setAttribute("role", "status");
  column.append(status);
}
function decorateCard(card) {
  if (card.querySelector(".course-completion-controls")) return;
  const controls = make("div", "course-completion-controls");
  const variants = variantsOf(card);
  if (variants.length > 1) {
    const picker = make("select", "course-variant-select");
    picker.setAttribute("aria-label", "Choose the course you actually took");
    for (const code of variants) {
      const option = document.createElement("option");
      option.value = code;
      option.textContent = code;
      picker.append(option);
    }
    controls.append(picker);
  }
  const button = make("button", "course-completion-button", "Mark complete");
  button.type = "button";
  button.dataset.completionToggle = "1";
  controls.append(button);
  card.append(controls);
}
function drawUniversityCompletions() {
  for (const university of document.querySelectorAll("#results .university-course-plan, #results #combined-course-board")) {
    for (const column of university.querySelectorAll(".course-column.required, .course-column.recommended")) {
      if (!column.querySelector(".course-completion-status")) {
        const status = make("p", "course-completion-status");
        status.setAttribute("role", "status");
        column.append(status);
      }
    }
    for (const row of university.querySelectorAll(".equivalency-course[data-source-id][data-course-code]")) {
      const isDone = !!user && ready && cardVariants(row).some(entry => completed.has(entry.key));
      row.classList.toggle("is-completed-course", isDone);
      let badge = row.querySelector(".university-course-completed-badge");
      if (!badge) {
        badge = make("span", "university-course-completed-badge", "Completed");
        row.append(badge);
      }
      badge.hidden = !isDone;
      decorateCard(row);
      const button = row.querySelector('.course-completion-button');
      button.textContent = !ready ? 'Loading...' : !user ? 'Log in to track' : isDone ? 'Undo' : 'Mark complete';
      button.disabled = !user || !ready || saving;
      const picker = row.querySelector('.course-variant-select');
      if (picker) picker.disabled = !user || !ready || saving || isDone;
    }
    for (const group of university.querySelectorAll(".equivalency-group:not(.not-articulated-group)")) {
      // Any valid articulation alternative can satisfy the requirement,
      // including alternatives hidden by the current display selection.
      const isDone = [...group.querySelectorAll('.equivalency-option')].some(option => {
        const parts = new Map();
        for (const row of option.querySelectorAll('.equivalency-course')) {
          const key = row.dataset.completionPart || '0';
          if (!parts.has(key)) parts.set(key, []);
          parts.get(key).push(row);
        }
        return parts.size > 0 && [...parts.values()].every(rows => {
          const done = row => row.classList.contains('is-completed-course');
          return rows[0].dataset.courseConjunction === 'or'
            ? rows.some(done)
            : rows.every(done);
        });
      });
      group.classList.toggle("is-completed-requirement", isDone);
    }
  }
}

function draw() {
  if (!activeBoard?.isConnected) return;
  drawUniversityCompletions();
  for (const column of activeBoard.querySelectorAll(".course-column.recommended, .course-column.required")) {
    prepareColumn(column);
    const pending = column.querySelector(".course-card-list");
    const finished = column.querySelector(".course-completed-section");
    const finishedList = finished.querySelector(".course-completed-list");
    for (const card of column.querySelectorAll(".course-board-card[data-source-id][data-course-code]")) {
      decorateCard(card);
      const entries = cardVariants(card);
      const matched = entries.find((entry) => completed.has(entry.key));
      const isDone = !!matched && !!user && ready;
      card.classList.toggle("is-completed-course", isDone);
      const control = card.querySelector(".course-completion-controls");
      const picker = control.querySelector("select");
      const button = control.querySelector("button");
      if (picker && isDone) picker.value = matched.code;
      if (picker) picker.disabled = !user || !ready || saving || isDone;
      button.textContent = !ready ? "Loading..." : !user ? "Log in to track" : isDone ? "Undo" : "Mark complete";
      button.disabled = !user || !ready || saving;
      (isDone ? finishedList : pending).append(card);
    }
    finished.hidden = !finishedList.children.length;
    let allDone = pending.querySelector(".course-all-completed");
    if (!allDone) {
      allDone = make("p", "course-all-completed", "All displayed courses are completed.");
      pending.append(allDone);
    }
    allDone.hidden = !!pending.querySelector(".course-board-card") || !finishedList.children.length;
    // Hide the old empty-message placeholder if this column has saved completions.
    const originalEmpty = pending.querySelector(".empty-course-column");
    if (originalEmpty) originalEmpty.hidden = !!finishedList.children.length;
  }
}

async function api(path, options = {}) {
  const response = await fetch(`${apiBase}${path}`, {
    credentials: "include",
    ...options,
    headers: { "X-Pathway-Request": "1", ...(options.body ? { "Content-Type": "application/json" } : {}) },
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : `Server error ${response.status}`);
  return result;
}

async function refresh() {
  const current = ++loadVersion;
  ready = false;
  draw();
  if (!activeBoard?.isConnected) return;
  try {
    const auth = await api("/api/auth/me");
    if (current !== loadVersion) return;
    user = auth.logged_in ? auth.user : null;
    completed = new Set();
    if (user) {
      const data = await api("/api/completed-courses");
      if (current !== loadVersion) return;
      completed = new Set((data.courses || []).map((item) => courseKey(item.source_id, item.course_code)));
    }
    ready = true;
    draw();
  } catch (error) {
    if (current !== loadVersion) return;
    ready = false;
    draw();
    for (const column of document.querySelectorAll("#results .course-column.recommended, #results .course-column.required")) {
      showStatus(column, `Could not load completed courses: ${error.message}`, true);
    }
  }
}

async function toggleCompleted(button) {
  if (!user || !ready || saving) return;
  const card = button.closest(".course-board-card, .equivalency-course");
  const column = card?.closest(".course-column");
  if (!card || !column) return;
  const variants = cardVariants(card);
  const alreadyDone = variants.find((entry) => completed.has(entry.key));
  const picker = card.querySelector(".course-variant-select");
  const chosen = alreadyDone?.code || picker?.value || variants[0]?.code;
  if (!chosen) return;
  const versionAtSave = loadVersion;
  const userAtSave = user.user_id;
  saving = true;
  draw();
  showStatus(column, "Saving...");
  try {
    await api("/api/completed-courses", {
      method: alreadyDone ? "DELETE" : "POST",
      body: JSON.stringify({ source_id: Number(card.dataset.sourceId), course_code: chosen }),
    });
    if (versionAtSave === loadVersion && user?.user_id === userAtSave) {
      const key = courseKey(card.dataset.sourceId, chosen);
      if (alreadyDone) completed.delete(key);
      else completed.add(key);
      showStatus(column, "Saved to your account.");
    }
  } catch (error) {
    if (versionAtSave === loadVersion) showStatus(column, `Could not save: ${error.message}`, true);
  } finally {
    saving = false;
    draw();
  }
}

// Called whenever the current plan is rendered, including saved plans.
export function mountCompletedCourses(plan) {
  const board = document.querySelector("#results #combined-course-board .course-board-columns")
    || document.querySelector("#results .course-board-columns");
  activeBoard = board;
  if (!board || !plan?.plan?.course_board) return;
  for (const column of board.querySelectorAll(".course-column.recommended, .course-column.required")) {
    prepareColumn(column);
  }
  if (!wiredBoards.has(board)) {
    board.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-completion-toggle]");
      if (button && board.contains(button)) toggleCompleted(button);
    });
    wiredBoards.add(board);
  }
  if (ready) draw();
  else refresh();
}

document.addEventListener('click', event => {
  const button = event.target.closest('.university-course-plan button[data-completion-toggle]');
  if (button) toggleCompleted(button);
});

window.addEventListener("pathway:auth-changed", (event) => {
  user = event.detail?.user || null;
  completed = new Set();
  ready = false;
  if (activeBoard?.isConnected) refresh();
});
