# Staged / Outline-First Content Generation — Real-Code Research Report

Method used: `git clone --depth 1` into
`/private/tmp/claude-501/-Users-balizero-nuzantara/1ec39280-48a4-48d9-9aeb-8d7ec9e668f2/scratchpad/oss/`
for both targets. Both clones succeeded (no WebFetch fallback needed). All code excerpts below were
read directly from the cloned working trees with the `Read` tool in this session — nothing is quoted
from memory or from a prior report.

## 1. Verification table

| Repo                         | Verified?            | Commit read                                             | License                                                  | Clone path                           |
| ---------------------------- | -------------------- | ------------------------------------------------------- | -------------------------------------------------------- | ------------------------------------ |
| `stanford-oval/storm`        | YES — read real code | `fb951af7744dab086e34962e9bc6fe878e145f8` (2025-09-30)  | MIT (Copyright 2024 Stanford Open Virtual Assistant Lab) | `.../scratchpad/oss/storm/`          |
| `assafelovic/gpt-researcher` | YES — read real code | `5d84d2f5553e70a2765a8ff3a0d2672d60437ce8` (2026-07-14) | Apache License 2.0                                       | `.../scratchpad/oss/gpt-researcher/` |

Files actually opened and read in this session (not summarized from docs, not paraphrased from a README):

**STORM**

- `knowledge_storm/storm_wiki/modules/outline_generation.py` (168 lines, read in full)
- `knowledge_storm/storm_wiki/modules/storm_dataclass.py` (505 lines, read in full)
- `knowledge_storm/interface.py` (609 lines, read in full)
- `knowledge_storm/storm_wiki/modules/article_generation.py` (177 lines, read in full)
- `knowledge_storm/storm_wiki/engine.py` (442 lines, read in full)
- `knowledge_storm/utils.py` (excerpt: `clean_up_outline` L457-505, `clean_up_section` L506-538, `parse_article_into_dict` L553-593)

**gpt-researcher**

- `multi_agents/agents/editor.py` (169 lines, read in full)
- `multi_agents/agents/writer.py` (147 lines, read in full)
- `multi_agents/agents/researcher.py` (58 lines, read in full)
- `gpt_researcher/skills/writer.py` (266 lines, read in full)
- `gpt_researcher/utils/validators.py` (excerpt: `Subtopic`/`Subtopics` classes L8-26)
- `gpt_researcher/utils/llm.py` (excerpt: `construct_subtopics` L155-185+)
- Directory listings of `gpt_researcher/` and `multi_agents/` confirmed via `find`, not assumed.

No repo was described without being fetched. Nothing below is invented.

---

## 2. STORM mechanism deep-dive

STORM's pipeline (`knowledge_storm/storm_wiki/engine.py`) is **four independently-invokable, disk-persisted
stages**: knowledge curation → outline generation → article generation → article polishing. Each stage
has its own `do_X: bool` flag in `STORMWikiRunner.run()`, and if a stage is skipped, its input is
**reloaded from a file on disk** rather than passed in memory — meaning outline generation and article
writing are not just logically separate functions, they're operationally decoupled processes that can
run in different invocations of the tool entirely.

### 2a. Outline generation

File: `knowledge_storm/storm_wiki/modules/outline_generation.py`

```python
# L11-72
class StormOutlineGenerationModule(OutlineGenerationModule):
    def __init__(self, outline_gen_lm: Union[dspy.dsp.LM, dspy.dsp.HFModel]):
        super().__init__()
        self.outline_gen_lm = outline_gen_lm
        self.write_outline = WriteOutline(engine=self.outline_gen_lm)

    def generate_outline(
        self,
        topic: str,
        information_table: StormInformationTable,
        old_outline: Optional[StormArticle] = None,
        callback_handler: BaseCallbackHandler = None,
        return_draft_outline=False,
    ) -> Union[StormArticle, Tuple[StormArticle, StormArticle]]:
        ...
        concatenated_dialogue_turns = sum(
            [conv for (_, conv) in information_table.conversations], []
        )
        result = self.write_outline(
            topic=topic,
            dlg_history=concatenated_dialogue_turns,
            callback_handler=callback_handler,
        )
        article_with_outline_only = StormArticle.from_outline_str(
            topic=topic, outline_str=result.outline
        )
        ...
        return article_with_outline_only
```

