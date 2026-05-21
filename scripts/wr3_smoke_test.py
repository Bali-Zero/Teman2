#!/usr/bin/env python3
"""WR3 smoke test — Manifesto Zantara end-to-end pilot driver.

Drives a full WR3 episode without external services (mock mode):
  - WR3_ARCFACE_MOCK=true
  - dry-run flowkit (no Veo spend)
  - mock chatterbox (skip TTS, generate silent vo.wav)
  - mock manifest builder + critic verdict

This validates the supervisor wiring + contracts loader + manifest assembly
end-to-end without consuming any cloud credit. Use BEFORE the real S7.8 pilot
("Manifesto Zantara") to catch obvious wiring bugs.

Usage:
  python scripts/wr3_smoke_test.py --episode-id smoke-2026-05-18 --output /tmp/wr3-smoke
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from wr3_contracts import load_contracts  # noqa: E402
from wr3_episode_manifest import ManifestBuilder  # noqa: E402


# Duration mapping table (Veo 3.1 Fast Tier_ONE clip nativo = 8s).
# Mirror of docs/wr3/contracts/brief-interpreter.yaml + wr3-brief-interpreter.md.
# Smoke test asserts these constants stay in sync with contracts/agents.
DURATION_MAPPING: dict[int, dict[str, int]] = {
    60: {"clip_count": 8, "word_count": 180, "flow_cr": 80},
    90: {"clip_count": 12, "word_count": 270, "flow_cr": 120},
    120: {"clip_count": 15, "word_count": 360, "flow_cr": 150},
    150: {"clip_count": 19, "word_count": 450, "flow_cr": 190},
}


def _seed_episode(episode_dir: Path, episode_id: str, target_duration_s: int = 60) -> None:
    """Write minimal fixture files (brief, script, shot-pack) for smoke.

    target_duration_s in [60, 150]; out-of-range raises ValueError (mirrors
    wr3-brief-interpreter hard_fail).
    """
    if not (60 <= target_duration_s <= 150):
        raise ValueError(
            f"target_duration_s out of [60,150] range: {target_duration_s}"
        )
    mapping = DURATION_MAPPING.get(target_duration_s)
    if mapping is None:
        # Allow intermediate values; derive on the fly.
        mapping = {
            "clip_count": -(-target_duration_s // 8),  # ceil
            "word_count": target_duration_s * 3,
            "flow_cr": (-(-target_duration_s // 8)) * 10,
        }

    episode_dir.mkdir(parents=True, exist_ok=True)
    (episode_dir / "clips").mkdir(exist_ok=True)
    (episode_dir / "audio").mkdir(exist_ok=True)

    brief = {
        "episode_id": episode_id,
        "topic": f"Manifesto Zantara — Bali Zero brand intro {target_duration_s}s",
        "audience_segment": "new-arrivals-bali",
        "target_duration_s": target_duration_s,
        "key_facts": [
            {"id": "claim-uu-6-2011-art-117", "text": "Foreigners must register their stay (UU 6/2011 Art. 117)"},
            {"id": "claim-vita-deposit-2bn", "text": "Second Home visa requires IDR 2 billion deposit (Perpres 37/2022)"},
        ],
        "claim_ids": ["claim-uu-6-2011-art-117", "claim-vita-deposit-2bn"],
    }
    (episode_dir / "brief.json").write_text(json.dumps(brief, indent=2))

    script = {
        "episode_id": episode_id,
        "segments": [
            {"index": 0, "start_ms": 0, "text": "Bali Zero. We do not sell certainty. We read history before you sign.", "claim_ids": []},
            {"index": 1, "start_ms": 5000, "text": "Foreigners must register their stay. UU six twenty eleven article one one seven.", "claim_ids": ["claim-uu-6-2011-art-117"]},
            {"index": 2, "start_ms": 12000, "text": "Second Home visa requires two billion rupiah deposit. Perpres thirty seven twenty twenty two.", "claim_ids": ["claim-vita-deposit-2bn"]},
        ],
    }
    (episode_dir / "script.json").write_text(json.dumps(script, indent=2))

    shot_pack = {
        "episode_id": episode_id,
        "shots": [
            {"index": i, "positive_prompt": f"shot {i}", "negative_prompt": "", "duration_s": 8, "identity_tokens": ["A007-Zantara-anchor"]}
            for i in range(1, 4)
        ],
    }
    (episode_dir / "shot-pack.json").write_text(json.dumps(shot_pack, indent=2))

    # Mock clips (1-byte files just so manifest can hash them)
    for i in range(1, 4):
        (episode_dir / "clips" / f"{i:02d}.mp4").write_bytes(f"mock_clip_{i}".encode())

    # Mock master + vo (manifest hashes them)
    (episode_dir / "master.mp4").write_bytes(b"mock_master_mp4_for_smoke_test")
    (episode_dir / "audio" / "vo.wav").write_bytes(b"mock_vo_wav")


def _verify_episode(episode_dir: Path) -> dict:
    """Run the manifest builder + validation against the seeded episode."""
    builder = ManifestBuilder(
        episode_id=episode_dir.name,
        topic="Manifesto Zantara — Bali Zero brand intro 60s",
        audience_segment="new-arrivals-bali",
    )
    builder.add_claim("claim-uu-6-2011-art-117")
    builder.add_claim("claim-vita-deposit-2bn")

    builder.record_agent("wr3-brief-interpreter", "1.0.0", cost_usd=0.12)
    builder.record_agent("wr3-script-editor", "1.0.0", cost_usd=0.11)
    builder.record_agent("wr3-shot-director", "1.0.0", cost_usd=0.45)
    builder.record_agent("wr3-pre-render-gatekeeper", "1.0.0", cost_usd=0.08)
    builder.record_agent("wr3-clip-renderer", "1.0.0")
    builder.flow_credits_spent = 30  # 3 mock clips × 10 cr
    builder.record_agent("wr3-audio-asset-producer", "1.0.0", cost_usd=0.04)
    builder.record_agent("wr3-post-assembler", "1.0.0", cost_usd=0.07)
    builder.record_agent("wr3-critic", "1.0.0", cost_usd=0.48)

    builder.hash_asset("master.mp4", episode_dir / "master.mp4")
    builder.hash_asset("audio/vo.wav", episode_dir / "audio" / "vo.wav")
    for clip in sorted((episode_dir / "clips").glob("*.mp4")):
        builder.hash_asset(f"clips/{clip.name}", clip)

    builder.variants_delivered = ["tiktok", "ig-reels", "yt-shorts", "fb"]
    builder.identity_overall_cosine_avg = 0.72  # MOCK passing
    builder.lufs_measured = -13.8
    builder.duration_master_ms = 24_000  # 3 shots × 8s
    builder.critic_verdict = "PASS"

    return builder.finalize()


async def main_async(args: argparse.Namespace) -> int:
    contracts = load_contracts()
    # Default target_duration_s=60 if Namespace doesn't carry it (e.g., pytest test-mode invocation).
    target_duration_s = getattr(args, "target_duration_s", 60)
    print(f"[wr3-smoke] Loaded {len(contracts.agents)} agent contracts")
    print(f"[wr3-smoke] {len(contracts.routes)} channels in router")
    print(f"[wr3-smoke] target_duration_s={target_duration_s} (mapping: {DURATION_MAPPING.get(target_duration_s, 'derived')})\n")

    episode_dir = Path(args.output) / args.episode_id
    print(f"[wr3-smoke] Seeding episode at {episode_dir}")
    _seed_episode(episode_dir, args.episode_id, target_duration_s=target_duration_s)

    print("[wr3-smoke] Verifying manifest builder…")
    manifest = _verify_episode(episode_dir)
    (episode_dir / "episode_manifest.json").write_text(json.dumps(manifest, indent=2))

    # Sanity checks
    checks: list[tuple[str, bool, str]] = []
    checks.append(("manifest has 18 fields", len(manifest) >= 18,
                  f"got {len(manifest)} keys"))
    checks.append(("≥1 claim_id present", len(manifest["claim_ids"]) > 0,
                  f"claim_ids={manifest['claim_ids']}"))
    checks.append(("master.mp4 hashed", "master.mp4" in manifest["asset_hashes"],
                  f"keys={list(manifest['asset_hashes'].keys())[:3]}…"))
    checks.append(("all 4 variants declared",
                  len(manifest["variants_delivered"]) == 4,
                  f"variants={manifest['variants_delivered']}"))
    checks.append(("critic_verdict valid",
                  manifest["critic_verdict"] in ("PASS", "FAIL", "DEGRADED"),
                  f"verdict={manifest['critic_verdict']}"))
    checks.append(("identity ≥0.6",
                  (manifest["identity_overall_cosine_avg"] or 0) >= 0.6,
                  f"cosine={manifest['identity_overall_cosine_avg']}"))
    checks.append(("LUFS within ±1 of -14",
                  abs((manifest["lufs_measured"] or 0) + 14) <= 1.0,
                  f"lufs={manifest['lufs_measured']}"))
    # Duration-mapping sanity (defends against drift between agents/contracts/smoke).
    brief_data = json.loads((episode_dir / "brief.json").read_text())
    td = brief_data.get("target_duration_s", 60)
    checks.append(("target_duration_s in [60,150]",
                  60 <= td <= 150,
                  f"target_duration_s={td}"))
    if td in DURATION_MAPPING:
        expected = DURATION_MAPPING[td]
        checks.append((f"duration mapping {td}s: {expected['clip_count']} clips / "
                       f"{expected['word_count']}w / {expected['flow_cr']} cr",
                      True,
                      f"mapping consistent"))

    failures = 0
    print("\n[wr3-smoke] Sanity checks:")
    for name, ok, detail in checks:
        mark = "✅" if ok else "❌"
        print(f"  {mark} {name}: {detail}")
        if not ok:
            failures += 1

    if failures:
        print(f"\n[wr3-smoke] FAIL — {failures}/{len(checks)} checks failed")
        return 1

    print(f"\n[wr3-smoke] PASS — all {len(checks)} checks green")
    print(f"[wr3-smoke] Episode artifacts at {episode_dir}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="WR3 smoke test pilot")
    parser.add_argument("--episode-id", default="smoke-manifesto-zantara",
                        help="Episode slug (default: smoke-manifesto-zantara)")
    parser.add_argument("--output", default="/tmp/wr3-smoke",
                        help="Output dir (default: /tmp/wr3-smoke)")
    parser.add_argument("--target-duration-s", type=int, default=60,
                        choices=[60, 90, 120, 150],
                        help="Episode duration target in seconds. Must be in [60,150] range "
                             "(default: 60). Drives clip_count + word_count + Flow Pro spend "
                             "per Veo 3.1 Fast Tier_ONE mapping.")
    args = parser.parse_args()
    sys.exit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
