import { APP_CONFIG } from "./config.js";
import { ACTIVE_YEAR_ID, generatePlan, getMajors, getSources, getTargets, sendChat } from "./api.js";
import { appendMessage, clearSessionMessages, createSession, getAppState, getTheme, selectSession, setTheme } from "./state.js";
import { escapeHtml, renderMessages, renderPlan } from "./ui.js";

const app = document.querySelector("#app");
const themeButton = document.querySelector("#theme-button");
let activeChatController = null;

const plannerState = {
  colleges: [],
  goals: [],
  mainCollegeId: null,
  sourceCatalog: [],
  targetCatalog: [],
  majorCatalog: [],
};

setTheme(getTheme());
refreshThemeButton();
themeButton.addEventListener("click", () => {
  setTheme(document.body.dataset.theme === "dark" ? "light" : "dark");
  refreshThemeButton();
});
function refreshThemeButton() {
  themeButton.textContent = document.body.dataset.theme === "dark" ? "☾ Dark" : "☀ Light";
}

function pageTemplate(content) {
  app.innerHTML = `<div class="hero"><p class="eyebrow">Verified transfer planning</p><h1>Build a clearer path forward.</h1><p>Add the community colleges you can attend and the university programs you want to keep open. Pathway uses saved Assist agreements to build your plan.</p></div>${content}`;
}

function options(items) {
  return items.map((item) => `<option value="${escapeHtml(item.name)}"></option>`).join("");
}

function selectedCollegeIds() {
  return plannerState.colleges.map((college) => college.id);
}

function itemForName(items, name) {
  const normalized = name.trim().toLocaleLowerCase();
  return items.find((item) => item.name.toLocaleLowerCase() === normalized);
}

function renderCollegeChoices() {
  const area = document.querySelector("#college-choices");
  if (!plannerState.colleges.length) {
    area.innerHTML = `<p class="selection-hint">Add at least one college. Your first college becomes the main college.</p>`;
    return;
  }
  area.innerHTML = plannerState.colleges.map((college) => `
    <div class="selection-chip ${college.id === plannerState.mainCollegeId ? "is-main" : ""}">
      <label><input type="radio" name="main-college" value="${college.id}" ${college.id === plannerState.mainCollegeId ? "checked" : ""}> Main</label>
      <span>${escapeHtml(college.name)}</span>
      <button class="chip-remove" type="button" data-remove-college="${college.id}" aria-label="Remove ${escapeHtml(college.name)}">×</button>
    </div>`).join("");

  area.querySelectorAll("input[name='main-college']").forEach((radio) => {
    radio.addEventListener("change", () => {
      plannerState.mainCollegeId = Number(radio.value);
      renderCollegeChoices();
    });
  });
  area.querySelectorAll("[data-remove-college]").forEach((button) => {
    button.addEventListener("click", async () => {
      const collegeId = Number(button.dataset.removeCollege);
      plannerState.colleges = plannerState.colleges.filter((college) => college.id !== collegeId);
      if (plannerState.mainCollegeId === collegeId) plannerState.mainCollegeId = plannerState.colleges[0]?.id ?? null;
      plannerState.goals = [];
      renderCollegeChoices();
      renderGoals();
      await refreshUniversityChoices();
      updatePlanButton();
    });
  });
}

function renderGoals() {
  const area = document.querySelector("#goals");
  area.innerHTML = plannerState.goals.length
    ? plannerState.goals.map((goal, index) => `<button class="selection-chip goal-chip" type="button" data-remove-goal="${index}">${escapeHtml(goal.target_name)} · ${escapeHtml(goal.major)} <span aria-hidden="true">×</span></button>`).join("")
    : `<p class="selection-hint">Add one or more university-major goals.</p>`;
  area.querySelectorAll("[data-remove-goal]").forEach((button) => {
    button.addEventListener("click", () => {
      plannerState.goals.splice(Number(button.dataset.removeGoal), 1);
      renderGoals();
      updatePlanButton();
    });
  });
}

function updatePlanButton() {
  document.querySelector("#generate").disabled = !plannerState.colleges.length || !plannerState.goals.length;
}

function showPlannerError(error) {
  document.querySelector("#results").innerHTML = `<p class="notice">${escapeHtml(error.message)}</p>`;
}

