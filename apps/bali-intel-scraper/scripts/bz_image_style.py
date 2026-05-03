"""
Bali Zero Image Style — Single source of truth for all image generation prompts.
Used by: intel scraper (step 8 covers), war room (step 3 carousel).

═══════════════════════════════════════════════════════════════════
VISUAL IDENTITY — 5 PILLARS (from @balizero0 brand analysis)
═══════════════════════════════════════════════════════════════════

1. CINEMATIC REALISM, NOT "AI ART"
   Images look like frames from a film — photorealistic with subtle
   high-end digital film grain. Never the "plastic" look of generic
   AI generative art. Absolute seriousness even when the subject is
   surreal. Treated as editorial documentary.

2. TEAL & AMBER COLOR GRADING
   Dominant palette: teal/cyan in shadows, amber/gold in highlights
   and sunlit areas. Same grading as Denis Villeneuve / Roger Deakins.
   Simultaneously warm (Bali) and cinematic (authority).
   THIS IS NON-NEGOTIABLE — include in every prompt.

3. SERIOUS SURREAL ANACHRONISM
   Einstein in batik at a Balinese temple. Dalí painting at Ubud
   Art Market. Historical icons transplanted into Balinese contexts.
   KEY: zero visual irony. The image is treated as a real editorial
   portrait — the conceptual contrast creates impact, not graphic style.

4. MONUMENTAL SCALE + GOLDEN HOUR
   Compositions favor grandeur: temples backlit, aerial panoramas,
   subjects framed from below. Light is almost always golden hour
   or backlit — volumetric, with visible rays, "epic" atmosphere.
   80% golden hour / 20% moody overcast (crisis/alert articles).

5. TONAL DUALISM: ASPIRATION vs THREAT
   Opportunity slides: warm tones, golden, enveloping light, paradise.
   Risk/alert slides: colder tones, deep shadows, tighter framing,
   surveillance or crisis aesthetic.

═══════════════════════════════════════════════════════════════════
TECHNICAL SPEC
═══════════════════════════════════════════════════════════════════

CAMERAS:  ARRI Alexa Mini LF | Hasselblad X2D | RED V-Raptor | DJI Inspire 3 (aerial)
LENSES:   24mm wide (epic/architecture) | 35mm (environmental portrait)
          50mm f/1.4 (standard) | 85mm f/1.4 (portrait/close-up)
          90-120mm macro (details/still life)
ASPECT:   16:9 for article covers (1200x630px output)
NEVER:    text, words, logos, watermarks, cartoon, illustration,
          3D render, neon, cyberpunk, smiling businesspeople,
          handshakes, stock photo clichés

ASPIRATION LIGHT: golden hour, warm amber sunlight, volumetric light
                  rays, backlit silhouettes, lens flare
CRISIS LIGHT:     harsh fluorescent, cold teal dominant, overcast moody,
                  flat institutional, screen glow, surveillance aesthetic
"""

import hashlib
import os
import re
import subprocess
import sys
from typing import Optional

# ── Mood classification ──────────────────────────────────────────────────────

# Keywords that signal CRISIS mood (regulation, risk, penalty, enforcement)
_CRISIS_KEYWORDS: frozenset[str] = frozenset({
    # enforcement / legal
    "deportat", "arrest", "raid", "fine", "penalt", "sanction", "ban", "prohibit",
    "illegal", "violation", "crackdown", "enforc", "seized", "revok", "suspend",
    "blacklist", "criminal", "fraud", "scam", "fake", "corrupt",
    # regulation / bureaucracy
    "new rule", "new regulation", "mandatory", "required", "deadline", "overdue",
    "compliance", "audit", "inspection", "warning", "alert", "crisis", "risk",
    "danger", "threat", "collapse", "failure", "rejected", "denied", "refused",
    # Indonesian specific
    "imigrasi", "deportasi", "tilang", "denda", "pajak baru", "coretax",
    "peraturan baru", "wajib", "larangan", "pelanggaran",
    # economic negative
    "oversupply", "crash", "bubble", "decline", "drop", "recession", "saturated",
    "abandoned", "empty", "foreclos", "bankrupt", "insolv", "collaps", "plunge",
    "slump", "shrink", "worsen", "deteriorat",
})

