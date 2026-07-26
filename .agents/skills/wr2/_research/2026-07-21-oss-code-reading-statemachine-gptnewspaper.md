# OSS editorial multi-agent / state-machine survey — real code, real paths

All repos below were physically cloned/fetched in this session to
`/private/tmp/claude-501/-Users-balizero-nuzantara/1ec39280-48a4-48d9-9aeb-8d7ec9e668f2/scratchpad/oss/`
and read with `Read`/`grep` in this turn. Nothing here is recalled from training data.

## 1. Verification table

| Repo                                                                          | Verdict                                                          | What was actually read                                                                                                                                                                                                                                                                                                                                                                                                | Commit / SHA                                            | License                                                                                                                                                            |
| ----------------------------------------------------------------------------- | ---------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `assafelovic/gpt-newspaper`                                                   | ✅ VERIFIED                                                      | `backend/langgraph_agent.py`, `backend/agents/{search,curator,writer,critique,designer,editor,publisher}.py`, `backend/agents/__init__.py`, `backend/server.py`, `app.py`, `requirements.txt`, `README.md`, `LICENCE` — full repo, 22 files                                                                                                                                                                           | `b86aff2d2c208c6abc44a51f443948bfae2d08cc` (2024-02-24) | MIT (Copyright Rotem Weiss)                                                                                                                                        |
| `crewAIInc/crewAI-examples` — `crews/instagram_post/`                         | ✅ VERIFIED                                                      | `agents.py`, `tasks.py`, `main.py`, `README.md`                                                                                                                                                                                                                                                                                                                                                                       | `da94a91e691e1cf5b3151416bb15b5b62729bea8` (2026-04-20) | repo has no separate per-crew LICENSE file checked; parent org is Apache-2.0 upstream (not re-verified at file level — flag as unconfirmed at sub-dir granularity) |
| `crewAIInc/crewAI-examples` — `flows/write_a_book_with_flows/`                | ✅ VERIFIED                                                      | `src/.../main.py` (BookFlow), `crews/write_book_chapter_crew/config/agents.yaml`, `crews/write_book_chapter_crew/write_book_chapter_crew.py`                                                                                                                                                                                                                                                                          | same commit as above                                    | same as above                                                                                                                                                      |
| `crewAIInc/crewAI-examples` — `flows/content_creator_flow/`                   | ❌ CANNOT VERIFY                                                 | Directory exists in the tree as a `160000` gitlink (`git ls-tree` confirms mode `160000 commit 1c87aeef9b...`) but there is **no `.gitmodules`** in the repo and the working directory is empty after clone — it is an orphaned/broken submodule reference, not fetchable content. Did not fabricate contents.                                                                                                        |                                                         |                                                                                                                                                                    |
| `langchain-ai/langgraph` `examples/multi_agent/`                              | ❌ NOT PURSUED (not "cannot verify" — deliberately out of scope) | Confirmed via `gh api` listing that only `hierarchical_agent_teams.ipynb` and `multi-agent-collaboration.ipynb` exist there — both are the well-known "Researcher + Chart-Generator" pattern, not editorial/content production. Listed but not deep-read since it doesn't match the editorial-production ask and a real hit (CrewAI) was already found — reported here for transparency rather than silently omitted. |                                                         |                                                                                                                                                                    |
| `ghana7989/linkedin-carousel-generator`                                       | ✅ VERIFIED (but not load-bearing)                               | Full file tree read (`git ls-tree`) — it's a React/NestJS SaaS editor (manual drag-and-drop carousel builder), no AI slide-structure decision logic to extract. Mentioned for completeness, not cited further.                                                                                                                                                                                                        | `31d8ec481aad0ca2fcbeb4d1d9055e5e92a64685`              | not read                                                                                                                                                           |
| `Maazsiddiqui01/linkedin-carousel-generator` ("AntiGravity Slides Generator") | ✅ VERIFIED                                                      | `schemas/carousel.schema.json`, `scripts/build_carousel.js`, `scripts/run_overseer_checks.js`, `README.md`, `LICENSE`                                                                                                                                                                                                                                                                                                 | `f5963e9986b68d7d00f1f44bf57996a5b4fe6442` (2026-02-23) | MIT (Copyright Maaz Siddiqui)                                                                                                                                      |

