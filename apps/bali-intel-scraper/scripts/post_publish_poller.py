#!/usr/bin/env python3
"""
Post-publish poller v2 — Unified pipeline for intel + news articles.

Runs every 5 minutes via LaunchAgent (com.balizero.post-publish-poller).
Reads from PostgreSQL-backed queue on backend, processes each article:
  - SEO/GEO metadata optimization (Gemini CLI)
  - Translation to 4 languages (Ollama local)
  - Cover image generation (bz_image_style + Fireworks Flux Dev)
  - Git commit + push

Handles two article sources:
  - 'intel': MDX articles from intel scraper (full pipeline: SEO + translate + image)
  - 'news':  news_items from /api/news (image generation + DB update only, no MDX)
"""
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
# Support both .venv (Pro) and venv (Air)
_venv = SCRIPT_DIR.parent / ".venv" / "bin" / "python3"
VENV_PYTHON = _venv if _venv.exists() else SCRIPT_DIR.parent / "venv" / "bin" / "python3"
LOG_DIR = Path.home() / ".openclaw" / "workspace" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"post_publish_poller_{datetime.now().strftime('%Y%m%d')}.log"

BACKEND_URL = os.environ.get("BACKEND_URL", "https://nuzantara-rag.fly.dev")
API_KEY = os.environ.get("SCRAPER_API_KEY", "internal-scraper-key")

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


def wait_for_ollama_free(max_wait: int = 60 * 30) -> bool:
    """Wait until no other translate_articles.py is running (max 30 min)."""
    import time
    waited = 0
    while waited < max_wait:
        check = subprocess.run(
            ["pgrep", "-f", "translate_articles.py"],
            capture_output=True, text=True
        )
        if check.returncode != 0:
            return True
        log(f"⏳ Ollama busy (another translate running) — waiting 60s...")
        time.sleep(60)
        waited += 60
    log("⚠ Timeout waiting for Ollama — proceeding anyway")
    return False


# ─── SEO/GEO ──────────────────────────────────────────────────────────────────

def run_seo(slug: str, category: str) -> bool:
    """Optimize SEO/GEO metadata of published MDX via Gemini."""
    import base64
    import re

    ARTICLES_PATH = "apps/mouth/src/content/articles"
    mdx_path = f"{ARTICLES_PATH}/{category}/{slug}.mdx"

    log(f"▶ SEO/GEO optimizer for {category}/{slug}")

    # Read MDX from GitHub
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{mdx_path}"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            log("⚠ SEO: file not found on GitHub — skip")
            return True
        data = json.loads(result.stdout)
        content = base64.b64decode(data["content"]).decode("utf-8")
        sha = data.get("sha", "")
    except Exception as e:
        log(f"⚠ SEO: GitHub read error: {e}")
        return True

    # Extract frontmatter and body
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
    if not match:
        log("⚠ SEO: frontmatter not found — skip")
        return True

    fm_raw = match.group(1)
    body = match.group(2)

    # Check if already optimized
    if "answerSnippet" in fm_raw and "Check article for specific dates" not in fm_raw and "What does" not in fm_raw:
        if "mean for expats in Bali?" not in fm_raw:
            log("⏭ SEO already optimized — skip")
            return True

    title_match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', fm_raw, re.MULTILINE)
    title = title_match.group(1) if title_match else slug

    body_preview = body[:3000]

    prompt = f"""You are an expert SEO and AI Search Optimization (GEO/AEO) specialist for Bali Zero, an immigration and business setup agency in Bali.

Analyze this article and return ONLY a JSON object with optimized metadata. No explanations, no markdown, just the JSON.

Article title: {title}
Category: {category}
Article body (first 3000 chars):
{body_preview}

Return this exact JSON structure:
{{
  "seoTitle": "<60 chars, keyword-first, include year 2026 if relevant>",
  "seoDescription": "<150-155 chars, include primary keyword + action>",
  "aiOptimization": {{
    "answerSnippet": "<2 clear declarative sentences answering the article's main question. Factual and specific. This is what AI systems cite.>",
    "primaryQuestion": "<The main question this article answers, phrased as users would search it>",
    "entityMentions": ["<key entity 1>", "<key entity 2>", "<key entity 3>"]
  }}
}}"""

    try:
        result = subprocess.run(
            ["gemini", "-m", "gemini-2.5-pro", "-p", prompt],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0 or not result.stdout.strip():
            result = subprocess.run(
                ["gemini", "-p", prompt],
                capture_output=True, text=True, timeout=60
            )
    except Exception as e:
        log(f"⚠ SEO: Gemini error: {e}")
        return True

    # Parse JSON response
    raw = result.stdout.strip()
    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not json_match:
        log("⚠ SEO: no JSON in Gemini response — skip")
        return True

    try:
        seo = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        log("⚠ SEO: invalid JSON — skip")
        return True

    # Update frontmatter
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
        fm_raw = re.sub(
            r'(answerSnippet:\s*)["\']?.*?["\']?\s*$',
            f'\\1"{answer}"',
            fm_raw, flags=re.MULTILINE
        )
    if ai_opt.get("primaryQuestion"):
        question = ai_opt["primaryQuestion"].replace('"', '\\"')
        fm_raw = re.sub(
            r'(primaryQuestion:\s*)["\']?.*?["\']?\s*$',
            f'\\1"{question}"',
            fm_raw, flags=re.MULTILINE
        )

    new_content = f"---\n{fm_raw}\n---\n{body}"

    # Commit to GitHub
    encoded = __import__("base64").b64encode(new_content.encode("utf-8")).decode("utf-8")
    payload = {
        "message": f"feat(seo): optimize GEO/AEO metadata for '{title[:50]}'",
        "content": encoded,
        "sha": sha,
    }
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{mdx_path}",
             "--method", "PUT", "--input", "-"],
            input=json.dumps(payload), capture_output=True, text=True, timeout=30
        )
        ok = result.returncode == 0
        log(f"{'✅' if ok else '❌'} SEO/GEO metadata updated for {slug}")
        return ok
    except Exception as e:
        log(f"⚠ SEO: commit error: {e}")
        return True


