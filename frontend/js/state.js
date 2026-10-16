const THEME_KEY = "pathway_theme";
const STATE_KEY = "pathway_state";

const emptyState = () => ({ activeSessionId: null, sessions: [], selection: null, plan: null });

export function getTheme(prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false) {
  const saved = localStorage.getItem(THEME_KEY);
  return saved === "light" || saved === "dark" ? saved : (prefersDark ? "dark" : "light");
}

export function setTheme(theme) {
  if (theme !== "light" && theme !== "dark") throw new Error("Theme must be light or dark.");
  localStorage.setItem(THEME_KEY, theme);
  if (typeof document !== "undefined") document.body.dataset.theme = theme;
}

export function getAppState() {
  try {
    const saved = JSON.parse(localStorage.getItem(STATE_KEY) || "null");
    return saved && Array.isArray(saved.sessions) ? saved : emptyState();
  } catch {
    return emptyState();
  }
}

export function saveAppState(state) { localStorage.setItem(STATE_KEY, JSON.stringify(state)); }

export function createSession(title = "New transfer plan", contextKey = null) {
  const state = getAppState();
  const session = { id: crypto.randomUUID?.() || String(Date.now()), title, contextKey, messages: [], createdAt: new Date().toISOString() };
  state.sessions.unshift(session);
  state.activeSessionId = session.id;
  saveAppState(state);
  return session;
}

export function appendMessage(sessionId, message) {
  if (!message?.role || !message?.content) throw new Error("A message needs a role and content.");
  const state = getAppState();
  const session = state.sessions.find((item) => item.id === sessionId);
  if (!session) throw new Error("Session not found.");
  session.messages.push({ role: message.role, content: message.content, createdAt: new Date().toISOString() });
  saveAppState(state);
}

export function clearSessionMessages(sessionId) {
  const state = getAppState();
  const session = state.sessions.find((item) => item.id === sessionId);
  if (!session) return;
  session.messages = [];
  saveAppState(state);
}

export function selectSession(sessionId) { const state = getAppState(); state.activeSessionId = sessionId; saveAppState(state); }
export function clearSessions() { const state = getAppState(); state.sessions = []; state.activeSessionId = null; saveAppState(state); }
