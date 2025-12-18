import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    original: str
    validated: str
    violations: list[str]
    was_modified: bool


class ZantaraResponseValidator:
    """
    Validates and corrects LLM output to ensure Zantara identity consistency.
    This is the last line of defense against model quirks.
    """

    FILLER_PATTERNS = [
        r"^(Certainly|Absolutely|Of course|Sure|Great question)[!,.]?\s*",
        r"^I('d| would) (be happy|love|be glad) to\s+",
        r"^Let me (help|explain|break)[^.]*\.\s*",
        r"^(Grazie per la domanda|Ottima domanda)[!.]?\s*",
        r"^(Here's what|What) you need to know[:.]\s*",
        r"^As an AI language model,?\s*",
    ]

    def __init__(self, mode_config: dict, dry_run: bool = True):
        self.config = mode_config
        self.dry_run = dry_run
        self.violations = []

    def validate(self, response: str, context: Any) -> ValidationResult:
        original = response
        validated = response
        self.violations = []  # Reset violations for each validation call

        # Get mode specific config
        # Assuming self.config is the full yaml loaded
        mode_name = context.mode
        mode_config = self.config.get("modes", {}).get(mode_name, {})

        # 1. Remove filler openings
        validated = self._remove_fillers(validated)

        # 2. Enforce length limits
        validated = self._enforce_length(validated, mode_config)

        # 3. Ensure hook if required
        validated = self._ensure_hook(validated, mode_config)

        # 4. Clean formatting artifacts
        validated = self._clean_artifacts(validated)

        was_modified = original != validated

        if self.dry_run and was_modified:
            logger.info(
                f"🔍 [Validator Dry-Run] Would modify response. Violations: {self.violations}"
            )
            # In dry run, return original but report violations
            return ValidationResult(
                original=original,
                validated=original,
                violations=self.violations,
                was_modified=False,
            )

        return ValidationResult(
            original=original,
            validated=validated.strip(),
            violations=self.violations,
            was_modified=was_modified,
        )

    def _remove_fillers(self, text: str) -> str:
        for pattern in self.FILLER_PATTERNS:
            if re.match(pattern, text, re.IGNORECASE):
                self.violations.append(f"Filler detected: {pattern}")
                text = re.sub(pattern, "", text, flags=re.IGNORECASE)
        return text

    def _enforce_length(self, text: str, mode_config: dict) -> str:
        max_sentences = mode_config.get("max_sentences")
        if not max_sentences:
            return text

        # Split by sentence endings (basic approximation)
        # Look for . ! ? followed by space or end of string
        sentences = re.split(r"(?<=[.!?])\s+", text)

        if len(sentences) > max_sentences:
            self.violations.append(f"Length exceeded: {len(sentences)} > {max_sentences} sentences")
            text = " ".join(sentences[:max_sentences])

            # Ensure ends properly
            if not text.rstrip().endswith((".", "!", "?")):
                text = text.rstrip() + "."

        return text

    def _ensure_hook(self, text: str, mode_config: dict) -> str:
        if not mode_config.get("include_hook"):
            return text

        # Check if ends with question or call to action
        has_hook = text.rstrip().endswith("?") or any(
            cta in text.lower()[-100:]
            for cta in [
                "vuoi",
                "want",
                "need",
                "posso",
                "can i",
                "shall",
                "dimmi",
                "tell me",
                "let me know",
                "fammi sapere",
            ]
        )

        if not has_hook:
            self.violations.append("Missing hook")
            # Don't add generic hook automatically yet - too risky

        return text

    def _clean_artifacts(self, text: str) -> str:
        # Remove common LLM artifacts
        artifacts = [
            (r"\[Source:.*?\]", ""),  # Remove explicit source brackets
            (r"\*\*\*+", ""),  # Remove excessive asterisks
            (r"\n{3,}", "\n\n"),  # Normalize newlines
        ]

        for pattern, replacement in artifacts:
            if re.search(pattern, text):
                self.violations.append(f"Artifact detected: {pattern}")
                text = re.sub(pattern, replacement, text)

        return text
