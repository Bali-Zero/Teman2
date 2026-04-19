"""Prompt templates — 7 tonal registers + Council rounds.

Registers (§3.5): rituale · analitico · ironico · militante · pedagogico · poetico · tecnico
Ciascun registro è un OVERLAY sopra la voce SSOT zantara_core.py (proiettata
come vincolo "questa voce è Zantara/Bali Zero"); il registro dice COME Zantara
parla per questo specifico pezzo editoriale.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.services.war_room.models import RegisterTone


@dataclass(frozen=True)
class RegisterDefinition:
    tone: RegisterTone
    voice: str
    when_to_use: str
    platforms: tuple[str, ...]
    example_headline: str
    example_opening: str
    anti_pattern: str

    @property
    def name(self) -> str:
        return self.tone.value

    def as_prompt_block(self) -> str:
        """Render a deterministic block used both for proponent prompts and judge context."""
        return (
            f"REGISTRO: {self.name}\n"
            f"VOCE: {self.voice}\n"
            f"QUANDO USARE: {self.when_to_use}\n"
            f"PIATTAFORME: {', '.join(self.platforms)}\n"
            f"ESEMPIO HEADLINE (per topic B211A): {self.example_headline}\n"
            f"ESEMPIO OPENING: {self.example_opening}\n"
            f"ANTI-PATTERN: {self.anti_pattern}"
        )


REGISTER_PROMPTS: dict[RegisterTone, RegisterDefinition] = {
    RegisterTone.RITUALE: RegisterDefinition(
        tone=RegisterTone.RITUALE,
        voice=(
            "solenne, ciclica; richiami a passaggi d'anno, calendari, riti di transito; "
            "lessico latino-giuridico; tempi lunghi"
        ),
        when_to_use=(
            "scadenze annuali (LKPM, tax year), cambi di regime, ricorrenze normative, "
            "chiusure d'anno"
        ),
        platforms=("newsletter", "linkedin_long", "blog"),
        example_headline="Il sesto mese del B211A. Una liturgia della proroga.",
        example_opening=(
            "C'è un'ora precisa in cui il visto smette di essere documento e "
            "diventa promessa scaduta."
        ),
        anti_pattern="hashtag di tendenza, clickbait temporale, emoji",
    ),
    RegisterTone.ANALITICO: RegisterDefinition(
        tone=RegisterTone.ANALITICO,
        voice=(
            "neutrale, dati prima delle opinioni, periodi lunghi ma senza enfasi, "
            "citazioni numeriche"
        ),
        when_to_use=(
            "contenuti dove il dato fa il lavoro (tassi LKPM, cifre KITAS, % PMA)"
        ),
        platforms=("linkedin", "blog", "newsletter"),
        example_headline="B211A: 60 giorni + 60 + 60. Cosa cambia oltre la terza proroga.",
        example_opening=(
            "Nel 2025 Imigrasi ha registrato 847.312 estensioni B211A. "
            "Solo il 4% arriva al quarto rinnovo."
        ),
        anti_pattern='aggettivi enfatici, giudizi morali, "incredibile", "scioccante"',
    ),
    RegisterTone.IRONICO: RegisterDefinition(
        tone=RegisterTone.IRONICO,
        voice="sottile, punge senza urlare, comic timing alto, detour narrativi",
        when_to_use=(
            "situazioni assurde del sistema (Coretax, contraddizioni regolatorie)"
        ),
        platforms=("instagram", "x"),
        example_headline="B211A: come pagare tre volte per restare turista.",
        example_opening=(
            "Il B211A è un capolavoro di sintassi burocratica: dichiari di non "
            "lavorare mentre lavori per non farlo dire."
        ),
        anti_pattern="sarcasmo amaro, cinismo, offesa al lettore",
    ),
    RegisterTone.MILITANTE: RegisterDefinition(
        tone=RegisterTone.MILITANTE,
        voice=(
            'diretta, performativa, breve, "io/voi", chiamate all\'azione'
        ),
        when_to_use=(
            "denuncia di pratiche predatorie (agenti abusivi, truffe), "
            "difesa di diritti di compliance"
        ),
        platforms=("instagram_reel_copy", "x_short", "linkedin_opinion"),
        example_headline=(
            "Ti hanno detto che il B211A è 'quasi come un KITAS'. Ti hanno mentito."
        ),
        example_opening=(
            "Ogni anno, 14.000 stranieri scoprono troppo tardi cosa non dice il B211A."
        ),
        anti_pattern=(
            '"quello che non ti dicono" (banlist §6), vittimismo, populismo fiscale'
        ),
    ),
    RegisterTone.PEDAGOGICO: RegisterDefinition(
        tone=RegisterTone.PEDAGOGICO,
        voice="paziente, strutturata, una nozione per frase, zero gergo non spiegato",
        when_to_use=(
            "contenuti didattici, onboarding, chiarimenti post-legislativi"
        ),
        platforms=("blog", "newsletter", "instagram_educational"),
        example_headline=(
            "B211A spiegato semplice: il visto turistico che si allunga fino a 180 giorni."
        ),
        example_opening=(
            "Il B211A è un visto di singolo ingresso. Questo significa tre cose."
        ),
        anti_pattern='condiscendenza, "è facile!", emoji didattiche eccessive',
    ),
    RegisterTone.POETICO: RegisterDefinition(
        tone=RegisterTone.POETICO,
        voice="immagini concrete, ritmo, sottrazione; mai astrazioni vaghe",
        when_to_use=(
            "pezzi longform atmosferici, aperture newsletter, brani di chiusura anno"
        ),
        platforms=("newsletter", "blog"),
        example_headline="B211A: il visto che dura quanto una stagione secca.",
        example_opening=(
            "A Ngurah Rai, tra l'aprile e l'ottobre, passano più estensioni che monsoni."
        ),
        anti_pattern='metafore banali, "come diceva il poeta", vaghezza',
    ),
    RegisterTone.TECNICO: RegisterDefinition(
        tone=RegisterTone.TECNICO,
        voice=(
            "precisa, riferimenti normativi esatti (legge, articolo, anno), "
            "termini indonesiani non tradotti, codici KBLI/visa integrali"
        ),
        when_to_use=(
            "aggiornamenti Peraturan, articoli deep-dive per professionisti"
        ),
        platforms=("linkedin_long", "blog"),
        example_headline=(
            "Permenkumham 22/2023 art. 51: le tre condizioni per la quarta "
            "proroga del B211A."
        ),
        example_opening=(
            "Il Permenkumham 22/2023, all'articolo 51 comma 3, introduce "
            "una soglia operativa che molti operatori interpretano male."
        ),
        anti_pattern="semplificazione, tono pedagogico, abbreviazioni informali",
    ),
}


# ── Banlist (enforcement in Validator M6 + referenced by judge) ───────

CLICKBAIT_BANLIST: tuple[str, ...] = (
    # formule italiane vietate
    "quello che non ti dicono",
    "nessuno ti dice",
    "ecco perché",
    "la verità su",
    "la cosa più importante",
    "svelato",
    "attenzione a",
    "devi sapere",
    "numero 3 ti stupirà",
    # metafore angoscianti (cicatrice War Room v1)
    "trap",
    "trappola",
    "kill-switch",
    "kill switch",
    "death clock",
    "countdown",
    "ghost",
    "ghosted",
    "your next move",
    "la tua prossima mossa",
    "game over",
    "don't be caught",
    "non farti cogliere",
)


# ── Council round prompts ────────────────────────────────────────────


_ROUND_0_PROPOSE_TEMPLATE = """Sei un proponente del Consiglio di Bali Zero.
Persona: {persona}

