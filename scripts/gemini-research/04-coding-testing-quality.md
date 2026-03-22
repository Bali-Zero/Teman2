# Deep Research: AI-Powered Testing & Quality Assurance 2026

You are researching for Nuzantara/Bali Zero — a production platform with 385 test files (test debt cleaned as of 2026-03-20).

## Current State

- 385 test files, pytest + vitest
- Core tests: 100% (KG 82/82, Channels 43/43, RAG 244/244)
- Unit test debt: CLEANED (was ~448 failures, resolved 2026-03-20)
- Frontend: 1013 tests passing (vitest)
- No CI/CD pipeline (pre-push hook runs tests but is often bypassed)
- No integration tests against real services

## Research Questions

1. **AI-assisted test repair**: Tools and techniques to automatically fix broken tests caused by refactoring (missing imports, renamed functions, deleted modules). CodiumAI, Diffblue, Qodo — what works for Python/TypeScript? (Note: our ~448 test debt has been cleaned, but this remains relevant for future prevention.)

2. **LLM output testing**: How to test non-deterministic AI outputs? Evaluation frameworks for RAG quality: RAGAS, DeepEval, Phoenix, custom. What metrics matter for our use case (immigration/legal advice accuracy)?

3. **CI/CD for AI apps**: Minimal CI pipeline for a monorepo with Python + Next.js. GitHub Actions vs Fly.io CI vs Dagger. Must support: parallel test suites, secret management, conditional deploys (backend vs frontend).

4. **Snapshot testing for AI agents**: How to test LangGraph workflows deterministically? State-based assertions, mock LLM responses, golden path testing. Best practices from production LangGraph deployments.

5. **Contract testing**: API contract testing between FastAPI backend and Next.js frontend. Schemathesis, Dredd, or TypeScript-first approach? How to keep frontend types in sync with backend Pydantic models automatically.

6. **Test prioritization**: With 385 test files and limited CI budget, how to run only relevant tests on each commit? Test impact analysis, file dependency mapping, git diff-based test selection.

## Output Format

For each area: tool recommendation, implementation effort (hours), and a priority-ordered action plan.

Save your research to `docs/research/2026-03-15-testing-quality.md`
