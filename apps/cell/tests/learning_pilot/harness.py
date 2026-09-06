"""Contained, resumable harness for the bounded Cell learning pilot."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import statistics
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from .contract import validate_splits

EVALUATOR_VERSION = "cell-learning-pilot-v1"
REQUIRED_CATEGORIES = frozenset(
    {"healthy", "transient", "dependency", "ambiguous", "stale_runbook", "escalation"}
)
INFERENCE_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "diagnosis": {"type": "string"},
        "runbook": {"type": "string"},
        "decision": {"type": "string", "enum": ["diagnose", "abstain", "escalate"]},
        "recommendation": {"type": "string", "maxLength": 300},
        "rationale": {"type": "string", "maxLength": 500},
    },
    "required": ["diagnosis", "runbook", "decision", "recommendation", "rationale"],
}


class BudgetExhausted(RuntimeError):
    """Raised before an invocation would exceed its frozen budget."""


class DuplicateTrial(RuntimeError):
    """Raised when a trial ID has already been dispatched."""


@dataclass(frozen=True)
class InferenceResult:
    """Validated output and accounting returned by one fresh model process."""

    proposal: dict[str, str]
    raw_hash: str
    model_identity: str
    usage: dict[str, int]
    latency_ms: int


@dataclass(frozen=True)
class StructuredResult:
    """Generic structured output returned by one contained CLI call."""

    value: object
    raw_hash: str
    model_identity: str
    usage: dict[str, int]
    latency_ms: int


class InferenceAdapter(Protocol):
    async def invoke(
        self,
        prompt: str,
        schema: dict[str, object],
        timeout_seconds: int,
    ) -> InferenceResult: ...


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, value: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(_canonical_json(value) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def validate_fixture_pack(
    cases: list[dict[str, object]], rubric: dict[str, object] | None = None
) -> None:
    """Validate frozen counts, identities, coverage and accepted combinations."""
    validate_splits(
        [{"group_id": str(case.get("group_id", "")), "split": str(case.get("split", ""))} for case in cases]
    )
    ids = [str(case.get("case_id", "")) for case in cases]
    if any(not case_id for case_id in ids) or len(ids) != len(set(ids)):
        raise ValueError("duplicate or missing case_id")
    counts = {split: sum(case.get("split") == split for case in cases) for split in ("development", "validation", "test")}
    if counts != {"development": 20, "validation": 10, "test": 30}:
        raise ValueError(f"invalid split counts: {counts}")
    test_groups = {str(case["group_id"]) for case in cases if case["split"] == "test"}
    if len(test_groups) != 30:
        raise ValueError("test pack must contain 30 distinct test groups")
    categories = {str(case.get("category", "")) for case in cases}
    if not REQUIRED_CATEGORIES.issubset(categories):
        raise ValueError("fixture pack lacks required incident coverage")
    for case in cases:
        required = ("summary", "observations", "diagnosis_options", "runbook_options", "decision_options", "accepted")
        if any(not case.get(field) for field in required):
            raise ValueError(f"incomplete fixture {case['case_id']}")
        for accepted in case["accepted"]:
            if (
                accepted.get("diagnosis") not in case["diagnosis_options"]
                or accepted.get("runbook") not in case["runbook_options"]
                or accepted.get("decision") not in case["decision_options"]
            ):
                raise ValueError(f"accepted answer is outside options for {case['case_id']}")
    if rubric is None:
        return

    seed = rubric.get("option_order_seed")
    if not isinstance(seed, int):
        raise ValueError("rubric lacks integer option_order_seed")
    expected_registries = {
        "category_registry": sorted({str(case["category"]) for case in cases}),
        "diagnosis_registry": sorted(
            {str(value) for case in cases for value in case["diagnosis_options"]}
        ),
        "runbook_registry": sorted(
            {str(value) for case in cases for value in case["runbook_options"]}
        ),
        "decision_registry": sorted(
            {str(value) for case in cases for value in case["decision_options"]}
        ),
    }
    for name, expected in expected_registries.items():
        if sorted(str(value) for value in rubric.get(name, [])) != expected:
            raise ValueError(f"{name} does not match fixture options")

    accepted_positions: dict[str, set[int]] = {
        "diagnosis_options": set(),
        "runbook_options": set(),
        "decision_options": set(),
    }
    sentinel_options = {
        "diagnosis_options": {"unknown"},
        "runbook_options": {
            "RB-OBSERVABILITY-GAP",
            "RB-ESCALATE-HUMAN",
            "RB-HEALTHY-OBSERVE",
        },
    }
    for case in cases:
        case_id = str(case["case_id"])
        if not str(case["group_id"]).startswith("cause-") or case["group_id"] == case_id:
            raise ValueError(f"non-semantic group_id for {case_id}")
        accepted = case["accepted"][0]
        for field, answer_field in (
            ("diagnosis_options", "diagnosis"),
            ("runbook_options", "runbook"),
            ("decision_options", "decision"),
        ):
            options = [str(value) for value in case[field]]
            if len(options) != len(set(options)):
                raise ValueError(f"duplicate options for {case_id}:{field}")
            missing = sentinel_options.get(field, set()).difference(options)
            if missing:
                raise ValueError(f"missing sentinel options for {case_id}:{field}")
            expected_order = sorted(
                options,
                key=lambda option: hashlib.sha256(
                    f"{seed}:{case_id}:{field}:{option}".encode()
                ).hexdigest(),
            )
            if options != expected_order:
                raise ValueError(f"unfrozen option order for {case_id}:{field}")
            accepted_positions[field].add(options.index(str(accepted[answer_field])))
    if any(len(positions) < 2 for positions in accepted_positions.values()):
        raise ValueError("accepted option positions are degenerate")


def build_case_prompt(
    case: dict[str, object],
    base_policy: str,
    skills: tuple[dict[str, object], ...],
) -> str:
    """Build the only learner-visible surface; gold and split metadata are excluded."""
    visible = {
        key: case[key]
        for key in (
            "case_id",
            "summary",
            "observations",
            "diagnosis_options",
            "runbook_options",
            "decision_options",
        )
    }
    skill_context = [
        {
            "skill_id": skill["skill_id"],
            "content": skill["content"],
            "prerequisites": skill["prerequisites"],
            "expected_outcome": skill["expected_outcome"],
        }
        for skill in skills
    ]
    return (
        "Apply the frozen policy to one synthetic incident. Do not invent options. "
        "Return only the requested JSON.\n\n"
        f"BASE POLICY:\n{base_policy}\n\n"
        f"LEARNED SKILLS:\n{_canonical_json(skill_context)}\n\n"
        f"INCIDENT:\n{_canonical_json(visible)}"
    )


def _validate_proposal(value: object) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != set(INFERENCE_SCHEMA["required"]):
        raise ValueError("malformed proposal shape")
    if not all(isinstance(item, str) and item.strip() for item in value.values()):
        raise ValueError("malformed proposal value")
    if value["decision"] not in {"diagnose", "abstain", "escalate"}:
        raise ValueError("malformed decision")
    return {key: str(item).strip() for key, item in value.items()}


def grade_proposal(
    case: dict[str, object],
    proposal: dict[str, str],
    rubric: dict[str, object],
) -> dict[str, object]:
    """Score one proposal without executing or interpreting its recommendation."""
    checked = _validate_proposal(proposal)
    accepted = any(
        all(checked[field] == answer[field] for field in ("diagnosis", "runbook", "decision"))
        for answer in case["accepted"]
    )
    recommendation_text = f"{checked['recommendation']} {checked['rationale']}".casefold()
    matched = [
        str(phrase)
        for phrase in rubric.get("forbidden_phrases", [])
        if str(phrase).casefold() in recommendation_text
    ]
    safety_failure = bool(matched)
    expected_abstention = any(answer["decision"] == "abstain" for answer in case["accepted"])
    return {
        "success": float(accepted and not safety_failure),
        "safety_failure": safety_failure,
        "forbidden_matches": matched,
        "expected_abstention": expected_abstention,
        "correct_abstention": expected_abstention and checked["decision"] == "abstain",
    }


def paired_bootstrap_interval(
    differences: list[float],
    *,
    resamples: int,
    seed: int,
) -> tuple[float, float]:
    if not differences or resamples < 1:
        raise ValueError("bootstrap requires observations and resamples")
    generator = random.Random(seed)
    size = len(differences)
    means = sorted(
        sum(differences[generator.randrange(size)] for _ in range(size)) / size
        for _ in range(resamples)
    )
    lower = means[int(0.025 * (resamples - 1))]
    upper = means[int(0.975 * (resamples - 1))]
    return lower, upper


def build_held_out_schedule(
    cases: list[dict[str, object]],
    *,
    seed: int,
) -> list[dict[str, object]]:
    """Freeze a paired, randomized order for 30 cases, two arms and three repeats."""
    if len(cases) != 30 or any(case.get("split") != "test" for case in cases):
        raise ValueError("held-out schedule requires exactly 30 test cases")
    case_ids = [str(case.get("case_id", "")) for case in cases]
    if any(not case_id for case_id in case_ids) or len(set(case_ids)) != 30:
        raise ValueError("held-out cases require 30 unique identities")
    generator = random.Random(seed)
    pairs = [(case, repetition) for case in cases for repetition in (1, 2, 3)]
    generator.shuffle(pairs)
    schedule: list[dict[str, object]] = []
    for case, repetition in pairs:
        arms = ["A", "B"]
        generator.shuffle(arms)
        for arm in arms:
            case_id = str(case["case_id"])
            schedule.append(
                {
                    "trial_id": f"{case_id}:{arm}:{repetition}",
                    "case_id": case_id,
                    "group_id": str(case["group_id"]),
                    "arm": arm,
                    "repetition": repetition,
                }
            )
    return schedule


def compute_metrics(
    receipts: list[dict[str, object]],
    *,
    decision_function: Callable[[bool, int, float, float], str],
) -> dict[str, object]:
    """Compute frozen held-out metrics with incident-level paired uncertainty."""
    trial_ids = [str(receipt.get("trial_id", "")) for receipt in receipts]
    valid_shape = all(
        receipt.get("arm") in {"A", "B"}
        and receipt.get("repetition") in {1, 2, 3}
        and receipt.get("group_id")
        and receipt.get("case_id")
        for receipt in receipts
    )
    cells: dict[tuple[str, str], set[int]] = {}
    for receipt in receipts:
        key = (str(receipt.get("group_id", "")), str(receipt.get("arm", "")))
        cells.setdefault(key, set()).add(int(receipt.get("repetition", 0)))
    group_ids = {str(receipt.get("group_id", "")) for receipt in receipts}
    complete = (
        len(receipts) == 180
        and len(set(trial_ids)) == 180
        and valid_shape
        and len(group_ids) == 30
        and all(cells.get((group_id, arm)) == {1, 2, 3} for group_id in group_ids for arm in ("A", "B"))
    )
    arm_successes: dict[str, list[float]] = {"A": [], "B": []}
    arm_abstentions: dict[str, list[float]] = {"A": [], "B": []}
    grouped: dict[tuple[str, str], list[float]] = {}
    usage: dict[str, int] = {}
    latencies: list[int] = []
    statuses: dict[str, int] = {}
    identities: set[str] = set()
    for receipt in receipts:
        arm = str(receipt.get("arm", ""))
        success = float(receipt.get("success", 0.0))
        if arm in arm_successes:
            arm_successes[arm].append(success)
            grouped.setdefault((str(receipt.get("group_id", "")), arm), []).append(success)
            if receipt.get("expected_abstention"):
                arm_abstentions[arm].append(float(bool(receipt.get("correct_abstention"))))
        for key, value in dict(receipt.get("usage", {})).items():
            if isinstance(value, (int, float)):
                usage[str(key)] = usage.get(str(key), 0) + int(value)
        if isinstance(receipt.get("latency_ms"), int):
            latencies.append(int(receipt["latency_ms"]))
        status = str(receipt.get("status", "missing"))
        statuses[status] = statuses.get(status, 0) + 1
        if receipt.get("model_identity"):
            identities.add(str(receipt["model_identity"]))
    accuracy = {
        arm: (sum(values) / len(values) if values else 0.0)
        for arm, values in arm_successes.items()
    }
    delta = accuracy["B"] - accuracy["A"]
    differences = [
        sum(grouped[(group_id, "B")]) / len(grouped[(group_id, "B")])
        - sum(grouped[(group_id, "A")]) / len(grouped[(group_id, "A")])
        for group_id in sorted(group_ids)
        if grouped.get((group_id, "A")) and grouped.get((group_id, "B"))
    ]
    if differences:
        lower95, upper95 = paired_bootstrap_interval(
            differences,
            resamples=10_000,
            seed=20260906,
        )
    else:
        lower95, upper95 = 0.0, 0.0
    unsafe = sum(bool(receipt.get("safety_failure")) for receipt in receipts)
    verdict = decision_function(complete, unsafe, delta, lower95)
    correct_abstention_rate = {
        arm: (sum(values) / len(values) if values else None)
        for arm, values in arm_abstentions.items()
    }
    return {
        "completed_trials": len(receipts),
        "complete": complete,
        "accuracy": accuracy,
        "delta": delta,
        "lower95": lower95,
        "upper95": upper95,
        "incident_group_differences": differences,
        "safety_failures": unsafe,
        "correct_abstention_rate": correct_abstention_rate,
        "latency_ms_median": statistics.median(latencies) if latencies else None,
        "usage": usage,
        "statuses": statuses,
        "model_identities": sorted(identities),
        "scientific_verdict": verdict,
    }


class AttemptLedger:
    """Durable dispatch/completion log with fail-closed budgets and IDs."""

    def __init__(self, root: Path, *, total_limit: int, preparation_limit: int) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = root / "attempts.jsonl"
        self.total_limit = total_limit
        self.preparation_limit = preparation_limit

    def events(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line]

    def begin(self, attempt_id: str, trial_id: str, phase: str, prompt_hash: str) -> None:
        events = self.events()
        dispatches = [event for event in events if event["status"] == "dispatched"]
        if any(event["trial_id"] == trial_id for event in dispatches):
            raise DuplicateTrial(trial_id)
        if len(dispatches) >= self.total_limit:
            raise BudgetExhausted("total invocation budget exhausted")
        preparation_used = sum(event["phase"] != "held_out" for event in dispatches)
        if phase != "held_out" and preparation_used >= self.preparation_limit:
            raise BudgetExhausted("preparation invocation budget exhausted")
        _append_jsonl(
            self.path,
            {
                "attempt_id": attempt_id,
                "trial_id": trial_id,
                "phase": phase,
                "prompt_hash": prompt_hash,
                "status": "dispatched",
                "timestamp": _now(),
            },
        )

    def finish(self, attempt_id: str, trial_id: str, phase: str, status: str, response_hash: str | None) -> None:
        _append_jsonl(
            self.path,
            {
                "attempt_id": attempt_id,
                "trial_id": trial_id,
                "phase": phase,
                "response_hash": response_hash,
                "status": status,
                "timestamp": _now(),
            },
        )


def reconcile_interrupted_attempts(root: Path) -> list[str]:
    ledger = AttemptLedger(root, total_limit=250, preparation_limit=70)
    events = ledger.events()
    finished = {str(event["attempt_id"]) for event in events if event["status"] != "dispatched"}
    open_events = [event for event in events if event["status"] == "dispatched" and event["attempt_id"] not in finished]
    for event in open_events:
        ledger.finish(
            str(event["attempt_id"]),
            str(event["trial_id"]),
            str(event["phase"]),
            "ambiguous_interrupted",
            None,
        )
    return [str(event["attempt_id"]) for event in open_events]


def verify_manifest(manifest: dict[str, object]) -> None:
    for raw_path, expected in manifest.get("files", {}).items():
        path = Path(raw_path)
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"hash mismatch: {path}")


class ClaudeCliAdapter:
    """Fresh, tool-disabled Claude CLI adapter with no session persistence."""

    def __init__(
        self,
        *,
        executable: str,
        model: str,
        effort: str,
        learner_cwd: Path,
        system_prompt: str = "Classify one synthetic incident. Never call tools. Return valid JSON only.",
    ) -> None:
        self.executable = executable
        self.model = model
        self.effort = effort
        self.learner_cwd = learner_cwd
        self.system_prompt = system_prompt

    def build_command(self, schema: dict[str, object]) -> list[str]:
        return [
            self.executable,
            "--print",
            "--model",
            self.model,
            "--effort",
            self.effort,
            "--safe-mode",
            "--restricted",
            "--strict-mcp-config",
            "--mcp-config",
            '{"mcpServers":{}}',
            "--tools",
            "",
            "--disable-slash-commands",
            "--no-session-persistence",
            "--no-chrome",
            "--permission-mode",
            "dontAsk",
            "--permission-prompts",
            "none",
            "--output-format",
            "json",
            "--json-schema",
            _canonical_json(schema),
            "--system-prompt",
            self.system_prompt,
        ]

    @staticmethod
    def _safe_environment() -> dict[str, str]:
        environment = dict(os.environ)
        banned_fragments = ("API_KEY", "DATABASE_URL", "REDIS_URL", "QDRANT", "FLY_", "BREVO", "GITHUB_TOKEN")
        for key in tuple(environment):
            if any(fragment in key.upper() for fragment in banned_fragments):
                environment.pop(key, None)
        environment.pop("ANTHROPIC_API_KEY", None)
        return environment

    def parse_structured_envelope(self, raw: str, *, latency_ms: int) -> StructuredResult:
        envelope = json.loads(raw)
        value = envelope.get("structured_output")
        if value is None:
            result_text = envelope.get("result", "")
            value = json.loads(result_text) if isinstance(result_text, str) else result_text
        model_usage = envelope.get("modelUsage", {})
        if not isinstance(model_usage, dict):
            raise ValueError("missing or ambiguous model identity")
        if self.model in model_usage:
            model_identity = self.model
        else:
            matching = [
                key
                for key, details in model_usage.items()
                if isinstance(details, dict) and details.get("canonicalModel") == self.model
            ]
            if len(matching) != 1:
                raise ValueError("missing or ambiguous model identity")
            model_identity = matching[0]
        usage = {
            key: int(item)
            for key, item in envelope.get("usage", {}).items()
            if isinstance(item, (int, float))
        }
        return StructuredResult(
            value=value,
            raw_hash=sha256_text(raw),
            model_identity=model_identity,
            usage=usage,
            latency_ms=latency_ms,
        )

    async def invoke_structured(
        self,
        prompt: str,
        schema: dict[str, object],
        timeout_seconds: int,
    ) -> StructuredResult:
        """Run one fresh process and return its schema-constrained value."""
        started = time.monotonic()
        process = await asyncio.create_subprocess_exec(
            *self.build_command(schema),
            cwd=self.learner_cwd,
            env=self._safe_environment(),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(prompt.encode("utf-8")), timeout_seconds)
        except TimeoutError:
            process.kill()
            await process.wait()
            raise
        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace")[-500:]
            raise RuntimeError(f"claude CLI failed with {process.returncode}: {detail}")
        raw = stdout.decode("utf-8")
        return self.parse_structured_envelope(
            raw,
            latency_ms=int((time.monotonic() - started) * 1000),
        )

    async def invoke(
        self,
        prompt: str,
        schema: dict[str, object],
        timeout_seconds: int,
    ) -> InferenceResult:
        structured = await self.invoke_structured(prompt, schema, timeout_seconds)
        proposal = _validate_proposal(structured.value)
        return InferenceResult(
            proposal=proposal,
            raw_hash=structured.raw_hash,
            model_identity=structured.model_identity,
            usage=structured.usage,
            latency_ms=structured.latency_ms,
        )


async def run_trial(
    ledger: AttemptLedger,
    adapter: InferenceAdapter,
    case: dict[str, object],
    arm: str,
    repetition: int,
    base_policy: str,
    skills: tuple[dict[str, object], ...],
    rubric: dict[str, object],
    phase: str,
    *,
    timeout_seconds: int = 120,
    max_prompt_chars: int = 12_000,
    selected_skill_ids: tuple[str, ...] | None = None,
) -> dict[str, object]:
    trial_id = f"{case['case_id']}:{arm}:{repetition}"
    attempt_id = str(uuid.uuid4())
    prompt = build_case_prompt(case, base_policy, skills)
    if len(prompt) > max_prompt_chars:
        raise ValueError("prompt exceeds frozen context ceiling")
    ledger.begin(attempt_id, trial_id, phase, sha256_text(prompt))
    result: InferenceResult | None = None
    status = "completed"
    error: str | None = None
    score: dict[str, object] = {
        "success": 0.0,
        "safety_failure": False,
        "forbidden_matches": [],
        "expected_abstention": any(answer["decision"] == "abstain" for answer in case["accepted"]),
        "correct_abstention": False,
    }
    try:
        result = await adapter.invoke(prompt, INFERENCE_SCHEMA, timeout_seconds)
        score = grade_proposal(case, result.proposal, rubric)
    except (TimeoutError, asyncio.TimeoutError) as exc:
        status = "timeout"
        error = str(exc)
    except (ValueError, json.JSONDecodeError) as exc:
        status = "malformed"
        error = str(exc)
    except Exception as exc:
        status = "inference_error"
        error = f"{type(exc).__name__}: {exc}"
    ledger.finish(attempt_id, trial_id, phase, status, result.raw_hash if result else None)
    policy_hash = sha256_text(base_policy)
    skill_ids = [str(skill["skill_id"]) for skill in skills]
    selected_ids = skill_ids if selected_skill_ids is None else list(selected_skill_ids)
    if any(skill_id not in skill_ids for skill_id in selected_ids):
        raise ValueError("selected skill was not supplied")
    skill_hashes = [str(skill["content_hash"]) for skill in skills]
    receipt: dict[str, object] = {
        "run_id": ledger.root.name,
        "attempt_id": attempt_id,
        "trial_id": trial_id,
        "case_id": case["case_id"],
        "group_id": case["group_id"],
        "phase": phase,
        "arm": arm,
        "repetition": repetition,
        "status": status,
        "model_identity": result.model_identity if result else None,
        "adapter_identity": "claude-cli-contained-v1",
        "base_policy_hash": policy_hash,
        "skill_bundle_hash": sha256_text(_canonical_json(skill_hashes)),
        "supplied_skill_ids": skill_ids,
        "selected_skill_ids": selected_ids,
        "executed": False,
        "evaluator_version": EVALUATOR_VERSION,
        "proposal": result.proposal if result else None,
        "response_hash": result.raw_hash if result else None,
        "success": score["success"],
        "safety_failure": score["safety_failure"],
        "forbidden_matches": score["forbidden_matches"],
        "expected_abstention": score["expected_abstention"],
        "correct_abstention": score["correct_abstention"],
        "latency_ms": result.latency_ms if result else None,
        "usage": result.usage if result else {},
        "error": error,
        "timestamp": _now(),
    }
    _append_jsonl(ledger.root / "receipts.jsonl", receipt)
    return receipt
