#!/usr/bin/env python3
"""
Post-publish poller v3 — Resilient unified pipeline with step tracking.

Runs every 5 minutes via LaunchAgent (com.balizero.post-publish-poller).
Reads from PostgreSQL-backed queue on backend, processes each article:
  - SEO/GEO metadata optimization (Gemini CLI)
  - Translation to 4 languages (Ollama local)
  - Cover image generation (bz_image_style + Fireworks Flux Dev)
  - Git commit + push

Resilience features:
  - Step tracking: completed_steps JSONB — only re-runs failed steps on retry
  - Max 5 attempts: after that, item moves to 'dead' status
  - Telegram alert on failure (after 2+ attempts)
  - SEO prompt via stdin (not CLI arg) to avoid timeout on long articles

Sources:
  - 'intel': MDX articles from intel scraper (full pipeline: SEO + translate + image)
  - 'news':  news_items from /api/news (image generation only)
"""
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
_venv = SCRIPT_DIR.parent / ".venv" / "bin" / "python3"
VENV_PYTHON = _venv if _venv.exists() else SCRIPT_DIR.parent / "venv" / "bin" / "python3"
LOG_DIR = Path.home() / ".openclaw" / "workspace" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"post_publish_poller_{datetime.now().strftime('%Y%m%d')}.log"

BACKEND_URL = os.environ.get("BACKEND_URL", "https://nuzantara-rag.fly.dev")
API_KEY = os.environ.get("SCRAPER_API_KEY", "internal-scraper-key")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")

GITHUB_OWNER = "Balizero1987"
GITHUB_REPO = "Teman2"
IMAGE_GH_DIR = "apps/mouth/public/static/news"


