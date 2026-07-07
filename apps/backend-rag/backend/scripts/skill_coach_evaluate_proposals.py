"""Evaluate trajectory-derived skill proposals into redacted evidence cards."""

from __future__ import annotations

import argparse
import logging
import sys

from backend.services.skill_coach.service import (
    DEFAULT_DB_PATH,
    SKILL_COACH_EVIDENCE_PATH,
    SKILL_CREATION_PROPOSALS_PATH,
    SkillCoachService,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    description = (__doc__ or "Evaluate trajectory-derived skill proposals.").splitlines()[0]
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH)
    parser.add_argument("--proposals", default=SKILL_CREATION_PROPOSALS_PATH)
    parser.add_argument("--out", default=SKILL_COACH_EVIDENCE_PATH)
    parser.add_argument("--min-support", type=int, default=3)
    args = parser.parse_args(argv)

    service = SkillCoachService(
        db_path=args.db_path,
        proposals_path=args.proposals,
        evidence_path=args.out,
        min_support=args.min_support,
    )
    proposals = service.read_proposals()
    cards = service.evaluate_proposals(proposals)
    service.write_evidence(cards)
    logger.info(
        "skill-coach evidence written: %d cards -> %s",
        len(cards),
        args.out,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