# Keywords that signal ASPIRATION mood
_ASPIRATION_KEYWORDS: frozenset[str] = frozenset({
    "opportun", "invest", "growth", "success", "launch", "open",
    "paradise", "dream", "lifestyle", "freedom", "remote work", "digital nomad",
    "luxury living", "beach life", "family visa", "thrive", "thriving",
    "boom", "surge", "record high", "milestone", "expand", "profit",
    "visa approval", "approved", "granted", "welcome foreigner",
    "attract investor", "incentive", "new opportunity", "easier",
})


def classify_mood(title: str, summary: str) -> str:
    """Classify article mood as aspiration or crisis.

    Uses ratio-based scoring (hits / total_words) to avoid bias on long texts,
    with a minimum hit threshold to avoid false positives on single keyword matches.
    Crisis wins ties — false negative on crisis = brand risk (golden light on bad news).
    """
    import re
    text = (title + " " + summary).lower()
    words = re.findall(r"\b\w+\b", text)
    total = max(len(words), 1)

    # Substring match for stemmed keywords (e.g. "collaps" matches "collapse", "collapsing")
    crisis_hits = sum(1 for kw in _CRISIS_KEYWORDS if kw in text)
    aspiration_hits = sum(1 for kw in _ASPIRATION_KEYWORDS if kw in text)

    crisis_ratio = crisis_hits / total
    aspiration_ratio = aspiration_hits / total

    # Require at least 1 hit AND ratio dominance of 1.5x
    if crisis_hits >= 1 and crisis_ratio >= aspiration_ratio * 1.2:
        return "crisis"
    if aspiration_hits >= 1 and aspiration_ratio > crisis_ratio * 1.2:
        return "aspiration"
    # Tiebreak: crisis wins
    if crisis_hits > 0 and aspiration_hits > 0:
        return "crisis"
    # Default to aspiration — brand stance is positive/opportunity-oriented
    return "aspiration"


# ── Camera/lens selection ────────────────────────────────────────────────────

def _select_camera_lens(category: str, mood: str, subject_type: str = "scene") -> tuple[str, str]:
    """Return (camera, lens) pair appropriate for category and mood."""
    # Aerial categories → DJI
    if category in ("property",) or "aerial" in subject_type:
        return "DJI Inspire 3 with Hasselblad camera", "wide anamorphic"

    # Portrait/close-up → Hasselblad + 85mm
    if subject_type in ("portrait", "detail", "macro"):
        cameras = ["Hasselblad X2D", "ARRI Alexa Mini LF"]
        camera = cameras[0] if category in ("lifestyle", "immigration") else cameras[1]
        lens = "85mm f/1.4 lens" if subject_type == "portrait" else "90mm macro lens"
        return camera, lens

    # Wide/architectural → RED or ARRI + 24-35mm
    if subject_type in ("wide", "architectural", "crowd"):
        camera = "RED V-Raptor" if mood == "crisis" else "ARRI Alexa Mini LF"
        lens = "35mm anamorphic lens" if mood == "crisis" else "24mm wide lens"
        return camera, lens

    # Default: ARRI + 35-50mm
    camera = "ARRI Alexa Mini LF"
    lens = "50mm f/1.4 lens" if category in ("lifestyle", "company") else "35mm lens"
    return camera, lens


# ── Light spec ───────────────────────────────────────────────────────────────

