"""Drive the `nlm` CLI: add source, sync (explicit — F2), run prompt-master.

F2: never trust `nlm source stale`. Always sync the specific source-id of a Doc
we just refreshed.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

from scripts.wa_corpus.config import NLM_PROFILE
from scripts.wa_corpus.prompt_master import PROMPT_MASTER


@dataclass(frozen=True)
class RecapResult:
    answer: str
    cited_texts: list[str]

    @property
    def has_citations(self) -> bool:
        return len(self.cited_texts) > 0


def parse_query_result(raw: str) -> RecapResult:
    data = json.loads(raw)
    value = data.get("value", data)
    answer = value.get("answer", "")
    refs = value.get("references", []) or []
    cited = [r.get("cited_text", "") for r in refs if r.get("cited_text")]
    return RecapResult(answer=answer, cited_texts=cited)


def _nlm(args: list[str], timeout: float = 300.0) -> str:
    proc = subprocess.run(
        ["nlm", *args, "-p", NLM_PROFILE],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"nlm {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout


class QueryRunner:
    def ensure_source(self, nb_id: str, file_id: str, title: str) -> str:
        """Add the Drive Doc as a source; return its source_id.

        Note: caller is responsible for sharing the Doc with the nlm account
        first (renderer does this on create — F1)."""
        out = _nlm(
            ["source", "add", nb_id, "--drive", file_id,
             "--type", "doc", "--title", title, "--wait"]
        )
        # nlm prints 'Source ID: <uuid>'
        for line in out.splitlines():
            if "Source ID:" in line:
                return line.split("Source ID:", 1)[1].strip()
        raise RuntimeError(f"could not parse source id from nlm output:\n{out}")

    def sync_source(self, nb_id: str, source_id: str) -> None:
        _nlm(["source", "sync", nb_id, "--source-ids", source_id, "-y"])

    def run_prompt_master(self, nb_id: str, source_id: str) -> RecapResult:
        out = _nlm(
            ["notebook", "query", nb_id, PROMPT_MASTER,
             "--source-ids", source_id, "--json", "-t", "150"]
        )
        return parse_query_result(out)
