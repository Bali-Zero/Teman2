#!/usr/bin/env python3
"""
Master Caching Pipeline - Zero API Cost Strategy

Orchestrates multi-tool workflow for generating 2,000-5,000 cached conversations
using existing subscriptions (Claude Max, Gemini AI Studio, ChatGPT Plus, etc.)

Author: Nuzantara Team
Date: 2026-02-09
Cost: $0 (uses flat-rate subscriptions)

Usage:
    python master_pipeline.py phase1    # Golden seeds (NotebookLM + Claude)
    python master_pipeline.py phase2    # Variations (Gemini AI Studio)
    python master_pipeline.py phase3    # Verification (ChatGPT)
    python master_pipeline.py phase4    # Human review (Claude + dashboard)
    python master_pipeline.py phase5    # Upload to Redis
    python master_pipeline.py status    # Check progress
"""

import click
import json
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
DOCS_DIR = PROJECT_ROOT / "docs" / "caching"

# File paths
GOLDEN_SEEDS_FILE = DATA_DIR / "golden_seeds.json"
VARIATIONS_DIR = DATA_DIR / "variations"
VERIFICATIONS_FILE = DATA_DIR / "verifications.json"
PROGRESS_FILE = DATA_DIR / "pipeline_progress.json"

# Quality thresholds
QUALITY_GATES = {
    "phase1_seeds": {
        "min_quality_score": 90,
        "min_citations": 3,
        "manual_review": True
    },
    "phase2_variations": {
        "min_quality_score": 75,
        "sample_verification": 0.15,
        "auto_reject_below": 60
    },
    "phase3_verification": {
        "pass_rate_threshold": 0.90
    }
}


class PipelineProgress:
    """Track pipeline progress across phases."""

    def __init__(self):
        self.progress_file = PROGRESS_FILE
        self.load()

    def load(self):
        """Load progress from file."""
        if self.progress_file.exists():
            with open(self.progress_file) as f:
                self.data = json.load(f)
        else:
            self.data = {
                "phase1": {"status": "not_started", "completed_at": None},
                "phase2": {"status": "not_started", "completed_at": None},
                "phase3": {"status": "not_started", "completed_at": None},
                "phase4": {"status": "not_started", "completed_at": None},
                "phase5": {"status": "not_started", "completed_at": None},
                "statistics": {}
            }

    def save(self):
        """Save progress to file."""
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.progress_file, 'w') as f:
            json.dump(self.data, f, indent=2)

    def update_phase(self, phase: str, status: str, stats: dict = None):
        """Update phase status."""
        self.data[phase]["status"] = status
        if status == "completed":
            self.data[phase]["completed_at"] = datetime.now().isoformat()
        if stats:
            self.data["statistics"][phase] = stats
        self.save()

    def get_status(self) -> Dict:
        """Get current pipeline status."""
        return self.data


@click.group()
def cli():
    """Master caching pipeline orchestrator."""
    pass


