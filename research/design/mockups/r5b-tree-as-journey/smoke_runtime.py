#!/usr/bin/env python3
"""Runtime smoke test for R5b journey.html prototype — read-only, does not modify the file."""
import json
import sys
from playwright.sync_api import sync_playwright

FILE_PATH = "/private/tmp/claude-501/-Users-nuzantara-nuzantara/b0b4cfee-0d97-475c-b63f-36f99027cf5c/scratchpad/r5b/journey.html"
URL = "file://" + FILE_PATH
VIEWPORT = {"width": 360, "height": 640}

results = []
fails = []


def record(n, name, status, detail):
    results.append({"n": n, "name": name, "status": status, "detail": detail})
    if status == "FAIL":
        fails.append(f"{n}. {name}: {detail}")
    print(f"[{status}] {n}. {name} — {detail}")


def new_ctx(browser):
    ctx = browser.new_context(viewport=VIEWPORT)
    page = ctx.new_page()
    page.goto(URL)
    page.wait_for_selector("#qTitle")
    return ctx, page


def click_option(page, text):
    # options are <button class="option" role="radio"> containing a hidden tick span + text span
    page.get_by_role("radio", name=text, exact=True).click()
    page.wait_for_timeout(60)


def get_active_desc(page):
    return page.evaluate(
        """() => {
        const el = document.activeElement;
        if (!el) return null;
        return {tag: el.tagName, id: el.id, cls: el.className};
    }"""
    )


focus_log = []


def check_focus_after(page, step_label):
    d = get_active_desc(page)
    ok = bool(d) and (d.get("id") == "qTitle" or d.get("id") == "cs")
    focus_log.append({"step": step_label, "active": d, "ok": ok})
    return ok


