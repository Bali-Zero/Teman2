#!/usr/bin/env python3
"""
Post-publish poller — gira ogni 5 minuti (launchd com.balizero.post-publish-poller)
Legge la coda da /api/intel/post-publish-queue/pending sul backend Fly.io,
lancia translate + SEO + image per ogni articolo in coda, poi marca come done.
"""
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
# Support both .venv (Air) and venv (Pro)
_venv = SCRIPT_DIR.parent / ".venv" / "bin" / "python3"
VENV_PYTHON = _venv if _venv.exists() else SCRIPT_DIR.parent / "venv" / "bin" / "python3"
LOG_DIR = Path.home() / ".openclaw" / "workspace" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"post_publish_poller_{datetime.now().strftime('%Y%m%d')}.log"

BACKEND_URL = os.environ.get("BACKEND_URL", "https://nuzantara-rag.fly.dev")
API_KEY = os.environ.get("SCRAPER_API_KEY", "internal-scraper-key")


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
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def api_post(path: str, data: dict) -> dict:
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{BACKEND_URL}{path}",
        data=body,
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def wait_for_ollama_free(max_wait: int = 60 * 30) -> bool:
    """Aspetta che nessun altro translate_articles.py stia girando (max 30 min)."""
    import time
    waited = 0
    while waited < max_wait:
        check = subprocess.run(
            ["pgrep", "-f", "translate_articles.py"],
            capture_output=True, text=True
        )
        if check.returncode != 0:
            return True  # nessun processo attivo
        log(f"⏳ Ollama occupato (altro translate in corso) — attendo 60s...")
        time.sleep(60)
        waited += 60
    log("⚠ Timeout attesa Ollama libero — procedo comunque")
    return False


def run_translate(slug: str, category: str) -> bool:
    wait_for_ollama_free()
    # translate-articles.py lives in monorepo root scripts/, not in scraper scripts/
    translate_script = SCRIPT_DIR.parent.parent.parent / "scripts" / "translate-articles.py"
    log(f"▶ translate-articles.py --slug {slug} --category {category} --lang both")
    result = subprocess.run(
        [str(VENV_PYTHON), str(translate_script),
         "--slug", slug, "--category", category, "--lang", "all"],
        capture_output=True, text=True, timeout=15 * 60  # 15 min max per singolo articolo
    )
    ok = result.returncode == 0
    log(f"{'✅' if ok else '❌'} translate exit={result.returncode}")
    if not ok and result.stderr:
        log(f"   stderr: {result.stderr[-300:]}")
    return ok


