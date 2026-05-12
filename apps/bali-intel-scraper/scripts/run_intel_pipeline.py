#!/usr/bin/env python3
"""
Intel Pipeline Orchestrator - Full 8-Step Pipeline
Coordinates: Scraping → Validation → Filter → Enrichment → SEO → Approval → Images → Publishing

Usage:
    # Full run (all steps)
    python run_intel_pipeline.py --mode full --categories immigration,tax --limit 10

    # Dry run (no approval/publishing)
    python run_intel_pipeline.py --mode dry-run --limit 5

    # Resume from step
    python run_intel_pipeline.py --resume-from 5_seo

    # Skip steps
    python run_intel_pipeline.py --skip 4_images,6_approval --auto-approve
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import subprocess

# Auto-load .env if present (no dependency on python-dotenv)
_env_file = Path(__file__).parent.parent / '.env'
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, _, val = line.partition('=')
            os.environ.setdefault(key.strip(), val.strip())

# Telegram recipient config: chat_id → lang/name/role
RECIPIENT_CONFIG = {
    "1813875994": {"lang": "id", "name": "Damar", "role": "designer"},
    # Owner is auto-detected as first chat_id not in this config
}

NEWS_ROOM_URL = "https://kita.balizero.com/intelligence/news-room"

# Pipeline steps
PIPELINE_STEPS = [
    '1_scraping',
    '2_validation',
    '2.5_qwen_filter',   # LLM scoring — gemma4:26b, threshold quality_score >= 30 (configurable)
    '2.6_quality_gate',  # 4-dimension quality gate: relevance, urgency, reliability, business impact
    '2.7_verification',  # Cross-check T1 sources + KB for regulatory articles
    '2.8_clustering',    # Semantic clustering — group articles by theme into dossiers
    '2.9_nlm_context',   # NLM legal context — query NB core + deep research temp NB
    '3_enrichment',      # Claude deep enrichment — 1400-2000 word articles per dossier
    '5_seo',             # Gemini SEO optimization
    '6_approval',        # Telegram notification + review file
    '8_images',          # Cover images: Fireworks.ai Flux.1 Dev (fallback: Pollinations.ai) — only T1/featured
    '7_publishing',      # Publish with cover image already in payload
]

class IntelPipeline:
    def __init__(self, config: Dict):
        self.config = config
        self.script_dir = Path(__file__).parent
        self.project_root = self.script_dir.parent
        self.data_dir = self.project_root / 'data'
        self.pipeline_dir = self.data_dir / 'pipeline'
        try:
            self.pipeline_dir.mkdir(exist_ok=True)
            # Test write permission (macOS LaunchAgent may lack Full Disk Access)
            test_file = self.pipeline_dir / '.write_test'
            test_file.write_text('ok')
            test_file.unlink()
        except (PermissionError, OSError):
            self.pipeline_dir = Path('/tmp/intel_pipeline_runs')
            self.pipeline_dir.mkdir(exist_ok=True)
        
        # State tracking
        self.run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.state_file = self.pipeline_dir / f'run_{self.run_id}.json'
        self.state = {
            'run_id': self.run_id,
            'config': config,
            'started_at': datetime.now().isoformat(),
            'steps': {},
            'articles': []
        }
    
    def log(self, message: str, level: str = 'INFO'):
        """Log with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f'[{timestamp}] [{level}] {message}')
        sys.stdout.flush()
    
    def save_state(self):
        """Save pipeline state to disk"""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
        self.log(f'State saved: {self.state_file.name}')
    
    def update_step_status(self, step: str, status: str, data: Dict = None):
        """Update step status in state"""
        self.state['steps'][step] = {
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'data': data or {}
        }
        self.save_state()
    
    def run_step(self, step: str) -> bool:
        """Execute single pipeline step"""
        self.log(f'{"="*60}')
        self.log(f'STEP: {step}')
        self.log(f'{"="*60}')
        
        try:
            if step == '1_scraping':
                return self.step_scraping()
            elif step == '2_validation':
                return self.step_validation()
            elif step == '2.5_qwen_filter':
                return self.step_qwen_filter()
            elif step == '2.6_quality_gate':
                return self.step_quality_gate()
            elif step == '2.7_verification':
                return self.step_verification()
            elif step == '2.8_clustering':
                return self.step_clustering()
            elif step == '2.9_nlm_context':
                return self.step_nlm_context()
            elif step == '3_enrichment':
                return self.step_enrichment()
            elif step == '8_images':
                return self.step_images()
            elif step == '5_seo':
                return self.step_seo()
            elif step == '6_approval':
                return self.step_approval()
            elif step == '7_publishing':
                return self.step_publishing()
            else:
                self.log(f'Unknown step: {step}', 'ERROR')
                return False
        except Exception as e:
            self.log(f'Step {step} failed: {e}', 'ERROR')
            self.update_step_status(step, 'failed', {'error': str(e)})
            return False
    
    def step_scraping(self) -> bool:
        """Step 1: Scrape articles from sources via UnifiedScraper"""
        self.log('Starting article scraping...')

        if self.config.get('dry_run'):
            self.state['articles'] = self._mock_scraped_articles()
            self.update_step_status('1_scraping', 'skipped', {'reason': 'dry_run'})
            return True

        try:
            sys.path.insert(0, str(self.script_dir))
            from unified_scraper import UnifiedScraper
            categories = self.config.get('categories', ['immigration', 'tax', 'business'])
            limit      = self.config.get('limit_per_source', 5)
            
            import asyncio
            scraper    = UnifiedScraper(categories=categories, limit_per_source=limit)
            async def _run_scraper():
                res = await scraper.scrape_all()
                await scraper.close()
                return res
            
            articles   = asyncio.run(_run_scraper())
            self.log(f'Scraped {len(articles)} articles from {scraper.stats.get("sources_processed",0)} sources')

            # Exa augmentation (semantic search)
            exa_stats = {}
            if os.environ.get('EXA_API_KEY'):
                try:
                    from exa_scraper import ExaScraper
                    # Note: ExaScraper categories (immigration, business, tax, emerging_trends,
                    # lifestyle, business_regulations) differ from pipeline categories.
                    # Pass None to run all Exa queries — filtering happens at validation.
                    exa = ExaScraper()
                    # Wrap in daemon thread with 10min timeout to prevent hanging on slow/stuck Exa API.
                    # FIX (2026-03-31): use daemon=True so the thread does NOT block Python exit
                    # when the process finishes — avoids the hang-on-exit that killed the 2026-03-30 run.
                    import threading
                    _exa_result: list = []
                    _exa_done = threading.Event()

                    def _exa_worker():
                        try:
                            _exa_result.extend(exa.search_all())
                        except Exception as _ex:
                            self.log(f'Exa worker error: {_ex}', 'WARN')
                        finally:
                            _exa_done.set()

                    _exa_thread = threading.Thread(target=_exa_worker, daemon=True, name='exa-search')
                    _exa_thread.start()
                    if _exa_done.wait(timeout=600):  # 10min max
                        exa_articles = list(_exa_result)
                    else:
                        self.log('Exa augmentation timed out after 10min — skipping', 'WARN')
                        exa_articles = []
                        # Thread is daemon=True so it will NOT block process exit
                    existing_urls = {a.get('url', '') for a in articles}
                    new_exa = [a for a in exa_articles if a['url'] not in existing_urls]
                    articles.extend(new_exa)
                    exa_stats = {
                        'exa_total': len(exa_articles),
                        'exa_new': len(new_exa),
                        'exa_dupes': len(exa_articles) - len(new_exa),
                        'exa_errors': exa.stats.get('errors', 0),
                    }
                    self.log(f'Exa added {len(new_exa)} unique articles (filtered {len(exa_articles) - len(new_exa)} dupes)')
                except Exception as e:
                    self.log(f'Exa augmentation failed (non-fatal): {e}', 'WARN')
                    exa_stats = {'exa_error': str(e)}
            else:
                self.log('EXA_API_KEY not set, skipping Exa augmentation')

            # intel_radar_findings augmentation (PR-1 §B)
            # Reads canonical signals INSERTed by intel_radar.py (Pro hourly cron)
            # after intel_radar_daily_digest marks them processed=true. Each
            # picked row is marked scraper_picked=true so we never double-fetch.
            radar_stats: dict[str, int] = {}
            if os.environ.get('INTEL_RADAR_PERSIST_DB', 'false').lower() == 'true':
                try:
                    radar_articles, radar_marked = self._fetch_intel_radar_findings()
                    existing_urls = {a.get('url', '') for a in articles}
                    new_radar = [a for a in radar_articles if a.get('url') and a['url'] not in existing_urls]
                    articles.extend(new_radar)
                    radar_stats = {
                        'radar_total': len(radar_articles),
                        'radar_new': len(new_radar),
                        'radar_dupes': len(radar_articles) - len(new_radar),
                        'radar_marked_picked': radar_marked,
                    }
                    self.log(
                        f'intel-radar added {len(new_radar)} unique articles '
                        f'(picked {radar_marked} from intel_radar_findings, filtered '
                        f'{len(radar_articles) - len(new_radar)} dupes)'
                    )
                except Exception as e:
                    self.log(f'intel-radar augmentation failed (non-fatal): {e}', 'WARN')
                    radar_stats = {'radar_error': str(e)}

            self.state['articles'] = articles
            self.update_step_status('1_scraping', 'completed', {
                'articles': len(articles),
                'sources':  scraper.stats.get('sources_processed', 0),
                **exa_stats,
                **radar_stats,
            })
            return True
        except Exception as e:
            self.log(f'Scraping error: {e}', 'ERROR')
            self.state['articles'] = self._mock_scraped_articles()
            self.update_step_status('1_scraping', 'failed', {'error': str(e)})
            return False
    
    def step_validation(self) -> bool:
        """Step 2: Validate articles (URL dedup + title similarity dedup)

        Rule-based, no LLM calls. Deduplicates by:
        1. Exact URL match (already done in scraping, but catch edge cases)
        2. Title Jaccard similarity >= 0.6 (same logic as gemini_validator)
        3. Cross-check against published_articles.json history
        """
        articles = self.state.get('articles', [])
        if not articles:
            self.update_step_status('2_validation', 'skipped', {'reason': 'no_articles'})
            return True

        self.log(f'Validating {len(articles)} articles (dedup + history check)...')

        # Load published history for cross-check
        published_file = self.project_root / 'data' / 'published_articles.json'
        published_titles: list[set[str]] = []
        published_urls: set[str] = set()
        if published_file.exists():
            try:
                with open(published_file) as f:
                    pub_data = json.load(f)
                # Load all history, not just last 200
                for pa in pub_data.get('articles', []):
                    published_urls.add(pa.get('url', ''))
                    words = set(pa.get('title', '').lower().split())
                    if words:
                        published_titles.append(words)
                self.log(f'  Loaded {len(published_urls)} published URLs for history check')
            except Exception as e:
                self.log(f'  Could not load published history: {e}', 'WARN')

        seen_urls: set[str] = set()
        seen_title_words: list[set[str]] = []
        validated = []
        dupes_url = 0
        dupes_title = 0
        dupes_history = 0

        for article in articles:
            url = article.get('url', '')
            title = article.get('title', '')
            title_words = set(title.lower().split())

            # 1. URL dedup (within batch)
            if url in seen_urls:
                dupes_url += 1
                continue

            # 2. URL in published history
            if url in published_urls:
                dupes_history += 1
                continue

            # 3. Title similarity (Jaccard >= 0.6) within batch
            dupe_source = None  # 'batch' or 'history'
            if title_words:
                for prev_words in seen_title_words:
                    if prev_words:
                        intersection = title_words & prev_words
                        union = title_words | prev_words
                        if len(intersection) / len(union) >= 0.6:
                            dupe_source = 'batch'
                            break
                # Also check against published history
                if not dupe_source:
                    for pub_words in published_titles:
                        if pub_words:
                            intersection = title_words & pub_words
                            union = title_words | pub_words
                            if len(intersection) / len(union) >= 0.6:
                                dupe_source = 'history'
                                break

            if dupe_source == 'batch':
                dupes_title += 1
                continue
            if dupe_source == 'history':
                dupes_history += 1
                continue

            # 4. Age validation (discard articles older than 30 days)
            published = article.get('published', '')
            if published:
                try:
                    from dateutil import parser as date_parser
                    pub_date = date_parser.parse(published)
                    # if timezone aware, make current time aware
                    now = datetime.now(pub_date.tzinfo) if pub_date.tzinfo else datetime.now()
                    if (now - pub_date).days > 30:
                        # old article, skip
                        self.log(f"    Skipping old article ({published}): {title[:50]}")
                        continue
                except Exception:
                    pass # if unparseable, we let it pass

            seen_urls.add(url)
            seen_title_words.append(title_words)
            validated.append(article)

        rejected = len(articles) - len(validated)
        self.state['articles'] = validated
        self.log(f'  Validated: {len(validated)} passed, {rejected} rejected '
                 f'(url_dupes={dupes_url}, title_dupes={dupes_title}, history={dupes_history})')
        self.update_step_status('2_validation', 'completed', {
            'input': len(articles),
            'validated': len(validated),
            'rejected': rejected,
            'dupes_url': dupes_url,
            'dupes_title': dupes_title,
            'dupes_history': dupes_history,
        })
        return True
    
    def step_qwen_filter(self) -> bool:
        """Step 2.5: LLM content quality scoring via Ollama (gemma4:26b).

        Evaluates each article for relevance to our audience (expats/investors
        in Indonesia) and assigns a quality score 0-100. Threshold: >= 30.
        ~20-30s per article, ~20 min for 50 articles.
        """
        articles = self.state.get('articles', [])
        if not articles:
            self.update_step_status('2.5_qwen_filter', 'skipped', {'reason': 'no_articles'})
            return True

        self.log(f'Qwen filter: scoring {len(articles)} articles via Ollama...')

        # Check Ollama availability — prefer gemma4:26b (MoE, reliable JSON output)
        import httpx as _httpx
        ollama_url = 'http://localhost:11434'
        ollama_model = None
        try:
            r = _httpx.get(f'{ollama_url}/api/tags', timeout=5)
            models = [m['name'] for m in r.json().get('models', [])]
            # Prefer gemma4 (reliable JSON), fallback to qwen3.5:9b
            for candidate in ['gemma4:26b', 'qwen3.5:9b']:
                if any(candidate in m for m in models):
                    ollama_model = candidate
                    break
            if not ollama_model:
                self.log(f'No suitable model in Ollama ({models}), falling back', 'WARN')
                return self._qwen_filter_fallback(articles)
        except Exception as e:
            self.log(f'Ollama not available ({e}), falling back to keyword filter', 'WARN')
            return self._qwen_filter_fallback(articles)

        self.log(f'Using model: {ollama_model}')

        scored = []
        errors = 0
        import re

        # Process in batches of 10 for efficiency (~15s per batch)
        BATCH_SIZE = 10
        for batch_start in range(0, len(articles), BATCH_SIZE):
            batch = articles[batch_start:batch_start + BATCH_SIZE]
            batch_num = batch_start // BATCH_SIZE + 1
            total_batches = (len(articles) + BATCH_SIZE - 1) // BATCH_SIZE

            # Build compact batch prompt
            article_lines = []
            for j, art in enumerate(batch, 1):
                title = art.get('title', '')[:100]
                text = art.get('text', art.get('content', art.get('summary', '')))[:200]
                source = art.get('source_name', art.get('source', ''))[:30]
                article_lines.append(f"{j}. {title} [{source}] {text}")

            articles_text = '\n'.join(article_lines)
            # Pre-build expected output shape
            example_items = ','.join(f'{{"id":{j+1},"s":__}}' for j in range(min(2, len(batch))))

            prompt = (
                f"Score each article 0-100: relevance for foreign investors/expats in Bali, Indonesia.\n"
                f"Criteria: Indonesia/Bali focus(0-30), Expat relevance(0-25), Actionability(0-20), Timeliness(0-15), Quality(0-10).\n"
                f"IMPORTANT: Articles about OTHER countries (India, Thailand, Malaysia, etc.) that do NOT affect Indonesia MUST score 0-10.\n"
                f"Reply JSON array only. No explanations.\n"
                f"{articles_text}\n"
                f"[{example_items},...]"
            )

            try:
                resp = _httpx.post(
                    f'{ollama_url}/api/generate',
                    json={
                        'model': ollama_model,
                        'prompt': prompt,
                        'stream': False,
                        'options': {'temperature': 0.0, 'num_predict': 40 * len(batch)},
                    },
                    timeout=90 + 20 * len(batch),  # 90s base (cold start) + ~20s per article
                )
                output = resp.json().get('response', '').strip()

                # Strip markdown code blocks
                if '```json' in output:
                    output = output.split('```json')[1].split('```')[0].strip()
                elif '```' in output:
                    output = output.split('```')[1].split('```')[0].strip()

                # Parse JSON array
                arr_start = output.find('[')
                arr_end = output.rfind(']') + 1
                results = []
                if arr_start >= 0 and arr_end > arr_start:
                    try:
                        results = json.loads(output[arr_start:arr_end])
                    except json.JSONDecodeError:
                        # Try to fix truncated array by closing it
                        truncated = output[arr_start:]
                        # Find last complete object
                        last_brace = truncated.rfind('}')
                        if last_brace > 0:
                            try:
                                results = json.loads(truncated[:last_brace + 1] + ']')
                            except json.JSONDecodeError:
                                pass

                # If we couldn't parse array, try individual objects via regex
                if not results:
                    for m in re.finditer(r'\{[^}]+\}', output):
                        try:
                            results.append(json.loads(m.group()))
                        except json.JSONDecodeError:
                            pass

                # Map results back to articles
                result_by_id = {}
                for r in results:
                    rid = r.get('id', 0)
                    result_by_id[rid] = r

                for j, art in enumerate(batch, 1):
                    r = result_by_id.get(j, {})
                    if r:
                        score = min(100, max(0, int(r.get('s', r.get('score', 50)))))
                        art['quality_score'] = score
                        art['qwen_score'] = score / 10
                        # tier stays as assigned by scraper (source-based)
                    else:
                        art['qwen_score'] = art.get('quality_score', 50) / 10
                        errors += 1
                    art['qwen_category'] = art.get('category', 'general')
                    scored.append(art)

                # Log batch results
                batch_scores = [a.get('quality_score', 50) for a in batch]
                self.log(f'  Batch {batch_num}/{total_batches}: {len(results)}/{len(batch)} scored '
                         f'(avg={sum(batch_scores)/len(batch_scores):.0f})')
                for art in batch:
                    score = art.get('quality_score', 50)
                    tier = art.get('tier', 'unknown')
                    if score != 50:  # Only log actually scored articles
                        self.log(f'    {score:3d}/100 [{tier}] {art["title"][:60]}')

            except Exception as e:
                self.log(f'  Batch {batch_num} error: {e}', 'WARN')
                errors += len(batch)
                for art in batch:
                    art['qwen_score'] = art.get('quality_score', 50) / 10
                    art['qwen_category'] = art.get('category', 'general')
                    scored.append(art)

        # Hard geo-filter: demote articles about other countries (Qwen sometimes scores them high)
        _OTHER_COUNTRY_KW = ("india ", "indian ", "thailand ", "thai ", "vietnam ", "philippines ",
                             "filipino ", "malaysia ", "malaysian ", "singapore ", "japan ", "china ",
                             "korea ", "cambodia ", "myanmar ", "laos ")
        _INDONESIA_KW = ("indonesia", "bali", "kitas", "kitap", "pma", "kbli", "imigrasi",
                         "djp", "pajak", "denpasar", "ngurah rai", "izin tinggal")
        geo_demoted = 0
        for art in scored:
            text = f"{art.get('title', '')} {art.get('summary', '')}".lower()
            is_other = any(kw in text for kw in _OTHER_COUNTRY_KW)
            is_indo = any(kw in text for kw in _INDONESIA_KW)
            if is_other and not is_indo:
                art['quality_score'] = min(art.get('quality_score', 0), 10)
                art['qwen_score'] = art['quality_score'] / 10
                geo_demoted += 1
        if geo_demoted:
            self.log(f'  Geo-filter: {geo_demoted} non-Indonesia articles demoted to ≤10')

        # Apply threshold
        threshold = self.config.get('min_score', 30)
        passed = [a for a in scored if a.get('quality_score', 50) >= threshold]
        filtered = [a for a in scored if a.get('quality_score', 50) < threshold]

        # Sort by score descending
        passed.sort(key=lambda a: a.get('quality_score', 0), reverse=True)

        self.state['articles'] = passed
        avg_score = sum(a.get('quality_score', 0) for a in scored) / max(len(scored), 1)
        self.log(f'Qwen filter: {len(passed)} passed / {len(filtered)} filtered '
                 f'(threshold={threshold}, avg={avg_score:.0f}, errors={errors})')
        self.update_step_status('2.5_qwen_filter', 'completed', {
            'scored': len(scored),
            'passed': len(passed),
            'filtered': len(filtered),
            'avg_score': round(avg_score, 1),
            'errors': errors,
            'method': 'qwen3.5_27b',
        })
        return True

    def _qwen_filter_fallback(self, articles: List[Dict]) -> bool:
        """Fallback when Ollama is unavailable: pass all with default scores."""
        for a in articles:
            # Ensure quality_score is always set (downstream steps depend on it)
            if 'quality_score' not in a:
                a['quality_score'] = 50
            a['qwen_score'] = a.get('quality_score', 50) / 10
            a['qwen_category'] = a.get('category', 'general')
        self.state['articles'] = articles
        self.log(f'Keyword fallback: all {len(articles)} articles passed')
        self.update_step_status('2.5_qwen_filter', 'completed', {
            'passed': len(articles), 'filtered': 0, 'method': 'fallback'
        })
        return True

    # ------------------------------------------------------------------
    # Step 2.6 — Quality Gate (4-dimension scoring)
    # ------------------------------------------------------------------

    def step_quality_gate(self) -> bool:
        """Step 2.6: 4-dimension quality gate — relevance, urgency, reliability, business impact.

        Evaluates each article through the quality gate and routes:
          - composite ≥ 0.70 → auto_publish (fast-tracked, tagged)
          - 0.40 ≤ composite < 0.70 → review (default path, continues pipeline)
          - composite < 0.40 → archive (removed from pipeline, saved to state)

        Articles tagged with quality_gate_* fields for downstream steps.
        """
        articles = self.state.get('articles', [])
        if not articles:
            self.update_step_status('2.6_quality_gate', 'skipped', {'reason': 'no_articles'})
            return True

        self.log(f'Quality Gate: evaluating {len(articles)} articles...')

        try:
            sys.path.insert(0, str(self.script_dir))
            from quality_gate import QualityGateConfig, evaluate_batch, GateDecision
        except ImportError:
            self.log('quality_gate module not found — passing all articles through', 'WARN')
            self.update_step_status('2.6_quality_gate', 'skipped', {'reason': 'module_not_found'})
            return True

        config = QualityGateConfig.load()
        results = evaluate_batch(articles, config)

        auto_publish = []
        review = []
        archived = []

        for art, result in results:
            art['quality_gate'] = result.to_dict()
            art['quality_gate_composite'] = result.composite
            art['quality_gate_decision'] = result.decision.value

            if result.decision == GateDecision.AUTO_PUBLISH:
                art['featured'] = True
                auto_publish.append(art)
            elif result.decision == GateDecision.REVIEW:
                review.append(art)
            else:
                archived.append(art)

        # Log per-article scores
        for art, result in results:
            decision = result.decision.value.upper()
            self.log(
                f'  {result.composite:.2f} [{decision:12s}] '
                f'R={result.relevance:.2f} U={result.urgency:.2f} '
                f'L={result.reliability:.2f} B={result.business_impact:.2f} '
                f'| {art.get("title", "")[:55]}'
            )

        # Pipeline continues with auto_publish + review articles
        # Archived articles are saved in state but removed from active pipeline
        self.state['articles'] = auto_publish + review
        self.state['archived_articles'] = self.state.get('archived_articles', []) + archived

        self.log(
            f'Quality Gate: {len(auto_publish)} auto-publish, '
            f'{len(review)} review, {len(archived)} archived '
            f'(thresholds: publish≥{config.threshold_auto_publish}, '
            f'review≥{config.threshold_review})'
        )

        self.update_step_status('2.6_quality_gate', 'completed', {
            'evaluated': len(articles),
            'auto_publish': len(auto_publish),
            'review': len(review),
            'archived': len(archived),
            'avg_composite': round(
                sum(r.composite for _, r in results) / max(len(results), 1), 3
            ),
            'thresholds': {
                'auto_publish': config.threshold_auto_publish,
                'review': config.threshold_review,
            },
        })
        return True

    # ------------------------------------------------------------------
    # Step 2.7 — Verification
    # ------------------------------------------------------------------

    # Categories that require T1 source verification
    REGULATORY_CATEGORIES = {'immigration', 'tax', 'business', 'legal', 'property', 'business_regulations'}

    def step_verification(self) -> bool:
        """Step 2.7: Cross-check articles against T1 official sources + KB.

        For regulatory articles (immigration, tax, business, legal):
          - Search Exa for official government sources confirming the news
          - Query Qdrant KB for existing knowledge on the topic
          - Mark as verified_t1 / unverified / kb_match

        For non-regulatory articles (lifestyle, tech):
          - Count independent sources in current batch reporting same topic
          - Mark as multi_source / single_source
        """
        articles = self.state.get('articles', [])
        if not articles:
            self.update_step_status('2.7_verification', 'skipped', {'reason': 'no_articles'})
            return True

        self.log(f'Verification: checking {len(articles)} articles...')

        # Separate regulatory vs non-regulatory
        regulatory = [a for a in articles if a.get('qwen_category', a.get('category', '')) in self.REGULATORY_CATEGORIES]
        non_regulatory = [a for a in articles if a not in regulatory]

        self.log(f'  Regulatory: {len(regulatory)}, Non-regulatory: {len(non_regulatory)}')

        # --- Verify regulatory articles via Exa T1 search ---
        exa_key = os.environ.get('EXA_API_KEY', '')
        verified_count = 0
        kb_match_count = 0

        if regulatory and exa_key:
            try:
                from exa_py import Exa
                exa = Exa(exa_key)

                # Official Indonesian government domains
                t1_domains = [
                    'kemenkumham.go.id', 'imigrasi.go.id', 'pajak.go.id',
                    'oss.go.id', 'bkpm.go.id', 'kemenkeu.go.id', 'djp.go.id',
                    'hukumonline.com', 'peraturan.go.id', 'jdih.kemenkumham.go.id',
                ]

                def _title_overlap(a: str, b: str) -> float:
                    """Jaccard similarity between two titles (word-level)."""
                    wa = set(a.lower().split())
                    wb = set(b.lower().split())
                    if not wa or not wb:
                        return 0.0
                    return len(wa & wb) / len(wa | wb)

                for art in regulatory:
                    title = art.get('title', '')
                    search_query = title[:80]

                    try:
                        r = exa.search(
                            query=search_query,
                            num_results=5,
                            include_domains=t1_domains,
                            type="keyword",  # Precise matching, no semantic expansion
                        )
                        # Filter results: only count those with title overlap >= 0.15
                        # (at least a few shared keywords with the article)
                        relevant = []
                        for res in (r.results or []):
                            res_title = getattr(res, 'title', '') or ''
                            overlap = _title_overlap(title, res_title)
                            if overlap >= 0.15:
                                relevant.append({'title': res_title, 'url': res.url, 'overlap': round(overlap, 2)})

                        if relevant:
                            art['verification'] = {
                                'status': 'verified_t1',
                                'source_count': len(relevant),
                                't1_sources': relevant[:3],
                            }
                            verified_count += 1
                            self.log(f'    T1 verified: {title[:50]}... ({len(relevant)} relevant official sources)')
                        else:
                            art['verification'] = {
                                'status': 'unverified',
                                'source_count': 0,
                                'note': f'Exa returned {len(r.results or [])} results but none relevant',
                            }
                            self.log(f'    Unverified: {title[:50]}... (no relevant T1 source)')
                    except Exception as e:
                        art['verification'] = {'status': 'check_failed', 'error': str(e)}

                self.log(f'  Exa T1 check: {verified_count}/{len(regulatory)} verified')

            except ImportError:
                self.log('  exa_py not installed, skipping T1 verification', 'WARN')
                for art in regulatory:
                    art['verification'] = {'status': 'skipped', 'reason': 'no_exa'}
        elif regulatory:
            self.log('  EXA_API_KEY not set, skipping T1 verification', 'WARN')
            for art in regulatory:
                art['verification'] = {'status': 'skipped', 'reason': 'no_api_key'}

        # --- KB cross-check via Qdrant ---
        qdrant_url = os.environ.get('QDRANT_URL', 'http://localhost:6333')
        openai_key = os.environ.get('OPENAI_API_KEY', '')

        if openai_key:
            try:
                import httpx as _httpx

                for art in articles:
                    title = art.get('title', '')
                    # Get embedding for title
                    emb_resp = _httpx.post(
                        'https://api.openai.com/v1/embeddings',
                        headers={'Authorization': f'Bearer {openai_key}'},
                        json={'model': 'text-embedding-3-small', 'input': title},
                        timeout=10,
                    )
                    if emb_resp.status_code != 200:
                        continue
                    vector = emb_resp.json()['data'][0]['embedding']

                    # Search Qdrant for similar content
                    q_resp = _httpx.post(
                        f'{qdrant_url}/collections/intel_articles/points/search',
                        json={'vector': vector, 'limit': 3, 'score_threshold': 0.75},
                        timeout=10,
                    )
                    if q_resp.status_code == 200:
                        results = q_resp.json().get('result', [])
                        if results:
                            kb_match_count += 1
                            art.setdefault('verification', {})['kb_matches'] = [
                                {
                                    'title': r['payload'].get('title', ''),
                                    'score': round(r['score'], 3),
                                }
                                for r in results[:3]
                            ]
                            art['verification']['has_kb_context'] = True

                self.log(f'  KB cross-check: {kb_match_count}/{len(articles)} have existing KB context')

            except Exception as e:
                self.log(f'  KB cross-check failed (non-fatal): {e}', 'WARN')
        else:
            self.log('  OPENAI_API_KEY not set, skipping KB cross-check', 'WARN')

        # --- Non-regulatory: count independent sources ---
        # Articles with same theme in current batch = multi_source
        for art in non_regulatory:
            if not art.get('verification'):
                art['verification'] = {'status': 'single_source', 'source_count': 1}

        self.state['articles'] = articles
        self.update_step_status('2.7_verification', 'completed', {
            'total': len(articles),
            'regulatory': len(regulatory),
            'verified_t1': verified_count,
            'kb_matches': kb_match_count,
        })
        return True

    # ------------------------------------------------------------------
    # Step 2.8 — Semantic Clustering
    # ------------------------------------------------------------------

    def step_clustering(self) -> bool:
        """Step 2.8: Group articles by semantic similarity into dossiers.

        Uses OpenAI embeddings (text-embedding-3-small) to compute title+content
        similarity. Articles with cosine similarity >= 0.70 are grouped together.
        Each cluster becomes a 'dossier' with a primary article and supporting sources.
        """
        articles = self.state.get('articles', [])
        if not articles or len(articles) <= 1:
            self.update_step_status('2.8_clustering', 'skipped', {'reason': 'too_few_articles'})
            return True

        self.log(f'Clustering: {len(articles)} articles...')

        openai_key = os.environ.get('OPENAI_API_KEY', '')
        if not openai_key:
            self.log('  OPENAI_API_KEY not set, skipping clustering', 'WARN')
            # Wrap each article as its own single-item dossier
            for art in articles:
                art['dossier'] = {
                    'is_primary': True,
                    'cluster_id': art.get('url', ''),
                    'cluster_size': 1,
                    'supporting_sources': [],
                }
            self.update_step_status('2.8_clustering', 'skipped', {'reason': 'no_api_key'})
            return True

        import httpx as _httpx

        # 1. Get embeddings for all articles (batch call)
        texts = []
        for art in articles:
            title = art.get('title', '')
            content = art.get('text', art.get('content', art.get('summary', '')))[:300]
            texts.append(f"{title}. {content}")

        try:
            emb_resp = _httpx.post(
                'https://api.openai.com/v1/embeddings',
                headers={'Authorization': f'Bearer {openai_key}'},
                json={'model': 'text-embedding-3-small', 'input': texts},
                timeout=30,
            )
            emb_resp.raise_for_status()
            embeddings = [d['embedding'] for d in sorted(emb_resp.json()['data'], key=lambda x: x['index'])]
        except Exception as e:
            self.log(f'  Embedding API failed: {e}', 'WARN')
            for art in articles:
                art['dossier'] = {'is_primary': True, 'cluster_id': art.get('url', ''), 'cluster_size': 1, 'supporting_sources': []}
            self.update_step_status('2.8_clustering', 'failed', {'error': str(e)})
            return True

        # 2. Compute cosine similarity matrix and cluster
        import math

        def cosine_sim(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

        SIMILARITY_THRESHOLD = 0.60
        n = len(articles)
        assigned = [False] * n
        clusters: list[list[int]] = []

        # Greedy clustering: for each unassigned article, find all similar ones
        # Compare against ANY article already in the cluster (not just the seed)
        for i in range(n):
            if assigned[i]:
                continue
            cluster = [i]
            assigned[i] = True
            # Iteratively expand: check if unassigned articles are similar to any cluster member
            changed = True
            while changed:
                changed = False
                for j in range(n):
                    if assigned[j]:
                        continue
                    # Check similarity against all current cluster members
                    max_sim = max(cosine_sim(embeddings[k], embeddings[j]) for k in cluster)
                    if max_sim >= SIMILARITY_THRESHOLD:
                        cluster.append(j)
                        assigned[j] = True
                        changed = True
            clusters.append(cluster)

        # 3. Build dossiers
        dossiers = []
        for cluster_idx, cluster in enumerate(clusters):
            # Primary = highest quality_score in cluster, with T1 preferred
            cluster_articles = [articles[i] for i in cluster]
            cluster_articles.sort(
                key=lambda a: (
                    {'T1': 0, 'T2': 1, 'T3': 2}.get(a.get('tier', 'T3'), 2),
                    -a.get('quality_score', 50),
                ),
            )
            primary = cluster_articles[0]
            supporting = cluster_articles[1:]

            cluster_id = f'cluster_{cluster_idx}'

            # Tag primary article
            primary['dossier'] = {
                'is_primary': True,
                'cluster_id': cluster_id,
                'cluster_size': len(cluster_articles),
                'supporting_sources': [],
            }

            # Build supporting sources summary for enrichment context
            for sup in supporting:
                source_info = {
                    'title': sup.get('title', ''),
                    'source': sup.get('source_name', sup.get('source', '')),
                    'tier': sup.get('tier', 'T3'),
                    'url': sup.get('url', ''),
                    'key_text': sup.get('text', sup.get('content', ''))[:300],
                }
                # Include verification status if available
                if sup.get('verification'):
                    source_info['verification'] = sup['verification'].get('status', 'unknown')
                primary['dossier']['supporting_sources'].append(source_info)

                # Mark supporting articles as non-primary
                sup['dossier'] = {
                    'is_primary': False,
                    'cluster_id': cluster_id,
                    'merged_into': primary.get('title', ''),
                }

            dossiers.append(primary)

        # 4. Replace articles with dossier primaries only
        # (supporting articles are embedded inside primary's dossier)
        self.state['articles'] = dossiers

        singles = sum(1 for d in dossiers if d['dossier']['cluster_size'] == 1)
        merged = sum(1 for d in dossiers if d['dossier']['cluster_size'] > 1)
        total_merged_in = len(articles) - len(dossiers)

        self.log(f'  Clusters: {len(dossiers)} dossiers from {len(articles)} articles')
        self.log(f'  Single-article: {singles}, Multi-source: {merged} (absorbed {total_merged_in} articles)')
        for d in dossiers:
            size = d['dossier']['cluster_size']
            marker = f'[{size} sources]' if size > 1 else ''
            self.log(f'    {d["quality_score"]:3d}/100 [{d["tier"]}] {d["title"][:55]} {marker}')

        self.update_step_status('2.8_clustering', 'completed', {
            'input_articles': len(articles),
            'output_dossiers': len(dossiers),
            'single_article': singles,
            'multi_source': merged,
            'articles_merged': total_merged_in,
        })
        return True

    # ------------------------------------------------------------------
    # Step 2.9 — NLM Legal Context
    # ------------------------------------------------------------------

    def step_nlm_context(self) -> bool:
        """Step 2.9: Query NotebookLM for legal context on top regulatory dossiers.

        Phase A: Read-only query on NB core (NB-2/3/4/5/6) for existing legal basis.
        Phase B: If insufficient, Deep Research in temporary NB for web findings.

        NB core notebooks are NEVER modified. Web findings go to temp NBs only.
        Pending sources saved to data/pending_sources/ for human approval.
        """
        articles = self.state.get('articles', [])
        if not articles:
            self.update_step_status('2.9_nlm_context', 'skipped', {'reason': 'no_articles'})
            return True

        if self.config.get('dry_run'):
            self.log('Dry run — skipping NLM legal context')
            self.update_step_status('2.9_nlm_context', 'skipped', {'reason': 'dry_run'})
            return True

        try:
            sys.path.insert(0, str(self.script_dir))
            from nlm_research_step import run_nlm_legal_context

            self.state['articles'] = run_nlm_legal_context(articles, log_fn=self.log)

            # Count results
            with_context = sum(1 for a in self.state['articles']
                               if a.get('nlm_context', {}).get('phase_a_status') == 'ok')
            with_web = sum(1 for a in self.state['articles']
                           if a.get('nlm_context', {}).get('phase_b_status') == 'ok')

            self.update_step_status('2.9_nlm_context', 'completed', {
                'total_articles': len(articles),
                'enriched_with_legal': with_context,
                'enriched_with_web': with_web,
            })
            return True

        except Exception as e:
            self.log(f'NLM context step failed (non-fatal): {e}', 'WARN')
            self.update_step_status('2.9_nlm_context', 'failed', {'error': str(e)})
            # Graceful degradation — continue pipeline without NLM context
            return True

    # ------------------------------------------------------------------
    # Article selection for enrichment
    # ------------------------------------------------------------------

    def _select_top_articles(self, articles: List[Dict], max_count: int) -> List[Dict]:
        """Select top articles for enrichment using tier + score + category diversity.

        Priority: T1 first, then T2 by score, then T3.
        Ensures at least 1 article per category (if available).
        """
        if len(articles) <= max_count:
            return articles

        # Sort by tier priority (T1=0, T2=1, T3=2) then by quality_score desc
        tier_order = {'T1': 0, 'T2': 1, 'T3': 2}
        ranked = sorted(
            articles,
            key=lambda a: (tier_order.get(a.get('tier', 'T3'), 2), -a.get('quality_score', 50))
        )

        # Ensure category diversity: pick best from each category first
        selected: list[Dict] = []
        selected_ids: set[str] = set()
        categories_seen: set[str] = set()

        # Pass 1: one per category (best by tier+score)
        for article in ranked:
            cat = article.get('qwen_category', article.get('category', 'general'))
            aid = article.get('id', article.get('url', ''))
            if cat not in categories_seen and aid not in selected_ids:
                selected.append(article)
                selected_ids.add(aid)
                categories_seen.add(cat)
                if len(selected) >= max_count:
                    break

        # Pass 2: fill remaining slots from ranked list
        for article in ranked:
            if len(selected) >= max_count:
                break
            aid = article.get('id', article.get('url', ''))
            if aid not in selected_ids:
                selected.append(article)
                selected_ids.add(aid)

        return selected

    def step_enrichment(self) -> bool:
        """Step 3: Enrich articles with Claude via proxy.

        Pre-selects top N articles (default 15) by tier/score/diversity
        before sending to Claude for enrichment (~30s each).
        """
        articles = self.state.get('articles', [])
        if not articles:
            self.log('No articles to enrich', 'WARN')
            self.update_step_status('3_enrichment', 'skipped', {'reason': 'no_articles'})
            return True

        if self.config.get('dry_run'):
            self.update_step_status('3_enrichment', 'skipped', {'reason': 'dry_run'})
            return True

        # Smart selection: pick top N from potentially 100+ articles
        max_enrich = self.config.get('max_enrich', 15)
        top_articles = self._select_top_articles(articles, max_enrich)

        self.log(f'Selected {len(top_articles)}/{len(articles)} articles for enrichment '
                 f'(tiers: {", ".join(sorted(set(a.get("tier","?") for a in top_articles)))})')

        try:
            sys.path.insert(0, str(self.script_dir))
            from claude_cli_enricher import batch_enrich_articles
            enriched = batch_enrich_articles(top_articles, max_articles=max_enrich)

            # Merge enriched back: enriched articles first, then remaining unenriched
            enriched_urls = {a.get('url', '') for a in enriched}
            remaining = [a for a in articles if a.get('url', '') not in enriched_urls]
            self.state['articles'] = enriched + remaining

            ok = sum(1 for a in enriched if a.get('enrichment'))
            self.log(f'Enriched {ok}/{len(enriched)} articles ({len(remaining)} unenriched kept)')

            # Generate intel digest — recap of ALL scraped topics (enriched + unenriched)
            digest = self._generate_intel_digest(enriched, remaining)
            if digest:
                self.state['intel_digest'] = digest
                self.log(f'Intel digest generated ({len(digest.get("topics", []))} topics)')

            self.update_step_status('3_enrichment', 'completed', {
                'total_input': len(articles),
                'selected': len(top_articles),
                'enriched': ok,
                'unenriched_kept': len(remaining),
                'digest_generated': bool(digest),
            })
            return True
        except Exception as e:
            self.log(f'Enrichment error: {e}', 'ERROR')
            self.update_step_status('3_enrichment', 'failed', {'error': str(e)})
            return False
    
    def _generate_intel_digest(self, enriched: List[Dict], unenriched: List[Dict]) -> Optional[Dict]:
        """Generate a recap article summarizing ALL scraped topics.

        This gives visibility to unenriched/scartati articles so the user
        can "rescue" interesting topics that weren't selected for deep enrichment.
        Uses Claude MAX proxy (same as enricher).
        """
        all_articles = enriched + unenriched
        if not all_articles:
            return None

        # Build a concise list of all articles for the digest prompt
        article_lines = []
        for i, a in enumerate(all_articles, 1):
            tier = a.get('tier', '?')
            cat = a.get('category', '?')
            title = a.get('title', '')[:80]
            source = a.get('source_name', a.get('source', ''))[:30]
            enriched_flag = '✅' if a.get('enrichment') else '⬜'
            summary = (a.get('summary') or a.get('text', ''))[:150]
            article_lines.append(
                f"{i}. [{tier}] {cat} | {title}\n   Source: {source} | Enriched: {enriched_flag}\n   {summary}"
            )

        articles_text = '\n'.join(article_lines[:80])  # Cap at 80 to stay within context

        prompt = f"""You are an intelligence analyst for Bali Zero, a business consultancy for foreigners in Indonesia.

Below are {len(all_articles)} articles scraped today by our intel pipeline. {len(enriched)} were selected for deep enrichment (marked ✅), the rest (⬜) were not.

YOUR TASK: Write an "Intel Digest" — a concise recap covering ALL major topics found today, organized by theme. This helps our team spot interesting stories among the unenriched articles.

ARTICLES:
{articles_text}

OUTPUT FORMAT (strict JSON only, no markdown):
{{
  "digest_title": "Intel Digest — [date]",
  "summary": "2-3 sentence overview of today's intel landscape",
  "topics": [
    {{
      "theme": "topic name",
      "category": "immigration|business|tax|emerging_trends|lifestyle|business_regulations",
      "key_points": ["point 1", "point 2"],
      "notable_articles": [1, 5, 12],
      "has_unenriched_gems": true
    }}
  ],
  "rescue_candidates": [
    {{
      "article_index": 23,
      "title": "article title",
      "reason": "why this deserves attention"
    }}
  ]
}}

IMPORTANT:
- Cover ALL categories, not just enriched ones
- Flag unenriched articles that look valuable (rescue_candidates)
- Output ONLY valid JSON
"""

        try:
            import httpx as _httpx
            proxy_url = None
            for url in ['http://localhost:13456/v1', 'http://localhost:3456/v1']:
                try:
                    r = _httpx.get(f'{url}/models', timeout=5)
                    if r.status_code == 200 and 'claude' in r.text:
                        proxy_url = url
                        break
                except (_httpx.TimeoutException, _httpx.ConnectError):
                    continue

            if not proxy_url:
                self.log('Claude MAX proxy not available for digest generation', 'WARN')
                return None

            resp = _httpx.post(
                f'{proxy_url}/chat/completions',
                json={
                    'model': 'claude-sonnet-4-5-20250514',
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': 4000,
                    'temperature': 0.3,
                },
                timeout=120,
            )

            if resp.status_code == 200:
                import re
                content = resp.json()['choices'][0]['message']['content']
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    digest = json.loads(json_match.group())
                    digest['generated_at'] = datetime.now().isoformat()
                    digest['total_articles'] = len(all_articles)
                    digest['enriched_count'] = len(enriched)
                    digest['unenriched_count'] = len(unenriched)
                    return digest

            self.log(f'Digest generation returned status {resp.status_code}', 'WARN')
            return None

        except Exception as e:
            self.log(f'Intel digest generation failed (non-fatal): {e}', 'WARN')
            return None

    def step_images(self) -> bool:
        """Step 8: Generate cover images via Fireworks.ai Flux.1 Dev (fallback: Pollinations.ai).
        Runs BEFORE publishing — only for T1/featured articles to avoid wasting API credits."""
        self.log('Generating images...')

        if self.config.get('skip_images'):
            self.log('Images skipped by config')
            self.update_step_status('8_images', 'skipped', {'reason': 'config'})
            return True

        # Only generate for T1 or featured articles (not all enriched)
        # These are the articles that will actually be highlighted on balizero.com
        all_enriched = [a for a in self.state.get('articles', []) if a.get('enrichment')]
        published = [a for a in all_enriched if a.get('tier') == 'T1' or a.get('featured')]
        if not published:
            # Fallback: if no T1/featured, take top-scored articles (up to 5)
            published = sorted(all_enriched, key=lambda a: a.get('quality_score', 0), reverse=True)[:5]
        if not published:
            self.log('No articles for image generation', 'WARN')
            self.update_step_status('8_images', 'skipped', {'reason': 'no_articles'})
            return True

        self.log(f'Generating images for {len(published)} T1/featured articles (of {len(all_enriched)} enriched)')

        # Fireworks.ai Flux.1 Dev (primary) → Pollinations.ai (fallback)
        script = self.script_dir / 'fireworks_image_generator.py'
        if not script.exists():
            self.log('fireworks_image_generator.py not found — skipping images', 'WARN')
            self.update_step_status('8_images', 'skipped', {'reason': 'script_missing'})
            return True

        # Save current state so the image generator can read articles
        self.save_state()

        result = subprocess.run(
            [sys.executable, str(script), str(self.state_file)],
            capture_output=True, text=True, timeout=1800,  # 30min max (~2min/image × 15)
            cwd=str(self.script_dir),
        )

        if result.returncode != 0:
            stderr_full = result.stderr
            stdout_full = result.stdout
            self.log(f'Image generation failed (exit {result.returncode}): {stderr_full[-500:]}', 'ERROR')
            if stdout_full:
                self.log(f'stdout: {stdout_full[-300:]}')
            self.update_step_status('8_images', 'failed', {'error': stderr_full[-500:]})
            return self.config.get('continue_on_error', False)

        # Reload state (image generator updates it with image_path/image_url)
        try:
            updated_state = json.loads(self.state_file.read_text())
            self.state['articles'] = updated_state.get('articles', self.state['articles'])
        except Exception as e:
            self.log(f'Warning: could not reload state after images: {e}', 'WARN')

        all_articles = self.state.get('articles', [])
        images_count = sum(1 for a in all_articles if a.get('image_path'))
        self.log(f'Images generated: {images_count}/{len(published)}')

        # Upload cover images sugli articoli già pubblicati
        import asyncio as _asyncio2
        import httpx as _httpx2
        import base64 as _b64
        import os as _os2
        BACKEND_URL2 = _os2.environ.get('BACKEND_URL', 'https://nuzantara-rag.fly.dev')
        API_KEY2     = _os2.environ.get('SCRAPER_API_KEY', '')

        async def _upload_covers():
            uploaded = 0
            async with _httpx2.AsyncClient(timeout=60) as c:
                for art in self.state.get('articles', []):
                    item_id   = art.get('_published_item_id')
                    intel_type = art.get('_published_intel_type', 'news')
                    img_path  = art.get('image_path')
                    if not (item_id and img_path):
                        continue
                    from pathlib import Path as _PL
                    p = _PL(img_path)
                    if not p.exists() or p.stat().st_size < 5000:
                        continue
                    try:
                        img_b64 = _b64.b64encode(p.read_bytes()).decode('utf-8')
                        r = await c.post(
                            f"{BACKEND_URL2}/api/intel/staging/{intel_type}/{item_id}/cover",
                            json={"cover_image_base64": img_b64, "cover_image_filename": p.name},
                            headers={"X-API-Key": API_KEY2}
                        )
                        if r.status_code in (200, 201):
                            self.log(f'Cover uploaded for {item_id}')
                            uploaded += 1
                        else:
                            self.log(f'Cover upload failed for {item_id}: {r.text}', 'WARN')
                    except Exception as e:
                        self.log(f'Cover upload error for {item_id}: {e}', 'WARN')
                    await _asyncio2.sleep(2)
            return uploaded

        covers_uploaded = _asyncio2.run(_upload_covers())
        self.log(f'Cover images uploaded: {covers_uploaded}/{images_count}')
        self.update_step_status('8_images', 'completed', {'images_generated': images_count, 'covers_uploaded': covers_uploaded})
        return True
    
    def step_seo(self) -> bool:
        """Step 5: SEO optimization via Gemini.

        Generates meta_title, meta_description, keywords, schema_org JSON-LD,
        and Open Graph tags for enriched articles using gemini_seo_optimizer.
        """
        enriched = [a for a in self.state.get('articles', []) if a.get('enrichment')]
        if not enriched:
            self.log('No enriched articles for SEO optimization')
            self.update_step_status('5_seo', 'skipped', {'reason': 'no_enriched_articles'})
            return True

        if self.config.get('skip_seo'):
            self.log('SEO: skipped by config (--skip-seo)')
            self.update_step_status('5_seo', 'skipped', {'reason': 'config'})
            return True

        if self.config.get('dry_run'):
            self.log('SEO: skipped (dry run)')
            self.update_step_status('5_seo', 'skipped', {'reason': 'dry_run'})
            return True

        self.log(f'Running SEO optimization on {len(enriched)} enriched articles...')

        try:
            sys.path.insert(0, str(self.script_dir))
            from gemini_seo_optimizer import SEOOptimizer

            optimizer = SEOOptimizer()
            optimized = optimizer.optimize_batch(enriched)

            # Merge SEO data back into state articles
            seo_by_url = {a.get('url', ''): a.get('seo') for a in optimized if a.get('seo')}
            for article in self.state['articles']:
                url = article.get('url', '')
                if url in seo_by_url:
                    article['seo'] = seo_by_url[url]
                    article['seo_optimized_at'] = datetime.now().isoformat()

            ok = optimizer.stats.get('optimized', 0)
            failed = optimizer.stats.get('failed', 0)
            self.log(f'SEO: {ok} optimized, {failed} failed')
            self.update_step_status('5_seo', 'completed', {
                'optimized': ok,
                'failed': failed,
                'total': len(enriched),
            })
            return True

        except Exception as e:
            self.log(f'SEO optimization error (non-fatal): {e}', 'WARN')
            self.update_step_status('5_seo', 'failed', {'error': str(e)})
            # Non-fatal: pipeline continues without SEO
            return True
    
    def step_approval(self) -> bool:
        """Step 6: Save all enriched articles to a review file + notify owner via Telegram.

        Creates a single text file with all enriched articles for review.
        Sends Telegram notification ONLY to the owner (first chat ID).
        With --auto-approve, skips this step entirely.
        """
        self.log('Submitting for approval...')

        if self.config.get('auto_approve'):
            self.log('Auto-approve enabled, skipping approval step')
            self.update_step_status('6_approval', 'auto_approved')
            return True

        enriched = [a for a in self.state.get('articles', []) if a.get('enrichment')]
        if not enriched:
            self.log('No enriched articles to approve')
            self.update_step_status('6_approval', 'skipped', {'reason': 'no_enriched'})
            return True

        # Auto-assign featured status
        # Featured = T1 with score >= 80 OR multi-source dossier with score >= 75
        for art in enriched:
            dossier = art.get('dossier', {})
            score = art.get('quality_score', 0)
            tier = art.get('tier', 'T3')
            is_multi = dossier.get('cluster_size', 1) > 1
            verified = art.get('verification', {}).get('status') == 'verified_t1'

            if (tier == 'T1' and score >= 80) or (is_multi and score >= 75) or (verified and score >= 85):
                art['featured'] = True
            else:
                art['featured'] = False

        featured_count = sum(1 for a in enriched if a.get('featured'))
        self.log(f'Featured: {featured_count}/{len(enriched)} articles marked for homepage')

        # Save all enriched articles to a single review file
        review_file = self.data_dir / f'review_{self.run_id}.txt'
        review_lines = [
            "INTEL PIPELINE — REVIEW FILE",
            f"Run: {self.run_id}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Articles: {len(enriched)}",
            f"{'=' * 80}\n",
        ]

        for i, art in enumerate(enriched, 1):
            enr = art.get('enrichment', {})
            review_lines.append(f"{'=' * 80}")
            review_lines.append(f"ARTICLE {i}/{len(enriched)}")
            review_lines.append(f"{'=' * 80}")
            featured_tag = "*** FEATURED (COPERTINA) ***" if art.get('featured') else "STANDARD"
            review_lines.append(f"Placement: {featured_tag}")
            review_lines.append(f"Original Title: {art.get('title', 'N/A')}")
            review_lines.append(f"Headline: {enr.get('headline', 'N/A')}")
            review_lines.append(f"Source: {art.get('source_name', art.get('source', 'N/A'))}")
            review_lines.append(f"Category: {art.get('category', 'N/A')}")
            review_lines.append(f"Tier: {art.get('tier', 'N/A')} | Score: {art.get('quality_score', 'N/A')}/100")
            review_lines.append(f"URL: {art.get('url', 'N/A')}")
            # Verification status
            verif = art.get('verification', {})
            if verif:
                review_lines.append(f"Verification: {verif.get('status', 'not_checked')}")
            # Dossier info
            dossier = art.get('dossier', {})
            if dossier.get('cluster_size', 1) > 1:
                review_lines.append(f"Dossier: {dossier['cluster_size']} sources merged")
                for sup in dossier.get('supporting_sources', []):
                    review_lines.append(f"  + [{sup.get('tier','?')}] {sup.get('title','')[:60]} ({sup.get('source','')})")
            review_lines.append("")

            # 30-second brief
            brief = enr.get('thirty_second_brief', {})
            if brief:
                review_lines.append("--- 30-SECOND BRIEF ---")
                review_lines.append(f"Should I worry? {brief.get('should_i_worry', 'N/A')}")
                review_lines.append(f"What: {brief.get('what', 'N/A')}")
                review_lines.append(f"Who: {brief.get('who', 'N/A')}")
                review_lines.append(f"When: {brief.get('when', 'N/A')}")
                review_lines.append(f"Risk Level: {brief.get('risk_level', 'N/A')}")
                review_lines.append("")

            # Full article sections
            for section_key, section_title in [
                ('the_facts', 'THE FACTS'),
                ('bali_zero_take', 'THE BALI ZERO TAKE'),
                ('in_practice', 'WHAT THIS MEANS IN PRACTICE'),
                ('next_steps', 'NEXT STEPS'),
            ]:
                section_text = enr.get(section_key, '')
                if section_text:
                    review_lines.append(f"--- {section_title} ---")
                    review_lines.append(section_text)
                    review_lines.append("")

            # FAQ
            faq = enr.get('faq', [])
            if faq:
                review_lines.append("--- FAQ ---")
                for q in faq:
                    review_lines.append(f"Q: {q.get('question', '')}")
                    review_lines.append(f"A: {q.get('answer', '')}")
                    review_lines.append("")

            # Metadata
            meta = enr.get('metadata', {})
            if meta:
                review_lines.append(f"Slug: {meta.get('suggested_slug', 'N/A')}")
                review_lines.append(f"Tags: {', '.join(meta.get('tags', []))}")
                review_lines.append(f"Priority: {meta.get('priority', 'N/A')}")
                review_lines.append(f"Reading time: {meta.get('reading_time_minutes', 'N/A')} min")

            # Legacy format fallback (executive_brief)
            if not enr.get('headline') and enr.get('executive_brief'):
                review_lines.append("--- EXECUTIVE BRIEF ---")
                review_lines.append(enr['executive_brief'])
                review_lines.append("")
                if enr.get('key_facts'):
                    review_lines.append("Key Facts:")
                    for fact in enr['key_facts']:
                        review_lines.append(f"  - {fact}")
                if enr.get('insights'):
                    review_lines.append("\nInsights:")
                    for ins in enr['insights']:
                        review_lines.append(f"  - {ins}")

            review_lines.append(f"\n{'~' * 80}\n")

        review_file.write_text('\n'.join(review_lines), encoding='utf-8')
        self.log(f'Review file saved: {review_file.name} ({len(enriched)} articles)')

        # Send Telegram notifications to all recipients (bilingual)
        import urllib.request as _ur
        import urllib.parse as _up
        import json as _json
        BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
        TG_RECIPIENTS = os.environ.get('TELEGRAM_APPROVAL_CHAT_ID', os.environ.get('TELEGRAM_GROUP_ID', ''))
        BACKEND_URL = os.environ.get('BACKEND_URL', 'https://nuzantara-rag.fly.dev')
        API_KEY = os.environ.get('SCRAPER_API_KEY', '')

        all_chat_ids = [cid.strip() for cid in TG_RECIPIENTS.split(',') if cid.strip()] if TG_RECIPIENTS else []

        for chat_id in all_chat_ids:
            if not BOT_TOKEN:
                break
            recipient = RECIPIENT_CONFIG.get(chat_id, {"lang": "it", "role": "owner"})

            if recipient["role"] == "designer":
                # --- DAMAR: welcome message (one-time) ---
                welcome_flag = self.project_root / 'data' / 'damar_welcomed.flag'
                if not welcome_flag.exists():
                    welcome_msg = (
                        "👋 <b>Halo Damar!</b>\n\n"
                        "Mulai sekarang, kamu akan menerima notifikasi artikel dari Intel Pipeline Bali Zero.\n\n"
                        "⚠️ <b>PENTING:</b> Kamu <b>TIDAK perlu</b> membuat gambar untuk semua artikel.\n\n"
                        "📋 <b>Cara kerjanya:</b>\n"
                        "1️⃣ Buka <b>News Room</b> dan review artikel yang tersedia\n"
                        "2️⃣ Pilih artikel yang menurutmu layak dipublikasikan\n"
                        "3️⃣ Untuk artikel yang dipilih, buat gambar cover berdasarkan prompt di bawah setiap notifikasi\n"
                        "4️⃣ Simpan gambar di folder Desktop kamu\n"
                        "5️⃣ Kirim gambar ke chat ini — <b>reply langsung</b> ke notifikasi artikel yang bersangkutan\n"
                        "6️⃣ Setelah semua gambar diunggah, buka News Room dan klik <b>Publish</b>\n\n"
                        "💡 Cara alternatif: kirim foto dengan caption <code>/cover [kode_artikel]</code>\n\n"
                        f"🔗 <a href=\"{NEWS_ROOM_URL}\">Buka News Room</a>\n\n"
                        "Terima kasih! 🙏"
                    )
                    try:
                        data = _up.urlencode({"chat_id": chat_id, "text": welcome_msg, "parse_mode": "HTML"}).encode()
                        _ur.urlopen(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data, timeout=15)
                        welcome_flag.write_text(datetime.now().isoformat())
                        self.log(f'Welcome message sent to Damar ({chat_id})')
                    except Exception as e:
                        self.log(f'Welcome message failed: {e}', 'WARN')

                # --- DAMAR: individual article messages with image prompt ---
                try:
                    from gemini_image_generator import build_image_prompt as _build_prompt
                except ImportError:
                    _build_prompt = None

                for i, art in enumerate(enriched[:20], 1):
                    enr = art.get('enrichment', {})
                    headline = enr.get('headline', art.get('title', ''))[:80]
                    headline_safe = headline.replace('<', '&lt;').replace('>', '&gt;')
                    cat = art.get('category', '?')
                    priority = enr.get('metadata', {}).get('priority', '?')
                    item_id = art.get('_staging_item_id', f'art_{i}')
                    intel_type = art.get('_staging_intel_type', 'news')

                    # Build image prompt
                    img_prompt = ""
                    if _build_prompt:
                        try:
                            img_prompt = _build_prompt(art)
                        except Exception:
                            img_prompt = ""

                    prompt_section = ""
                    if img_prompt:
                        prompt_section = (
                            f"\n\n{'─' * 30}\n"
                            f"🎨 <b>Prompt gambar</b> <i>(untuk referensi pembuatan gambar)</i>:\n\n"
                            f"<pre>{img_prompt[:800]}</pre>"
                        )

                    msg = (
                        f"📰 <b>Artikel #{i}</b> — Intel Pipeline\n\n"
                        f"📝 <b>{headline_safe}</b>\n"
                        f"📂 {cat} | ⚡ {priority.upper()}\n\n"
                        f"🔗 <a href=\"{NEWS_ROOM_URL}\">Buka News Room</a>\n"
                        f"🏷️ Kode: <code>{item_id}</code>"
                        f"{prompt_section}"
                    )

                    try:
                        data = _up.urlencode({"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}).encode()
                        resp = _ur.urlopen(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data, timeout=15)
                        resp_data = _json.loads(resp.read())
                        tg_msg_id = resp_data.get('result', {}).get('message_id')

                        # Register mapping for cover image reply matching
                        if tg_msg_id and API_KEY and BACKEND_URL:
                            try:
                                mapping_payload = _json.dumps({
                                    "telegram_message_id": tg_msg_id,
                                    "chat_id": int(chat_id),
                                    "intel_type": intel_type,
                                    "item_id": item_id,
                                    "title": headline,
                                }).encode()
                                req = _ur.Request(
                                    f"{BACKEND_URL}/api/intel/staging/register-notification",
                                    data=mapping_payload,
                                    headers={"Content-Type": "application/json", "X-API-Key": API_KEY},
                                )
                                _ur.urlopen(req, timeout=15)
                            except Exception as e:
                                self.log(f'Notification mapping failed for {item_id}: {e}', 'WARN')

                        import time as _time
                        _time.sleep(1)  # Rate limit: avoid Telegram flood
                    except Exception as e:
                        self.log(f'Damar notification failed for art #{i}: {e}', 'WARN')

                self.log(f'Sent {min(len(enriched), 20)} article notifications to Damar ({chat_id})')

            else:
                # --- OWNER: compact Italian summary (unchanged) ---
                lines = [f"<b>Intel Pipeline — {len(enriched)} articoli pronti per review</b>\n"]
                for i, art in enumerate(enriched[:20], 1):
                    enr = art.get('enrichment', {})
                    headline = enr.get('headline', art.get('title', ''))[:70]
                    headline = headline.replace('<', '&lt;').replace('>', '&gt;')
                    cat = art.get('category', '?')
                    featured_icon = "***" if art.get('featured') else ""
                    priority = enr.get('metadata', {}).get('priority', '?')
                    lines.append(f"{i}. {featured_icon}<b>[{priority.upper()}]</b> <i>{cat}</i>\n   {headline}")

                if len(enriched) > 20:
                    lines.append(f"\n... +{len(enriched) - 20} altri")

                lines.append(f"\n🔗 <a href=\"{NEWS_ROOM_URL}\">News Room</a>")
                lines.append(f"Run: {self.run_id} | {datetime.now().strftime('%H:%M')}")
                msg = '\n'.join(lines)

                try:
                    data = _up.urlencode({"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}).encode()
                    _ur.urlopen(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data, timeout=15)
                    self.log(f'Telegram notification sent to owner ({chat_id})')
                except Exception as e:
                    self.log(f'Telegram notification failed: {e}', 'WARN')

        self.update_step_status('6_approval', 'auto_approved', {
            'notified': len(all_chat_ids) > 0 and bool(BOT_TOKEN),
            'articles_count': len(enriched),
            'review_file': str(review_file),
        })
        return True
    
    def step_publishing(self) -> bool:
        """Step 7: Publish approved articles"""
        self.log('Publishing articles...')
        
        # FIX2: blocca publishing se approval pending
        approval_status = self.state.get('steps', {}).get('6_approval', {}).get('status', '')
        if approval_status == 'pending' and not self.config.get('auto_approve'):
            self.log('BLOCKED: publishing halted, approval still pending. Use --auto-approve to bypass.', 'WARN')
            self.update_step_status('7_publishing', 'blocked', {'reason': 'approval_pending'})
            return True

        if self.config.get('dry_run'):
            self.log('Dry run mode - skipping actual publishing')
            self.update_step_status('7_publishing', 'skipped', {'reason': 'dry_run'})
            return True
        
        # Pubblica articoli arricchiti via backend API
        import asyncio as _asyncio
        import httpx as _httpx
        import os as _os

        BACKEND_URL = _os.environ.get('BACKEND_URL', 'https://nuzantara-rag.fly.dev')
        API_KEY     = _os.environ.get('SCRAPER_API_KEY', '')
        BOT_TOKEN   = _os.environ.get('TELEGRAM_BOT_TOKEN', '')
        TG_RECIPIENTS = _os.environ.get('TELEGRAM_APPROVAL_CHAT_ID', _os.environ.get('TELEGRAM_GROUP_ID', ''))
        enriched    = [a for a in self.state.get('articles', []) if a.get('enrichment')]
        published   = 0

        async def _push(art):
            enr   = art.get("enrichment") or {}
            # Build full article from new enrichment structure
            sections = []
            if enr.get("the_facts"):
                sections.append("## Facts\n\n" + enr["the_facts"])
            if enr.get("bali_zero_take"):
                sections.append("## Bali Zero Take\n\n" + enr["bali_zero_take"])
            if enr.get("in_practice"):
                sections.append("## In Practice\n\n" + enr["in_practice"])
            if enr.get("next_steps"):
                sections.append("## Next Steps\n\n" + enr["next_steps"])
            # Fallback to legacy format
            if not sections:
                brief = enr.get("executive_brief", "")
                text = art.get("text", "")
                sections = [s for s in [brief, text] if s]
            content = "\n\n".join(sections)[:8000]
            headline = enr.get("headline", art.get("title", ""))
            payload = {
                "title":           headline,
                "content":         content,
                "category":        art.get("qwen_category", art.get("category", "general")),
                "source_name":     art.get("source_name", art.get("source", "")),
                "source_url":      art.get("url", art.get("source_url", "")),
                "relevance_score": int(round(art.get("qwen_score", 7) * 10)),
                "tier":            art.get("tier", "T3"),
            }
            # Include SEO metadata if available
            if art.get("seo"):
                payload["seo"] = art["seo"]
            if art.get("image_url"):
                payload["image_url"] = art["image_url"]
            # Send cover image as base64 for Drive upload on backend
            if art.get("image_path"):
                try:
                    import base64 as _b64
                    from pathlib import Path as _P
                    img_p = _P(art["image_path"])
                    if img_p.exists() and img_p.stat().st_size > 5000:
                        payload["cover_image_base64"] = _b64.b64encode(img_p.read_bytes()).decode("utf-8")
                except Exception as _img_err:
                    self.log(f'Warning: could not read image for upload: {_img_err}', 'WARN')
            # Include enrichment metadata
            if enr.get("thirty_second_brief"):
                payload["brief"] = enr["thirty_second_brief"]
            if enr.get("faq"):
                payload["faq"] = enr["faq"]
            enr_meta = enr.get("metadata", {})
            if enr_meta.get("suggested_slug"):
                payload["slug"] = enr_meta["suggested_slug"]
            if enr_meta.get("tags"):
                payload["tags"] = enr_meta["tags"]
            payload["featured"] = art.get("featured", False)
            async with _httpx.AsyncClient(timeout=60) as c:
                r = await c.post(
                    f"{BACKEND_URL}/api/intel/scraper/submit",
                    json=payload,
                    headers={"X-API-Key": API_KEY}
                )
                if r.status_code in (200, 201):
                    # Articolo inviato a STAGING — attende approvazione nella News Room
                    # (kita.balizero.com/intelligence/news-room)
                    res_data = r.json()
                    item_id = res_data.get("item_id")
                    intel_type = res_data.get("intel_type", "news")
                    if item_id:
                        self.log(f'Submitted to staging: {item_id} ({intel_type}) — awaiting News Room approval')
                        art['_staging_item_id'] = item_id
                        art['_staging_intel_type'] = intel_type

                    # Intel Lake Wave 5 (2026-05-12): enqueue observation to
                    # local SQLite outbox so the unified pipeline sees this
                    # finding alongside other producers (intel_radar, mata-garuda,
                    # imigrasi_monitor, ...). Best-effort — failure must not
                    # break the existing staging submission flow.
                    try:
                        import hashlib as _h  # noqa: PLC0415
                        import sys as _sys  # noqa: PLC0415
                        _sys.path.insert(0, "/Users/nuzantara/scripts")
                        from intel_lake_outbox import enqueue as _lake_enqueue  # type: ignore
                        _url = art.get("url") or art.get("source_url") or f"bali-intel-scraper://item/{item_id or 'unknown'}"
                        _title = art.get("title") or "untitled"
                        _ch = _h.sha256((_title + " " + _url).encode()).hexdigest()[:32]
                        # Domain inferred from URL when possible
                        try:
                            from urllib.parse import urlparse as _up  # noqa: PLC0415
                            _domain = _up(_url).netloc or "bali-intel-scraper"
                        except Exception:
                            _domain = "bali-intel-scraper"
                        _lake_enqueue(
                            "bali_intel_scraper",
                            {
                                "producer_name": "bali_intel_scraper",
                                "canonical_url": _url,
                                "content_hash": _ch,
                                "title": _title[:500],
                                "summary": (art.get("summary") or art.get("description") or "")[:2000],
                                "source_domain": _domain,
                                "language": art.get("language") or "id",
                                "jurisdiction": "ID-bali" if intel_type == "news" else "ID-national",
                                "topic_tags": [intel_type, "news-room", art.get("category", "general")],
                                "published_at": art.get("published_at") or art.get("scraped_at"),
                                "score": art.get("score"),
                                "raw_payload": {
                                    "intel_type": intel_type,
                                    "staging_item_id": item_id,
                                    "tier": art.get("tier"),
                                    "source": art.get("source"),
                                },
                            },
                        )
                    except Exception as _exc:
                        self.log(f"intel-lake enqueue failed: {_exc}", "WARN")
                    return True
                return False

        async def _run():
            nonlocal published
            for art in enriched:
                try:
                    if await _push(art):
                        published += 1
                    await _asyncio.sleep(7)  # Rate limit: 10/min on backend
                except Exception as e:
                    self.log(f'Publish error: {e}', 'WARN')

        _asyncio.run(_run())
        self.log(f'✅ Inviati {published}/{len(enriched)} articoli alla News Room per approvazione')

        # Notifica Telegram a tutti i destinatari (bilingue)
        import urllib.request as _ur2
        import urllib.parse as _up2
        _timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        for chat_id in TG_RECIPIENTS.split(','):
            chat_id = chat_id.strip()
            if not chat_id or not BOT_TOKEN:
                continue
            recipient = RECIPIENT_CONFIG.get(chat_id, {"lang": "it"})
            if recipient["lang"] == "id":
                msg = (
                    f"🦞 <b>Intel Scraper selesai</b>\n"
                    f"📰 Artikel di News Room: {published}/{len(enriched)} — menunggu persetujuan\n"
                    f"🔗 <a href=\"{NEWS_ROOM_URL}\">Buka News Room</a>\n"
                    f"🕐 {_timestamp} Bali"
                )
            else:
                msg = (
                    f"🦞 <b>Intel Scraper completato</b>\n"
                    f"📰 Articoli in News Room: {published}/{len(enriched)} — in attesa di approvazione\n"
                    f"🔗 <a href=\"{NEWS_ROOM_URL}\">News Room</a>\n"
                    f"🕐 {_timestamp} Bali"
                )
            try:
                data = _up2.urlencode({"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}).encode()
                _ur2.urlopen(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data, timeout=10)
                self.log(f'✅ Notifica Telegram inviata a {chat_id}')
            except Exception as e:
                self.log(f'⚠️  Telegram notify error ({chat_id}): {e}', 'WARN')

        # Update published_articles.json for history dedup
        try:
            pub_file = self.project_root / 'data' / 'published_articles.json'
            pub_data = {'articles': []}
            if pub_file.exists():
                pub_data = json.loads(pub_file.read_text())
            for art in enriched:
                pub_data['articles'].append({
                    'url': art.get('url', ''),
                    'title': art.get('title', ''),
                    'published_at': datetime.now().isoformat(),
                })
            pub_file.write_text(json.dumps(pub_data, ensure_ascii=False, indent=2))
            self.log(f'Published history updated ({len(pub_data["articles"])} total)')
        except Exception as e:
            self.log(f'Published history update failed: {e}', 'WARN')

        self.update_step_status('7_publishing', 'completed')
        return True

    def _fetch_intel_radar_findings(self, limit: int = 50) -> tuple[List[Dict], int]:
        """Fetch unprocessed-by-scraper findings from intel_radar_findings table.

        Atomically picks up to ``limit`` rows where ``processed=true`` AND
        ``scraper_picked=false``, marks them ``scraper_picked=true`` in the
        same transaction, and returns them shaped like UnifiedScraper articles
        so they merge cleanly with the existing pipeline downstream.

        Returns:
            (articles, marked) — articles list (may be empty) plus the count
            of rows we just marked scraper_picked=true (== len(articles) on
            the happy path; less only on partial DB write failure).

        Schema mapping intel_radar_findings → article dict:
            - canonical_url      → url
            - source_domain      → source_name
            - title              → title
            - description        → content (description is short, the
              enrichment step will fetch the full page if needed)
            - query_tier         → category hint (L1/L2/L3 stored on the
              article so downstream WR2 selector can read it)
            - observed_at        → published_date (best proxy when the source
              didn't return a publication date)

        Failure modes (all non-fatal — caller treats this as augmentation):
            - asyncpg not installed → returns ([], 0)
            - DATABASE_URL unset    → returns ([], 0)
            - DB unreachable        → returns ([], 0), error logged

        The transaction guarantees we never double-pick: the SELECT FOR UPDATE
        + UPDATE happens in one round-trip, so a concurrent scraper run on
        another machine cannot race us.
        """
        try:
            import asyncpg  # local import: only loaded when feature flag enabled
        except ImportError:
            self.log('asyncpg not installed; skipping intel-radar fetch', 'WARN')
            return [], 0

        dsn = os.environ.get('DATABASE_URL')
        if not dsn:
            self.log('DATABASE_URL not set; skipping intel-radar fetch', 'WARN')
            return [], 0

        import asyncio

        async def _fetch_and_mark() -> tuple[List[Dict], int]:
            conn = await asyncpg.connect(dsn, timeout=10)
            try:
                async with conn.transaction():
                    rows = await conn.fetch(
                        """
                        SELECT id, query, query_tier, url, canonical_url,
                               title, description, source_domain,
                               published_at, observed_at, source
                        FROM intel_radar_findings
                        WHERE processed = TRUE AND scraper_picked = FALSE
                        ORDER BY observed_at DESC
                        LIMIT $1
                        FOR UPDATE SKIP LOCKED
                        """,
                        limit,
                    )
                    if not rows:
                        return [], 0
                    ids = [r['id'] for r in rows]
                    await conn.execute(
                        """
                        UPDATE intel_radar_findings
                        SET scraper_picked = TRUE, scraper_picked_at = NOW()
                        WHERE id = ANY($1::uuid[])
                        """,
                        ids,
                    )
                articles = [
                    {
                        'url': r['canonical_url'] or r['url'],
                        'title': r['title'] or '',
                        'content': r['description'] or '',
                        'source_name': r['source_domain'] or 'intel-radar',
                        'category': 'general',  # downstream qwen_filter assigns the real category
                        'tier': 'T2',  # default tier; quality_gate will re-rank
                        'published_date': (r['published_at'] or r['observed_at']).isoformat(),
                        'intel_radar_query': r['query'],
                        'intel_radar_query_tier': r['query_tier'],
                        'intel_radar_source': r['source'],
                    }
                    for r in rows
                ]
                return articles, len(rows)
            finally:
                await conn.close()

        try:
            return asyncio.run(_fetch_and_mark())
        except Exception as e:
            self.log(f'intel_radar_findings fetch failed: {e}', 'WARN')
            return [], 0

    def _mock_scraped_articles(self) -> List[Dict]:
        """Mock data for testing pipeline"""
        return [
            {
                'title': 'New KITAS Regulations 2026',
                'url': 'https://example.com/kitas-2026',
                'source_name': 'imigrasi.go.id',
                'category': 'immigration',
                'quality_score': 85,
                'tier': 'T1',
            }
        ]
    
    def run(self):
        """Execute full pipeline"""
        self.log(f'Starting Intel Pipeline - Run ID: {self.run_id}')
        self.log(f'Config: {json.dumps(self.config, indent=2)}')
        
        steps_to_run = PIPELINE_STEPS
        
        # Handle resume
        if self.config.get('resume_from'):
            resume_step = self.config['resume_from']
            if resume_step in steps_to_run:
                idx = steps_to_run.index(resume_step)
                steps_to_run = steps_to_run[idx:]
                self.log(f'Resuming from: {resume_step}')
        
        # Handle skip
        if self.config.get('skip_steps'):
            skip = self.config['skip_steps']
            steps_to_run = [s for s in steps_to_run if s not in skip]
            self.log(f'Skipping steps: {skip}')
        
        # Execute pipeline
        for step in steps_to_run:
            success = self.run_step(step)
            if not success and not self.config.get('continue_on_error'):
                self.log(f'Pipeline failed at step: {step}', 'ERROR')
                self.state['status'] = 'failed'
                self.state['failed_at'] = step
                self.save_state()
                return False
        
        self.state['status'] = 'completed'
        self.state['completed_at'] = datetime.now().isoformat()
        self.save_state()
        
        self.log(f'{"="*60}')
        self.log('PIPELINE COMPLETED')
        self.log(f'{"="*60}')
        self.print_summary()

        # Salva intel_output_latest.json per War Room
        try:
            latest = self.data_dir / 'intel_output_latest.json'
            output = {
                'generated_at': datetime.now().isoformat(),
                'articles': self.state.get('articles', []),
            }
            if self.state.get('intel_digest'):
                output['intel_digest'] = self.state['intel_digest']
            latest.write_text(json.dumps(output, ensure_ascii=False, indent=2))
            self.log(f'✅ intel_output_latest.json salvato ({len(self.state.get("articles",[]))} articoli)')
        except Exception as e:
            self.log(f'⚠️  Salvataggio intel_output_latest.json fallito: {e}', 'WARN')

        return True
    
    def print_summary(self):
        """Print pipeline execution summary"""
        print('\n📊 PIPELINE SUMMARY\n')
        print(f'Run ID: {self.run_id}')
        print(f'Status: {self.state.get("status", "unknown")}')
        print(f'Started: {self.state["started_at"]}')
        if self.state.get('completed_at'):
            print(f'Completed: {self.state["completed_at"]}')
        
        print('\nSteps:')
        for step, data in self.state.get('steps', {}).items():
            status = data.get('status', 'unknown')
            print(f'  {step}: {status}')
        
        print(f'\nState file: {self.state_file}')


def main():
    parser = argparse.ArgumentParser(description='Intel Pipeline Orchestrator')
    
    # Mode
    parser.add_argument('--mode', choices=['full', 'dry-run', 'test'], default='full',
                       help='Pipeline execution mode')
    
    # Data selection
    parser.add_argument('--categories', default='immigration,tax,legal',
                       help='Comma-separated categories')
    parser.add_argument('--limit', type=int, default=10,
                       help='Limit articles per source')
    parser.add_argument('--min-score', type=int, default=40,
                       help='Minimum quality score')
    
    # Flow control
    parser.add_argument('--resume-from', choices=PIPELINE_STEPS,
                       help='Resume from specific step')
    parser.add_argument('--skip', dest='skip_steps',
                       help='Comma-separated steps to skip')
    parser.add_argument('--continue-on-error', action='store_true',
                       help='Continue pipeline even if step fails')
    
    # Options
    parser.add_argument('--skip-images', action='store_true',
                       help='Skip image generation')
    parser.add_argument('--skip-seo', action='store_true',
                       help='Skip SEO optimization (requires gemini CLI)')
    parser.add_argument('--auto-approve', action='store_true',
                       help='Auto-approve articles (skip Telegram)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Dry run (no publishing)')
    parser.add_argument('--max-enrich', type=int, default=15,
                       help='Max articles to enrich with Claude (default: 15)')
    parser.add_argument('--no-cell-emit', action='store_true',
                       help='Disable Phase 3 TICKET B cell-aware HGT post-emit (debug only)')

    args = parser.parse_args()

    # Build config
    config = {
        'mode': args.mode,
        'categories': args.categories.split(','),
        'limit': args.limit,
        'limit_per_source': args.limit,
        'min_score': args.min_score,
        'skip_images': args.skip_images,
        'skip_seo': args.skip_seo,
        'auto_approve': args.auto_approve,
        'dry_run': args.dry_run or args.mode == 'dry-run',
        'continue_on_error': args.continue_on_error,
        'max_enrich': args.max_enrich,
    }
    
    if args.resume_from:
        config['resume_from'] = args.resume_from
    
    if args.skip_steps:
        config['skip_steps'] = args.skip_steps.split(',')
    
    # Run pipeline
    pipeline = IntelPipeline(config)
    success = pipeline.run()

    # Phase 3 TICKET B — IntelScraperHGTBridge async post-emit (bounded blast).
    # See spec v2: research/symbiosis/2026-05-13-ticket-b-narrow-spec.md
    if not args.no_cell_emit:
        try:
            import asyncio
            from backend.cell.cell_post_emit import emit_pipeline_run

            asyncio.run(
                asyncio.wait_for(
                    emit_pipeline_run(pipeline.state),
                    timeout=60.0,
                )
            )
        except asyncio.TimeoutError:
            print("⚠️ cell post-emit timeout after 60s (non-fatal)",
                  file=sys.stderr)
        except Exception as cell_exc:
            print(f"⚠️ cell post-emit skipped (non-fatal): {cell_exc}",
                  file=sys.stderr)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