def _light_spec(mood: str) -> str:
    if mood == "aspiration":
        return (
            "golden hour warm amber sunlight streaming from the left, "
            "volumetric light rays, subtle lens flare, backlit atmosphere"
        )
    if mood == "crisis":
        return (
            "harsh overhead fluorescent lighting mixed with cold teal ambient, "
            "flat institutional light, deep teal shadows, no warmth"
        )
    # neutral — soft golden hour
    return (
        "dramatic golden hour side lighting, teal shadows in darker areas, "
        "volumetric atmosphere, editorial light"
    )


# ── Universal quality suffix ─────────────────────────────────────────────────

def _quality_suffix(mood: str) -> str:
    grading = (
        "cinematic teal and amber color grading"
        if mood != "crisis"
        else "cinematic color grading, teal dominant shadows, desaturated amber"
    )
    return (
        f"{grading}, hyper-realistic, editorial photography, subtle film grain, "
        "purely visual scene, no written elements, no user interface, no cartoon, no illustration"
    )


# ── Fallback visual concepts (used when LLM unavailable) ────────────────────
# Structured as {category: {mood: [visual_concepts]}}
# These are REFERENCE EXAMPLES, not templates — LLM generates originals.

_FALLBACK_VISUALS: dict[str, dict[str, list[str]]] = {
    "immigration": {
        "crisis": [
            "hundreds of frustrated tourists densely packed in an overcrowded airport immigration hall, "
            "long snaking queues, harsh fluorescent light, teal shadows, documentary realism",
            "a stern Indonesian immigration officer in full uniform standing arms crossed at airport entrance, "
            "commanding authority, backlit silhouette, teal shadows on uniform",
            "a lone Western man sitting on a metal bench in a stark airport holding area, head down, "
            "two immigration officers nearby, cold institutional light, isolation and consequence",
        ],
        "aspiration": [
            "a hyper-realistic close-up of an Indonesian KITAS permit card on a dark teak desk beside "
            "a Balinese canang sari offering and fresh Bali coffee, warm golden light, teal shadows",
            "a young digital nomad working on a MacBook in a bamboo Bali coworking space, "
            "golden hour light through bamboo walls, striped teal shadows, aspirational and serene",
        ],
        "neutral": [
            "a weathered Western hand sliding a passport across an immigration counter, "
            "stamp mid-air, dramatic side lighting, teal shadows, shallow depth of field",
            "an ornate Balinese temple gate at golden hour, a lone traveler silhouette passing through, "
            "mist and volumetric light, monumental scale",
        ],
    },
    "tax": {
        "crisis": [
            "a chaotic desk covered in scattered Indonesian tax documents, crumpled receipts, "
            "laptop showing a complex government portal, coffee cups, stressed hand gripping a pen, "
            "teal laptop screen glow, golden desk lamp shadows",
            "a crowded Indonesian tax office waiting room, mixed crowd holding numbered tickets, "
            "fluorescent overhead light with one golden beam cutting through, bureaucratic patience",
            "a beautiful golden rope tightening around stacked Rupiah banknotes on dark teak, "
            "dramatic side light, deep teal shadows, tension and consequence",
        ],
        "aspiration": [
            "cascade of gold rupiah coins catching warm sunlight against dark volcanic stone, "
            "macro shot, amber highlights, teal shadows, financial abundance",
        ],
        "neutral": [
            "macro of ancient brass scales tipping, Balinese offering flowers as counterweight, "
            "golden hour light, teal shadows, symbolic balance",
            "dramatic aerial of Bali coastline at dusk with subtle holographic data grid overlay, "
            "temples and villas connected by amber lines, cinematic surveillance metaphor",
        ],
    },
    "company": {
        "crisis": [
            "a stunning modern Bali villa completely abandoned and overgrown with tropical vegetation, "
            "heavy chain on gate, pool turning green, golden sunset creating melancholic amber glow "
            "while teal shadows creep from the jungle, paradise lost",
            "long line of ornate golden dominoes in a spiral on dark polished stone, first domino falling, "
            "each engraved with business symbols, shallow depth of field, chain reaction metaphor",
        ],
        "aspiration": [
            "modern glass conference table in a sleek Bali office with jungle views, legal documents "
            "spread out including company registration papers with government stamps, two hands about "
            "to shake, golden hour light, teal shadows from tropical plants",
            "aerial Canggu district at golden hour, motorbikes creating amber light trails below, "
            "lush jungle pressing in from all sides, entrepreneurial energy",
        ],
        "neutral": [
            "macro of an official Indonesian company stamp pressing into golden wax, dramatic side light, "
            "teal shadows, weight of bureaucracy in one gesture",
        ],
    },
    "property": {
        "crisis": [
            "dramatic aerial looking straight down at dozens of identical white villas with blue pools "
            "arranged in a grid resembling a graveyard, remaining rice paddies squeezed between developments, "
            "flat overcast teal light, haunting repetition",
            "aerial of monotonous rows of identical white modern villas consuming former rice terraces, "
            "construction cranes visible, overcast moody sky, muted teal and desaturated amber, "
            "urban sprawl meets paradise",
        ],
        "aspiration": [
            "stunning luxury Bali villa interior, open-air living room with infinity pool merging into "
            "rice terrace valley, couple relaxing on daybed, golden hour flooding space with amber, "
            "teal shadows in high thatched roof, aspirational warmth",
            "lone clifftop villa above Indian Ocean at sunset, rich terracotta and amber sky, "
            "teal ocean below, epic scale, cinematic grandeur",
        ],
        "neutral": [
            "dramatic drone view of infinity pool villa mirroring a dramatic Bali sky, "
            "golden hour reflection, teal water, cinematic symmetry",
        ],
    },
    "lifestyle": {
        "crisis": [
            "a young Western digital nomad in a Bali coworking space looking worried at phone screen "
            "showing a notification, laptop open, golden hour light through bamboo walls, "
            "subtle tension in paradise, shallow depth of field",
        ],
        "aspiration": [
            "mixed Indonesian-Western family walking hand in hand on Bali black sand beach at golden hour, "
            "children running ahead, warm amber sunset on silhouettes, teal ocean, emotional warmth",
            "focused digital nomad on MacBook in open-air bamboo coworking space, fresh coconut on desk, "
            "golden afternoon light, striped teal shadows, aspirational remote work",
        ],
        "neutral": [
            "lone surfer at Uluwatu cliff edge at golden hour, explosive ocean spray catching amber light, "
            "teal deep water below, monumental scale, cinematic energy",
        ],
    },
    "regulation": {
        "crisis": [
            "impossibly tall tower of stacked Indonesian government forms spiraling upward in a dim room, "
            "single golden beam from skylight down through documents, teal shadows surrounding, "
            "tiny human silhouette at base, Kafkaesque scale",
            "massive golden tsunami wave made entirely of floating government documents and official stamps "
            "crashing toward a small Balinese temple on shore, amber sunset light, teal shadows on temple, "
            "overwhelming regulatory change",
            "computer monitor showing Indonesian government portal with red error message and glitch artifacts, "
            "reflected frustrated face in screen, cold teal-blue screen glow, warm amber desk lamp at edges",
        ],
        "aspiration": [
            "Indonesian government building with glass facade, Indonesian flag flying, golden hour side light "
            "casting long teal shadows, Western businessman approaching entrance with documents, "
            "institutional power meets individual entrepreneur",
        ],
        "neutral": [
            "extreme macro of Indonesian government rubber stamp pressing onto official document, red ink "
            "spreading, Garuda emblem visible, warm amber on wooden handle, teal shadows on paper, "
            "weight of bureaucracy",
            "Indonesian notary in formal attire behind mahogany desk covered in leather-bound legal books, "
            "Western client across, golden window light with striped shadows, institutional authority",
        ],
    },
    "general": {
        "crisis": [
            "monumental golden Buddha statue in a Balinese temple courtyard wrapped and constricted "
            "by massive golden serpents, serene expression contrasting slow suffocation, amber light "
            "from left, deep teal shadows, metaphorical paralysis",
            "dramatic wide shot of a Balinese stone pathway fork at an ancient carved gateway, "
            "one path in warm golden light toward a temple, the other in cold teal shadow into dark jungle, "
            "lone Western figure at the fork, choice and consequence",
        ],
        "aspiration": [
            "aerial Mount Agung at sunrise above a sea of clouds, epic scale, amber light on volcanic peak, "
            "teal atmosphere below, monumental grandeur",
            "golden Garuda Indonesia eagle statue against cinematic storm clouds, "
            "dramatic amber backlight, teal sky, national authority",
        ],
        "neutral": [
            "ornate Balinese temple gate splitting the frame between deep shadow and brilliant sunlight, "
            "single figure passing through, mist and volumetric light",
            "macro of traditional Balinese canang sari offering, rich colors, symbolic geometry, "
            "golden hour side light, shallow depth of field",
        ],
    },
}


