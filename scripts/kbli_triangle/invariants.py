"""KBLI Triangle — Layer 0: deterministic transitive invariants.

ZERO LLM. Pure rules over the canonical dataset. Each rule is a function
(code_record) -> list[Finding]. A Finding is logically forced by the data +
the cited regulation, never an opinion. Where the fix is forced (not a choice),
`auto_fix` carries the corrected (field_path, value); a fix that requires
judgment leaves auto_fix=None (report-only).

The PMA fingerprint (pma_status / pma_max_asing / pma_kondisi) is FROZEN: no
rule here may emit an auto_fix touching those fields. Findings ON them are
allowed but always report-only.

Transitive property: a verdict-layer field (l4_bali.*) is DERIVED from the
structural layer (pma_status, per_skala risk) + the regulatory source. A rule
that finds the derived layer contradicting the layer it depends on reports a
bug in the DERIVED field — never silently "fixes" the source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# ── Severity ladder ──────────────────────────────────────────────────────────
HIGH = "HIGH"      # client-misleading: a foreigner could act on a false green light
MED = "MED"        # internal contradiction, not directly client-facing
LOW = "LOW"        # provenance / flag hygiene
INFO = "INFO"      # observation, no action

# Fields whose mutation is forbidden by any auto_fix (PMA fingerprint, frozen).
PMA_FROZEN = ("pma_status", "pma_max_asing", "pma_kondisi")

# l4 statuses that assert Bali-registrability ("open"). Used by the national-
# closure dominance rule. Verified against the live taxonomy (9 distinct values).
L4_OPEN_STATUSES = {"OK_or_HIGHER_RISK", "APERTO_BALI_RISCHIO_ALTO"}

# Risk tiers that the 2026 Bali moratorium blocks for a PT PMA (island-wide).
# Source: Gubernur letter B.27.000/642/PM/DPMPTSP, effective 2026-05-13.
MORATORIUM_BLOCKED_RISK = {"Rendah", "Menengah Rendah"}

# Risk tiers requiring more than a bare NIB (Pasal 124(4) PP 28/2025).
RISK_NEEDS_LICENSE = {"Tinggi", "Menengah Tinggi"}


@dataclass
class Finding:
    code: str
    rule_id: str
    severity: str
    field: str
    evidence: str
    source: str  # regulation / structural fact the rule rests on
    auto_fix: Optional[tuple[str, Any]] = None  # (dotted_field_path, new_value)
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = {
            "code": self.code,
            "rule_id": self.rule_id,
            "severity": self.severity,
            "field": self.field,
            "evidence": self.evidence,
            "source": self.source,
            "auto_fixable": self.auto_fix is not None,
        }
        if self.auto_fix is not None:
            d["fix_path"], d["fix_value"] = self.auto_fix
        if self.note:
            d["note"] = self.note
        return d


# ── helpers ──────────────────────────────────────────────────────────────────
def _scales(rec: dict) -> list[dict]:
    return rec.get("per_skala") or []


def _has_besar(rec: dict) -> bool:
    for s in _scales(rec):
        for sk in s.get("skala_usaha") or []:
            if "besar" in sk.lower():
                return True
    return False


def _risk_tiers(rec: dict) -> set[str]:
    return {
        (s.get("kategori_risiko") or "").strip()
        for s in _scales(rec)
        if s.get("kategori_risiko")
    }


def _l4(rec: dict) -> dict:
    return rec.get("l4_bali") or {}


def _is_national_closed(rec: dict) -> bool:
    # TERTUTUP or a hard 0% cap, EXCEPT a special-distribution code (47221-class)
    # which is open-with-conditions, not closed.
    if rec.get("pma_cap_special") is True:
        return False
    return rec.get("pma_status") == "TERTUTUP" or rec.get("pma_max_asing") == 0


def _code(rec: dict) -> str:
    return str(rec.get("kode_kbli_2025") or rec.get("kode") or "")


# ── INVARIANTS ───────────────────────────────────────────────────────────────
# Each returns list[Finding]. Registered in RULES at the bottom.

def r_nat_dom(rec: dict) -> list[Finding]:
    """R-NAT-DOM (transitive): national TERTUTUP dominates the Bali verdict.
    pma_status==TERTUTUP  ⟹  l4.status must NOT be an 'open in Bali' status.
    This is the 58-code bug found 2026-06-29 (e.g. 84111 Lembaga Legislatif).
    Forced fix: the DERIVED l4.status is wrong → set to TERTUTUP. pma_* untouched.
    """
    if not _is_national_closed(rec):
        return []
    st = _l4(rec).get("status")
    if st in L4_OPEN_STATUSES:
        return [Finding(
            code=_code(rec), rule_id="R-NAT-DOM", severity=HIGH, field="l4_bali.status",
            evidence=f"pma_status={rec.get('pma_status')} max_asing={rec.get('pma_max_asing')} "
                     f"but l4.status={st} (asserts Bali-registrable)",
            source="Perpres 10/2021 negative-list; national closure dominates locality",
            auto_fix=("l4_bali.status", "TERTUTUP"),
            note="derived verdict contradicts frozen national layer",
        )]
    return []


def r_besar(rec: dict) -> list[Finding]:
    """R-BESAR (transitive): no Besar scale row ⟹ reserved UMKM ⟹ l4.blocked.
    A PT PMA is Besar by law (Perpres 49/2021 Annex II), so a code with no
    Usaha-Besar scale cannot host a PMA → blocked must be true.
    Report-only when pma is closed (R-NAT-DOM owns that); auto-fix only the
    blocked flag on nationally-open codes lacking Besar.
    """
    if _has_besar(rec) or not _scales(rec):
        return []
    l4 = _l4(rec)
    if l4.get("blocked") is True:
        return []
    sev = HIGH if not _is_national_closed(rec) else MED
    fix = ("l4_bali.blocked", True) if not _is_national_closed(rec) else None
    return [Finding(
        code=_code(rec), rule_id="R-BESAR", severity=sev, field="l4_bali.blocked",
        evidence="per_skala has no 'Besar' row but l4.blocked is not true",
        source="Perpres 49/2021 Annex II (PMA is Besar by law)",
        auto_fix=fix,
    )]


def r_moratorium(rec: dict) -> list[Finding]:
    """R-MORAT (transitive): lowest risk in {Rendah, Menengah Rendah} ⟹ blocked
    by the island-wide Bali moratorium (B.27.000/642), for nationally-open codes.
    Report-only (the moratorium read is per-address-sensitive at the margin) —
    no auto_fix, this needs the editorial/regulatory reviewer to confirm scope.
    """
    if _is_national_closed(rec) or not _scales(rec):
        return []
    tiers = _risk_tiers(rec)
    # the Besar scale's own tier governs the PMA path; approximate by "any scale
    # whose tier is moratorium-blocked AND no higher tier present is messy" — so
    # we only FLAG, never fix, when the lowest tier is in the blocked set.
    if tiers and tiers <= MORATORIUM_BLOCKED_RISK and not _l4(rec).get("blocked"):
        return [Finding(
            code=_code(rec), rule_id="R-MORAT", severity=MED, field="l4_bali.blocked",
            evidence=f"all scale risk tiers {sorted(tiers)} ⊆ moratorium-blocked, "
                     f"but l4.blocked={_l4(rec).get('blocked')}",
            source="Gubernur letter B.27.000/642/PM/DPMPTSP (2026-05-13)",
            note="per-address sensitive → report-only",
        )]
    return []


# R-RISK-LIC was REMOVED after empirical A/B (2026-06-30): only 1% (160/9266) of
# scale-rows populate `perizinan` at all — it is empty BY DESIGN in this dataset,
# with the license type derived from kategori_risiko downstream
# (resolveLicenseType in kbli-derive.ts). So "high-risk + empty perizinan" is the
# norm, not a defect; firing on it produced 5408 false findings that drowned the
# 66 real ones (superscar #3 over-match). The license is never client-misleading
# because the renderer derives it from the tier. No rule replaces it.


def r_flag(rec: dict) -> list[Finding]:
    """R-FLAG: the _l4_needs_review marker and l4_bali.needs_review must agree.
    Forced fix: realign the boolean flag to the presence of the marker.
    """
    marker = rec.get("_l4_needs_review") is not None
    flag = bool(_l4(rec).get("needs_review"))
    if marker != flag:
        return [Finding(
            code=_code(rec), rule_id="R-FLAG", severity=LOW, field="l4_bali.needs_review",
            evidence=f"_l4_needs_review present={marker} but l4.needs_review={flag}",
            source="internal flag-consistency contract",
            auto_fix=("l4_bali.needs_review", marker),
        )]
    return []


def r_prov(rec: dict) -> list[Finding]:
    """R-PROV: every derived layer must name its provenance source.
    A blocked/closed verdict with no reason, or a missing layer source, breaks
    the transitive chain (you can't verify a claim with no citation). Report-only.
    """
    out: list[Finding] = []
    l4 = _l4(rec)
    if l4 and not (l4.get("reason") or "").strip():
        out.append(Finding(
            code=_code(rec), rule_id="R-PROV", severity=LOW, field="l4_bali.reason",
            evidence="l4_bali present but reason empty (unverifiable verdict)",
            source="provenance-chain contract",
        ))
    return out


def r_pma_fingerprint(rec: dict) -> list[Finding]:
    """R-PMA-FP: a TERTUTUP code with max_asing != 0, or TERBUKA with max_asing==0,
    is self-contradictory in the FROZEN layer. ALWAYS report-only (never touch pma_*).
    """
    st, mx = rec.get("pma_status"), rec.get("pma_max_asing")
    if st == "TERTUTUP" and mx not in (0, None) and rec.get("pma_cap_special") is not True:
        return [Finding(
            code=_code(rec), rule_id="R-PMA-FP", severity=HIGH, field="pma_max_asing",
            evidence=f"pma_status=TERTUTUP but max_asing={mx} (≠0)",
            source="frozen-fingerprint internal consistency",
            note="REPORT-ONLY — pma_* never auto-patched",
        )]
    if st == "TERBUKA" and mx == 0:
        return [Finding(
            code=_code(rec), rule_id="R-PMA-FP", severity=HIGH, field="pma_max_asing",
            evidence="pma_status=TERBUKA but max_asing=0 (self-contradictory)",
            source="frozen-fingerprint internal consistency",
            note="REPORT-ONLY — pma_* never auto-patched",
        )]
    return []


# Editorial text fields that LLM Layer 2 must scrutinize when they read as a
# foreign-ownership go-ahead on a code the structural layer says is blocked.
# Layer 0 only FLAGS the candidate; the LLM refuter decides + rewrites.
import re  # noqa: E402

_PMA_GO_AHEAD = re.compile(r"\b(PT PMA|100% foreign|foreign-owned|open to foreign)\b", re.I)


def r_editorial_candidate(rec: dict) -> list[Finding]:
    """R-EDIT-CAND: editorial text promises PMA on a blocked code → hand to LLM.
    Not a fix — a routing signal. severity INFO; Layer 2 owns the verdict.
    """
    if not _l4(rec).get("blocked"):
        return []
    intel = rec.get("intel_2026") or {}
    out: list[Finding] = []
    for fld in ("baliContext", "zantaraOpener", "whatYouNeed", "whatItMeans"):
        txt = intel.get(fld) or ""
        if _PMA_GO_AHEAD.search(txt):
            out.append(Finding(
                code=_code(rec), rule_id="R-EDIT-CAND", severity=INFO,
                field=f"intel_2026.{fld}",
                evidence=f"text matches PMA-go-ahead on blocked code: '{txt[:80]}'",
                source="routing → LLM Layer 2 (propose≠grade + refuter)",
            ))
    return out


RULES: list[Callable[[dict], list[Finding]]] = [
    r_nat_dom,
    r_besar,
    r_moratorium,
    r_flag,
    r_prov,
    r_pma_fingerprint,
    r_editorial_candidate,
]


def run_all(rec: dict) -> list[Finding]:
    out: list[Finding] = []
    for rule in RULES:
        try:
            out.extend(rule(rec))
        except Exception as e:  # a buggy rule must not sink the sweep
            out.append(Finding(
                code=_code(rec), rule_id="R-ERR", severity=INFO, field="(rule)",
                evidence=f"rule {rule.__name__} raised: {e}", source="self-check",
            ))
    return out