The outline is produced by a `dspy.Module` (`WriteOutline`, L75-125) that does a **two-pass LLM call**:
first a naive outline from the LLM's own parametric knowledge (`self.draft_page_outline`, using
`WritePageOutline` signature), then a refinement pass conditioned on the collected research dialogue
(`self.write_page_outline`, using `WritePageOutlineFromConv` signature, L153-167). The dspy `Signature`
docstring is literally the prompt contract handed to the model:

```python
# L128-138
class WritePageOutline(dspy.Signature):
    """Write an outline for a Wikipedia page.
    Here is the format of your writing:
    1. Use "#" Title" to indicate section title, "##" Title" to indicate subsection title, "###" Title" to indicate subsubsection title, and so on.
    2. Do not include other information.
    3. Do not include topic name itself in the outline.
    """
    topic = dspy.InputField(prefix="The topic you want to write: ", format=str)
    outline = dspy.OutputField(prefix="Write the Wikipedia page outline:\n", format=str)
```

So the outline is **plain markdown headers as a string** — the LLM output format is literally `#`/`##`/`###`.
There is no forced JSON schema at generation time.

### 2b. The outline data structure

The markdown string is immediately parsed into a real in-memory **tree**, not kept as text. This happens
in `knowledge_storm/storm_wiki/modules/storm_dataclass.py`, class `StormArticle` (subclass of `Article`
in `interface.py`), backed by `ArticleSectionNode`:

```python
# interface.py L136-159
class ArticleSectionNode:
    """
    The ArticleSectionNode is the dataclass for handling the section of the article.
    The content storage, section writing preferences are defined in this node.
    """
    def __init__(self, section_name: str, content=None):
        self.section_name = section_name
        self.content = content
        self.children = []
        self.preference = None

    def add_child(self, new_child_node, insert_to_front=False):
        if insert_to_front:
            self.children.insert(0, new_child_node)
        else:
            self.children.append(new_child_node)

    def remove_child(self, child):
        self.children.remove(child)
```

```python
# interface.py L162-165
class Article(ABC):
    def __init__(self, topic_name):
        self.root = ArticleSectionNode(topic_name)
```

The markdown → tree parser is `StormArticle.from_outline_str` (`storm_dataclass.py` L437-474). It's a
classic stack-based header-depth parser: it counts `#` characters per line to get `level`, pops the stack
until it finds the right parent depth, and appends:

```python
# storm_dataclass.py L437-474
@classmethod
def from_outline_str(cls, topic: str, outline_str: str):
    lines = []
    try:
        lines = outline_str.split("\n")
        lines = [line.strip() for line in lines if line.strip()]
    except:
        pass

    instance = cls(topic)
    if lines:
        ...
        node_stack = [(0, instance.root)]  # Stack to keep track of (level, node)

        for line in lines:
            level = line.count("#") - adjust_level
            section_name = line.replace("#", "").strip()

            if section_name == topic:
                continue

            new_node = ArticleSectionNode(section_name)

            while node_stack and level <= node_stack[-1][0]:
                node_stack.pop()

            node_stack[-1][1].add_child(new_node)
            node_stack.append((level, new_node))
    return instance
```

So: **outline representation = a real n-ary tree of `ArticleSectionNode` objects, each with
`section_name`, `content` (initially `None`), and `children`**, wrapped in a `StormArticle` whose `.root`
is the topic node. `content` stays empty until the writing stage fills it in — the tree IS the contract
between outline stage and writer stage, and `content=None` on every leaf is the explicit "not yet written"
state.

`get_outline_tree()` (`interface.py` L193-230, overridden identically in `storm_dataclass.py` L414-421)
exposes this same tree as a nested `Dict[str, Dict]` for external consumption (e.g. UI rendering) — proof
the representation is meant to be introspected structurally, not just re-serialized to text.

### 2c. How the outline constrains/feeds the writer stage

File: `knowledge_storm/storm_wiki/modules/article_generation.py`, class `StormArticleGenerationModule`.
The full driving method:

