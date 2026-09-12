"""Obligations register engine: statutory-obligation catalog, applicability and due dates.

Pure functions; the only I/O is load_catalog reading the YAML catalog
(backend/data/obligations_catalog.yaml). Nothing here writes to a database or sends anything.

Due-date semantics (v1):
- monthly: the period is a calendar month; due on `day` of the month that is
  `months_after_period_end` months after it (0 = the same month).
- quarterly: Q1..Q4 of the client's fiscal year (basis: fiscal, the default) or of the calendar
  year (basis: calendar); due on `day` of the month `months_after_period_end` after the quarter's
  last month.
- annual: the period is the fiscal year; due on `day` of the month `months_after_period_end`
  after its last month, or on the first `month`/`day` after the fiscal year end when `month` is set.
- one_time / event: nothing is scheduled in v1; the rule names its `trigger` instead.
A `day` past the end of a month means that month's last day. Fiscal years are month-granular:
the MM of fiscal_year_end is the closing month. Period keys: "YYYY-MM" (monthly), "YYYY-Qn"
(calendar quarter), "FYyyyy-Qn" (fiscal quarter), "FYyyyy" (annual), where yyyy is the calendar
year in which the fiscal year ends.
roll=next_business_day moves a Saturday or Sunday to the following Monday. Indonesian national
holidays and cuti bersama are NOT modelled in v1: a due date on a holiday does not move.
The horizon window is [start, start + horizon_days): start inclusive, end exclusive, after rolling.
"""

from __future__ import annotations

import calendar
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "obligations_catalog.yaml"

COMPANY_TYPES = frozenset({"PT_PMA", "PT_PMDN", "CV", "KP3A", "KPPA", "FOREIGN_PLATFORM", "OTHER"})
BOOL_ATTRS = frozenset(
    {
        "has_employees",
        "has_foreign_employees",
        "pkp",
        "serves_indonesian_users_online",
        "pse_registered",
        "pmse_vat_appointed",
        "has_expat_staff_over_6_months",
    }
)
INT_ATTRS = frozenset({"employee_count", "annual_turnover_idr"})
ATTRIBUTES = BOOL_ATTRS | INT_ATTRS | {"company_type", "investment_stage", "fiscal_year_end"}
INVESTMENT_STAGES = frozenset({"construction", "commercial"})
OPS = frozenset({"eq", "in", "gte", "lte", "is_true", "is_false"})
SCHEDULED = frozenset({"monthly", "quarterly", "annual"})
FREQUENCIES = SCHEDULED | {"one_time", "event"}

_RULE_KEYS = frozenset(
    {"id", "name", "authority", "legal_source", "verified", "applies_if", "due"}
    | {"needs_review_reason", "trigger", "notes"}
)
_DUE_KEYS = frozenset({"frequency", "day", "month", "months_after_period_end", "roll", "basis"})
_RULE_ID_RE = re.compile(r"^[a-z0-9_]{3,64}$")
_FYE_RE = re.compile(r"^\d{2}-\d{2}$")
_COMPANY_TYPE_MAP = {
    "PT PMA": "PT_PMA",
    "PT PMDN": "PT_PMDN",
    "PT PERORANGAN": "PT_PMDN",
    "PT": "PT_PMDN",
    "CV": "CV",
    "KP3A": "KP3A",
    "KPPA": "KPPA",
}


class CatalogError(ValueError):
    """The obligations catalog is malformed."""


def _valid_fye(value: Any) -> bool:
    if not isinstance(value, str) or not _FYE_RE.match(value):
        return False
    try:
        date(2000, int(value[:2]), int(value[3:]))  # leap year: 02-29 is a valid year end
    except ValueError:
        return False
    return True


