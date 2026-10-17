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
  return `<article class="course-board-card ${course.is_main_college ? "is-main" : "is-fallback"}" data-source-id="${escapeHtml(course.source_id)}" data-course-code="${escapeHtml(course.course_code)}"><div class="course-card-top"><div><h4>${escapeHtml(course.course_code)}</h4><p>${escapeHtml(course.course_name)}</p></div><div class="course-dots" aria-label="Supports ${course.supports_count} university goal${course.supports_count === 1 ? "" : "s"}">${dots}</div></div><div class="course-card-meta"><span>${escapeHtml(course.source_name)}${course.is_main_college ? " · Main college" : " · Fallback college"}</span>${course.units ? `<span>${escapeHtml(course.units)} units</span>` : ""}</div>${policyNotes}${fallbackNotes}</article>`;
}

function renderUnavailableCourseCard(course) {
  const dots = (course.goals || []).map((goal) => `<span class="university-dot dot-${goal.dot_index % 8}" data-tooltip="${escapeHtml(goal.label)}" role="img" tabindex="0" aria-label="${escapeHtml(goal.label)}"></span>`).join("");
  return `<article class="unavailable-course-card"><div class="course-card-top"><div><h4>${escapeHtml(course.course_code)}</h4><p>${escapeHtml(course.course_name)}</p></div><div class="course-dots" aria-label="Required by ${course.supports_count} university goal${course.supports_count === 1 ? "" : "s"}">${dots}</div></div><p class="unavailable-course-reason">${escapeHtml(course.reason)}</p></article>`;
}

function renderCourseColumn(title, description, courses, kind, renderCard = renderCourseCard, emptyMessage = "No courses in this group were found in the saved Assist agreement.") {
  const content = courses.length ? courses.map(renderCard).join("") : `<p class="empty-course-column">${escapeHtml(emptyMessage)}</p>`;
  return `<section class="course-column ${kind}"><div class="course-column-heading"><h3>${title}</h3><p>${description}</p></div><div class="course-card-list">${content}</div></section>`;
}

function renderOptionCourse(course) {
  return `<div class="equivalency-course"><div><strong>${escapeHtml(course.code)}</strong>${course.title ? `<span>${escapeHtml(course.title)}</span>` : ""}</div><div class="equivalency-course-meta"><span>${escapeHtml(course.source_name || "")}</span>${course.units ? `<span>${escapeHtml(course.units)} units</span>` : ""}</div></div>`;
}

function renderEquivalencyGroup(group, universityIndex, category, groupIndex) {
  const optionGroupId = `option-${universityIndex}-${category}-${groupIndex}`;
  const options = group.options || [];
  const optionsMarkup = options.map((option, optionIndex) => `<div class="equivalency-option" data-option-group="${optionGroupId}" data-option-index="${optionIndex}" ${optionIndex ? "hidden" : ""}>${option.courses.map((course, courseIndex) => `${courseIndex ? `<span class="equivalency-conjunction">${option.conjunction === "or" ? "or" : "and"}</span>` : ""}${renderOptionCourse({ ...course, source_name: group.source_name })}`).join("")}</div>`).join("");
  const switcher = options.length > 1
    ? `<button class="option-switch" type="button" data-option-switch="${optionGroupId}" data-option-count="${options.length}" data-option-current="0" aria-label="Show next articulated course group">${escapeHtml(options[0].label || `Option 1 of ${options.length}`)} <span aria-hidden="true">›</span></button>`
    : "";
  const tooltip = `${group.target_course}${group.target_title && group.target_title !== group.target_course ? ` — ${group.target_title}` : ""}`;
  return `<article class="equivalency-group" tabindex="0" data-tooltip="${escapeHtml(tooltip)}" aria-label="Community college courses that satisfy ${escapeHtml(tooltip)}"><div class="equivalency-group-heading"><span class="equivalency-group-college">${escapeHtml(group.source_name)}${group.is_main_college ? " · Main college" : " · Fallback college"}</span>${switcher}</div>${optionsMarkup}${group.policy_note ? `<p class="course-policy-note">${escapeHtml(group.policy_note)}</p>` : ""}${group.fallback_note ? `<p class="course-fallback-note">${escapeHtml(group.fallback_note)}</p>` : ""}</article>`;
}