```python
# article_generation.py L53-133
def generate_article(
    self,
    topic: str,
    information_table: StormInformationTable,
    article_with_outline: StormArticle,
    callback_handler: BaseCallbackHandler = None,
) -> StormArticle:
    information_table.prepare_table_for_retrieval()

    if article_with_outline is None:
        article_with_outline = StormArticle(topic_name=topic)

    sections_to_write = article_with_outline.get_first_level_section_names()

    section_output_dict_collection = []
    if len(sections_to_write) == 0:
        ...
    else:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_thread_num
        ) as executor:
            future_to_sec_title = {}
            for section_title in sections_to_write:
                if section_title.lower().strip() == "introduction":
                    continue
                if section_title.lower().strip().startswith("conclusion") \
                        or section_title.lower().strip().startswith("summary"):
                    continue
                section_query = article_with_outline.get_outline_as_list(
                    root_section_name=section_title, add_hashtags=False
                )
                queries_with_hashtags = article_with_outline.get_outline_as_list(
                    root_section_name=section_title, add_hashtags=True
                )
                section_outline = "\n".join(queries_with_hashtags)
                future_to_sec_title[
                    executor.submit(
                        self.generate_section,
                        topic,
                        section_title,
                        information_table,
                        section_outline,
                        section_query,
                    )
                ] = section_title

            for future in as_completed(future_to_sec_title):
                section_output_dict_collection.append(future.result())

    article = copy.deepcopy(article_with_outline)
    for section_output_dict in section_output_dict_collection:
        article.update_section(
            parent_section_name=topic,
            current_section_content=section_output_dict["section_content"],
            current_section_info_list=section_output_dict["collected_info"],
        )
    article.post_processing()
    return article
```

This is the **exact answer to "how the outline is passed to and constrains the writing stage."** The
outline object (`article_with_outline`, a `StormArticle` tree) is walked to get `sections_to_write =
article_with_outline.get_first_level_section_names()` — i.e. the writer only ever sees the top-level
section names as its unit of work. For each top-level section, `get_outline_as_list(root_section_name=X)`
is called TWICE:

1. without hashtags → `section_query` — a flat list of that section's own subsection names, used purely
   as **retrieval queries** to pull the top-k relevant snippets for that section only
   (`information_table.retrieve_information`).
2. with hashtags → `section_outline` — the markdown-rendered slice of the outline tree **scoped to that
   section's subtree only** (its own sub-headers, re-indented), which is what's actually shown to the
   writer LLM as its structural brief.

So each writer call gets: (topic, its own scoped mini-outline, its own section name, its own
retrieved evidence) — it never sees the other sections' outline or content, and it cannot see or write
outside its assigned subtree.

### 2d. Section writing is genuinely parallel and independently scoped

`generate_section` (L33-51) is the per-section unit of work:

```python
# article_generation.py L33-51
def generate_section(
    self, topic, section_name, information_table, section_outline, section_query
):
    collected_info: List[Information] = []
    if information_table is not None:
        collected_info = information_table.retrieve_information(
            queries=section_query, search_top_k=self.retrieve_top_k
        )
    output = self.section_gen(
        topic=topic,
        outline=section_outline,
        section=section_name,
        collected_info=collected_info,
    )
    return {
        "section_name": section_name,
        "section_content": output.section,
        "collected_info": collected_info,
    }
```

This is dispatched into a real `concurrent.futures.ThreadPoolExecutor(max_workers=self.max_thread_num)`
(default `max_thread_num=10`, set in `STORMWikiRunnerArguments`, `engine.py` L162-168) — one thread per
top-level section, fully parallel, collected via `as_completed`. Each thread's LLM call is fully
independent: separate `dspy.Predict` invocation of `ConvToSection`/`WriteSection`
(`article_generation.py` L136-177), with its own `dspy.settings.context(lm=self.engine)`. No shared
mutable state is touched inside the loop — results are only merged back into the tree afterward, sequentially,
via `article.update_section(...)` (L126-131), which re-parses the returned markdown text into subsections
and grafts it onto the matching node of the (deep-copied) outline tree.

`WriteSection`'s dspy Signature (L162-177) is again the literal writer contract:

