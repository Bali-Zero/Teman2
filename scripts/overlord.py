#!/usr/bin/env python3
import subprocess
import sys
import json
from pathlib import Path
import time

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_DIR = PROJECT_ROOT / "apps" / "backend-rag"
SENTINEL_LOG = PROJECT_ROOT / "OVERLORD_LOG.md"

COLORS = {
    "HEADER": "\033[95m",
    "OKBLUE": "\033[94m",
    "OKCYAN": "\033[96m",
    "OKGREEN": "\033[92m",
    "WARNING": "\033[93m",
    "FAIL": "\033[91m",
    "ENDC": "\033[0m",
    "BOLD": "\033[1m",
    "UNDERLINE": "\033[4m",
}

def log(message, level="INFO"):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    color = COLORS["OKBLUE"]
    if level == "SUCCESS":
        color = COLORS["OKGREEN"]
    elif level == "WARNING":
        color = COLORS["WARNING"]
    elif level == "ERROR":
        color = COLORS["FAIL"]
    elif level == "HEADER":
        color = COLORS["HEADER"]

    print(f"{color}[{level}] {message}{COLORS['ENDC']}")
    
    # Notify Mac OS if it's an error or success
    if level in ["ERROR", "SUCCESS", "WARNING"]:
        try:
            # Escape double quotes for shell
            safe_msg = message.replace('"', '\\"')
            subprocess.run(f'osascript -e \'display notification \"{safe_msg}\" with title \"Nuzantara Overlord\" subtitle \"{level}\"\' ', shell=True)
        except:
            pass

    with open(SENTINEL_LOG, "a") as f:
        f.write(f"- **{timestamp}** [{level}]: {message}\n")

def run_command(command, cwd=None, capture=True):
    try:
        result = subprocess.run(
            command, cwd=cwd, shell=True, text=True, capture_output=capture
        )
        return result
    except Exception as e:
        log(f"Execution failed: {e}", "ERROR")
        return None

def get_target_files(path=None):
    if path:
        path_obj = Path(path)
        if path_obj.is_file():
            return [path_obj]
        return list(path_obj.rglob("*.py"))

    res = run_command("git status --porcelain", cwd=PROJECT_ROOT)
    if not res:
        return []

    files = []
    for line in res.stdout.splitlines():
        if line.strip():
            path_str = line[3:].strip()
            # Handle quoted paths from git if they exist
            if path_str.startswith('"') and path_str.endswith('"'):
                path_str = path_str[1:-1]
            if path_str.endswith(".py"):
                files.append(PROJECT_ROOT / path_str)
    return files

def check_production_health():
    log("Checking Production System Health (Fly.io)...", "INFO")
    cmd = "fly status -a nuzantara-rag --json"
    res = run_command(cmd, capture=True)

    if res and res.returncode == 0:
        try:
            data = json.loads(res.stdout)
            machines = data.get("Machines", [])
            active_count = 0
            sleeping_count = 0
            crashed_count = 0
            
            for m in machines:
                state = m.get("state")
                events = m.get("events", [])
                last_event = events[0] if events else {}
                exit_code = 0
                requested_stop = False
                
                if last_event.get("type") == "exit":
                    exit_info = last_event.get("request", {}).get("exit_event", {})
                    exit_code = exit_info.get("exit_code", 0)
                    requested_stop = exit_info.get("requested_stop", False)

                if state == "started":
                    active_count += 1
                elif state == "stopped":
                    if exit_code == 143 or requested_stop:
                        sleeping_count += 1
                    else:
                        crashed_count += 1
            
            total = len(machines)
            if active_count > 0:
                log(f"Production Backend: {active_count}/{total} active. ({sleeping_count} sleeping)", "SUCCESS")
            elif sleeping_count == total:
                log("Production Backend: SLEEPING (Auto-Stop active).", "INFO")
            elif crashed_count > 0:
                log(f"Production Backend CRASHED: {crashed_count} machines failed!", "ERROR")
            else:
                log(f"Production Status: {active_count}/{total} active", "WARNING")
        except:
            log("Parsing Fly.io status failed", "WARNING")
    else:
        log("Fly.io offline or unreachable", "ERROR")

def overlord_scan(target_path=None):
    log("OVERLORD PROTOCOL INITIATED", "HEADER")
    check_production_health()
    
    target_files = get_target_files(target_path)
    if not target_files:
        log("No changes detected. System clean.", "SUCCESS")
        return

    log(f"Analyzing {len(target_files)} files...", "WARNING")
    files_str = " ".join([f'"{str(f)}"' for f in target_files])
    venv_activate = f"source {BACKEND_DIR}/.venv/bin/activate"
    
    # 1. Auto-Fix
    log("Running Auto-Fix (Ruff)...")
    run_command(f"{venv_activate} && ruff check --fix {files_str}", cwd=PROJECT_ROOT)
    
    # 2. Targeted Testing
    log("Running tests...")
    tests_to_run = []
    for f in target_files:
        if "tests/" in str(f) and f.name.startswith("test_"):
            tests_to_run.append(str(f))

    if tests_to_run:
        res = run_command(f"{venv_activate} && pytest {' '.join(tests_to_run)}", cwd=BACKEND_DIR)
        if res and res.returncode == 0:
            log("Tests PASSED.", "SUCCESS")
        else:
            log("Tests FAILED.", "ERROR")
    else:
        # Fallback to general sentinel if no specific tests
        res = run_command("./sentinel", cwd=PROJECT_ROOT)
        if res and res.returncode == 0:
            log("Sentinel PASSED.", "SUCCESS")
        else:
            log("Sentinel FAILED.", "ERROR")

    log("Overlord cycle complete.", "HEADER")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    overlord_scan(target)