@dataclass(frozen=True)
class ClientProfile:
    """Applicability attributes of one client. Only company_type is required."""

    company_type: str
    has_employees: bool = False
    employee_count: int = 0
    has_foreign_employees: bool = False
    pkp: bool = False
    annual_turnover_idr: int | None = None
    investment_stage: str | None = None
    fiscal_year_end: str = "12-31"
    serves_indonesian_users_online: bool = False
    pse_registered: bool = False
    pmse_vat_appointed: bool = False
    has_expat_staff_over_6_months: bool = False

    def __post_init__(self) -> None:
        if self.company_type not in COMPANY_TYPES:
            raise ValueError(f"unknown company_type {self.company_type!r}")
        if not _valid_fye(self.fiscal_year_end):
            raise ValueError(f"fiscal_year_end must be MM-DD, got {self.fiscal_year_end!r}")


@dataclass(frozen=True)
class Predicate:
    attr: str
    op: str
    value: Any = None

    def holds(self, profile: ClientProfile) -> bool:
        actual = getattr(profile, self.attr)
        if self.op == "is_true":
            return actual is True
        if self.op == "is_false":
            return not actual
        if self.op == "eq":
            return bool(actual == self.value)
        if self.op == "in":
            return actual in self.value
        if actual is None:  # unknown number: keep the rule (safe superset)
            return True
        return bool(actual >= self.value) if self.op == "gte" else bool(actual <= self.value)


@dataclass(frozen=True)
class DueRule:
    frequency: str
    day: int | None
    month: int | None
    months_after_period_end: int
    roll: str
    basis: str


@dataclass(frozen=True)
class ObligationRule:
    id: str
    name: str
    authority: str
    legal_source: str
    verified: bool
    applies_if: tuple[Predicate, ...]
    due: DueRule
    needs_review_reason: str | None = None
    trigger: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class ProposedObligation:
    rule_id: str
    period_key: str
    due_date: date
    needs_review_reason: str | None


def _require(ok: bool, where: str, msg: str) -> None:
    if not ok:
        raise CatalogError(f"{where}: {msg}")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_predicate(raw: Any, where: str) -> Predicate:
    _require(isinstance(raw, Mapping), where, "predicate must be a mapping")
    extra = set(raw) - {"attr", "op", "value"}
    _require(not extra, where, f"unknown predicate keys {sorted(extra)}")
    attr, op, value = raw.get("attr"), raw.get("op"), raw.get("value")
    _require(attr in ATTRIBUTES, where, f"unknown attr {attr!r}")
    _require(op in OPS, where, f"unknown op {op!r}")
    if op in ("is_true", "is_false"):
        _require(
            attr in BOOL_ATTRS and "value" not in raw, where, f"{op} needs a bool attr, no value"
        )
    elif op in ("gte", "lte"):
        _require(
            attr in INT_ATTRS and _is_int(value), where, f"{op} needs an int attr and int value"
        )
    elif op == "in":
        _require(isinstance(value, list) and bool(value), where, "in needs a non-empty list")
        value = tuple(value)
    else:
        _require("value" in raw, where, "eq needs a value")
    if op in ("eq", "in"):
        bad = [v for v in (value if op == "in" else (value,)) if not _value_ok(attr, v)]
        _require(not bad, where, f"impossible {attr} value(s) {bad!r}")
    return Predicate(attr, op, value)


def _value_ok(attr: str, value: Any) -> bool:
    """A predicate value that the attribute can actually take (else the rule silently never fires)."""
    if attr in BOOL_ATTRS:
        return isinstance(value, bool)
    if attr in INT_ATTRS:
        return _is_int(value)
    if attr == "fiscal_year_end":
        return _valid_fye(value)
    domain = COMPANY_TYPES if attr == "company_type" else INVESTMENT_STAGES
    return isinstance(value, str) and value in domain


