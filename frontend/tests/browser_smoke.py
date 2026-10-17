"""Browser verification with isolated mock accounts; never contacts real APIs."""
import json
import threading
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT / "frontend")))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    output = ROOT / "scratch" / "integration-preview"
    output.mkdir(parents=True, exist_ok=True)
    state = {"user": None, "profile": {"transfer_stage": "", "major": "", "interests": []}, "email_enabled": False, "ranks": 0, "extra_events": [], "completed": [], "completion_writes": 0}
    event = {"title": "Transfer workshop", "date": "2026-10-20", "location": "Transfer Center", "latitude": 37.321623, "longitude": -122.0447979, "description": "Prepare your university application.", "url": "https://example.org/workshop"}
    errors = []

    def set_interests(page, values):
        pressed = page.locator('#compass-interest-options button[aria-pressed="true"]')
        while pressed.count():
            pressed.first.click()
        for value in (["transfer"] + values if values else []):
            page.locator(f'#compass-interest-options button[data-interest="{value}"]').click()

    def toggle_transfer(page, enabled):
        button = page.get_by_role("button", name="Transfer", exact=True)
        if button.get_attribute("aria-pressed") != str(enabled).lower():
            button.click()

    def respond(route):
        req = route.request
        path = urlsplit(req.url).path
        body = req.post_data_json if req.post_data else {}
        code = 200
        if req.method == "OPTIONS":
            data = {}
        elif path == "/api/auth/config":
            data = {"google_client_id": "", "password_reset_available": True}
        elif path == "/api/auth/me":
            data = {"logged_in": bool(state["user"]), "user": state["user"]}
        elif path in ("/api/auth/login", "/api/auth/signup"):
            state["user"] = {"user_id": 1, "email": body["email"]}
            data = {"logged_in": True, "user": state["user"]}
        elif path == "/api/auth/logout":
            state["user"] = None
            data = {"logged_in": False}
        elif path == "/api/auth/reset-password":
            data = {"message": "Password updated. Please log in with your new password."}
        elif path == "/api/compass/events":
            data = {"events": [event, *state["extra_events"]]}
        elif path == "/api/compass/profile-options":
            data = {"transfer_stages": [{"value": "", "label": "Not selected"}, {"value": "exploring", "label": "Exploring transfer options"}, {"value": "preparing", "label": "Preparing to transfer"}, {"value": "applying", "label": "Applying this admission cycle"}], "majors": ["Computer Science"]}
        elif path == "/api/compass/profile":
            if req.method == "PUT":
                state["profile"] = body
            data = {"profile": state["profile"]}
        elif path == "/api/compass/rerank":
            state["ranks"] += 1
            data = {"events": [{**event, "tier": "high", "reason": "This supports your transfer goal."}, *state["extra_events"]]}
        elif path == "/api/compass/email-preferences":
            if req.method == "PUT":
                state["email_enabled"] = body["enabled"]
            data = {"available": True, "enabled": state["email_enabled"], "pending": False}
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
            # Exercise graceful map failure while keeping the test offline.
            context.route("https://**/*", lambda route: route.abort())
            page = context.new_page()
            page.clock.install(time=datetime(2026, 10, 16, 19, tzinfo=timezone.utc))
            page.on("pageerror", lambda error: errors.append(str(error)))
            base = f"http://127.0.0.1:{server.server_port}"
            page.goto(base)
            expect(page.get_by_role("heading", name="One pathway. More possibilities.")).to_be_visible()
            page.screenshot(path=str(output / "home.png"), full_page=True)
            page.get_by_role("link", name="Explore campus events").click()
            expect(page.get_by_role("heading", name="Transfer workshop")).to_be_visible()
            expect(page.locator(".leaflet-marker-icon")).to_have_count(1)
            expect(page.get_by_label("Transfer preparation stage", exact=True)).to_have_count(0)
            toggle_transfer(page, False)
            expect(page.locator(".compass-event")).to_have_count(0)
            expect(page.locator(".leaflet-marker-icon")).to_have_count(0)
            toggle_transfer(page, True)
            expect(page.locator(".compass-event")).to_have_count(1)

            expect(page.get_by_role("button", name="Save and recommend")).to_be_disabled()
            page.get_by_role("button", name="Log in / Sign up").click()
            page.locator("#auth-email").fill("browser-test@example.invalid")
            page.locator("#auth-password").fill("local-test-password")
            page.locator("#auth-submit").click()
            expect(page.get_by_role("button", name="Save and recommend")).to_be_enabled()
            page.get_by_label("Major", exact=True).select_option("Computer Science")
            set_interests(page, ["career and scholarships", "campus life"])
            page.get_by_role("button", name="Save and recommend").click()
            expect(page.locator("#compass-profile-status")).to_have_text("Profile saved. Your recommendations are ready.")
            assert state["profile"]["interests"] == ["transfer", "career and scholarships", "campus life"]
            page.reload()
            expect(page.locator("#compass-profile-status")).to_have_text("Your saved profile and recommendations are ready.")
            expect(page.get_by_role("button", name="Campus Life", exact=True)).to_have_attribute("aria-pressed", "true")
            expect(page.get_by_role("button", name="Career & Scholarships", exact=True)).to_have_attribute("aria-pressed", "true")
            expect(page.locator(".compass-event.priority-high")).to_have_count(1)
            expect(page.locator(".compass-pin.priority-high")).to_have_count(1)
            assert page.locator(".compass-pin.priority-high").evaluate("el => getComputedStyle(el).backgroundColor") == "rgb(232, 90, 79)"
            page.get_by_role("button", name="Clear major", exact=True).click()
            expect(page.get_by_label("Major", exact=True)).to_have_value("")
            expect(page.locator("#compass-profile-status")).to_contain_text("Profile changed")
            set_interests(page, ["campus life"])
            page.get_by_role("button", name="Save and recommend", exact=True).click()
            expect(page.locator("#compass-profile-status")).to_have_text("Profile saved. Your recommendations are ready.")
            assert state["profile"]["major"] == ""
            assert state["profile"]["interests"] == ["transfer", "campus life"]
            page.reload()
            expect(page.locator("#compass-profile-status")).to_have_text("Your saved profile and recommendations are ready.")
            expect(page.get_by_label("Major", exact=True)).to_have_value("")
            expect(page.get_by_role("button", name="Campus Life", exact=True)).to_have_attribute("aria-pressed", "true")
            expect(page.get_by_role("button", name="Clear major", exact=True)).to_be_disabled()
            set_interests(page, [])
            page.get_by_role("button", name="Save and recommend", exact=True).click()
            expect(page.locator("#compass-profile-status")).to_have_text("Profile saved. Your recommendations are ready.")
            assert state["profile"] == {"transfer_stage": "", "major": "", "interests": []}
            page.reload()
            expect(page.locator("#compass-profile-status")).to_have_text("Your profile is linked to your Pathway account.")
            expect(page.get_by_label("Major", exact=True)).to_have_value("")
            page.get_by_label("Major", exact=True).select_option("Computer Science")
            set_interests(page, ["career and scholarships"])
            page.get_by_role("button", name="Save and recommend", exact=True).click()
            expect(page.locator("#compass-profile-status")).to_have_text("Profile saved. Your recommendations are ready.")
            ranks = state["ranks"]
            page.get_by_role("button", name="Today", exact=True).click()
            expect(page.locator(".compass-event")).to_have_count(0)
            expect(page.locator(".leaflet-marker-icon")).to_have_count(0)
            expect(page.locator("#compass-status")).to_contain_text("No events in this range")
            page.get_by_role("button", name="1 week", exact=True).click()
            expect(page.locator(".compass-event.priority-high")).to_have_count(1)
            expect(page.locator(".compass-pin.priority-high")).to_have_count(1)
            assert state["ranks"] == ranks, "Changing the range must reuse the existing AI result"
            page.reload()
            expect(page.locator("#compass-profile-status")).to_have_text("Your saved profile and recommendations are ready.")
            expect(page.locator(".compass-pin.priority-high")).to_have_count(1)
            page.get_by_label("Daily campus event emails", exact=True).check()
            expect(page.locator("#compass-email-status")).to_contain_text("Daily emails are on")
            state["extra_events"] = [
                {**event, "title": "Same-location workshop", "tier": "medium"},
                {**event, "title": "Library workshop", "location": "Library", "description": "Study skills and library resources", "latitude": 37.318, "longitude": -122.045, "tier": "low"},
            ]
            page.reload()
            expect(page.locator("#compass-profile-status")).to_have_text("Your saved profile and recommendations are ready.")
            expect(page.locator(".compass-event")).to_have_count(3)
            expect(page.locator(".leaflet-marker-icon")).to_have_count(2)
            toggle_transfer(page, False)
            expect(page.locator(".compass-event")).to_have_count(1)
            expect(page.get_by_role("heading", name="Library workshop", exact=True)).to_be_visible()
            page.get_by_role("button", name="Save and recommend", exact=True).click()
            expect(page.locator("#compass-profile-status")).to_have_text("Profile saved. Your recommendations are ready.")
            page.reload()
            expect(page.locator("#compass-profile-status")).to_have_text("Your saved profile and recommendations are ready.")
            expect(page.get_by_role("button", name="Transfer", exact=True)).to_have_attribute("aria-pressed", "false")
            expect(page.locator(".compass-event")).to_have_count(1)
            toggle_transfer(page, True)
            expect(page.locator(".compass-event")).to_have_count(3)
            assert page.locator("#compass-events").bounding_box()["x"] > page.locator("#compass-map").bounding_box()["x"]
            page.locator('.leaflet-marker-icon[title^="2 event"]').click()
            expect(page.locator(".compass-event")).to_have_count(2)
            expect(page.get_by_role("heading", name="Library workshop", exact=True)).to_have_count(0)
            expect(page.locator(".leaflet-popup")).to_have_count(0)
            expect(page.locator(".leaflet-marker-icon")).to_have_count(2)
            expect(page.locator(".compass-marker.is-selected")).to_have_count(1)
            page.screenshot(path=str(output / "compass-location-selection.png"), full_page=True)
            page.locator('.leaflet-marker-icon[title^="1 event"]').click()
            expect(page.locator(".compass-event")).to_have_count(1)
            expect(page.get_by_role("heading", name="Library workshop", exact=True)).to_be_visible()
            page.get_by_role("button", name="Show all locations", exact=True).click()
            expect(page.locator(".compass-event")).to_have_count(3)
            page.locator('.leaflet-marker-icon[title^="2 event"]').click()
            page.get_by_role("button", name="Today", exact=True).click()
            expect(page.locator(".compass-event")).to_have_count(0)
            expect(page.get_by_role("button", name="Show all locations", exact=True)).to_be_hidden()
            page.get_by_role("button", name="1 week", exact=True).click()
            expect(page.locator(".compass-event")).to_have_count(3)
            state["extra_events"] = []
            page.get_by_role("button", name="Save and recommend", exact=True).click()
            expect(page.locator("#compass-profile-status")).to_have_text("Profile saved. Your recommendations are ready.")
            page.reload()
            expect(page.locator("#compass-profile-status")).to_have_text("Your saved profile and recommendations are ready.")
            page.screenshot(path=str(output / "compass.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            page.screenshot(path=str(output / "compass-mobile.png"), full_page=True)
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Mobile page overflows horizontally"
            page.evaluate("""() => {
                const original = window.fetch;
                let delayed = false;
                window.fetch = async (...args) => {
                    if (!delayed && String(args[0]).includes('/compass/rerank')) {
                        delayed = true;
                        await new Promise(resolve => setTimeout(resolve, 1800));
                    }
                    return original(...args);
                };
                window.dispatchEvent(new CustomEvent('pathway:auth-changed'));
            }""")
            expect(page.locator("#compass-profile-status")).to_have_text("Preparing recommendations for your saved profile...")
            expect(page.get_by_label("Major", exact=True)).to_be_enabled()
            page.get_by_role("button", name="Clear major", exact=True).click()
            set_interests(page, ["campus life"])
            page.clock.run_for(2000)
            expect(page.get_by_role("button", name="Save and recommend", exact=True)).to_be_enabled()
            expect(page.get_by_label("Major", exact=True)).to_have_value("")
            expect(page.locator("#compass-profile-status")).to_contain_text("Profile changed")
            page.get_by_role("button", name="Log out", exact=True).click()
            expect(page.get_by_role("button", name="Save and recommend")).to_be_disabled()
            expect(page.locator(".compass-event.priority-high")).to_have_count(0)
            expect(page.locator(".compass-pin.priority-ranking")).to_have_count(1)
            page.get_by_role("link", name="Transfer Planner", exact=True).click()
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
            page.goto(base + "/#reset=" + "a" * 50)
            expect(page.get_by_role("heading", name="Choose a new password")).to_be_visible()
            expect(page.locator("#auth-email")).to_be_hidden()
            page.locator("#auth-password").fill("new-local-test-password")
            page.locator("#auth-submit").click()
            expect(page.locator("#auth-message")).to_contain_text("Password updated")
            assert not errors, errors
            browser.close()
        print(json.dumps({"browser": "passed", "checks": ["service navigation", "login", "save profile and rank", "email opt-in", "logout clears personalized results", "mobile width", "password recovery", "date ranges", "AI marker colors", "saved-profile auto ranking", "marker selects event list without popup", "switch and clear location", "range resets unavailable location", "clear major and persist interest-only profile", "clear entire profile", "transfer checkbox filtering and persistence", "major remains editable while AI is pending"], "screenshots": str(output)}))
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
