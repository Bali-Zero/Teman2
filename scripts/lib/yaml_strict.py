"""Strict YAML loading for documents that decide whether an action is PERMITTED.

WHY THIS EXISTS. PyYAML's `safe_load` accepts a duplicate top-level key and lets the
LAST one win, in silence — no warning, no error. For a config that is data, that is a
quirk. For a document that encodes a POLICY it is a review-defeating defect: appending
two lines at the end of a long file replaces the section that governs, and the diff reads
as one added line.

Measured on this repo, 2026-09-04, with `yaml.safe_load` on copies of the real files:

    agent-library/config/redaction-rules.yaml   pass1:  18 rules -> 0
    apps/team-agent/.../config/roles.yaml       roles:  4 roles -> 1, tools: ["*"]
    scripts/verify_the_verifiers_gates.yaml     gates:  34 -> 0

The first stops NPWP, KTP, passport, bank-account and OSINT patterns from being stripped
before text leaves to an external LLM, while passes 2-4 keep running so the output looks
entirely normal. The second is privilege escalation. The third blinds the meta-verifier
whose whole job is to make "a gate is DISARMED" observable.

This is NOT a claim that the repository is breached: anyone who can append to those files
can already edit them outright. What the silence defeats is REVIEW, and review is the
control this repo actually relies on.

WHAT IS REFUSED, and why each one:

  duplicate keys   the defect above.
  aliases (`*x`)   an anchor defined far from its use means the governing value is not
                   where the reviewer is looking.
  merge keys (`<<`) the same, one level worse: it splices a mapping in wholesale.

SCOPE, deliberately narrow. This is for POLICY documents only — six of them, eight call
sites. 76 files in this repo load YAML; pointing all of them here would be the over-match
twin of the defect it cures (superscar #3): a CI config or a test fixture with a duplicate
key is a mistake to fix, not an attack to refuse, and failing them buys no safety.

Lineage: `UniqueKeyLoader` in `scripts/tests/test_runtime_truth_ci_gauntlet.py` already had
the duplicate-key half, scoped to one CI workflow. This is that idea promoted to one shared
place with the alias half added, rather than a fourth copy (superscar #1).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class StrictYAMLError(RuntimeError):
    """A policy document was ambiguous. Callers must fail CLOSED on this."""


class StrictLoader(yaml.SafeLoader):
    """`SafeLoader` that refuses duplicate keys, aliases and merge keys."""


def _compose_node(self: StrictLoader, parent: Any, index: Any) -> Any:
    """Refuse aliases before they resolve.

    Checked at COMPOSE time rather than on the constructed value: by the time a
    document is built, an alias is indistinguishable from a value written inline,
    which is exactly the property that makes it unreviewable.
    """
    if self.check_event(yaml.events.AliasEvent):
        event = self.peek_event()
        raise StrictYAMLError(
            f"YAML alias `*{event.anchor}` at line {event.start_mark.line + 1}: a policy "
            f"document may not carry aliases — the governing value would live somewhere "
            f"other than where it is read."
        )
    return yaml.SafeLoader.compose_node(self, parent, index)


def _construct_mapping(self: StrictLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    """Refuse duplicate keys and merge keys, naming the line so the fix is findable."""
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        if key_node.tag == "tag:yaml.org,2002:merge":
            raise StrictYAMLError(
                f"YAML merge key `<<` at line {key_node.start_mark.line + 1}: a policy "
                f"document may not splice another mapping in wholesale."
            )
        key = self.construct_object(key_node, deep=deep)
        if key in mapping:
            raise StrictYAMLError(
                f"duplicate key `{key}` at line {key_node.start_mark.line + 1}: PyYAML "
                f"would let the LAST one win in silence, so appending a section at the "
                f"end of this file would replace the one above it and review as a single "
                f"added line."
            )
        mapping[key] = self.construct_object(value_node, deep=deep)
    return mapping


StrictLoader.compose_node = _compose_node  # type: ignore[method-assign]
StrictLoader.construct_mapping = _construct_mapping  # type: ignore[method-assign]
StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    lambda loader, node: _construct_mapping(loader, node, deep=False),
)


def load_policy_text(text: str, *, source: str = "<text>") -> dict[str, Any]:
    """Parse a policy document. Raises `StrictYAMLError` on anything ambiguous.

    An empty document raises rather than returning `{}`: every caller here reads a
    document whose ABSENCE of rules is itself a disarmed control, and `{}` is the shape
    that then flows on looking normal.
    """
    try:
        document = yaml.load(text, Loader=StrictLoader)
    except StrictYAMLError:
        raise
    except yaml.YAMLError as exc:
        raise StrictYAMLError(f"{source}: not parseable as YAML ({type(exc).__name__})") from exc
    if not isinstance(document, dict) or not document:
        raise StrictYAMLError(
            f"{source}: a policy document must be a non-empty mapping, got "
            f"{type(document).__name__}"
        )
    return document


def load_policy(path: Path | str) -> dict[str, Any]:
    """`load_policy_text` over a file, with the path in every error message."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StrictYAMLError(f"policy document unreadable at {path}: {exc}") from exc
    return load_policy_text(text, source=str(path))
