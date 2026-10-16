export const DEMO_PLAN = Object.freeze({
  isDemo: true,
  total_targets: 2,
  matrix: [
    { course_code: "MATH 1A", course_name: "Calculus I", targets: ["UC Davis", "San José State"], overlap_count: 2, official_url: "https://assist.org" },
    { course_code: "PHYS 4A", course_name: "Mechanics", targets: ["UC Davis"], overlap_count: 1, official_url: "https://assist.org" },
  ],
  series_rules: ["Verify full course sequences before changing colleges."],
  summary: "## Your transfer plan\n\n- **Shared priority:** MATH 1A supports both selected destinations.\n- **Check carefully:** PHYS 4A is currently shown only for UC Davis.\n- This is sample data. Confirm every requirement on Assist.org.",
  technical_plan: { status: "demo", evidence_note: "This demo never represents official advice." },
});

export const DEMO_REPLY = "This is a demo reply. Once FastAPI is connected, this answer will be generated only from your verified transfer-plan data and its official Assist.org links.";
