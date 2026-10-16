export function escapeHtml(value = "") { return String(value).replace(/[&<>'"]/g, (char) => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", "'":"&#39;", '"':"&quot;" })[char]); }

function renderSummaryInline(value = "") {
  return escapeHtml(value)
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

function renderSummary(value = "") {
  const lines = String(value).split(/\r?\n/);
  const blocks = [];
  let bullets = [];
  const flushBullets = () => {
    if (bullets.length) blocks.push(`<ul>${bullets.map((item) => `<li>${renderSummaryInline(item)}</li>`).join("")}</ul>`);
    bullets = [];
  };
  for (const rawLine of lines) {
    const line = rawLine.trim();
    const bullet = line.match(/^[*-]\s+(.+)/);
    if (bullet) {
      bullets.push(bullet[1]);
      continue;
    }
    flushBullets();
    if (line) blocks.push(`<p>${renderSummaryInline(line)}</p>`);
  }
  flushBullets();
  return blocks.join("");
}

function renderCourseCard(course) {
  const dots = (course.goals || []).map((goal) => `<span class="university-dot dot-${goal.dot_index % 8}" data-tooltip="${escapeHtml(goal.label)}" role="img" tabindex="0" aria-label="${escapeHtml(goal.label)}"></span>`).join("");
  const fallbackNotes = (course.fallback_notes || []).map((note) => `<p class="course-fallback-note">${escapeHtml(note)}</p>`).join("");
  const policyNotes = (course.policy_notes || []).map((note) => `<p class="course-policy-note">${escapeHtml(note)}</p>`).join("");
  return `<article class="course-board-card ${course.is_main_college ? "is-main" : "is-fallback"}"><div class="course-card-top"><div><h4>${escapeHtml(course.course_code)}</h4><p>${escapeHtml(course.course_name)}</p></div><div class="course-dots" aria-label="Supports ${course.supports_count} university goal${course.supports_count === 1 ? "" : "s"}">${dots}</div></div><div class="course-card-meta"><span>${escapeHtml(course.source_name)}${course.is_main_college ? " · Main college" : " · Fallback college"}</span>${course.units ? `<span>${escapeHtml(course.units)} units</span>` : ""}</div>${policyNotes}${fallbackNotes}</article>`;
}

function renderUnavailableCourseCard(course) {
  const dots = (course.goals || []).map((goal) => `<span class="university-dot dot-${goal.dot_index % 8}" data-tooltip="${escapeHtml(goal.label)}" role="img" tabindex="0" aria-label="${escapeHtml(goal.label)}"></span>`).join("");
  return `<article class="unavailable-course-card"><div class="course-card-top"><div><h4>${escapeHtml(course.course_code)}</h4><p>${escapeHtml(course.course_name)}</p></div><div class="course-dots" aria-label="Required by ${course.supports_count} university goal${course.supports_count === 1 ? "" : "s"}">${dots}</div></div><p class="unavailable-course-reason">${escapeHtml(course.reason)}</p></article>`;
}

function renderCourseColumn(title, description, courses, kind, renderCard = renderCourseCard, emptyMessage = "No courses in this group were found in the saved Assist agreement.") {
  const content = courses.length ? courses.map(renderCard).join("") : `<p class="empty-course-column">${escapeHtml(emptyMessage)}</p>`;
  return `<section class="course-column ${kind}"><div class="course-column-heading"><h3>${title}</h3><p>${description}</p></div><div class="course-card-list">${content}</div></section>`;
}

function renderCourseBoard(board) {
  const goalChips = (board.legend || []).map((goal) => `<span class="selected-goal-chip dot-chip-${goal.dot_index % 8}"><span class="university-dot dot-${goal.dot_index % 8}"></span>${escapeHtml(goal.label)}</span>`).join("");
  const footnotes = (board.footnotes || []).map((note) => `<li>${escapeHtml(note)}</li>`).join("");
  return `<section class="transfer-board"><div class="transfer-board-goals"><h2>University goals</h2><div class="selected-goal-chips">${goalChips}</div></div><div class="course-board-layout"><div class="course-board-columns">${renderCourseColumn("Recommended", "Courses Assist strongly recommends, but no selected university requires.", board.recommended || [], "recommended")}${renderCourseColumn("Required", "Major preparation courses required for transfer.", board.required || [], "required")}${renderCourseColumn("Not articulated", "University requirements without an articulated option at any selected community college.", board.not_articulated || [], "not-articulated", renderUnavailableCourseCard, "Every listed university requirement has an articulated option at a selected college.")}</div>${footnotes ? `<article class="course-board-footnotes"><h3>Important course-placement notes</h3><ul>${footnotes}</ul></article>` : ""}</div></section>`;
}

export function renderPlan(plan) {
  if (plan.plan) {
    const board = plan.plan.course_board || { required: [], recommended: [], not_articulated: [], legend: [], footnotes: [] };
    return `<div class="notice">This plan uses saved Assist agreement data. Dots show which university goals each course supports. Verify every agreement before enrolling.</div>${renderCourseBoard(board)}`;
  }
  const rows = plan.matrix.map((row) => `<tr><td><strong>${escapeHtml(row.course_code)}</strong><br><small>${escapeHtml(row.course_name)}</small></td><td>${escapeHtml(row.targets.join(", "))}</td><td><a href="${escapeHtml(row.official_url)}" target="_blank" rel="noreferrer">Verify ↗</a></td></tr>`).join("");
  return `<div class="notice">${plan.isDemo ? "Demo data is shown. Connect FastAPI later to see your live plan." : "Verified plan data"}</div><div class="grid"><article class="card"><h2>Student summary</h2><div>${renderSummary(plan.summary)}</div></article><article class="card"><h2>Series and policy notes</h2><ul>${plan.series_rules.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></article></div><article class="card" style="margin-top:14px"><h2>Course overlap</h2><table class="matrix"><thead><tr><th>Community college course</th><th>Supports</th><th>Source</th></tr></thead><tbody>${rows}</tbody></table></article>`;
}
export function renderMessages(messages) { return messages.map((message) => `<article class="message ${escapeHtml(message.role)}"><span class="message-author">${message.role === "user" ? "You" : "Pathway · Model 2"}</span><div class="message-content">${escapeHtml(message.content).replaceAll("\n", "<br>")}</div></article>`).join(""); }