```python
# article_generation.py L162-177
class WriteSection(dspy.Signature):
    """Write a Wikipedia section based on the collected information.
    Here is the format of your writing:
        1. Use "#" Title" ... "##" Title" ... to indicate section/subsection title.
        2. Use [1], [2], ..., [n] in line ... You DO NOT need to include a References
           or Sources section to list the sources at the end.
    """
    info = dspy.InputField(prefix="The collected information:\n", format=str)
    topic = dspy.InputField(prefix="The topic of the page: ", format=str)
    section = dspy.InputField(prefix="The section you need to write: ", format=str)
    output = dspy.OutputField(
        prefix="Write the section with proper inline citations (Start your writing with # section title. Don't include the page title or try to write other sections):\n",
        format=str,
    )
```

### 2e. Stage decoupling is enforced at the orchestrator level, not just logically

`STORMWikiRunner.run()` (`engine.py` L341-441) treats each stage as independently resumable, persisting
and reloading via the filesystem:

```python
# engine.py L393-424 (abridged)
outline: StormArticle = None
if do_generate_outline:
    if information_table is None:
        information_table = self._load_information_table_from_local_fs(...)
    outline = self.run_outline_generation_module(
        information_table=information_table, callback_handler=callback_handler
    )

draft_article: StormArticle = None
if do_generate_article:
    if information_table is None:
        information_table = self._load_information_table_from_local_fs(...)
    if outline is None:
        outline = self._load_outline_from_local_fs(
            topic=topic,
            outline_local_path=os.path.join(self.article_output_dir, "storm_gen_outline.txt"),
        )
    draft_article = self.run_article_generation_module(
        outline=outline, information_table=information_table, callback_handler=callback_handler,
    )
```

And `run_outline_generation_module` (L237-254) dumps the outline to a plain-text file
(`storm_gen_outline.txt`) immediately after generation — this is the literal file the writer stage reloads
from disk if invoked as a separate process (`--do-generate-article` without `--do-generate-outline` on
the CLI). This is as decoupled as a planner→writer split gets: they don't even need to run in the same
process invocation.

---

## 3. gpt-researcher — plan/research/write separation

`gpt-researcher` ships two relevant systems in the same repo: (a) the base `gpt_researcher/` package,
which has a lightweight typed "subtopics" outline for its `DetailedReport` mode, and (b) a full
LangGraph-based multi-agent team in `multi_agents/`, which is the closer analog to STORM's outline→write
split (confirmed present via `find`, not assumed — `multi_agents/agents/{editor,researcher,reviewer,
reviser,writer,publisher}.py` all exist).

### 3a. The planner: `EditorAgent.plan_research`

File: `multi_agents/agents/editor.py`, L22-50.

```python
async def plan_research(self, research_state: Dict[str, any]) -> Dict[str, any]:
    initial_research = research_state.get("initial_research")
    task = research_state.get("task")
    include_human_feedback = task.get("include_human_feedback")
    human_feedback = research_state.get("human_feedback")
    max_sections = task.get("max_sections")

    prompt = self._create_planning_prompt(
        initial_research, include_human_feedback, human_feedback, max_sections)

    print_agent_output("Planning an outline layout based on initial research...", agent="EDITOR")
    plan = await call_model(
        prompt=prompt,
        model=task.get("model"),
        response_format="json",
    )

    return {
        "title": plan.get("title"),
        "date": plan.get("date"),
        "sections": plan.get("sections"),
    }
```

The planning prompt (`_format_planning_instructions`, L96-116) is explicit about the outline's shape and
about NOT writing prose yet:

```python
return f"""...
           \nYour task is to generate an outline of sections headers for the research project
           based on the research summary report above.
           You must generate a maximum of {max_sections} section headers.
           You must focus ONLY on related research topics for subheaders and do NOT include
           introduction, conclusion and references.
           You must return nothing but a JSON with the fields 'title' (str) and
           'sections' (maximum {max_sections} section headers) with the following structure:
           '{{title: string research title, date: today's date,
           sections: ['section header 1', 'section header 2', 'section header 3' ...]}}'."""
```

**This is a flat outline** — just a JSON list of section-title strings — unlike STORM's nested `#`/`##`/`###`
tree. It's the minimum viable outline schema: title + ordered list of slot-names. There's an initial
research pass (`run_initial_research`, in `researcher.py` L34-44) that gathers a summary BEFORE planning
even happens — the planner's prompt is conditioned on that summary (`initial_research`), analogous to
STORM's conversation-history-informed outline refinement.

### 3b. The outline data structure (typed, for the simpler single-process path)

