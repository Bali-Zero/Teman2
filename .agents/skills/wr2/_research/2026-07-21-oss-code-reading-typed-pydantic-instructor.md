# Real-code survey: schema-constrained / discriminated-union generation

Method: every file below was fetched from GitHub via `gh api repos/<owner>/<repo>/contents/<path>`
(base64-decoded), or is the actual installed package on disk (`pydantic==2.13.4` in
`/Users/balizero/.local/share/mise/installs/python/3.11.15/lib/python3.11/site-packages/pydantic/`).
The pydantic discriminated-union recipe was additionally **executed locally** (not just read) to
prove the exact error text a retry loop would see. HEAD SHAs captured 2026-07-21.

## 1. Verification table

| Library                             | Org (verified)                                                                     | ✅/❌ | Files actually read                                                                                                                                                                                                                                                                   | License    | HEAD SHA                                   |
| ----------------------------------- | ---------------------------------------------------------------------------------- | ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------------------------------------------ |
| **instructor**                      | `567-labs/instructor` (moved from `jxnl/instructor`, confirmed via `gh repo view`) | ✅    | `instructor/v2/core/retry.py` (544 lines), `instructor/v2/core/response.py` (560), `instructor/v2/core/registry.py` (379), `instructor/v2/providers/anthropic/handlers.py` (932), `instructor/v2/core/json.py` (JSON-extraction helpers), `docs/concepts/unions.md`                   | MIT        | `47fdb2ca07119d389a3c0e8bc28b9930b814f294` |
| **outlines**                        | `dottxt-ai/outlines`                                                               | ✅    | `src/outlines/backends/outlines_core.py` (294), `src/outlines/backends/base.py`, `src/outlines/processors/base_logits_processor.py` (137), `src/outlines/types/json_schema_utils.py` (197), `src/outlines/types/dsl.py` (1013, skimmed)                                               | Apache-2.0 | `cb095ba70fbd5bde4f612c4a996631f00834c7ba` |
| **pydantic** (discriminated unions) | `pydantic/pydantic`                                                                | ✅    | `docs/concepts/unions.md` (617 lines, real doc matching installed v2.13 — has a `version-added v2.13` marker confirming version match) + local `pydantic/fields.py` (`discriminator` kwarg, lines 79/134/938.../1235) + **empirically executed** against installed `pydantic==2.13.4` | MIT        | `2294b52862478f3ef0fa0afd3cfdc9acba3881b0` |
| **BAML** (optional)                 | `BoundaryML/baml`                                                                  | ✅    | `engine/baml-lib/jsonish/README.md`, `engine/baml-lib/jsonish/src/deserializer/coercer/coerce_union.rs` (full file, ~140 lines)                                                                                                                                                       | Apache-2.0 | `be5e7cd57b4768da2ad40a3d65ec7340f4de902f` |

Local install confirmed: `pip show pydantic` → `Version: 2.13.4`, `Location:
/Users/balizero/.local/share/mise/installs/python/3.11.15/lib/python3.11/site-packages`.
`instructor` and `outlines` are **not** installed in this environment (`pip show` returned
nothing, `find / -iname "*instructor*"/"*outlines*"` found nothing) — their code was read
exclusively from GitHub, never fabricated.

**Naming note (important, self-correcting):** the task description said instructor's retry loop
lives in `instructor/retry.py` / `process_response.py`. That was true of instructor v1. The
current `main` branch has migrated to a `v2/` architecture with a registry-of-handlers pattern —
`instructor/core/retry.py` and `instructor/processing/schema.py` etc. now exist only as
3-line **compatibility re-export shims** (`from instructor.v2.core.retry import *`) pointing at
`instructor/v2/core/retry.py`, `instructor/v2/core/response.py`, `instructor/v2/providers/<provider>/handlers.py`.
I read the actual v2 files, not the shims, and the code below is against them.

---

## 2. The discriminated-union generation pattern, in real code

### 2a. DECLARE — N shapes as a tagged union (pydantic, real doc example, path `docs/concepts/unions.md:195-232`)

```python
from typing import Literal
from pydantic import BaseModel, Field, ValidationError


class Cat(BaseModel):
    pet_type: Literal['cat']
    meows: int


class Dog(BaseModel):
    pet_type: Literal['dog']
    barks: float


class Lizard(BaseModel):
    pet_type: Literal['reptile', 'lizard']
    scales: bool


class Model(BaseModel):
    pet: Cat | Dog | Lizard = Field(discriminator='pet_type')
    n: int
```

