#!/usr/bin/env python3
"""Build the official Zantara v1 visual identity seed dataset.

The source images live outside the repo on Antonello's Desktop. This script
keeps the repo artifact reproducible: raw references are copied, collages are
split into single-image crops, rejected images are separated, and metadata is
written next to the assets.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("zantara_visual_dataset")

Status = Literal["approved", "reference_only", "rejected"]
UsageTier = Literal["A_anchor", "B_pose_expression", "C_reference_only", "reject"]


@dataclass(frozen=True)
class SourceAsset:
    key: str
    path: Path
    role: str
    status: Status
    reason: str


@dataclass(frozen=True)
class DatasetItem:
    asset_id: str
    filename: str
    source_key: str
    status: Status
    usage_tier: UsageTier
    quality_grade: str
    pose: str
    expression: str
    crop: str
    lighting: str
    background: str
    outfit: str
    hair: str
    caption: str
    notes: str
    crop_box: tuple[int, int, int, int] | None = None
    output_subdir: str = "approved"


SOURCE_ASSETS: tuple[SourceAsset, ...] = (
    SourceAsset(
        key="zan",
        path=Path("/Users/nuzantara/Desktop/zan.png"),
        role="expression collage, 4x2",
        status="reference_only",
        reason="collage source split into single frames; never train directly on the collage",
    ),
    SourceAsset(
        key="zan1",
        path=Path("/Users/nuzantara/Desktop/zan1.png"),
        role="pose-angle collage, mixed 3+4 grid",
        status="reference_only",
        reason="collage source split into single frames; never train directly on the collage",
    ),
    SourceAsset(
        key="zan2",
        path=Path("/Users/nuzantara/Desktop/zan2.png"),
        role="single high-resolution three-quarter reference",
        status="approved",
        reason="coherent with core identity; useful secondary anchor",
    ),
    SourceAsset(
        key="zan3",
        path=Path("/Users/nuzantara/Desktop/zan3.png"),
        role="single high-resolution three-quarter reference",
        status="approved",
        reason="strongest high-resolution identity anchor",
    ),
    SourceAsset(
        key="riri",
        path=Path("/Users/nuzantara/Desktop/riri.png"),
        role="duplicate single reference",
        status="rejected",
        reason="bit-identical duplicate of zan2; excluded to avoid duplicate weighting",
    ),
    SourceAsset(
        key="generate_angles_1",
        path=Path("/Users/nuzantara/Desktop/Generate_diverse_images_angles_202605160201 (1).jpeg"),
        role="generated front portrait",
        status="rejected",
        reason="identity drift: softer generic face, different earrings, smoother plastic skin",
    ),
    SourceAsset(
        key="generate_angles_2",
        path=Path("/Users/nuzantara/Desktop/Generate_diverse_images_angles_202605160201.jpeg"),
        role="generated front portrait",
        status="rejected",
        reason="identity drift: different face proportions, jewelry and blouse details",
    ),
)


COMMON_LIGHTING = "neutral soft studio light"
COMMON_BACKGROUND = "neutral gray studio background"
COMMON_OUTFIT = "ivory silk blouse with delicate gold floral embroidery, small gold hoop earrings"
COMMON_HAIR = "long straight black hair, center part"


APPROVED_ITEMS: tuple[DatasetItem, ...] = (
    DatasetItem(
        asset_id="ZAN-V1-A001",
        filename="zan_v1_a001_primary_3q_bust_anchor.png",
        source_key="zan3",
        status="approved",
        usage_tier="A_anchor",
        quality_grade="A",
        pose="three-quarter right",
        expression="neutral confident",
        crop="bust portrait",
        lighting=COMMON_LIGHTING,
        background=COMMON_BACKGROUND,
        outfit=COMMON_OUTFIT,
        hair=COMMON_HAIR,
        caption="Zantara v1 primary anchor, three-quarter right bust portrait, neutral confident expression, ivory silk blouse with gold embroidery, neutral gray studio, soft light.",
        notes="Primary face/identity anchor for Flow, Imagen, photo and video prompt matching.",
        output_subdir="approved/anchors",
    ),
    DatasetItem(
        asset_id="ZAN-V1-A002",
        filename="zan_v1_a002_primary_3q_face_closeup_anchor.png",
        source_key="zan3",
        status="approved",
        usage_tier="A_anchor",
        quality_grade="A",
        pose="three-quarter right",
        expression="neutral confident",
        crop="face close-up",
        lighting=COMMON_LIGHTING,
        background=COMMON_BACKGROUND,
        outfit=COMMON_OUTFIT,
        hair=COMMON_HAIR,
        caption="Zantara v1 primary face close-up, three-quarter right angle, neutral confident expression, realistic skin texture, center-parted black hair, soft gray studio.",
        notes="Derived close-up crop from primary anchor for face identity lock.",
        crop_box=(405, 45, 1035, 775),
        output_subdir="approved/anchors",
    ),
    DatasetItem(
        asset_id="ZAN-V1-A003",
        filename="zan_v1_a003_secondary_3q_bust_anchor.png",
        source_key="zan2",
        status="approved",
        usage_tier="A_anchor",
        quality_grade="A-",
        pose="three-quarter right",
        expression="neutral soft",
        crop="bust portrait",
        lighting=COMMON_LIGHTING,
        background=COMMON_BACKGROUND,
        outfit=COMMON_OUTFIT,
        hair=COMMON_HAIR,
        caption="Zantara v1 secondary high-resolution anchor, three-quarter right bust portrait, neutral soft expression, ivory embroidered blouse, neutral gray studio.",
        notes="Secondary high-resolution anchor. Keep lower weight than A001.",
        output_subdir="approved/anchors",
    ),
    DatasetItem(
        asset_id="ZAN-V1-A004",
        filename="zan_v1_a004_secondary_3q_face_closeup_anchor.png",
        source_key="zan2",
        status="approved",
        usage_tier="A_anchor",
        quality_grade="A-",
        pose="three-quarter right",
        expression="neutral soft",
        crop="face close-up",
        lighting=COMMON_LIGHTING,
        background=COMMON_BACKGROUND,
        outfit=COMMON_OUTFIT,
        hair=COMMON_HAIR,
        caption="Zantara v1 secondary face close-up, three-quarter right angle, neutral soft expression, realistic skin texture, center-parted black hair, soft gray studio.",
        notes="Derived close-up crop from secondary anchor.",
        crop_box=(405, 45, 1035, 775),
        output_subdir="approved/anchors",
    ),
)


def grid_items() -> list[DatasetItem]:
    """Return manually labeled crops from the two source collages."""
    zan_specs = [
        ("B001", "front_neutral_headshot", "front-facing", "neutral", (0, 0, 384, 512)),
        ("B002", "front_micro_smile_headshot", "front-facing", "micro-smile", (384, 0, 768, 512)),
        ("B003", "front_serious_headshot", "front-facing", "serious", (768, 0, 1152, 512)),
        ("B004", "front_soft_smile_headshot", "front-facing", "soft smile", (1152, 0, 1536, 512)),
        ("B005", "gaze_camera_left_headshot", "front-facing, gaze camera-left", "neutral sideways gaze", (0, 512, 384, 1024)),
        ("B006", "chin_high_confident_headshot", "slight three-quarter right, chin high", "confident", (384, 512, 768, 1024)),
        ("B007", "gaze_down_headshot", "front-facing, gaze down", "calm eyes down", (768, 512, 1152, 1024)),
        ("B008", "front_open_smile_headshot", "front-facing", "open natural smile", (1152, 512, 1536, 1024)),
    ]
    zan1_specs = [
        ("B009", "front_neutral_square", "front-facing", "neutral", (0, 0, 512, 512)),
        ("B010", "three_quarter_right_square", "three-quarter right", "neutral", (512, 0, 1024, 512)),
        ("B011", "right_profile_square", "right profile", "neutral", (1024, 0, 1536, 512)),
        ("B012", "three_quarter_left_confident_headshot", "three-quarter left", "serious confident", (0, 536, 384, 1024)),
        ("B013", "three_quarter_right_chin_high_headshot", "three-quarter right, chin high", "confident", (384, 536, 768, 1024)),
        ("B014", "gaze_down_bust_headshot", "three-quarter right, gaze down", "calm eyes down", (768, 536, 1152, 1024)),
        ("B015", "back_hair_reference", "back view", "not applicable", (1152, 536, 1536, 1024)),
    ]

    items: list[DatasetItem] = []
    for item_id, slug, pose, expression, box in zan_specs:
        items.append(
            DatasetItem(
                asset_id=f"ZAN-V1-{item_id}",
                filename=f"zan_v1_{item_id.lower()}_{slug}.png",
                source_key="zan",
                status="approved",
                usage_tier="B_pose_expression",
                quality_grade="B",
                pose=pose,
                expression=expression,
                crop="headshot",
                lighting=COMMON_LIGHTING,
                background=COMMON_BACKGROUND,
                outfit=COMMON_OUTFIT,
                hair=COMMON_HAIR,
                caption=f"Zantara v1 pose reference, {pose}, {expression} expression, headshot crop, ivory embroidered blouse, neutral gray studio, soft light.",
                notes="Split from collage; use for pose/expression reference, not as the strongest face anchor.",
                crop_box=box,
                output_subdir="approved/poses",
            )
        )
    for item_id, slug, pose, expression, box in zan1_specs:
        crop_name = "back hair reference" if "back_hair" in slug else "pose reference"
        items.append(
            DatasetItem(
                asset_id=f"ZAN-V1-{item_id}",
                filename=f"zan_v1_{item_id.lower()}_{slug}.png",
                source_key="zan1",
                status="approved",
                usage_tier="B_pose_expression",
                quality_grade="B",
                pose=pose,
                expression=expression,
                crop="square bust/head reference" if item_id in {"B009", "B010", "B011"} else "headshot",
                lighting=COMMON_LIGHTING,
                background=COMMON_BACKGROUND,
                outfit=COMMON_OUTFIT,
                hair=COMMON_HAIR if item_id != "B015" else "long straight black hair from rear, center part not visible",
                caption=f"Zantara v1 {crop_name}, {pose}, {expression} expression, neutral gray studio, ivory embroidered blouse.",
                notes="Split from collage; use for angle coverage. Back view is hair/outfit reference only.",
                crop_box=box,
                output_subdir="approved/poses",
            )
        )
    return items


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_info(path: Path) -> dict[str, int | str]:
    with Image.open(path) as image:
        return {"width": image.width, "height": image.height, "mode": image.mode, "format": image.format or ""}


def git_head(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "log", "--oneline", "-1"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def write_image_item(item: DatasetItem, source: SourceAsset, dataset_root: Path) -> dict[str, str | int | None]:
    output_dir = dataset_root / item.output_subdir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / item.filename

    with Image.open(source.path) as image:
        image = image.convert("RGB")
        if item.crop_box is not None:
            image = image.crop(item.crop_box)
        image.save(output_path, format="PNG", optimize=True)

    info = image_info(output_path)
    record = asdict(item)
    record["path"] = str(output_path.relative_to(dataset_root))
    record["sha256"] = sha256_file(output_path)
    record["width"] = info["width"]
    record["height"] = info["height"]
    record["format"] = info["format"]
    return record


def copy_raw_sources(dataset_root: Path) -> list[dict[str, str | int]]:
    raw_dir = dataset_root / "sources" / "raw"
    reference_dir = dataset_root / "reference_only" / "collages"
    rejected_dir = dataset_root / "rejected"
    raw_dir.mkdir(parents=True, exist_ok=True)
    reference_dir.mkdir(parents=True, exist_ok=True)
    rejected_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, str | int]] = []
    for source in SOURCE_ASSETS:
        if not source.path.exists():
            raise FileNotFoundError(source.path)
        raw_dest = raw_dir / source.path.name
        shutil.copy2(source.path, raw_dest)
        visible_path = raw_dest
        if source.status == "reference_only":
            visible_path = reference_dir / source.path.name
            shutil.copy2(source.path, visible_path)
        elif source.status == "rejected":
            visible_path = rejected_dir / source.path.name
            shutil.copy2(source.path, visible_path)

        info = image_info(source.path)
        records.append(
            {
                "key": source.key,
                "role": source.role,
                "status": source.status,
                "reason": source.reason,
                "source_path": str(source.path),
                "dataset_path": str(visible_path.relative_to(dataset_root)),
                "raw_copy": str(raw_dest.relative_to(dataset_root)),
                "sha256": sha256_file(source.path),
                "width": int(info["width"]),
                "height": int(info["height"]),
                "format": str(info["format"]),
            }
        )
    return records


def write_captions(dataset_root: Path, records: list[dict[str, str | int | None]]) -> None:
    metadata_dir = dataset_root / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    csv_path = metadata_dir / "captions.csv"
    fieldnames = [
        "asset_id",
        "filename",
        "path",
        "status",
        "usage_tier",
        "quality_grade",
        "pose",
        "expression",
        "crop",
        "lighting",
        "background",
        "outfit",
        "hair",
        "caption",
        "notes",
        "sha256",
        "width",
        "height",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)

    jsonl_path = metadata_dir / "captions.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def prompt_text(pose: str, expression: str, crop: str, lighting: str, background: str, outfit: str, hair: str) -> str:
    return (
        "Ultra-realistic studio portrait of Zantara, the same adult Indonesian woman from the Zantara v1 official reference dataset, "
        "consistent facial identity, natural proportions, warm medium skin tone, dark almond-shaped eyes, defined cheekbones, "
        "subtle natural makeup, sharp black eyeliner, "
        f"{hair}, {outfit}, {background}, {lighting}, realistic skin texture, natural pores, no plastic skin, "
        "eye-level camera, photorealistic RAW photograph, single image only, no collage. "
        f"Pose: {pose}. Expression: {expression}. Crop: {crop}."
    )


def write_generation_queue(dataset_root: Path) -> None:
    prompts_dir = dataset_root / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []

    specs = [
        ("identity", "front-facing", "neutral calm expression", "head and shoulders", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("identity", "front-facing", "slight smile", "head and shoulders", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("identity", "front-facing", "serious", "head and shoulders", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("identity", "front-facing", "eyes closed", "head and shoulders", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("identity", "front-facing, looking down", "calm introspective", "head and shoulders", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("identity", "front-facing, looking camera-left", "neutral", "head and shoulders", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("identity", "front-facing, looking camera-right", "neutral", "head and shoulders", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("identity", "three-quarter left", "neutral", "head and shoulders", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("identity", "three-quarter right", "neutral", "head and shoulders", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("identity", "left profile 90 degrees", "neutral", "head and shoulders", "soft side light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("identity", "right profile 90 degrees", "neutral", "head and shoulders", "soft side light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("identity", "back view", "not applicable", "shoulders and hair", "soft back rim light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("expression", "front-facing", "calm", "headshot", "diffused studio light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("expression", "front-facing", "closed-mouth smile", "headshot", "diffused studio light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("expression", "front-facing", "open natural smile", "headshot", "diffused studio light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("expression", "front-facing", "confident", "headshot", "diffused studio light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("expression", "front-facing", "thoughtful", "headshot", "diffused studio light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("expression", "front-facing", "slightly surprised", "headshot", "diffused studio light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("expression", "front-facing", "relaxed", "headshot", "diffused studio light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("expression", "front-facing", "intense", "headshot", "diffused studio light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("expression", "front-facing", "micro-smile", "headshot", "diffused studio light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("expression", "front-facing, chin slightly high", "secure and composed", "headshot", "diffused studio light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("expression", "front-facing", "protective serious", "headshot", "diffused studio light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("expression", "front-facing", "warm attentive", "headshot", "diffused studio light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("expression", "front-facing", "determined", "headshot", "diffused studio light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("expression", "front-facing", "archival calm", "headshot", "diffused studio light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("expression", "front-facing", "soft laugh, natural and controlled", "headshot", "diffused studio light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("expression", "front-facing", "eyes closed calm", "headshot", "diffused studio light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("crop", "front-facing", "neutral", "close-up face", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("crop", "front-facing", "neutral", "headshot", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("crop", "front-facing", "neutral", "shoulders", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("crop", "front-facing", "neutral", "bust portrait", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("crop", "front-facing", "neutral", "half body", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("crop", "front-facing", "neutral", "three-quarter body", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("crop", "front-facing", "neutral", "full body", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("crop", "sitting, front-facing", "neutral", "half body seated", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("crop", "front-facing", "neutral", "wide portrait with negative space", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("crop", "three-quarter right", "neutral", "wide portrait with negative space", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("crop", "right profile", "neutral", "bust profile portrait", "soft side light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("crop", "standing, front-facing", "neutral", "full body standing", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("lighting", "front-facing", "neutral", "head and shoulders", "side light from camera-left", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("lighting", "front-facing", "neutral", "head and shoulders", "side light from camera-right", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("lighting", "front-facing", "neutral", "head and shoulders", "slightly dramatic editorial light", "dark neutral gray studio background", COMMON_OUTFIT, COMMON_HAIR),
        ("lighting", "front-facing", "neutral", "head and shoulders", "high-key soft studio light", "white studio background", COMMON_OUTFIT, COMMON_HAIR),
        ("lighting", "front-facing", "neutral", "head and shoulders", "warm diffused studio light", "beige neutral studio background", COMMON_OUTFIT, COMMON_HAIR),
        ("lighting", "front-facing", "neutral", "head and shoulders", "cool diffused studio light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("lighting", "front-facing", "neutral", "head and shoulders", "warm amber side light from camera-left", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("lighting", "front-facing", "neutral", "head and shoulders", "soft rim light behind hair", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("lighting", "front-facing", "neutral", "head and shoulders", "low-contrast beauty light", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("lighting", "front-facing", "neutral", "head and shoulders", "high-contrast editorial light with soft shadow", COMMON_BACKGROUND, COMMON_OUTFIT, COMMON_HAIR),
        ("lighting", "front-facing", "neutral", "head and shoulders", "soft window light from camera-left", "light gray studio wall with soft falloff", COMMON_OUTFIT, COMMON_HAIR),
        ("lighting", "front-facing", "neutral", "head and shoulders", "soft window light from camera-right", "light gray studio wall with soft falloff", COMMON_OUTFIT, COMMON_HAIR),
        ("lighting", "front-facing", "neutral", "head and shoulders", "even diffused studio light", "charcoal gray studio background", COMMON_OUTFIT, COMMON_HAIR),
        ("lighting", "front-facing", "neutral", "head and shoulders", "even diffused studio light", "warm beige neutral background", COMMON_OUTFIT, COMMON_HAIR),
        ("lighting", "front-facing", "neutral", "head and shoulders", "even diffused studio light", "clean white studio background", COMMON_OUTFIT, COMMON_HAIR),
        ("hair", "front-facing", "neutral", "head and shoulders", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, "long straight black hair, center part, tucked slightly behind both ears"),
        ("hair", "front-facing", "neutral", "head and shoulders", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, "long straight black hair, center part, one soft strand falling forward"),
        ("hair", "front-facing", "neutral", "head and shoulders", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, "long black hair gathered in a loose low bun, same color and hairline"),
        ("hair", "front-facing", "neutral", "head and shoulders", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, "long straight black hair, center part, tucked behind the left ear only"),
        ("hair", "front-facing", "neutral", "head and shoulders", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, "long straight black hair, center part, tucked behind the right ear only"),
        ("hair", "front-facing", "neutral", "head and shoulders", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, "long straight black hair, center part, softly brushed behind shoulders"),
        ("hair", "front-facing", "neutral", "head and shoulders", "soft front light", COMMON_BACKGROUND, COMMON_OUTFIT, "long black hair in a loose low ponytail, same hairline and color"),
        ("outfit", "front-facing", "neutral", "bust portrait", "soft front light", COMMON_BACKGROUND, "structured charcoal silk blouse with subtle antique gold trim, small gold hoop earrings", COMMON_HAIR),
        ("outfit", "front-facing", "neutral", "bust portrait", "soft front light", COMMON_BACKGROUND, "black modern blazer over ivory silk blouse with gold embroidery, small gold hoop earrings", COMMON_HAIR),
        ("outfit", "front-facing", "neutral", "half body", "soft front light", COMMON_BACKGROUND, "ivory silk blouse with gold embroidery and simple black tailored trousers, small gold hoop earrings", COMMON_HAIR),
        ("outfit", "front-facing", "neutral", "bust portrait", "soft front light", COMMON_BACKGROUND, "cream kebaya-inspired silk blouse with restrained gold embroidery, small gold hoop earrings", COMMON_HAIR),
    ]

    for index, spec in enumerate(specs, start=1):
        category, pose, expression, crop, lighting, background, outfit, hair = spec
        shot_id = f"ZAN-V1-GEN-{index:03d}"
        rows.append(
            {
                "shot_id": shot_id,
                "category": category,
                "pose": pose,
                "expression": expression,
                "crop": crop,
                "lighting": lighting,
                "background": background,
                "outfit": outfit,
                "hair": hair,
                "prompt": prompt_text(pose, expression, crop, lighting, background, outfit, hair),
            }
        )

    csv_path = prompts_dir / "generation_queue_v1.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    jsonl_path = prompts_dir / "generation_queue_v1.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    prompt_md = prompts_dir / "zantara_official_character_prompt.md"
    prompt_md.write_text(
        """# Zantara Official Character Prompt v1