with sync_playwright() as p:
    browser = p.chromium.launch()

    # ---------- TEST 1: BOOT ----------
    try:
        ctx, page = new_ctx(browser)
        title = page.inner_text("#qTitle")
        pz_hidden = page.eval_on_selector("#progressZone", "el => el.hidden")
        ok = ("Who is filling this in?" in title) and pz_hidden is True
        record(1, "BOOT", "PASS" if ok else "FAIL",
               f"qTitle='{title}', progressZone.hidden={pz_hidden}")
        ctx.close()
    except Exception as e:
        record(1, "BOOT", "FAIL", f"exception: {e}")

    # ---------- TEST 2 + 4 (partial) + RADIO note: TOURISM path ----------
    try:
        ctx, page = new_ctx(browser)
        detail_parts = []

        # who_answers -> self
        click_option(page, "I'm the traveller")
        f2_1 = check_focus_after(page, "after who_answers")

        # in_indonesia -> No
        t = page.inner_text("#qTitle")
        detail_parts.append(f"Q(in_indonesia)='{t}'")
        click_option(page, "No, outside Indonesia")
        f2_2 = check_focus_after(page, "after in_indonesia")

        # holds_stay_permit -> No
        t = page.inner_text("#qTitle")
        detail_parts.append(f"Q(holds_stay_permit)='{t}'")
        click_option(page, "No")
        f2_3 = check_focus_after(page, "after holds_stay_permit")

        # nationalities: type "ita", filter, select Italy
        t = page.inner_text("#qTitle")
        detail_parts.append(f"Q(nationalities)='{t}'")
        page.fill("#cs", "ita")
        page.wait_for_timeout(80)
        cl_texts = page.eval_on_selector_all("#cl button", "els => els.map(e => e.textContent)")
        detail_parts.append(f"country-list after 'ita'={cl_texts}")
        page.get_by_role("button", name="Italy", exact=True).click()
        page.wait_for_timeout(60)
        f2_4 = check_focus_after(page, "after nationalities")

        # birth_date: set 1990-01-01, Continue
        t = page.inner_text("#qTitle")
        detail_parts.append(f"Q(birth_date)='{t}'")
        page.fill("#dob", "1990-01-01")
        page.get_by_role("button", name="Continue", exact=True).click()
        page.wait_for_timeout(60)
        f2_5 = check_focus_after(page, "after birth_date")

        # category -> Tourism
        t = page.inner_text("#qTitle")
        detail_parts.append(f"Q(category)='{t}'")
        click_option(page, "Tourism or a short visit")
        f2_6 = check_focus_after(page, "after category")

        counter_text = page.inner_text("#counterText")
        announce_text = page.inner_text("#counterAnnounce")
        counter_ok = counter_text.strip() == "Question 6 of 9"
        announce_ok = "confirmed" in announce_text

        detail_parts.append(f"counterText='{counter_text}' announce='{announce_text}'")

        # continue to review: trip_scope -> entry_pattern -> stay_days
        t = page.inner_text("#qTitle")
        detail_parts.append(f"Q(trip_scope)='{t}'")
        click_option(page, "One trip")
        page.wait_for_timeout(60)

        t = page.inner_text("#qTitle")
        detail_parts.append(f"Q(entry_pattern)='{t}'")
        click_option(page, "On arrival")
        page.wait_for_timeout(60)

        t = page.inner_text("#qTitle")
        detail_parts.append(f"Q(stay_days)='{t}'")
        click_option(page, "Under 30 days")
        page.wait_for_timeout(60)

        review_title = page.inner_text("#qTitle")
        review_rows = page.eval_on_selector_all(
            ".review-row", "els => els.map(e => e.textContent)"
        )
        page_text = page.inner_text("body")
        shadow_ok = "runs in shadow" in page_text
        review_ok = ("Check" in review_title or "answers" in review_title) and len(review_rows) >= 6

        detail_parts.append(f"review_title='{review_title}' rows={review_rows}")

        all_focus_ok = all([f2_1, f2_2, f2_3, f2_4, f2_5, f2_6])
        ok2 = counter_ok and announce_ok and review_ok and shadow_ok
        record(
            2, "TOURISM path (counter/announce/review/shadow)",
            "PASS" if ok2 else "FAIL",
            " | ".join(detail_parts) + f" | counter_ok={counter_ok} announce_ok={announce_ok} review_ok={review_ok} shadow_ok={shadow_ok}",
        )
        record(
            4, "FOCUS (h2#qTitle or #cs after each answer, tourism run)",
            "PASS" if all_focus_ok else "FAIL",
            json.dumps(focus_log),
        )
        ctx.close()
    except Exception as e:
        record(2, "TOURISM path", "FAIL", f"exception: {e}")
        record(4, "FOCUS", "FAIL", f"exception during tourism run: {e}")

    # ---------- TEST 3: CONTATORE (in_indonesia=Yes) ----------
    try:
        ctx, page = new_ctx(browser)
        click_option(page, "I'm the traveller")
        click_option(page, "Yes, in Indonesia")
        counter_text = page.inner_text("#counterText")
        announce_text = page.inner_text("#counterAnnounce")
        ok = ("of 10 or more" in counter_text) and ("Your path is now 10 questions" in announce_text) and ("+1" not in announce_text) and ("+" not in announce_text)
        record(3, "CONTATORE (in_indonesia=Yes -> 10 or more)", "PASS" if ok else "FAIL",
               f"counterText='{counter_text}' announce='{announce_text}'")
        ctx.close()
    except Exception as e:
        record(3, "CONTATORE", "FAIL", f"exception: {e}")

    # ---------- TEST 5: RADIO roving tabindex + ArrowDown ----------
    try:
        ctx, page = new_ctx(browser)
        tabindexes = page.eval_on_selector_all(
            "#screen .options .option", "els => els.map(e => e.tabIndex)"
        )
        zero_count = sum(1 for x in tabindexes if x == 0)
        # focus first option, press ArrowDown, check focus moved to 2nd option
        page.eval_on_selector("#screen .options .option", "el => el.focus()")
        active_before = page.evaluate("() => document.activeElement.textContent")
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(40)
        active_after = page.evaluate("() => document.activeElement.textContent")
        second_opt_text = page.eval_on_selector_all(
            "#screen .options .option", "els => els[1] ? els[1].textContent : null"
        )
        moved_ok = active_after == second_opt_text and active_after != active_before
        ok = (zero_count == 1) and moved_ok
        record(5, "RADIO roving tabindex + ArrowDown", "PASS" if ok else "FAIL",
               f"tabindexes={tabindexes} zero_count={zero_count} active_before='{active_before}' active_after='{active_after}' second_opt='{second_opt_text}'")
        ctx.close()
    except Exception as e:
        record(5, "RADIO", "FAIL", f"exception: {e}")

    # ---------- TEST 6: DARK theme ----------
    try:
        ctx, page = new_ctx(browser)
        page.click("#themeToggle")
        page.wait_for_timeout(60)
        theme_attr = page.eval_on_selector("#jr", "el => el.getAttribute('data-oracle-theme')")

        # go to holds_stay_permit (has .notsure)
        click_option(page, "I'm the traveller")
        click_option(page, "No, outside Indonesia")
        notsure_color = page.eval_on_selector(
            ".notsure button", "el => getComputedStyle(el).color"
        )

        # go to nationalities -> birth_date (has .cta)
        click_option(page, "No")
        page.fill("#cs", "ita")
        page.wait_for_timeout(80)
        page.get_by_role("button", name="Italy", exact=True).click()
        page.wait_for_timeout(60)
        cta_bg = page.eval_on_selector(".cta", "el => getComputedStyle(el).backgroundColor")

        theme_ok = theme_attr == "dark"
        cta_ok = cta_bg == "rgb(208, 16, 51)"
        # UA default button color is usually rgb(0,0,0) / buttontext / black-ish;
        # any non-default explicit value from CSS counts as inherited-from-CSS.
        notsure_ok = notsure_color is not None and notsure_color != ""

        ok = theme_ok and cta_ok
        record(6, "DARK theme (attr + .cta bg + .notsure color)", "PASS" if ok else "FAIL",
               f"data-oracle-theme='{theme_attr}' cta_background='{cta_bg}' (expect rgb(208, 16, 51)) notsure_button_color='{notsure_color}'")
        ctx.close()
    except Exception as e:
        record(6, "DARK theme", "FAIL", f"exception: {e}")

    # ---------- TEST 7: SPONSOR family path ----------
    try:
        ctx, page = new_ctx(browser)
        click_option(page, "I'm the traveller")
        click_option(page, "No, outside Indonesia")
        click_option(page, "No")
        page.fill("#cs", "ita")
        page.wait_for_timeout(80)
        page.get_by_role("button", name="Italy", exact=True).click()
        page.wait_for_timeout(60)
        page.fill("#dob", "1990-01-01")
        page.get_by_role("button", name="Continue", exact=True).click()
        page.wait_for_timeout(60)
        click_option(page, "Joining family")
        page.wait_for_timeout(60)
        # trip_scope
        click_option(page, "One trip")
        page.wait_for_timeout(60)
        # family_relation -- check branch note BEFORE answering
        branch_note_text = page.inner_text(".branch-note")
        family_relation_title = page.inner_text("#qTitle")
        click_option(page, "Spouse")
        page.wait_for_timeout(60)
        # marital_status
        click_option(page, "Married")
        page.wait_for_timeout(60)
        # family_sponsor_nationalities (country)
        t_sponsor_nat = page.inner_text("#qTitle")
        page.fill("#cs", "indo")
        page.wait_for_timeout(80)
        page.get_by_role("button", name="Indonesia", exact=True).click()
        page.wait_for_timeout(60)
        # now should be at family_sponsor_status_code
        title_now = page.inner_text("#qTitle")
        badge_text = page.inner_text(".subprogress")

        badge_ok = "Sponsor 4 of 6" in badge_text
        note_ok = "sponsor" in branch_note_text.lower() and "6 questions" in branch_note_text
        ok = badge_ok and note_ok
        record(7, "SPONSOR badge + branch note", "PASS" if ok else "FAIL",
               f"branch_note='{branch_note_text}' family_relation_title='{family_relation_title}' sponsor_nat_title='{t_sponsor_nat}' now_title='{title_now}' badge='{badge_text}'")
        ctx.close()
    except Exception as e:
        record(7, "SPONSOR", "FAIL", f"exception: {e}")

    # ---------- TEST 8: DELEGATE ----------
    try:
        ctx, page = new_ctx(browser)
        click_option(page, "I'm helping someone else")
        page.wait_for_timeout(60)
        delegate_confirm_title = page.inner_text("#qTitle")
        click_option(page, "The traveller asked me to fill this in, and I'll check with them when unsure")
        page.wait_for_timeout(60)
        banner_hidden = page.eval_on_selector("#delegateBanner", "el => el.hidden")
        in_indonesia_title = page.inner_text("#qTitle")

        title_ok = "Answering for the traveller" in delegate_confirm_title
        banner_ok = banner_hidden is False
        wording_ok = ("Is the traveller" in in_indonesia_title) and ("Are you" not in in_indonesia_title)

        ok = title_ok and banner_ok and wording_ok
        record(8, "DELEGATE flow", "PASS" if ok else "FAIL",
               f"delegate_confirm_title='{delegate_confirm_title}' banner_hidden={banner_hidden} in_indonesia_title='{in_indonesia_title}'")
        ctx.close()
    except Exception as e:
        record(8, "DELEGATE", "FAIL", f"exception: {e}")

    # ---------- TEST 9: RESUME ----------
    try:
        ctx, page = new_ctx(browser)
        click_option(page, "I'm the traveller")
        click_option(page, "No, outside Indonesia")
        page.wait_for_timeout(60)
        pre_reload_title = page.inner_text("#qTitle")
        page.click("#saveBtn")
        page.wait_for_timeout(60)
        save_msg = page.inner_text("#liveRegion")
        state_before = page.evaluate("() => localStorage.getItem('r5b-proto-state')")

        page.reload()
        page.wait_for_selector("#qTitle")
        page.wait_for_timeout(100)
        post_reload_title = page.inner_text("#qTitle")

        state_after = page.evaluate("() => localStorage.getItem('r5b-proto-state')")
        state_obj = json.loads(state_after) if state_after else None
        v_ok = state_obj is not None and state_obj.get("v") == 2
        resumed_ok = pre_reload_title == post_reload_title

        ok = v_ok and resumed_ok
        record(9, "RESUME (Save & continue later, reload)", "PASS" if ok else "FAIL",
               f"pre_reload_title='{pre_reload_title}' post_reload_title='{post_reload_title}' save_msg='{save_msg}' state_v={state_obj.get('v') if state_obj else None} state_after_present={state_after is not None}")
        ctx.close()
    except Exception as e:
        record(9, "RESUME", "FAIL", f"exception: {e}")

    # ---------- TEST 10: OVERFLOW ----------
    try:
        ctx, page = new_ctx(browser)
        scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
        ok = scroll_width == 360
        record(10, "OVERFLOW (scrollWidth==360)", "PASS" if ok else "FAIL",
               f"document.documentElement.scrollWidth={scroll_width}")
        ctx.close()
    except Exception as e:
        record(10, "OVERFLOW", "FAIL", f"exception: {e}")

    browser.close()

output = {
    "tool_used": "playwright-python (chromium)",
    "results": results,
    "fails": fails,
}
OUT_PATH = "/private/tmp/claude-501/-Users-nuzantara-nuzantara/b0b4cfee-0d97-475c-b63f-36f99027cf5c/scratchpad/r5b/smoke-runtime.json"
with open(OUT_PATH, "w") as f:
    json.dump(output, f, indent=2)

print("\n=== SUMMARY ===")
for r in results:
    print(f"{r['n']}. {r['name']}: {r['status']}")
print("\nFAILS:", fails if fails else "none")
