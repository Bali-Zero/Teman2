"""
Mata Garuda — YouTube transcript harvesting via yt-dlp subprocess.

yt-dlp is a system binary (brew install yt-dlp), NOT a Python dependency.
"""
from __future__ import annotations

import json
import logging
import subprocess

from mata_garuda.registry import register_tool

logger = logging.getLogger("mata_garuda.tools")


@register_tool(name="fetch_youtube_transcript")
def fetch_youtube_transcript(
    channel_url: str,
    max_videos: int = 3,
    context_variables: dict | None = None,
) -> str:
    """Fetch recent video metadata and auto-subtitles from a YouTube channel.

    Args:
        channel_url: YouTube channel URL or @handle
        max_videos: Maximum videos to fetch
    """
    try:
        # Fetch video metadata
        result = subprocess.run(
            [
                "yt-dlp",
                "--flat-playlist",
                "--playlist-end", str(max_videos),
                "--dump-json",
                f"https://www.youtube.com/{channel_url}/videos",
            ],
            capture_output=True, text=True, timeout=60,
        )

        if result.returncode != 0:
            return f"[ERROR] yt-dlp failed: {result.stderr[:200]}"

        videos = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                try:
                    data = json.loads(line)
                    videos.append({
                        "title": data.get("title", ""),
                        "url": f"https://www.youtube.com/watch?v={data.get('id', '')}",
                        "duration": data.get("duration", 0),
                        "view_count": data.get("view_count", 0),
                        "upload_date": data.get("upload_date", ""),
                        "channel": data.get("channel", channel_url),
                    })
                except json.JSONDecodeError:
                    continue

        if not videos:
            return f"[WARNING] No videos found for {channel_url}"

        lines = [f"Found {len(videos)} recent videos from {channel_url}:"]
        for i, v in enumerate(videos, 1):
            lines.append(
                f"  {i}. {v['title'][:80]}\n"
                f"     URL: {v['url']}\n"
                f"     Views: {v['view_count']} | Date: {v['upload_date']}"
            )
        return "\n".join(lines)

    except FileNotFoundError:
        return "[ERROR] yt-dlp not found. Install with: brew install yt-dlp"
    except subprocess.TimeoutExpired:
        return "[ERROR] yt-dlp timeout (60s)"
    except Exception as e:
        return f"[ERROR] YouTube fetch failed: {e}"


@register_tool(name="fetch_video_subtitles")
def fetch_video_subtitles(
    video_url: str,
    context_variables: dict | None = None,
) -> str:
    """Fetch auto-generated subtitles/transcript for a YouTube video.

    Args:
        video_url: Full YouTube video URL
    """
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--write-auto-sub",
                "--sub-lang", "en",
                "--skip-download",
                "--sub-format", "vtt",
                "--output", "/tmp/yt_sub_%(id)s",
                video_url,
            ],
            capture_output=True, text=True, timeout=30,
        )

        # Find the subtitle file
        import glob
        vtt_files = glob.glob("/tmp/yt_sub_*.vtt")
        if vtt_files:
            with open(vtt_files[-1]) as f:
                content = f.read()
            # Clean VTT to plain text
            import re
            lines = content.split("\n")
            text_lines = []
            for line in lines:
                line = line.strip()
                if not line or "-->" in line or line.startswith("WEBVTT") or line[0].isdigit():
                    continue
                clean = re.sub(r"<[^>]+>", "", line)
                if clean and clean not in text_lines[-1:]:
                    text_lines.append(clean)
            transcript = " ".join(text_lines)[:3000]
            return f"[TRANSCRIPT] {transcript}"

        return "[WARNING] No subtitles found for this video"

    except FileNotFoundError:
        return "[ERROR] yt-dlp not found"
    except subprocess.TimeoutExpired:
        return "[ERROR] subtitle download timeout"
    except Exception as e:
        return f"[ERROR] Subtitle fetch failed: {e}"