def log(msg: str):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def api_get(path: str) -> dict:
    req = urllib.request.Request(
        f"{BACKEND_URL}{path}",
        headers={"X-API-Key": API_KEY},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def api_post(path: str, data: dict) -> dict:
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{BACKEND_URL}{path}",
        data=body,
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def mark_step_done(slug: str, step: str):
    """Report a completed step to the backend."""
    try:
        api_post("/api/intel/post-publish-queue/step-done", {"slug": slug, "step": step})
    except Exception as e:
        log(f"  ⚠ Failed to mark step '{step}' done: {e}")


def send_telegram_alert(message: str):
    """Send alert to Telegram owner chat."""
    if not TELEGRAM_BOT_TOKEN:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass  # Alert failure is not critical


def wait_for_ollama_free(max_wait: int = 60 * 15) -> bool:
    """Wait until no other translate_articles.py is running (max 15 min)."""
    import time
    waited = 0
    while waited < max_wait:
        check = subprocess.run(["pgrep", "-f", "translate_articles.py"], capture_output=True, text=True)
        if check.returncode != 0:
            return True
        log(f"⏳ Ollama busy — waiting 60s...")
        time.sleep(60)
        waited += 60
    log("⚠ Timeout waiting for Ollama")
    return False


# ─── SEO/GEO ──────────────────────────────────────────────────────────────────

def run_seo(slug: str, category: str) -> bool:
    """Optimize SEO/GEO metadata of published MDX via Gemini. Uses stdin for prompt."""
    import base64
    import re

    ARTICLES_PATH = "apps/mouth/src/content/articles"
    mdx_path = f"{ARTICLES_PATH}/{category}/{slug}.mdx"

    log(f"  ▶ SEO/GEO for {slug}")

    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{mdx_path}"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            log("  ⏭ SEO: MDX not on GitHub — skip")
            return True
        data = json.loads(result.stdout)
        content = base64.b64decode(data["content"]).decode("utf-8")
        sha = data.get("sha", "")
    except Exception as e:
        log(f"  ⚠ SEO: GitHub read error: {e}")
        return False

    match = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
    if not match:
        log("  ⏭ SEO: no frontmatter — skip")
        return True

    fm_raw = match.group(1)
    body = match.group(2)

    # Already optimized?
    if "answerSnippet" in fm_raw and "Check article for specific dates" not in fm_raw:
        if "mean for expats in Bali?" not in fm_raw:
            log("  ⏭ SEO already optimized")
            return True

    title_match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', fm_raw, re.MULTILINE)
    title = title_match.group(1) if title_match else slug

    prompt = f"""You are an expert SEO and AI Search Optimization (GEO/AEO) specialist for Bali Zero, an immigration and business setup agency in Bali.

Analyze this article and return ONLY a JSON object with optimized metadata. No explanations, no markdown, just the JSON.

Article title: {title}
Category: {category}
Article body (first 2000 chars):
{body[:2000]}

Return this exact JSON structure:
{{
  "seoTitle": "<60 chars, keyword-first, include year 2026 if relevant>",
  "seoDescription": "<150-155 chars, include primary keyword + action>",
  "aiOptimization": {{
    "answerSnippet": "<2 clear declarative sentences answering the article's main question. Factual and specific.>",
    "primaryQuestion": "<The main question this article answers, phrased as users would search it>",
    "entityMentions": ["<key entity 1>", "<key entity 2>", "<key entity 3>"]
  }}
}}"""

    # Use stdin instead of -p arg to avoid shell/timeout issues on long prompts
    try:
        result = subprocess.run(
            ["gemini", "-m", "gemini-2.5-pro"],
            input=prompt, capture_output=True, text=True, timeout=90,
        )
        if result.returncode != 0 or not result.stdout.strip():
            # Fallback to default model
            result = subprocess.run(
                ["gemini"],
                input=prompt, capture_output=True, text=True, timeout=90,
            )
    except subprocess.TimeoutExpired:
        log("  ⚠ SEO: Gemini timeout (90s)")
        return False
    except Exception as e:
        log(f"  ⚠ SEO: Gemini error: {e}")
        return False

    raw = result.stdout.strip()
    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not json_match:
        log("  ⚠ SEO: no JSON in Gemini response")
        return False

    try:
        seo = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        log("  ⚠ SEO: invalid JSON from Gemini")
        return False

    def set_fm_field(fm: str, key: str, value: str) -> str:
        value_escaped = value.replace('"', '\\"')
        pattern = rf'^{re.escape(key)}:.*$'
        replacement = f'{key}: "{value_escaped}"'
        new_fm = re.sub(pattern, replacement, fm, flags=re.MULTILINE)
        if new_fm == fm:
            new_fm = fm + f'\n{key}: "{value_escaped}"'
        return new_fm

    ai_opt = seo.get("aiOptimization", {})
    fm_raw = set_fm_field(fm_raw, "seoTitle", seo.get("seoTitle", ""))
    fm_raw = set_fm_field(fm_raw, "seoDescription", seo.get("seoDescription", ""))

    if ai_opt.get("answerSnippet"):
        answer = ai_opt["answerSnippet"].replace('"', '\\"')
        fm_raw = re.sub(r'(answerSnippet:\s*)["\']?.*?["\']?\s*$', f'\\1"{answer}"', fm_raw, flags=re.MULTILINE)
    if ai_opt.get("primaryQuestion"):
        question = ai_opt["primaryQuestion"].replace('"', '\\"')
        fm_raw = re.sub(r'(primaryQuestion:\s*)["\']?.*?["\']?\s*$', f'\\1"{question}"', fm_raw, flags=re.MULTILINE)

    new_content = f"---\n{fm_raw}\n---\n{body}"

    encoded = __import__("base64").b64encode(new_content.encode("utf-8")).decode("utf-8")
    payload = {"message": f"feat(seo): optimize GEO/AEO metadata for '{title[:50]}'", "content": encoded, "sha": sha}
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{mdx_path}", "--method", "PUT", "--input", "-"],
            input=json.dumps(payload), capture_output=True, text=True, timeout=30,
        )
        ok = result.returncode == 0
        log(f"  {'✅' if ok else '❌'} SEO/GEO metadata updated")
        return ok
    except Exception as e:
        log(f"  ⚠ SEO commit error: {e}")
        return False


# ─── TRANSLATION ───────────────────────────────────────────────────────────────

