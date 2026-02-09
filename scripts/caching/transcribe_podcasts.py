#!/usr/bin/env python3
"""
NotebookLM Podcast Transcription Helper

Converts NotebookLM audio podcasts to text transcriptions for Claude Max polishing.
Uses Whisper API (via existing subscriptions) or manual transcription.

Author: Nuzantara Team
Date: 2026-02-09
Reference: docs/caching/WORKFLOW_GUIDE.md (Phase 1)
"""

import json
import os
from pathlib import Path
from typing import Dict, List

import click


@click.group()
def cli():
    """NotebookLM Podcast Transcription Helper."""
    pass


@cli.command()
@click.argument("audio_dir", type=click.Path(exists=True))
@click.option("--output-dir", default="data/transcriptions", help="Output directory for transcriptions")
@click.option("--method", type=click.Choice(["whisper", "manual"]), default="manual", help="Transcription method")
def transcribe(audio_dir: str, output_dir: str, method: str):
    """
    Transcribe NotebookLM podcast audio files.

    AUDIO_DIR: Directory containing NotebookLM MP3 files

    Methods:
    - manual: Instructions for manual transcription (no API calls)
    - whisper: Use OpenAI Whisper API (requires API key)
    """
    audio_path = Path(audio_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    audio_files = list(audio_path.glob("*.mp3")) + list(audio_path.glob("*.m4a"))

    if not audio_files:
        click.echo(f"❌ No audio files found in {audio_dir}")
        return

    click.echo(f"📁 Found {len(audio_files)} audio files")

    if method == "manual":
        _show_manual_instructions(audio_files, output_path)
    elif method == "whisper":
        _transcribe_with_whisper(audio_files, output_path)


def _show_manual_instructions(audio_files: List[Path], output_path: Path):
    """
    Show instructions for manual transcription.

    Zero-cost approach using existing tools.
    """
    click.echo("\n" + "="*70)
    click.echo("📝 MANUAL TRANSCRIPTION INSTRUCTIONS (Zero Cost)")
    click.echo("="*70)

    click.echo("\n🎯 Option 1: Use NotebookLM Web Interface")
    click.echo("   1. Go to https://notebooklm.google.com")
    click.echo("   2. Select your notebook")
    click.echo("   3. Click on the podcast episode")
    click.echo("   4. Click 'Show transcript' button")
    click.echo("   5. Copy full transcript text")
    click.echo("   6. Save to files below")

    click.echo("\n🎯 Option 2: Use MacOS Dictation (Free)")
    click.echo("   1. Enable Dictation in System Preferences")
    click.echo("   2. Play audio at normal speed")
    click.echo("   3. Use Fn key twice to start dictation")
    click.echo("   4. Speak into mic while audio plays")
    click.echo("   5. Save to files below")

    click.echo("\n🎯 Option 3: Use Chrome Live Captions (Free)")
    click.echo("   1. Enable Live Captions in Chrome settings")
    click.echo("   2. Play audio in Chrome tab")
    click.echo("   3. Copy live caption text as it generates")
    click.echo("   4. Save to files below")

    click.echo("\n📄 Save transcriptions to these files:")
    click.echo("-" * 70)

    for audio_file in audio_files:
        output_file = output_path / f"{audio_file.stem}.txt"
        click.echo(f"   {audio_file.name}")
        click.echo(f"   → {output_file}")
        click.echo()

    click.echo("="*70)
    click.echo("\n💡 TIP: Transcription doesn't need to be perfect!")
    click.echo("   Claude Max will polish and structure the content in Phase 1.")
    click.echo("   Focus on capturing the key Q&A structure and facts.\n")


def _transcribe_with_whisper(audio_files: List[Path], output_path: Path):
    """
    Transcribe using OpenAI Whisper API.

    Requires OPENAI_API_KEY environment variable.
    Cost: ~$0.006/minute (25 min podcast = $0.15)
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        click.echo("❌ OPENAI_API_KEY not found in environment")
        click.echo("   Set it with: export OPENAI_API_KEY='your-key'")
        return

    try:
        import openai
        openai.api_key = api_key
    except ImportError:
        click.echo("❌ openai package not installed")
        click.echo("   Install with: pip install openai")
        return

    click.echo(f"\n🎙️ Transcribing {len(audio_files)} files with Whisper API...")

    for i, audio_file in enumerate(audio_files, 1):
        output_file = output_path / f"{audio_file.stem}.txt"

        if output_file.exists():
            click.echo(f"⏭️ [{i}/{len(audio_files)}] Skipping {audio_file.name} (already exists)")
            continue

        click.echo(f"🔄 [{i}/{len(audio_files)}] Transcribing {audio_file.name}...")

        try:
            with open(audio_file, "rb") as f:
                transcript = openai.Audio.transcribe("whisper-1", f)

            with open(output_file, "w") as f:
                f.write(transcript["text"])

            click.echo(f"✅ [{i}/{len(audio_files)}] Saved to {output_file.name}")

        except Exception as e:
            click.echo(f"❌ [{i}/{len(audio_files)}] Error: {e}")
            continue

    click.echo(f"\n✅ Transcription complete! {len(audio_files)} files processed")


@cli.command()
@click.argument("transcriptions_dir", type=click.Path(exists=True))
def validate(transcriptions_dir: str):
    """
    Validate transcription files before Phase 1 polishing.

    TRANSCRIPTIONS_DIR: Directory containing transcription text files
    """
    trans_path = Path(transcriptions_dir)
    txt_files = list(trans_path.glob("*.txt"))

    if not txt_files:
        click.echo(f"❌ No .txt files found in {transcriptions_dir}")
        return

    click.echo(f"\n📊 Validating {len(txt_files)} transcription files...")
    click.echo("="*70)

    total_words = 0
    issues = []

    for txt_file in txt_files:
        with open(txt_file, "r") as f:
            content = f.read()

        word_count = len(content.split())
        total_words += word_count

        # Validation checks
        has_issue = False

        if word_count < 100:
            issues.append(f"⚠️ {txt_file.name}: Too short ({word_count} words)")
            has_issue = True

        if word_count > 10000:
            issues.append(f"⚠️ {txt_file.name}: Very long ({word_count} words)")
            has_issue = True

        if not has_issue:
            click.echo(f"✅ {txt_file.name}: {word_count:,} words")

    click.echo("="*70)
    click.echo(f"\n📈 Total: {len(txt_files)} files, {total_words:,} words")
    click.echo(f"📏 Average: {total_words // len(txt_files):,} words/file")

    if issues:
        click.echo("\n⚠️ Issues found:")
        for issue in issues:
            click.echo(f"   {issue}")
    else:
        click.echo("\n✅ All files validated successfully!")

    click.echo("\n🎯 Next step: Use Claude Max to polish these transcriptions")
    click.echo("   See: prompts/claude_max_polish.txt")


@cli.command()
@click.argument("transcriptions_dir", type=click.Path(exists=True))
@click.option("--output", default="data/golden_seeds.json", help="Output JSON file")
def prepare_batch(transcriptions_dir: str, output: str):
    """
    Prepare batch file for Claude Max polishing.

    Creates JSON file mapping transcriptions to golden seed IDs.

    TRANSCRIPTIONS_DIR: Directory containing transcription text files
    """
    trans_path = Path(transcriptions_dir)
    txt_files = sorted(trans_path.glob("*.txt"))

    if not txt_files:
        click.echo(f"❌ No .txt files found in {transcriptions_dir}")
        return

    batch_data = {
        "metadata": {
            "created_at": "2026-02-09",
            "total_seeds": len(txt_files),
            "source": "NotebookLM podcasts",
            "status": "pending_polish"
        },
        "seeds": []
    }

    for i, txt_file in enumerate(txt_files, 1):
        seed_id = f"seed_{i:03d}_{txt_file.stem}"

        with open(txt_file, "r") as f:
            transcript = f.read()

        batch_data["seeds"].append({
            "id": seed_id,
            "source_file": txt_file.name,
            "transcript": transcript,
            "polished_response": None,
            "citations_count": 0,
            "quality_score": 0,
            "status": "pending"
        })

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(batch_data, f, indent=2)

    click.echo(f"✅ Created batch file: {output}")
    click.echo(f"📊 {len(txt_files)} seeds ready for Claude Max polishing")
    click.echo(f"\n🎯 Next: Use Claude Max with prompts/claude_max_polish.txt")


if __name__ == "__main__":
    cli()
