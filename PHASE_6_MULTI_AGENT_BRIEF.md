# Phase 6: Multi-Agent Orchestration - Implementation Brief

**Assigned to:** Available AI Agent
**Priority:** MEDIUM
**Estimated Effort:** 4-5 hours
**Dependencies:** Phase 1, Phase 2, Phase 4 (Feedback Loop)

---

## Objective

Create specialized sub-agents (Legal, Financial, Timeline) that collaborate to answer complex queries requiring multi-domain expertise.

---

## Architecture

```
User Query: "How much will PT PMA cost and when can I start operations?"
     ↓
Orchestrator (decides multi-agent needed)
     ↓
  ┌──────────────────────────────────┐
  │  Multi-Agent Coordinator         │
  │  (LangGraph StateGraph)          │
  └──────────────────────────────────┘
       ↓         ↓           ↓
   Legal     Financial    Timeline
   Agent      Agent        Agent
     ↓          ↓            ↓
   "Need     "Total:      "45-60 days
   NPWP,     Rp 20M +     (breakdown)"
   Akta"     notary"
       ↓         ↓           ↓
  ┌──────────────────────────────────┐
  │  Synthesizer Node                │
  │  (Combines agent outputs)        │
  └──────────────────────────────────┘
              ↓
        Final Answer
```

---

## Implementation

### File 1: `backend/services/rag/multi_agent_coordinator.py` (~400 lines)