async function refreshUniversityChoices() {
  const universityInput = document.querySelector("#university-search");
  const major = document.querySelector("#major-search");
  plannerState.targetCatalog = [];
  plannerState.majorCatalog = [];
  document.querySelector("#university-options").innerHTML = "";
  document.querySelector("#major-options").innerHTML = "";
  major.value = "";
  major.disabled = true;
  major.placeholder = "Choose a university first";
  if (!plannerState.colleges.length) {
    universityInput.value = "";
    universityInput.disabled = true;
    return;
  }
  universityInput.disabled = true;
  universityInput.placeholder = "Loading universities…";
  try {
    plannerState.targetCatalog = await getTargets(selectedCollegeIds(), APP_CONFIG);
    document.querySelector("#university-options").innerHTML = options(plannerState.targetCatalog);
    universityInput.disabled = !plannerState.targetCatalog.length;
    universityInput.placeholder = plannerState.targetCatalog.length ? "Type a university name" : "No saved university agreements";
  } catch (error) {
    showPlannerError(error);
    universityInput.placeholder = "Could not load universities";
  }
}

async function refreshMajorChoices() {
  const university = itemForName(plannerState.targetCatalog, document.querySelector("#university-search").value);
  const major = document.querySelector("#major-search");
  if (!university) {
    plannerState.majorCatalog = [];
    document.querySelector("#major-options").innerHTML = "";
    major.value = "";
    major.disabled = true;
    major.placeholder = "Choose a university first";
    return;
  }
  plannerState.majorCatalog = [];
  document.querySelector("#major-options").innerHTML = "";
  major.disabled = true;
  major.value = "";
  major.placeholder = "Loading majors…";
  try {
    const majors = await getMajors(selectedCollegeIds(), university.id, APP_CONFIG);
    plannerState.majorCatalog = majors;
    document.querySelector("#major-options").innerHTML = options(majors);
    major.disabled = !majors.length;
    major.placeholder = majors.length ? "Search for a major" : "No saved majors";
  } catch (error) {
    showPlannerError(error);
  }
}

function addCollege() {
  const input = document.querySelector("#college-search");
  const college = itemForName(plannerState.sourceCatalog, input.value);
  if (!college) {
    document.querySelector("#college-message").textContent = "Choose a college from the suggested list.";
    return;
  }
  if (!plannerState.colleges.some((item) => item.id === college.id)) {
    plannerState.colleges.push(college);
    plannerState.mainCollegeId ??= college.id;
  }
  input.value = "";
  document.querySelector("#college-message").textContent = "";
  plannerState.goals = [];
  renderCollegeChoices();
  renderGoals();
  refreshUniversityChoices();
  updatePlanButton();
}

function addGoal() {
  const university = itemForName(plannerState.targetCatalog, document.querySelector("#university-search").value);
  const majorInput = document.querySelector("#major-search");
  const major = itemForName(plannerState.majorCatalog, majorInput.value);
  if (!university || !major || majorInput.disabled || !plannerState.targetCatalog.some((item) => item.id === university.id)) return;
  const goal = { target_id: university.id, target_name: university.name, major: major.name };
  if (!plannerState.goals.some((item) => item.target_id === goal.target_id && item.major === goal.major)) plannerState.goals.push(goal);
  document.querySelector("#university-search").value = "";
  majorInput.value = "";
  majorInput.disabled = true;
  majorInput.placeholder = "Choose a university first";
  plannerState.majorCatalog = [];
  document.querySelector("#major-options").innerHTML = "";
  renderGoals();
  updatePlanButton();
}

