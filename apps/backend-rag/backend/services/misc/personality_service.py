"""
ZANTARA Multi-Personality Service

Gestisce le diverse personalità dell'AI system:
- Jaksel: Indonesian slang (Amanda, Anton, Krisna, Dea, etc.)
- ZERO: Italian style (Zero, Nina)
- Professional: Standard English/Indonesian
- Custom: Basato sulle preferenze del team member

Integra Gemini 1.5 (RAG research) + Zantara Oracle Cloud (personality voice)
"""

import logging
import os

# Note: Google services will be injected to avoid circular imports
# Team members database
import sys
from pathlib import Path
from typing import Any

import aiohttp

sys.path.append(str(Path(__file__).parent.parent))
from data.team_members import TEAM_MEMBERS

logger = logging.getLogger(__name__)


class PersonalityService:
    """
    Servizio che gestisce le diverse personalità di ZANTARA
    basandosi sul team member che interagisce
    """

    def __init__(self):
        # Usa il nostro modello Zantara su Oracle Cloud
        self.zantara_oracle_url = os.getenv(
            "ZANTARA_ORACLE_URL", "https://zantara.oracle.cloud/api/generate"
        )
        self.oracle_api_key = os.getenv("ORACLE_API_KEY", "")
        self.team_members = TEAM_MEMBERS
        self.personality_profiles = self._build_personality_profiles()

        logger.info("✅ PersonalityService initialized")
        logger.info(f"   Zantara Oracle URL: {self.zantara_oracle_url}")
        logger.info(f"   Oracle API Key: {'✅ Set' if self.oracle_api_key else '⚠️ Not set'}")
        logger.info(f"   Team members loaded: {len(self.team_members)}")
        logger.info(f"   Personality profiles: {len(self.personality_profiles)}")

    def _build_personality_profiles(self) -> dict[str, dict]:
        """Costruisce i profili di personalità basati sui team members"""

        profiles = {}

        # JAKSEL PERSONALITY (Indonesian slang users)
        jaksel_members = [
            "amanda",
            "anton",
            "krisna",
            "adi",
            "ari",
            "dea",
            "vino",
            "surya",
            "damar",
            "veronika",
            "angel",
            "kadek",
            "dewaayu",
            "faisha",
            "rina",
            "sahira",
        ]

        profiles["jaksel"] = {
            "name": "Zantara Jaksel",
            "language": "id",
            "style": "bahasa_jaksel",
            "system_prompt": """You are Zantara, but you MUST speak in Bahasa Jaksel (Indonesian slang heavily mixed with English terms).

RULES:
- Use "kayak", "gitu", "dong", "banget", "cuy" frequently
- Mix English terms like "basically", "literally", "which is", "prefer"
- Talk like Jakarta kids: casual, trendy, a bit playful
- Keep it professional but cool - like a smart friend who knows the law
- Use "Kak" for users, "gue" for yourself
- ALWAYS mix Indonesian and English naturally

Examples:
- "Contract itu basically kayak perjanjian gitu loh"
- "Jadi gue jelasin yang detail ya, biar paham banget"
- "Literally, prosesnya memang agak ribet sih"

Be helpful but speak in authentic Jaksel style!""",
            "team_members": jaksel_members,
            "traits": ["friendly", "trendy", "knowledgeable", "helpful"],
        }

        # ZERO PERSONALITY (Italian style)
        zero_members = ["zero", "nina"]

        profiles["zero"] = {
            "name": "Zantara ZERO",
            "language": "it",
            "style": "italian_depth",
            "system_prompt": """You are Zantara ZERO, speaking Italian with depth and clarity.

STYLE:
- Direct but profound communication
- Mix Italian precision with strategic insight
- Use "praticamente", "essenzialmente", "letteralmente" when appropriate
- Maintain professional but personal tone
- Be analytical but approachable
- Reference legal/business concepts with confidence

Examples:
- "Praticamente, il contratto è un vincolo giuridico..."
- "Essenzialmente, devi considerare questi aspetti..."
- "Letteralmente, stiamo parlando di protezione legale"

Be the trusted Italian advisor who combines expertise with human understanding.""",
            "team_members": zero_members,
            "traits": ["strategic", "direct", "deep", "analytical"],
        }

        # PROFESSIONAL PERSONALITY (Standard multilingual)
        professional_members = ["zainal", "ruslana", "olena", "marta"]

        profiles["professional"] = {
            "name": "Zantara Professional",
            "language": "en",
            "style": "professional_multilingual",
            "system_prompt": """You are Zantara Professional, speaking in clear, professional language.

STYLE:
- Professional and articulate
- Match user's language (EN/ID/IT/UA) naturally
- Clear, structured communication
- Authoritative but approachable
- Precise legal and business terminology
- Helpful and comprehensive

Be the expert consultant who provides reliable professional guidance.""",
            "team_members": professional_members,
            "traits": ["professional", "reliable", "knowledgeable", "structured"],
        }

        return profiles

    def get_user_personality(self, user_email: str) -> dict[str, Any]:
        """
        Determina la personalità da usare basata sull'utente

        Args:
            user_email: Email dell'utente

        Returns:
            Dict con profilo personalità e user info
        """
        # Find team member
        team_member = None
        for member in self.team_members:
            if member["email"].lower() == user_email.lower():
                team_member = member
                break

        if not team_member:
            # Default to professional for unknown users
            return {
                "personality_type": "professional",
                "personality": self.personality_profiles["professional"],
                "user": {"email": user_email, "name": "Guest"},
            }

        # Determine personality type based on team member
        user_id = team_member["id"]

        if user_id in self.personality_profiles["jaksel"]["team_members"]:
            personality_type = "jaksel"
        elif user_id in self.personality_profiles["zero"]["team_members"]:
            personality_type = "zero"
        else:
            personality_type = "professional"

        return {
            "personality_type": personality_type,
            "personality": self.personality_profiles[personality_type],
            "user": team_member,
        }

    async def translate_to_personality(
        self, gemini_response: str, user_email: str, original_query: str
    ) -> dict[str, Any]:
        """
        Traduce la risposta di Gemini nella personalità appropriata

        Args:
            gemini_response: Risposta da Gemini 1.5 dopo RAG
            user_email: Email dell'utente
            original_query: Query originale dell'utente

        Returns:
            Dict con risposta personalizzata e metadata
        """
        try:
            # Get user personality
            user_context = self.get_user_personality(user_email)
            personality = user_context["personality"]
            user = user_context["user"]

            logger.info(f"🎭 Applying {personality['name']} personality for {user['name']}")

            # Build prompt for Zantara local model
            zantara_prompt = f"""{personality["system_prompt"]}

USER QUERY: {original_query}

PROFESSIONAL ANSWER: {gemini_response}

TASK: Rewrite this professional answer in your personality style. Keep all the accurate information but make it sound naturally like you. Be helpful and maintain the legal accuracy.

Your response:"""

            # Call Zantara model on Oracle Cloud
            headers = {}
            if self.oracle_api_key:
                headers["Authorization"] = f"Bearer {self.oracle_api_key}"

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    self.zantara_oracle_url,
                    json={"model": "zantara", "prompt": zantara_prompt, "stream": False},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response,
            ):
                if response.status == 200:
                    result = await response.json()
                    personalized_response = result.get("response", gemini_response)
                else:
                    logger.warning(f"⚠️ Zantara model failed: {response.status}")
                    personalized_response = gemini_response

            return {
                "success": True,
                "response": personalized_response,
                "personality_used": personality["name"],
                "personality_type": user_context["personality_type"],
                "user": user,
                "model_used": "zantara-local",
                "original_gemini_response": gemini_response,
            }

        except Exception as e:
            logger.error(f"❌ Personality translation failed: {e}")
            return {
                "success": False,
                "response": gemini_response,  # Fallback to original
                "error": str(e),
                "personality_used": "fallback",
                "model_used": "gemini-only",
            }

    def get_available_personalities(self) -> list[dict[str, Any]]:
        """Restituisce la lista delle personalità disponibili"""
        personalities = []

        for profile_id, profile in self.personality_profiles.items():
            personalities.append(
                {
                    "id": profile_id,
                    "name": profile["name"],
                    "language": profile["language"],
                    "style": profile["style"],
                    "team_count": len(profile["team_members"]),
                    "traits": profile["traits"],
                }
            )

        return personalities

    async def test_personality(self, personality_type: str, test_message: str) -> dict[str, Any]:
        """
        Testa una personalità specifica

        Args:
            personality_type: Tipo di personalità (jaksel, zero, professional)
            test_message: Messaggio di test

        Returns:
            Dict con risposta di test
        """
        if personality_type not in self.personality_profiles:
            return {"error": f"Personality {personality_type} not found"}

        personality = self.personality_profiles[personality_type]

        try:
            headers = {}
            if self.oracle_api_key:
                headers["Authorization"] = f"Bearer {self.oracle_api_key}"

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.zantara_oracle_url,
                    json={
                        "model": "zantara",
                        "prompt": f"{personality['system_prompt']}\n\nUser: {test_message}\n\nResponse:",
                        "stream": False,
                    },
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return {
                            "success": True,
                            "personality": personality["name"],
                            "response": result.get("response", ""),
                        }
                    else:
                        return {"success": False, "error": f"Model failed: {response.status}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def translate_to_personality_advanced(
        self,
        gemini_response: str,
        user_email: str,
        original_query: str,
        language_context: str = "auto",
        gemini_model_getter=None,
    ) -> dict[str, Any]:
        """
        Versione avanzata che usa Gemini PRO per traduzione personalizzata di alta qualità

        Args:
            gemini_response: Risposta da Gemini RAG
            user_email: Email utente
            original_query: Query originale
            language_context: Contesto linguistico (id/it/en/ua)
            gemini_model_getter: Function to get Gemini model (injected to avoid circular imports)

        Returns:
            Dict con risposta personalizzata usando Gemini PRO + Zantara model
        """
        try:
            # Get user personality
            user_context = self.get_user_personality(user_email)
            personality = user_context["personality"]
            user = user_context["user"]

            logger.info(
                f"🎭 Advanced personality translation for {user['name']} ({personality['name']})"
            )

            # Use Gemini PRO for sophisticated personality translation
            if gemini_model_getter:
                try:
                    gemini_pro_model = gemini_model_getter("personality_translation")

                    # Build sophisticated translation prompt
                    translation_prompt = f"""
You are ZANTARA Personality Translator. You translate professional legal/business responses
into authentic personality voices while preserving ALL legal accuracy.

USER PROFILE:
- Name: {user["name"]}
- Language: {personality["language"]}
- Personality: {personality["name"]}
- Traits: {", ".join(personality["traits"])}

PERSONALITY STYLE:
{personality["system_prompt"]}

ORIGINAL QUERY: {original_query}

PROFESSIONAL RESPONSE: {gemini_response}

TASK:
Rewrite this professional response in the exact personality style. Be 100% authentic to the personality
while maintaining complete legal accuracy. The response should feel natural and personal.

Your response:"""

                    # Get personality-translated response from Gemini PRO
                    gemini_translated = await gemini_pro_model.generate_content_async(
                        translation_prompt
                    )
                    gemini_personality_response = gemini_translated.text

                    logger.info("✅ Gemini PRO personality translation completed")

                    # Optional: Further enhance with Zantara local model for authentic slang
                    if (
                        personality["language"] == "id"
                        and user_context["personality_type"] == "jaksel"
                    ):
                        zantara_enhanced = await self._enhance_with_zantara_model(
                            gemini_personality_response, personality
                        )
                        final_response = zantara_enhanced
                        model_used = "gemini-pro + zantara-local"
                    else:
                        final_response = gemini_personality_response
                        model_used = "gemini-pro"

                    return {
                        "success": True,
                        "response": final_response,
                        "personality_used": personality["name"],
                        "personality_type": user_context["personality_type"],
                        "user": user,
                        "model_used": model_used,
                        "enhanced": "zantara-local"
                        if "zantara-local" in model_used
                        else "gemini-only",
                        "original_gemini_response": gemini_response,
                    }

                except Exception as gemini_error:
                    logger.warning(f"⚠️ Gemini PRO personality translation failed: {gemini_error}")
                    # Fallback to original method
                    return await self.translate_to_personality(
                        gemini_response, user_email, original_query
                    )
            else:
                # No model getter provided, fallback to original method
                return await self.translate_to_personality(
                    gemini_response, user_email, original_query
                )

        except Exception as e:
            logger.error(f"❌ Advanced personality translation failed: {e}")
            return {
                "success": False,
                "response": gemini_response,
                "error": str(e),
                "personality_used": "fallback",
                "model_used": "gemini-only",
            }

    async def _enhance_with_zantara_model(self, text: str, personality: dict) -> str:
        """Enhance text with Zantara local model for authentic slang"""
        try:
            headers = {}
            if self.oracle_api_key:
                headers["Authorization"] = f"Bearer {self.oracle_api_key}"

            enhancement_prompt = f"""
Make this response more authentic {personality["name"]} style. Add natural slang and expressions.

Text: {text}

Enhanced text:"""

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    self.zantara_oracle_url,
                    json={"model": "zantara", "prompt": enhancement_prompt, "stream": False},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response,
            ):
                if response.status == 200:
                    result = await response.json()
                    return result.get("response", text)
                else:
                    return text

        except Exception as e:
            logger.warning(f"⚠️ Zantara enhancement failed: {e}")
            return text