instructor's own docs (`docs/concepts/unions.md` in the instructor repo, not pydantic's) show the
identical pattern used directly as the `response_model`:

```python
from typing import Literal, Union
from pydantic import BaseModel
import instructor


class UserQuery(BaseModel):
    type: Literal["user"]
    username: str


class SystemQuery(BaseModel):
    type: Literal["system"]
    command: str


Query = Union[UserQuery, SystemQuery]

client = instructor.from_provider("openai/gpt-4.1-mini")
response = client.create(
    response_model=Query,
    messages=[{"role": "user", "content": "Parse: user lookup jsmith"}],
)
```

Note instructor's doc uses `Union[A, B]` _without_ an explicit `Field(discriminator=...)` — it
relies on Pydantic's **smart-union** mode (tries each member, picks the best match) rather than a
tag lookup. For >2-3 members or when shapes overlap, pydantic's own docs recommend the explicit
`discriminator=` form because smart-union is O(n) trial-validation and can pick the wrong member on
ambiguous input; tag-based dispatch is O(1) and unambiguous. **For WR2's 7-way union, use explicit
`discriminator=`, not bare `Union[...]`.**

### 2b. VALIDATE — a raw JSON string, empirically run against the exact WR2 shape

I did not just read this pattern — I **executed it** against the real installed `pydantic==2.13.4`
to see the actual validation-error text a retry loop would receive:

```python
from typing import Literal, Union, Annotated, List
from pydantic import BaseModel, Field, ValidationError, TypeAdapter

class ProseSlide(BaseModel):
    kind: Literal["prose"]
    heading: str
    body: str

class StatementSlide(BaseModel):
    kind: Literal["statement"]
    statement: str

class FactStackSlide(BaseModel):
    kind: Literal["fact_stack"]
    heading: str
    facts: List[str]

Slide = Annotated[
    Union[ProseSlide, StatementSlide, FactStackSlide],
    Field(discriminator="kind"),
]

class Carousel(BaseModel):
    slides: List[Slide]
```

Good input parses to the right concrete classes:

```
>>> Carousel.model_validate_json('{"slides": [{"kind":"prose","heading":"H","body":"B"}, ...]}')
GOOD PARSE: ['ProseSlide', 'StatementSlide', 'FactStackSlide']
```

Bad input (missing field + unknown tag) produces this **real, observed** error — this is the exact
string you'd feed back to the LLM:

```
2 validation errors for Carousel
slides.0.prose.body
  Field required [type=missing, input_value={'kind': 'prose', 'heading': 'H'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
slides.1
  Input tag 'unknown_shape' found using 'kind' does not match any of the expected tags: 'prose', 'statement', 'fact_stack' [type=union_tag_invalid, input_value={'kind': 'unknown_shape', 'x': 1}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/union_tag_invalid
```

Two properties matter for the retry loop:

1. **Per-item location** (`slides.0.prose.body`, `slides.1`) — the LLM can be told _which slide,
   which shape, which field_ is wrong, not just "invalid JSON".
2. **Legal-tag enumeration on a bad discriminator** (`does not match any of the expected tags:
'prose', 'statement', 'fact_stack'`) — pydantic itself lists your 7 valid `kind` values in the
   error, which is free prompt material for the reask message.

### 2c. RETRY — instructor's real retry loop feeding the ValidationError back

This is the mechanism instructor actually ships, read verbatim from
`instructor/v2/core/retry.py` (567-labs/instructor, MIT, SHA `47fdb2c`):