Use this prompt only with the approved anchors in `../approved/anchors/`.

```text
Ultra-realistic studio portrait of Zantara, the same adult Indonesian woman from the Zantara v1 official reference dataset, consistent facial identity, natural proportions, long straight black hair parted in the center, dark almond-shaped eyes, defined cheekbones, warm medium skin tone, subtle natural makeup, sharp black eyeliner, small gold hoop earrings, ivory silk blouse with delicate gold floral embroidery, neutral gray studio background, soft professional lighting, realistic skin texture, natural pores, no plastic skin, eye-level camera, photorealistic RAW photograph, single image only, no collage.
Pose: {pose}.
Expression: {expression}.
Crop: {crop}.
Lighting: {lighting}.
```

## Negative Prompt

No collage, no grid, no multiple faces, no identity drift, no generic beauty model, no changed face structure, no changed eye shape, no plastic skin, no waxy skin, no blur, no deformed hands, no asymmetric eyes, no different earrings, no necklace unless requested, no blouse redesign, no logos, no text, no over-retouching.

## Production Rule

The ivory silk blouse with delicate gold floral embroidery is the v1 hero look, not a permanent uniform. Alternate outfits, jewelry-light variants, and Bali context backgrounds are allowed once the face passes identity QA against `ZAN-V1-A001` and `ZAN-V1-A002`.
""",
        encoding="utf-8",
    )


def write_production_priority_queue(dataset_root: Path) -> None:
    prompts_dir = dataset_root / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []

    def add(
        shot_id: str,
        priority: str,
        category: str,
        purpose: str,
        pose: str,
        expression: str,
        crop: str,
        lighting: str,
        background: str,
        outfit: str,
        hair: str,
        jewelry: str,
        qa_gate: str,
    ) -> None:
        prompt = (
            "Ultra-realistic photorealistic RAW image of Zantara, the same adult Indonesian woman from the official Zantara v1 anchors. "
            "Preserve facial identity: warm medium skin tone, dark almond-shaped eyes, defined cheekbones, same hairline, natural proportions, subtle makeup, sharp black eyeliner. "
            f"Hair: {hair}. Jewelry: {jewelry}. Outfit: {outfit}. Background: {background}. Lighting: {lighting}. "
            "Single subject only, no collage, no text, no logo, no watermark, realistic skin texture, natural pores, no plastic skin. "
            f"Pose: {pose}. Expression: {expression}. Crop: {crop}. "
            "Negative: no identity drift, no generic beauty model, no changed eye shape, no changed jaw, no waxy retouching, no deformed hands, no inconsistent wardrobe."
        )
        rows.append(
            {
                "shot_id": shot_id,
                "priority": priority,
                "category": category,
                "purpose": purpose,
                "pose": pose,
                "expression": expression,
                "crop": crop,
                "lighting": lighting,
                "background": background,
                "outfit": outfit,
                "hair": hair,
                "jewelry": jewelry,
                "qa_gate": qa_gate,
                "prompt": prompt,
            }
        )

    hero_outfit = "ivory silk blouse with delicate gold floral embroidery"
    charcoal_outfit = "structured charcoal silk blouse with subtle antique gold trim"
    blazer_outfit = "black modern blazer over ivory silk blouse with restrained gold embroidery"
    studio_gray = "neutral gray studio background"
    rice_terrace = "early morning Bali rice terrace with soft volcanic haze, shallow depth of field, background subdued and not touristic"
    temple_courtyard = "quiet Balinese temple courtyard with carved stone and warm amber highlights, respectful editorial framing"
    wood_office = "Bali Zero office interior with dark teak, neutral wall, subtle legal archive shelves, no visible text"
    banyan = "ancient banyan tree setting with warm amber practical lights, cinematic but photorealistic"

    add("ZAN-V1-PRI-001", "P0", "identity_anchor", "missing high-resolution primary front anchor", "front-facing", "neutral calm", "head and shoulders", "soft front studio light", studio_gray, hero_outfit, COMMON_HAIR, "small gold hoop earrings", "must match A001/A002 face before use")
    add("ZAN-V1-PRI-002", "P0", "identity_anchor", "front anchor alternate expression", "front-facing", "serious protective", "head and shoulders", "soft front studio light", studio_gray, hero_outfit, COMMON_HAIR, "small gold hoop earrings", "must match A001/A002 face before use")
    add("ZAN-V1-PRI-003", "P0", "angle", "missing left profile", "left profile 90 degrees", "neutral", "bust profile portrait", "soft side light from camera-right", studio_gray, hero_outfit, COMMON_HAIR, "small gold hoop earrings", "profile must keep nose, brow, jaw coherent")
    add("ZAN-V1-PRI-004", "P0", "angle", "balanced profile pair", "right profile 90 degrees", "neutral", "bust profile portrait", "soft side light from camera-left", studio_gray, hero_outfit, COMMON_HAIR, "small gold hoop earrings", "compare to existing B011 before approval")
    add("ZAN-V1-PRI-005", "P0", "body", "standing production reference", "standing front-facing", "neutral confident", "full body standing", "soft front studio light", studio_gray, "ivory embroidered blouse with simple black tailored trousers", COMMON_HAIR, "small gold hoop earrings", "hands must be natural or relaxed out of frame")
    add("ZAN-V1-PRI-006", "P0", "body", "seated production reference", "seated front-facing", "calm attentive", "half body seated", "soft front studio light", studio_gray, hero_outfit, COMMON_HAIR, "small gold hoop earrings", "hands must be anatomically clean")

    add("ZAN-V1-PRI-007", "P1", "lighting", "controlled side light left", "front-facing", "neutral", "head and shoulders", "side light from camera-left", studio_gray, hero_outfit, COMMON_HAIR, "small gold hoop earrings", "same identity, no face reshaping from shadow")
    add("ZAN-V1-PRI-008", "P1", "lighting", "controlled side light right", "front-facing", "neutral", "head and shoulders", "side light from camera-right", studio_gray, hero_outfit, COMMON_HAIR, "small gold hoop earrings", "same identity, no face reshaping from shadow")
    add("ZAN-V1-PRI-009", "P1", "lighting", "high-key production variant", "front-facing", "neutral", "head and shoulders", "high-key soft studio light", "clean white studio background", hero_outfit, COMMON_HAIR, "small gold hoop earrings", "avoid plastic skin")
    add("ZAN-V1-PRI-010", "P1", "lighting", "dark gray editorial variant", "front-facing", "neutral", "head and shoulders", "low-key editorial softbox light", "dark neutral gray studio background", hero_outfit, COMMON_HAIR, "small gold hoop earrings", "retain eye detail")

    add("ZAN-V1-PRI-011", "P1", "outfit", "charcoal blouse variant", "front-facing", "neutral confident", "bust portrait", "soft front studio light", studio_gray, charcoal_outfit, COMMON_HAIR, "small gold hoop earrings", "outfit can vary only if face passes QA")
    add("ZAN-V1-PRI-012", "P1", "outfit", "black blazer authority variant", "front-facing", "archival calm", "bust portrait", "soft front studio light", studio_gray, blazer_outfit, COMMON_HAIR, "small gold hoop earrings", "outfit can vary only if face passes QA")
    add("ZAN-V1-PRI-013", "P2", "jewelry", "reduced jewelry variant", "front-facing", "neutral", "head and shoulders", "soft front studio light", studio_gray, hero_outfit, COMMON_HAIR, "no visible earrings", "approve only if lack of earrings does not change identity")
    add("ZAN-V1-PRI-014", "P2", "jewelry", "pearl earring variant", "front-facing", "neutral", "head and shoulders", "soft front studio light", studio_gray, hero_outfit, COMMON_HAIR, "small pearl stud earrings", "approve only after A/B with gold hoop anchor")

    add("ZAN-V1-PRI-015", "P1", "bali_context", "rice terrace authority portrait", "three-quarter right", "calm confident", "bust portrait", "soft golden morning light", rice_terrace, hero_outfit, COMMON_HAIR, "small gold hoop earrings", "background must not overpower face")
    add("ZAN-V1-PRI-016", "P1", "bali_context", "temple courtyard portrait", "front-facing", "protective serious", "bust portrait", "warm diffused courtyard light", temple_courtyard, hero_outfit, COMMON_HAIR, "small gold hoop earrings", "respectful, non-costume framing")
    add("ZAN-V1-PRI-017", "P1", "bali_context", "office authority portrait", "front-facing", "measured archival", "half body", "soft window light from camera-left", wood_office, blazer_outfit, COMMON_HAIR, "small gold hoop earrings", "no readable documents or text")
    add("ZAN-V1-PRI-018", "P2", "bali_context", "banyan cinematic reference", "three-quarter right", "protective calm", "half body", "warm amber cinematic light", banyan, charcoal_outfit, COMMON_HAIR, "small gold hoop earrings", "cinematic but still photorealistic")

    add("ZAN-V1-PRI-019", "P2", "hair", "hair behind ears", "front-facing", "neutral", "head and shoulders", "soft front studio light", studio_gray, hero_outfit, "long straight black hair, center part, tucked behind both ears", "small gold hoop earrings", "same hairline and face shape")
    add("ZAN-V1-PRI-020", "P2", "hair", "loose low bun variant", "front-facing", "neutral", "head and shoulders", "soft front studio light", studio_gray, hero_outfit, "long black hair gathered in a loose low bun, same hairline and color", "small gold hoop earrings", "do not change age or face")

    csv_path = prompts_dir / "production_priority_queue_v1.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    jsonl_path = prompts_dir / "production_priority_queue_v1.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_voice_ingredient_guide(dataset_root: Path) -> None:
    voice_dir = dataset_root / "voice"
    voice_dir.mkdir(parents=True, exist_ok=True)
    (voice_dir / "VOICE_INGREDIENT_V1.md").write_text(
        """# Zantara Voice Ingredient v1

