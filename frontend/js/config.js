// Local preview uses port 8000; deployed sites use the same origin for APIs.
const localHost = ["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname);
export const API_BASE = localHost && window.location.port !== "8000"
  ? `${window.location.protocol}//${window.location.hostname}:8000`
  : window.location.origin;

export const APP_CONFIG = Object.freeze({
  appName: "Pathway",
  useDemoData: false,
  // Match the IPv4 address FastAPI binds to in run_local.ps1.
  apiBaseUrl: API_BASE,
  maxSavedSessions: 8,
});
