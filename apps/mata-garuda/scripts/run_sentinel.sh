#!/bin/zsh
# run_sentinel.sh — Full AI-Intel-Sentinel pipeline
#
# Runs nightly on Pro via LaunchAgent:
#   1. Harvest (arXiv, RSS, GitHub, YouTube)
#   2. Normalize + Score (Ollama)
#   3. Digest (Claude CLI synthesis)
#   4. Log results
#
# Schedule: 02:00 WITA daily (Pro, Ollama H24)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PY="$REPO_DIR/.venv/bin/python"
LOG="/Users/nuzantara/logs/ai-intel-sentinel.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S %Z')

mkdir -p "$(dirname "$LOG")"

echo "" >> "$LOG"
echo "=== AI-Intel-Sentinel — $DATE ===" >> "$LOG"

cd "$REPO_DIR"

# Step 1: Harvest all sources → garuda:raw
echo "[$(date '+%H:%M:%S')] Harvesting..." >> "$LOG"
$VENV_PY -c "
import subprocess
from mata_garuda.tools.arxiv_tools import _parse_arxiv_atom
from mata_garuda.tools.stream_tools import stream_publish
from mata_garuda.tools.feed_tools import fetch_rss_feed
from mata_garuda.tools.github_tools import fetch_github_trending
from mata_garuda.tools.youtube_tools import fetch_youtube_transcript
from mata_garuda.config import AI_RSS_FEEDS, AI_YOUTUBE_CHANNELS

counts = {'arxiv': 0, 'rss': 0, 'github': 0, 'youtube': 0}

# ArXiv
url = 'http://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.CL+OR+cat:cs.LG+OR+cat:cs.IR&sortBy=submittedDate&sortOrder=descending&max_results=15'
r = subprocess.run(['curl', '-sL', url, '--connect-timeout', '15'], capture_output=True, text=True, timeout=20)
for p in _parse_arxiv_atom(r.stdout):
    stream_publish(title=p['title'][:200], url=p['url'], source='arxiv', content=p['abstract'][:500])
    counts['arxiv'] += 1

# RSS
for feed_url in AI_RSS_FEEDS:
    try:
        r = fetch_rss_feed(feed_url, max_items=5)
        for line in r.split('\n'):
            if 'URL: http' in line:
                u = line.strip().replace('URL: ', '')
                t = r.split(u)[0].split('\n')[-2].strip()
                stream_publish(title=t[:200], url=u, source='rss', content='newsletter')
                counts['rss'] += 1
    except Exception:
        pass

# GitHub
try:
    r = fetch_github_trending(topics='machine-learning', max_results=10, days=1)
    for line in r.split('\n'):
        if line.strip().startswith('URL: https://github.com'):
            u = line.strip().replace('URL: ', '')
            t = r.split(u)[0].split('\n')[-2].strip()
            stream_publish(title=t[:200], url=u, source='github', content='trending repo')
            counts['github'] += 1
except Exception:
    pass

# YouTube (top 3 channels, 2 videos each)
for channel in AI_YOUTUBE_CHANNELS[:3]:
    try:
        r = fetch_youtube_transcript(f'@{channel}', max_videos=2)
        for line in r.split('\n'):
            if 'URL: https://www.youtube.com' in line:
                u = line.strip().replace('URL: ', '')
                t = r.split(u)[0].split('\n')[-2].strip()
                stream_publish(title=t[:200], url=u, source='youtube', content='video')
                counts['youtube'] += 1
    except Exception:
        pass

total = sum(counts.values())
print(f'Harvested: {total} items ({counts})')
" >> "$LOG" 2>&1

# Step 2: Normalize + Score
echo "[$(date '+%H:%M:%S')] Processing..." >> "$LOG"
$VENV_PY -c "
from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.workers.normalizer import run_normalizer
from mata_garuda.workers.scorer import run_scorer

kb = KnowledgeBase()
n = run_normalizer(kb, max_items=50)
s = run_scorer(kb, max_items=50)
print(f'Normalizer: {n}')
print(f'Scorer: {s}')
print(f'KB: {kb.stats()}')
kb.close()
" >> "$LOG" 2>&1

# Step 3: Digest
echo "[$(date '+%H:%M:%S')] Generating digest..." >> "$LOG"
$VENV_PY scripts/run_ai_digest.py >> "$LOG" 2>&1

EXIT_CODE=$?
echo "[$(date '+%H:%M:%S')] Sentinel exit=$EXIT_CODE" >> "$LOG"
exit $EXIT_CODE