async function loadPlan() {
  const button = document.querySelector("#generate");
  button.disabled = true;
  button.textContent = "Building verified plan…";
  try {
    const plan = await generatePlan({
      year_id: ACTIVE_YEAR_ID,
      source_ids: selectedCollegeIds(),
      main_source_id: plannerState.mainCollegeId,
      targets: plannerState.goals,
    }, APP_CONFIG);
    const contextKey = JSON.stringify({
      year_id: ACTIVE_YEAR_ID,
      source_ids: selectedCollegeIds(),
      main_source_id: plannerState.mainCollegeId,
      goals: plannerState.goals.map(({ target_id, major }) => ({ target_id, major })),
    });
    const savedSession = getAppState().sessions.find((item) => item.contextKey === contextKey);
    const session = savedSession || createSession("My transfer plan", contextKey);
    if (savedSession) selectSession(savedSession.id);
    document.querySelector("#results").innerHTML = `${renderPlan(plan)}<section class="card plan-chat" aria-label="Ask a question about your plan"><form class="plan-chat-form" id="chat-form"><label class="visually-hidden" for="message">Ask a question about your transfer plan</label><textarea id="message" rows="1" placeholder="Ask about courses, articulation, or policies in your plan…" required></textarea><button class="chat-submit" id="chat-submit" type="button" aria-label="Send question"><span aria-hidden="true">›</span></button></form><div class="chat-toolbar"><button class="chat-text-button" id="toggle-answers" type="button" aria-controls="answer-panel" aria-expanded="true" hidden>Show answers</button><button class="chat-text-button" id="clear-chat" type="button" disabled>Clear</button></div><section class="answer-panel" id="answer-panel" aria-label="Questions and answers" aria-live="polite" hidden><div class="messages" id="messages"></div></section></section>`;
    wirePlanChat(session, plan);
  } catch (error) {
    showPlannerError(error);
  } finally {
    button.disabled = false;
    button.textContent = "View plan";
  }
}

function completedChatHistory(messages) {
  const lastAssistant = messages.findLastIndex((message) => message.role === "assistant");
  return lastAssistant < 0 ? [] : messages.slice(0, lastAssistant + 1);
}

function setChatBusy(busy) {
  const input = document.querySelector("#message");
  const button = document.querySelector("#chat-submit");
  if (!input || !button) return;
  input.readOnly = busy;
  button.classList.toggle("is-stopping", busy);
  button.setAttribute("aria-label", busy ? "Stop answer" : "Send question");
  button.innerHTML = busy ? '<span aria-hidden="true">■</span>' : '<span aria-hidden="true">›</span>';
}

function updateChatToolbar(session) {
  const state = getAppState();
  const messages = state.sessions.find((item) => item.id === session.id)?.messages || [];
  const answerPanel = document.querySelector("#answer-panel");
  const toggle = document.querySelector("#toggle-answers");
  const clear = document.querySelector("#clear-chat");
  toggle.hidden = messages.length === 0;
  toggle.textContent = answerPanel.hidden ? `Show answers (${messages.filter((item) => item.role === "assistant").length})` : "Hide answers";
  toggle.setAttribute("aria-expanded", String(!answerPanel.hidden));
  clear.disabled = messages.length === 0 && !activeChatController;
}