For the plain `GPTResearcher` (non-multi-agent) `DetailedReport` path, the "outline" unit is a Pydantic
model, `gpt_researcher/utils/validators.py` L8-26:

```python
class Subtopic(BaseModel):
    """Model representing a single research subtopic."""
    task: str = Field(description="Task name", min_length=1)

class Subtopics(BaseModel):
    """Model representing a collection of research subtopics."""
    subtopics: List[Subtopic] = []
```

Constructed via `construct_subtopics()` in `gpt_researcher/utils/llm.py` (L155-185+), which uses
LangChain's `PydanticOutputParser(pydantic_object=Subtopics)` to force the LLM's output into that schema
— a stricter contract than STORM's raw markdown-string outline, at the cost of a flatter (non-nested)
structure. This confirms gpt-researcher's design intentionally trades hierarchy depth for schema
strictness where it can.

### 3c. Fan-out: each planned section becomes an independent research+write sub-agent, run in parallel

File: `multi_agents/agents/editor.py`, `run_parallel_research` (L52-77) + `_create_workflow` (L126-144).

```python
async def run_parallel_research(self, research_state: Dict[str, any]) -> Dict[str, List[str]]:
    agents = self._initialize_agents()
    workflow = self._create_workflow()
    chain = workflow.compile()

    queries = research_state.get("sections")
    title = research_state.get("title")

    self._log_parallel_research(queries)

    final_drafts = [
        chain.ainvoke(self._create_task_input(
            research_state, query, title), config={"tags": ["gpt-researcher"]})
        for query in queries
    ]
    research_results = [
        result["draft"] for result in await asyncio.gather(*final_drafts)
    ]
    return {"research_data": research_results}
```

```python
def _create_workflow(self) -> StateGraph:
    agents = self._initialize_agents()
    workflow = StateGraph(DraftState)

    workflow.add_node("researcher", agents["research"].run_depth_research)
    workflow.add_node("reviewer", agents["reviewer"].run)
    workflow.add_node("reviser", agents["reviser"].run)

    workflow.set_entry_point("researcher")
    workflow.add_edge("researcher", "reviewer")
    workflow.add_edge("reviser", "reviewer")
    workflow.add_conditional_edges(
        "reviewer",
        self._route_draft_review,
        {"accept": END, "revise": "reviser"},
    )
    return workflow
```

Each `query` in `research_state.get("sections")` (i.e. every outline slot the planner emitted) gets its
**own LangGraph sub-workflow instance**, launched concurrently via a list comprehension of
`chain.ainvoke(...)` fed into `asyncio.gather(*final_drafts)` — the async analog of STORM's
`ThreadPoolExecutor`. Crucially, the sub-workflow is not just "write prose for this slot" — it's a full
**researcher → reviewer → reviser loop per section** (a self-critique cycle absent from STORM's
single-pass writer), with `reviewer` conditionally routing back to `reviser` until accepted.

Each section's researcher (`multi_agents/agents/researcher.py`, `run_depth_research`, L46-58) spins up a
**complete standalone `GPTResearcher` instance** scoped to that one section as its own sub-topic, doing
its own web search AND its own writing:

```python
async def run_depth_research(self, draft_state: dict):
    task = draft_state.get("task")
    topic = draft_state.get("topic")
    parent_query = task.get("query")
    source = task.get("source", "web")
    verbose = task.get("verbose")
    ...
    research_draft = await self.run_subtopic_research(parent_query=parent_query, subtopic=topic,
                                                      verbose=verbose, source=source, headers=self.headers)
    return {"draft": research_draft}
```

```python
async def run_subtopic_research(self, parent_query: str, subtopic: str, verbose: bool = True, source="web", headers=None):
    try:
        report = await self.research(parent_query=parent_query, query=subtopic,
                                     research_report="subtopic_report", verbose=verbose, source=source, tone=self.tone, headers=None)
    except Exception as e:
        print(f"{Fore.RED}Error in researching topic {subtopic}: {e}{Style.RESET_ALL}")
        report = None
    return {subtopic: report}
```

```python
async def research(self, query: str, research_report: str = "research_report",
                   parent_query: str = "", verbose=True, source="web", tone=None, headers=None):
    researcher = GPTResearcher(query=query, report_type=research_report, parent_query=parent_query,
                               verbose=verbose, report_source=source, tone=tone, websocket=self.websocket, headers=self.headers)
    await researcher.conduct_research()
    report = await researcher.write_report()
    return report
```