def run_seo(slug: str, category: str) -> bool:
    """Ottimizza SEO/GEO metadata dell'MDX pubblicato via Gemini."""
    import base64
    import re
    import time

    GITHUB_OWNER = "Balizero1987"
    GITHUB_REPO = "Teman2"
    ARTICLES_PATH = "apps/mouth/src/content/articles"
    mdx_path = f"{ARTICLES_PATH}/{category}/{slug}.mdx"

    log(f"▶ SEO/GEO optimizer per {category}/{slug}")

    # Leggi MDX da GitHub
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{mdx_path}"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            log(f"⚠ SEO: file non trovato su GitHub — skip")
            return True
        data = json.loads(result.stdout)
        content = base64.b64decode(data["content"]).decode("utf-8")
        sha = data.get("sha", "")
    except Exception as e:
        log(f"⚠ SEO: errore lettura GitHub: {e}")
        return True

    # Estrai frontmatter e body
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
    if not match:
        log("⚠ SEO: frontmatter non trovato — skip")
        return True

    fm_raw = match.group(1)
    body = match.group(2)

    # Controlla se già ottimizzato (answerSnippet non è placeholder)
    if "answerSnippet" in fm_raw and "Check article for specific dates" not in fm_raw and "What does" not in fm_raw:
        if "mean for expats in Bali?" not in fm_raw:
            log(f"⏭ SEO già ottimizzato — skip")
            return True

    # Estrai title e body preview per il prompt
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

    # Parsa JSON dalla risposta
    raw = result.stdout.strip()
    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not json_match:
        log("⚠ SEO: nessun JSON nella risposta Gemini — skip")
        return True

    try:
        seo = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        log("⚠ SEO: JSON non valido — skip")
        return True

    # Aggiorna frontmatter — sostituisce i campi SEO
    def set_fm_field(fm: str, key: str, value: str) -> str:
        value_escaped = value.replace('"', '\\"')
        pattern = rf'^{re.escape(key)}:.*$'
        replacement = f'{key}: "{value_escaped}"'
        new_fm = re.sub(pattern, replacement, fm, flags=re.MULTILINE)
        if new_fm == fm:  # campo non esisteva, aggiungilo
            new_fm = fm + f'\n{key}: "{value_escaped}"'
        return new_fm

    ai_opt = seo.get("aiOptimization", {})
    fm_raw = set_fm_field(fm_raw, "seoTitle", seo.get("seoTitle", ""))
    fm_raw = set_fm_field(fm_raw, "seoDescription", seo.get("seoDescription", ""))

    # Aggiorna aiOptimization block (answerSnippet e primaryQuestion)
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

    # Commit su GitHub
    encoded = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")
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
        log(f"{'✅' if ok else '❌'} SEO/GEO metadata aggiornati per {slug}")
        return ok
    except Exception as e:
        log(f"⚠ SEO: errore commit: {e}")
        return True


