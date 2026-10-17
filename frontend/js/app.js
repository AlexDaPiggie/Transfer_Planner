import { mountCompletedCourses } from "./completed_courses.js";
import { APP_CONFIG } from "./config.js";
import { ACTIVE_YEAR_ID, generatePlan, getMajors, getSources, getTargets, sendChat } from "./api.js";
import { appendMessage, clearSessionMessages, createSession, getAppState, getSavedPlanner, getTheme, savePlanner, selectSession, setTheme } from "./state.js";
import { escapeHtml, renderCombinedCourseBoard, renderMessages, renderPlan } from "./ui.js";
import { renderServiceHome, renderCompass } from "./services.js";

const app = document.querySelector("#app");
const themeButton = document.querySelector("#theme-button");
let activeChatController = null;

const savedPlanner = getSavedPlanner();
const plannerState = {
  colleges: Array.isArray(savedPlanner.selection?.colleges) ? savedPlanner.selection.colleges : [],
  goals: Array.isArray(savedPlanner.selection?.goals) ? savedPlanner.selection.goals : [],
  mainCollegeId: Number.isInteger(savedPlanner.selection?.mainCollegeId) ? savedPlanner.selection.mainCollegeId : null,
  sourceCatalog: [],
  targetCatalog: [],
  majorCatalog: [],
  selectedTargetId: null,
  goalType: "primary",
  pendingMajor: null,
};

function persistPlanner(plan = null) {
  savePlanner({
    colleges: plannerState.colleges,
    goals: plannerState.goals,
    mainCollegeId: plannerState.mainCollegeId,
  }, plan);
}

function invalidateSavedPlan() {
  persistPlanner();
  const results = document.querySelector("#results");
  if (results) results.innerHTML = "";
}

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
  app.innerHTML = `<div class="hero"><h1>Let's make transfer easier</h1><p>Add the Community Colleges you can attend and universities you want to transfer, Pathway will help you to plan out all the courses you could take.</p></div>${content}`;
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
    area.innerHTML = `<p class="selection-hint">Add at least one college, then choose your main college below.</p>`;
    return;
  }
  area.innerHTML = plannerState.colleges.map((college) => `
    <div class="selection-chip ${college.id === plannerState.mainCollegeId ? "is-main" : ""}">
      <label><input type="radio" name="main-college" value="${college.id}" ${college.id === plannerState.mainCollegeId ? "checked" : ""}> Select as main</label>
      <span>${escapeHtml(college.name)}</span>
      ${college.id === plannerState.mainCollegeId ? `<span class="main-selected-label">Selected as main college</span>` : ""}
      <button class="chip-remove" type="button" data-remove-college="${college.id}" aria-label="Remove ${escapeHtml(college.name)}">×</button>
    </div>`).join("");

  area.querySelectorAll("input[name='main-college']").forEach((radio) => {
    radio.addEventListener("change", () => {
      plannerState.mainCollegeId = Number(radio.value);
      invalidateSavedPlan();
      renderCollegeChoices();
    });
  });
  area.querySelectorAll("[data-remove-college]").forEach((button) => {
    button.addEventListener("click", async () => {
      const collegeId = Number(button.dataset.removeCollege);
      plannerState.colleges = plannerState.colleges.filter((college) => college.id !== collegeId);
      if (plannerState.mainCollegeId === collegeId) plannerState.mainCollegeId = plannerState.colleges[0]?.id ?? null;
      plannerState.goals = [];
      invalidateSavedPlan();
      renderCollegeChoices();
      renderGoals();
      await refreshUniversityChoices();
      updatePlanButton();
    });
  });
}