@cli.command()
def status():
    """Check pipeline progress and statistics."""
    click.echo("📊 Pipeline Status Report\n")

    progress = PipelineProgress()
    status_data = progress.get_status()

    # Phase status
    phases = {
        "phase1": "Golden Seeds (NotebookLM + Claude Max)",
        "phase2": "Variation Generation (Gemini AI Studio)",
        "phase3": "Quality Verification (ChatGPT Plus)",
        "phase4": "Human Review (Claude Max + Dashboard)",
        "phase5": "Cache Upload (Redis)"
    }

    for phase_id, phase_name in phases.items():
        phase_data = status_data[phase_id]
        status_emoji = {
            "not_started": "⚪",
            "in_progress": "🔵",
            "completed": "✅",
            "failed": "❌"
        }.get(phase_data["status"], "❓")

        click.echo(f"{status_emoji} {phase_name}: {phase_data['status']}")
        if phase_data.get("completed_at"):
            click.echo(f"   Completed: {phase_data['completed_at']}")

    # Statistics
    if status_data["statistics"]:
        click.echo("\n📈 Statistics:")
        for phase, stats in status_data["statistics"].items():
            click.echo(f"\n{phase}:")
            for key, value in stats.items():
                click.echo(f"  - {key}: {value}")

    # Next steps
    click.echo("\n🎯 Next Steps:")
    if status_data["phase1"]["status"] == "not_started":
        click.echo("  Run: python master_pipeline.py phase1")
    elif status_data["phase2"]["status"] == "not_started":
        click.echo("  Run: python master_pipeline.py phase2")
    elif status_data["phase3"]["status"] == "not_started":
        click.echo("  Run: python master_pipeline.py phase3")
    elif status_data["phase4"]["status"] == "not_started":
        click.echo("  Run: python master_pipeline.py phase4")
    elif status_data["phase5"]["status"] == "not_started":
        click.echo("  Run: python master_pipeline.py phase5")
    else:
        click.echo("  ✅ All phases completed!")


@cli.command()
def phase1():
    """
    Phase 1: Generate golden seeds with NotebookLM + Claude Max.

    Output: 30 high-quality seed conversations (1-2 per route × 3 languages)
    Time: 2-3 days
    Cost: $0
    """
    click.echo("📚 Phase 1: Golden Seeds Generation\n")
    click.echo("=" * 60)

    progress = PipelineProgress()
    progress.update_phase("phase1", "in_progress")

    # Check prerequisites
    kb_sources_dir = DATA_DIR / "kb_sources"
    if not kb_sources_dir.exists():
        click.echo("❌ Missing KB sources directory")
        click.echo(f"   Create: {kb_sources_dir}")
        click.echo("   Add: PDF files for NotebookLM")
        sys.exit(1)

    # Step 1: NotebookLM
    click.echo("\n1️⃣ NotebookLM Setup:")
    click.echo("   → Open https://notebooklm.google.com")
    click.echo("   → Click 'New notebook'")
    click.echo(f"   → Upload PDFs from: {kb_sources_dir}")
    click.echo("   → For each golden route:")
    click.echo("      - Ask: 'Generate a detailed guide for [route topic]'")
    click.echo("      - Click 'Generate Audio Overview'")
    click.echo("      - Download podcast MP3")
    click.echo(f"      - Save to: {DATA_DIR / 'notebooklm_podcasts'}/")

    click.echo("\n📋 Golden Routes to cover:")
    golden_routes = load_golden_routes()
    for i, route_id in enumerate(golden_routes.keys(), 1):
        click.echo(f"   {i}. {route_id}")

    click.echo("\n⏸️  Pause here and complete NotebookLM generation")
    click.echo("   When ready, proceed to transcription:")
    click.echo("   → Run: python scripts/caching/transcribe_podcasts.py")

    # Step 2: Transcription guide
    click.echo("\n2️⃣ Transcription:")
    click.echo("   Option A - Whisper API (if available):")
    click.echo("      python scripts/caching/transcribe_podcasts.py --method whisper")
    click.echo("   Option B - Manual transcription:")
    click.echo("      Use https://otter.ai or similar")

    # Step 3: Claude Max polish
    click.echo("\n3️⃣ Polish with Claude Max (20 conversations/day):")
    click.echo(f"   → Open prompt template: {PROMPTS_DIR / 'claude_max_polish.txt'}")
    click.echo("   → For each transcription:")
    click.echo("      - Copy template")
    click.echo("      - Paste transcription")
    click.echo("      - Submit to Claude Max")
    click.echo("      - Save polished response")
    click.echo(f"   → Save all to: {GOLDEN_SEEDS_FILE}")

    click.echo("\n📝 When phase 1 complete:")
    click.echo("   python master_pipeline.py mark-complete phase1")

    # Create template file
    create_golden_seeds_template()