# ─── TRANSLATION ───────────────────────────────────────────────────────────────

def run_translate(slug: str, category: str) -> bool:
    wait_for_ollama_free()
    translate_script = SCRIPT_DIR.parent.parent.parent / "scripts" / "translate-articles.py"
    log(f"▶ translate-articles.py --slug {slug} --category {category} --lang all")
    result = subprocess.run(
        [str(VENV_PYTHON), str(translate_script),
         "--slug", slug, "--category", category, "--lang", "all"],
        capture_output=True, text=True, timeout=15 * 60
    )
    ok = result.returncode == 0
    log(f"{'✅' if ok else '❌'} translate exit={result.returncode}")
    if not ok and result.stderr:
        log(f"   stderr: {result.stderr[-300:]}")
    return ok


# ─── COVER IMAGE ───────────────────────────────────────────────────────────────

def run_image(slug: str, category: str, title: str | None = None, article_id: str | None = None) -> bool:
    """
    Generate cover image and commit to GitHub.
    Uses bz_image_style for prompt generation (Claude Haiku visual director).
    Fireworks.ai Flux Dev → Pollinations → Picsum → Unsplash fallback chain.

    If article_id is provided (news source), also updates news_items.image_url via API.
    """
    import base64
    import re
    import tempfile
    import urllib.parse

    IMAGE_GH_PATH = f"{IMAGE_GH_DIR}/{slug}.jpg"
    log(f"▶ cover image for {category}/{slug}")

    # Get title from MDX if not provided
    if not title:
        try:
            result = subprocess.run(
                ["gh", "api", f"repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/apps/mouth/src/content/articles/{category}/{slug}.mdx"],
                capture_output=True, text=True, timeout=30
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

    # Check if image already exists on GitHub
    try:
        check = subprocess.run(
            ["gh", "api", f"repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{IMAGE_GH_PATH}",
             "--jq", ".sha"],
            capture_output=True, text=True, timeout=15
        )
        existing_sha = check.stdout.strip() if check.returncode == 0 else ""
        if existing_sha:
            log("⏭ Image already on GitHub — skip generation")
            # Still update DB if needed
            if article_id:
                _update_news_image_url(article_id, f"/static/news/{slug}.jpg")
            return True
    except Exception:
        existing_sha = ""

    # Build prompt via bz_image_style
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        from bz_image_style import build_cover_prompt
        prompt = build_cover_prompt(title, category)
    except Exception as e:
        log(f"⚠ bz_image_style error: {e} — using fallback prompt")
        prompt = (
            f"Cinematic Bali photography, {category} theme, {title[:60]}, "
            "dramatic light, teal and amber color grading, "
            "shot on ARRI Alexa Mini LF, editorial photography, no text"
        )

    # Generate image
    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = Path(tmpdir) / f"{slug}.jpg"
        generated = False

        # --- 1. Fireworks.ai Flux Dev (cloud, high quality) ---
        fireworks_key = os.environ.get("FIREWORKS_API_KEY", "")
        if fireworks_key:
            log("  Trying Fireworks.ai Flux Dev")
            fw_url = "https://api.fireworks.ai/inference/v1/workflows/accounts/fireworks/models/flux-1-dev-fp8/text_to_image"
            fw_payload = json.dumps({
                "prompt": prompt,
                "width": 1344,
                "height": 768,
                "steps": 28,
                "cfg_scale": 3.5,
            }).encode()
            fw_req = urllib.request.Request(
                fw_url,
                data=fw_payload,
                headers={
                    "Authorization": f"Bearer {fireworks_key}",
                    "Content-Type": "application/json",
                    "Accept": "image/jpeg",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(fw_req, timeout=90) as fw_resp:
                    img_bytes_fw = fw_resp.read()
                    if len(img_bytes_fw) > 5000:
                        img_path.write_bytes(img_bytes_fw)
                        generated = True
                        log(f"  Image generated via Fireworks.ai Flux Dev ({len(img_bytes_fw)} bytes)")
            except Exception as e:
                log(f"  Fireworks.ai error: {e}")
        else:
            log("  FIREWORKS_API_KEY not set — skip Fireworks")

        # --- 2. Pollinations.ai fallback ---
        if not generated:
            log("  Trying Pollinations.ai")
            encoded_prompt = urllib.parse.quote(prompt)
            seed = int(__import__("time").time()) % 99999
            for model in ["sana", "turbo"]:
                url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1200&height=630&seed={seed}&nologo=true&model={model}"
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "BaliZero/1.0"})
                    resp = urllib.request.urlopen(req, timeout=90)
                    if resp.status == 200:
                        data = resp.read()
                        if len(data) > 5000:
                            img_path.write_bytes(data)
                            generated = True
                            log(f"  Image generated via Pollinations [{model}]")
                            break
                except Exception as e:
                    log(f"  Pollinations [{model}] error: {e}")

        # --- 3. Picsum fallback (curated photos) ---
        if not generated:
            log("  Pollinations offline — using Picsum Photos")
            category_seeds = {
                "business": 237, "immigration": 452, "tax": 178,
                "property": 312, "lifestyle": 501, "digital-nomad": 89,
                "tech": 667, "emerging_trends": 730, "tax-legal": 195,
                "visas": 452, "taxes": 178, "living": 501, "trends": 667,
            }
            seed_id = category_seeds.get(category, 42)
            url = f"https://picsum.photos/seed/{seed_id}/1200/630"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "BaliZero/1.0"})
                resp = urllib.request.urlopen(req, timeout=30)
                if resp.status == 200:
                    data = resp.read()
                    if len(data) > 5000:
                        img_path.write_bytes(data)
                        generated = True
                        log(f"  Image from Picsum [seed={seed_id}]")
            except Exception as e:
                log(f"  Picsum error: {e}")

        if not generated or not img_path.exists():
            log("⚠ Image generation failed — skip")
            return True  # non-blocking

        # Commit to GitHub
        img_bytes = img_path.read_bytes()
        encoded_img = base64.b64encode(img_bytes).decode("utf-8")
        payload = {
            "message": f"feat(image): add cover image for '{title[:50]}'",
            "content": encoded_img,
        }
        if existing_sha:
            payload["sha"] = existing_sha

        try:
            result = subprocess.run(
                ["gh", "api", f"repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{IMAGE_GH_PATH}",
                 "--method", "PUT", "--input", "-"],
                input=json.dumps(payload), capture_output=True, text=True, timeout=60
            )
            ok = result.returncode == 0
            log(f"{'✅' if ok else '❌'} Image committed: {IMAGE_GH_PATH}")

            # Update news_items.image_url if this is a news source article
            if ok and article_id:
                _update_news_image_url(article_id, f"/static/news/{slug}.jpg")

            return ok
        except Exception as e:
            log(f"⚠ Image commit failed: {e}")
            return True