Note `report_type=research_report="subtopic_report"` and `parent_query=parent_query` — this
`report_type` value is read back inside `ReportGenerator.write_report`
(`gpt_researcher/skills/writer.py` L114-120): when `report_type == "subtopic_report"`, the prompt is
given `main_topic=self.researcher.parent_query` plus `existing_headers` (so it can avoid duplicating
headers already written by sibling sections) — i.e. **the section-level writer is aware of its slot's
scope AND of the overall topic**, but not of sibling sections' actual prose, only their header list. This
is a slightly looser isolation boundary than STORM's (which passes zero cross-section awareness).

### 3d. The top-level "writer" only glues, never re-writes bodies

File: `multi_agents/agents/writer.py`. Once every section sub-workflow's draft lands in
`research_state["research_data"]` (a list, one entry per section, already fully written), the top-level
`WriterAgent.write_sections` (L32-71) does NOT rewrite section bodies. It's given the **already-written**
`research_data` as raw string context and asked only for glue content — table of contents, introduction,
conclusion, sources list:

```python
sample_json = """
{
  "table_of_contents": A table of contents in markdown syntax (using '-') based on the research headers and subheaders,
  "introduction": An indepth introduction to the topic in markdown syntax and hyperlink references to relevant sources,
  "conclusion": A conclusion to the entire research based on all research data in markdown syntax and hyperlink references to relevant sources,
  "sources": A list with strings of all used source links in the entire research data in markdown syntax and apa citation format. ...
}
"""
...
async def write_sections(self, research_state: dict):
    query = research_state.get("title")
    data = research_state.get("research_data")
    ...
    prompt = [
        {"role": "system", "content": "You are a research writer. ..."},
        {"role": "user", "content": f"...Research data: {str(data)}\n..."
            f"Your task is to write an in depth, well written and detailed "
            f"introduction and conclusion to the research report based on the provided research data. "
            f"Do not include headers in the results.\n..."},
    ]
    response = await call_model(prompt, task.get("model"), response_format="json")
    return response
```

`WriterAgent.run` (L98-146) then merges `{**research_layout_content, "headers": headers}` — i.e. the
final artifact is: (planner's title) + (glue JSON: TOC/intro/conclusion/sources) + (the list of
already-independently-written section bodies, assembled downstream by the publisher, not shown here but
confirmed present as `multi_agents/agents/publisher.py`). The separation of concerns is total: **planner
decides section names, N parallel section-sub-agents research+write+revise their own body independently,
and a final pass writes only the connective tissue (title/TOC/intro/conclusion) around bodies it never
touches.**

---

## 4. The transferable pattern, stripped of STORM/gpt-researcher specifics

Distilling both systems down to what's actually load-bearing (present in both, independently arrived at):

1. **A cheap, structural first pass produces a _slot list_, not prose.** STORM: markdown headers.
   gpt-researcher: a JSON array of section-title strings (or a strict Pydantic list for the simpler path).
   The slot list is generated from a _summary_ of the gathered material (STORM: perspective-guided
   dialogue history; gpt-researcher: `initial_research`), not from raw unprocessed source dumps — the
   planner sees a condensed signal, not everything the writer will later see.

2. **The slot list is parsed into an addressable structure before writing starts** — STORM makes this a
   real object tree (`ArticleSectionNode`, parent/children, `content=None` = "not yet written" is a first-class
   state); gpt-researcher keeps it flatter (a list of strings) because its writer step doesn't need
   nesting, only isolation.