@cli.command()
@click.option('--seeds', default=str(GOLDEN_SEEDS_FILE), help='Path to golden seeds JSON')
@click.option('--variations-per-seed', default=50, help='Variations to generate per seed')
def phase2(seeds, variations_per_seed):
    """
    Phase 2: Generate variations with Gemini AI Studio.

    Output: 1,500-3,000 conversation variations
    Time: 2-3 days
    Cost: $0 (free tier)
    """
    click.echo("🔄 Phase 2: Variation Generation\n")
    click.echo("=" * 60)

    progress = PipelineProgress()
    progress.update_phase("phase2", "in_progress")

    # Load seeds
    seeds_path = Path(seeds)
    if not seeds_path.exists():
        click.echo(f"❌ Seeds file not found: {seeds_path}")
        click.echo("   Run phase1 first!")
        sys.exit(1)

    with open(seeds_path) as f:
        seeds_data = json.load(f)

    click.echo(f"✅ Loaded {len(seeds_data)} golden seeds")

    # Generate batch prompts
    click.echo(f"\n📦 Generating {len(seeds_data) * variations_per_seed} prompt files...")

    generator = GeminiBatchGenerator(
        output_dir=VARIATIONS_DIR,
        variations_per_seed=variations_per_seed
    )

    prompt_files = generator.generate_all_batches(seeds_data)

    click.echo(f"✅ Generated {len(prompt_files)} prompt files")
    click.echo(f"📂 Location: {VARIATIONS_DIR / 'prompts'}/")

    # Instructions for AI Studio
    click.echo("\n🔗 Google AI Studio Instructions:")
    click.echo("   1. Go to https://aistudio.google.com/prompts/new_chat")
    click.echo("   2. Use 'Batch prompts' feature (10 tabs × 150 prompts)")
    click.echo(f"   3. Import prompts from: {VARIATIONS_DIR / 'prompts'}/")
    click.echo("   4. Click 'Run all'")
    click.echo("   5. Export results as CSV")
    click.echo(f"   6. Save CSV to: {VARIATIONS_DIR / 'responses'}/")

    click.echo("\n📖 Detailed guide:")
    click.echo(f"   {DOCS_DIR / 'GEMINI_BATCH_GUIDE.md'}")

    click.echo("\n⏸️  Pause here and complete AI Studio generation")
    click.echo("   When ready, parse responses:")
    click.echo("   → Run: python scripts/caching/parse_gemini_responses.py")

    progress.update_phase("phase2", "in_progress", {
        "seeds_count": len(seeds_data),
        "target_variations": len(seeds_data) * variations_per_seed,
        "prompt_files_generated": len(prompt_files)
    })


@cli.command()
def phase3():
    """
    Phase 3: Verify quality with ChatGPT Plus.

    Output: Quality report on 15% sample
    Time: 1 day
    Cost: $0
    """
    click.echo("🔍 Phase 3: Quality Verification\n")
    click.echo("=" * 60)

    progress = PipelineProgress()
    progress.update_phase("phase3", "in_progress")

    # Load variations
    variations_file = VARIATIONS_DIR / "conversations.json"
    if not variations_file.exists():
        click.echo(f"❌ Variations file not found: {variations_file}")
        click.echo("   Run phase2 first and parse responses!")
        sys.exit(1)

    with open(variations_file) as f:
        conversations = json.load(f)

    total = len(conversations)
    sample_size = int(total * QUALITY_GATES["phase2_variations"]["sample_verification"])

    click.echo(f"📊 Total conversations: {total}")
    click.echo(f"📊 Sample size (15%): {sample_size}")

    # Generate verification prompts
    click.echo(f"\n📝 Generating verification prompts...")
    verifier = ChatGPTVerifier(sample_size=sample_size)
    verification_prompts = verifier.generate_prompts(conversations)

    click.echo(f"✅ Generated {len(verification_prompts)} verification prompts")
    click.echo(f"📂 Location: {DATA_DIR / 'verification_prompts'}/")

    # Instructions
    click.echo("\n🔗 ChatGPT Plus Instructions:")
    click.echo("   1. Open https://chat.openai.com")
    click.echo("   2. For each prompt file:")
    click.echo("      - Copy prompt")
    click.echo("      - Paste to ChatGPT")
    click.echo("      - Copy JSON response")
    click.echo("      - Save to verification_responses/")
    click.echo(f"   3. Process in batches of 40 (rate limit: 40 msgs/3h)")
    click.echo(f"   4. Save responses to: {DATA_DIR / 'verification_responses'}/")

    click.echo("\n⏸️  Pause here and complete verification")
    click.echo("   When ready, analyze results:")
    click.echo("   → Run: python scripts/caching/analyze_verification.py")


