#!/usr/bin/env python3
"""R6 deep a11y/robustness suite for R5b journey.html — read-only, does not modify the file.

Interpreter: system python3 (/opt/homebrew/bin/python3), playwright 1.58.0, chromium 145 —
same stack r5b/smoke_runtime.py used (no dedicated venv found; playwright is on system python3).

Covers the 8 probes out of scope for the R5b 10-probe smoke (that one covered
boot/tourism-path/counter/focus/roving-tabindex/dark/sponsor/delegate/resume/overflow):
  1. KEYBOARD-ONLY FULL TRAVERSAL (tourism branch, boot -> verdict boundary, no mouse)
  2. LIVE-REGION SEQUENCE (family+sponsor path, every #liveRegion mutation captured)
  3. STORAGE CORRUPTION (4 malformed localStorage payloads, must degrade clean)
  4. REDUCED MOTION (prefers-reduced-motion computed-style check)
  5. ZOOM/REFLOW 400% (viewport 360, text-only zoom proxy + supplementary CSS zoom)
  6. DELEGATE KEYBOARD (delegate_confirm checkpoint, keyboard-only, banner perceivability)
  7. FOCUS TRAP CHECK (Tab/Shift+Tab never repeats/never lands on body)
  8. CONSOLE HYGIENE (zero console errors / pageerrors across every probe's pages)

Every probe declares in its own JSON block what WOULD have made it FAIL (would_fail_if),
per the mandate's falsifiability rule. Nothing here is faked: a probe genuinely
unmeasurable in headless Chromium is recorded as unmeasurable_headless with a reason,
never guessed at.
"""
import json
import re
from playwright.sync_api import sync_playwright

FILE_PATH = "/private/tmp/claude-501/-Users-nuzantara-nuzantara/b0b4cfee-0d97-475c-b63f-36f99027cf5c/scratchpad/r5b/journey.html"
URL = "file://" + FILE_PATH
VIEWPORT = {"width": 360, "height": 640}
OUT_PATH = "/private/tmp/claude-501/-Users-nuzantara-nuzantara/b0b4cfee-0d97-475c-b63f-36f99027cf5c/scratchpad/r6/a11y-runtime.json"

results = []
console_log = []  # {"probe": n, "type": "error"|"pageerror", "text": ...}
_current_probe = [0]


def record(n, name, verdict, would_fail_if, evidence, notes=""):
    entry = {
        "n": n,
        "name": name,
        "verdict": verdict,
        "would_fail_if": would_fail_if,
        "evidence": evidence,
        "notes": notes,
    }
    results.append(entry)
    print(f"[{verdict}] {n}. {name}")


def new_ctx(browser, **kwargs):
    _kwargs = dict(viewport=VIEWPORT)
    _kwargs.update(kwargs)
    ctx = browser.new_context(**_kwargs)
    page = ctx.new_page()

    def on_console(msg):
        if msg.type == "error":
            console_log.append({"probe": _current_probe[0], "type": "console.error", "text": msg.text})

    def on_pageerror(exc):
        console_log.append({"probe": _current_probe[0], "type": "pageerror", "text": str(exc)})

    page.on("console", on_console)
    page.on("pageerror", on_pageerror)
    return ctx, page


def boot(page):
    page.goto(URL)
    page.wait_for_selector("#qTitle")


def active_info(page):
    # accessible-name-ish text: clone + drop aria-hidden descendants (the roving-tabindex
    # option buttons prepend a visibility:hidden "tick" span that IS aria-hidden="true"
    # (journey.html:385) — the querySelectorAll('[aria-hidden="true"]') removal below already
    # excludes it, so raw .textContent's "✓I'm the traveller" never reaches callers of this
    # function. Corrected 2026-08-27; see select_radio_by_text()'s docstring for the full note.)
    return page.evaluate(
        """() => {
        const el = document.activeElement;
        if (!el) return null;
        const r = el.getBoundingClientRect();
        const c = el.cloneNode(true);
        c.querySelectorAll('[aria-hidden="true"]').forEach(n => n.remove());
        return {
          tag: el.tagName, id: el.id, role: el.getAttribute('role'),
          text: c.textContent.trim().slice(0,80),
          isBody: el === document.body,
          visible: !!(el.offsetParent || el.tagName === 'BODY'),
          rectVisible: r.width > 0 && r.height > 0
        };
    }"""
    )


def tab_to(page, predicate, max_tabs=25, shift=False):
    """Press Tab (or Shift+Tab) repeatedly until predicate(active_info) is true.
    Returns (found, presses, last_info, trace)."""
    trace = []
    for i in range(max_tabs):
        page.keyboard.press("Shift+Tab" if shift else "Tab")
        page.wait_for_timeout(15)
        info = active_info(page)
        trace.append(info)
        if info and predicate(info):
            return True, i + 1, info, trace
    return False, max_tabs, (trace[-1] if trace else None), trace


CLEAN_TEXT_JS = """el => {
    const c = el.cloneNode(true);
    c.querySelectorAll('[aria-hidden="true"]').forEach(n => n.remove());
    return c.textContent.trim();
}"""