function wirePlanChat(session, plan) {
  const form = document.querySelector("#chat-form");
  const input = document.querySelector("#message");
  const sendButton = document.querySelector("#chat-submit");
  const answerPanel = document.querySelector("#answer-panel");
  const messagesArea = document.querySelector("#messages");

  const savedMessages = getAppState().sessions.find((item) => item.id === session.id)?.messages || [];
  if (savedMessages.length) {
    answerPanel.hidden = false;
    messagesArea.innerHTML = renderMessages(savedMessages);
  }

  form.addEventListener("submit", (event) => chat(event, session, plan));
  sendButton.addEventListener("click", () => {
    if (activeChatController) activeChatController.abort();
    else form.requestSubmit();
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!activeChatController) form.requestSubmit();
    }
  });
  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 180)}px`;
  });
  document.querySelector("#toggle-answers").addEventListener("click", () => {
    answerPanel.hidden = !answerPanel.hidden;
    updateChatToolbar(session);
  });
  document.querySelector("#clear-chat").addEventListener("click", () => {
    activeChatController?.abort();
    clearSessionMessages(session.id);
    messagesArea.innerHTML = "";
    answerPanel.hidden = true;
    updateChatToolbar(session);
  });
  updateChatToolbar(session);
  input.focus();
}

async function chat(event, session, plan) {
  event.preventDefault();
  if (activeChatController) return;
  const input = document.querySelector("#message");
  const message = input.value.trim();
  if (!message) return;

  const savedMessages = getAppState().sessions.find((item) => item.id === session.id)?.messages || [];
  const history = completedChatHistory(savedMessages);
  appendMessage(session.id, { role: "user", content: message });
  input.value = "";
  input.style.height = "auto";
  const answerPanel = document.querySelector("#answer-panel");
  const messagesArea = document.querySelector("#messages");
  answerPanel.hidden = false;
  activeChatController = new AbortController();
  const controller = activeChatController;
  setChatBusy(true);
  messagesArea.innerHTML = `${renderMessages(getAppState().sessions.find((item) => item.id === session.id).messages)}<div class="message assistant answer-thinking">Pathway is preparing an answer…</div>`;
  updateChatToolbar(session);
  try {
    const reply = await sendChat({ plan_context: JSON.stringify(plan), history, message }, APP_CONFIG, { signal: controller.signal });
    appendMessage(session.id, { role: "assistant", content: reply.reply });
  } catch (error) {
    const currentMessages = getAppState().sessions.find((item) => item.id === session.id)?.messages || [];
    if (error.name === "AbortError") {
      if (currentMessages.at(-1)?.role === "user" && currentMessages.at(-1)?.content === message) {
        appendMessage(session.id, { role: "assistant", content: "Response stopped." });
      }
    } else {
      appendMessage(session.id, { role: "assistant", content: error.message });
    }
  } finally {
    if (activeChatController === controller) activeChatController = null;
    setChatBusy(false);
    messagesArea.innerHTML = renderMessages(getAppState().sessions.find((item) => item.id === session.id)?.messages || []);
    updateChatToolbar(session);
  }
}

async function renderPlanner() {
  pageTemplate(`<section class="planner-card card"><h2>1. Community colleges</h2><p>Add every California community college where you could take courses. Choosing a suggested college adds it automatically.</p><div class="search-add-row"><input id="college-search" list="college-options" placeholder="Type a college name" autocomplete="off" disabled></div><datalist id="college-options"></datalist><p class="field-message" id="college-message"></p><div class="selection-list" id="college-choices"></div><p class="main-college-note">The first college you add is your main college. When equally useful courses are available at several colleges, it is prioritized.</p></section><section class="planner-card card"><h2>2. University transfer goals</h2><p>Choose a suggested university, then search for a major to add that goal automatically.</p><div class="search-add-row"><input id="university-search" list="university-options" placeholder="Add a community college first" autocomplete="off" disabled></div><datalist id="university-options"></datalist><div class="field"><label for="major-search">Major</label><input id="major-search" list="major-options" placeholder="Choose a university first" autocomplete="off" disabled><datalist id="major-options"></datalist></div><div class="selection-list" id="goals"></div></section><section class="card plan-action"><h2>3. See your plan</h2><p>Pathway ranks verified courses that keep the most transfer options open, giving your main college priority when the options are tied.</p><button class="primary" id="generate" disabled>View plan</button></section><section id="results"></section>`);
  renderCollegeChoices();
  renderGoals();
  const collegeInput = document.querySelector("#college-search");
  const universityInput = document.querySelector("#university-search");
  collegeInput.addEventListener("input", () => {
    if (itemForName(plannerState.sourceCatalog, collegeInput.value)) addCollege();
  });
  collegeInput.addEventListener("change", () => {
    if (itemForName(plannerState.sourceCatalog, collegeInput.value)) addCollege();
  });
  collegeInput.addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); addCollege(); } });
  universityInput.addEventListener("change", refreshMajorChoices);
  universityInput.addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); refreshMajorChoices(); } });
  const majorInput = document.querySelector("#major-search");
  majorInput.addEventListener("input", () => {
    if (itemForName(plannerState.majorCatalog, majorInput.value)) addGoal();
  });
  majorInput.addEventListener("change", () => {
    if (itemForName(plannerState.majorCatalog, majorInput.value)) addGoal();
  });
  majorInput.addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); addGoal(); } });
  document.querySelector("#generate").addEventListener("click", loadPlan);
  try {
    plannerState.sourceCatalog = await getSources(APP_CONFIG);
    document.querySelector("#college-options").innerHTML = options(plannerState.sourceCatalog);
    collegeInput.disabled = false;
  } catch (error) {
    showPlannerError(error);
  }
}

if (!APP_CONFIG.useDemoData) {
  document.querySelector(".status").textContent = "● Live connection";
  renderPlanner();
}
