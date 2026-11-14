"""Browser verification with isolated mock accounts; never contacts real APIs."""
import argparse
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main(services_only=False):
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT / "frontend")))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    output = ROOT / "scratch" / "integration-preview"
    output.mkdir(parents=True, exist_ok=True)
    state = {"user": None, "completed": [], "completion_writes": 0}
    errors = []

    def respond(route):
        req = route.request
        path = urlsplit(req.url).path
        body = req.post_data_json if req.post_data else {}
        code = 200
        if req.method == "OPTIONS":
            data = {}
        elif path == "/api/auth/config":
            data = {"google_client_id": ""}
        elif path == "/api/auth/me":
            data = {"logged_in": bool(state["user"]), "user": state["user"]}
        elif path in ("/api/auth/login", "/api/auth/signup"):
            state["user"] = {"user_id": 1, "email": body["email"]}
            data = {"logged_in": True, "user": state["user"]}
        elif path == "/api/auth/logout":
            state["user"] = None
            data = {"logged_in": False}
        elif path == "/api/completed-courses":
            if req.method == "POST":
                state["completed"] = [body]
                state["completion_writes"] += 1
            elif req.method == "DELETE":
                state["completed"] = []
                state["completion_writes"] += 1
            data = {"courses": state["completed"]}
        elif path == "/api/catalog/sources":
            data = [{"id": 113, "name": "De Anza College"}]
        else:
            raise AssertionError(f"Unexpected API request: {req.method} {path}")
        route.fulfill(status=code, json=data, headers={"Access-Control-Allow-Origin": req.headers.get("origin", "*"), "Access-Control-Allow-Credentials": "true", "Access-Control-Allow-Headers": "content-type,x-pathway-request", "Access-Control-Allow-Methods": "GET,POST,PUT,OPTIONS"})

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="msedge", headless=True)
            context = browser.new_context(viewport={"width": 1365, "height": 950})
            context.route("**/api/**", respond)
            # Keep browser verification offline.
            context.route("https://**/*", lambda route: route.abort())
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            base = f"http://127.0.0.1:{server.server_port}"
            page.goto(base)
            expect(page.locator(".service-card")).to_have_count(2)
            expect(page.get_by_role("link", name="De Anza Events", exact=True)).to_have_count(0)
            page.screenshot(path=str(output / "home.png"), full_page=True)
            page.goto(base + "/?service=compass")
            expect(page.locator("body")).to_have_class("home-view")
            expect(page.locator(".service-card")).to_have_count(2)
            page.get_by_role("button", name="Log in / Sign up", exact=True).click()
            page.locator("#auth-email").fill("browser-test@example.invalid")
            page.locator("#auth-password").fill("local-test-password")
            page.locator("#auth-submit").click()
            expect(page.get_by_role("button", name="Log out", exact=True)).to_be_visible()
            page.get_by_role("button", name="Log out", exact=True).click()
            page.get_by_role("link", name="De Anza Chatbot", exact=True).click()
            expect(page.locator(".chatbot-frame")).to_be_visible()
            chat = page.frame_locator(".chatbot-frame")
            expect(chat.locator('a[href*="service=compass"]')).to_have_count(0)
            expect(chat.locator("#input-box")).to_be_visible()
            page.goto(base)
            page.set_viewport_size({"width": 390, "height": 844})
            expect(page.locator(".service-card")).to_have_count(2)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(output / "home-mobile.png"), full_page=True)
            page.get_by_role("button", name="Log in / Sign up", exact=True).click()
            expect(page.get_by_role("button", name="Forgot password?")).to_have_count(0)
            page.locator("#auth-toggle").click()
            expect(page.locator("#auth-submit")).to_have_text("Create account")
            page.locator("#auth-close").click()
            page.goto(base + "/?service=transfer")
            expect(page.locator("#college-search")).to_be_enabled()
            if services_only:
                assert not errors, errors
                browser.close()
                print(json.dumps({"browser": "passed", "checks": ["two services", "retired service fallback", "login and logout", "chatbot navigation", "mobile width", "login and signup without email recovery", "planner loads"]}))
                return
            expect(page.get_by_role("heading", name="1. Community colleges")).to_be_visible()
            expect(page.locator("#college-search")).to_be_enabled()
            page.set_viewport_size({"width": 1365, "height": 950})
            await_layout = page.evaluate("""async () => {
                const { renderPlan } = await import('/js/ui.js');
                const { mountCompletedCourses } = await import('/js/completed_courses.js');
                const course = i => ({source_id:113, course_code:`MATH ${i}`, course_name:'Example course', source_name:'De Anza College', is_main_college:true, supports_count:1, goals:[{label:'University A / Computer Science', dot_index:0, category:i<=6?'required':'recommended'},{label:'University B / Computer Science',dot_index:1,category:'recommended'}], units:5});
                const plan = {plan:{course_board:{required:[1,2,3,4,5,6].map(course), recommended:[7,8,9,10].map(course), not_articulated:[{course_code:'BIO 200',course_name:'Example requirement',reason:'No articulation at the selected colleges.',goals:[],supports_count:1}],legend:[{label:'University goal',dot_index:0}],footnotes:[]}}};
                document.querySelector('#results').innerHTML = renderPlan(plan);
                mountCompletedCourses(plan);
            }""")
            sections = page.locator("#results .course-board-columns > .course-column")
            assert sections.nth(0).get_attribute("class").endswith("required")
            assert sections.nth(1).get_attribute("class").endswith("recommended")
            assert sections.nth(2).get_attribute("class").endswith("not-articulated")
            required = page.locator("#results .course-column.required")
            recommended = page.locator("#results .course-column.recommended")
            assert required.bounding_box()["y"] < recommended.bounding_box()["y"]
            cards = required.locator(".course-board-card")
            expect(cards.first.locator(".course-goal-role > strong")).to_have_text(["Required by", "Recommended by"])
            assert len({round(cards.nth(i).bounding_box()["y"]) for i in range(3)}) == 1
            assert cards.nth(3).bounding_box()["y"] > cards.nth(0).bounding_box()["y"]
            page.locator("#results").screenshot(path=str(output / "planner-course-layout.png"))
            page.set_viewport_size({"width":390,"height":844})
            assert cards.nth(1).bounding_box()["y"] > cards.nth(0).bounding_box()["y"]
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            state["user"] = {"user_id": 1, "email": "browser-test@example.invalid"}
            page.evaluate("""async () => {
                const {renderPlan} = await import('/js/ui.js');
                const {mountCompletedCourses} = await import('/js/completed_courses.js');
                const group={source_id:113,source_name:'De Anza College',is_main_college:true,target_course:'MATH 101',options:[{courses:[{code:'MATH 1A',title:'Calculus I',units:5}]},{courses:[{code:'MATH 1B',title:'Calculus II',units:5}]}]};
                const sameCourse={...group,options:[group.options[0]]};
                const otherCollege={...sameCourse,source_id:114,source_name:'Other College'};
                window.completionPlan={plan:{course_board:{universities:[
                    {university:'University A',major:'CS',required:[group],recommended:[],not_articulated:[]},
                    {university:'University B',major:'CS',required:[],recommended:[sameCourse],not_articulated:[]},
                    {university:'University C',major:'CS',required:[otherCollege],recommended:[],not_articulated:[]}
                ],legend:[],footnotes:[]}}};
                document.querySelector('#results').innerHTML=renderPlan(window.completionPlan);
                mountCompletedCourses(window.completionPlan);
                mountCompletedCourses(window.completionPlan);
            }""")
            combined = page.locator("#combined-course-board")
            expect(combined).to_be_visible()
            expect(page.locator('#university-plan-0')).to_be_hidden()
            page.locator('[data-plan-view="0"]').click()
            expect(combined).to_be_hidden()
            expect(page.locator('#university-plan-0')).to_be_visible()
            expect(page.locator('#university-plan-1')).to_be_hidden()
            tracked = combined.locator('[data-source-id="113"][data-course-code="MATH 1A"]')
            complete = tracked.get_by_role("button", name="Mark complete", exact=True)
            page.locator('.university-course-plan').first.get_by_role('button', name='Mark complete', exact=True).click()
            page.locator('[data-plan-view="1"]').click()
            expect(page.locator('#university-plan-0')).to_be_hidden()
            expect(page.locator('#university-plan-1 .equivalency-course.is-completed-course')).to_be_visible()
            page.locator('[data-plan-view="combined"]').click()
            expect(combined).to_be_visible()
            undo = tracked.get_by_role("button", name="Undo", exact=True)
            expect(undo).to_be_enabled()
            assert state["completion_writes"] == 1
            university_rows = page.locator('.university-course-plan .equivalency-course[data-source-id="113"][data-course-code="MATH 1A"]')
            expect(page.locator('.university-course-plan .equivalency-course.is-completed-course')).to_have_count(2)
            expect(page.locator('.university-course-plan .is-completed-requirement')).to_have_count(2)
            expect(page.locator('.equivalency-course[data-source-id="114"].is-completed-course')).to_have_count(0)
            assert university_rows.first.evaluate("el => getComputedStyle(el).filter") == "grayscale(1)"
            assert tracked.evaluate("el => getComputedStyle(el).filter") == "grayscale(1)"
            page.evaluate("""async () => {
                const group = document.querySelector('#university-plan-0 .equivalency-group');
                group.querySelectorAll('.equivalency-option').forEach(option => {
                    option.hidden = option.dataset.optionIndex !== '1';
                });
                (await import('/js/completed_courses.js')).mountCompletedCourses(window.completionPlan);
            }""")
            expect(undo).to_be_enabled()
            alternative = page.locator('#university-plan-0 .equivalency-group')
            expect(alternative).to_have_class('equivalency-group is-completed-requirement')
            assert alternative.evaluate('el => getComputedStyle(el).filter') == 'grayscale(1)'
            expect(alternative.locator('.equivalency-option:not([hidden]) .is-completed-course')).to_have_count(0)
            page.evaluate("async () => (await import('/js/completed_courses.js')).mountCompletedCourses(window.completionPlan)")
            expect(undo).to_be_enabled()
            expect(page.locator('.university-course-plan .equivalency-course.is-completed-course')).to_have_count(2)
            undo.click()
            expect(complete).to_be_enabled()
            expect(page.locator('.university-course-plan .is-completed-course')).to_have_count(0)
            expect(page.locator('.university-course-plan .is-completed-requirement')).to_have_count(0)
            assert state["completion_writes"] == 2
            page.evaluate("""async () => {
                const {renderCombinedCourseBoard} = await import('/js/ui.js');
                const {mountCompletedCourses} = await import('/js/completed_courses.js');
                document.querySelector('[data-option-switch]').dataset.optionCurrent='1';
                document.querySelector('#combined-course-board').innerHTML=renderCombinedCourseBoard(window.completionPlan.plan.course_board,true);
                mountCompletedCourses(window.completionPlan);
            }""")
            expect(combined.locator('[data-course-code="MATH 1B"]')).to_have_count(1)
            expect(combined.locator('[data-course-code="MATH 1B"]').get_by_role("button", name="Mark complete", exact=True)).to_be_enabled()
            assert not errors, errors
            browser.close()
        print(json.dumps({"browser": "passed", "checks": ["service navigation", "retired service fallback", "login and logout", "planner layout", "completed courses", "mobile width", "login and signup without email recovery"], "screenshots": str(output)}))
    finally:
        server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--services-only", action="store_true", help="Check service removal and shared account flows without planner rendering scenarios")
    main(services_only=parser.parse_args().services_only)