def run_image(slug: str, category: str) -> bool:
    """
    Genera copertina e committa su GitHub.
    1. Legge title dall'MDX via GitHub API
    2. Costruisce prompt con bz_image_style
    3. Genera con Fireworks.ai Flux → ComfyUI → Pollinations → Picsum → Unsplash
    4. Committa il JPG su GitHub in public/static/news/
    """
    import base64
    import re
    import tempfile
    import urllib.parse

    GITHUB_OWNER = "Balizero1987"
    GITHUB_REPO = "Teman2"
    ARTICLES_PATH = "apps/mouth/src/content/articles"
    IMAGE_GH_PATH = f"apps/mouth/public/static/news/{slug}.jpg"
    COMFYUI_URL = "http://127.0.0.1:8188"

    log(f"▶ immagine per {category}/{slug}")

    # Leggi title dall'MDX
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{ARTICLES_PATH}/{category}/{slug}.mdx"],
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

    # Controlla se immagine già esiste su GitHub
    try:
        check = subprocess.run(
            ["gh", "api", f"repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{IMAGE_GH_PATH}",
             "--jq", ".sha"],
            capture_output=True, text=True, timeout=15
        )
        existing_sha = check.stdout.strip() if check.returncode == 0 else ""
        if existing_sha:
            log(f"⏭ Immagine già presente su GitHub — skip")
            return True
    except Exception:
        existing_sha = ""

    # Costruisci prompt con bz_image_style
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        from bz_image_style import build_cover_prompt
        prompt = build_cover_prompt(title, category)
    except Exception as e:
        log(f"⚠ bz_image_style error: {e} — uso prompt generico")
        prompt = f"Cinematic Bali photography, {category} theme, dramatic light, terracotta and gold palette, no text"

    # Genera immagine
    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = Path(tmpdir) / f"{slug}.jpg"
        generated = False

        # --- 1. Fireworks.ai Flux (cloud, veloce e alta qualità) ---
        fireworks_key = os.environ.get("FIREWORKS_API_KEY", "")
        if fireworks_key:
            log("  Provo Fireworks.ai Flux")
            fw_url = "https://api.fireworks.ai/inference/v1/image_generation/accounts/fireworks/models/flux-1-schnell-fp8"
            fw_payload = json.dumps({
                "prompt": prompt,
                "width": 1200,
                "height": 630,
                "num_inference_steps": 4,
            }).encode()
            fw_req = urllib.request.Request(
                fw_url,
                data=fw_payload,
                headers={
                    "Authorization": f"Bearer {fireworks_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(fw_req, timeout=60) as fw_resp:
                    fw_data = json.loads(fw_resp.read())
                    fw_image_url = fw_data.get("output", [{}])[0].get("url", "")
                    if fw_image_url:
                        img_req = urllib.request.Request(fw_image_url, headers={"User-Agent": "BaliZero/1.0"})
                        with urllib.request.urlopen(img_req, timeout=30) as img_resp:
                            img_bytes_fw = img_resp.read()
                            if len(img_bytes_fw) > 5000:
                                img_path.write_bytes(img_bytes_fw)
                                generated = True
                                log("  Immagine generata via Fireworks.ai Flux")
            except Exception as e:
                log(f"  Fireworks.ai error: {e}")
        else:
            log("  FIREWORKS_API_KEY non impostata — skip Fireworks")

        # --- 2. ComfyUI (locale, qualità massima) ---
        if not generated:
            try:
                resp = urllib.request.urlopen(f"{COMFYUI_URL}/system_stats", timeout=5)
                if resp.status == 200:
                    log("  Fireworks non disponibile — uso ComfyUI locale")
                    state = {"articles": [{"_published_item_id": slug, "enrichment": {"headline": title}, "category": category, "image_path": str(img_path)}]}
                    state_file = Path(tmpdir) / "state.json"
                    state_file.write_text(json.dumps(state))
                    r = subprocess.run(
                        [str(VENV_PYTHON), str(SCRIPT_DIR / "comfyui_image_generator.py"), str(state_file)],
                        capture_output=True, text=True, timeout=10 * 60
                    )
                    generated = r.returncode == 0 and img_path.exists() and img_path.stat().st_size > 5000
            except Exception:
                pass

        # --- 3. Pollinations.ai fallback ---
        if not generated:
            log("  Provo Pollinations.ai")
            encoded_prompt = urllib.parse.quote(prompt)
            seed = int(__import__("time").time()) % 99999
            for model in ["sana", "turbo", "zimage"]:
                url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1200&height=630&seed={seed}&nologo=true&model={model}"
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "BaliZero/1.0"})
                    resp = urllib.request.urlopen(req, timeout=90)
                    if resp.status == 200:
                        data = resp.read()
                        if len(data) > 5000:
                            img_path.write_bytes(data)
                            generated = True
                            log(f"  Immagine generata via Pollinations [{model}]")
                            break
                except Exception as e:
                    log(f"  Pollinations [{model}] error: {e}")

        # --- 4. Picsum fallback (foto curate, sempre disponibile) ---
        if not generated:
            log("  Pollinations offline — uso Picsum Photos")
            # Seed per categoria per foto coerenti
            category_seeds = {
                "business": 237, "immigration": 452, "tax": 178,
                "property": 312, "lifestyle": 501, "digital-nomad": 89,
                "tech": 667, "emerging_trends": 730, "tax-legal": 195,
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
                        log(f"  Immagine da Picsum [seed={seed_id}]")
            except Exception as e:
                log(f"  Picsum error: {e}")

        # --- 5. Unsplash fallback (foto reali per categoria) ---
        if not generated:
            log("  Picsum offline — provo Unsplash")
            category_keywords = {
                "business": "bali+business+office",
                "immigration": "bali+visa+passport",
                "tax": "bali+finance+tax",
                "property": "bali+villa+property",
                "lifestyle": "bali+lifestyle+expat",
                "digital-nomad": "bali+coworking+laptop",
                "tech": "bali+technology",
                "emerging_trends": "bali+innovation",
                "tax-legal": "bali+law+legal",
            }
            keyword = category_keywords.get(category, "bali+indonesia")
            url = f"https://source.unsplash.com/1200x630/?{keyword}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "BaliZero/1.0"})
                resp = urllib.request.urlopen(req, timeout=30)
                if resp.status == 200:
                    data = resp.read()
                    if len(data) > 5000:
                        img_path.write_bytes(data)
                        generated = True
                        log(f"  Immagine da Unsplash [{keyword}]")
            except Exception as e:
                log(f"  Unsplash error: {e}")

        if not generated or not img_path.exists():
            log(f"⚠ Generazione immagine fallita — skip")
            return True  # non bloccante

        # Committa su GitHub
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
            log(f"{'✅' if ok else '❌'} Immagine committata: {IMAGE_GH_PATH}")
            return ok
        except Exception as e:
            log(f"⚠ Commit immagine fallito: {e}")
            return True


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

    # Find all untracked/modified translation files for these slugs
    translation_files = []
    for slug in slugs:
        for f in articles_dir.rglob(f"{slug}.*.mdx"):
            translation_files.append(str(f.relative_to(repo_root)))

    if not translation_files:
        log("⚠ Nessun file di traduzione trovato da committare")
        return

    log(f"▶ git commit+push {len(translation_files)} file di traduzione")
    try:
        # Stage files
        subprocess.run(["git", "add"] + translation_files,
                       cwd=str(repo_root), capture_output=True, check=True, timeout=30)
        # Check if there's anything to commit
        status = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=str(repo_root), capture_output=True, timeout=10
        )
        if status.returncode == 0:
            log("⏭ Nessuna modifica staged — traduzioni già committate")
            return
        # Commit
        msg = f"feat(articles): add translations for {', '.join(slugs[:3])}{'...' if len(slugs) > 3 else ''}"
        subprocess.run(
            ["git", "commit", "--no-verify", "-m", msg],
            cwd=str(repo_root), capture_output=True, check=True, timeout=30
        )
        # Push to origin
        push = subprocess.run(
            ["git", "push", "--no-verify", "origin", "main"],
            cwd=str(repo_root), capture_output=True, text=True, timeout=60
        )
        if push.returncode == 0:
            log(f"✅ Traduzioni pushate su GitHub")
        else:
            # Remote diverged — rebase and retry
            log(f"⚠ Push fallito, provo rebase: {push.stderr.strip()[:100]}")
            subprocess.run(
                ["git", "pull", "--rebase", "origin", "main"],
                cwd=str(repo_root), capture_output=True, timeout=60
            )
            push2 = subprocess.run(
                ["git", "push", "--no-verify", "origin", "main"],
                cwd=str(repo_root), capture_output=True, text=True, timeout=60
            )
            log(f"{'✅' if push2.returncode == 0 else '❌'} Push dopo rebase: exit={push2.returncode}")
    except Exception as e:
        log(f"⚠ git commit/push traduzioni fallito (non-bloccante): {e}")


