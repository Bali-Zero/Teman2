from __future__ import annotations

import json
import random
from datetime import datetime, timezone

from backend.services.autonomous_lab.planner import (
    AutonomousLabPlanner,
    MaterialSourceType,
    ResearchMaterial,
)
from backend.services.autonomous_lab.receipt_store import assert_receipt_persistable
from backend.services.autonomous_lab.reviewer import (
    AutonomousLabReviewer,
    invalid_autonomous_lab_target_path_reason,
)
from backend.services.autonomous_lab.shadow_run import build_shadow_run

SENSITIVE_SAMPLES = (
    "operator@example.com",
    "+62 812 3456 7890",
    "6281234567890@s.whatsapp.net",
    "api_key=sk-proj-abcdefghijklmnop",
    "https://example.test/path?token=abcdef1234567890&sig=123",
    "RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR",
)

SAFE_TARGETS = (
    "apps/backend-rag/backend/services/autonomous_lab/planner.py",
    "apps/backend-rag/backend/tests/unit/services/autonomous_lab/test_router.py",
    "research/operations/autonomous-lab/2026-06-16-sota-next-steps-plan.md",
    "scripts/autonomous_lab_run.py",
    "apps/admin-dashboard/app/autonomous-lab/page.tsx",
    "apps/admin-dashboard/lib/autonomous-lab.ts",
)

UNSAFE_TARGETS = (
    "../outside.py",
    "/etc/passwd",
    "~/Desktop/secret.py",
    "apps/admin-dashboard/app/legal/page.tsx",
    "apps/backend-rag/backend/services/autonomous_lab/planner.py\nBAD",
    "https://example.test/repo.py",
)


def test_planner_reviewer_and_receipt_store_mass_invariants() -> None:
    random.seed(17062026)
    planner = AutonomousLabPlanner(worktree_lane="ops")
    reviewer = AutonomousLabReviewer()
    captured_at = datetime(2026, 6, 17, tzinfo=timezone.utc)
    source_types = list(MaterialSourceType)

    for path in SAFE_TARGETS:
        assert invalid_autonomous_lab_target_path_reason(path) is None
    for path in UNSAFE_TARGETS:
        assert invalid_autonomous_lab_target_path_reason(path) is not None

    for index in range(72):
        sample = SENSITIVE_SAMPLES[index % len(SENSITIVE_SAMPLES)]
        source_type = random.choice(source_types)
        source_uri = _source_uri(index=index, source_type=source_type, sample=sample)
        material = ResearchMaterial(
            material_id=f"mass-{index}",
            source_type=source_type,
            source_uri=source_uri,
            title=f"Mass invariant material {index} {sample if index % 7 == 0 else ''}",
            text=(
                "AI agent workflow research should become a bounded Nuzantara experiment. "
                f"Private marker: {sample}"
            ),
            captured_at=captured_at,
            metadata={"tags": "ai,software,lab", "idx": str(index)},
        )
        targets = random.sample(SAFE_TARGETS, k=random.randint(1, 3))

        run = planner.draft_run(
            objective=f"mass objective {index}: {sample}",
            materials=[material],
            target_paths=list(targets),
            task_id=f"mass-{index}",
            created_at=captured_at,
        )
        receipt_text = json.dumps(run.to_receipt(), sort_keys=True)
        shadow_text = json.dumps(
            build_shadow_run(
                objective=f"shadow {sample}",
                target_paths=tuple(targets),
                task_id=f"shadow-{index}",
                created_at=captured_at,
            ).to_receipt(),
            sort_keys=True,
        )

        for raw in SENSITIVE_SAMPLES:
            assert raw not in receipt_text
            assert raw not in shadow_text
        assert reviewer.review(run).blocked is False
        assert_receipt_persistable(run.to_receipt())


def _source_uri(*, index: int, source_type: MaterialSourceType, sample: str) -> str:
    if index % 3 == 0:
        return f"https://research.example/item/{index}?token=abcdef1234567890"
    return f"{source_type.value}://local/{index}/{sample}"