def _fallback_visual(category: str, mood: str, title: str) -> str:
    """Pick a fallback visual concept deterministically from title hash."""
    cat = category if category in _FALLBACK_VISUALS else "general"
    concepts = _FALLBACK_VISUALS[cat].get(mood) or _FALLBACK_VISUALS[cat].get("neutral", [])
    if not concepts:
        concepts = _FALLBACK_VISUALS["general"]["neutral"]
    idx = int(hashlib.md5(title.encode()).hexdigest(), 16) % len(concepts)
    return concepts[idx]


# ── LLM system prompt ────────────────────────────────────────────────────────

_VISUAL_DIRECTOR_SYSTEM = """You are the visual director for Bali Zero, an investigative editorial brand in Bali, Indonesia.
Your task: given an article, generate ONE precise Flux image generation prompt for the cover photo.

VISUAL IDENTITY — NON-NEGOTIABLE RULES:
1. Cinematic realism — the image must look like a frame from a Denis Villeneuve or Roger Deakins film.
   Hyper-realistic, editorial photography, subtle film grain. NEVER cartoon, illustration, or 3D render.
2. Teal & amber color grading — ALWAYS include this. It is the Bali Zero signature.
   Teal in shadows, warm amber/gold in highlights and sunlit areas.
3. Images are EMOTIONAL HOOKS, not illustrations. A surveillance article is NOT a camera.
   It is the shadow of a watching eye over a temple. Abstract, symbolic, visceral.
4. Choose ONE of these cameras: ARRI Alexa Mini LF / Hasselblad X2D / RED V-Raptor / DJI Inspire 3 (aerial)
   Choose ONE lens: 24mm wide / 35mm / 50mm f/1.4 / 85mm f/1.4 / 90-120mm macro
5. NEVER include: text, words, logos, watermarks, cartoons, neon, cyberpunk, smiling businesspeople, handshakes.
6. The image must be Bali-rooted: use Balinese temples, rice terraces, beaches, coworking spaces,
   government offices, immigration halls, villas, or markets as locations.
7. Absolute seriousness — even surreal subjects (historical figures in batik) are treated as
   National Geographic editorial portraits. The contrast is conceptual, never visual irony.

MOOD RULES (already determined for you, passed as input):
- aspiration: golden hour light, warm amber, volumetric rays, paradise aesthetic
- crisis: harsh fluorescent OR cold teal dominant, deep shadows, claustrophobic framing,
  surveillance aesthetic, institutional coldness
- neutral: dramatic golden hour with teal shadows, editorial balance

OUTPUT FORMAT:
Return ONLY the image prompt — no explanation, no preamble, no quotes.
The prompt must follow this structure:
[VISUAL SCENE DESCRIPTION], shot on [CAMERA] with [LENS], cinematic teal and amber color grading, [DEPTH OF FIELD], [LIGHT DESCRIPTION], hyper-realistic, editorial photography, film grain

The scene description must be specific and vivid: describe subjects, action, location, exact light direction, composition.
Length: 60-120 words. Dense, specific, no filler."""