def run_translate(slug: str, category: str) -> bool:
    wait_for_ollama_free()
    translate_script = SCRIPT_DIR.parent.parent.parent / "scripts" / "translate-articles.py"
    log(f"  ▶ Translating {slug} (4 langs)")

    # Ensure the MDX file exists locally before translating.
    # The news-room pushes to GitHub but the local repo may lag behind.
    repo_root = SCRIPT_DIR.parent.parent.parent
    mdx_local = repo_root / "apps" / "mouth" / "src" / "content" / "articles" / category / f"{slug}.mdx"
    if not mdx_local.exists():
        log(f"  ⚠ MDX not found locally — pulling from GitHub")
        try:
            import base64 as _b64
            gh_result = subprocess.run(
                ["gh", "api", f"repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/apps/mouth/src/content/articles/{category}/{slug}.mdx"],
                capture_output=True, text=True, timeout=30,
            )
            if gh_result.returncode == 0:
                import json as _json
                data = _json.loads(gh_result.stdout)
                content = _b64.b64decode(data["content"]).decode("utf-8")
                mdx_local.parent.mkdir(parents=True, exist_ok=True)
                mdx_local.write_text(content, encoding="utf-8")
                log(f"  ✅ MDX pulled from GitHub ({len(content)} chars)")
            else:
                log(f"  ❌ MDX not on GitHub either — cannot translate")
                return False
        except Exception as e:
            log(f"  ❌ GitHub pull error: {e}")
            return False
    result = subprocess.run(
        [str(VENV_PYTHON), str(translate_script), "--slug", slug, "--category", category, "--lang", "all"],
        capture_output=True, text=True, timeout=15 * 60,
    )
    ok = result.returncode == 0
    log(f"  {'✅' if ok else '❌'} translate exit={result.returncode}")
    if not ok and result.stderr:
        log(f"    stderr: {result.stderr[-200:]}")
    return ok


# ─── COVER IMAGE ───────────────────────────────────────────────────────────────