def _update_news_image_url(article_id: str, image_url: str) -> None:
    """Update news_items.image_url via backend API."""
    try:
        api_post(f"/api/news/{article_id}/image", {"image_url": image_url})
        log(f"  ✅ Updated news_items.image_url for {article_id}")
    except Exception as e:
        log(f"  ⚠ Failed to update news_items.image_url: {e}")


# ─── GIT OPERATIONS ───────────────────────────────────────────────────────────

def git_pull_monorepo() -> None:
    """Pull latest commits so translate-articles.py can find newly published MDX files."""
    repo_root = SCRIPT_DIR.parent.parent.parent
    try:
        result = subprocess.run(
            ["git", "pull", "--ff-only"],
            capture_output=True, text=True, cwd=str(repo_root), timeout=60
        )
        if result.returncode == 0:
            log(f"✅ git pull OK: {result.stdout.strip()[:80]}")
        else:
            log(f"⚠ git pull failed (non-blocking): {result.stderr.strip()[:200]}")
    except Exception as e:
        log(f"⚠ git pull error (non-blocking): {e}")


def git_commit_and_push_translations(slugs: list[str]) -> None:
    """Commit and push translation files generated by translate-articles.py."""
    repo_root = SCRIPT_DIR.parent.parent.parent
    articles_dir = repo_root / "apps" / "mouth" / "src" / "content" / "articles"

    translation_files = []
    for slug in slugs:
        for f in articles_dir.rglob(f"{slug}.*.mdx"):
            translation_files.append(str(f.relative_to(repo_root)))

    if not translation_files:
        log("⚠ No translation files found to commit")
        return

    log(f"▶ git commit+push {len(translation_files)} translation files")
    try:
        subprocess.run(["git", "add"] + translation_files,
                       cwd=str(repo_root), capture_output=True, check=True, timeout=30)
        status = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=str(repo_root), capture_output=True, timeout=10
        )
        if status.returncode == 0:
            log("⏭ No staged changes — translations already committed")
            return
        msg = f"feat(articles): add translations for {', '.join(slugs[:3])}{'...' if len(slugs) > 3 else ''}"
        subprocess.run(
            ["git", "commit", "--no-verify", "-m", msg],
            cwd=str(repo_root), capture_output=True, check=True, timeout=30
        )
        push = subprocess.run(
            ["git", "push", "--no-verify", "origin", "main"],
            cwd=str(repo_root), capture_output=True, text=True, timeout=60
        )
        if push.returncode == 0:
            log("✅ Translations pushed to GitHub")
        else:
            log(f"⚠ Push failed, trying rebase: {push.stderr.strip()[:100]}")
            subprocess.run(
                ["git", "pull", "--rebase", "origin", "main"],
                cwd=str(repo_root), capture_output=True, timeout=60
            )
            push2 = subprocess.run(
                ["git", "push", "--no-verify", "origin", "main"],
                cwd=str(repo_root), capture_output=True, text=True, timeout=60
            )
            log(f"{'✅' if push2.returncode == 0 else '❌'} Push after rebase: exit={push2.returncode}")
    except Exception as e:
        log(f"⚠ git commit/push translations failed (non-blocking): {e}")