Status: missing. This dataset is visually production-ready for silent/VO-less clips, but spoken Veo clips need a voice ingredient before serial production.

## Target Voice

- Adult Indonesian English, warm, precise, protective.
- Medium-low female register, calm authority, no influencer brightness.
- Natural soft Indonesian English accent.
- Pace: measured, 130-145 words per minute.
- Delivery: clear legal/regulatory terms, softens at reassurance, sharpens on risk words.

## Recording Script

Record 45-75 seconds in a quiet room, WAV 48 kHz if possible.

```text
Beautiful villa. Five years prison. Know the difference.

Permenkumham twenty-two of twenty-twenty-three. C one replaces B two one one A. Sixty days. One extension.

Bali does not punish clarity. Bali punishes assumptions.

Before you sign, we verify the land, the license, the tax position, and the person asking you to trust them.

I am Zantara. I do not sell certainty. I show you where certainty ends.
```

## Veo Prompt Voice Line

Use this sentence in every spoken clip until a stable voice ingredient exists:

```text
Zantara speaks with a warm, precise, calm adult Indonesian English voice, medium-low female register, natural soft Indonesian English accent, measured pace, protective authority, no influencer tone.
```

## Acceptance Gate

- Same timbre across three regenerated clips.
- Visa/legal codes pronounced clearly.
- No American/British accent drift.
- No over-dramatic trailer voice.
- No childish or overly cheerful tone.
""",
        encoding="utf-8",
    )


def write_docs(dataset_root: Path, records: list[dict[str, str | int | None]], source_records: list[dict[str, str | int]]) -> None:
    approved_count = sum(1 for record in records if record["status"] == "approved")
    anchor_count = sum(1 for record in records if record["usage_tier"] == "A_anchor")
    pose_count = sum(1 for record in records if record["usage_tier"] == "B_pose_expression")
    rejected_count = sum(1 for source in source_records if source["status"] == "rejected")

    (dataset_root / "README.md").write_text(
        f"""# Zantara Visual Dataset v1