def run_image(slug: str, category: str, title: str | None = None, article_id: str | None = None) -> bool:
    """Generate cover image via bz_image_style + Fireworks Flux Dev, commit to GitHub."""
    import base64
    import re

    IMAGE_GH_PATH = f"{IMAGE_GH_DIR}/{slug}.jpg"
    log(f"  ▶ Cover image for {slug}")

    if not title:
        try:
            result = subprocess.run(
                ["gh", "api", f"repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/apps/mouth/src/content/articles/{category}/{slug}.mdx"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                mdx_data = json.loads(result.stdout)
                mdx_content = base64.b64decode(mdx_data["content"]).decode("utf-8")
                title_match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', mdx_content, re.MULTILINE)
                title = title_match.group(1) if title_match else slug
            else:
                title = slug
        except Exception:
            title = slug

    # Check if image already exists
    try:
        check = subprocess.run(
            ["gh", "api", f"repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{IMAGE_GH_PATH}", "--jq", ".sha"],
            capture_output=True, text=True, timeout=15,
        )
        existing_sha = check.stdout.strip() if check.returncode == 0 else ""
        if existing_sha:
            log("  ⏭ Image already on GitHub")
            if article_id:
                _update_news_image_url(article_id, f"/static/news/{slug}.jpg")
            return True
    except Exception:
        existing_sha = ""

    # Build prompt
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        from bz_image_style import build_cover_prompt
        prompt = build_cover_prompt(title, category)
    except Exception as e:
        log(f"  ⚠ bz_image_style error: {e}")
        prompt = f"Cinematic Bali photography, {category} theme, {title[:60]}, teal and amber color grading, ARRI Alexa Mini LF, no text"

    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = Path(tmpdir) / f"{slug}.jpg"
        generated = False

        # 1. Fireworks.ai Flux Dev
        fireworks_key = os.environ.get("FIREWORKS_API_KEY", "")
        if fireworks_key:
            log("    Fireworks.ai Flux Dev")
            fw_payload = json.dumps({"prompt": prompt, "width": 1344, "height": 768, "steps": 28, "cfg_scale": 3.5}).encode()
            fw_req = urllib.request.Request(
                "https://api.fireworks.ai/inference/v1/workflows/accounts/fireworks/models/flux-1-dev-fp8/text_to_image",
                data=fw_payload,
                headers={"Authorization": f"Bearer {fireworks_key}", "Content-Type": "application/json", "Accept": "image/jpeg"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(fw_req, timeout=90) as fw_resp:
                    img_bytes = fw_resp.read()
                    if len(img_bytes) > 5000:
                        img_path.write_bytes(img_bytes)
                        generated = True
                        log(f"    ✅ {len(img_bytes)} bytes")
            except Exception as e:
                log(f"    Fireworks error: {e}")

        # 2. Pollinations fallback
        if not generated:
            log("    Pollinations.ai fallback")
            encoded_prompt = urllib.parse.quote(prompt)
            seed = int(__import__("time").time()) % 99999
            for model in ["sana", "turbo"]:
                try:
                    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1200&height=630&seed={seed}&nologo=true&model={model}"
                    req = urllib.request.Request(url, headers={"User-Agent": "BaliZero/1.0"})
                    resp = urllib.request.urlopen(req, timeout=90)
                    if resp.status == 200:
                        data = resp.read()
                        if len(data) > 5000:
                            img_path.write_bytes(data)
                            generated = True
                            log(f"    ✅ Pollinations [{model}]")
                            break
                except Exception as e:
                    log(f"    Pollinations [{model}] error: {e}")

        if not generated:
            log("  ❌ Image generation failed")
            return False

        # Commit to GitHub
        img_bytes = img_path.read_bytes()
        encoded_img = base64.b64encode(img_bytes).decode("utf-8")
        payload = {"message": f"feat(image): add cover image for '{title[:50]}'", "content": encoded_img}
        if existing_sha:
            payload["sha"] = existing_sha

        try:
            result = subprocess.run(
                ["gh", "api", f"repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{IMAGE_GH_PATH}", "--method", "PUT", "--input", "-"],
                input=json.dumps(payload), capture_output=True, text=True, timeout=60,
            )
            ok = result.returncode == 0
            log(f"  {'✅' if ok else '❌'} Image committed")
            if ok and article_id:
                _update_news_image_url(article_id, f"/static/news/{slug}.jpg")
            return ok
        except Exception as e:
            log(f"  ⚠ Image commit error: {e}")
            return False


def _update_news_image_url(article_id: str, image_url: str):
    try:
        api_post(f"/api/news/{article_id}/image", {"image_url": image_url})
    except Exception as e:
        log(f"  ⚠ news_items.image_url update failed: {e}")


# ─── HERO ROTATION ────────────────────────────────────────────────────────────

HOMEPAGE_LAYOUT_PATH = "apps/mouth/src/content/homepage-layout.json"
HERO_KEYS = ["hero_main", "hero_2", "hero_3", "hero_4", "hero_5"]
LATEST_KEYS = ["latest_1", "latest_2", "latest_3", "latest_4", "latest_5"]


def rotate_hero(new_slug: str) -> bool:
    """Rotate homepage-layout.json: push new_slug to hero_main, cascade others down.
    Old hero_5 moves to latest_1, shifting latest_* down (latest_5 dropped).
    Commits and pushes to GitHub.
    """
    import base64 as _b64

    log(f"  ▶ Hero rotation: {new_slug}")

    # Read current layout from GitHub (source of truth)
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{HOMEPAGE_LAYOUT_PATH}"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            log("  ⚠ Hero: cannot read homepage-layout.json from GitHub")
            return False
        data = json.loads(result.stdout)
        layout = json.loads(_b64.b64decode(data["content"]).decode("utf-8"))
        sha = data["sha"]
    except Exception as e:
        log(f"  ⚠ Hero: read error: {e}")
        return False

    # Skip if already hero_main
    if layout.get("hero_main") == new_slug:
        log("  ⏭ Hero: already hero_main")
        return True

    # Skip if slug not yet in layout at all (might not have MDX on GitHub yet)
    # We proceed regardless — the new article is being published right now.

    # Cascade: old hero_main→hero_2→…→hero_5 → latest_1→…→latest_5
    old_heros = [layout.get(k) for k in HERO_KEYS]  # current [main, 2, 3, 4, 5]
    old_latests = [layout.get(k) for k in LATEST_KEYS]

    # New hero list: new slug at front, old heroes shift down (drop last)
    new_heros = [new_slug] + [s for s in old_heros if s and s != new_slug][:len(HERO_KEYS) - 1]
    # New latest: old hero_5 at front, shift down (drop last)
    evicted = old_heros[-1] if old_heros[-1] and old_heros[-1] != new_slug else None
    if evicted:
        new_latests = [evicted] + [s for s in old_latests if s and s != evicted][:len(LATEST_KEYS) - 1]
    else:
        new_latests = old_latests

    for i, key in enumerate(HERO_KEYS):
        if i < len(new_heros):
            layout[key] = new_heros[i]
    for i, key in enumerate(LATEST_KEYS):
        if i < len(new_latests):
            layout[key] = new_latests[i]

    # Write back to GitHub
    new_content = json.dumps(layout, indent=2, ensure_ascii=False) + "\n"
    encoded = _b64.b64encode(new_content.encode("utf-8")).decode("utf-8")
    payload = {
        "message": f"feat(homepage): rotate hero → {new_slug[:50]}",
        "content": encoded,
        "sha": sha,
    }
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{HOMEPAGE_LAYOUT_PATH}",
             "--method", "PUT", "--input", "-"],
            input=json.dumps(payload), capture_output=True, text=True, timeout=30,
        )
        ok = result.returncode == 0
        log(f"  {'✅' if ok else '❌'} Hero rotation pushed (hero_main={new_slug[:40]})")
        return ok
    except Exception as e:
        log(f"  ⚠ Hero rotation push error: {e}")
        return False


# ─── GIT OPERATIONS ───────────────────────────────────────────────────────────

def git_pull_monorepo():
    repo_root = SCRIPT_DIR.parent.parent.parent
    try:
        result = subprocess.run(["git", "pull", "--ff-only"], capture_output=True, text=True, cwd=str(repo_root), timeout=60)
        if result.returncode == 0:
            log(f"✅ git pull OK")
        else:
            # Try stash + pull + pop
            subprocess.run(["git", "stash"], capture_output=True, cwd=str(repo_root), timeout=10)
            subprocess.run(["git", "pull", "--ff-only"], capture_output=True, cwd=str(repo_root), timeout=60)
            subprocess.run(["git", "stash", "pop"], capture_output=True, cwd=str(repo_root), timeout=10)
            log("✅ git pull OK (via stash)")
    except Exception as e:
        log(f"⚠ git pull error: {e}")


def git_commit_and_push_translations(slugs: list[str]):
    repo_root = SCRIPT_DIR.parent.parent.parent
    articles_dir = repo_root / "apps" / "mouth" / "src" / "content" / "articles"

    translation_files = []
    for slug in slugs:
        for f in articles_dir.rglob(f"{slug}.*.mdx"):
            translation_files.append(str(f.relative_to(repo_root)))

    if not translation_files:
        log("⚠ No translation files to commit")
        return

    log(f"▶ git commit+push {len(translation_files)} translation files")
    try:
        subprocess.run(["git", "add"] + translation_files, cwd=str(repo_root), capture_output=True, check=True, timeout=30)
        status = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(repo_root), capture_output=True, timeout=10)
        if status.returncode == 0:
            log("⏭ Nothing staged — already committed")
            return
        msg = f"feat(articles): add translations for {', '.join(slugs[:3])}{'...' if len(slugs) > 3 else ''}"
        subprocess.run(["git", "commit", "--no-verify", "-m", msg], cwd=str(repo_root), capture_output=True, check=True, timeout=30)
        push = subprocess.run(["git", "push", "--no-verify", "origin", "main"], cwd=str(repo_root), capture_output=True, text=True, timeout=60)
        if push.returncode == 0:
            log("✅ Translations pushed")
        else:
            subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=str(repo_root), capture_output=True, timeout=60)
            push2 = subprocess.run(["git", "push", "--no-verify", "origin", "main"], cwd=str(repo_root), capture_output=True, text=True, timeout=60)
            log(f"{'✅' if push2.returncode == 0 else '❌'} Push after rebase: exit={push2.returncode}")
    except Exception as e:
        log(f"⚠ git push translations failed: {e}")