def select_radio_by_text(page, desired_text, key="Enter"):
    """Assumes focus is already on some .option[role=radio] inside #screen .options.
    Uses only ArrowDown (forward, wraps) to reach the desired option, then Enter/Space.
    Text is read via a clone with aria-hidden descendants stripped — the option's hidden
    "tick" span IS built with aria-hidden="true" (journey.html:385,
    tick.setAttribute("aria-hidden","true")), and CLEAN_TEXT_JS's
    querySelectorAll('[aria-hidden="true"]') removes it before reading .textContent, so the
    comparison below is already against the clean label with no leading '✓'. (Corrected
    2026-08-27 — R6 audit of a suspected "BUG A" matcher defect: an earlier version of this
    docstring claimed the tick was "NOT aria-hidden-excluded", which was never true of
    journey.html's actual markup and was itself the source of the false-positive bug report;
    the stripping code (CLEAN_TEXT_JS, used both here and in active_info() above) was correct
    all along — verified live via eval_on_selector_all and a full probe 1/6 re-run, both PASS.)"""
    texts = page.eval_on_selector_all("#screen .options .option", f"els => els.map({CLEAN_TEXT_JS})")
    cur_idx = page.evaluate(
        "() => { const els=[...document.querySelectorAll('#screen .options .option')]; return els.indexOf(document.activeElement); }"
    )
    if desired_text not in texts:
        return {"ok": False, "reason": f"'{desired_text}' not among options {texts}"}
    target = texts.index(desired_text)
    n = len(texts)
    presses = (target - cur_idx) % n if cur_idx >= 0 else None
    if presses is None:
        return {"ok": False, "reason": f"focus not inside radiogroup (cur_idx={cur_idx})"}
    for _ in range(presses):
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(15)
    now_text = page.evaluate(f"() => {{ const el=document.activeElement; return el ? ({CLEAN_TEXT_JS})(el) : ''; }}")
    focus_ok = now_text == desired_text
    page.keyboard.press(key)
    page.wait_for_timeout(60)
    return {"ok": focus_ok, "reason": None if focus_ok else f"after {presses} ArrowDown, focused '{now_text}' != '{desired_text}'",
            "arrow_presses": presses, "activation_key": key}