function renderCollegeSuggestions() {
  const input = document.querySelector("#college-search");
  const list = document.querySelector("#college-suggestions");
  const query = input.value.trim().toLocaleLowerCase();
  const matches = plannerState.sourceCatalog.filter((college) => !query || college.name.toLocaleLowerCase().includes(query));
  list.innerHTML = matches.length ? matches.map((college) => {
    const alreadySelected = plannerState.colleges.some((item) => item.id === college.id);
    const style = college.name.toLocaleLowerCase().includes("west valley") ? "west-valley" : college.name.toLocaleLowerCase().includes("foothill") ? "foothill" : college.name.toLocaleLowerCase().includes("de anza") ? "de-anza" : "";
    return `<button type="button" class="college-suggestion ${style}" data-college-id="${college.id}" ${alreadySelected ? "aria-disabled=\"true\"" : ""}><span>${escapeHtml(college.name)}</span>${alreadySelected ? `<span class="already-selected">Already selected</span>` : ""}</button>`;
  }).join("") : `<p class="suggestion-empty">No matching colleges found.</p>`;
  list.hidden = false;
  list.querySelectorAll("[data-college-id]").forEach((button) => button.addEventListener("mousedown", (event) => event.preventDefault()));
  list.querySelectorAll("[data-college-id]").forEach((button) => button.addEventListener("click", () => {
    if (button.getAttribute("aria-disabled") === "true") return;
    addCollege(Number(button.dataset.collegeId));
    list.hidden = true;
  }));
}

function schoolColor(name) {
  const index = plannerState.targetCatalog.findIndex((school) => school.name === name);
  // A golden-angle hue step keeps neighboring entries visually distinct as the list grows.
  const hue = (index < 0 ? 0 : index) * 137.508 + 18;
  return `hsl(${hue % 360} 58% 34%)`;
}

function renderUniversitySuggestions() {
  const input = document.querySelector("#university-search");
  const list = document.querySelector("#university-suggestions");
  const query = input.value.trim().toLocaleLowerCase();
  const matches = plannerState.targetCatalog.filter((school) => !query || school.name.toLocaleLowerCase().includes(query));
  list.innerHTML = matches.length ? matches.map((school) => {
    const hasPrimary = plannerState.goals.some((goal) => goal.target_id === school.id && goal.goal_type === "primary");
    return `<button type="button" class="college-suggestion university-suggestion" style="--school-color:${schoolColor(school.name)}" data-university-id="${school.id}"><span>${escapeHtml(school.name)}</span>${hasPrimary ? `<span class="already-selected primary-selected-option">Primary major selected</span>` : ""}</button>`;
  }).join("") : `<p class="suggestion-empty">No matching universities found.</p>`;
  list.hidden = false;
  list.querySelectorAll("[data-university-id]").forEach((button) => button.addEventListener("mousedown", (event) => event.preventDefault()));
  list.querySelectorAll("[data-university-id]").forEach((button) => button.addEventListener("click", async () => {
    const school = plannerState.targetCatalog.find((item) => item.id === Number(button.dataset.universityId));
    if (!school) return;
    input.value = school.name;
    list.hidden = true;
    await refreshMajorChoices();
  }));
}

