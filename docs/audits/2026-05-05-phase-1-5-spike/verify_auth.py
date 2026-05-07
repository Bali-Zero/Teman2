#!/usr/bin/env python3
"""Phase 1.5 spike — verify notebooklm-py auth + introspect API."""
import asyncio
import json
import sys
import time
from pathlib import Path

import notebooklm

AUTH_PATH = "/tmp/nlm-py-spike/storage_state.json"
NB_META_ID = "6164fbb6-e079-4d2a-a1cc-c38ea5a086b7"


async def main() -> int:
    t0 = time.time()
    async with await notebooklm.NotebookLMClient.from_storage(AUTH_PATH) as client:
        print("--- listing notebooks (notebook_list equivalent) ---")
        try:
            nbs = await client.notebooks.list()
            print(f"AUTH_OK notebook_count={len(nbs)} elapsed_s={time.time()-t0:.2f}")
            for nb in nbs[:5]:
                print(f"  - {nb.id} | {nb.title!r} | sources={getattr(nb, 'sources_count', '?')}")
        except Exception as e:
            print(f"AUTH_FAIL list: {type(e).__name__}: {e}")
            return 3

        print()
        print(f"--- describing NB-META {NB_META_ID} ---")
        try:
            nb_meta = await client.notebooks.get(NB_META_ID)
            print(f"NB-META: {nb_meta.title!r} sources={getattr(nb_meta, 'sources_count', '?')}")
        except Exception as e:
            print(f"NB-META describe failed: {type(e).__name__}: {e}")

        print()
        print("--- listing sources of NB-META ---")
        try:
            srcs = await client.sources.list(NB_META_ID)
            print(f"NB-META source_count={len(srcs)}")
            for s in srcs[:3]:
                print(f"  - {s.id} | {s.title!r} | type={getattr(s, 'kind', '?')}")
        except Exception as e:
            print(f"NB-META source list failed: {type(e).__name__}: {e}")

    return 0


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
