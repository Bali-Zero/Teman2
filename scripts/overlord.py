#!/usr/bin/env python3
import subprocess
import sys
import os
import json
import ast
import requests
import time
from pathlib import Path

# --- CONFIGURATION ---
PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_DIR = PROJECT_ROOT / "apps" / "backend-rag"
TESTS_DIR = BACKEND_DIR / "backend" / "tests"
SENTINEL_LOG = PROJECT_ROOT / "OVERLORD_LOG.md"
OLLAMA_MODEL = "deepseek-r1"
MAX_REPAIR_ATTEMPTS = 2

COLORS = {
    "HEADER": "\033[95m",
    "OKBLUE": "\033[94m",
    "OKCYAN": "\033[96m",
    "OKGREEN": "\033[92m",
    "WARNING": "\033[93m",
    "FAIL": "\033[91m",
    "ENDC": "\033[0m",
}

# --- UTILS ---
def log(message, level="INFO"):
    color = COLORS.get(level, COLORS["OKBLUE"])
    if level == "SUCCESS": color = COLORS["OKGREEN"]
    elif level == "WARNING": color = COLORS["WARNING"]
    elif level == "ERROR": color = COLORS["FAIL"]
    elif level == "HEADER": color = COLORS["HEADER"]
    
    print(f"{color}[{level}] {message}{COLORS['ENDC']}")
    
    if level in ["ERROR", "SUCCESS", "WARNING"]:
        try:
            safe_msg = message.replace('"', '\"')
            subprocess.run(f'osascript -e \'display notification \"{safe_msg}\" with title \"Nuzantara Overlord\" subtitle \"{level}\"\' ', shell=True)
        except: pass

    with open(SENTINEL_LOG, "a") as f:
        f.write(f"- **{time.strftime('%Y-%m-%d %H:%M:%S')}** [{level}]: {message}\n")

def run_command(command, cwd=None, capture=True):
    try:
        return subprocess.run(command, cwd=cwd, shell=True, text=True, capture_output=capture)
    except Exception as e:
        log(f"Command failed: {e}", "ERROR")
        return None

# --- AI BRAIN (OLLAMA) ---
def ollama_generate(prompt):
    url = "http://localhost:11434/api/generate"
    data = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": True}
    full_response = ""
    try:
        log(f"   🧠 {OLLAMA_MODEL} is thinking...", "INFO")
        with requests.post(url, json=data, stream=True, timeout=300) as response:
            if response.status_code != 200:
                log(f"Ollama error: {response.status_code}", "ERROR")
                return ""
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    full_response += chunk.get("response", "")
                    if len(full_response) % 200 < 5: print(".", end="", flush=True)
        print("\n")
        return full_response
    except Exception as e:
        log(f"\nOllama connection failed: {e}", "ERROR")
        return ""

def extract_code_block(response):
    if "```python" in response:
        return response.split("```python")[1].split("```")[0]
    elif "```" in response:
        return response.split("```")[1].split("```")[0]
    return response

# --- MODULES ---

def check_production_health():
    """☁️ Cloud Sentinel"""
    log("Checking Production System Health (Fly.io)...", "INFO")
    res = run_command("fly status -a nuzantara-rag --json", capture=True)
    if res and res.returncode == 0:
        try:
            data = json.loads(res.stdout)
            machines = data.get("Machines", [])
            active_count = sum(1 for m in machines if m.get("state") == "started")
            sleeping_count = sum(1 for m in machines if m.get("state") == "stopped" and (m.get("events", [{}])[0].get("request", {}).get("exit_event", {}).get("requested_stop") or m.get("events", [{}])[0].get("type") == "update"))
            
            if active_count > 0: log(f"Production: {active_count}/{len(machines)} active.", "SUCCESS")
            elif sleeping_count == len(machines): log("Production: SLEEPING (Auto-Stop).", "INFO")
            else: log("Production: CRASHED/UNKNOWN State!", "ERROR")
        except: log("Fly.io status parse error.", "WARNING")
    else: log("Fly.io unreachable.", "ERROR")

def auto_clean(files):
    """🧹 Auto-Clean"""
    if not files: return
    log(f"Cleaning {len(files)} files...", "INFO")
    files_str = " ".join([f'\"{str(f)}\"' for f in files])
    venv = f"source {BACKEND_DIR}/.venv/bin/activate"
    run_command(f"{venv} && ruff check --fix {files_str}", cwd=PROJECT_ROOT)

