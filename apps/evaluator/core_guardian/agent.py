"""
Core Guardian - Phase 2 & 3: DECIDE & ACT
The routing orchestrator that prepares the task and invokes Claude Opus 4.6 via OpenClaw CLI.
"""

import json
import logging
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import asyncio
import re
import shlex

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[Core Guardian - AGENT] %(levelname)s: %(message)s")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
STATE_FILE = PROJECT_ROOT / ".agent" / "decisions" / "state_backend.json"
DECISIONS_DIR = PROJECT_ROOT / ".agent" / "decisions" / "adr"
WORKSPACE_DIR = PROJECT_ROOT

def load_state() -> dict:
    if not STATE_FILE.exists():
        logger.error("State file not found. Run observe.py first.")
        return {}
    with open(STATE_FILE) as f:
        return json.load(f)

async def ask_openclaw_opus(prompt: str) -> str:
    """Invoca l'agente 'main' di OpenClaw (Claude Opus 4.6) via CLI in modalità reale."""
    logger.info("Sending request to OpenClaw (Claude Opus 4.6) via CLI...")

    try:
        # Usa il comando ufficiale openclaw agent
        cmd = [
            "openclaw", "agent",
            "--agent", "main",
            "--message", prompt,
            "--thinking", "high",
            "--timeout", "600",
            "--json"
        ]

        logger.info(f"Executing: openclaw agent --agent main ... (prompt length: {len(prompt)})")

        # Esecuzione reale bloccante (può durare fino a 10 minuti per ragionamenti complessi)
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(WORKSPACE_DIR))

        if result.returncode != 0:
            logger.error(f"OpenClaw execution failed with code {result.returncode}")
            logger.error(f"Stderr: {result.stderr}")
            return ""

        # Parse the JSON response
        try:
            output_data = json.loads(result.stdout)
            # Dipende da come OpenClaw formatta il JSON, assumiamo ci sia un campo text/message/content
            content = output_data.get("text", output_data.get("message", output_data.get("content", result.stdout)))

            if isinstance(content, dict):
                 content = content.get("text", str(content))

            return content
        except json.JSONDecodeError:
            logger.warning("Could not parse JSON from OpenClaw, returning raw stdout")
            return result.stdout

    except Exception as e:
        logger.error(f"Failed to reach OpenClaw CLI: {e}")
        return ""

def create_branch_and_apply(target_file: str, response: str) -> bool:
    """Applica la logica su branch isolata e lancia il test."""
    logger.info("Phase 3: ACT. Extracting python code from response...")

    # 1. Estrai il blocco di codice Python dalla risposta di Opus
    code_match = re.search(r"```python(.*?)```", response, re.DOTALL)
    if not code_match:
        logger.error("No python code block found in Opus response.")
        return False

    code_content = code_match.group(1).strip()

    # Per sicurezza in questa prima esecuzione, non modificheremo i test reali,
    # ma salveremo il fix proposto in un file di patch per la tua review.
    # In produzione, l'agente farebbe:
    # 1. git checkout -b auto-fix/...
    # 2. write code to target_file
    # 3. pytest target_file
    # 4. git commit

    patch_file = DECISIONS_DIR / f"proposed_fix_for_{target_file.replace('/', '_')}.py"
    with open(patch_file, "w") as f:
        f.write(code_content)

    logger.info(f"✅ Extracted patch saved to {patch_file} for human review before applying.")
    return True

async def handle_pytest_failures(traceback: str):
    logger.info("Preparing OpenClaw payload...")

    # Cerchiamo di identificare il file del test che sta fallendo
    # Es: backend/tests/test_conversation_persistence.py
    file_match = re.search(r"backend/tests/[^\s:]+\.py", traceback)
    target_file = file_match.group(0) if file_match else "unknown"

    logger.info(f"Target file identified: {target_file}")

    prompt = f"""
SEI IL NUZANTARA CORE GUARDIAN.
Il tuo ruolo è risolvere il debito tecnico nel backend FastAPI autonomamente.

L'esecuzione della CI ha rilevato un errore nel file test: {target_file}

Traceback parziale:
{traceback[:3000]}

Regole (dal tuo GEMINI.md):
- Usa mock async (AsyncMock) per i test di database (es. asyncpg pool, qdrant client)
- Non rimuovere type hints
- Non usare `requests`, usa sempre `httpx`
- I test che falliscono per timeout (socket.gaierror) solitamente mancano del mock del DB pool all'avvio.

ISTRUZIONI:
1. Analizza l'errore profondamente.
2. Fornisci il codice python completo o la funzione da sostituire per fixare il test all'interno di un blocco ```python.
3. Spiega brevemente il ragionamento architetturale sotto il blocco di codice.
"""

    response = await ask_openclaw_opus(prompt)

    if response:
        logger.info("✅ Received response from Claude Opus 4.6.")

        success = create_branch_and_apply(target_file, response)

        if success:
            adr_content = f"""# ADR: Auto-Fix per {target_file}

## Dettagli dell'Esecuzione
- **Data**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- **Modello**: Claude Opus 4.6 (via OpenClaw)
- **Target**: `{target_file}`

## Risposta Originale del Modello
{response}
"""
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            safe_target = target_file.split('/')[-1].replace('.py', '')
            adr_file = DECISIONS_DIR / f"auto_{timestamp}_{safe_target}.md"
            DECISIONS_DIR.mkdir(parents=True, exist_ok=True)

            with open(adr_file, "w") as f:
                f.write(adr_content)

            logger.info(f"💾 ADR salvato in {adr_file}")
            logger.info("🎉 Task completato.")
    else:
        logger.error("Failed to get a valid response from Claude Opus.")

async def run():
    state = load_state()
    if not state:
        return

    logger.info("Analyzing state...")

    pytest_state = state.get("pytest", {})
    if pytest_state.get("failures_found"):
        logger.info("Critical test failures found. Routing to Claude Opus 4.6.")
        await handle_pytest_failures(pytest_state.get("output", ""))
    else:
        logger.info("No test failures. Analyzing Ruff smells.")

if __name__ == "__main__":
    asyncio.run(run())