function renderGoals() {
  const area = document.querySelector("#goals");
  area.innerHTML = plannerState.goals.length
    ? [...new Set(plannerState.goals.map((goal) => goal.target_id))].map((targetId) => {
      const schoolGoals = plannerState.goals.map((goal, index) => ({ ...goal, index })).filter((goal) => goal.target_id === targetId);
      return `<div class="goal-school"><div class="goal-school-heading"><strong style="--school-color:${schoolColor(schoolGoals[0].target_name)}">${escapeHtml(schoolGoals[0].target_name)}</strong></div>${schoolGoals.map((goal) => `<div class="selection-chip goal-chip"><span>${escapeHtml(goal.major)}</span><span class="goal-type-badge ${goal.goal_type}">${goal.goal_type === "primary" ? "Primary major" : "Alternate major"}</span><button class="chip-remove" type="button" data-remove-goal="${goal.index}" aria-label="Remove ${escapeHtml(goal.major)}">×</button></div>`).join("")}</div>`;
    }).join("")
    : `<p class="selection-hint">Add one or more university and the major.</p>`;
  area.querySelectorAll("[data-remove-goal]").forEach((button) => {
    button.addEventListener("click", () => {
      plannerState.goals.splice(Number(button.dataset.removeGoal), 1);
      invalidateSavedPlan();
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
  plannerState.selectedTargetId = null;
  document.querySelector("#goal-type-picker").hidden = true;
  plannerState.pendingMajor = null;
  document.querySelector("#university-options").innerHTML = "";
  document.querySelector("#university-suggestions").innerHTML = "";
  document.querySelector("#university-suggestions").hidden = true;
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
    plannerState.selectedTargetId = null;
    document.querySelector("#goal-type-picker").hidden = true;
    plannerState.majorCatalog = [];
    document.querySelector("#major-options").innerHTML = "";
    major.value = "";
    major.disabled = true;
    major.placeholder = "Choose a university first";
    return;
  }
  plannerState.selectedTargetId = university.id;
  plannerState.goalType = plannerState.goals.some((goal) => goal.target_id === university.id) ? "alternate" : "primary";
  plannerState.pendingMajor = null;
  document.querySelector("#goal-type-picker").hidden = true;
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

function addCollege(selectedId = null) {
  const input = document.querySelector("#college-search");
  const college = selectedId === null ? itemForName(plannerState.sourceCatalog, input.value) : plannerState.sourceCatalog.find((item) => item.id === selectedId);
  if (!college) {
    document.querySelector("#college-message").textContent = "Choose a college from the suggested list.";
    return;
  }
  if (!plannerState.colleges.some((item) => item.id === college.id)) {
    plannerState.colleges.push(college);
    plannerState.mainCollegeId ??= college.id;
  }
  input.value = "";
  document.querySelector("#college-suggestions").hidden = true;
  document.querySelector("#college-message").textContent = "";
  plannerState.goals = [];
  invalidateSavedPlan();
  renderCollegeChoices();
  renderGoals();
  refreshUniversityChoices();
  updatePlanButton();
}

function addGoal() {
  const university = plannerState.targetCatalog.find((item) => item.id === plannerState.selectedTargetId);
  if (!university || !plannerState.pendingMajor || !plannerState.targetCatalog.some((item) => item.id === university.id)) return;
  const majorInput = document.querySelector("#major-search");
  const goal = { target_id: university.id, target_name: university.name, major: plannerState.pendingMajor.name, goal_type: plannerState.goalType };
  if (!plannerState.goals.some((item) => item.target_id === goal.target_id && item.major === goal.major)) plannerState.goals.push(goal);
  plannerState.pendingMajor = null;
  majorInput.value = "";
  // Keep the selected university's majors available for an alternate major.
  document.querySelector("#goal-type-picker").hidden = true;
  invalidateSavedPlan();
  renderGoals();
  updatePlanButton();
}

function showPlan(plan, session) {
  const results = document.querySelector("#results");
  results.innerHTML = `${renderPlan(plan)}<section class="card plan-chat" aria-label="Ask a question about your plan"><form class="plan-chat-form" id="chat-form"><label class="visually-hidden" for="message">Ask a question about your transfer plan</label><textarea id="message" rows="1" placeholder="Ask about courses, articulation, or policies in your plan…" required></textarea><button class="chat-submit" id="chat-submit" type="button" aria-label="Send question"><span aria-hidden="true">›</span></button></form><div class="chat-toolbar"><button class="chat-text-button" id="toggle-answers" type="button" aria-controls="answer-panel" aria-expanded="true" hidden>Show answers</button><button class="chat-text-button" id="clear-chat" type="button" disabled>Clear</button></div><section class="answer-panel" id="answer-panel" aria-label="Questions and answers" aria-live="polite" hidden><div class="messages" id="messages"></div></section></section>`;
  const activateChoice = (choiceSetId, choiceIndex) => {
    const choiceSet = results.querySelector(`[data-choice-set-id="${choiceSetId}"]`);
    if (!choiceSet) return;
    choiceSet.dataset.activeChoice = String(choiceIndex);
    choiceSet.querySelectorAll(".course-choice-card").forEach((card) => {
      const selected = Number(card.dataset.choiceIndex) === choiceIndex;
      card.classList.toggle("is-active-choice", selected);
      card.hidden = !selected;
    });
  };
  const refreshCombinedBoard = () => {
    const combinedBoard = results.querySelector("#combined-course-board");
    const board = plan.plan?.course_board;
    if (combinedBoard && board) combinedBoard.innerHTML = renderCombinedCourseBoard(board, true);
  };
  results.onclick = (event) => {
    const choiceSwitch = event.target.closest("[data-choice-switch]");
    if (choiceSwitch) {
      const count = Number(choiceSwitch.dataset.optionCount);
      const next = (Number(choiceSwitch.dataset.optionCurrent) + 1) % count;
      activateChoice(choiceSwitch.dataset.choiceSwitch, next);
      choiceSwitch.dataset.optionCurrent = String(next);
      choiceSwitch.innerHTML = `Option ${next + 1} of ${count} <span aria-hidden="true">›</span>`;
      refreshCombinedBoard();
      mountCompletedCourses(plan);
      return;
    }
    const button = event.target.closest("[data-option-switch]");
    if (!button) return;
    if (button.dataset.choiceSetId) activateChoice(button.dataset.choiceSetId, Number(button.dataset.choiceIndex));
    const optionCount = Number(button.dataset.optionCount);
    const nextOption = (Number(button.dataset.optionCurrent) + 1) % optionCount;
    const groupId = button.dataset.optionSwitch;
    results.querySelectorAll(`[data-option-group="${groupId}"]`).forEach((option) => {
      option.hidden = Number(option.dataset.optionIndex) !== nextOption;
    });
    const [, universityIndex, category, groupIndex] = groupId.match(/^option-(\d+)-(required|recommended)-(\d+)$/) || [];
    const group = plan.plan?.course_board?.universities?.[Number(universityIndex)]?.[category]?.[Number(groupIndex)];
    if (group) {
      group.selected_option = nextOption;
      persistPlanner(plan);
    }
    button.dataset.optionCurrent = String(nextOption);
    button.innerHTML = `Option ${nextOption + 1} of ${optionCount} <span aria-hidden="true">›</span>`;
    refreshCombinedBoard();
    mountCompletedCourses(plan);
  };
  wirePlanChat(session, plan);
  mountCompletedCourses(plan);
}

function prepareMajor() {
  const major = itemForName(plannerState.majorCatalog, document.querySelector("#major-search").value);
  if (!major || plannerState.selectedTargetId === null) {
    plannerState.pendingMajor = null;
    document.querySelector("#goal-type-picker").hidden = true;
    return;
  }
  plannerState.pendingMajor = major;
  plannerState.goalType = plannerState.goals.some((goal) => goal.target_id === plannerState.selectedTargetId) ? "alternate" : "primary";
  document.querySelector(`input[name="goal-type"][value="${plannerState.goalType}"]`).checked = true;
  document.querySelector("#goal-type-picker").hidden = false;
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
    persistPlanner({ data: plan, contextKey });
    showPlan(plan, session);
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
  pageTemplate(`<section class="planner-card card"><h2>1. Community colleges</h2><p>Add community colleges that you can attend.</p><div class="college-picker"><div class="search-add-row"><input id="college-search" placeholder="Type a college name" autocomplete="off" aria-controls="college-suggestions" aria-autocomplete="list" disabled></div><div id="college-suggestions" class="college-suggestions" role="listbox" hidden></div></div><p class="field-message" id="college-message"></p><div class="selection-list" id="college-choices"></div><p class="main-college-note">Courses will be prioritized to be taken at the main college.</p></section><section class="planner-card card"><h2>2. University transfer goals</h2><p>Choose a university, then choose a major and mark it as primary or alternate.</p><div class="college-picker"><div class="search-add-row"><input id="university-search" placeholder="Add a community college first" autocomplete="off" aria-controls="university-suggestions" aria-autocomplete="list" disabled></div><div id="university-suggestions" class="college-suggestions" role="listbox" hidden></div></div><datalist id="university-options"></datalist><div class="field"><label for="major-search">Major</label><input id="major-search" list="major-options" placeholder="Choose a university first" autocomplete="off" disabled><datalist id="major-options"></datalist></div><div id="goal-type-picker" class="goal-type-picker" hidden><span>This major is:</span><label><input type="radio" name="goal-type" value="primary" checked> Primary</label><label><input type="radio" name="goal-type" value="alternate"> Alternate</label><button class="primary add-major-button" type="button" id="add-major">Add major</button></div><div class="selection-list" id="goals"></div></section><section class="card plan-action"><h2>3. See your plan</h2><p>Click "View plan" and wait a few seconds for the courses table to be created.</p><button class="primary" id="generate" disabled>View plan</button></section><section id="results"></section>`);
  renderCollegeChoices();
  renderGoals();
  const collegeInput = document.querySelector("#college-search");
  const universityInput = document.querySelector("#university-search");
  collegeInput.addEventListener("focus", renderCollegeSuggestions);
  collegeInput.addEventListener("input", renderCollegeSuggestions);
  collegeInput.addEventListener("keydown", (event) => { if (event.key === "Enter") { const match = itemForName(plannerState.sourceCatalog, collegeInput.value); if (match) { event.preventDefault(); addCollege(match.id); } } if (event.key === "Escape") document.querySelector("#college-suggestions").hidden = true; });
  collegeInput.addEventListener("blur", () => setTimeout(() => { document.querySelector("#college-suggestions").hidden = true; }, 120));
  universityInput.addEventListener("focus", renderUniversitySuggestions);
  universityInput.addEventListener("input", renderUniversitySuggestions);
  universityInput.addEventListener("change", refreshMajorChoices);
  universityInput.addEventListener("keydown", (event) => { if (event.key === "Enter") { const school = itemForName(plannerState.targetCatalog, universityInput.value); if (school) { event.preventDefault(); refreshMajorChoices(); document.querySelector("#university-suggestions").hidden = true; } } if (event.key === "Escape") document.querySelector("#university-suggestions").hidden = true; });
  universityInput.addEventListener("blur", () => setTimeout(() => { document.querySelector("#university-suggestions").hidden = true; }, 120));
  document.querySelectorAll("input[name='goal-type']").forEach((radio) => radio.addEventListener("change", () => { plannerState.goalType = radio.value; }));
  const majorInput = document.querySelector("#major-search");
  majorInput.addEventListener("input", prepareMajor);
  majorInput.addEventListener("change", prepareMajor);
  majorInput.addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); prepareMajor(); } });
  document.querySelector("#add-major").addEventListener("click", addGoal);
  document.querySelector("#generate").addEventListener("click", loadPlan);
  try {
    plannerState.sourceCatalog = await getSources(APP_CONFIG);
    collegeInput.disabled = false;
    plannerState.colleges = plannerState.colleges
      .map((college) => plannerState.sourceCatalog.find((item) => item.id === college.id))
      .filter(Boolean);
    if (!plannerState.colleges.some((college) => college.id === plannerState.mainCollegeId)) {
      plannerState.mainCollegeId = plannerState.colleges[0]?.id ?? null;
    }
    renderCollegeChoices();
    renderGoals();
    updatePlanButton();
    if (plannerState.colleges.length) await refreshUniversityChoices();
    if (savedPlanner.plan?.data) {
      const savedSession = getAppState().sessions.find((item) => item.contextKey === savedPlanner.plan.contextKey);
      const session = savedSession || createSession("My transfer plan", savedPlanner.plan.contextKey);
      if (savedSession) selectSession(savedSession.id);
      showPlan(savedPlanner.plan.data, session);
    }
  } catch (error) {
    showPlannerError(error);
  }
}

const selectedService = new URLSearchParams(window.location.search).get("service");
if (selectedService === "compass") {
  renderCompass(app);
} else if (selectedService === "transfer") {
  renderPlanner();
} else {
  renderServiceHome(app);
}