Yesterday's sibling pass named repos that turned out not to exist — this pass replaces that with only repos that were physically fetched. Two secondary candidates that came up in search (`santmun/...`, `TaliNata/...`, `Lindadao92/...`) were **not** cloned/read and are therefore **not cited** anywhere below — they are absent from this report by design, not silently assumed real.

---

## 2. gpt-newspaper mechanism deep-dive

### 2a. The graph wiring — `backend/langgraph_agent.py` (full file, 59 lines)

```python
# backend/langgraph_agent.py:1-58
import os
import time
from concurrent.futures import ThreadPoolExecutor
from langgraph.graph import Graph

from .agents import SearchAgent, CuratorAgent, WriterAgent, DesignerAgent, EditorAgent, PublisherAgent, CritiqueAgent


class MasterAgent:
    def __init__(self):
        self.output_dir = f"outputs/run_{int(time.time())}"
        os.makedirs(self.output_dir, exist_ok=True)

    def run(self, queries: list, layout: str):
        # Initialize agents
        search_agent = SearchAgent()
        curator_agent = CuratorAgent()
        writer_agent = WriterAgent()
        critique_agent = CritiqueAgent()
        designer_agent = DesignerAgent(self.output_dir)
        editor_agent = EditorAgent(layout)
        publisher_agent = PublisherAgent(self.output_dir)

        # Define a Langchain graph
        workflow = Graph()

        # Add nodes for each agent
        workflow.add_node("search", search_agent.run)
        workflow.add_node("curate", curator_agent.run)
        workflow.add_node("write", writer_agent.run)
        workflow.add_node("critique", critique_agent.run)
        workflow.add_node("design", designer_agent.run)

        # Set up edges
        workflow.add_edge('search', 'curate')
        workflow.add_edge('curate', 'write')
        workflow.add_edge('write', 'critique')
        workflow.add_conditional_edges(start_key='critique',
                                       condition=lambda x: "accept" if x['critique'] is None else "revise",
                                       conditional_edge_mapping={"accept": "design", "revise": "write"})

        # set up start and end nodes
        workflow.set_entry_point("search")
        workflow.set_finish_point("design")

        # compile the graph
        chain = workflow.compile()

        # Execute the graph for each query in parallel
        with ThreadPoolExecutor() as executor:
            parallel_results = list(executor.map(lambda q: chain.invoke({"query": q}), queries))

        # Compile the final newspaper
        newspaper_html = editor_agent.run(parallel_results)
        newspaper_path = publisher_agent.run(newspaper_html)

        return newspaper_path
```

Key facts, verbatim from the code:

- **6 nodes, 4 unconditional edges, 1 conditional edge.** `Editor` and `Publisher` are deliberately kept **outside** the per-article graph — they run once, after `ThreadPoolExecutor` fans the whole per-query graph out in parallel (one compiled `chain` invoked once per topic in `queries`). The state-machine is per-article; the newspaper assembly is a plain post-loop step, not a graph node.
- **The state object is the article `dict` itself** — there is no separate `State` TypedDict/Pydantic model. `chain.invoke({"query": q})` seeds the state with a single key, and every node function receives and returns the _same dict_, mutating it via `.update()`. LangGraph's `Graph` (not the newer `StateGraph`) just threads this dict node-to-node.
- **The loop is a 2-way conditional edge keyed on a single field's truthiness**: `condition=lambda x: "accept" if x['critique'] is None else "revise"`. No max-retry counter, no loop-breaker — in this codebase the critic is trusted to eventually emit `None`.

### 2b. The shared state — what actually flows through the dict

Reconstructing the schema from every `.update()` / key-read across the 5 node files (there is no explicit schema file — this is itself a transferable lesson, see §3):