def _parse_due(raw: Any, where: str) -> DueRule:
    _require(isinstance(raw, Mapping), where, "due must be a mapping")
    extra = set(raw) - _DUE_KEYS
    _require(not extra, where, f"unknown due keys {sorted(extra)}")
    freq, day, month = raw.get("frequency"), raw.get("day"), raw.get("month")
    after = raw.get("months_after_period_end", 0)
    roll, basis = raw.get("roll", "none"), raw.get("basis", "fiscal")
    _require(freq in FREQUENCIES, where, f"unknown frequency {freq!r}")
    _require(roll in ("next_business_day", "none"), where, f"unknown roll {roll!r}")
    _require(basis in ("fiscal", "calendar"), where, f"unknown basis {basis!r}")
    _require(_is_int(after) and 0 <= after <= 24, where, "months_after_period_end must be 0..24")
    if freq in SCHEDULED:
        _require(_is_int(day) and 1 <= day <= 31, where, "day must be 1..31")
    else:
        _require(day is None, where, f"{freq} rules take no day")
    month_ok = month is None or (freq == "annual" and _is_int(month) and 1 <= month <= 12)
    _require(month_ok, where, "month must be null, or 1..12 on annual rules")
    return DueRule(freq, day, month, after, roll, basis)


def _parse_rule(raw: Any, index: int) -> ObligationRule:
    _require(isinstance(raw, Mapping), f"rule #{index}", "must be a mapping")
    where = f"rule {raw.get('id', index)!r}"
    extra = set(raw) - _RULE_KEYS
    missing = [k for k in ("id", "name", "authority", "legal_source", "due") if k not in raw]
    _require(not extra, where, f"unknown keys {sorted(extra)}")
    _require(not missing, where, f"missing keys {missing}")
    _require(isinstance(raw["id"], str) and bool(_RULE_ID_RE.match(raw["id"])), where, "bad id")
    for key in ("name", "authority", "legal_source", "needs_review_reason", "trigger", "notes"):
        val = raw.get(key)
        ok = isinstance(val, str) and bool(val.strip())
        _require(
            ok or (val is None and key not in ("name", "authority", "legal_source")), where, key
        )
    verified, preds = raw.get("verified", False), raw.get("applies_if", [])
    _require(isinstance(verified, bool), where, "verified must be a bool")
    _require(isinstance(preds, list), where, "applies_if must be a list")
    due = _parse_due(raw["due"], where)
    has_trigger = raw.get("trigger") is not None
    _require(has_trigger != (due.frequency in SCHEDULED), where, "trigger iff one_time/event")
    return ObligationRule(
        id=raw["id"],
        name=raw["name"],
        authority=raw["authority"],
        legal_source=raw["legal_source"],
        verified=verified,
        applies_if=tuple(_parse_predicate(p, where) for p in preds),
        due=due,
        needs_review_reason=raw.get("needs_review_reason"),
        trigger=raw.get("trigger"),
        notes=raw.get("notes"),
    )


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that refuses duplicate mapping keys instead of keeping the last one."""


def _unique_mapping(loader: _StrictLoader, node: yaml.MappingNode) -> dict[Any, Any]:
    keys = [loader.construct_object(k, deep=True) for k, _ in node.value]
    dupes = {str(k) for k in keys if keys.count(k) > 1}
    if dupes:
        raise CatalogError(f"line {node.start_mark.line + 1}: duplicate keys {sorted(dupes)}")
    return loader.construct_mapping(node, deep=True)


_StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def load_catalog(path: str | Path = DEFAULT_CATALOG_PATH) -> list[ObligationRule]:
    """Load and validate the catalog; raise CatalogError on any unknown key, op, attr or value."""
    with open(path, encoding="utf-8") as fh:
        doc = yaml.load(fh, Loader=_StrictLoader)  # SafeLoader subclass: no arbitrary objects
    _require(isinstance(doc, Mapping) and isinstance(doc.get("rules"), list), str(path), "no rules")
    rules = [_parse_rule(raw, i) for i, raw in enumerate(doc["rules"])]
    ids = [r.id for r in rules]
    _require(len(ids) == len(set(ids)), str(path), f"duplicate rule ids {sorted(ids)}")
    return rules


def applies(rule: ObligationRule, profile: ClientProfile) -> bool:
    return all(p.holds(profile) for p in rule.applies_if)


def _add_months(year: int, month: int, k: int) -> tuple[int, int]:
    total = year * 12 + month - 1 + k
    return total // 12, total % 12 + 1


def _on_day(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def _periods(
    rule: ObligationRule, profile: ClientProfile, years: range
) -> Iterable[tuple[str, date]]:
    due = rule.due
    day = due.day or 1
    fy_end = int(profile.fiscal_year_end[:2])
    for y in years:
        if due.frequency == "monthly":
            for m in range(1, 13):
                yield (
                    f"{y:04d}-{m:02d}",
                    _on_day(*_add_months(y, m, due.months_after_period_end), day),
                )
        elif due.frequency == "quarterly":
            close, prefix = (12, "") if due.basis == "calendar" else (fy_end, "FY")
            for q in range(1, 5):
                qy, qm = _add_months(y, close, -3 * (4 - q))
                yield (
                    f"{prefix}{y}-Q{q}",
                    _on_day(*_add_months(qy, qm, due.months_after_period_end), day),
                )
        elif due.frequency == "annual":
            if due.month is None:
                yield f"FY{y}", _on_day(*_add_months(y, fy_end, due.months_after_period_end), day)
            else:
                first = _on_day(y, due.month, day)
                later = first <= _on_day(y, fy_end, 31)
                yield f"FY{y}", _on_day(y + 1, due.month, day) if later else first


def due_dates(
    rule: ObligationRule, profile: ClientProfile, start: date, horizon_days: int
) -> list[tuple[str, date]]:
    """(period_key, due_date) pairs with due_date in [start, start + horizon_days), sorted."""
    if horizon_days < 0:
        raise ValueError("horizon_days must be >= 0")
    end = start + timedelta(days=horizon_days)
    span = rule.due.months_after_period_end // 12 + 2
    out = []
    for key, due in _periods(rule, profile, range(start.year - span, end.year + 2)):
        if rule.due.roll == "next_business_day":
            due += timedelta(days=max(0, 7 - due.weekday()) if due.weekday() >= 5 else 0)
        if start <= due < end:
            out.append((key, due))
    return sorted(out, key=lambda kd: (kd[1], kd[0]))


def propose(
    rules: Iterable[ObligationRule], profile: ClientProfile, start: date, horizon_days: int
) -> list[ProposedObligation]:
    out = [
        ProposedObligation(rule.id, key, due, rule.needs_review_reason)
        for rule in rules
        if applies(rule, profile)
        for key, due in due_dates(rule, profile, start, horizon_days)
    ]
    return sorted(out, key=lambda p: (p.due_date, p.rule_id, p.period_key))


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if _is_int(value) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("true", "yes", "y", "1"):
            return True
        if text in ("false", "no", "n", "0"):
            return False
    return None


def _as_int(value: Any) -> int | None:
    if _is_int(value) and value >= 0:
        return int(value)
    if isinstance(value, float) and value.is_integer() and value >= 0:
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _custom_fields(row: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = row.get("custom_fields") if row else None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return {}
    return dict(raw) if isinstance(raw, Mapping) else {}


@dataclass(frozen=True)
class ProfileInputs:
    """A computed profile plus WHICH custom_fields keys produced it.

    ``present_keys``: engine-recognised custom_fields keys that carried a value the engine could
    parse, so they actually shaped the profile. ``missing_attributes``: engine ATTRIBUTES left at
    their ClientProfile default because nothing valid was supplied (``company_type`` is listed
    when it fell back to OTHER without an explicit ``compliance_company_type``).
    """

    profile: ClientProfile
    present_keys: tuple[str, ...]
    missing_attributes: tuple[str, ...]


def profile_inputs(
    client_row: Mapping[str, Any] | None, company_row: Mapping[str, Any] | None
) -> ProfileInputs:
    """Build a profile from a clients row and a companies row, with its provenance.

    company_type precedence, highest first:
    1. ``custom_fields["compliance_company_type"]`` when it is one of COMPANY_TYPES. This key is
       written by PATCH /api/compliance/obligations/profile/{client_id} and WINS over the
       companies.company_type string, so a reviewer can classify a company whose string spelling
       the map below reads as OTHER.
    2. the companies.company_type string mapped through _COMPANY_TYPE_MAP ("PT PMA" -> PT_PMA,
       "PT Perorangan"/"PT" -> PT_PMDN, "CV" -> CV); anything unrecognised is OTHER.
    3. FOREIGN_PLATFORM, when 2. yielded OTHER and custom_fields has is_foreign_platform true.

    Every other attribute is read from custom_fields under its own name (companies.custom_fields
    wins over clients.custom_fields); missing or malformed values fall back to the ClientProfile
    defaults. has_employees is true if set or if employee_count > 0.
    """
    custom = {**_custom_fields(client_row), **_custom_fields(company_row)}
    present: list[str] = []
    supplied: set[str] = set()

    explicit = custom.get("compliance_company_type")
    company_type = explicit.strip().upper() if isinstance(explicit, str) else ""
    if company_type in COMPANY_TYPES:
        present.append("compliance_company_type")
        supplied.add("company_type")
    else:
        raw_type = str((company_row or {}).get("company_type") or "").upper()
        raw_type = " ".join(re.sub(r"\(.*?\)|\.", " ", raw_type).split())  # "PT. PMA (Persero)"
        company_type = _COMPANY_TYPE_MAP.get(raw_type, "OTHER")
        if company_type != "OTHER":
            supplied.add("company_type")
        elif _as_bool(custom.get("is_foreign_platform")):
            company_type = "FOREIGN_PLATFORM"
            present.append("is_foreign_platform")
            supplied.add("company_type")

    kwargs: dict[str, Any] = {"company_type": company_type}
    for name in BOOL_ATTRS:
        flag = _as_bool(custom.get(name))
        if flag is not None:
            kwargs[name] = flag
            present.append(name)
            supplied.add(name)
    for name in INT_ATTRS:
        number = _as_int(custom.get(name))
        if number is not None:
            kwargs[name] = number
            present.append(name)
            supplied.add(name)
    stage = custom.get("investment_stage")
    if isinstance(stage, str) and stage in INVESTMENT_STAGES:
        kwargs["investment_stage"] = stage
        present.append("investment_stage")
        supplied.add("investment_stage")
    if _valid_fye(custom.get("fiscal_year_end")):
        kwargs["fiscal_year_end"] = custom["fiscal_year_end"]
        present.append("fiscal_year_end")
        supplied.add("fiscal_year_end")
    kwargs["has_employees"] = (
        bool(kwargs.get("has_employees")) or kwargs.get("employee_count", 0) > 0
    )
    if kwargs["has_employees"]:  # explicit, or derived from a positive employee_count
        supplied.add("has_employees")
    return ProfileInputs(
        profile=ClientProfile(**kwargs),
        present_keys=tuple(sorted(present)),
        missing_attributes=tuple(sorted(ATTRIBUTES - supplied)),
    )


def profile_from_rows(
    client_row: Mapping[str, Any] | None, company_row: Mapping[str, Any] | None
) -> ClientProfile:
    """The profile only. See ``profile_inputs`` for the company_type precedence it applies."""
    return profile_inputs(client_row, company_row).profile


__all__ = [
    "ATTRIBUTES",
    "COMPANY_TYPES",
    "DEFAULT_CATALOG_PATH",
    "CatalogError",
    "ClientProfile",
    "DueRule",
    "ObligationRule",
    "Predicate",
    "ProfileInputs",
    "ProposedObligation",
    "applies",
    "due_dates",
    "load_catalog",
    "profile_from_rows",
    "profile_inputs",
    "propose",
]