def forge_skeletons(files, refine=False):
    """🏗️ Test Forge"""
    created = []
    for f in files:
        if "backend/services" in str(f) or "backend/app/routers" in str(f):
            try:
                abs_s = f.resolve()
                rel = abs_s.relative_to((BACKEND_DIR/"backend").resolve())
                test_p = TESTS_DIR / rel.parent / f"test_{rel.name}"
                
                # Check if exists or create
                if not test_p.exists():
                    log(f"Forging: {test_p.name}", "INFO")
                    test_p.parent.mkdir(parents=True, exist_ok=True)
                    with open(test_p, "w") as tf:
                        tf.write("import pytest\n@pytest.mark.skip(reason='skeleton')\ndef test_stub(): assert True")
                    created.append(test_p)
                
                # Refine immediately if requested and skeleton detected
                if refine and test_p.exists():
                    content = open(test_p).read()
                    if "test_stub" in content or "Auto-generated skeleton" in content:
                        refine_test(test_p)
                        created.append(test_p) # Add to list to run it later

            except Exception as e: pass
    return created

# ... (update call in overlord_main) ...
    # 4. Forge & Refine Skeletons
    new_tests = forge_skeletons(files, refine=True) # Pass refine flag (assume true if arg present, wait fixing main)

def fix_import_error(test_path, error_log):
    """💀 Terminator Protocol: Deterministically fix imports."""
    if "ModuleNotFoundError" not in error_log:
        return False
    
    try:
        # Extract missing module name
        missing_mod = error_log.split("No module named '")[1].split("'")[0]
        log(f"Terminator detecting missing module: {missing_mod}", "WARNING")
        
        # Guess file name (last part)
        guess_name = missing_mod.split(".")[-1] + ".py"
        
        # Hunt for the real file
        candidates = list(PROJECT_ROOT.rglob(guess_name))
        
        # If not found, try fuzzy match (maybe 'burnout_detector_service' -> 'burnout_detector.py')
        if not candidates and "_service" in guess_name:
            stripped_name = guess_name.replace("_service.py", ".py")
            candidates = list(PROJECT_ROOT.rglob(stripped_name))
            
        if not candidates:
            log(f"Terminator could not locate real file for {guess_name}", "ERROR")
            return False
            
        real_file = candidates[0]
        
        # Calculate correct import path
        # from /Users/.../apps/backend-rag/backend/services/analytics/burnout_detector.py
        # to backend.services.analytics.burnout_detector
        rel_path = real_file.relative_to(PROJECT_ROOT / "apps/backend-rag")
        correct_import = str(rel_path).replace("/", ".").replace(".py", "")
        
        log(f"Terminator found target: {correct_import}", "SUCCESS")
        
        # Rewrite the test file
        with open(test_path, "r") as f:
            lines = f.readlines()
            
        new_lines = []
        fixed = False
        for line in lines:
            if missing_mod in line and ("import" in line or "from" in line):
                # Replace the bad import with the good one
                # We need to be careful. If it's 'from X import Y', we replace X
                if "from" in line:
                    parts = line.split("import")
                    new_lines.append(f"from {correct_import} import{parts[1]}")
                else:
                    new_lines.append(f"import {correct_import}\n")
                fixed = True
                log(f"Terminator surgically replaced import.", "SUCCESS")
            else:
                new_lines.append(line)
                
        if fixed:
            with open(test_path, "w") as f:
                f.writelines(new_lines)
            return True
            
    except Exception as e:
        log(f"Terminator malfunction: {e}", "ERROR")
        
    return False

def refine_test(test_path, error_log=None):
    """🧠 AI Refinement & Repair with Deep Context"""
    
    # PHASE 1: TERMINATOR (Deterministic Fix)
    if error_log and fix_import_error(test_path, error_log):
        return True
        
    # PHASE 2: QWEN (AI Fallback)
    log(f"Refining/Repairing: {test_path.name}...", "INFO")
    # ... rest of Qwen logic ...

    
    # Identify source file
    test_name = test_path.name.replace("test_", "")
    source_path = None
    for p in (BACKEND_DIR/"backend").rglob(test_name):
        source_path = p
        break
    
    context_files = {}
    if source_path:
        with open(source_path, "r") as f: context_files["SOURCE"] = f.read()
    
    # Analyze error for missing modules
    hint = ""
    if error_log and "ModuleNotFoundError" in error_log:
        try:
            missing_mod = error_log.split("No module named '")[1].split("'")[0]
            real_path = find_real_path(missing_mod)
            if real_path:
                hint = f"\nHINT: The module '{missing_mod}' might be located at '{real_path.relative_to(PROJECT_ROOT)}'. Adjust imports."
                with open(real_path, "r") as f: context_files["DEPENDENCY"] = f.read()[:1000] # Snippet
        except: pass

    # Build Prompt for Qwen
    prompt = f"Sei un Senior QA Engineer. Correggi il test pytest che fallisce.\n"
    if error_log:
        prompt += f"ERROR LOG:\n{error_log}\n"
    
    # Add context
    source_name = test_path.name.replace("test_", "")
    candidates = list((BACKEND_DIR/"backend").rglob(source_name))
    if candidates:
        with open(candidates[0], "r") as f:
            prompt += f"SOURCE CODE:\n{f.read()}\n"
            
    prompt += "\nRestituisci SOLO il codice Python completo del test corretto."
    
    # Generate with Qwen
    new_code = extract_code_block(ollama_generate(prompt))
    
    # TERMINATOR SANITIZATION (Post-Processing)
    # Scan new_code for bad imports and fix them before writing
    sanitized_lines = []
    if new_code.strip():
        for line in new_code.splitlines():
            if ("import" in line or "from" in line) and "backend." in line:
                # Check if module exists
                try:
                    # naive extraction of module path
                    mod_name = line.split("import")[0].replace("from", "").strip()
                    # if simple import
                    if not mod_name: mod_name = line.split("import")[1].strip()
                    
                    # Try to find it
                    if not find_real_path(mod_name):
                        # It's missing! Try to find real one
                        guess_name = mod_name.split(".")[-1] + ".py"
                        candidates = list(PROJECT_ROOT.rglob(guess_name))
                        if not candidates and "_service" in guess_name:
                             candidates = list(PROJECT_ROOT.rglob(guess_name.replace("_service", "")))
                        
                        if candidates:
                            real_file = candidates[0]
                            rel_path = real_file.relative_to(PROJECT_ROOT / "apps/backend-rag")
                            correct_import = str(rel_path).replace("/", ".").replace(".py", "")
                            # Replace in line
                            line = line.replace(mod_name, correct_import)
                            log(f"Terminator corrected AI import: {mod_name} -> {correct_import}", "SUCCESS")
                except: pass
            sanitized_lines.append(line)
            
        with open(test_path, "w") as f: f.write("\n".join(sanitized_lines))
        return True
    return False