3. **Each slot's writer receives a _scoped_ view, not the whole plan.** STORM: `section_outline` is the
   outline sliced to just that section's own subtree; `section_query` is that subtree's headers used only
   to retrieve that section's own evidence. gpt-researcher: each section gets its own `GPTResearcher`
   instance scoped to `query=subtopic`, told the `parent_query`/`main_topic` for framing but not shown
   sibling bodies (only sibling _headers_, and only in the subtopic-report prompt path). **The writer never
   receives the planner's private reasoning — only the resolved slot assignment plus enough shared context
   (topic/title, and in gpt-researcher's case existing headers) to stay coherent with its neighbors.**

4. **Slot-writing is embarrassingly parallel and mechanically enforced as such** — not an accident of
   async code, but an explicit `ThreadPoolExecutor`/`asyncio.gather` fan-out with a fixed worker cap
   (STORM `max_thread_num`, default 10). Both systems treat "no slot depends on another slot's finished
   prose" as an architectural invariant, which is _what makes the parallelism safe_, not just fast.

5. **A merge step reassembles the parts, and it is dumb by design.** STORM: `article.update_section(...)`
   grafts each returned section markdown back onto the matching tree node — no LLM call, pure
   string/tree surgery, only the citation index gets touched. gpt-researcher: the top-level `WriterAgent`
   is explicitly barred from rewriting bodies (its prompt: _"Do not include headers in the results"_) — its
   only creative job is the connective tissue (title, TOC, intro, conclusion) that references but never
   duplicates the sections. The reassembly step is the one place structure and prose meet again, and both
   systems keep the LLM's role there minimal and non-authoritative over content it didn't generate.

6. **Decoupling is strong enough to survive a process boundary.** STORM literally writes the outline to a
   flat file (`storm_gen_outline.txt`) and can resume article generation in a _separate CLI invocation_
   that reloads it from disk. This is the strongest form of "planner and writer are different concerns" —
   not just different function calls in one call stack, but different _stages of a job_ that don't need to
   share a process, a context window, or even a wall-clock session.

**Minimal contract, stripped to essence**: `plan(condensed_context) -> ordered_list[slot_id]`, then for
each `slot_id` independently and in parallel: `write(slot_id, scoped_context(slot_id), shared_frame) ->
content`, then `merge(ordered_list[(slot_id, content)]) -> final_artifact` where merge does no
free-generation, only assembly + minimal connective glue. The planner never writes prose. The per-slot
writer never sees other slots' prose while writing (STORM: literally cannot, no channel exists;
gpt-researcher: is told not to duplicate other slots' headers, and is architecturally isolated as its own
sub-agent instance). The merge step is prose-light and structure-heavy.

---

## 5. WR2 mapping

Current WR2 shape (per the task brief): ONE Claude call produces the whole 7-9-slide carousel JSON
(structure + copy + everything, in one shot), then a renderer routes slides to layouts. That single call
is doing what STORM/gpt-researcher split into 2-3 stages plus a fan-out.

### 5a. What maps to "planner"

The **planner's job, by the STORM/gpt-researcher contract, is exactly: decide the slot list, not the
prose that fills it.** For a WR2 carousel that's:

- the narrative **arc** (Hook → Frame → Discovery → Closing, per the existing `wr2-storyboarder` agent
  description — this agent already half-does this today, but currently in the same shot as the copy)
- the **spine**: how many slides (4-10, bounded), and which slide is the hero
- each slide's **role** (Hook / Frame / Discovery-N / Closing / elegant-close) — this is the WR2 analog of
  STORM's `section_name` / gpt-researcher's `sections: [...]` string list
- each slide's **layout family** assignment (a WR2-specific field neither STORM nor gpt-researcher has an
  analog for, since they don't route to visual templates — this would be WR2's own addition to the slot
  schema, decided at plan time because layout choice affects how much copy that slot can hold, i.e. the
  planner needs to know the writer's budget before dispatching)
- the **bullet-promise contract** per slot if the heading announces N items (Article 6.3 in the brand
  constitution) — this is metadata _about_ the slot, decided before the slot's body copy exists, exactly
  like STORM's `section_outline` string is metadata the writer receives, not writes.

The planner does **not** write final heading/body copy — same as STORM's planner never writes `output.section`
and gpt-researcher's `EditorAgent.plan_research` never writes body prose, only `title`+`sections`.

### 5b. What maps to "writer"