```python
"""
Multi-Agent Coordinator using LangGraph.
Coordinates Legal, Financial, and Timeline agents for complex queries.
"""

from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
import operator

# State definition
class MultiAgentState(TypedDict):
    query: str
    user_context: dict
    legal_analysis: str
    financial_breakdown: str
    timeline_estimate: str
    agent_outputs: Annotated[list[dict], operator.add]
    final_answer: str
    errors: list[str]

# Agent definitions
class LegalAgent:
    """Analyzes legal requirements (documents, compliance, regulations)."""

    def __init__(self, llm: ChatAnthropic, kg_retrieval):
        self.llm = llm
        self.kg_retrieval = kg_retrieval

    async def analyze(self, state: MultiAgentState) -> dict:
        """
        Extract legal requirements from query.

        Returns:
            - Required documents (NPWP, Akta, passport, etc.)
            - Legal entities involved (PT PMA, Perorangan, etc.)
            - Compliance requirements (BKPM, notary, etc.)
        """
        query = state["query"]

        # Use KG to find legal requirements
        kg_results = await self.kg_retrieval.search(query, limit=10)

        # Extract entities with type "dokumen", "undang_undang", "pasal"
        legal_entities = [
            r for r in kg_results
            if r.get("entity_type") in ["dokumen", "undang_undang", "pasal"]
        ]

        # LLM analyzes legal requirements
        prompt = f"""
        Based on the query: "{query}"

        Legal entities found: {legal_entities}

        List required documents and compliance steps in order.
        Format as bullet points.
        """

        response = await self.llm.ainvoke(prompt)

        return {
            "legal_analysis": response.content,
            "agent_outputs": [{
                "agent": "legal",
                "output": response.content,
                "entities_used": len(legal_entities)
            }]
        }

class FinancialAgent:
    """Calculates total costs (government fees + Bali Zero services)."""

    def __init__(self, llm: ChatAnthropic, pricing_service):
        self.llm = llm
        self.pricing_service = pricing_service

    async def analyze(self, state: MultiAgentState) -> dict:
        """
        Calculate cost breakdown.

        Returns:
            - Bali Zero service fee
            - Government PNBP fees
            - Notary/third-party fees
            - Total estimate
        """
        query = state["query"]

        # Get Bali Zero pricing
        service_match = self._extract_service_type(query)
        pricing = await self.pricing_service.get_price(service_match)

        # LLM analyzes additional costs
        prompt = f"""
        Query: "{query}"

        Bali Zero service: {pricing}

        Calculate additional costs (PNBP, notary, etc.) based on service type.
        Provide itemized breakdown.
        """

        response = await self.llm.ainvoke(prompt)

        return {
            "financial_breakdown": response.content,
            "agent_outputs": [{
                "agent": "financial",
                "output": response.content,
                "bali_zero_price": pricing
            }]
        }

    def _extract_service_type(self, query: str) -> str:
        """Map query to service type (pt_pma, kitas, etc.)."""
        if any(kw in query.lower() for kw in ["pt pma", "pt"]):
            return "pt_pma"
        elif any(kw in query.lower() for kw in ["kitas", "work permit"]):
            return "kitas"
        # ... add more mappings
        return "general_consultation"

class TimelineAgent:
    """Estimates timelines and deadlines."""

    def __init__(self, llm: ChatAnthropic, kg_retrieval):
        self.llm = llm
        self.kg_retrieval = kg_retrieval

    async def analyze(self, state: MultiAgentState) -> dict:
        """
        Estimate timeline with breakdown.

        Returns:
            - Phase-by-phase timeline
            - Critical path items
            - Buffer for delays
            - Expected completion date
        """
        query = state["query"]
        legal_steps = state.get("legal_analysis", "")

        # Use KG to find duration entities
        kg_results = await self.kg_retrieval.search(query, limit=10)
        duration_entities = [
            r for r in kg_results
            if "duration" in r.get("properties", {})
        ]

        # LLM creates timeline
        prompt = f"""
        Query: "{query}"

        Legal steps required: {legal_steps}
        Known durations: {duration_entities}

        Create phase-by-phase timeline:
        1. Document preparation: X days
        2. Submission to authority: Y days
        3. Approval/processing: Z days

        Include buffer for delays. Give total estimate.
        """

        response = await self.llm.ainvoke(prompt)

        return {
            "timeline_estimate": response.content,
            "agent_outputs": [{
                "agent": "timeline",
                "output": response.content,
                "duration_entities_used": len(duration_entities)
            }]
        }

# Coordinator (LangGraph)
class MultiAgentCoordinator:
    def __init__(self, llm, kg_retrieval, pricing_service):
        self.legal_agent = LegalAgent(llm, kg_retrieval)
        self.financial_agent = FinancialAgent(llm, pricing_service)
        self.timeline_agent = TimelineAgent(llm, kg_retrieval)
        self.llm = llm

        # Build graph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(MultiAgentState)

        # Add nodes
        workflow.add_node("legal", self.legal_agent.analyze)
        workflow.add_node("financial", self.financial_agent.analyze)
        workflow.add_node("timeline", self.timeline_agent.analyze)
        workflow.add_node("synthesize", self._synthesize_outputs)

        # Parallel execution: legal, financial, timeline run simultaneously
        workflow.set_entry_point("legal")
        workflow.add_edge("legal", "financial")
        workflow.add_edge("financial", "timeline")
        workflow.add_edge("timeline", "synthesize")
        workflow.add_edge("synthesize", END)

        return workflow.compile()

    async def _synthesize_outputs(self, state: MultiAgentState) -> dict:
        """Combine agent outputs into final answer."""
        prompt = f"""
        User query: "{state['query']}"

        Legal analysis:
        {state['legal_analysis']}

        Financial breakdown:
        {state['financial_breakdown']}

        Timeline estimate:
        {state['timeline_estimate']}

        Synthesize into a coherent answer for the user.
        Format:
        **Legal Requirements:** ...
        **Cost Breakdown:** ...
        **Timeline:** ...
        **Next Steps:** ...
        """

        response = await self.llm.ainvoke(prompt)

        return {
            "final_answer": response.content
        }

    async def process(self, query: str, user_context: dict) -> dict:
        """Run multi-agent workflow."""
        initial_state = MultiAgentState(
            query=query,
            user_context=user_context,
            legal_analysis="",
            financial_breakdown="",
            timeline_estimate="",
            agent_outputs=[],
            final_answer="",
            errors=[]
        )

        result = await self.graph.ainvoke(initial_state)
        return result
```