Official local seed dataset for Zantara photo and video production.

## Status

- Approved single images: {approved_count}
- Primary/secondary identity anchors: {anchor_count}
- Pose/expression references split from collages: {pose_count}
- Rejected source files: {rejected_count}
- Collages kept only under `reference_only/`

## Folder Contract

- `approved/anchors/` - highest-trust face identity references.
- `approved/poses/` - single-frame pose/expression crops split from source collages.
- `ingredients/` - convenience copies for Google Flow / Veo / image-to-video ingredients.
- `reference_only/collages/` - original grids; never train directly on these.
- `rejected/` - excluded files with reasons in `metadata/manifest.json`.
- `metadata/captions.csv` and `metadata/captions.jsonl` - per-image captions.
- `prompts/generation_queue_v1.csv` - controlled prompt queue for completing the 40-80 image production set.
- `prompts/production_priority_queue_v1.csv` - first 20 shots to generate before expanding the library.
- `voice/VOICE_INGREDIENT_V1.md` - voice target, recording script, and Veo prompt line.

## Identity Lock

Zantara v1 is an adult Indonesian woman with warm medium skin tone, dark almond-shaped eyes, defined cheekbones, subtle natural makeup, sharp black eyeliner, and long straight black hair parted in the center.

The ivory silk blouse with delicate gold floral embroidery is the v1 hero look, not a permanent uniform. Gold hoop earrings are the current default anchor detail, not a lifetime lock.

