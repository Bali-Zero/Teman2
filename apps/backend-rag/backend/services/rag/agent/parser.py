import logging
import re
from typing import Optional

from services.rag.agent.structures import ToolCall

logger = logging.getLogger(__name__)


def clean_response(response: str) -> str:
    """
    Remove internal reasoning patterns from user-facing response.

    Filters out THOUGHT leaks, observation statements, and generic philosophical
    reasoning that should not be exposed to users.

    Args:
        response: Raw response from LLM

    Returns:
        Cleaned response without internal reasoning patterns
    """
    if not response:
        return ""

    patterns = [
        # Remove "Okay, since/with/given..." patterns (expanded to catch more variants)
        r"^Okay[,.]?\s*(since|with|given|without|lacking|based|in the absence)[^.]*observation[^.]*\.\s*",
        r"^Okay[,.]?\s*(based|since|with|given|without|lacking)[^.]*prior (information|context)[^.]*\.\s*",
        r"^Okay[,.]?\s*(based|since|with|given|without|lacking)[^.]*context[^.]*\.\s*",
        r"^Okay[,.]?\s*(based|since|with|given|without|lacking)[^.]*input[^.]*\.\s*",
        r"^Okay[,.]?\s*I need to (either|understand|consider)[^.]*\.\s*",
        r"^Okay[,.]?\s*Given the (observation|lack)[^.]*\.\s*",
        # Remove entire "Okay. Based/Given/Without..." sentences at start (non-greedy)
        r"^Okay\.\s*[A-Z][^.]*?(observation|context|information)[^.]*\.\s*",
        # Remove "solicit input" patterns
        r"[Mm]y next thought is to solicit input[^.]*\.\s*",
        r"[Ss]olicit input to understand[^.]*\.\s*",
        r"[Pp]rovide me with some context[^.]*\.\s*",
        # Remove THOUGHT: markers (case-insensitive)
        r"^THOUGHT:.*?\n",
        r"^THOUGHT\s*:.*?\n",
        r"^Thought:.*?\n",
        r"^Thought\s*:.*?\n",
        # Remove Observation: markers (case-insensitive)
        r"^Observation:.*?\n",
        r"^Observation\s*:.*?\n",
        # Remove stub responses
        r"Zantara has provided the final answer\.?\s*",
        r"ZANTARA has provided the final answer\.?\s*",
        r"\(No further action needed[^)]*\)\s*",
        r"No new query[^.]*\.\s*",
        r"Waiting for (your|user)[^.]*\.\s*",
        # Remove "Next thought" patterns
        r"^Next thought:.*?\n",
        r'^My "?next thought"?[^.]*\.\s*',
        r"[Mm]y next thought is:?\s*[^.]*\.\s*",
        # Remove generic philosophical reasoning
        r"^What (could|do|are|is) (I|we)[^?]*\?\s*",
        r"^Perhaps (the|I|we)[^.]*\.\s*",
        r"^Given (no|the lack of) (specific )?observation[^.]*\.\s*",
        r"^I will proceed with a general thought[^.]*\.\s*",
        r"^I\'ll (just )?offer a general[^.]*\.\s*",
        r"^In the absence of (an )?observation[^.]*\.\s*",
        r"^Since (there\'s|I have) no (prior )?observation[^.]*\.\s*",
        r"^Without (any )?(specific |prior )?(context|observation|information)[^.]*\.\s*",
        # Remove scenario/possibility statements that don't add value
        r"^Scenario \d+:[^.]*\.\s*",
        r"^Possible Next Steps[^:]*:\s*",
        # Remove meta-commentary about reasoning process
        r"^How can I be helpful[^?]*\?\s*",
        r"^The (power|importance|interplay) of[^.]*\.\s*",
        r"^Humans are remarkably[^.]*\.\s*",
        # Remove "Final Answer:" prefix if present
        r"^Final Answer:\s*",
        r"^FINAL ANSWER:\s*",
        # Remove "The search results..." reasoning leaks
        r"^The search results (mostly |don\'t |didn\'t |only )?[^.]*\.\s*",
        r"^I need to answer based on[^.]*\.\s*",
        r"^Based on (the |my )?search results[^.]*\.\s*",
        r"^(From |Looking at )the (search |observation |)results[^.]*\.\s*",
        # Remove internal notes about lack of information
        r"^Non ho bisogno di pensieri aggiuntivi[^.]*\.\s*",
        r"^Ho già fornito[^.]*\.\s*",
        r"^I don\'t need additional thoughts[^.]*\.\s*",
        r"^I\'ve already provided[^.]*\.\s*",
        # Remove "But there are still things..." patterns
        r"^But there are still things[^.]*\.\s*",
        # Remove "Let me..." patterns
        r"^Let me (check|search|look|find)[^.]*\.\s*",
        r"^Fammi (cercare|controllare|verificare)[^.]*\.\s*",
        # Remove standalone ACTION patterns that leaked
        r"^ACTION:\s*[a-z_]+\([^)]*\)\.?\s*",
        r"^ACTION:\s*No tool call needed[^.]*\.\s*",
        # Remove CRITICAL/IMPORTANT system message leaks
        r"^CRITICAL:\s*[^\n]*\n*",
        r"^IMPORTANT:\s*[^\n]*\n*",
        # Remove "User Query:" prompt leaks
        r"^User Query:\s*[^\n]*\n*",
        # Remove vector_search call leaks
        r"^vector_search\([^)]*\)\s*",
    ]

    cleaned = response
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.MULTILINE)

    # Remove multiple consecutive newlines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    # Remove leading/trailing whitespace
    cleaned = cleaned.strip()

    # Truncate if too long (strict limit)
    if len(cleaned) > 1000:
        logger.warning(f"⚠️ Response truncated from {len(cleaned)} to 1000 chars")
        cleaned = cleaned[:997] + "..."

    logger.info(f"🧹 Cleaned response length: {len(cleaned)}")
    return cleaned


def parse_tool_call(text: str) -> Optional[ToolCall]:
    """Simple parser for ReAct tool calls (ACTION: tool_name(args))"""
    # This is a simplified parser. In production, use structured output or native function calling.

    match = re.search(r"ACTION:\s*(\w+)\((.*)\)", text)
    if match:
        tool_name = match.group(1)
        args_str = match.group(2)
        try:
            # Try to parse args as JSON-like key=value or just string
            # This is very basic
            if "=" in args_str:
                args = dict(item.split("=") for item in args_str.split(","))
                # Clean quotes
                args = {k.strip(): v.strip().strip('"').strip("'") for k, v in args.items()}
            else:
                # Assume single arg 'query' or 'expression' based on tool
                if tool_name in ["vector_search", "web_search", "vision_analysis"]:
                    # Vision tool has 2 args (file_path, query), this basic parser might fail if not k=v
                    # But prompts usually output k=v.
                    # If only 1 arg string, assume query.
                    args = {"query": args_str.strip().strip('"')}
                elif tool_name == "calculator":
                    args = {"expression": args_str.strip().strip('"')}
                elif tool_name == "get_pricing":
                    # Likely single arg string passed as service_type if not k=v
                    args = {"service_type": args_str.strip().strip('"')}
                else:
                    args = {}

            return ToolCall(tool_name=tool_name, arguments=args)
        except Exception:
            return None
    return None