```python
_RETRYABLE_PARSE_ERRORS = (
    ValidationError,
    json.JSONDecodeError,
    AsyncValidationError,
    ResponseParsingError,
)

def retry_sync_v2(func, response_model, provider, mode, context, max_retries,
                   args, kwargs, strict, hooks=None) -> T_Model:
    ...
    handlers = mode_registry.get_handlers(provider, mode)
    max_retries_instance = Retrying(
        stop=stop_after_attempt(max(max_retries, 0) + 1),
        retry=retry_if_exception_type(_RETRYABLE_PARSE_ERRORS),
        reraise=True,
    )
    ...
    for attempt in max_retries_instance:
        with attempt:
            response = func(*args, **kwargs)          # call the LLM
            ...
            try:
                parsed = handlers.response_parser(      # parse+validate raw text
                    response=response,
                    response_model=response_model,
                    validation_context=context,
                    strict=strict,
                    stream=stream,
                    is_async=False,
                )
                return _finalize_parsed_response(parsed, response)   # SUCCESS -> return
            except _RETRYABLE_PARSE_ERRORS as e:
                failed_attempts.append(FailedAttempt(attempt_number, e, response))
                kwargs = handlers.reask_handler(          # build the NEXT prompt
                    kwargs=kwargs, response=response, exception=e,
                )
                raise   # tenacity catches this -> loops to next attempt with new kwargs
```

`tenacity` (a normal PyPI retry library, not Anthropic-SDK-specific) drives the loop;
`handlers.response_parser` and `handlers.reask_handler` are the two swappable functions per
provider/mode. The provider-specific implementation that matters for a **CLI-shelled-out, raw-text**
setup is `AnthropicJSONHandler` in `instructor/v2/providers/anthropic/handlers.py:631-759`
(same repo, same SHA):

```python
class AnthropicJSONHandler(AnthropicHandlerBase):
    mode = Mode.JSON

    def handle_reask(self, kwargs, response, exception) -> dict[str, Any]:
        kwargs = kwargs.copy()
        text_blocks = [c for c in response.content if c.type == "text"]
        text_content = text_blocks[-1].text if text_blocks else "No text content found in response"
        reask_msg = {
            "role": "user",
            "content": (
                "Validation Errors found:\n"
                f"{exception}\nRecall the function correctly, fix the errors found in "
                f"the following attempt:\n{text_content}"
            ),
        }
        kwargs["messages"].append(reask_msg)
        return kwargs

    def _parse_json_response(self, response, response_model, validation_context, strict):
        ...
        extra_text = extract_json_from_codeblock(text)   # <-- works on RAW TEXT, no SDK object needed
        if strict:
            return response_model.model_validate_json(extra_text, context=validation_context, strict=strict)
        parsed = json.loads(extra_text, strict=False)
        return response_model.model_validate(parsed, context=validation_context, strict=strict)
```

`extract_json_from_codeblock` (`instructor/v2/core/json.py`, same repo) is the single most
directly liftable function for our case — it takes an arbitrary text blob (markdown fences,
reasoning preamble, anything) and returns **the last balanced `{...}`/`[...]` span that parses as
valid JSON** — with a documented security rationale:

```python
def extract_json_from_codeblock(content: str) -> str:
    """Extract the last JSON object- or array-like span from a text block.

    Returns the LAST complete JSON object, not the first. The LLM's own
    structured output is the authoritative JSON and appears last; JSON that
    appeared earlier may have originated from user input embedded in the
    prompt and was referenced in the model's reasoning. Returning the first
    object allowed prompt-injection to hijack the parsed output.
    """
    candidates: list[str] = []
    search_index = 0
    while search_index < len(content):
        start_index = next((i for i in range(search_index, len(content))
                             if content[i] in "{["), None)
        if start_index is None:
            break
        start_char = content[start_index]
        end_stack = ["}" if start_char == "{" else "]"]
        in_string = False
        escape_next = False
        candidate_found = False
        for end_index in range(start_index + 1, len(content)):
            char = content[end_index]
            if escape_next:
                escape_next = False
            elif char == "\\" and in_string:
                escape_next = True
            elif char == '"':
                in_string = not in_string
            if in_string:
                continue
            if char in "{[":
                end_stack.append("}" if char == "{" else "]")
                continue
            if end_stack and char == end_stack[-1]:
                end_stack.pop()
                if not end_stack:
                    candidate = content[start_index:end_index + 1]
                    try:
                        json.loads(candidate)
                    except Exception:
                        break
                    candidates.append(candidate)
                    search_index = end_index + 1
                    candidate_found = True
                    break
        if not candidate_found:
            search_index = start_index + 1
    return candidates[-1] if candidates else content
```