Use `approved/anchors/zan_v1_a001_primary_3q_bust_anchor.png` and `approved/anchors/zan_v1_a002_primary_3q_face_closeup_anchor.png` as the main identity references.

## Hard Rules

- Do not use collage files as direct training images.
- Do not mix in the rejected JPEGs; they drift from the official face.
- Do not overweight duplicate images; `riri.png` is a byte-identical duplicate of `zan2.png`.
- Every generated addition must be a single image with a caption row before entering `approved/`.
- Studio gray is the identity lab, not the whole brand world. Production candidates should add Bali Zero contexts after face QA.
""",
        encoding="utf-8",
    )

    (dataset_root / "DATASET_CARD.md").write_text(
        """# Dataset Card - Zantara Visual Dataset v1

## Purpose

This is the official seed dataset for Zantara character consistency across Bali Zero photo, video, Google Flow, Veo, Imagen, and editorial production.

## Source Material

The dataset was built from seven local user-provided reference files on `/Users/nuzantara/Desktop/`. Two collage files were split into single-frame crops. Two high-resolution single portraits became anchors. Two generated JPEGs were rejected for identity drift. One duplicate PNG was rejected.

## Approved Use

- Character identity lock for synthetic Zantara production.
- Pose, expression, crop, angle, and lighting reference.
- Ingredient/reference upload to video and image generation tools.
- Internal production QA.