def _build_llm_user_prompt(title: str, category: str, summary: str, mood: str) -> str:
    mood_instruction = {
        "aspiration": "MOOD: Aspiration — warm golden paradise aesthetic. Use golden hour, amber sunlight, volumetric rays.",
        "crisis": "MOOD: Crisis/Alert — cold, institutional, threatening. Use harsh fluorescent, cold teal dominant, deep shadows, claustrophobic or surveillance framing.",
        "neutral": "MOOD: Neutral — dramatic editorial. Use golden hour with deep teal shadows, authoritative and cinematic.",
    }[mood]

    return (
        f"Article Title: {title}\n"
        f"Category: {category}\n"
        f"{mood_instruction}\n\n"
        f"Article Summary:\n{summary[:500]}\n\n"
        "Generate the Flux image prompt now. Output ONLY the prompt, nothing else."
    )


# ── Core generation functions ────────────────────────────────────────────────

_IMG_RATE_LIMIT_RE = re.compile(
    r"rate.?limit|too many requests|429|exhausted|quota|hit your limit|"
    r"timeout after 90s|possibly rate limit|capacity|overloaded",
    re.IGNORECASE,
)
_IMG_EXHAUSTED_TOKENS: dict[str, str] = {}


def _load_img_token_chain() -> list[tuple[str, str]]:
    """Load ordered list of (label, oauth_token) for image prompt generation."""
    chain: list[tuple[str, str]] = []
    for i in (1, 2, 3):
        tok = os.environ.get(f"CLAUDE_CODE_OAUTH_TOKEN_{i}", "").strip()
        if tok:
            chain.append((f"token_{i}", tok))
    legacy = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if legacy and not any(t == legacy for _, t in chain):
        chain.append(("token_legacy", legacy))
    chain.append(("keychain", ""))
    return chain


