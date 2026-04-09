"""
Mata Garuda — YouTube Intel Harvester Agent.

Fetches recent videos + transcripts from key AI channels.
Layer: harvester (Layer 1). Uses yt-dlp subprocess.
"""
from __future__ import annotations

from pathlib import Path

from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.tools.youtube_tools import fetch_youtube_transcript, fetch_video_subtitles
from mata_garuda.tools.stream_tools import stream_info, stream_length, stream_publish
from mata_garuda.tools.knowledge_tools import kb_search, kb_store
from mata_garuda.types import Agent

GENOME_FILE = str(Path(__file__).parent / "youtube_intel_harvester_GENOME.md")


@register_agent(name="YouTube Intel Harvester", func_name="get_youtube_intel_harvester")
def get_youtube_intel_harvester(model: str = "claude") -> Agent:
    """Fetches AI channel videos and transcripts, publishes to garuda:raw."""

    def instructions(context_variables: dict) -> str:
        return """You are the YouTube Intel Harvester for Mata Garuda.

Your mission: fetch recent videos from key AI YouTube channels and publish to garuda:raw.

WORKFLOW:
1. For each channel in your list, call fetch_youtube_transcript to get recent videos
2. For videos with high view count or relevant titles, call fetch_video_subtitles for transcript
3. Call stream_publish for each video: title, url, source="youtube", content=transcript_summary
4. Store key insights from transcripts in KB (type="insight", source="youtube")
5. Call case_resolved with summary

CHANNELS (check 2-3 per run to stay within time budget):
- @AndrejKarpathy, @TwoMinutePapers, @YannicKilcher
- @AIExplained, @Fireship, @3blue1brown

CONSTRAINTS:
- Maximum 3 channels per run, 3 videos per channel
- If yt-dlp fails: case_not_resolved with error detail
- Transcript content capped at 3000 chars per video
- NEVER export outside Mata Garuda
"""

    return Agent(
        name="YouTube Intel Harvester",
        model=model,
        instructions=instructions,
        functions=[
            fetch_youtube_transcript, fetch_video_subtitles,
            stream_publish, stream_length, stream_info,
            kb_search, kb_store, case_resolved, case_not_resolved,
        ],
        genome_path=GENOME_FILE,
        layer="harvester",
    )