# ─── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    log("=" * 50)
    log("🔄 Post-publish poller v2 started")

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

    # Pull latest MDX files
    git_pull_monorepo()

    done_slugs = []
    failed_slugs = []
    translated_slugs = []

    for item in pending:
        slug = item["slug"]
        category = item.get("category", "business")
        source = item.get("source", "intel")
        article_id = item.get("article_id")
        title = item.get("title")
        log(f"📄 [{source}] {category}/{slug}")

        if source == "intel":
            # Full pipeline: SEO + translate + image
            run_seo(slug, category)
            translate_ok = run_translate(slug, category)
            run_image(slug, category, title=title)
            if translate_ok:
                translated_slugs.append(slug)
            done_slugs.append(slug)

        elif source == "news":
            # News items: image only (no MDX, no translations)
            run_image(slug, category, title=title, article_id=article_id)
            done_slugs.append(slug)

        else:
            log(f"⚠ Unknown source '{source}' — processing as intel")
            run_seo(slug, category)
            run_translate(slug, category)
            run_image(slug, category)
            done_slugs.append(slug)

    # Commit and push translations
    if translated_slugs:
        git_commit_and_push_translations(translated_slugs)

    # Mark as done
    if done_slugs:
        try:
            api_post("/api/intel/post-publish-queue/done", {"slugs": done_slugs})
            log(f"✅ Marked done: {done_slugs}")
        except Exception as e:
            log(f"⚠ Error marking done: {e}")

    # Mark failures
    if failed_slugs:
        try:
            api_post("/api/intel/post-publish-queue/failed", {
                "slugs": failed_slugs,
                "error": "Processing failed after max attempts",
            })
            log(f"❌ Marked failed: {failed_slugs}")
        except Exception as e:
            log(f"⚠ Error marking failed: {e}")

    log("🏁 Poller completed")


if __name__ == "__main__":
    main()