@cli.command()
def phase4():
    """
    Phase 4: Human review with Claude Max + dashboard.

    Output: 50 manually reviewed conversations
    Time: 2-3 days
    Cost: $0
    """
    click.echo("👁️ Phase 4: Human Review\n")
    click.echo("=" * 60)

    progress = PipelineProgress()
    progress.update_phase("phase4", "in_progress")

    click.echo("🔨 Building review dashboard with Windsurf...")
    click.echo("\nWindsurf Cascade prompt:")
    click.echo("-" * 60)
    click.echo("""
Build a conversation review dashboard:
- Single HTML file with inline CSS/JS
- Load conversations from data/conversations.json
- Load verifications from data/verifications.json
- Show top 50 conversations sorted by importance
- Display: query, response, verification scores
- Buttons: Approve ✅, Edit ✏️, Reject ❌
- Inline markdown editor for edits
- Export approved to data/approved_conversations.json
    """)
    click.echo("-" * 60)

    click.echo("\n📋 Manual review workflow:")
    click.echo("   1. Open dashboard in browser")
    click.echo("   2. For each conversation:")
    click.echo("      - Read query + response")
    click.echo("      - Check verification scores")
    click.echo("      - Approve/Edit/Reject")
    click.echo("   3. For top 20 high-value conversations:")
    click.echo("      - Use Claude Max for review assistance")
    click.echo(f"      - See prompt: {PROMPTS_DIR / 'claude_max_review.txt'}")

    click.echo("\n✅ When phase 4 complete:")
    click.echo("   python master_pipeline.py mark-complete phase4")


@cli.command()
def phase5():
    """
    Phase 5: Upload approved conversations to Redis cache.

    Output: Conversations cached and ready
    Time: 1 hour
    Cost: $0
    """
    click.echo("📤 Phase 5: Cache Upload\n")
    click.echo("=" * 60)

    progress = PipelineProgress()
    progress.update_phase("phase5", "in_progress")

    # Load approved conversations
    approved_file = DATA_DIR / "approved_conversations.json"
    if not approved_file.exists():
        click.echo(f"❌ Approved conversations not found: {approved_file}")
        click.echo("   Run phase4 first!")
        sys.exit(1)

    with open(approved_file) as f:
        approved = json.load(f)

    click.echo(f"📊 Approved conversations: {len(approved)}")

    # Generate Redis commands
    click.echo("\n🔨 Generating Redis import script...")
    uploader = RedisUploader()
    redis_script = uploader.generate_upload_script(approved)

    script_path = DATA_DIR / "redis_upload.sh"
    with open(script_path, 'w') as f:
        f.write(redis_script)

    click.echo(f"✅ Redis script generated: {script_path}")

    # Upload options
    click.echo("\n📤 Upload options:")
    click.echo("   Option A - Direct upload (if Redis accessible):")
    click.echo(f"      bash {script_path}")
    click.echo("   Option B - Manual upload:")
    click.echo("      1. Copy script to server with Redis")
    click.echo("      2. Run: bash redis_upload.sh")

    click.echo("\n✅ Pipeline complete!")
    progress.update_phase("phase5", "completed", {
        "conversations_uploaded": len(approved)
    })