def run_tests_and_repair(test_files):
    """Test Runner & Self-Healer"""
    if not test_files: return
    venv = f"source {BACKEND_DIR}/.venv/bin/activate"
    # ... rest of logic ...

def run_tests_and_repair(test_files):
    """Test Runner & Self-Healer"""
    if not test_files: return
    venv = f"source {BACKEND_DIR}/.venv/bin/activate"
    
    for test_f in test_files:
        log(f"Testing {test_f.name}...", "INFO")
        cmd = f"{venv} && PYTHONPATH=. pytest {str(test_f)}"
        res = run_command(cmd, cwd=BACKEND_DIR)
        
        if res.returncode == 0:
            log(f"✅ {test_f.name} PASSED", "SUCCESS")
        else:
            log(f"❌ {test_f.name} FAILED. Attempting Repair...", "WARNING")
            repaired = False
            for attempt in range(MAX_REPAIR_ATTEMPTS):
                if refine_test(test_f, res.stdout + res.stderr):
                    # Retry
                    res_retry = run_command(cmd, cwd=BACKEND_DIR)
                    if res_retry.returncode == 0:
                        log(f"🩹 {test_f.name} REPAIRED and PASSED!", "SUCCESS")
                        repaired = True
                        break
                    else:
                        log(f"Attempt {attempt+1} failed.", "WARNING")
            
            if not repaired:
                log(f"💀 {test_f.name} could not be repaired.", "ERROR")

# --- MAIN LOOP ---
def overlord_main(path_arg=None, forge=False, refine=False):
    log("🛡️  OVERLORD PROTOCOL v2 STARTED", "HEADER")
    
    # 1. Cloud Check
    check_production_health()
    
    # ... (target id logic) ...
    if path_arg:
        p = Path(path_arg)
        files = [p] if p.is_file() else list(p.rglob("*.py"))
    else:
        res = run_command("git status --porcelain", cwd=PROJECT_ROOT)
        files = []
        if res:
            for l in res.stdout.splitlines():
                if l.strip().endswith(".py"):
                    files.append(PROJECT_ROOT / l[3:].strip().replace('"',''))
    
    if not files:
        log("No target files.", "SUCCESS")
        return

    # 3. Clean
    auto_clean(files)
    
    # 4. Forge & Refine Skeletons
    new_tests = []
    if forge:
        new_tests = forge_skeletons(files, refine=refine)
    
    # Identify relevant tests (existing + new)
    tests_to_run = set(new_tests)
    for f in files:
        # If input is a test, run it
        if "tests/" in str(f): 
            tests_to_run.add(f)
        
        # If input is source, find test
        try:
            abs_s = f.resolve()
            rel = abs_s.relative_to((BACKEND_DIR/"backend").resolve())
            test_p = TESTS_DIR / rel.parent / f"test_{rel.name}"
            if test_p.exists():
                tests_to_run.add(test_p)
                # Refine existing skeletons if requested
                if forge and refine:
                    content = open(test_p).read()
                    if "test_stub" in content or "Auto-generated skeleton" in content:
                        refine_test(test_p)
        except: pass

    # 5. Run & Repair
    run_tests_and_repair(list(tests_to_run))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?")
    parser.add_argument("--forge", action="store_true")
    parser.add_argument("--refine", action="store_true")
    args = parser.parse_args()
    
    overlord_main(args.path, args.forge, args.refine)