def main():
    log("=" * 50)
    log("🔄 Post-publish poller avviato")

    try:
        result = api_get("/api/intel/post-publish-queue/pending")
        pending = result.get("pending", [])
    except Exception as e:
        log(f"❌ Errore lettura queue: {e}")
        return

    if not pending:
        log("✅ Nessun articolo in coda")
        return

    log(f"📋 {len(pending)} articoli in coda")

    # Pull latest MDX files so translator can find newly published articles
    git_pull_monorepo()

    done_slugs = []
    translated_slugs = []
    for item in pending:
        slug = item["slug"]
        category = item.get("category", "business")
        log(f"📄 {category}/{slug}")
        run_seo(slug, category)
        translate_ok = run_translate(slug, category)
        run_image(slug, category)
        if translate_ok:
            done_slugs.append(slug)
            translated_slugs.append(slug)

    # Committa e pusha le traduzioni su GitHub
    if translated_slugs:
        git_commit_and_push_translations(translated_slugs)

    # Marca come done
    if done_slugs:
        try:
            api_post("/api/intel/post-publish-queue/done", {"slugs": done_slugs})
            log(f"✅ Marcati done: {done_slugs}")
        except Exception as e:
            log(f"⚠ Errore mark done: {e}")

    log("🏁 Poller completato")


if __name__ == "__main__":
    main()
