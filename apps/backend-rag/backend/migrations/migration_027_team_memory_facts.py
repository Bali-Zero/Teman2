"""
Migration 027: Populate Memory Facts for Team Members

Populates the memory_facts table with rich profile facts for all Bali Zero team members.
This enables Zantara to recognize team members and provide personalized responses.

Facts are stored by EMAIL (user_id = email), as the memory system uses email for lookups.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

import asyncpg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_facts_for_member(member: dict) -> list[dict]:
    """
    Generate rich memory facts for a team member.

    Returns list of fact dictionaries with: content, fact_type, confidence, source
    """
    facts = []
    email = member["email"]
    name = member["name"]
    role = member["role"]
    department = member.get("department", "general")

    # 1. Identity fact (highest priority)
    identity = f"{name} è {role} nel team {department} di Bali Zero"
    if member.get("location"):
        identity += f", lavora da {member['location']}"
    facts.append(
        {"content": identity, "fact_type": "identity", "confidence": 1.0, "source": "team_database"}
    )

    # 2. Language preferences
    languages = member.get("languages", [])
    preferred = member.get("preferred_language", "id")
    lang_names = {
        "it": "italiano",
        "en": "inglese",
        "id": "indonesiano",
        "uk": "ucraino",
        "jv": "giavanese",
        "ban": "balinese",
        "su": "sundanese",
        "ua": "ucraino",
    }
    if preferred and preferred in lang_names:
        facts.append(
            {
                "content": f"{name} preferisce comunicare in {lang_names.get(preferred, preferred)}",
                "fact_type": "preference",
                "confidence": 1.0,
                "source": "team_database",
            }
        )

    # 3. Emotional preferences / communication style
    emo_prefs = member.get("emotional_preferences", {})
    if emo_prefs:
        tone = emo_prefs.get("tone", "").replace("_", " ")
        formality = emo_prefs.get("formality", "medium")
        humor = emo_prefs.get("humor", "light")

        formality_desc = {
            "high": "formale e rispettoso",
            "medium": "bilanciato tra formale e informale",
            "low": "informale e diretto",
        }
        humor_desc = {
            "minimal": "serio e professionale",
            "light": "con un pizzico di leggerezza",
            "witty": "spiritoso e arguto",
            "playful": "giocoso e divertente",
            "subtle": "con umorismo sottile",
        }

        style_parts = []
        if formality in formality_desc:
            style_parts.append(formality_desc[formality])
        if humor in humor_desc:
            style_parts.append(humor_desc[humor])

        if style_parts:
            facts.append(
                {
                    "content": f"Con {name}, usa un tono {', '.join(style_parts)}",
                    "fact_type": "communication_style",
                    "confidence": 0.95,
                    "source": "team_database",
                }
            )

    # 4. Personal traits
    traits = member.get("traits", [])
    trait_descriptions = {
        "leader": "ha qualità di leadership",
        "experienced": "è molto esperto nel suo campo",
        "visionary": "è un visionario con idee innovative",
        "tech_lead": "guida la direzione tecnologica",
        "dreamer": "è una sognatrice con grandi visioni",
        "strategic": "pensa in modo strategico",
        "curious": "è molto curioso e ama imparare",
        "friendly": "è amichevole e socievole",
        "loyal": "è leale e affidabile",
        "undisciplined": "a volte manca di disciplina",
        "willpower": "ha grande forza di volontà",
        "resilient": "è resiliente e non si arrende",
        "perfectionist": "è un perfezionista attento ai dettagli",
        "aesthetic": "ha un forte senso estetico",
        "polite": "è educato e rispettoso",
        "newcomer": "è un nuovo membro del team",
        "animal_lover": "ama gli animali",
        "respected": "è molto rispettato nel team",
        "analytical": "ha un approccio analitico",
        "direct": "è diretto nella comunicazione",
        "empathetic": "è empatico e comprensivo",
        "structured": "è metodico e organizzato",
        "dedicated": "è dedicato al suo lavoro",
        "young_veteran": "nonostante la giovane età è già un veterano",
        "brilliant": "è brillante nel suo campo",
        "growing": "sta crescendo professionalmente",
        "sweet": "è dolce e gentile",
        "social": "è socievole e ama TikTok",
        "talkative": "è chiacchierona",
        "easily_scared": "si spaventa facilmente",
        "introvert": "è introversa ma molto gentile",
        "kind": "è gentile e disponibile",
        "creative": "è creativa",
        "italian_style": "ha uno stile italiano",
        "stylish": "ha stile e gusto",
        "ambitious": "è ambiziosa",
        "multi_tasker": "è brava nel multitasking",
        "quiet": "è piuttosto riservata",
        "junior": "è ancora junior ma sta imparando",
    }

    relevant_traits = [trait_descriptions[t] for t in traits if t in trait_descriptions]
    if relevant_traits:
        facts.append(
            {
                "content": f"{name} {', '.join(relevant_traits[:3])}",  # Max 3 traits
                "fact_type": "personality",
                "confidence": 0.9,
                "source": "team_database",
            }
        )

    # 5. Notes / special info
    notes = member.get("notes", "")
    if notes and len(notes) > 10:
        # Extract key info from notes
        facts.append(
            {
                "content": f"Info su {name}: {notes}",
                "fact_type": "background",
                "confidence": 0.85,
                "source": "team_database",
            }
        )

    # 6. Relationships (if any)
    relationships = member.get("relationships", [])
    for rel in relationships:
        rel_type = rel.get("type", "")
        rel_with = rel.get("with", "")
        if rel_type and rel_with:
            facts.append(
                {
                    "content": f"{name} ha una relazione di tipo '{rel_type}' con {rel_with}",
                    "fact_type": "relationship",
                    "confidence": 0.8,
                    "source": "team_database",
                }
            )

    # 7. Expertise level
    expertise = member.get("expertise_level", "")
    expertise_desc = {
        "expert": "è un esperto di alto livello",
        "advanced": "ha competenze avanzate",
        "intermediate": "ha competenze intermedie",
        "beginner": "sta ancora imparando",
    }
    if expertise in expertise_desc:
        facts.append(
            {
                "content": f"{name} {expertise_desc[expertise]} nel suo ruolo",
                "fact_type": "expertise",
                "confidence": 0.9,
                "source": "team_database",
            }
        )

    # 8. Religion (for cultural awareness)
    religion = member.get("religion", "")
    if religion:
        facts.append(
            {
                "content": f"{name} è di religione {religion}",
                "fact_type": "cultural",
                "confidence": 0.9,
                "source": "team_database",
            }
        )

    return facts


async def apply_migration(database_url: str = None):
    """Apply the migration to populate team member memory facts."""

    if not database_url:
        database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        logger.error("DATABASE_URL not provided")
        return False

    # Load team members JSON
    team_file = Path(__file__).parent.parent / "data" / "team_members.json"
    if not team_file.exists():
        logger.error(f"Team members file not found: {team_file}")
        return False

    with open(team_file) as f:
        team_members = json.load(f)

    logger.info(f"Loaded {len(team_members)} team members from {team_file}")

    try:
        conn = await asyncpg.connect(database_url)
        logger.info("Connected to PostgreSQL")

        # Track stats
        total_facts = 0
        members_processed = 0

        for member in team_members:
            email = member.get("email", "")
            name = member.get("name", "unknown")

            if not email:
                logger.warning(f"Skipping member without email: {name}")
                continue

            # Generate facts for this member
            facts = generate_facts_for_member(member)

            # Delete existing facts for this user (clean slate)
            await conn.execute(
                "DELETE FROM memory_facts WHERE user_id = $1 AND source = 'team_database'", email
            )

            # Insert new facts
            for fact in facts:
                await conn.execute(
                    """
                    INSERT INTO memory_facts (user_id, content, fact_type, confidence, source, metadata, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    email,
                    fact["content"],
                    fact["fact_type"],
                    fact["confidence"],
                    fact["source"],
                    json.dumps({"member_id": member.get("id", "")}),
                    datetime.now(),
                )
                total_facts += 1

            members_processed += 1
            logger.info(f"✅ {name} ({email}): {len(facts)} facts inserted")

        await conn.close()

        logger.info(f"""
╔════════════════════════════════════════════════════════════════╗
║  MIGRATION 027: Team Memory Facts Population Complete!         ║
╠════════════════════════════════════════════════════════════════╣
║  Team members processed: {members_processed:3d}                                 ║
║  Total facts inserted:   {total_facts:3d}                                 ║
║  Source: team_database                                         ║
╚════════════════════════════════════════════════════════════════╝
        """)

        return True

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        return False


async def rollback_migration(database_url: str = None):
    """Rollback the migration by removing team_database facts."""

    if not database_url:
        database_url = os.environ.get("DATABASE_URL")

    try:
        conn = await asyncpg.connect(database_url)

        result = await conn.execute("DELETE FROM memory_facts WHERE source = 'team_database'")

        await conn.close()
        logger.info(f"Rollback complete: {result}")
        return True

    except Exception as e:
        logger.error(f"Rollback failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        asyncio.run(rollback_migration())
    else:
        asyncio.run(apply_migration())
