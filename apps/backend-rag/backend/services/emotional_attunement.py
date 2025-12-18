"""
ZANTARA Emotional Attunement Service - Phase 4

Detects emotional state from message content and adapts response tone/style.
Integrates with CollaboratorService for personalized emotional preferences.
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class EmotionalState(str, Enum):
    """Detected emotional states"""

    NEUTRAL = "neutral"
    STRESSED = "stressed"
    EXCITED = "excited"
    CONFUSED = "confused"
    FRUSTRATED = "frustrated"
    CURIOUS = "curious"
    GRATEFUL = "grateful"
    URGENT = "urgent"
    # PRIORITY 4: Added missing states for router integration
    SAD = "sad"
    ANXIOUS = "anxious"
    EMBARRASSED = "embarrassed"
    LONELY = "lonely"
    SCARED = "scared"
    WORRIED = "worried"


class ToneStyle(str, Enum):
    """Response tone styles"""

    PROFESSIONAL = "professional"
    WARM = "warm"
    TECHNICAL = "technical"
    SIMPLE = "simple"
    ENCOURAGING = "encouraging"
    DIRECT = "direct"


@dataclass
class EmotionalProfile:
    """Emotional analysis result"""

    detected_state: EmotionalState
    confidence: float  # 0.0 - 1.0
    suggested_tone: ToneStyle
    reasoning: str
    detected_indicators: list[str]


class EmotionalAttunementService:
    """
    Analyzes message content to detect emotional state and suggest appropriate tone.

    Features:
    - Pattern-based emotion detection
    - Keyword analysis
    - Punctuation and capitalization analysis
    - Integration with collaborator preferences
    - Tone adaptation suggestions
    """

    # Emotional indicator patterns
    EMOTION_PATTERNS = {
        EmotionalState.STRESSED: {
            "keywords": [
                "urgent",
                "asap",
                "emergency",
                "help",
                "problem",
                "issue",
                "stuck",
                "broken",
            ],
            "patterns": [r"!!+", r"\?\?+", r"please.*urgent", r"need.*asap"],
            "caps_threshold": 0.3,  # 30% caps = stressed
        },
        EmotionalState.EXCITED: {
            "keywords": [
                "amazing",
                "awesome",
                "fantastic",
                "great",
                "love",
                "perfect",
                "excellent",
            ],
            "patterns": [r"!+", r"wow", r"omg", r"yes+"],
            "caps_threshold": 0.2,
        },
        EmotionalState.CONFUSED: {
            "keywords": ["confused", "don't understand", "unclear", "not sure", "don't get"],
            "patterns": [r"\?\s+\?", r"what.*mean", r"how does.*work"],
            "caps_threshold": 0.0,
        },
        EmotionalState.FRUSTRATED: {
            "keywords": ["frustrated", "annoyed", "tired", "again", "still not", "why won't"],
            "patterns": [r"ugh", r"seriously", r"come on", r"really\?"],
            "caps_threshold": 0.25,
        },
        EmotionalState.CURIOUS: {
            "keywords": ["curious", "wondering", "interested", "technical", "implementation"],
            "patterns": [r"what if", r"how about", r"could you.*explain", r"curious about"],
            "caps_threshold": 0.0,
        },
        EmotionalState.GRATEFUL: {
            "keywords": ["thank", "thanks", "appreciate", "grateful", "helpful"],
            "patterns": [r"thank you", r"thanks+"],
            "caps_threshold": 0.0,
        },
        EmotionalState.URGENT: {
            "keywords": ["now", "immediately", "critical", "asap", "urgent"],
            "patterns": [r"right now", r"as soon as", r"immediately"],
            "caps_threshold": 0.4,
        },
        # PRIORITY 4: Added patterns for missing emotional states
        EmotionalState.SAD: {
            "keywords": ["sad", "depressed", "down", "unhappy", "triste", "sedih", "giù"],
            "patterns": [r"feel.*sad", r"i'm.*sad", r"sono.*triste", r"aku.*sedih"],
            "caps_threshold": 0.0,
        },
        EmotionalState.ANXIOUS: {
            "keywords": [
                "anxious",
                "worried",
                "nervous",
                "scared",
                "afraid",
                "ansioso",
                "khawatir",
                "preoccupato",
            ],
            "patterns": [
                r"feel.*anxious",
                r"i'm.*worried",
                r"sono.*preoccupato",
                r"saya.*khawatir",
            ],
            "caps_threshold": 0.1,
        },
        EmotionalState.EMBARRASSED: {
            "keywords": ["embarrassed", "ashamed", "shy", "awkward", "imbarazzato", "malu"],
            "patterns": [
                r"feel.*embarrassed",
                r"i'm.*embarrassed",
                r"sono.*imbarazzato",
                r"aku.*malu",
            ],
            "caps_threshold": 0.0,
        },
        EmotionalState.LONELY: {
            "keywords": ["lonely", "alone", "isolated", "solo", "kesepian", "sendirian"],
            "patterns": [r"feel.*lonely", r"i'm.*alone", r"mi.*sento.*solo", r"aku.*kesepian"],
            "caps_threshold": 0.0,
        },
        EmotionalState.SCARED: {
            "keywords": ["scared", "frightened", "terrified", "afraid", "paura", "takut"],
            "patterns": [r"i'm.*scared", r"i'm.*afraid", r"ho.*paura", r"aku.*takut"],
            "caps_threshold": 0.2,
        },
        EmotionalState.WORRIED: {
            "keywords": ["worried", "concern", "anxious", "trouble", "preoccupato", "khawatir"],
            "patterns": [
                r"worried about",
                r"concerned about",
                r"preoccupato per",
                r"khawatir tentang",
            ],
            "caps_threshold": 0.1,
        },
    }

    # Tone suggestions based on emotional state
    STATE_TO_TONE = {
        EmotionalState.STRESSED: ToneStyle.ENCOURAGING,
        EmotionalState.EXCITED: ToneStyle.WARM,
        EmotionalState.CONFUSED: ToneStyle.SIMPLE,
        EmotionalState.FRUSTRATED: ToneStyle.DIRECT,
        EmotionalState.CURIOUS: ToneStyle.TECHNICAL,
        EmotionalState.GRATEFUL: ToneStyle.WARM,
        EmotionalState.URGENT: ToneStyle.DIRECT,
        EmotionalState.NEUTRAL: ToneStyle.PROFESSIONAL,
        # PRIORITY 4: Tone mappings for new states (empathetic responses)
        EmotionalState.SAD: ToneStyle.WARM,
        EmotionalState.ANXIOUS: ToneStyle.ENCOURAGING,
        EmotionalState.EMBARRASSED: ToneStyle.WARM,
        EmotionalState.LONELY: ToneStyle.WARM,
        EmotionalState.SCARED: ToneStyle.ENCOURAGING,
        EmotionalState.WORRIED: ToneStyle.ENCOURAGING,
    }

    # Tone style prompts (to be injected into system prompt)
    TONE_PROMPTS = {
        ToneStyle.PROFESSIONAL: "Maintain a professional, balanced tone. Be clear and concise.",
        ToneStyle.WARM: "Use a warm, friendly tone. Show empathy and encouragement.",
        ToneStyle.TECHNICAL: "Provide detailed technical explanations. Use precise terminology.",
        ToneStyle.SIMPLE: "Explain in simple terms. Break down complex concepts step by step.",
        ToneStyle.ENCOURAGING: "Be reassuring and supportive. Acknowledge the challenge and offer clear next steps.",
        ToneStyle.DIRECT: "Be direct and action-oriented. Focus on solutions, not explanations.",
    }

    def __init__(self):
        logger.info("✅ EmotionalAttunementService initialized")

    def analyze_message(
        self, message: str, collaborator_preferences: dict | None = None
    ) -> EmotionalProfile:
        """
        Analyze message to detect emotional state.

        Args:
            message: User message text
            collaborator_preferences: Optional dict with emotional_preferences

        Returns:
            EmotionalProfile with detected state and tone suggestion
        """
        message_lower = message.lower()
        detected_indicators = []
        scores = dict.fromkeys(EmotionalState, 0.0)

        # 1. Check keyword matches
        for state, config in self.EMOTION_PATTERNS.items():
            for keyword in config["keywords"]:
                if keyword in message_lower:
                    scores[state] += 1.0
                    detected_indicators.append(f"keyword:{keyword}")

        # 2. Check regex patterns
        for state, config in self.EMOTION_PATTERNS.items():
            for pattern in config["patterns"]:
                if re.search(pattern, message_lower):
                    scores[state] += 1.5  # Patterns weigh more
                    detected_indicators.append(f"pattern:{pattern}")

        # 3. Check capitalization (stress indicator)
        caps_ratio = (
            sum(1 for c in message if c.isupper()) / len(message) if len(message) > 0 else 0
        )
        for state, config in self.EMOTION_PATTERNS.items():
            if caps_ratio >= config.get("caps_threshold", 0):
                scores[state] += caps_ratio * 2.0
                if caps_ratio > 0.2:
                    detected_indicators.append(f"caps:{caps_ratio:.2f}")

        # 4. Check punctuation intensity
        exclamations = message.count("!")
        questions = message.count("?")
        if exclamations >= 2:
            scores[EmotionalState.EXCITED] += exclamations * 0.5
            scores[EmotionalState.STRESSED] += exclamations * 0.3
            detected_indicators.append(f"exclamations:{exclamations}")
        if questions >= 2:
            scores[EmotionalState.CONFUSED] += questions * 0.5
            detected_indicators.append(f"questions:{questions}")

        # 5. Determine dominant state
        if max(scores.values()) == 0:
            detected_state = EmotionalState.NEUTRAL
            confidence = 1.0
            reasoning = "No strong emotional indicators detected"
        else:
            detected_state = max(scores, key=scores.get)
            max_score = scores[detected_state]
            total_score = sum(scores.values())
            confidence = min(max_score / (total_score + 1e-6), 1.0)

            # If confidence too low, default to neutral
            if confidence < 0.5:
                detected_state = EmotionalState.NEUTRAL
                confidence = 1.0
                reasoning = "Weak emotional indicators, defaulting to neutral"
            else:
                reasoning = (
                    f"Detected via {len(detected_indicators)} indicators (score: {max_score:.1f})"
                )

        # 6. Apply collaborator preferences (override if strong preference)
        suggested_tone = self.STATE_TO_TONE[detected_state]
        if collaborator_preferences:
            pref_tone = collaborator_preferences.get("preferred_tone")
            pref_formality = collaborator_preferences.get("formality", "balanced")

            # Override tone based on preferences
            if pref_formality == "formal":
                suggested_tone = ToneStyle.PROFESSIONAL
            elif pref_formality == "casual" and detected_state == EmotionalState.NEUTRAL:
                suggested_tone = ToneStyle.WARM

            if pref_tone:
                # Direct tone preference override
                try:
                    suggested_tone = ToneStyle(pref_tone)
                    reasoning += f" | Preference override: {pref_tone}"
                except ValueError:
                    pass

        logger.info(
            f"🎭 Emotional Analysis: {detected_state.value} "
            f"(conf: {confidence:.2f}) → Tone: {suggested_tone.value}"
        )

        return EmotionalProfile(
            detected_state=detected_state,
            confidence=confidence,
            suggested_tone=suggested_tone,
            reasoning=reasoning,
            detected_indicators=detected_indicators,
        )

    def get_tone_prompt(self, tone_style: ToneStyle) -> str:
        """Get tone adaptation prompt for system prompt injection"""
        return self.TONE_PROMPTS.get(tone_style, self.TONE_PROMPTS[ToneStyle.PROFESSIONAL])

    def build_enhanced_system_prompt(
        self,
        base_prompt: str,
        emotional_profile: EmotionalProfile,
        collaborator_name: str | None = None,
    ) -> str:
        """
        Build enhanced system prompt with emotional attunement.

        Args:
            base_prompt: Original system prompt
            emotional_profile: Detected emotional state
            collaborator_name: Optional collaborator name for personalization

        Returns:
            Enhanced system prompt with tone adaptation
        """
        tone_instruction = self.get_tone_prompt(emotional_profile.suggested_tone)

        emotional_context = "\n\n--- EMOTIONAL ATTUNEMENT ---\n"

        if collaborator_name:
            emotional_context += f"User: {collaborator_name}\n"

        emotional_context += f"Detected State: {emotional_profile.detected_state.value.title()}\n"
        emotional_context += f"Suggested Tone: {emotional_profile.suggested_tone.value.title()}\n"
        emotional_context += f"Tone Guidance: {tone_instruction}\n"

        # Add specific state-based guidance
        if emotional_profile.detected_state == EmotionalState.STRESSED:
            emotional_context += "\nNote: User appears stressed. Be extra clear, reassuring, and provide actionable next steps.\n"
        elif emotional_profile.detected_state == EmotionalState.CONFUSED:
            emotional_context += "\nNote: User appears confused. Break down your explanation into simple steps. Avoid jargon.\n"
        elif emotional_profile.detected_state == EmotionalState.URGENT:
            emotional_context += (
                "\nNote: User has urgent need. Be direct and solution-focused. Skip preamble.\n"
            )
        # PRIORITY 4: Guidance for empathetic emotional states
        elif emotional_profile.detected_state == EmotionalState.SAD:
            emotional_context += "\nNote: User appears sad. Show warmth, empathy, and gentle support. Avoid being overly cheerful.\n"
        elif emotional_profile.detected_state == EmotionalState.ANXIOUS:
            emotional_context += "\nNote: User appears anxious. Be calm, reassuring, and provide clear structure. Break down overwhelming tasks.\n"
        elif emotional_profile.detected_state == EmotionalState.EMBARRASSED:
            emotional_context += "\nNote: User appears embarrassed. Be tactful, non-judgmental, and normalize their concerns.\n"
        elif emotional_profile.detected_state == EmotionalState.LONELY:
            emotional_context += "\nNote: User appears lonely. Be warm, present, and engage meaningfully. Show genuine interest.\n"
        elif emotional_profile.detected_state == EmotionalState.SCARED:
            emotional_context += "\nNote: User appears scared. Be gentle, reassuring, and provide safety. Address fears directly but kindly.\n"
        elif emotional_profile.detected_state == EmotionalState.WORRIED:
            emotional_context += "\nNote: User appears worried. Be supportive, practical, and help organize their concerns into manageable steps.\n"

        return base_prompt + emotional_context

    def get_stats(self) -> dict:
        """Get service statistics"""
        return {
            "supported_states": len(EmotionalState),
            "supported_tones": len(ToneStyle),
            "emotion_patterns": len(self.EMOTION_PATTERNS),
            "states": [s.value for s in EmotionalState],
            "tones": [t.value for t in ToneStyle],
        }