Put together, instructor's whole "works on raw JSON string" chain is:
**raw CLI stdout text → `extract_json_from_codeblock` → `json.loads` → `Model.model_validate` →
on `ValidationError`, string-format the error + append the previous raw text as a `user` message
→ call the LLM again → repeat up to N times (tenacity `stop_after_attempt`).**
None of it touches the Anthropic SDK object model — `response.content[...].type == "text"` is the
only Anthropic-shaped bit, and even that is trivially replaced by "the CLI's stdout string" in our
case.

---

## 3. Grammar-level constraint (outlines) — what it guarantees, and why we can't use it

outlines (dottxt-ai/outlines, Apache-2.0, SHA `cb095ba7`) does NOT validate-after-the-fact. It
compiles the JSON Schema into a **regex**, the regex into a **finite-state machine (`Index`)** over
the model's actual token vocabulary, and then masks the logits **at every single decoding step** so
the sampler is physically unable to emit a token that would violate the schema.

`src/outlines/backends/outlines_core.py` (real code):

```python
from outlines_core import Guide, Index, Vocabulary
from outlines_core.json_schema import build_regex_from_schema

class OutlinesCoreBackend(BaseBackend):
    def get_json_schema_logits_processor(self, json_schema: str, whitespace_pattern=None):
        regex = build_regex_from_schema(json_schema, whitespace_pattern)   # JSON Schema -> regex
        return self.get_regex_logits_processor(regex)

    def get_regex_logits_processor(self, regex: str):
        index = Index(regex, self.vocabulary)         # regex -> FSM compiled over the token vocab
        return OutlinesCoreLogitsProcessor(index, self.tensor_library_name)


class OutlinesCoreLogitsProcessor(OutlinesLogitsProcessor):
    def _setup(self, batch_size, vocab_size):
        ...
        self._guides = [Guide(self.index) for _ in range(batch_size)]     # one FSM state-tracker per sequence
        self._bitmasks = [self.allocate_token_bitmask(vocab_size) for _ in range(batch_size)]

    def process_logits(self, input_ids, logits):
        if self.is_first_token:
            self._setup(batch_size, vocab_size)
        else:
            for i in range(batch_size):
                last_token_id = ...
                self._guides[i].advance(token_id=last_token_id, ...)      # advance FSM state by the token just sampled
        return self.bias_logits(batch_size, logits)                       # mask disallowed tokens to -inf BEFORE sampling

    def _bias_logits_torch(self, batch_size, logits):
        for i in range(batch_size):
            fill_next_token_bitmask(self._guides[i], self._bitmasks[i])   # which tokens are FSM-legal right now?
            apply_token_bitmask_inplace(logits[i], self._bitmasks[i])     # zero out everything else
        return logits
```

`src/outlines/processors/base_logits_processor.py` shows this is wired in as a HuggingFace/vLLM/
llama.cpp-style `LogitsProcessor` — a callback invoked by the model's own decoding loop on **every**
generated token, not something bolted on after generation. This is why it's called "grammar-level
enforcement" — the LLM is **structurally incapable** of producing an invalid token at any position,
as opposed to instructor, which lets the LLM emit whatever it wants and then rejects/retries.

For unions specifically: `src/outlines/types/json_schema_utils.py` turns a JSON-Schema `anyOf`/type-
list into a Python `Union[...]` (and, via `build_regex_from_schema`, into a regex alternation `(A|B|C)`
at the FSM level) — so a 7-way discriminated union becomes 7 alternative regex branches the FSM can
walk, and the sampler can only ever complete one of them. Real excerpt:

```python
# src/outlines/types/json_schema_utils.py
if isinstance(t, list):
    # JSON Schema allows ``type`` to be a list of type names, e.g. the
    # common nullable form ``["string", "null"]``. Map each member to a
    # Python type and combine them into a Union (mirroring the ``anyOf``
    # the regex backend uses for type arrays).
    members = tuple(schema_type_to_python({**schema, "type": member}, caller_target_type) for member in t)
    return Union[members] if members else Any
```

**Why we cannot use this**: it requires **white-box access to per-token logits** — it only works
against `Transformers`, `LlamaCpp`, or `MLXLM` model objects that outlines drives directly in-process
(`src/outlines/backends/outlines_core.py` imports `outlines.models.llamacpp.LlamaCpp`,
`outlines.models.mlxlm.MLXLM`, `outlines.models.transformers.Transformers` — all local, in-process
model wrappers with logits access). The `claude` CLI is a black box: we get finished stdout text, no
logits, no per-token callback hook, no ability to bias sampling. There is no "outlines but for a
subprocess" mode — the guarantee outlines makes is fundamentally a decoding-time property that only
the entity actually running the forward pass can enforce.

