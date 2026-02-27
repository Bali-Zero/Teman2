"""
Record a 2-minute demo video of Bali Zero PRIME dashboard in 9:16 (vertical/reel).
Flow: Indonesian → Nusa Dua coords → Analisis Lahan → KBLI 55203 → Analisi Investimento
Usage: python3 record_prime_demo.py
Output: ~/Desktop/balizero_prime_demo_9x16.webm
"""
import time
import glob
import os
import shutil
from playwright.sync_api import sync_playwright

OUTPUT = "/Users/nuzantara/Desktop/balizero_prime_demo_9x16.webm"
URL = "http://localhost:8501"

# 9:16 vertical format — mobile/reel style
VW = 1080
VH = 1920


def wait(s: float):
    time.sleep(s)


def set_number_input(page, label_text: str, value: str):
    """Set a Streamlit number_input by finding its label, then editing the input."""
    label = page.locator(f"label:has-text('{label_text}')")
    if label.count() == 0:
        print(f"  WARNING: label '{label_text}' not found")
        return False
    container = label.locator("..").locator("..")
    inp = container.locator("input")
    if inp.count() == 0:
        print(f"  WARNING: input for '{label_text}' not found")
        return False
    inp.click(click_count=3)
    wait(0.2)
    page.keyboard.type(value, delay=50)
    page.keyboard.press("Enter")
    wait(0.5)
    return True