| Key                                      | Written by                                                                              | Read by                                                                                                               |
| ---------------------------------------- | --------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `query`                                  | seed (`chain.invoke({"query": q})`)                                                     | curator, writer, designer (`article["query"]` in `curator.py:41`, `writer.py:97`, `designer.py:33`)                   |
| `sources`                                | `search.py:22` (`article["sources"] = res[0]`)                                          | `curator.py:41` (filters in place), `writer.py:97`                                                                    |
| `image`                                  | `search.py:23`                                                                          | `designer.py:21`                                                                                                      |
| `title`, `date`, `paragraphs`, `summary` | `writer.py:63` (`json.loads(response)`, merged via `article.update(...)`)               | `designer.py:19-22`, `editor.py:47-49`                                                                                |
| `critique`                               | `critique.py:29/33` (`{'critique': None}` or `{'critique': response, 'message': None}`) | the conditional edge in `langgraph_agent.py:40`, and `writer.py:93` (`article.get("critique")`)                       |
| `message`                                | `writer.py:90` (`self.revise()` return, `response['message']`)                          | read back by critique's next prompt (`critique.py:20-21`, textually referencing "if you noticed the field 'message'") |
| `html`, `path`                           | `designer.py:28,38`                                                                     | `editor.py` (via the parallel list of article dicts)                                                                  |

This is the crux of the pattern: **the state IS a growing dict with no fixed contract** — every node is free to read any key any prior node wrote, and the "schema" is only discoverable by grepping every node file. There is zero runtime validation that a key exists before it's read (e.g. `writer.py:97` does `article["sources"]` — a `KeyError` if curator failed to set it — no try/except).

### 2c. One agent node in full — `backend/agents/writer.py`

```python
# backend/agents/writer.py:92-98
def run(self, article: dict):
    critique = article.get("critique")
    if critique is not None:
        article.update(self.revise(article))
    else:
        article.update(self.writer(article["query"], article["sources"]))
    return article
```

This is the entire "role isolation" mechanism: `WriterAgent.run()` is the ONLY function LangGraph calls for the `"write"` node. Internally it branches on whether `critique` is present in the state — first pass writes from scratch (`writer()`, `writer.py:39-63`, forcing a JSON contract via `response_format: json_object` and a hardcoded `sample_json` template embedded in the prompt string), subsequent passes call `revise()` (`writer.py:65-90`) which is a **different prompt with a different expected-JSON shape** (`sample_revise_json`, only `paragraphs` + `message`, no `title`/`date`/`summary` — meaning revision passes silently keep the ORIGINAL title/date/summary since `.update()` only overwrites returned keys). Role isolation = one class, one `run(article) -> article` contract, all decision logic (write-vs-revise) lives inside that one node — the graph itself carries zero business logic, only wiring.

### 2d. The critic→writer feedback edge

```python
# backend/agents/critique.py:9-37 (full file)
def critique(self, article: dict):
    prompt = [{
        "role": "system",
        "content": "You are a newspaper writing critique. Your sole purpose is to provide short feedback on a written "
                   "article so the writer will know what to fix.\n "
    }, {
        "role": "user",
        "content": f"Today's date is {datetime.now().strftime('%d/%m/%Y')}\n."
                   f"{str(article)}\n"
                   f"Your task is to provide a really short feedback on the article only if necessary.\n"
                   f"if you think the article is good, please return None.\n"
                   f"if you noticed the field 'message' in the article, it means the writer has revised the article"
                    f"based on your previous critique. you can provide feedback on the revised article or just "
                   f"return None if you think the article is good.\n"
                    f"Please return a string of your critique or None.\n"
    }]
    lc_messages = convert_openai_messages(prompt)
    response = ChatOpenAI(model='gpt-4', max_retries=1).invoke(lc_messages).content
    if response == 'None':
        return {'critique': None}
    else:
        print(f"For article: {article['title']}")
        print(f"Feedback: {response}\n")
        return {'critique': response, 'message': None}

def run(self, article: dict):
    article.update(self.critique(article))
    return article
```