---

### File 2: Integration with Orchestrator

**File:** `backend/services/rag/agentic/orchestrator_core.py`

**Add detection logic:**

```python
def _requires_multi_agent(self, query: str, entities: list) -> bool:
    """
    Detect if query needs multi-agent coordination.

    Triggers:
        - Query asks about cost AND timeline ("how much and when")
        - Query mentions multiple domains (visa + tax)
        - Entity count > 5 (complex query)
    """
    query_lower = query.lower()

    # Cost + Timeline patterns
    cost_keywords = ['cost', 'price', 'biaya', 'harga', 'berapa']
    time_keywords = ['when', 'kapan', 'timeline', 'duration', 'lama']

    has_cost = any(kw in query_lower for kw in cost_keywords)
    has_time = any(kw in query_lower for kw in time_keywords)

    if has_cost and has_time:
        return True

    # Multiple domains
    domains = set()
    for entity in entities:
        entity_type = entity.get("entity_type", "")
        if entity_type in ["visa", "kitas"]:
            domains.add("immigration")
        elif entity_type in ["tax", "pajak"]:
            domains.add("tax")
        elif entity_type in ["pt_pma", "cv"]:
            domains.add("company")

    if len(domains) >= 2:
        return True

    # High entity count
    if len(entities) > 5:
        return True

    return False
```

---

### File 3: Tests

**File:** `backend/tests/services/rag/test_multi_agent.py` (~250 lines)

```python
import pytest
from backend.services.rag.multi_agent_coordinator import (
    MultiAgentCoordinator,
    LegalAgent,
    FinancialAgent,
    TimelineAgent,
    MultiAgentState
)

class TestLegalAgent:
    async def test_analyze_pt_pma_query(self):
        """Legal agent extracts PT PMA requirements."""
        # Mock LLM and KG
        # Test that legal_analysis includes "NPWP", "Akta"
        pass

class TestFinancialAgent:
    async def test_calculate_pt_pma_cost(self):
        """Financial agent calculates PT PMA total cost."""
        # Mock pricing service
        # Test that financial_breakdown includes Bali Zero price + PNBP
        pass

class TestTimelineAgent:
    async def test_estimate_kitas_timeline(self):
        """Timeline agent estimates KITAS processing time."""
        # Mock KG with duration entities
        # Test that timeline_estimate includes phase breakdown
        pass

class TestMultiAgentCoordinator:
    async def test_full_workflow(self):
        """End-to-end multi-agent workflow."""
        query = "How much will PT PMA cost and when can I start?"
        result = await coordinator.process(query, user_context={})

        assert "legal_analysis" in result
        assert "financial_breakdown" in result
        assert "timeline_estimate" in result
        assert "final_answer" in result
        assert len(result["agent_outputs"]) == 3  # 3 agents ran
```

---

## Success Criteria

✅ Legal agent extracts required documents
✅ Financial agent calculates total cost breakdown
✅ Timeline agent estimates phase-by-phase timeline
✅ Synthesizer combines outputs coherently
✅ Integration with orchestrator detects multi-agent queries
✅ All tests passing (target: 15+ tests)

---

## Files to Create

| File | Purpose | Lines |
|------|---------|-------|
| `backend/services/rag/multi_agent_coordinator.py` | Coordinator + 3 agents | ~400 |
| `backend/tests/services/rag/test_multi_agent.py` | Test suite | ~250 |

**Total:** ~650 lines

---

## Notes

- **Parallel execution:** Use LangGraph edges for concurrent agent runs
- **State sharing:** Legal agent output feeds into Timeline agent
- **Error handling:** Each agent should handle failures gracefully
- **Cost optimization:** Cache agent outputs for similar queries

---

**Ready to implement?** Start with LegalAgent, then Financial, then Timeline. Test each agent independently before full workflow.
