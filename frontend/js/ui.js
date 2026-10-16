export function escapeHtml(value = "") { return String(value).replace(/[&<>'"]/g, (char) => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", "'":"&#39;", '"':"&quot;" })[char]); }

function renderCollegeGoalStatus(status) {
  if (status.status === "not_in_database") {
    return `<article class="college-goal-status"><h4>${escapeHtml(status.college)}</h4><p>Agreement data is not available yet.</p></article>`;
  }
  if (status.status === "no_courses") {
    return `<article class="college-goal-status"><h4>${escapeHtml(status.college)}</h4><p class="coverage-warning">No course articulated.</p>${renderPolicyNotes(status)}</article>`;
  }

  const courses = (status.courses || []).map((course) => `<li><strong>${escapeHtml(course.course_code)}</strong>${course.course_name ? ` — ${escapeHtml(course.course_name)}` : ""}<span class="course-equivalency"> → ${escapeHtml(course.target_course)}</span>${course.is_series ? " <small>(part of a course group)</small>" : ""}</li>`).join("");
  return `<article class="college-goal-status"><h4>${escapeHtml(status.college)} <span class="coverage-ok">${status.course_count} articulated course${status.course_count === 1 ? "" : "s"}</span></h4><details class="articulation-details"><summary>View articulated courses</summary><ul class="articulated-courses">${courses}</ul></details>${renderPolicyNotes(status)}</article>`;
}

function renderPolicyNotes(status) {
  const notes = [...(status.series_rules || []), ...(status.policy_notes || [])]
    .filter((note, index, all) => !(status.status === "no_courses" && note.toLowerCase().includes("no course articulated")) && all.indexOf(note) === index);
  if (!notes.length) return `<p class="no-policy-notes">No additional policy notes were found in the saved agreement.</p>`;
  return `<div class="policy-notes"><strong>Important notes from Assist</strong><ul>${notes.map((note) => `<li>${escapeHtml(note)}</li>`).join("")}</ul></div>`;
}

function renderUniversityPlan(target) {
  const link = target.assist_url ? `<a href="${escapeHtml(target.assist_url)}" target="_blank" rel="noreferrer">Open Assist agreement ↗</a>` : `<span class="muted">No saved agreement link is available yet.</span>`;
  const colleges = (target.college_statuses || []).map(renderCollegeGoalStatus).join("");
  return `<article class="card university-plan"><div class="university-plan-heading"><div><p class="eyebrow">University transfer plan</p><h3>${escapeHtml(target.university)}</h3><p class="goal-major">${escapeHtml(target.major)}</p></div>${link}</div><div class="university-college-statuses">${colleges}</div></article>`;
}

function renderCombinedRoute(recommendedCourses) {
  const byCollege = new Map();
  for (const course of recommendedCourses) {
    if (!byCollege.has(course.source_name)) byCollege.set(course.source_name, []);
    byCollege.get(course.source_name).push(course);
  }

  if (!byCollege.size) return `<p class="notice">No articulated courses are available to combine for the selected goals.</p>`;
  return [...byCollege.entries()].map(([college, courses]) => {
    const isMain = courses.some((course) => course.is_main_college);
    const rows = courses.map((course) => {
      const goalNames = (course.supported_goals || []).map((goal) => `<li>${escapeHtml(goal)}</li>`).join("");
      return `<tr><td><strong>${escapeHtml(course.course_code)}</strong><br><small>${escapeHtml(course.course_name)}</small></td><td>${course.supports_count} goal${course.supports_count === 1 ? "" : "s"}<ul class="supported-goals">${goalNames}</ul></td></tr>`;
    }).join("");
    return `<article class="card route-college"><h3>${escapeHtml(college)}${isMain ? ` <span class="main-college-badge">Main college</span>` : ""}</h3><div class="table-wrap"><table class="matrix"><thead><tr><th>Course to consider</th><th>University goals it supports</th></tr></thead><tbody>${rows}</tbody></table></div></article>`;
  }).join("");
}

export function renderPlan(plan) {
  if (plan.plan) {
    const universityPlans = plan.plan.targets.map(renderUniversityPlan).join("");
    const combinedRoute = renderCombinedRoute(plan.plan.recommended_courses);
    return `<div class="notice">Use the university-specific sections first to review each agreement. The combined route then highlights courses that may support multiple goals. Verify policies and course details on Assist before enrolling.</div><section class="output-section"><div class="section-heading"><p class="eyebrow">Step 1</p><h2>Plans by university</h2><p>Review the articulation, course options, and notes for each university and major.</p></div><div class="university-plans">${universityPlans}</div></section><section class="output-section combined-output"><div class="section-heading"><p class="eyebrow">Step 2</p><h2>Combined transfer route</h2><p>${plan.plan.coverage.selected_targets} university goal${plan.plan.coverage.selected_targets === 1 ? "" : "s"}. Courses are grouped by community college; shared courses can support more than one goal.</p></div><div class="route-colleges">${combinedRoute}</div><article class="card plain-language"><h3>How to use this route</h3><div>${escapeHtml(plan.summary).replaceAll("\n", "<br>")}</div></article></section>`;
  }
  const rows = plan.matrix.map((row) => `<tr><td><strong>${escapeHtml(row.course_code)}</strong><br><small>${escapeHtml(row.course_name)}</small></td><td>${escapeHtml(row.targets.join(", "))}</td><td><a href="${escapeHtml(row.official_url)}" target="_blank" rel="noreferrer">Verify ↗</a></td></tr>`).join("");
  return `<div class="notice">${plan.isDemo ? "Demo data is shown. Connect FastAPI later to see your live plan." : "Verified plan data"}</div><div class="grid"><article class="card"><h2>Student summary</h2><div>${escapeHtml(plan.summary).replaceAll("\n", "<br>")}</div></article><article class="card"><h2>Series and policy notes</h2><ul>${plan.series_rules.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></article></div><article class="card" style="margin-top:14px"><h2>Course overlap</h2><table class="matrix"><thead><tr><th>Community college course</th><th>Supports</th><th>Source</th></tr></thead><tbody>${rows}</tbody></table></article>`;
}
export function renderMessages(messages) { return messages.map((message) => `<article class="message ${escapeHtml(message.role)}"><span class="message-author">${message.role === "user" ? "You" : "Pathway · Model 2"}</span><div class="message-content">${escapeHtml(message.content).replaceAll("\n", "<br>")}</div></article>`).join(""); }