## Not Approved

- Direct training on collage/grid images.
- Client-facing publication of raw dataset structure.
- Treating rejected files as alternate identities.
- Using this as evidence about any real person.

## Current Gaps

- Missing high-resolution front-facing neutral anchor.
- Missing high-resolution left profile.
- Missing full-body and seated references.
- Missing controlled lighting variants.
- Missing outfit variants beyond the ivory embroidered blouse.
- Missing Bali-context references: rice terrace, temple courtyard, dark teak office, banyan cinematic setup.
- Missing jewelry-light variants: no earring / pearl stud / alternate subtle earring.
- Missing voice ingredient for spoken Veo 3.1 clips.

Generated candidates may exist under `generated_candidates/`, but nothing there is approved until QA promotes it into `approved/`.

## Acceptance Gate For New Images

New images can enter `approved/` only if they preserve face shape, eye shape, hairline, skin texture, and single-subject framing. Outfit, jewelry, and background may vary, but only after the face passes QA against the anchor pair. Reject blur, plastic skin, identity drift, deformed hands, visible text, or collage outputs.
""",
        encoding="utf-8",
    )

    (dataset_root / "SHOT_LIST.md").write_text(
        """# Shot List v1

## Already Covered By Current Seed

- Three-quarter right high-resolution bust anchor.
- Three-quarter right close-up anchor.
- Front-facing neutral, serious, slight smile, soft smile, open smile.
- Gaze down and lateral gaze.
- Chin-high confident expression.
- Right profile.
- Rear hair/outfit view.