def _prompt_via_claude(title: str, category: str, summary: str, mood: str) -> Optional[str]:
    """Call Claude Haiku via CLI subprocess to generate visual concept.
    Multi-account fallback: tries TOKEN_1→2→3→legacy→keychain.
    Returns the raw prompt string, or None if CLI unavailable/failed."""
    user_msg = _build_llm_user_prompt(title, category, summary, mood)
    combined = f"{_VISUAL_DIRECTOR_SYSTEM}\n\n{user_msg}"
    chain = _load_img_token_chain()

    for label, token in chain:
        if label in _IMG_EXHAUSTED_TOKENS:
            continue

        # Strip ANTHROPIC_API_KEY — claude CLI uses OAuth (Max subscription)
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        if token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = token
        else:
            env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)

        try:
            result = subprocess.run(
                ["claude", "--print", "--model", "claude-haiku-4-5-20251001", combined],
                capture_output=True, text=True, timeout=45, env=env,
            )
        except subprocess.TimeoutExpired:
            print(f"  claude CLI: {label} timeout after 45s", file=sys.stderr)
            _IMG_EXHAUSTED_TOKENS[label] = "timeout"
            continue
        except FileNotFoundError:
            print("  claude CLI: not found in PATH", file=sys.stderr)
            return None
        except Exception as e:
            print(f"  claude CLI: {label} {e}", file=sys.stderr)
            return None

        output_combined = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0 and _IMG_RATE_LIMIT_RE.search(output_combined):
            print(f"  claude CLI: {label} rate-limited — trying next", file=sys.stderr)
            _IMG_EXHAUSTED_TOKENS[label] = "rate_limit"
            continue

        if result.returncode == 0:
            output = result.stdout.strip()
            if output and len(output) > 30:
                return output

        print(f"  claude CLI: {label} rc={result.returncode}", file=sys.stderr)
        return None  # Non-rate-limit error — stop trying

    print("  claude CLI: all tokens exhausted", file=sys.stderr)
    return None