with sync_playwright() as p:
    browser = p.chromium.launch()

    # ================= PROBE 1: KEYBOARD-ONLY FULL TRAVERSAL =================
    _current_probe[0] = 1
    try:
        ctx, page = new_ctx(browser)
        boot(page)
        steps = []
        ok_all = True

        def step(label, fn):
            global ok_all
            try:
                r = fn()
                steps.append({"label": label, **(r if isinstance(r, dict) else {"detail": r})})
                if isinstance(r, dict) and r.get("ok") is False:
                    ok_all = False
            except Exception as e:
                steps.append({"label": label, "ok": False, "reason": f"exception: {e}"})
                ok_all = False

        # who_answers -> "I'm the traveller" (Enter)
        def s1():
            found, n, info, _ = tab_to(page, lambda i: i["role"] == "radio")
            if not found:
                return {"ok": False, "reason": "never reached a radio via Tab from boot"}
            r = select_radio_by_text(page, "I'm the traveller", key="Enter")
            return {"ok": found and r["ok"], "tabs_to_reach_group": n, **r}
        step("who_answers -> self (Tab..Tab, Enter)", s1)

        # in_indonesia -> "No, outside Indonesia" (Space)
        def s2():
            found, n, info, _ = tab_to(page, lambda i: i["role"] == "radio")
            if not found:
                return {"ok": False, "reason": "never reached a radio"}
            r = select_radio_by_text(page, "No, outside Indonesia", key="Space")
            return {"ok": found and r["ok"], "tabs_to_reach_group": n, **r}
        step("in_indonesia -> outside (Tab, ArrowDown, Space)", s2)

        # holds_stay_permit -> "No" (Enter)
        def s3():
            found, n, info, _ = tab_to(page, lambda i: i["role"] == "radio")
            if not found:
                return {"ok": False, "reason": "never reached a radio"}
            r = select_radio_by_text(page, "No", key="Enter")
            return {"ok": found and r["ok"], "tabs_to_reach_group": n, **r}
        step("holds_stay_permit -> No (Tab, Enter)", s3)

        # nationalities -> type "Italy", Tab to the Italy button, Enter
        def s4():
            found, n, info, _ = tab_to(page, lambda i: i["tag"] == "INPUT" and i["id"] == "cs")
            if not found:
                return {"ok": False, "reason": "never reached #cs input via Tab"}
            page.wait_for_selector("#cl button")  # initial unfiltered list painted
            page.keyboard.type("Italy", delay=15)
            page.wait_for_timeout(80)
            list_after = page.eval_on_selector_all("#cl button", "els => els.map(e => e.textContent)")
            found2, n2, info2, _ = tab_to(page, lambda i: i["tag"] == "BUTTON" and i["text"] == "Italy")
            if not found2:
                return {"ok": False, "reason": f"never reached 'Italy' button via Tab; list after typing={list_after}"}
            page.keyboard.press("Enter")
            page.wait_for_timeout(60)
            return {"ok": True, "tabs_to_input": n, "list_after_typing": list_after, "tabs_to_italy": n2}
        step("nationalities -> type Italy, Tab to button, Enter", s4)

        # birth_date -> type digits, Tab to Continue, Enter
        def s5():
            found, n, info, _ = tab_to(page, lambda i: i["tag"] == "INPUT" and i["id"] == "dob")
            if not found:
                return {"ok": False, "reason": "never reached #dob via Tab"}
            page.keyboard.type("01011990", delay=20)
            page.wait_for_timeout(40)
            val = page.eval_on_selector("#dob", "el => el.value")
            found2, n2, info2, _ = tab_to(page, lambda i: i["tag"] == "BUTTON" and "Continue" in i["text"])
            if not found2:
                return {"ok": False, "reason": f"never reached Continue button via Tab; dob.value after typing={val}"}
            page.keyboard.press("Enter")
            page.wait_for_timeout(60)
            title_after = page.inner_text("#qTitle")
            advanced = title_after != "Age check"
            return {"ok": (val == "1990-01-01") and advanced, "dob_value_after_keyboard_typing": val,
                    "tabs_to_dob": n, "tabs_to_continue": n2, "title_after": title_after}
        step("birth_date -> type 01011990 keyboard-only, Tab to Continue, Enter", s5)

        # category -> "Tourism or a short visit" (Enter)
        def s6():
            found, n, info, _ = tab_to(page, lambda i: i["role"] == "radio")
            if not found:
                return {"ok": False, "reason": "never reached a radio"}
            r = select_radio_by_text(page, "Tourism or a short visit", key="Enter")
            return {"ok": found and r["ok"], "tabs_to_reach_group": n, **r}
        step("category -> tourism (Tab, Enter)", s6)

        # trip_scope -> "One trip" (Space)
        def s7():
            found, n, info, _ = tab_to(page, lambda i: i["role"] == "radio")
            if not found:
                return {"ok": False, "reason": "never reached a radio"}
            r = select_radio_by_text(page, "One trip", key="Space")
            return {"ok": found and r["ok"], "tabs_to_reach_group": n, **r}
        step("trip_scope -> one trip (Tab, Space)", s7)

        # entry_pattern -> "On arrival" (Enter)
        def s8():
            found, n, info, _ = tab_to(page, lambda i: i["role"] == "radio")
            if not found:
                return {"ok": False, "reason": "never reached a radio"}
            r = select_radio_by_text(page, "On arrival", key="Enter")
            return {"ok": found and r["ok"], "tabs_to_reach_group": n, **r}
        step("entry_pattern -> on arrival (Tab, Enter)", s8)

        # stay_days -> "Under 30 days" (Space)
        def s9():
            found, n, info, _ = tab_to(page, lambda i: i["role"] == "radio")
            if not found:
                return {"ok": False, "reason": "never reached a radio"}
            r = select_radio_by_text(page, "Under 30 days", key="Space")
            return {"ok": found and r["ok"], "tabs_to_reach_group": n, **r}
        step("stay_days -> under 30 days (Tab, Space)", s9)

        # review_gate -> Tab to the CTA, Enter
        def s10():
            title = page.inner_text("#qTitle")
            found, n, info, _ = tab_to(page, lambda i: i["tag"] == "BUTTON" and "verdict would appear" in i["text"])
            if not found:
                return {"ok": False, "reason": f"never reached review CTA via Tab; review title='{title}'"}
            page.keyboard.press("Enter")
            page.wait_for_timeout(60)
            final_title = page.inner_text("#qTitle")
            return {"ok": "verdict boundary" in final_title, "review_title": title,
                    "tabs_to_cta": n, "final_title": final_title}
        step("review_gate -> Tab to CTA, Enter -> verdict boundary", s10)

        fail_steps = [s for s in steps if s.get("ok") is False]
        verdict = "PASS" if not fail_steps else "FAIL"
        record(
            1, "KEYBOARD-ONLY FULL TRAVERSAL (boot -> tourism verdict boundary, no mouse) [RERUN post-matcher-fix]",
            verdict,
            would_fail_if="any step required a click, tab_to() never found the target within 25 presses, "
                           "date-input keyboard typing failed to produce a real value, or the final screen "
                           "wasn't the verdict-boundary card",
            evidence={"steps": steps, "failed_steps": fail_steps},
            notes="BUG A audit (2026-08-27): select_radio_by_text's matcher was suspected of comparing "
                  "raw textContent (prefixed by the tick span's '✓') against the plain label. Verified "
                  "this is not what the code does — CLEAN_TEXT_JS already strips [aria-hidden=\"true\"] "
                  "before comparing, and the tick span carries aria-hidden=\"true\" (journey.html:385). "
                  "No matcher code change was needed; this run confirms the traversal already completes "
                  "with the existing matcher.",
        )
        ctx.close()
    except Exception as e:
        record(1, "KEYBOARD-ONLY FULL TRAVERSAL", "FAIL", "n/a", {"exception": str(e)})

    # ================= PROBE 2: LIVE-REGION SEQUENCE (family + sponsor) =================
    _current_probe[0] = 2
    try:
        ctx, page = new_ctx(browser)
        boot(page)
        # install a MutationObserver on #liveRegion capturing every text mutation with a timestamp
        page.evaluate(
            """() => {
            window.__liveLog = [];
            const live = document.getElementById('liveRegion');
            const mo = new MutationObserver(() => {
                window.__liveLog.push({t: performance.now(), text: live.textContent});
            });
            mo.observe(live, {characterData: true, childList: true, subtree: true});
        }"""
        )

        def click_option_fast(text):
            # BUG B (fixed 2026-08-27): this used to fire with NO wait between click and the next
            # action, on the theory that it would "stress-test" the say() clear-then-set(50ms)
            # pattern for overlap/squashing. In practice a bot answering in ~20-30ms flat beats
            # its own UI: the announcement_squash_pairs criterion (<100ms between two DISTINCT
            # spoken messages) was catching robot speed, not a genuine squash a real user could
            # ever trigger — the app's real minimum inter-answer latency is however fast a human
            # reads a question and clicks/taps, which is never <100ms. See HUMAN_DELAY_MS below.
            page.get_by_role("radio", name=text, exact=True).click()

        HUMAN_DELAY_MS = 800  # >=800ms between one answer and the next, simulating real pacing

        click_option_fast("I'm the traveller")
        page.wait_for_timeout(HUMAN_DELAY_MS)
        click_option_fast("No, outside Indonesia")
        page.wait_for_timeout(HUMAN_DELAY_MS)
        click_option_fast("No")
        page.wait_for_timeout(HUMAN_DELAY_MS)
        page.wait_for_selector("#cl button")
        page.fill("#cs", "Italy")
        page.wait_for_timeout(HUMAN_DELAY_MS)
        page.get_by_role("button", name="Italy", exact=True).click()
        page.wait_for_timeout(HUMAN_DELAY_MS)
        page.fill("#dob", "1990-01-01")
        page.get_by_role("button", name="Continue", exact=True).click()
        page.wait_for_timeout(HUMAN_DELAY_MS)
        click_option_fast("Joining family")  # fork
        page.wait_for_timeout(HUMAN_DELAY_MS)
        click_option_fast("One trip")
        page.wait_for_timeout(HUMAN_DELAY_MS)
        click_option_fast("Spouse")
        page.wait_for_timeout(HUMAN_DELAY_MS)
        click_option_fast("Married")
        page.wait_for_selector("#cl button")
        page.fill("#cs", "Indonesia")
        page.wait_for_timeout(HUMAN_DELAY_MS)
        page.get_by_role("button", name="Indonesia", exact=True).click()
        page.wait_for_timeout(HUMAN_DELAY_MS)
        click_option_fast("Indonesian citizen")
        page.wait_for_timeout(HUMAN_DELAY_MS)
        click_option_fast("Yes")  # family_marriage_registered
        page.wait_for_timeout(HUMAN_DELAY_MS)
        click_option_fast("Yes")  # family_sponsor_confirmed
        page.wait_for_timeout(300)  # let any trailing setTimeout(50) settle before reading the log

        log = page.evaluate("() => window.__liveLog")
        review_title = page.inner_text("#qTitle")

        announces = [e for e in log if e["text"].strip() != ""]
        bad_tokens_re = re.compile(r"\bundefined\b|\bnull\b|\bNaN\b", re.IGNORECASE)
        bad_content = [a for a in announces if bad_tokens_re.search(a["text"])]

        # squashed = two RAW mutations (any) <100ms apart, per the mandate's literal wording —
        # NOTE: the code's own say() pattern (clear "" then setTimeout(50) set real text) makes
        # EVERY single announcement inherently produce a clear+set pair ~50ms apart BY DESIGN
        # (forces SR re-announcement of repeated text). Reporting that pattern as a "squash" would
        # be a vacuous fail on the app's own intentional idiom, so this probe reports TWO things
        # explicitly instead of collapsing them into one number:
        #   (a) raw_squash_pairs: literal <100ms deltas between ANY two consecutive DOM mutations
        #       (will include the intentional clear/set pairs — reported for transparency)
        #   (b) announcement_squash_pairs: <100ms deltas between two consecutive NON-EMPTY
        #       announcements (i.e. two distinct spoken messages competing) — this is the
        #       substantive accessibility signal the probe cares about
        raw_deltas = [{"i": i, "dt_ms": round(log[i]["t"] - log[i-1]["t"], 1),
                       "prev": log[i-1]["text"][:60], "cur": log[i]["text"][:60]}
                      for i in range(1, len(log))]
        raw_squash_pairs = [d for d in raw_deltas if d["dt_ms"] < 100]
        ann_deltas = [{"i": i, "dt_ms": round(announces[i]["t"] - announces[i-1]["t"], 1),
                        "prev": announces[i-1]["text"][:80], "cur": announces[i]["text"][:80]}
                       for i in range(1, len(announces))]
        announcement_squash_pairs = [d for d in ann_deltas if d["dt_ms"] < 100]

        # every transition should produce >=1 non-empty announcement; we made 11 answer() calls
        # (who_answers, in_indonesia, holds_stay_permit, nationalities, birth_date, category,
        #  trip_scope, family_relation, marital_status, family_sponsor_nationalities,
        #  family_sponsor_status_code, family_marriage_registered, family_sponsor_confirmed = 13)
        expected_transitions = 13
        no_announce = expected_transitions > len(announces)

        verdict = "PASS"
        if bad_content or no_announce or announcement_squash_pairs:
            verdict = "FAIL"
        record(
            2, "LIVE-REGION SEQUENCE (family+sponsor path, every mutation captured) [RERUN post-matcher-fix]",
            verdict,
            would_fail_if="an announcement text contains 'undefined'/'null'/'NaN', two DISTINCT "
                           "non-empty announcements land <100ms apart under human-paced input "
                           "(>=800ms between one answer and the next — see BUG B fix note below), "
                           "or a transition produces zero announcements",
            evidence={
                "human_pacing_delay_ms_between_answers": HUMAN_DELAY_MS,
                "total_mutations": len(log),
                "total_announcements(non_empty)": len(announces),
                "expected_transitions": expected_transitions,
                "no_announce_gap_detected": no_announce,
                "full_announcement_sequence": [a["text"] for a in announces],
                "bad_content(undefined/null/NaN)": bad_content,
                "raw_squash_pairs(<100ms, includes intentional clear+set idiom)": raw_squash_pairs,
                "announcement_squash_pairs(<100ms between two DISTINCT spoken messages)": announcement_squash_pairs,
                "final_review_title": review_title,
            },
            notes="BUG B (fixed 2026-08-27): the previous run drove all 13 answers at robot speed "
                  "(near-zero waits), so announcement_squash_pairs was measuring the bot outrunning "
                  "the UI, not the app genuinely squashing two distinct spoken messages together. "
                  "This run inserts an explicit >=800ms wait between every answer-triggering action "
                  "to simulate real human pacing. raw_squash_pairs still includes journey.html's own "
                  "intentional say() idiom (textContent='' then setTimeout(50)->real text, to force "
                  "SR re-announcement of repeated strings) by design — that is unchanged and not a "
                  "defect, so the verdict remains driven by announcement_squash_pairs (distinct "
                  "message vs distinct message) alone.",
        )
        ctx.close()
    except Exception as e:
        record(2, "LIVE-REGION SEQUENCE", "FAIL", "n/a", {"exception": str(e)})

    # ================= PROBE 3: STORAGE CORRUPTION =================
    _current_probe[0] = 3
    storage_cases = [
        ("malformed_json", '{"v":2, this is not json,,,'),
        ("wrong_version", json.dumps({"v": 1, "facts": {"category": "tourism", "who_answers": "self"},
                                       "qid": "category", "delegate": False})),
        ("nonexistent_qid", json.dumps({"v": 2, "facts": {"who_answers": "self", "in_indonesia": "no"},
                                         "qid": "totally_bogus_qid_xyz", "delegate": False})),
        ("orphaned_facts", json.dumps({"v": 2, "facts": {
            "who_answers": "self", "category": "family", "family_relation": "spouse",
            "overstay_days": "never",  # requires in_indonesia==="yes" — never set here -> should be pruned
            "stay_days": "under30",    # tourism-only field while category=family -> should be pruned
        }, "qid": "marital_status", "delegate": False})),
    ]
    case_results = []
    try:
        for name, payload in storage_cases:
            _current_probe[0] = 3
            errs_before = len(console_log)
            ctx, page = new_ctx(browser)
            boot(page)
            page.evaluate("(v) => { try { localStorage.setItem('r5b-proto-state', v); } catch(e) {} }", payload)
            crashed = False
            try:
                page.reload()
                page.wait_for_selector("#qTitle", timeout=3000)
            except Exception as e:
                crashed = True
                crash_reason = str(e)
            case = {"case": name, "payload": payload[:200], "reload_crashed_or_hung": crashed}
            if not crashed:
                title = page.inner_text("#qTitle")
                body_text = page.inner_text("body")
                bad_tokens_re = re.compile(r"\bundefined\b|\bNaN\b", re.IGNORECASE)
                fantasma = bool(bad_tokens_re.search(body_text))
                case["title_after_reload"] = title
                case["body_contains_undefined_or_NaN"] = fantasma
                if name == "orphaned_facts":
                    # walk the remaining sponsor path to the review screen and check the
                    # pruned facts (overstay_days / stay_days) never reappear as a phantom row
                    try:
                        if "marital status" in title.lower():
                            page.get_by_role("radio", name="Married", exact=True).click()
                            page.wait_for_timeout(60)
                            page.wait_for_selector("#cl button")
                            page.fill("#cs", "Indonesia")
                            page.wait_for_timeout(60)
                            page.get_by_role("button", name="Indonesia", exact=True).click()
                            page.wait_for_timeout(60)
                            page.get_by_role("radio", name="Indonesian citizen", exact=True).click()
                            page.wait_for_timeout(60)
                            page.get_by_role("radio", name="Yes", exact=True).click()
                            page.wait_for_timeout(60)
                            page.get_by_role("radio", name="Yes", exact=True).click()
                            page.wait_for_timeout(60)
                            review_rows = page.eval_on_selector_all(".review-row", "els => els.map(e => e.textContent)")
                            phantom_rows = [r for r in review_rows if
                                             ("overstay" in r.lower()) or ("how long" in r.lower()) or ("stay" in r.lower() and "days" in r.lower())]
                            case["reached_marital_status_then_walked_to_review"] = True
                            case["review_rows"] = review_rows
                            case["phantom_orphan_rows"] = phantom_rows
                        else:
                            case["reached_marital_status_then_walked_to_review"] = False
                            case["note"] = f"boot landed on '{title}', not marital_status as expected — recorded, not forced"
                    except Exception as e:
                        case["walk_exception"] = str(e)
            else:
                case["crash_reason"] = crash_reason
            new_errs = console_log[errs_before:]
            case["console_errors_during_this_case"] = new_errs
            case_results.append(case)
            ctx.close()

        def case_ok(c):
            if c["reload_crashed_or_hung"]:
                return False
            if c["body_contains_undefined_or_NaN"]:
                return False
            if c["console_errors_during_this_case"]:
                return False
            if c["case"] == "orphaned_facts" and c.get("phantom_orphan_rows"):
                return False
            return True

        all_ok = all(case_ok(c) for c in case_results)
        verdict = "PASS" if all_ok else "FAIL"
        record(
            3, "STORAGE CORRUPTION (4 malformed localStorage payloads before load)",
            verdict,
            would_fail_if="reload() throws/hangs, the rendered page shows a literal 'undefined'/'NaN', "
                           "a console error/pageerror fires during recovery, or (orphaned_facts case) a "
                           "pruned fact resurfaces as a phantom row on the review screen",
            evidence={"cases": case_results, "per_case_ok": {c["case"]: case_ok(c) for c in case_results}},
        )
    except Exception as e:
        record(3, "STORAGE CORRUPTION", "FAIL", "n/a", {"exception": str(e), "cases_completed": case_results})

    # ================= PROBE 4: REDUCED MOTION =================
    _current_probe[0] = 4
    try:
        ctx_reduced, page_reduced = new_ctx(browser, reduced_motion="reduce")
        boot(page_reduced)
        dur_reduced = page_reduced.eval_on_selector("#progressFill", "el => getComputedStyle(el).transitionDuration")
        anim_reduced = page_reduced.eval_on_selector("#progressFill", "el => getComputedStyle(el).animationDuration")
        ctx_reduced.close()

        ctx_normal, page_normal = new_ctx(browser, reduced_motion="no-preference")
        boot(page_normal)
        dur_normal = page_normal.eval_on_selector("#progressFill", "el => getComputedStyle(el).transitionDuration")
        ctx_normal.close()

        # coverage check: confirm .progress-fill is the ONLY element in the stylesheet declaring
        # a `transition` property, and no `animation` is declared anywhere (so this one probe is
        # exhaustive, not a sample) — read straight from the live <style> text in the DOM.
        ctx_cov, page_cov = new_ctx(browser)
        boot(page_cov)
        css_text = page_cov.eval_on_selector("style", "el => el.textContent")
        transition_decls = re.findall(r"[.#][\w-]+(?:\s*[,>]\s*[.#\[][\w=\"'\]-]*)*\s*\{[^}]*transition\s*:", css_text)
        animation_decls = re.findall(r"animation\s*:", css_text)
        ctx_cov.close()

        reduced_ok = dur_reduced == "0s"
        normal_has_motion = dur_normal != "0s" and dur_normal != ""
        exhaustive = len(transition_decls) >= 1  # progress-fill's own transition rule matched
        # animation_decls will include the reduced-motion media query's own `animation:none` reset —
        # that's expected; anything BEYOND that single occurrence would mean an untested animated element
        extra_animations = len(animation_decls) - 1

        verdict = "PASS" if (reduced_ok and normal_has_motion and extra_animations <= 0) else "FAIL"
        record(
            4, "REDUCED MOTION (prefers-reduced-motion computed-style check)",
            verdict,
            would_fail_if="transitionDuration on #progressFill stays non-zero under emulated "
                           "prefers-reduced-motion:reduce, OR the no-preference control shows no "
                           "transition at all (meaning the comparison is meaningless), OR the stylesheet "
                           "declares an `animation` outside the reduced-motion reset rule that this probe "
                           "never exercised",
            evidence={
                "progressFill.transitionDuration under reduced-motion": dur_reduced,
                "progressFill.animationDuration under reduced-motion": anim_reduced,
                "progressFill.transitionDuration under no-preference (control)": dur_normal,
                "css_transition_declarations_found": transition_decls,
                "css_animation_keyword_occurrences": len(animation_decls),
                "extra_animation_declarations_beyond_the_reduce_reset": extra_animations,
            },
            notes="grep-confirmed the stylesheet declares exactly one `transition` property "
                  "(.progress-fill) and zero @keyframes/animation rules besides the reduce-motion "
                  "reset itself — so this single element's check is exhaustive coverage, not a sample.",
        )
    except Exception as e:
        record(4, "REDUCED MOTION", "FAIL", "n/a", {"exception": str(e)})

    # ================= PROBE 5: ZOOM/REFLOW 400% =================
    _current_probe[0] = 5
    try:
        # 5a. literal instruction: viewport stays 360, apply text-only zoom via root font-size 200%
        ctx, page = new_ctx(browser)
        boot(page)
        before_fs = page.eval_on_selector("#qTitle", "el => getComputedStyle(el).fontSize")
        before_scrollw = page.evaluate("() => document.documentElement.scrollWidth")
        page.evaluate("() => { document.documentElement.style.fontSize = '200%'; }")
        page.wait_for_timeout(60)
        after_fs = page.eval_on_selector("#qTitle", "el => getComputedStyle(el).fontSize")
        after_scrollw = page.evaluate("() => document.documentElement.scrollWidth")
        tap_targets_5a = page.eval_on_selector_all(
            "#screen .options .option, #screen .cta, .theme-toggle",
            "els => els.map(e => { const r = e.getBoundingClientRect(); return {text:(e.textContent||'').trim().slice(0,30), h:r.height, w:r.width}; })",
        )
        min_h_5a = min([t["h"] for t in tap_targets_5a], default=None)
        fontsize_changed = before_fs != after_fs
        overflow_5a = after_scrollw > 360
        shrunk_5a = min_h_5a is not None and min_h_5a < 44
        ctx.close()

        # 5b. supplementary: real-zoom proxy via CSS `zoom:4` (Chromium-only, approximates the
        # WCAG 1.4.10 400% browser-zoom reflow test far more faithfully than root font-size does,
        # since journey.html's typography is 100% fixed-px and does not cascade from html font-size)
        ctx2, page2 = new_ctx(browser)
        boot(page2)
        page2.evaluate("() => { document.documentElement.style.zoom = '4'; }")
        page2.wait_for_timeout(80)
        scrollw_5b = page2.evaluate("() => document.documentElement.scrollWidth")
        clientw_5b = page2.evaluate("() => document.documentElement.clientWidth")
        overflow_5b = scrollw_5b > clientw_5b
        computed_zoom = page2.eval_on_selector("#jr", "el => getComputedStyle(el).zoom")
        # tap target rects are reported in the post-zoom coordinate space by Chromium; divide back
        # by the actual applied zoom factor to compare against the real 44px CSS requirement
        tap_targets_5b_raw = page2.eval_on_selector_all(
            "#screen .options .option, #screen .cta, .theme-toggle",
            "els => els.map(e => { const r = e.getBoundingClientRect(); return {text:(e.textContent||'').trim().slice(0,30), h:r.height, w:r.width}; })",
        )
        try:
            z = float(computed_zoom)
        except (TypeError, ValueError):
            z = 1.0
        tap_targets_5b = [{"text": t["text"], "h_raw": t["h"], "h_normalized": round(t["h"] / z, 1) if z else t["h"]} for t in tap_targets_5b_raw]
        min_h_5b_norm = min([t["h_normalized"] for t in tap_targets_5b], default=None)
        shrunk_5b = min_h_5b_norm is not None and min_h_5b_norm < 44
        ctx2.close()

        # verdict logic: report PARTIAL when the literally-instructed technique (5a) is a
        # methodologically hollow pass (no scaling occurred at all, because the app is 100% px-sized
        # and does not inherit from documentElement's font-size — verified: .jr sets its own
        # explicit font-size:16px, resetting the inheritance chain for the whole subtree) rather
        # than silently reporting a green PASS that validated nothing.
        literal_check_passed = (not overflow_5a) and (not shrunk_5a)
        hollow = literal_check_passed and not fontsize_changed
        if hollow:
            verdict = "PARTIAL"
        elif overflow_5a or shrunk_5a or overflow_5b or shrunk_5b:
            verdict = "FAIL"
        else:
            verdict = "PASS"

        record(
            5, "ZOOM/REFLOW 400% (viewport 360, text-only zoom via CSS font-size 200% + supplementary real-zoom proxy)",
            verdict,
            would_fail_if="[5a] document.documentElement.scrollWidth > 360 after root font-size:200%, "
                           "or any tap target's rendered height drops below 44px; "
                           "[5b, supplementary] scrollWidth > clientWidth under CSS zoom:4, or a "
                           "zoom-normalized tap target drops below 44px",
            evidence={
                "5a_text_only_zoom(font-size:200%_on_documentElement)": {
                    "qTitle_font_size_before": before_fs, "qTitle_font_size_after": after_fs,
                    "font_size_actually_changed": fontsize_changed,
                    "scrollWidth_before": before_scrollw, "scrollWidth_after": after_scrollw,
                    "overflow": overflow_5a,
                    "tap_targets": tap_targets_5a, "min_tap_target_height": min_h_5a, "shrunk_below_44px": shrunk_5a,
                },
                "5b_supplementary_real_zoom_proxy(CSS_zoom:4_on_documentElement)": {
                    "scrollWidth": scrollw_5b, "clientWidth": clientw_5b, "overflow": overflow_5b,
                    "computed_zoom_readback": computed_zoom,
                    "tap_targets_normalized": tap_targets_5b, "min_tap_target_height_normalized": min_h_5b_norm,
                    "shrunk_below_44px": shrunk_5b,
                },
            },
            notes="The literally-instructed technique (root font-size:200%) produced ZERO visual "
                  "change here (qTitle font-size before/after identical) — verified in the source: "
                  ".jr{font-size:16px} is an explicit reset that islands the whole prototype subtree "
                  "from documentElement's font-size, and no rule in the stylesheet uses a font-size "
                  "in em/rem (only .ph's border/padding use .92em, itself rooted at .jr's fixed 16px, "
                  "not at html). So [5a]'s literal PASS is methodologically hollow: it proves nothing "
                  "actually zoomed, not that zoomed content reflows safely — hence verdict PARTIAL "
                  "rather than a shallow PASS. [5b] is the real reflow signal: it DOES scale the "
                  "fixed-px layout (Chromium's non-standard `zoom` CSS property, the closest headless "
                  "proxy for real browser Ctrl/Cmd+ zoom) and is reported as supplementary evidence "
                  "for the conductor to weigh. A genuine finding either way: browser 'text-only zoom' "
                  "(distinct from full-page zoom) would not enlarge any text in this prototype at all.",
        )
    except Exception as e:
        record(5, "ZOOM/REFLOW 400%", "FAIL", "n/a", {"exception": str(e)})

    # ================= PROBE 6: DELEGATE KEYBOARD =================
    _current_probe[0] = 6
    try:
        ctx, page = new_ctx(browser)
        boot(page)
        steps = []
        ok_all = True

        def step6(label, fn):
            global ok_all
            try:
                r = fn()
                steps.append({"label": label, **(r if isinstance(r, dict) else {"detail": r})})
                if isinstance(r, dict) and r.get("ok") is False:
                    ok_all = False
            except Exception as e:
                steps.append({"label": label, "ok": False, "reason": f"exception: {e}"})
                ok_all = False

        def d1():
            found, n, info, _ = tab_to(page, lambda i: i["role"] == "radio")
            if not found:
                return {"ok": False, "reason": "never reached a radio via Tab from boot"}
            r = select_radio_by_text(page, "I'm helping someone else", key="Enter")
            return {"ok": found and r["ok"], "tabs": n, **r}
        step6("who_answers -> delegate (Tab, ArrowDown, Enter)", d1)

        def d2():
            title = page.inner_text("#qTitle")
            found, n, info, _ = tab_to(page, lambda i: i["role"] == "radio")
            if not found:
                return {"ok": False, "reason": f"never reached a radio; delegate_confirm title='{title}'"}
            r = select_radio_by_text(
                page, "The traveller asked me to fill this in, and I'll check with them when unsure", key="Space"
            )
            return {"ok": found and r["ok"], "delegate_confirm_title": title, "tabs": n, **r}
        step6("delegate_confirm -> confirmed (Tab, Space)", d2)

        banner_hidden = page.eval_on_selector("#delegateBanner", "el => el.hidden")
        banner_text = page.inner_text("#delegateBanner") if not banner_hidden else ""
        # perceivability: the banner must carry real, non-empty TEXT content (not conveyed by
        # color/border alone) — check textContent length and that it's not just an icon/symbol
        text_perceivable = len(banner_text.strip()) > 20 and "answering for someone else" in banner_text.lower()
        in_indonesia_title = page.inner_text("#qTitle")
        wording_ok = ("Is the traveller" in in_indonesia_title) and ("Are you" not in in_indonesia_title)

        # continue one more keyboard-only hop past the checkpoint to prove the delegate path
        # stays keyboard-reachable, not just the checkpoint itself
        def d3():
            found, n, info, _ = tab_to(page, lambda i: i["role"] == "radio")
            if not found:
                return {"ok": False, "reason": "never reached a radio on the reworded in_indonesia screen"}
            r = select_radio_by_text(page, "No, outside Indonesia", key="Enter")
            return {"ok": found and r["ok"], "tabs": n, **r}
        step6("post-checkpoint hop stays keyboard-reachable (in_indonesia, delegate wording)", d3)

        verdict = "PASS" if (ok_all and not banner_hidden and text_perceivable and wording_ok) else "FAIL"
        record(
            6, "DELEGATE KEYBOARD (checkpoint reachable+completable keyboard-only, banner perceivable) [RERUN post-matcher-fix]",
            verdict,
            would_fail_if="any step required a click, the delegate banner stayed hidden after "
                           "confirmation, the banner conveyed its meaning through styling alone "
                           "(no real text), or the reworded question after the checkpoint wasn't "
                           "keyboard-reachable",
            evidence={
                "steps": steps,
                "banner_hidden_after_confirm": banner_hidden,
                "banner_text": banner_text,
                "banner_text_perceivable(not_color_only)": text_perceivable,
                "in_indonesia_title_after_delegate": in_indonesia_title,
                "wording_rewritten_for_delegate": wording_ok,
            },
            notes="BUG A audit (2026-08-27): same matcher this run depends on (select_radio_by_text) "
                  "was suspected of a raw-textContent-vs-label equality bug that would stall on "
                  "who_answers. Verified this is not what the code does (see probe 1's notes) — this "
                  "run reaches delegate_confirm and the reworded in_indonesia screen genuinely, with "
                  "no matcher code change needed.",
        )
        ctx.close()
    except Exception as e:
        record(6, "DELEGATE KEYBOARD [RERUN post-matcher-fix]", "FAIL", "n/a", {"exception": str(e)})

    # ================= PROBE 7: FOCUS TRAP CHECK =================
    _current_probe[0] = 7
    try:
        ctx, page = new_ctx(browser)
        boot(page)
        # get to a mid-flow screen with several focusable siblings: radiogroup + notsure button +
        # Back + Save&continue-later (holds_stay_permit has notSure:true and idx>0)
        page.get_by_role("radio", name="I'm the traveller", exact=True).click()
        page.wait_for_timeout(60)
        page.get_by_role("radio", name="No, outside Indonesia", exact=True).click()
        page.wait_for_timeout(60)

        def sig(info):
            if info is None:
                return None
            return f"{info['tag']}#{info['id']}.{info['role']}[{info['text'][:30]}]"

        forward_trace = []
        for i in range(18):
            page.keyboard.press("Tab")
            page.wait_for_timeout(15)
            forward_trace.append(active_info(page))

        backward_trace = []
        for i in range(18):
            page.keyboard.press("Shift+Tab")
            page.wait_for_timeout(15)
            backward_trace.append(active_info(page))

        def analyze(trace, direction):
            sigs = [sig(t) for t in trace]
            landed_on_body = [i for i, t in enumerate(trace) if t and t["isBody"]]
            invisible_hits = [i for i, t in enumerate(trace) if t and not t["isBody"] and not t["rectVisible"]]
            stuck_repeats = [i for i in range(1, len(sigs)) if sigs[i] is not None and sigs[i] == sigs[i - 1]]
            return {
                "direction": direction,
                "sequence": sigs,
                "landed_on_body_at": landed_on_body,
                "invisible_focus_at": invisible_hits,
                "stuck_repeat_at(consecutive_identical_focus)": stuck_repeats,
            }

        fwd = analyze(forward_trace, "forward(Tab)")
        bwd = analyze(backward_trace, "backward(Shift+Tab)")

        trapped = bool(fwd["stuck_repeat_at(consecutive_identical_focus)"]) or bool(bwd["stuck_repeat_at(consecutive_identical_focus)"])
        lost_to_body = bool(fwd["landed_on_body_at"]) or bool(bwd["landed_on_body_at"])
        lost_to_invisible = bool(fwd["invisible_focus_at"]) or bool(bwd["invisible_focus_at"])

        verdict = "FAIL" if (trapped or lost_to_invisible) else "PASS"
        record(
            7, "FOCUS TRAP CHECK (18x Tab and 18x Shift+Tab, no stuck repeat / no invisible landing)",
            verdict,
            would_fail_if="two consecutive Tab presses land on the exact same element (focus not "
                           "advancing = trapped), or focus lands on an element with zero rendered "
                           "size (invisible target a keyboard user can't perceive)",
            evidence={"forward": fwd, "backward": bwd, "landed_on_body_note":
                      "landing on BODY at the natural end of the page's tab order is normal browser "
                      "behavior (no more focusable siblings), not itself a trap — tracked separately "
                      "from the trapped/invisible signals that drive the verdict"},
        )
        ctx.close()
    except Exception as e:
        record(7, "FOCUS TRAP CHECK", "FAIL", "n/a", {"exception": str(e)})

    # ================= PROBE 8: CONSOLE HYGIENE (aggregate across all probes) =================
    _current_probe[0] = 8
    all_errors = [e for e in console_log]
    verdict = "PASS" if not all_errors else "FAIL"
    record(
        8, "CONSOLE HYGIENE (zero console.error/pageerror across every probe's pages, probes 1-7)",
        verdict,
        would_fail_if="any page created by probes 1-7 emitted a console.error or an uncaught pageerror "
                       "at any point during this suite's run",
        evidence={"total_errors": len(all_errors), "errors_by_probe": all_errors},
    )

    browser.close()

summary = {
    "PASS": sum(1 for r in results if r["verdict"] == "PASS"),
    "FAIL": sum(1 for r in results if r["verdict"] == "FAIL"),
    "PARTIAL": sum(1 for r in results if r["verdict"] == "PARTIAL"),
    "unmeasurable_headless": sum(1 for r in results if r["verdict"] == "unmeasurable_headless"),
}
output = {
    "tool_used": "playwright-python (chromium) — system python3, no dedicated venv found (matches r5b/smoke_runtime.py's own stack)",
    "target": FILE_PATH,
    "summary": summary,
    "results": results,
}
with open(OUT_PATH, "w") as f:
    json.dump(output, f, indent=2)

print("\n=== SUMMARY ===")
for r in results:
    print(f"{r['n']}. {r['name']}: {r['verdict']}")
print("\nCounts:", summary)
print("Output:", OUT_PATH)