@cli.command()
@click.argument('phase')
def mark_complete(phase):
    """Mark a phase as completed."""
    progress = PipelineProgress()
    progress.update_phase(phase, "completed")
    click.echo(f"✅ Marked {phase} as completed")


# Helper functions

def load_golden_routes() -> Dict:
    """Load golden routes from codebase."""
    # Import from kg_enhanced_retrieval.py
    import sys
    sys.path.insert(0, str(PROJECT_ROOT / "apps" / "backend-rag" / "backend" / "services" / "rag"))

    try:
        from kg_enhanced_retrieval import KGEnhancedRetrieval
        # Get GOLDEN_ROUTES dict
        routes = KGEnhancedRetrieval.GOLDEN_ROUTES
        return {route_id: route for route_id, route in routes.items()}
    except:
        # Fallback: hardcoded list
        return {
            "kitas_work": {"name": "Work KITAS Application"},
            "pt_pma_setup": {"name": "PT PMA Company Setup"},
            "nib_oss": {"name": "NIB Registration via OSS"},
            "restaurant_foreigner": {"name": "Open Restaurant as Foreigner"},
            # ... other routes
        }


def create_golden_seeds_template():
    """Create template JSON for golden seeds."""
    template = {
        "seeds": [
            {
                "id": "seed_001",
                "route_id": "kitas_work",
                "language": "it",
                "query": "Come funziona il KITAS per lavoro?",
                "response": "[Paste polished response from Claude Max here]",
                "quality_score": 95,
                "citations_count": 5,
                "generated_at": datetime.now().isoformat(),
                "source": "notebooklm_podcast_01_claude_polished"
            }
        ]
    }

    template_file = DATA_DIR / "golden_seeds_template.json"
    with open(template_file, 'w') as f:
        json.dump(template, f, indent=2)

    click.echo(f"\n📄 Template created: {template_file}")


class GeminiBatchGenerator:
    """Generate batch prompts for Gemini AI Studio."""

    def __init__(self, output_dir: Path, variations_per_seed: int = 50):
        self.output_dir = Path(output_dir)
        self.variations_per_seed = variations_per_seed
        self.prompts_dir = self.output_dir / "prompts"
        self.prompts_dir.mkdir(parents=True, exist_ok=True)

    def generate_all_batches(self, seeds_data: List[Dict]) -> List[Path]:
        """Generate prompt files for all seeds."""
        prompt_files = []

        for seed in seeds_data:
            files = self.generate_for_seed(seed)
            prompt_files.extend(files)

        return prompt_files

    def generate_for_seed(self, seed: Dict) -> List[Path]:
        """Generate variation prompts for one seed."""
        files = []

        for i in range(1, self.variations_per_seed + 1):
            prompt = self._build_variation_prompt(seed, i)

            filename = f"{seed['id']}_var_{i:03d}.txt"
            filepath = self.prompts_dir / filename

            with open(filepath, 'w') as f:
                f.write(prompt)

            files.append(filepath)

        return files

    def _build_variation_prompt(self, seed: Dict, var_num: int) -> str:
        """Build variation prompt."""
        return f"""Generate a natural variation of this conversation.

SEED CONVERSATION:
Query: {seed['query']}
Response: {seed['response']}
Language: {seed['language']}
Route: {seed['route_id']}

VARIATION GUIDELINES:
1. Change phrasing but keep intent
2. Vary user context (investor/employee/freelancer/director)
3. Vary specificity (generic/sector-specific/cost-focused/timeline-focused)
4. Keep language: {seed['language']}
5. Maintain citation format [Source: ...]
6. Keep response 400-600 words
7. Variation style: {['formal', 'casual', 'direct', 'detailed'][var_num % 4]}

Generate VARIATION #{var_num}:
"""