Brief editoriale:
- Topic: {topic}
- Ricerca (fonti + fatti): {research_json}
- Brand vincoli: {brand_constraints}

Registri disponibili (scegline UNO):
{registers_block}

Ultimo rapporto del tuo stesso modello (riflessione episodica, può essere vuoto):
{self_reflection}

COMPITO: scegli il registro più adatto a questo brief editoriale e rispondi
SOLO con JSON strict:

{{
  "register": "uno tra: rituale|analitico|ironico|militante|pedagogico|poetico|tecnico",
  "rationale": "2-4 righe spiegando perché QUESTO registro per QUESTO brief",
  "risk": "1-2 righe sul rischio specifico (deriva tonale, rigetto pubblico, banalizzazione)",
  "example_headline": "la tua proposta di headline in italiano, max 12 parole"
}}
"""


_ROUND_1_CHALLENGE_TEMPLATE = """Sei ancora il proponente del Consiglio.
Persona: {persona}

Ecco le TRE proposte del Round 0 (inclusa la tua):
{all_proposals_json}

COMPITO: (a) scegli la migliore fra le DUE proposte NON tue, con motivazione.
(b) stronca la PEGGIORE fra le tre con una critica argomentata.

Rispondi SOLO con JSON:

{{
  "best_not_mine": {{
    "author": "claude|gemini|deepseek",
    "motivation": "2-3 righe"
  }},
  "worst": {{
    "author": "claude|gemini|deepseek",
    "critique": "2-3 righe, niente insulti"
  }}
}}
"""


_ROUND_2_JUDGE_TEMPLATE = """Sei il giudice del Consiglio (Claude Sonnet).
Autorità: massima. Veto concesso.