function renderNotArticulatedGroup(group) {
  const tooltip = `${group.target_course}${group.target_title && group.target_title !== group.target_course ? ` — ${group.target_title}` : ""}`;
  return `<article class="equivalency-group not-articulated-group" tabindex="0" data-tooltip="${escapeHtml(tooltip)}" aria-label="No selected college articulation for ${escapeHtml(tooltip)}"><div class="equivalency-group-heading"><strong>${escapeHtml(group.target_course)}</strong></div><p class="unavailable-course-reason">${escapeHtml(group.reason)}</p></article>`;
}

function renderUniversityPlan(university, universityIndex) {
  const link = university.assist_url ? `<a class="university-assist-link" href="${escapeHtml(university.assist_url)}" target="_blank" rel="noreferrer">Open Assist ↗</a>` : "";
  const categoryColumn = (title, key, description) => {
    const groups = university[key] || [];
    const content = groups.length
      ? groups.map((group, index) => key === "not_articulated" ? renderNotArticulatedGroup(group) : renderEquivalencyGroup(group, universityIndex, key, index)).join("")
      : `<p class="empty-course-column">${key === "not_articulated" ? "All listed university courses have an articulation at a selected college." : "No courses in this category were found in the saved Assist agreement."}</p>`;
    return `<section class="course-column ${key}"><div class="course-column-heading"><h3>${title}</h3><p>${description}</p></div><div class="course-card-list">${content}</div></section>`;
  };
  return `<section class="university-course-plan"><header class="university-course-plan-heading"><div><h2>${escapeHtml(university.university)}</h2><p>${escapeHtml(university.major)}</p></div>${link}</header><div class="course-board-columns">${categoryColumn("Recommended", "recommended", "Assist strongly recommends these courses.")}${categoryColumn("Required", "required", "Assist lists these courses as required for the major.")}${categoryColumn("Not articulated", "not_articulated", "No selected college has an articulated course for these requirements.")}</div></section>`;
}

function renderCourseBoard(board) {
  const goalChips = (board.legend || []).map((goal) => `<span class="selected-goal-chip dot-chip-${goal.dot_index % 8}"><span class="university-dot dot-${goal.dot_index % 8}"></span>${escapeHtml(goal.label)}</span>`).join("");
  const footnotes = (board.footnotes || []).map((note) => `<li>${escapeHtml(note)}</li>`).join("");
  return `<section class="transfer-board"><div class="transfer-board-goals"><h2>University goals</h2><div class="selected-goal-chips">${goalChips}</div></div><div class="course-board-layout"><div class="course-board-columns">${renderCourseColumn("Recommended", "Courses Assist strongly recommends, but no selected university requires.", board.recommended || [], "recommended")}${renderCourseColumn("Required", "Major preparation courses required for transfer.", board.required || [], "required")}${renderCourseColumn("Not articulated", "University requirements without an articulated option at any selected community college.", board.not_articulated || [], "not-articulated", renderUnavailableCourseCard, "Every listed university requirement has an articulated option at a selected college.")}</div>${footnotes ? `<article class="course-board-footnotes"><h3>Important course-placement notes</h3><ul>${footnotes}</ul></article>` : ""}</div></section>`;
}