class ChatGPTVerifier:
    """Generate verification prompts for ChatGPT."""

    def __init__(self, sample_size: int):
        self.sample_size = sample_size

    def generate_prompts(self, conversations: List[Dict]) -> List[Path]:
        """Generate verification prompts."""
        # Stratified sampling
        sample = self._stratified_sample(conversations, self.sample_size)

        prompts_dir = DATA_DIR / "verification_prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)

        prompt_files = []

        for i, conv in enumerate(sample, 1):
            prompt = self._build_verification_prompt(conv)

            filename = f"verify_{i:03d}.txt"
            filepath = prompts_dir / filename

            with open(filepath, 'w') as f:
                f.write(prompt)

            prompt_files.append(filepath)

        return prompt_files

    def _stratified_sample(self, conversations: List[Dict], size: int) -> List[Dict]:
        """Sample proportionally from each route/language."""
        import random

        # Group by route and language
        groups = {}
        for conv in conversations:
            key = (conv.get('route_id', 'unknown'), conv.get('language', 'en'))
            if key not in groups:
                groups[key] = []
            groups[key].append(conv)

        # Sample from each group
        samples_per_group = max(1, size // len(groups))
        sample = []

        for group_convs in groups.values():
            n = min(samples_per_group, len(group_convs))
            sample.extend(random.sample(group_convs, n))

        return sample[:size]

    def _build_verification_prompt(self, conv: Dict) -> str:
        """Build verification prompt."""
        return f"""Verify this cached conversation for quality.

CONVERSATION:
Query: {conv['query']}
Response: {conv['response']}

VERIFICATION CHECKLIST:

1. CITATIONS (weight: 30%)
   - Count citations in format [Source: ...]
   - Are all citations valid and specific?
   - List any missing or vague citations

2. FACTUAL ACCURACY (weight: 40%)
   - Extract 5-10 key factual claims
   - Mark each as: verified / unverifiable / questionable
   - Flag any obvious errors or contradictions

3. COMPLETENESS (weight: 20%)
   - Does it fully answer the query?
   - Includes workflow steps?
   - Mentions costs/timeline if relevant?

4. UNCERTAINTY HANDLING (weight: 10%)
   - Uses appropriate hedging ("typically", "may vary")?
   - States when info may be outdated?
   - Recommends verification for critical decisions?

OUTPUT FORMAT (JSON only):
{{
  "citations": {{"count": X, "valid": X, "issues": ["..."]}},
  "accuracy": {{"verified_claims": X, "total_claims": X, "errors": ["..."]}},
  "completeness": {{"score": 0-100, "missing": ["..."]}},
  "uncertainty": {{"handled": true/false, "notes": "..."}},
  "overall_score": 0.0-1.0,
  "recommendation": "approve|review|reject",
  "issues": ["..."]
}}
"""


class RedisUploader:
    """Generate Redis upload script."""

    def generate_upload_script(self, conversations: List[Dict]) -> str:
        """Generate bash script with Redis commands."""
        script = """#!/bin/bash
# Redis Cache Upload Script
# Generated: """ + datetime.now().isoformat() + """

set -e

REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}
REDIS_DB=${REDIS_DB:-0}

echo "📤 Uploading """ + str(len(conversations)) + """ conversations to Redis..."

"""

        for i, conv in enumerate(conversations, 1):
            # Generate cache key
            cache_key = f"cache:conversation:{conv['route_id']}:{conv['language']}:{i}"

            # Escape JSON for Redis
            conv_json = json.dumps(conv).replace('"', '\\"')

            # Set with 24h TTL
            script += f"""
redis-cli -h $REDIS_HOST -p $REDIS_PORT -n $REDIS_DB SET "{cache_key}" '{conv_json}' EX 86400
"""

        script += f"""
echo "✅ Upload complete: {len(conversations)} conversations cached"
echo "🔍 Verify: redis-cli -n $REDIS_DB KEYS 'cache:conversation:*' | wc -l"
"""

        return script


if __name__ == '__main__':
    cli()