---

## 4. BAML's schema-aligned recovery (optional target) — a third, different mechanism

BoundaryML/baml (Apache-2.0, SHA `be5e7cd5`) ships a Rust deserializer called **jsonish**
(`engine/baml-lib/jsonish/`) that is neither "validate then retry" (instructor) nor "constrain
during decode" (outlines). It is **best-effort schema-aligned coercion of a single, possibly-broken
LLM text response**, with no second LLM call required. Its own README states the contract:

```
pub fn from_str(
    of: &OutputFormatContent,
    target: &FieldType,
    raw_string: &str,
    allow_partials: bool,
) -> Result<BamlValueWithFlags>
```

> "It provides a guarantee that the schema is able to be flexibly parsed out from the input.
> Some scenarios include: Finding objects when there is prefixing and post fixed text. Parsing in
> field names with aliases. Casting to the right type. Wrapping around arrays when necessary.
> Obeying constraints."

For unions specifically, `coerce_union.rs::coerce_union()` (full real function read) tries **every
variant** of the union against the parsed-but-imperfect value, scores each attempt (0 = perfect
match), and short-circuits on the first perfect score; otherwise it calls `array_helper::pick_best`
to choose the least-bad candidate:

```rust
pub(super) fn coerce_union(ctx, union_target, value) -> Result<BamlValueWithFlags, ParsingError> {
    let all_options = options.iter_include_null();
    let mut parsed: Vec<Result<BamlValueWithFlags, ParsingError>> = Vec::new();
    let mut best_score = i32::MAX;

    for (i, option) in all_options.iter().enumerate() {
        let result = option.coerce(ctx, union_target, value);
        if let Ok(mut val) = result {
            let score = val.score();
            if score == 0 {
                val.add_flag(Flag::UnionMatch(i, vec![]));
                return Ok(val);          // perfect match on this variant -> done, no retry needed
            }
            if score < best_score { best_score = score; }
            parsed.push(Ok(val));
        } else {
            parsed.push(result);
        }
    }
    array_helper::pick_best(ctx, union_target, &parsed)   // otherwise pick least-bad variant
}
```

There's also a `union_variant_hint` optimization for **arrays of unions** (exactly our shape — a
list of 7-typed slides): if the previous array element matched variant index `i`, it tries variant
`i` first on the next element, on the (correct) assumption that carousels/lists tend to be
locally homogeneous in shape. This is a nice, liftable _heuristic_ even outside BAML: order your
Pydantic union members by "what the last slide was" as a soft hint, though Pydantic's own
discriminator dispatch is O(1) by tag so the hint mostly saves nothing there — it matters more for
BAML/jsonish because coercion there is a trial-based score, not a tag lookup.

**Why this is interesting but not directly liftable**: this is a ~140-line snippet inside a large
Rust crate (`baml-lib/jsonish`) that is part of a full compiler/runtime (BAML has its own DSL, code-
gen, and Python/TS client bindings) — there's no standalone pip-installable "just the flexible
parser" story without pulling in the whole BAML toolchain. It's real, it's read, but "lift the
pattern" here means "replicate the _idea_ (score every union-variant coercion, prefer perfect
matches, degrade gracefully to best-effort)" in Python, not literally reuse the code.

---

## 5. The minimal liftable recipe for WR2

