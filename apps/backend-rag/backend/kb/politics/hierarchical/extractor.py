"""
Rule-based claim extractor for Indonesian politics KB.

Extracts claim-level sentences from structured JSONL records by traversing
JSON fields and generating natural-language claims.

Design trade-off: We use structured field traversal instead of spaCy NLP
because:
1. The KB data is already structured JSONL with known schemas.
2. spaCy Indonesian model adds ~30MB dependency not currently in the project.
3. Field traversal is deterministic and testable — no model drift.
4. On Air (4GB RAM constraint), avoiding spaCy saves significant memory.

Each claim follows the pattern: {subject} {predicate} {object} [temporal_marker].
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ClaimExtractor:
    """Extract atomic claim sentences from structured politics records.

    Each claim is a self-contained sentence that can be independently
    embedded and searched. Claims preserve temporal markers and entity
    references for precise retrieval.
    """

    def extract_claims(self, record: dict[str, Any]) -> list[str]:
        """Extract claims from a record based on its type.

        Args:
            record: Parsed JSONL record with 'type' field.

        Returns:
            List of claim sentences (Indonesian).
        """
        record_type = record.get("type")

        if record_type == "person":
            return self._extract_person_claims(record)
        if record_type == "party":
            return self._extract_party_claims(record)
        if record_type == "election":
            return self._extract_election_claims(record)
        if record_type == "jurisdiction":
            return self._extract_jurisdiction_claims(record)

        logger.warning(f"Unknown record type: {record_type}")
        return []

    def _extract_person_claims(self, r: dict[str, Any]) -> list[str]:
        claims: list[str] = []
        name = r.get("name", "?")
        aliases = r.get("aliases", [])

        # Identity claim
        if aliases:
            claims.append(f"{name} dikenal juga sebagai {', '.join(aliases)}.")

        # Birth claim
        dob = r.get("dob")
        pob = r.get("pob")
        if dob and pob:
            claims.append(f"{name} lahir pada {dob} di {pob}.")
        elif dob:
            claims.append(f"{name} lahir pada {dob}.")

        # Party membership claims
        for p in r.get("party_memberships", []):
            party_id = p.get("party_id", "?")
            pfrom = p.get("from", "?")
            pto = p.get("to")
            if pto:
                claims.append(f"{name} menjadi anggota {party_id} dari {pfrom} sampai {pto}.")
            else:
                claims.append(f"{name} menjadi anggota {party_id} sejak {pfrom}.")

        # Office claims
        for o in r.get("offices", []):
            office = o.get("office", "?")
            jid = o.get("jurisdiction_id", "")
            ofrom = o.get("from", "?")
            oto = o.get("to")
            elected = o.get("elected", False)

            method = "terpilih sebagai" if elected else "menjabat sebagai"
            loc = f" di {jid}" if jid else ""

            if oto:
                claims.append(f"{name} {method} {office}{loc} dari {ofrom} sampai {oto}.")
            else:
                claims.append(f"{name} {method} {office}{loc} sejak {ofrom}.")

        # Legal case claims
        for case in r.get("cases", []):
            if isinstance(case, str):
                claims.append(f"{name} terlibat dalam kasus: {case}.")
            elif isinstance(case, dict):
                desc = case.get("description", str(case))
                claims.append(f"{name} terlibat dalam kasus: {desc}.")

        return claims

    def _extract_party_claims(self, r: dict[str, Any]) -> list[str]:
        claims: list[str] = []
        name = r.get("name", "?")
        abbrev = r.get("abbrev", "")

        # Identity claim
        if abbrev:
            claims.append(f"{name} disingkat {abbrev}.")

        # Founding claim
        founded = r.get("founded")
        if founded:
            claims.append(f"{name} didirikan pada {founded}.")

        # Dissolution claim
        dissolved = r.get("dissolved")
        if dissolved:
            claims.append(f"{name} dibubarkan pada {dissolved}.")

        # Ideology claims
        ideology = r.get("ideology", [])
        if ideology:
            claims.append(f"{name} menganut ideologi {', '.join(ideology)}.")

        # Leadership claims
        for ld in r.get("leaders", []):
            pid = ld.get("person_id", "?")
            lfrom = ld.get("from", "?")
            lto = ld.get("to")
            if lto:
                claims.append(f"{pid} memimpin {name} dari {lfrom} sampai {lto}.")
            else:
                claims.append(f"{pid} memimpin {name} sejak {lfrom}.")

        return claims

    def _extract_election_claims(self, r: dict[str, Any]) -> list[str]:
        claims: list[str] = []
        eid = r.get("id", "?")
        date = r.get("date", "?")
        scope = r.get("scope", "?")
        jid = r.get("jurisdiction_id", "?")

        # Election event claim
        claims.append(f"Pemilu {scope} diadakan pada {date} di {jid}.")

        # Turnout claim
        turnout = r.get("turnout_pct")
        if turnout:
            claims.append(f"Tingkat partisipasi pemilu {eid} adalah {turnout}%.")

        # Contest result claims
        for contest in r.get("contests", []):
            office = contest.get("office", "?")
            results = contest.get("results", [])

            # Find winner (highest pct)
            if results:
                winner = max(results, key=lambda x: x.get("pct", 0))
                winner_id = winner.get("candidate_id", "?")
                winner_pct = winner.get("pct", 0)
                winner_party = winner.get("party_id")
                party_str = f" dari {winner_party}" if winner_party else ""
                claims.append(
                    f"{winner_id}{party_str} memenangkan pemilu {office} {date} "
                    f"dengan {winner_pct}% suara."
                )

            # Individual result claims
            for res in results:
                cand = res.get("candidate_id", "?")
                pct = res.get("pct", 0)
                party = res.get("party_id")
                votes = res.get("votes")

                party_str = f" dari {party}" if party else " (independen)"
                vote_str = f" dengan {votes:,} suara" if votes else ""
                claims.append(
                    f"{cand}{party_str} memperoleh {pct}% suara{vote_str} "
                    f"dalam pemilu {office} {date}."
                )

        return claims

    def _extract_jurisdiction_claims(self, r: dict[str, Any]) -> list[str]:
        claims: list[str] = []
        name = r.get("name", "?")
        kind = r.get("kind", "?")
        parent_id = r.get("parent_id")
        valid_from = r.get("valid_from")
        codes = r.get("codes", {})

        # Type claim
        claims.append(f"{name} adalah sebuah {kind}.")

        # Parent claim
        if parent_id:
            claims.append(f"{name} berada di bawah {parent_id}.")

        # Establishment claim
        if valid_from:
            claims.append(f"{name} berdiri sejak {valid_from}.")

        # Code claims
        for code_type, code_val in codes.items():
            claims.append(f"Kode {code_type} untuk {name} adalah {code_val}.")

        return claims