# Clean old recordings
shutil.rmtree("/tmp/pw_video_prime", ignore_errors=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": VW, "height": VH},
        record_video_dir="/tmp/pw_video_prime",
        record_video_size={"width": VW, "height": VH},
    )
    page = context.new_page()

    # ═══════════════════════════════════════════════════
    # SCENE 1: Open dashboard (5s)
    # ═══════════════════════════════════════════════════
    print("[1/8] Opening PRIME...")
    page.goto(URL, wait_until="load", timeout=30000)
    wait(4)

    # ═══════════════════════════════════════════════════
    # Collapse sidebar for vertical format
    # ═══════════════════════════════════════════════════
    print("  Collapsing sidebar...")
    try:
        collapse_btn = page.locator("[data-testid='stSidebarCollapseButton'], button[aria-label='Close sidebar']")
        if collapse_btn.count() > 0:
            collapse_btn.first.click()
            wait(1)
            print("  Sidebar collapsed")
    except Exception as e:
        print(f"  Sidebar collapse: {e}")

    # ═══════════════════════════════════════════════════
    # SCENE 2: Switch to Indonesian (8s)
    # The language selectbox is in the sidebar — need to
    # open sidebar, switch, then close again
    # ═══════════════════════════════════════════════════
    print("[2/8] Switching to Indonesian...")
    try:
        # Re-open sidebar to access language selector
        expand_btn = page.locator("[data-testid='stSidebarCollapsedControl'] button, button[aria-label='Open sidebar']")
        if expand_btn.count() > 0:
            expand_btn.first.click()
            wait(1)

        lang_box = page.locator("[data-testid='stSelectbox']").first
        lang_box.click()
        wait(0.5)
        page.locator("[data-testid='stSelectboxVirtualDropdown'] li:has-text('Indonesia')").click()
        wait(3)
        print("  Language set to Indonesia")

        # Collapse sidebar again
        collapse_btn = page.locator("[data-testid='stSidebarCollapseButton'], button[aria-label='Close sidebar']")
        if collapse_btn.count() > 0:
            collapse_btn.first.click()
            wait(1)
    except Exception as e:
        print(f"  Lang: {e}")

    page.screenshot(path="/tmp/pw_prime_v_s2.png")
    wait(2)

    # ═══════════════════════════════════════════════════
    # SCENE 3: Set Nusa Dua coordinates (12s)
    # Try both Indonesian and Italian label names
    # ═══════════════════════════════════════════════════
    print("[3/8] Setting Nusa Dua coordinates...")

    # Try Indonesian first, then Italian fallback
    lat_labels = ["Lintang", "Latitudine"]
    lon_labels = ["Bujur", "Longitudine"]

    lat_set = False
    for lbl in lat_labels:
        if set_number_input(page, lbl, "-8.800000"):
            print(f"  Lat set via label '{lbl}'")
            lat_set = True
            break
    if not lat_set:
        print("  FALLBACK: Setting lat via direct input")
        lat_inputs = page.locator("input[type='number']").all()
        if len(lat_inputs) >= 1:
            lat_inputs[0].click(click_count=3)
            wait(0.2)
            page.keyboard.type("-8.800000", delay=50)
            page.keyboard.press("Enter")
            wait(0.5)

    wait(1)

    lon_set = False
    for lbl in lon_labels:
        if set_number_input(page, lbl, "115.223000"):
            print(f"  Lon set via label '{lbl}'")
            lon_set = True
            break
    if not lon_set:
        print("  FALLBACK: Setting lon via direct input")
        lon_inputs = page.locator("input[type='number']").all()
        if len(lon_inputs) >= 2:
            lon_inputs[1].click(click_count=3)
            wait(0.2)
            page.keyboard.type("115.223000", delay=50)
            page.keyboard.press("Enter")
            wait(0.5)

    wait(3)
    page.screenshot(path="/tmp/pw_prime_v_s3.png")

    # ═══════════════════════════════════════════════════
    # SCENE 4: Click ANALISIS LAHAN / ANALIZZA TERRENO (20s)
    # ═══════════════════════════════════════════════════
    print("[4/8] Clicking analysis button...")
    try:
        # Try multiple button labels (Indonesian, Italian, English)
        btn = page.locator("button:has-text('ANALISIS LAHAN'), button:has-text('ANALIZZA TERRENO'), button:has-text('ANALYZE LAND')")
        if btn.count() == 0:
            # Broader fallback — any red/primary button with analysis text
            btn = page.locator("button").filter(has_text="ANALI")
        btn.first.scroll_into_view_if_needed()
        wait(0.5)
        btn.first.click()
        print(f"  Clicked analysis button: {btn.first.inner_text()[:30]}")
    except Exception as e:
        print(f"  Button: {e}")

    # Wait for BATARA API response + Streamlit rerun
    print("  Waiting for BATARA response...")
    wait(20)

    page.screenshot(path="/tmp/pw_prime_v_s4.png")

    # ═══════════════════════════════════════════════════
    # SCENE 5: Scroll to show zone results + map (18s)
    # In vertical mode, content stacks — more scrolling needed
    # ═══════════════════════════════════════════════════
    print("[5/8] Showing zone results...")
    for _ in range(4):
        page.mouse.wheel(0, 500)
        wait(3)
    wait(2)

    page.screenshot(path="/tmp/pw_prime_v_s5.png")

    # ═══════════════════════════════════════════════════
    # SCENE 6: Enter KBLI 55203 (15s)
    # ═══════════════════════════════════════════════════
    print("[6/8] Entering KBLI code 55203...")
    try:
        # Try the specific KBLI input first
        kbli_input = page.locator("input[aria-label='kbli_compliance_input']")
        if kbli_input.count() == 0:
            # Look for text inputs that are NOT the search bar
            # The KBLI input typically appears after analysis results
            all_text_inputs = page.locator("input[type='text']").all()
            print(f"  Found {len(all_text_inputs)} text inputs")
            # Use the last one (KBLI is after search bar)
            if len(all_text_inputs) > 1:
                kbli_input = all_text_inputs[-1]
            elif len(all_text_inputs) == 1:
                kbli_input = all_text_inputs[0]

        if hasattr(kbli_input, 'count'):
            if kbli_input.count() > 0:
                kbli_input = kbli_input.first
            else:
                raise Exception("KBLI input not found")

        kbli_input.scroll_into_view_if_needed()
        wait(0.5)
        kbli_input.click()
        wait(0.3)
        for ch in "55203":
            page.keyboard.type(ch, delay=200)
        wait(2)
        print("  Typed: 55203")
    except Exception as e:
        print(f"  KBLI input: {e}")

    page.screenshot(path="/tmp/pw_prime_v_s6a.png")

    # Click Cek Kepatuhan / Verifica Conformita
    try:
        verify_btn = page.locator("button:has-text('Cek'), button:has-text('Verif'), button:has-text('compliance'), button:has-text('Conformit')")
        if verify_btn.count() > 0:
            verify_btn.first.scroll_into_view_if_needed()
            wait(0.3)
            verify_btn.first.click()
            print(f"  Clicked verify: {verify_btn.first.inner_text()[:30]}")
            wait(8)
    except Exception as e:
        print(f"  Verify btn: {e}")

    # Scroll to see KBLI result
    page.mouse.wheel(0, 500)
    wait(4)

    page.screenshot(path="/tmp/pw_prime_v_s6b.png")

    # ═══════════════════════════════════════════════════
    # SCENE 7: Full Investment Analysis (30s)
    # ═══════════════════════════════════════════════════
    print("[7/8] Running investment analysis...")
    try:
        invest_btn = page.locator(
            "button:has-text('Analisa Investasi'), "
            "button:has-text('Analisi Investimento'), "
            "button:has-text('Investment Analysis'), "
            "button:has-text('Analisis Investasi')"
        )
        if invest_btn.count() == 0:
            # Broader search
            all_btns = page.locator("button").all()
            for b in all_btns:
                try:
                    t = b.inner_text().lower()
                    if "invest" in t or "analisa" in t or "analisi" in t:
                        invest_btn = b
                        print(f"  Found invest button: {t[:40]}")
                        break
                except Exception:
                    continue

        if hasattr(invest_btn, 'count') and invest_btn.count() > 0:
            invest_btn.first.scroll_into_view_if_needed()
            wait(0.5)
            invest_btn.first.click()
        elif hasattr(invest_btn, 'scroll_into_view_if_needed'):
            invest_btn.scroll_into_view_if_needed()
            wait(0.5)
            invest_btn.click()
        else:
            print("  WARNING: invest button not found at all")
        print("  Clicked Investment Analysis")
    except Exception as e:
        print(f"  Invest btn: {e}")

    # Wait for analysis
    wait(22)

    page.screenshot(path="/tmp/pw_prime_v_s7a.png")

    # ═══════════════════════════════════════════════════
    # SCENE 8: Scroll through results slowly (25s)
    # ═══════════════════════════════════════════════════
    print("[8/8] Scrolling through results...")
    for i in range(8):
        page.mouse.wheel(0, 400)
        wait(3)

    page.screenshot(path="/tmp/pw_prime_v_s8.png")

    # Final hold
    wait(3)

    # ═══════════════════════════════════════════════════
    # Save video
    # ═══════════════════════════════════════════════════
    print("\nSaving video...")
    page.close()
    context.close()
    browser.close()

    videos = glob.glob("/tmp/pw_video_prime/*.webm")
    if videos:
        latest = max(videos, key=lambda f: os.path.getmtime(f))
        shutil.move(latest, OUTPUT)
        size_mb = os.path.getsize(OUTPUT) / 1024 / 1024
        print(f"Video saved: {OUTPUT} ({size_mb:.1f} MB)")
    else:
        print("ERROR: No video file found!")
