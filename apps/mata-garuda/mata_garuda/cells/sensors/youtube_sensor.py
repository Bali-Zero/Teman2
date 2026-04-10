"""YouTube Sensor — perceives AI channel videos via yt-dlp."""
from __future__ import annotations

import json
import subprocess

from cell_core.types import SensorReading

from mata_garuda.config import AI_YOUTUBE_CHANNELS


class YouTubeSensor:
    """Fetches recent videos from AI YouTube channels."""

    name = "youtube"

    def __init__(self, channels: list[str] | None = None, max_channels: int = 3, max_videos: int = 2):
        self._channels = channels or AI_YOUTUBE_CHANNELS
        self._max_channels = max_channels
        self._max_videos = max_videos

    async def read(self, **context) -> SensorReading:
        all_videos = []
        errors = 0

        for channel in self._channels[:self._max_channels]:
            try:
                result = subprocess.run(
                    [
                        "yt-dlp", "--flat-playlist",
                        "--playlist-end", str(self._max_videos),
                        "--dump-json",
                        f"https://www.youtube.com/@{channel}/videos",
                    ],
                    capture_output=True, text=True, timeout=60,
                )
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        try:
                            data = json.loads(line)
                            all_videos.append({
                                "title": data.get("title", ""),
                                "url": f"https://www.youtube.com/watch?v={data.get('id', '')}",
                                "channel": channel,
                                "views": data.get("view_count", 0),
                                "upload_date": data.get("upload_date", ""),
                                "source": "youtube",
                            })
                        except json.JSONDecodeError:
                            pass
            except Exception:
                errors += 1

        status = "green" if all_videos else ("yellow" if errors < self._max_channels else "red")
        return SensorReading(
            sensor_name=self.name,
            status=status,
            value=all_videos,
            metadata={"count": len(all_videos), "channels": self._max_channels, "errors": errors},
        )