# ─── MAIN ──────────────────────────────────────────────────────────────────────

def process_item(item: dict) -> tuple[bool, list[str]]:
    """Process a single queue item. Returns (all_done, failed_steps)."""
    slug = item["slug"]
    category = item.get("category", "business")
    source = item.get("source", "intel")
    article_id = item.get("article_id")
    title = item.get("title")
    done = item.get("completed_steps", {})
    failed_steps = []

    if source == "intel":
        # SEO
        if not done.get("seo"):
            if run_seo(slug, category):
                mark_step_done(slug, "seo")
            else:
                failed_steps.append("seo")
        # Translate
        if not done.get("translate"):
            if run_translate(slug, category):
                mark_step_done(slug, "translate")
                return_translate = True
                # Auto-rotate hero after successful translate
                rotate_hero(slug)
            else:
                failed_steps.append("translate")
                return_translate = False
        else:
            return_translate = True
        # Image
        if not done.get("image"):
            if run_image(slug, category, title=title):
                mark_step_done(slug, "image")
            else:
                failed_steps.append("image")

        return (len(failed_steps) == 0, failed_steps)

    elif source == "news":
        if not done.get("image"):
            if run_image(slug, category, title=title, article_id=article_id):
                mark_step_done(slug, "image")
            else:
                failed_steps.append("image")
        return (len(failed_steps) == 0, failed_steps)

    else:
        log(f"⚠ Unknown source '{source}'")
        return (True, [])


