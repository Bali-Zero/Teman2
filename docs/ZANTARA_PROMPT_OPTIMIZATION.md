# 🎯 Zantara Prompt Optimization Strategy

**Date:** 2026-02-12
**Purpose:** Ottimizzazione dei prompt di sistema per Zantara basata su best practice 2026 per LLM enterprise

---

## 📊 Situazione Attuale

### Prompt Trovati nel Sistema

1. **zantara_system_prompt.md** - Prompt principale (italiano/WhatsApp style)
2. **prompt_builder.py (V6)** - Prompt tecnico/agentico (molto dettagliato, ~250 righe)
3. **prompt_builder_simple.py** - Versione semplificata per test Gemini
4. **5 Generals System Prompts** - Antigravity, Intelligence, Coding, Marketing, Perplexity

### Problema Identificato

**Il prompt V6 è troppo lungo e dettagliato** (~2000+ tokens stimati):

- Regole ripetute multiple volte
- Esempi eccessivi di closing phrases (7+ lingue)
- Spiegazioni verbose di concetti che il modello già conosce
- Istruzioni sovrapposte tra sezioni diverse

---

## 🔬 Best Practice 2026 (Ricerca Web)

### Principi Fondamentali

#### 1. **Brevità ed Efficacia**

> "Budget no more than 5 to 10 percent of your total window for the system prompt in typical apps. For moderately complex tasks, the optimal prompt length typically falls between 150 and 300 words… without crossing the 500-word threshold where diminishing returns and prompt bloat begin to degrade performance."