def _assemble_prompt(visual_concept: str, mood: str) -> str:
    """Append the universal quality suffix to a visual concept."""
    return f"{visual_concept}, {_quality_suffix(mood)}"


# ── Public API ───────────────────────────────────────────────────────────────

def build_cover_prompt(
    title: str,
    category: str = "general",
    summary: Optional[str] = None,
    mood: Optional[str] = None,
) -> str:
    """Generate a cinematic Flux image prompt for an intel article cover.

    Args:
        title:    Article headline.
        category: Content category (immigration|tax|company|property|lifestyle|regulation|general).
        summary:  Article summary (~400 chars). Required for LLM-generated prompts.
        mood:     Override mood classification. If None, auto-determined from title+summary.

    Returns:
        A Flux-ready image generation prompt string.
    """
    # 1. Determine mood
    effective_mood = mood or classify_mood(title, summary or "")

    # 2. Try LLM generation (primary path)
    if summary:
        llm_prompt = _prompt_via_claude(title, category, summary, effective_mood)
        if llm_prompt:
            # LLM already follows the formula — append quality suffix only if not already present
            if "hyper-realistic" not in llm_prompt.lower():
                llm_prompt = _assemble_prompt(llm_prompt, effective_mood)
            return llm_prompt

    # 3. Fallback: structured fallback visual + quality suffix
    print(f"  Using fallback visual for [{category}/{effective_mood}]", file=sys.stderr)
    visual = _fallback_visual(category, effective_mood, title)
    return _assemble_prompt(visual, effective_mood)


def build_slide_prompt(
    title: str,
    body: str = "",
    style_hint: str = "",
    mood: Optional[str] = None,
) -> str:
    """Generate a background photo prompt for war room carousel slides.

    Slides use the same visual identity but default to 'general' category.
    """
    effective_mood = mood or classify_mood(title, body)
    hint = f" {style_hint}" if style_hint else ""

    if body:
        llm_prompt = _prompt_via_claude(title, "general", body, effective_mood)
        if llm_prompt:
            if "hyper-realistic" not in llm_prompt.lower():
                llm_prompt = _assemble_prompt(llm_prompt, effective_mood)
            return llm_prompt + hint

    visual = _fallback_visual("general", effective_mood, title)
    return _assemble_prompt(visual, effective_mood) + hint


# ── CLI for standalone testing ───────────────────────────────────────────────

if __name__ == "__main__":
    import json

    test_cases = [
        {
            "title": "Indonesia Launches Surprise Tax Audit on Foreign-Owned Villas",
            "category": "tax",
            "summary": "Indonesian tax authorities have announced unannounced inspections of villas owned by foreigners in Bali, with fines up to 200% of unpaid taxes. Over 3,000 properties are under review.",
        },
        {
            "title": "New Digital Nomad Visa Opens Indonesia to Remote Workers Worldwide",
            "category": "immigration",
            "summary": "Indonesia's E33G digital nomad visa now allows remote workers from 60 countries to live and work legally in Bali for up to 5 years, with no local tax obligations.",
        },
        {
            "title": "Bali Villa Market Splits: Branded Resorts Thrive While Generic Villas Collapse",
            "category": "property",
            "summary": "A new market study shows branded eco-resorts achieving 85% occupancy while generic white-box villas sit at 23%. The polarization is accelerating.",
        },
    ]

    for tc in test_cases:
        mood = classify_mood(tc["title"], tc["summary"])
        print(f"\n{'='*70}")
        print(f"TITLE:    {tc['title']}")
        print(f"CATEGORY: {tc['category']} | MOOD: {mood}")
        print(f"PROMPT:")
        prompt = build_cover_prompt(**tc)
        print(prompt)
