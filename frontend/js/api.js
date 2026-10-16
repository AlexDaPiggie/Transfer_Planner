import { DEMO_PLAN, DEMO_REPLY } from "./demo-data.js";

export const ACTIVE_YEAR_ID = 77;

async function ensureOk(response) {
  if (response.ok) return response.json();
  let message = "The service could not complete that request.";
  try { message = (await response.json()).detail || message; } catch { /* Use the default message. */ }
  throw new Error(message);
}

async function request(url, options) {
  try { return await fetch(url, options); }
  catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error("The local backend is not running. Keep the PowerShell launcher open, then check frontend/.local-api-error.log.");
  }
}

export async function getSources(config) { return ensureOk(await request(`${config.apiBaseUrl}/api/catalog/sources?year_id=${ACTIVE_YEAR_ID}`)); }
export async function getTargets(sourceIds, config) { return ensureOk(await request(`${config.apiBaseUrl}/api/catalog/targets?year_id=${ACTIVE_YEAR_ID}&source_ids=${encodeURIComponent(sourceIds.join(","))}`)); }
export async function getMajors(sourceIds, targetId, config) { return ensureOk(await request(`${config.apiBaseUrl}/api/catalog/majors?year_id=${ACTIVE_YEAR_ID}&source_ids=${encodeURIComponent(sourceIds.join(","))}&target_id=${encodeURIComponent(targetId)}`)); }
export async function generatePlan(payload, config) {
  if (config.useDemoData) return structuredClone(DEMO_PLAN);
  const response = await request(`${config.apiBaseUrl}/api/generate-plan`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  return ensureOk(response);
}
export async function sendChat(payload, config, { signal } = {}) {
  if (config.useDemoData) return { reply: DEMO_REPLY, isDemo: true };
  const response = await request(`${config.apiBaseUrl}/api/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload), signal });
  return ensureOk(response);
}