The **writer's job is: given one slide's role + its scoped context (brief facts relevant to THAT slide,
not the whole brief), produce that slide's heading/body/image-prompt** — analogous to STORM's
`generate_section(topic, section_name, information_table, section_outline, section_query)` or
gpt-researcher's per-section `GPTResearcher(query=subtopic, parent_query=parent_query,
report_type="subtopic_report")`.

Concretely, per-slide fan-out would look like STORM's `ThreadPoolExecutor` loop: N slide-writer calls, one
per planned slot, each receiving:

- the slide's role + heading-intent (from the plan)
- the slice of the brief relevant to that slide (STORM's `section_query`/`section_outline` scoping —
  today WR2's storyboarder gets the WHOLE brief for ALL slides at once, which is the single-shot pattern
  this research is meant to break)
- the shared frame: topic, audience segment, voice register, the overall title/hook (so slides don't
  contradict each other — this is gpt-researcher's `existing_headers` mechanism: give siblings' _headers_,
  never their bodies)
- NOT the other slides' body copy — exactly the isolation STORM enforces architecturally and
  gpt-researcher enforces by convention.

### 5c. The intermediate outline-object for a carousel

Modeling directly on STORM's `ArticleSectionNode` tree (adapted: a carousel is flat/ordered, not deeply
nested, so gpt-researcher's flatter `Subtopics` list is actually the closer shape) plus WR2's own
slot-metadata needs:

```json
{
  "topic": "PMK 37/2025 exemption threshold",
  "arc": "hook-frame-discovery-closing",
  "slides": [
    {
      "slot_id": 1,
      "role": "hook",
      "layout_family": "cover-statement",
      "heading_intent": "the number everyone gets wrong",
      "bullet_promise_n": null,
      "body": null,
      "hero": true,
      "image_prompt": null
    },
    {
      "slot_id": 2,
      "role": "frame",
      "layout_family": "context-bilingual",
      "heading_intent": "what 'dikecualikan' actually means",
      "bullet_promise_n": null,
      "body": null,
      "hero": false,
      "image_prompt": null
    },
    {
      "slot_id": 3,
      "role": "discovery-1",
      "layout_family": "bullet-list",
      "heading_intent": "3 conditions that trigger the exemption",
      "bullet_promise_n": 3,
      "body": null,
      "hero": false,
      "image_prompt": null
    },
    {
      "slot_id": 7,
      "role": "closing",
      "layout_family": "cta-statement",
      "heading_intent": "what to check before you file",
      "bullet_promise_n": null,
      "body": null,
      "hero": false,
      "image_prompt": null
    }
  ]
}
```

`body: null` here is the direct analog of STORM's `ArticleSectionNode.content = None` — an explicit,
inspectable "not yet written" state on every slot, set once by the planner and filled in independently by
N parallel writer calls, one per `slot_id`, each constrained to write only its own `body`/`heading`/
`image_prompt` fields and forbidden from touching `role`/`layout_family`/`bullet_promise_n` (those are the
planner's structural decisions, immutable inputs to the writer — same non-negotiable boundary as STORM's
writer never altering `section_name` or tree shape, only `content`).

The **merge step** (renderer routing slides to layouts, per WR2's existing architecture) stays exactly
what it already is — pure assembly, no LLM — which already matches STORM's `article.update_section()` /
gpt-researcher's publisher: the one part of WR2's current pipeline that's already correctly "dumb by
design" per the pattern in §4.

**What changes concretely if WR2 adopts this**: today's ONE Claude call becomes 1 planner call (small,
cheap, JSON-schema-constrained like gpt-researcher's `Subtopics`) + up to 9 parallel writer calls (each
scoped only to its slide, cheap individually, running concurrently the way STORM's
`ThreadPoolExecutor(max_workers=N)` does) + the existing deterministic renderer merge. This buys: (a) each
writer call can retry/regenerate independently without regenerating the whole carousel (STORM's
resumability-from-disk benefit, scaled down to "resumability per slide"); (b) `wr2-critic`'s retry-feedback
loop (which today has to reason about the whole 7-9-slide JSON at once) could target individual `slot_id`s
for re-write, the same way gpt-researcher's `reviewer`→`reviser` sub-loop operates per-section rather than
on the whole report; (c) the bullet-promise-rule and layout-budget constraints become plan-time decisions
the writer is handed rather than something the single mega-call has to self-enforce across 9 slides
simultaneously, which is exactly the kind of cross-cutting consistency failure a single-shot generation is
structurally worst at (WR2's own scars — Article 6.3 bullet-promise violations, §"WR2 slide-7 closer
statement-bomb" in memory — are precisely the failure mode this pattern is designed to prevent, by making
each slot's contract explicit and separately verifiable before prose exists).