function combinedBoardFromUniversityPlans(board, readDisplayedOptions = false) {
  const cardsByStage = new Map();
  const unavailableByCourse = new Map();
  const goalIndexByLabel = new Map((board.legend || []).map((goal, index) => [goal.label, goal.dot_index ?? index]));
  (board.universities || []).forEach((university, universityIndex) => {
    const goalLabel = `${university.university} — ${university.major}`;
    const dotIndex = goalIndexByLabel.get(goalLabel) ?? universityIndex;
    for (const category of ["required", "recommended"]) {
      for (const [groupIndex, group] of (university[category] || []).entries()) {
        const options = group.options || [];
        const switcher = readDisplayedOptions
          ? document.querySelector(`[data-option-switch="option-${universityIndex}-${category}-${groupIndex}"]`)
          : null;
        const optionIndex = Math.min(Number(switcher?.dataset.optionCurrent || 0), Math.max(0, options.length - 1));
        const option = options[optionIndex];
        if (!option) continue;
        for (const course of option.courses || []) {
          const match = course.code.match(/^(.*?\s+\d+)([A-Z]+?)(H)?$/i);
          const family = match ? match[1].toUpperCase() : course.code.toUpperCase();
          const stage = match ? match[2].toUpperCase() : "";
          const variant = match?.[3] ? "honors" : "regular";
          const key = `${group.source_id}:${family}:${stage}`;
          const card = cardsByStage.get(key) || {
            source_id: group.source_id,
            source_name: group.source_name,
            is_main_college: group.is_main_college,
            variants: {},
            goals: new Map(),
            fallback_notes: new Set(),
            policy_notes: new Set(),
            assist_urls: new Set(),
            category,
          };
          card.variants[variant] ||= course;
          card.goals.set(goalLabel, { label: goalLabel, dot_index: dotIndex });
          if (category === "required") card.category = "required";
          if (group.fallback_note) card.fallback_notes.add(group.fallback_note);
          if (group.policy_note) card.policy_notes.add(group.policy_note);
          if (group.assist_url) card.assist_urls.add(group.assist_url);
          cardsByStage.set(key, card);
        }
      }
    }
    for (const group of university.not_articulated || []) {
      const key = group.target_course;
      const unavailable = unavailableByCourse.get(key) || {
        course_code: group.target_course,
        course_name: group.target_title || group.target_course,
        reason: group.reason,
        goals: new Map(),
      };
      unavailable.goals.set(goalLabel, { label: goalLabel, dot_index: dotIndex });
      unavailableByCourse.set(key, unavailable);
    }
  });

  const required = [];
  const recommended = [];
  for (const card of cardsByStage.values()) {
    const variants = ["regular", "honors"].filter((key) => card.variants[key]).map((key) => card.variants[key]);
    card.course_code = variants.map((course) => course.code).join(" or ");
    card.course_name = variants[0]?.title || card.course_code;
    card.units = Math.max(0, ...variants.map((course) => Number(course.units || 0)));
    card.goals = [...card.goals.values()];
    card.supports_count = card.goals.length;
    card.fallback_notes = [...card.fallback_notes];
    card.policy_notes = [...card.policy_notes];
    card.assist_urls = [...card.assist_urls];
    (card.category === "required" ? required : recommended).push(card);
  }
  const sortCourses = (a, b) => b.supports_count - a.supports_count || Number(b.is_main_college) - Number(a.is_main_college) || a.course_code.localeCompare(b.course_code);
  required.sort(sortCourses);
  recommended.sort(sortCourses);
  const not_articulated = [...unavailableByCourse.values()].map((course) => {
    course.goals = [...course.goals.values()];
    course.supports_count = course.goals.length;
    return course;
  }).sort(sortCourses);
  const legend = (board.legend || []).map((goal, index) => ({ ...goal, dot_index: goal.dot_index ?? index }));
  return { ...board, required, recommended, not_articulated, legend };
}

export function renderCombinedCourseBoard(board, readDisplayedOptions = false) {
  return renderCourseBoard(combinedBoardFromUniversityPlans(board, readDisplayedOptions));
}

export function renderPlan(plan) {
  if (plan.plan) {
    const board = plan.plan.course_board || { required: [], recommended: [], not_articulated: [], legend: [], footnotes: [] };
    if (board.universities?.length) {
      return `<div class="notice">Review the required, recommended, and unavailable courses for each selected university. Each bordered group satisfies the university course shown when focused or hovered.</div><div class="university-course-plans">${board.universities.map(renderUniversityPlan).join("")}</div><div id="combined-course-board">${renderCombinedCourseBoard(board)}</div>`;
    }
    return `<div class="notice">This plan uses saved Assist agreement data. Dots show which university goals each course supports. Verify every agreement before enrolling.</div>${renderCourseBoard(board)}`;
  }
  const rows = plan.matrix.map((row) => `<tr><td><strong>${escapeHtml(row.course_code)}</strong><br><small>${escapeHtml(row.course_name)}</small></td><td>${escapeHtml(row.targets.join(", "))}</td><td><a href="${escapeHtml(row.official_url)}" target="_blank" rel="noreferrer">Verify ↗</a></td></tr>`).join("");
  return `<div class="notice">${plan.isDemo ? "Demo data is shown. Connect FastAPI later to see your live plan." : "Verified plan data"}</div><div class="grid"><article class="card"><h2>Student summary</h2><div>${renderSummary(plan.summary)}</div></article><article class="card"><h2>Series and policy notes</h2><ul>${plan.series_rules.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></article></div><article class="card" style="margin-top:14px"><h2>Course overlap</h2><table class="matrix"><thead><tr><th>Community college course</th><th>Supports</th><th>Source</th></tr></thead><tbody>${rows}</tbody></table></article>`;
}
export function renderMessages(messages) { return messages.map((message) => `<article class="message ${escapeHtml(message.role)}"><span class="message-author">${message.role === "user" ? "You" : "Pathway · Model 2"}</span><div class="message-content">${escapeHtml(message.content).replaceAll("\n", "<br>")}</div></article>`).join(""); }