Contesto:
- Brief: {topic}
- Brand: {brand_constraints}
- Banlist: {banlist}

Storico ultimi 14 giorni (registri usati):
{registers_last_14d}

Cicatrici recenti (scar ultimi 14gg — tono/formula da evitare):
{recent_scars}

Proposte Round 0:
{all_proposals_json}

Dissensi Round 1 (chi ha scelto chi come migliore, chi ha stroncato):
{challenges_json}

HARD RULES:
- Max 3 post dello stesso registro negli ultimi 7 giorni.
- Max 3 "ironico" o "militante" in 7 giorni (prevenzione deriva comico/cinica).
- Se concordanza Round 0 > 90%, DEVI cercare una falla; se non la trovi,
  scegli un registro DIVERSO dal più frequente ultimi 7gg.

COMPITO: scegli il registro finale.

Rispondi SOLO con JSON:

{{
  "chosen_register": "rituale|analitico|ironico|militante|pedagogico|poetico|tecnico",
  "rationale": "3-5 righe (cita i dati storici e le proposte che hai pesato)",
  "rejected_registers": ["..."],
  "hard_rules_triggered": ["..."],
  "groupthink_detected": true|false
}}
"""


PROPONENT_PERSONAS: dict[str, str] = {
    "claude": "critico editoriale, economista comportamentale, stile Wired Italia",
    "gemini": "linguista pragmatico, studio retorica politica italiana contemporanea",
    "deepseek": "narratologo, studioso di mitopoiesi ed escatologia",
}


def render_round_0_prompt(
    proponent: str,
    topic: str,
    research_json: str,
    brand_constraints: str,
    self_reflection: str = "",
) -> str:
    persona = PROPONENT_PERSONAS.get(proponent, proponent)
    registers_block = "\n\n".join(
        reg.as_prompt_block() for reg in REGISTER_PROMPTS.values()
    )
    return _ROUND_0_PROPOSE_TEMPLATE.format(
        persona=persona,
        topic=topic,
        research_json=research_json or "{}",
        brand_constraints=brand_constraints or "(vedi brand.json)",
        registers_block=registers_block,
        self_reflection=self_reflection or "(nessuna riflessione precedente)",
    )


def render_round_1_prompt(
    proponent: str,
    all_proposals_json: str,
) -> str:
    persona = PROPONENT_PERSONAS.get(proponent, proponent)
    return _ROUND_1_CHALLENGE_TEMPLATE.format(
        persona=persona,
        all_proposals_json=all_proposals_json,
    )


def render_round_2_judge_prompt(
    topic: str,
    brand_constraints: str,
    registers_last_14d: str,
    recent_scars: str,
    all_proposals_json: str,
    challenges_json: str,
) -> str:
    return _ROUND_2_JUDGE_TEMPLATE.format(
        topic=topic,
        brand_constraints=brand_constraints or "(vedi brand.json)",
        banlist=", ".join(f'"{k}"' for k in CLICKBAIT_BANLIST),
        registers_last_14d=registers_last_14d or "(nessun post registrato)",
        recent_scars=recent_scars or "(nessuna cicatrice recente)",
        all_proposals_json=all_proposals_json,
        challenges_json=challenges_json,
    )
