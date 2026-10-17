import test from "node:test";
import assert from "node:assert/strict";
import { renderCombinedCourseBoard, renderPlan } from "../js/ui.js";

test("saved alternative is restored in university and combined views", () => {
  const school = university('University A', 'required');
  school.required[0].options.push({courses:[{code:'MATH 1AH',title:'Honors Calculus',units:5}]});
  school.required[0].selected_option = 1;
  const plan = JSON.parse(JSON.stringify({plan:{course_board:{universities:[school],legend:[]}}}));
  const html = renderPlan(plan);
  assert.match(html, /data-option-current="1"/);
  assert.match(html, /Option 2 of 2/);
  assert.match(html, /data-option-index="0" hidden/);
  assert.match(html, /data-option-index="1" >/);
  const combined = renderCombinedCourseBoard(plan.plan.course_board);
  assert.match(combined, /data-course-code="MATH 1AH"/);
  assert.doesNotMatch(combined, /data-course-code="MATH 1A"/);
});

const group = (source_id = 113) => ({source_id, source_name:"De Anza College", is_main_college:true, options:[{courses:[{code:"MATH 1A",title:"Calculus",units:5}]}]});
const university = (name, category, source_id = 113) => ({university:name, major:"Computer Science", required:[], recommended:[], not_articulated:[], [category]:[group(source_id)]});

test("shared course appears once under Required and preserves each school's role", () => {
  for (const universities of [
    [university("University A", "required"), university("University B", "recommended")],
    [university("University B", "recommended"), university("University A", "required")],
  ]) {
    const html = renderCombinedCourseBoard({universities, legend:[]});
    assert.equal((html.match(/data-course-code="MATH 1A"/g) || []).length, 1);
    assert.match(html, /Required by<\/strong><ul>.*University A/);
    assert.match(html, /Recommended by<\/strong><ul>.*University B/);
    assert.ok(html.indexOf('data-course-code="MATH 1A"') < html.indexOf('class="course-column recommended"'));
  }
});

test("same course at different community colleges remains separate", () => {
  const html = renderCombinedCourseBoard({universities:[university("University A","required",113),university("University B","recommended",114)], legend:[]});
  assert.equal((html.match(/data-course-code="MATH 1A"/g) || []).length, 2);
});

test("a university's required role is not overwritten by its recommendation", () => {
  const school = university("University A", "required");
  school.recommended = [group()];
  const html = renderCombinedCourseBoard({universities:[school],legend:[]});
  assert.match(html,/Required by/);
  assert.doesNotMatch(html,/Recommended by<\/strong>/);
});