**Fonte:** [Why Long System Prompts Hurt Context Windows](https://medium.com/data-science-collective/why-long-system-prompts-hurt-context-windows-and-how-to-fix-it-7a3696e1cdf9)

#### 2. **Chiarezza Batte Lunghezza**

> "Clarity beats length. Move reference material out of the system prompt. Put long policies and docs behind retrieval. RAG isolates big text from the instruction block and lets you fetch only what is relevant."

**Fonte:** [The Impact of Prompt Bloat on LLM Output Quality](https://mlops.community/the-impact-of-prompt-bloat-on-llm-output-quality/)

#### 3. **Fiducia nei Modelli Moderni**

> "Modern AI models respond exceptionally well to clear, explicit instructions, and you shouldn't assume the model will infer what you want—state it directly. Claude performs best when you give it clear success criteria, structured inputs, and explicit output constraints."

**Fonte:** [Prompt Engineering Best Practices | Claude](https://claude.com/blog/best-practices-for-prompt-engineering)

#### 4. **Prompt Caching di Claude**

> "Customers can reduce costs by up to 90% and latency by up to 85% for long prompts. Place static content (tool definitions, system instructions, context, examples) at the beginning of your prompt."

**Fonte:** [Prompt Caching - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)

---

## 🎯 Strategia di Ottimizzazione per Zantara

### Principi Guida

1. **Sistema a 3 Livelli:**
   - **Core Identity** (sempre presente, cacheable) - 150-200 parole
   - **Contextual Rules** (inject on demand via RAG) - variabile
   - **Turn-Specific Instructions** (solo quando serve) - mini prompt

2. **Trust the Giant:**
   - Claude Sonnet 4.5 e Gemini 2.5 sono modelli enormi e intelligenti
   - Non serve spiegare cosa è "proactivity" o "warmth" - capiscono già
   - Focus su **cosa fare**, non **come pensare**

3. **Move to RAG:**
   - Esempi di closing phrases → Database o tool
   - Pricing rules → Tool `get_pricing` (già fatto ✅)
   - Legal citation format → Inject solo quando serve

4. **Versioning & A/B Testing:**
   - Tenere V6 come fallback
   - Creare V7 "lean" per test comparativi
   - Metriche: risposta quality score, latency, token usage

---

## 📝 Proposta: Zantara V7 Prompt (Lean & Mean)

### Struttura Ottimizzata

```markdown
# ZANTARA - AI Assistant for Bali Zero

## Identity

You are Zantara, AI assistant for Bali Zero (visa & business consulting, Bali).
Team: Adit (lead), Sahira, Surya, Ari, Dea, Damar, Vino, Ruslana (all human).

## Core Principles

1. **Compass** - Legal accuracy is critical
2. **Brain** - Comprehensive, detailed answers
3. **Heart** - Warm, relationship-first tone
4. **Proactive** - Suggest 1-2 next steps naturally

## Absolute Rules

- **Language:** Respond in user's language (detect: IT/EN/ID/DE/UK/ES/FR/PT/RU)
- **Pricing:** ONLY use `get_pricing` tool. If unavailable → "DA VERIFICARE"
- **Citations:** Legal answers require format: "📜 Sumber: [Regulation], Pasal [X]"
- **Identity:** If asked about tech (model, training) → "Sono Zan, l'AI di Bali Zero"
- **Greetings:** Only on first message per conversation
- **Evidence Threshold:** If score < 0.3 → ABSTAIN ("Let me confirm with team")

## Tools Priority

1. `knowledge_graph_search` - Documents, procedures, requirements
2. `get_pricing` - Bali Zero service prices (mandatory for pricing)
3. `web_search` - General knowledge, tourism, current events
4. `vector_search` - Context and explanations

## Communication Style (WhatsApp Mode)

- Short, direct messages (no markdown)
- Occasional emojis (natural, not excessive)
- Plain text paragraphs
- Escalation phrase: "Ti metto in contatto col team, ti scrivono a breve ✅"

## Output Quality

- Never repeat same closing phrase (rotate naturally)
- Never invent prices, dates, or regulations
- If uncertain → ask team or abstain
- Proactive suggestions at end (context-aware)

---

Context data will follow below this line.
```

### Cosa È Stato Rimosso (e Perché)

| Elemento Rimosso                     | Motivo                               | Soluzione Alternativa                     |
| ------------------------------------ | ------------------------------------ | ----------------------------------------- |
| 50+ closing phrase examples          | Bloat inutile, il modello sa variare | Trust the model                           |
| Spiegazioni verbose di "proactivity" | Il modello capisce già               | Comando diretto: "Suggest 1-2 next steps" |
| Regole ripetute 3+ volte             | Ridondanza confonde                  | Stated once, clearly                      |
| Anti-pattern lists per model         | Maintenance nightmare                | Let model's training handle it            |
| Emotional adaptation section         | Over-engineering                     | Natural tone + examples via RAG           |
| Detailed greeting rules              | Troppo specifico                     | Simple rule: "Only first message"         |

### Risultato Atteso

- **Da ~2000 tokens → ~400 tokens** (80% reduction)
- **Cacheability perfetta** (static content in testa)
- **Latency migliorata** (meno prefill time)
- **Cost reduction** (90% con prompt caching attivo)
- **Manutenibilità** (regole chiare, non ripetute)

---

## 🧪 Piano di Testing V7 vs V6

### Metriche da Misurare

1. **Quality Scores:**
   - Response relevance (1-5)
   - Accuracy (fact-check sample)
   - Tone consistency (warm/professional balance)
   - Proactivity score (suggests next steps?)

2. **Performance:**
   - Time to first token (TTFT)
   - Total response time
   - Input tokens per request
   - Cache hit rate (if caching enabled)

3. **User Satisfaction:**
   - Conversation completion rate
   - Escalation rate (to human team)
   - Follow-up question rate
   - Thumbs up/down feedback

### Test Setup

```python
# A/B Split
- 50% traffic → V7 (lean prompt)
- 50% traffic → V6 (current verbose prompt)
- Duration: 7 days
- Sample size: 500+ conversations

# Success Criteria for V7 Adoption
- Quality score: >= V6 (within 5% margin)
- TTFT: < V6 by at least 20%
- Token usage: < V6 by at least 60%
- User satisfaction: >= V6
```

---

## 🔧 Implementazione Tecnica

### 1. Creare prompt_builder_v7.py

```python
# backend/services/rag/agentic/prompt_builder_v7.py

ZANTARA_V7_CORE = """
[Il prompt lean sopra - 400 tokens max]
"""

def build_zantara_v7_prompt(
    context: str,
    conversation_history: List[Message],
    tools: List[Tool],
    mode: str = "chat"
) -> str:
    """
    Build Zantara V7 lean prompt with caching optimization.

    Cache structure (4 breakpoints):
    1. Core identity + rules (static, 5min TTL)
    2. Tool definitions (static, 5min TTL)
    3. RAG context (semi-static, 5min TTL)
    4. Conversation history (dynamic, 1min TTL)
    """

    # Layer 1: Core (cacheable)
    prompt_parts = [ZANTARA_V7_CORE]

    # Layer 2: Tools (cacheable)
    if tools:
        prompt_parts.append(format_tools_section(tools))

    # Layer 3: RAG Context (cacheable)
    if context:
        prompt_parts.append(f"\n## Retrieved Context\n{context}\n")

    # Layer 4: History (incremental cache)
    if conversation_history:
        prompt_parts.append(format_conversation(conversation_history))

    return "\n".join(prompt_parts)
```

### 2. Feature Flag per Rollout Graduale

```python
# backend/core/config.py

class Settings(BaseSettings):
    # Existing settings...

    ZANTARA_PROMPT_VERSION: str = "v6"  # or "v7"
    ZANTARA_V7_ROLLOUT_PERCENTAGE: int = 0  # 0-100
    PROMPT_CACHING_ENABLED: bool = True
```

### 3. Abilitare Prompt Caching (Claude API)

```python
# backend/services/llm_clients/claude_service.py

def create_message_with_caching(
    system_prompt: str,
    messages: List[Message]
):
    return anthropic.messages.create(
        model="claude-sonnet-4-5-20250929",
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"}  # Cache this!
            }
        ],
        messages=messages,
        # ... other params
    )
```

---

## 📚 Riferimenti Esterni

### Best Practice Guides

- [Claude Prompt Engineering Best Practices](https://claude.com/blog/best-practices-for-prompt-engineering)
- [Prompt Caching - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Azure Prompt Engineering Best Practices](https://www.netguru.com/blog/azure-prompt-engineering-best-practices)

### Research & Case Studies

- [Why Long System Prompts Hurt Context Windows](https://medium.com/data-science-collective/why-long-system-prompts-hurt-context-windows-and-how-to-fix-it-7a3696e1cdf9)
- [The Impact of Prompt Bloat on LLM Output Quality](https://mlops.community/the-impact-of-prompt-bloat-on-llm-output-quality/)
- [Disadvantage of Long Prompt for LLM](https://blog.promptlayer.com/disadvantage-of-long-prompt-for-llm/)

### LLM Comparisons

- [Best AI for Developers: Claude vs GPT vs Gemini (2026)](https://www.cosmicjs.com/blog/best-ai-for-developers-claude-vs-gpt-vs-gemini-technical-comparison-2026)
- [Claude vs ChatGPT vs Gemini Token Limits](https://www.topfreeprompts.com/resources/claude-vs-chatgpt-vs-gemini-token-limits-complete-2026-comparison)

---

## 🎬 Next Steps

1. **Review Prompt V7** - Team feedback sul lean prompt proposto
2. **Implement Feature Flag** - Setup per A/B testing
3. **Enable Prompt Caching** - Activate in Claude API calls
4. **Run 7-Day Pilot** - 50/50 split V6 vs V7
5. **Analyze Metrics** - Quality, performance, cost comparison
6. **Decision Point** - Adopt V7, iterate, or keep V6

---

## 💡 Filosofia Finale

> **"I giganti come Claude e Gemini non hanno bisogno di essere soffocati da prompt biblici. Hanno bisogno di istruzioni chiare, obiettivi precisi, e fiducia nella loro intelligenza."**

**Meno parole, più risultati.**

---

**Created by:** Claude Sonnet 4.5
**Based on:** 2026 prompt engineering research + Zantara codebase analysis