Combined with the conditional edge in `langgraph_agent.py:39-41`:

```python
workflow.add_conditional_edges(start_key='critique',
                               condition=lambda x: "accept" if x['critique'] is None else "revise",
                               conditional_edge_mapping={"accept": "design", "revise": "write"})
```

The gate is: **critic returns a literal Python `None`/string `'None'` (string comparison against the LLM's raw text output, `critique.py:28`) → conditional edge reads `x['critique'] is None` → routes to `"design"` (exit the loop) or `"write"` (loop back)**. Notable fragility read directly in the code, not inferred: the gate is a brittle string-equality check on raw LLM output (`if response == 'None':` — any deviation like `"None."` or `"None, looks good"` would fail to close the loop), and there is **no loop-count cap** — an adversarial or confused critic could in principle loop forever (bounded only by `max_retries=1` on the _ChatOpenAI call itself_, not on the graph traversal).

---

## 3. The transferable pattern, stripped of framework

What LangGraph is actually buying gpt-newspaper, concretely, from the code read above:

1. **Edge wiring + traversal loop** (`workflow.add_edge`, `add_conditional_edges`, `.compile()`, `chain.invoke`) — replaces what would otherwise be a hand-written `while` loop.
2. **Nothing else.** There is no `StateGraph` typed schema in this codebase (it uses the older untyped `Graph`), no checkpointing, no persistence, no human-in-the-loop primitives, no streaming, no automatic retries, no parallel-node fan-out inside the graph (the parallelism is a bare `ThreadPoolExecutor.map` OUTSIDE the graph, `langgraph_agent.py:51-52`). Every node is a plain Python class with a `run(article: dict) -> dict` method — could be a bare function.

**Minimal contract, framework-free equivalent (would cost ~15 lines in plain Python):**

```python
def run_article_pipeline(query: str) -> dict:
    article = {"query": query}
    article.update(search(article))
    article.update(curate(article))
    while True:
        article.update(write(article))
        article.update(critique(article))
        if article["critique"] is None:
            break
    article.update(design(article))
    return article
```

This is _exactly_ what the compiled LangGraph chain does at runtime for this specific graph shape (linear + one back-edge) — a `while`-loop with an exit condition. The framework earns its keep only when the shape gets more branchy (multiple conditional exits, subgraphs, need for checkpointed resume across process restarts, or you want a visual graph / LangSmith trace of the state transitions for free). For a graph this shape (5 nodes, 1 loop-back, no branching, no checkpoint requirement), a `while` loop **costs less and is strictly more debuggable** (no need to understand `Graph()` vs `StateGraph()` semantics, no dependency on `langchain.adapters.openai.convert_openai_messages` which is itself a `langchain` compatibility shim visible in every node file's imports) — this is the actual answer to "could it be done without a framework": **yes, trivially, for this shape**, and the repo's own code proves it by putting ZERO business logic in the graph layer — 100% of the interesting logic (write-vs-revise branch, critique done-check, source curation) lives in plain-Python `run()` methods that don't touch LangGraph at all. LangGraph here is exclusively wiring glue around code that would work identically called directly.

The CrewAI examples independently confirm the same lesson from the opposite direction: `write_a_book_with_flows/src/.../main.py:50-89` uses `@listen(generate_book_outline)` + `asyncio.gather(*tasks)` to fan out chapter-writing — i.e. even CrewAI's own "Flow" abstraction, when it needs real fan-out concurrency, drops to bare `asyncio.create_task`/`asyncio.gather` (`main.py:81,85`) rather than a framework primitive. The framework supplies decorators for wiring (`@start`, `@listen`) and a `Crew`/`Process.sequential` container for role-based agent teams (`write_book_chapter_crew.py:42-50`), but the actual parallel dispatch is plain asyncio underneath.

`Maazsiddiqui01/linkedin-carousel-generator` is the sharpest real-world data point for "no framework at all": it is **100% plain Node.js scripts + a JSON schema + a deterministic pipeline runner** (`scripts/build_carousel.js:75-99`, sequential `spawnSync` steps: chart-gen → image-gen → render → validate → **overseer** → performance-log, each step gating the next via `.success`), with the "critic" role (`scripts/run_overseer_checks.js`) implemented as **deterministic heuristics, not an LLM call** — Jaccard-similarity duplicate detection (`run_overseer_checks.js:41-52`), bullet-count/length thresholds (`:118-132`), workflow-chip sequence validation (`:265-286`), visual-coverage-ratio checks against a configurable target (`:221-237`). It proves a full editorial-critic gate can be built with zero LLM calls and zero framework when the failure modes are structurally checkable (duplication, missing CTA, out-of-sequence numbering, coverage ratio) — reserving LLM judgment only for what's genuinely subjective.

---

## 4. WR2 mapping

Grounded in the actual live WR2 code (verified this turn, not recalled):

- `/Users/balizero/nuzantara/scripts/wr2_draft_generator.py` — 2162 lines, plain Python, `asyncpg` for Postgres (`:45`, `:2069` `asyncpg.create_pool`), **one function `claude_compose_slides()` (`:1071-1097`) makes a single `complete_async(..., model="claude-opus-4-7", timeout_s=300)` call that returns the entire slide JSON** (`_extract_json(resp.text)`) — confirming the prompt's framing: "one monolithic Claude call for the whole carousel."
- No `import langgraph` / `import crewai` anywhere under `scripts/wr2*.py` (grep run this turn returned zero matches).
- Orchestration is `infra/launchagents/com.balizero.wr2.*.plist` (launchd) chaining separate cron-scheduled scripts (`wr2_draft_generator.py` → `wr2_canva_*` → `wr2_ig_publish.py`, etc.) — i.e. WR2's "graph" already exists, but it is expressed as **separate OS processes wired by launchd + a Postgres queue table**, not as in-process node objects.
- There IS a distinct critic role already: the `wr2-critic` subagent (per this session's system prompt, agent catalog) runs on rendered PNGs as a Step-5 gate in the interactive `wr2-design-architect` pipeline — a SEPARATE, non-cron pipeline from `wr2_draft_generator.py`. That interactive pipeline already has brief-interpreter → storyboarder → layout-composer → critic role-split, dispatched via the `Agent` tool, not a graph library.

**What maps 1:1 from gpt-newspaper's mechanism:**

| gpt-newspaper concept                                   | WR2 equivalent today                                                                                                                                                    |
| ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `article` dict threaded through nodes                   | Postgres row(s) in the WR2 queue table, threaded through pipeline stages (already superior: durable + inspectable vs. an in-memory dict)                                |
| `critique.py` conditional-edge loop (`accept`/`revise`) | Already exists as a _separate_ interactive gate (`wr2-critic` subagent), NOT wired into the cron `wr2_draft_generator.py` monolithic-call path — this is the actual gap |
| One node = one Python class with `run()`                | WR2 already does this at the _process_ level (one script per stage) — finer-grained than gpt-newspaper's in-process nodes                                               |
| `ThreadPoolExecutor` fan-out across topics              | WR2 queue table + launchd cron intervals already provides this (coarser-grained, cross-process)                                                                         |

**Should WR2 adopt a framework (LangGraph/CrewAI), or replicate the pattern in its existing plain-Python+DB idiom?**

Argued directly from the code read above, not in the abstract: **replicate the pattern, don't adopt a framework.**

1. **gpt-newspaper's own code proves the framework adds no business value for a loop-shaped graph** — every interesting behavior (write-vs-revise, critique-done-check) lives in plain-Python node methods; the graph layer is 4 lines of edge declarations. WR2's monolithic-call gap is structurally the same shape as gpt-newspaper's write→critique loop — closing it needs a `while`-with-exit-condition around `claude_compose_slides()`, which is a ~20-line change to `wr2_draft_generator.py`, not a new dependency.
2. **WR2 already has the harder infrastructure gpt-newspaper lacks**: durable state (Postgres row, survives process crash — gpt-newspaper's in-memory dict does NOT survive a crash mid-graph, since `Graph.compile()` gives no checkpointing in the version this repo pins, `requirements.txt:2` bare `langgraph`), and process-level isolation via launchd (crash of one stage doesn't kill the whole run, unlike gpt-newspaper's single Python process running the whole `ThreadPoolExecutor`). Introducing LangGraph would mean _re-deriving inside a single process_ durability WR2's launchd+Postgres design gets for free — a straight regression per CLAUDE.md's own `PYTHONPATH=. python -m backend.module` / async-first / Postgres invariants (§8-9), and per the repo's `W64/W34 asyncpg silent-death` scar family (cicatrix #2) — a framework that re-centralizes state in-process is exactly the shape that produces "esiste ≠ armato" (green but the underlying worker died) failures the org has been burned by repeatedly.
3. **The one thing worth lifting verbatim is the deterministic-overseer pattern from `Maazsiddiqui01`**, not a graph library: `run_overseer_checks.js` shows a **non-LLM, non-framework critic** — structural checks (duplicate-content Jaccard similarity, bullet-count ceilings, CTA-presence, visual-coverage ratio, chip-sequence validation) that catch a large class of defects for $0 and 0ms LLM latency, BEFORE the expensive LLM-judge (`wr2-critic`) is invoked. WR2 currently has zero deterministic pre-gate of this kind in `wr2_draft_generator.py` — bolting a cheap structural-checks function (repeated-phrase/duplicate-bullet detection, bullet-length ceilings, CTA/closer-presence, kicker-uniqueness — some of which, e.g. `_kicker_collision` at `wr2_draft_generator.py:668`, WR2 already half-has) directly ahead of the Opus call, or directly after it as a fast-fail before the (expensive, slow) `wr2-critic` vision pass, is a genuine, cheap, framework-free win extractable from this research.
4. **Net verdict**: adopt the _shape_ (state-with-role-isolation, critic-gated loop, deterministic-check-before-LLM-judge), reject the _framework_ — consistent with WR2's existing architecture (plain Python + launchd + Postgres, per CLAUDE.md §12/§WR2 corner) and with the org's own documented scar pattern against introducing new stateful abstractions into a system whose reliability model is built on process isolation + DB durability, not in-process graph state.

---

## Files/paths referenced in this report (all read this session)

- `/private/tmp/claude-501/.../scratchpad/oss/gpt-newspaper/backend/langgraph_agent.py`
- `/private/tmp/claude-501/.../scratchpad/oss/gpt-newspaper/backend/agents/{search,curator,writer,critique,designer,editor,publisher,__init__}.py`
- `/private/tmp/claude-501/.../scratchpad/oss/gpt-newspaper/backend/server.py`, `app.py`, `requirements.txt`, `README.md`, `LICENCE`
- `/private/tmp/claude-501/.../scratchpad/oss/crewAI-examples/crews/instagram_post/{agents,tasks,main}.py`, `README.md`
- `/private/tmp/claude-501/.../scratchpad/oss/crewAI-examples/flows/write_a_book_with_flows/src/write_a_book_with_flows/main.py`
- `/private/tmp/claude-501/.../scratchpad/oss/crewAI-examples/flows/write_a_book_with_flows/src/write_a_book_with_flows/crews/write_book_chapter_crew/{write_book_chapter_crew.py, config/agents.yaml}`
- `/private/tmp/claude-501/.../scratchpad/oss/lcg-maaz/{schemas/carousel.schema.json, scripts/build_carousel.js, scripts/run_overseer_checks.js, README.md, LICENSE}`
- `/Users/balizero/nuzantara/scripts/wr2_draft_generator.py` (lines 45, 1071-1097, 2069, 668)
- `/Users/balizero/nuzantara/infra/launchagents/com.balizero.wr2.*.plist`
