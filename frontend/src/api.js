const API_BASE = "http://localhost:8000/api";

export async function fetchInstitutions() {
  const res = await fetch(`${API_BASE}/institutions`);
  return res.json();
}

export async function generatePlan(yearId, sourceIds, targets) {
  const res = await fetch(`${API_BASE}/generate-plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ year_id: yearId, source_ids: sourceIds, targets }),
  });
  if (!res.ok) throw new Error("Failed to generate plan");
  return res.json();
}

export async function sendChatMessage(planContext, history, message) {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan_context: planContext, history, message }),
  });
  if (!res.ok) throw new Error("Chat request failed");
  return res.json();
}