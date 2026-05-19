#!/usr/bin/env python3
"""Build Zantara face anchor embedding for ArcFace identity gate.

Reads PNG anchor images from
  research/marketing/zantara-visual-dataset/v1/ingredients/
and writes the L2-normalized average embedding to
  zantara-anchor-A007.embedding.npy

The output is consumed by scripts/wr3_arcface_verify.py at episode-time
identity verification: per-clip cosine similarity ≥0.6 vs this anchor.

Process:
  1. insightface FaceAnalysis(name="buffalo_l") on each PNG
  2. Pick highest-confidence face per PNG (det_score)
  3. Average their normed_embedding vectors
  4. L2-normalize the result
  5. np.save to .embedding.npy

This is a ONE-OFF script — re-run only if anchors change.
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import insightface
import numpy as np

INGREDIENTS_DIR = Path(__file__).resolve().parent.parent / "research/marketing/zantara-visual-dataset/v1/ingredients"
ANCHOR_PATTERN = "*anchor*.png"
OUTPUT_NAME = "zantara-anchor-A007.embedding.npy"


def main() -> int:
    if not INGREDIENTS_DIR.exists():
        print(f"ERROR: ingredients dir not found: {INGREDIENTS_DIR}", file=sys.stderr)
        return 1

    anchor_pngs = sorted(INGREDIENTS_DIR.glob(ANCHOR_PATTERN))
    if not anchor_pngs:
        # Fallback — accept any PNG in dir
        anchor_pngs = sorted(INGREDIENTS_DIR.glob("*.png"))
    if not anchor_pngs:
        print(f"ERROR: no anchor PNGs in {INGREDIENTS_DIR}", file=sys.stderr)
        return 1

    print(f"[anchor-build] Found {len(anchor_pngs)} PNG(s):")
    for p in anchor_pngs:
        print(f"  - {p.name}")

    print("[anchor-build] Loading insightface model (buffalo_l, may download on first run)...")
    app = insightface.app.FaceAnalysis(name="buffalo_l")
    app.prepare(ctx_id=-1, det_size=(640, 640))  # CPU (-1) by default

    embeddings = []
    for png in anchor_pngs:
        img = cv2.imread(str(png))
        if img is None:
            print(f"  [warn] cv2 failed to read {png.name}, skip")
            continue
        faces = app.get(img)
        if not faces:
            print(f"  [warn] no face detected in {png.name}, skip")
            continue
        # Pick highest-confidence face
        best = max(faces, key=lambda f: float(f.det_score))
        emb = best.normed_embedding  # already L2-normalized
        embeddings.append(emb)
        print(f"  [ok]   {png.name}: face conf={float(best.det_score):.3f}, embedding dim={emb.shape}")

    if not embeddings:
        print("ERROR: no faces detected in any anchor PNG — cannot build embedding", file=sys.stderr)
        return 1

    avg = np.mean(np.stack(embeddings), axis=0)
    # Re-normalize the average (mean of normalized vectors is NOT itself unit)
    avg = avg / np.linalg.norm(avg)
    print(f"[anchor-build] Averaged {len(embeddings)} embedding(s), L2-renormalized, shape={avg.shape}")

    output_path = INGREDIENTS_DIR / OUTPUT_NAME
    np.save(output_path, avg)
    print(f"[anchor-build] ✅ saved to {output_path}")
    print(f"               file size: {output_path.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