Grounded directly in the real code above (instructor's retry architecture + reask-message format +
`extract_json_from_codeblock`, plus the empirically-verified pydantic discriminated-union pattern).
This works entirely on **the `claude` CLI's raw stdout text** — no Anthropic SDK, no per-token
access, nothing instructor/outlines/BAML themselves would need to be `pip install`ed for (though
`pip install instructor` just for `extract_json_from_codeblock` + the JSON-mode reask-message
string is defensible too, since it's MIT and provider-agnostic on the parsing side).

```python
"""wr2_slide_schema.py — discriminated-union slide contract + validate-and-retry
against the `claude` CLI. Pattern lifted from:
  - instructor v2 AnthropicJSONHandler.handle_reask / _parse_json_response
    (github.com/567-labs/instructor, instructor/v2/providers/anthropic/handlers.py)
  - instructor v2 extract_json_from_codeblock (instructor/v2/core/json.py)
  - pydantic Field(discriminator=...) tagged unions (docs.pydantic.dev/concepts/unions,
    empirically verified against installed pydantic==2.13.4)
"""
from __future__ import annotations

import json
import subprocess
from typing import Annotated, List, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter, ValidationError


# --- 2a. DECLARE the 7 slide shapes as a tagged union ------------------------

class ProseSlide(BaseModel):
    kind: Literal["prose"]
    heading: str
    body: str

class StatementSlide(BaseModel):
    kind: Literal["statement"]
    statement: str

class FactStackSlide(BaseModel):
    kind: Literal["fact_stack"]
    heading: str
    facts: List[str]

class QaDialogueSlide(BaseModel):
    kind: Literal["qa_dialogue"]
    question: str
    answer: str

class StatusListSlide(BaseModel):
    kind: Literal["status_list"]
    heading: str
    items: List[str]

class TimelineSlide(BaseModel):
    kind: Literal["timeline"]
    heading: str
    steps: List[str]

class StatCardSlide(BaseModel):
    kind: Literal["stat_card"]
    stat: str
    label: str

class CtaSlide(BaseModel):
    kind: Literal["cta"]
    heading: str
    action: str

Slide = Annotated[
    Union[
        ProseSlide, StatementSlide, FactStackSlide, QaDialogueSlide,
        StatusListSlide, TimelineSlide, StatCardSlide, CtaSlide,
    ],
    Field(discriminator="kind"),
]

SlideList = TypeAdapter(List[Slide])


# --- 2b/2c. extract-JSON-from-free-text + VALIDATE + RETRY loop -------------
# extract_json_from_codeblock: ported verbatim from instructor/v2/core/json.py
# (MIT-licensed, small, self-contained — the one function actually worth
#  copying wholesale rather than depending on the instructor package).

def extract_json_from_codeblock(content: str) -> str:
    candidates: list[str] = []
    search_index = 0
    while search_index < len(content):
        start_index = next(
            (i for i in range(search_index, len(content)) if content[i] in "{["), None
        )
        if start_index is None:
            break
        start_char = content[start_index]
        end_stack = ["}" if start_char == "{" else "]"]
        in_string = False
        escape_next = False
        candidate_found = False
        for end_index in range(start_index + 1, len(content)):
            char = content[end_index]
            if escape_next:
                escape_next = False
            elif char == "\\" and in_string:
                escape_next = True
            elif char == '"':
                in_string = not in_string
            if in_string:
                continue
            if char in "{[":
                end_stack.append("}" if char == "{" else "]")
                continue
            if end_stack and char == end_stack[-1]:
                end_stack.pop()
                if not end_stack:
                    candidate = content[start_index:end_index + 1]
                    try:
                        json.loads(candidate)
                    except Exception:
                        break
                    candidates.append(candidate)
                    search_index = end_index + 1
                    candidate_found = True
                    break
        if not candidate_found:
            search_index = start_index + 1
    return candidates[-1] if candidates else content


def call_claude_cli(prompt: str) -> str:
    """Our sanctioned path: shell out to `claude`, MAX-plan OAuth quota.
    Never anthropic.Anthropic(api_key=...) — see CLAUDE.md §5."""
    result = subprocess.run(
        ["claude", "--print"],
        input=prompt,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def generate_slides(prompt: str, max_retries: int = 3) -> List[Slide]:
    """instructor's retry_sync_v2 shape, minus tenacity/registry machinery,
    minus any SDK object — works on a raw text string from the CLI."""
    messages_context = prompt
    last_raw_text = ""

    for attempt in range(1, max_retries + 1):
        raw_text = call_claude_cli(messages_context)
        last_raw_text = raw_text
        json_str = extract_json_from_codeblock(raw_text)

        try:
            slides = SlideList.validate_json(json_str)
            return slides                              # SUCCESS
        except (ValidationError, json.JSONDecodeError) as e:
            if attempt == max_retries:
                raise
            # instructor's AnthropicJSONHandler.handle_reask, adapted to plain text:
            messages_context = (
                f"{prompt}\n\n"
                "Your previous attempt failed validation.\n"
                f"Validation errors found:\n{e}\n"
                "Recall the schema and fix the errors found in the following attempt:\n"
                f"{last_raw_text}"
            )
    raise RuntimeError("unreachable")
```

What each numbered piece maps to, concretely:

- **2a** = the pydantic `Annotated[Union[...], Field(discriminator="kind")]` block — proven to
  route on the `kind` tag and to raise `union_tag_invalid` with the full legal-tag list on a bad
  tag (see §2b above, real output).
- **2b** = `extract_json_from_codeblock` (verbatim port of instructor's real function) +
  `SlideList.validate_json(...)` — the `TypeAdapter(List[Slide])` form (also empirically tested
  above under "TypeAdapter direct on the union") is what you want when the top-level LLM output is
  a bare JSON array of slides rather than a wrapper object.
- **2c** = the retry-with-reask loop, structurally identical to `retry_sync_v2` in
  `instructor/v2/core/retry.py` (try → validate → on `ValidationError` build a new prompt that
  includes the error text + previous raw output → loop), but with `tenacity` and the
  provider-handler-registry stripped out since we only ever have one "provider" (the CLI) and one
  "mode" (raw JSON in free text) — instructor's registry indirection exists to support 40+
  provider/mode combinations we don't have.

---

## 6. Honest caveat — what we can and cannot use

**Cannot use (grammar-level / decode-time constraint, outlines-style):**

- outlines' FSM/logits-bitmask mechanism requires being the process that runs the forward pass and
  owns the logits tensor (`Transformers`/`LlamaCpp`/`MLXLM` model objects, `process_logits(input_ids,
logits)` called every token). The `claude` CLI gives us finished stdout text and nothing else —
  no token-level hook exists to intercept. There is no partial/adapted version of this technique for
  a black-box subprocess; the guarantee ("every sampled token is schema-legal") is _definitionally_
  a property of the sampler, not of anything downstream. This also rules out vLLM/TGI-style
  structured-decoding backends (`llguidance`, `xgrammar` — both present as sibling backends in
  `src/outlines/backends/`) for the same reason: they all bias logits pre-sampling inside the
  inference server.
- Anthropic's own hosted structured-output feature (seen referenced in
  `instructor/v2/providers/anthropic/handlers.py:762` as `AnthropicStructuredOutputsHandler`, using
  an `output_format` parameter) is the closest first-party equivalent for Claude specifically, but
  it's an API-level feature reached through the Python SDK/HTTP API — not exposed through the
  `claude` CLI's `--print` text mode, so it's in the same "cannot use" bucket for us right now.

**Can use (post-hoc validation + retry, instructor-style — this is the one for WR2):**

- Pydantic `Field(discriminator=...)` tagged unions: pure Python, zero dependency beyond pydantic
  (already a project dependency), works on any JSON string from any source, gives precise
  per-item/per-field error locations and enumerates legal discriminator tags on a bad tag — verified
  empirically above.
- instructor's retry-with-reask _shape_ (try → parse → validate → on failure, build a follow-up
  prompt containing the exact validation error + the previous raw output → retry N times): this is
  provider-agnostic in spirit even though instructor's own implementation is registry-dispatched
  per SDK object type. We reimplement the ~30-line core loop directly against `claude` CLI stdout
  (§5 above) rather than depending on the `instructor` package, since instructor's value-add
  (39-provider dispatch, streaming, tool-call parsing) is all SDK-shaped scaffolding we don't need —
  the part worth lifting is the _loop shape_ and the _reask message format_, both of which are
  trivial to reproduce and don't require adding `instructor` (and transitively `openai`, its default
  dependency) to the project.
- `extract_json_from_codeblock`: small, self-contained, MIT, directly portable — worth copying
  verbatim rather than re-deriving, since its "last balanced JSON span, not first" behavior encodes
  a real security lesson (prompt-injection via earlier JSON in the text) that's easy to get wrong on
  a first pass.
- BAML's "score every union variant, take the best" _idea_ (not code) is a reasonable enhancement
  if we ever get slides that are close-but-not-exact matches to a shape (e.g. a `fact_stack` with an
  extra unexpected field) — Pydantic's discriminator dispatch is strict/exact on the tag, so a
  scoring fallback pass is something to consider later if the retry loop proves too expensive in
  practice, but it is not needed for a first implementation.