## Next Production Batch

Use `prompts/production_priority_queue_v1.csv` before the longer `prompts/generation_queue_v1.csv`. Priority order:

1. High-resolution front-facing neutral, serious, slight smile, eyes closed.
2. Left profile and right profile at 90 degrees.
3. Full-body, three-quarter body, seated, standing.
4. Side-light left/right and high-key/dark-gray background variants.
5. Bali contexts: rice terrace, temple courtyard, dark teak office, banyan cinematic.
6. Alternate outfits: charcoal blouse, black blazer, simple trousers.
7. Jewelry-light variants only after the face passes QA.
8. Voice ingredient recording before serial spoken video production.

## QA Rubric

- 5/5 identity: same face structure, eye shape, skin tone, hairline.
- 5/5 production quality: sharp, realistic skin texture, no artifacts.
- 5/5 controllability: single pose/expression/crop only.
- 5/5 wardrobe/context control: outfit, jewelry, and background are intentional, not accidental drift.

Anything below 18/20 stays in `rejected/` or `reference_only/`.
""",
        encoding="utf-8",
    )


def write_manifest(
    dataset_root: Path,
    repo_root: Path,
    records: list[dict[str, str | int | None]],
    source_records: list[dict[str, str | int]],
) -> None:
    metadata_dir = dataset_root / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(ZoneInfo("Asia/Makassar"))
    manifest = {
        "dataset": "zantara_visual_dataset",
        "version": "v1",
        "created_at_wita": now.isoformat(),
        "repo_head": git_head(repo_root),
        "root": str(dataset_root),
        "counts": {
            "approved": sum(1 for record in records if record["status"] == "approved"),
            "anchors": sum(1 for record in records if record["usage_tier"] == "A_anchor"),
            "pose_expression": sum(1 for record in records if record["usage_tier"] == "B_pose_expression"),
            "reference_sources": sum(1 for source in source_records if source["status"] == "reference_only"),
            "rejected_sources": sum(1 for source in source_records if source["status"] == "rejected"),
        },
        "identity_lock": {
            "character": "Zantara",
            "description": "adult Indonesian woman, warm medium skin tone, dark almond-shaped eyes, defined cheekbones, long straight black center-parted hair, small gold hoop earrings, ivory silk blouse with delicate gold floral embroidery",
            "primary_anchor_ids": ["ZAN-V1-A001", "ZAN-V1-A002"],
        },
        "source_files": source_records,
        "items": records,
    }
    (metadata_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_contact_sheet(dataset_root: Path, records: list[dict[str, str | int | None]]) -> None:
    contact_dir = dataset_root / "contact_sheets"
    contact_dir.mkdir(parents=True, exist_ok=True)
    thumbs: list[tuple[str, Image.Image]] = []
    for record in records:
        path = dataset_root / str(record["path"])
        with Image.open(path) as image:
            thumb = image.convert("RGB")
            thumb.thumbnail((220, 220), Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", (240, 270), "white")
            x = (240 - thumb.width) // 2
            canvas.paste(thumb, (x, 10))
            draw = ImageDraw.Draw(canvas)
            label = str(record["asset_id"])
            draw.text((10, 235), label, fill=(20, 20, 20), font=ImageFont.load_default())
            thumbs.append((label, canvas))

    cols = 5
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 240, rows * 270), (245, 245, 245))
    for index, (_, thumb) in enumerate(thumbs):
        x = (index % cols) * 240
        y = (index // cols) * 270
        sheet.paste(thumb, (x, y))
    sheet.save(contact_dir / "approved_v1_contact_sheet.png", format="PNG", optimize=True)


def copy_ingredients(dataset_root: Path) -> None:
    ingredients_dir = dataset_root / "ingredients"
    ingredients_dir.mkdir(parents=True, exist_ok=True)
    anchor = dataset_root / "approved" / "anchors" / "zan_v1_a001_primary_3q_bust_anchor.png"
    face = dataset_root / "approved" / "anchors" / "zan_v1_a002_primary_3q_face_closeup_anchor.png"
    front = dataset_root / "approved" / "poses" / "zan_v1_b009_front_neutral_square.png"
    shutil.copy2(anchor, ingredients_dir / "zantara-face-anchor-v1.png")
    shutil.copy2(face, ingredients_dir / "zantara-face-closeup-anchor-v1.png")
    shutil.copy2(front, ingredients_dir / "zantara-front-neutral-reference-v1.png")


def build_dataset(repo_root: Path, dataset_root: Path) -> None:
    logger.info("Building Zantara visual dataset at %s", dataset_root)
    source_by_key = {source.key: source for source in SOURCE_ASSETS}
    source_records = copy_raw_sources(dataset_root)

    records: list[dict[str, str | int | None]] = []
    for item in [*APPROVED_ITEMS, *grid_items()]:
        source = source_by_key[item.source_key]
        records.append(write_image_item(item, source, dataset_root))

    copy_ingredients(dataset_root)
    write_captions(dataset_root, records)
    write_generation_queue(dataset_root)
    write_production_priority_queue(dataset_root)
    write_voice_ingredient_guide(dataset_root)
    write_manifest(dataset_root, repo_root, records, source_records)
    make_contact_sheet(dataset_root, records)
    write_docs(dataset_root, records, source_records)
    logger.info("Dataset complete: %d approved image assets", len(records))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Nuzantara repo root",
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=None,
        help="Output root; defaults to research/marketing/zantara-visual-dataset/v1 under the repo",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    repo_root = args.repo_root.resolve()
    dataset_root = args.dataset_root or repo_root / "research" / "marketing" / "zantara-visual-dataset" / "v1"
    build_dataset(repo_root, dataset_root.resolve())


if __name__ == "__main__":
    main()
