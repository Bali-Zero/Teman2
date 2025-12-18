# Zantara Agent Architecture

## Overview
Zantara's agentic core (`AgenticRAGOrchestrator`) has been refactored into a modular architecture to improve maintainability, testing, and scalability. The system implements a **ReAct (Reason-Act-Observe)** loop with dynamic system prompting and tool execution.

## Directory Structure
`apps/backend-rag/backend/services/rag/agentic/` (Refactored Package)

- **`orchestrator.py`**: Main entry point (`AgenticRAGOrchestrator`). Manages the conversation loop, state, and streaming.
- **`tools.py`**: Concrete tool implementations (`VectorSearchTool`, `PricingTool`, `VisionTool`, etc.).
- **`prompt_builder.py`**: System prompt construction with caching and persona management.
- **`reasoning.py`**: Encapsulates the ReAct (Reason-Act-Observe) logic.
- **`llm_gateway.py`**: Unified interface for LLM calls with fallback cascades.
- **`pipeline.py`**: Response processing pipeline (verification, citation, formatting).
- **`tool_executor.py`**: Tool execution logic and output parsing.

*Note: Core data models (`AgentState`, `AgentStep`, `BaseTool`) are located in `apps/backend-rag/backend/services/tools/definitions.py`.*

## Core Components

### 1. Orchestrator (`orchestrator.py`)
The `AgenticRAGOrchestrator` class coordinates the entire process:
- **State Management**: Tracks steps, history, and max iterations.
- **Streaming**: Yields Server-Sent Events (SSE) for real-time UI updates.
- **Fallback Strategy**: Handled by `LLMGateway` (Gemini Flash -> Flash-Lite -> OpenRouter).

### 2. Tools (`tools.py`)
Tools are self-contained classes inheriting from `BaseTool`.
- **Vector Search**: Queries Qdrant for semantic knowledge.
- **Pricing**: Queries the `PricingService` for official Bali Zero rates.
- **Vision**: Analyzes PDF/Image content.
- **Diagnostics**: System health checks.

### 3. Persona & Prompting (`prompt_builder.py`)
Dynamic system prompt generation (`build_system_prompt`) based on:
- User Profile & Role
- Conversation History
- Query Characteristics (Language, Complexity)
- **Persona Injection**: Applies the Zantara "Jakarta Selatan" persona.

### 4. Reasoning Engine (`reasoning.py`)
Implements the ReAct loop:
1. **Thought**: The model analyzes the situation.
2. **Action**: The model decides to call a tool.
3. **Observation**: The tool executes and returns data.
4. **Refinement**: The model processes the observation.