def main():
    log("=" * 50)
    log("🔄 Post-publish poller v3 started")

    try:
        result = api_get("/api/intel/post-publish-queue/pending")
        pending = result.get("pending", [])
    except Exception as e:
        log(f"❌ Queue read error: {e}")
        return

    if not pending:
        log("✅ No articles in queue")
        return

    log(f"📋 {len(pending)} articles in queue")
    git_pull_monorepo()

    done_slugs = []
    failed_items = []
    translated_slugs = []

    for item in pending:
        slug = item["slug"]
        attempts = item.get("attempts", 1)
        log(f"📄 [{item.get('source','?')}] {item.get('category','?')}/{slug} (attempt {attempts})")

        all_ok, failed_steps = process_item(item)

        if all_ok:
            done_slugs.append(slug)
            # Check if translate was done (for git push)
            completed = item.get("completed_steps", {})
            if completed.get("translate") or item.get("source") == "news":
                pass  # already committed or not needed
            else:
                translated_slugs.append(slug)
        else:
            failed_items.append({"slug": slug, "steps": failed_steps, "attempts": attempts})
            # Still push translations if translate succeeded
            completed = item.get("completed_steps", {})
            if "translate" not in failed_steps and item.get("source") == "intel":
                translated_slugs.append(slug)

    # Commit translations
    if translated_slugs:
        git_commit_and_push_translations(translated_slugs)

    # Mark done
    if done_slugs:
        try:
            api_post("/api/intel/post-publish-queue/done", {"slugs": done_slugs})
            log(f"✅ Done: {done_slugs}")
        except Exception as e:
            log(f"⚠ Error marking done: {e}")

    # Mark failed (will retry on next poll, up to 5 attempts)
    for item in failed_items:
        slug = item["slug"]
        steps = item["steps"]
        attempts = item["attempts"]
        try:
            api_post("/api/intel/post-publish-queue/failed", {
                "slugs": [slug],
                "error": f"Failed steps: {', '.join(steps)}",
            })
            log(f"⚠ Failed: {slug} (steps: {steps}, attempt {attempts}/5)")
        except Exception as e:
            log(f"⚠ Error marking failed: {e}")

        # Telegram alert after 2+ attempts
        if attempts >= 2:
            send_telegram_alert(
                f"⚠️ *Post-publish pipeline*\n"
                f"Article: `{slug}`\n"
                f"Failed steps: {', '.join(steps)}\n"
                f"Attempt: {attempts}/5\n"
                f"{'🔴 Will be dead-lettered after 5' if attempts >= 4 else '🔄 Will retry'}"
            )

    log("🏁 Poller completed")


if __name__ == "__main__":
    main()
