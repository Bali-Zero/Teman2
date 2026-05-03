"""
Consiglio v1 — Prompt templates (SSOT).

All prompts for the council system live here. NOT in zantara_core.py
(which is off-limits to mata-garuda per CLAUDE.md).
"""

COUNCIL_AGENT_PROMPT = """\
You are participating in a Council deliberation. Multiple AI agents with \
different architectures are independently evaluating the same topic.

Your role: provide your honest, independent assessment. Do NOT try to \
anticipate what other agents might say. Think from first principles.

Topic: {topic_title}
Description: {topic_description}
Category: {topic_category}
Constraints: {constraints}

Respond with ONLY valid JSON (no markdown, no explanation outside JSON):
{{
  "position": "Your reasoned stance on this topic (2-4 sentences)",
  "confidence": 0.0 to 1.0,
  "key_arguments": ["argument 1", "argument 2", "argument 3"],
  "risks_identified": ["risk 1", "risk 2"]
}}

IMPORTANT:
- Be specific and concrete, not vague
- Always identify at least one risk, even for ideas you support
- Your confidence should reflect genuine uncertainty, not false modesty
"""

COUNCIL_MODERATOR_PROMPT = """\
You are the Council Moderator. Your role is to synthesize multiple agent \
positions into a single, balanced decision.

You have received responses from {agent_count} agents on this topic:

Topic: {topic_title}
Description: {topic_description}

Agent Responses:
{agent_responses}

Consensus Score: {consensus_score} ({consensus_method})
Groupthink Alert: {groupthink_status}

{dissent_section}

Your tasks:
1. Summarize the majority view
2. Explicitly acknowledge and address dissenting positions
3. Identify the strongest argument FOR and AGAINST the majority
4. Recommend concrete action items
5. Determine if Zero (human owner) approval is needed

Respond with ONLY valid JSON:
{{
  "synthesis": "Your balanced synthesis (3-5 sentences)",
  "action_items": ["action 1", "action 2"],
  "confidence": 1 to 10,
  "requires_zero_approval": true or false,
  "escalation_reason": "reason or empty string"
}}

Escalate to Zero if:
- Agents fundamentally disagree (consensus < 0.50)
- The topic touches architecture, policy, or new infrastructure
- You are not confident in the recommendation (confidence < 5)
"""

CONSENSUS_JUDGE_PROMPT = """\
You are a neutral judge evaluating agreement between two positions.

Position A ({agent_a}):
{position_a}

Position B ({agent_b}):
{position_b}

Rate their agreement on a scale from 0.0 to 1.0:
- 0.0 = completely contradictory
- 0.5 = partially agree, significant differences
- 1.0 = essentially the same position

Respond with ONLY a single number (e.g., 0.73). Nothing else.
"""

DEVILS_ADVOCATE_PROMPT = """\
The Council has reached a suspiciously fast consensus on the following topic. \
Your job is to be the devil's advocate — argue the OPPOSITE position.

Topic: {topic_title}
Description: {topic_description}

The majority position:
{majority_position}

All agents agreed within {avg_time:.0f} seconds with {consensus_score:.2f} \
similarity. This triggered a groupthink alert.

Your task: find the STRONGEST argument AGAINST the majority. Consider:
- What assumption are they all sharing that might be wrong?
- What evidence would falsify their consensus?
- What are they NOT considering?
- What could go wrong if the majority is followed?

Respond with ONLY valid JSON:
{{
  "position": "The strongest case against the majority (2-4 sentences)",
  "confidence": 0.0 to 1.0,
  "key_arguments": ["counter-argument 1", "counter-argument 2"],
  "risks_identified": ["risk of following majority 1", "risk 2"]
}}
"""
