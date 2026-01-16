#!/usr/bin/env python3
import os
import subprocess
import shutil
from pathlib import Path

def run_cmd(cmd):
    """Esegue un comando e ritorna l'output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "Timeout", 1
    except Exception as e:
        return "", str(e), 1

def get_size(path):
    """Ritorna la dimensione di un file/directory"""
    try:
        if os.path.isfile(path):
            return os.path.getsize(path)
        elif os.path.isdir(path):
            total = 0
            for dirpath, dirnames, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total += os.path.getsize(fp)
                    except:
                        pass
            return total
    except:
        pass
    return 0

def format_size(size):
    """Formatta la dimensione in formato leggibile"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size:.1f}TB"

print("=== PULIZIA CONTINUA ===")
print(f"Data: {subprocess.run('date', shell=True, capture_output=True, text=True).stdout.strip()}\n")

# 1. Spazio disco
print("1. Spazio disco attuale:")
stdout, stderr, code = run_cmd("df -h /")
if stdout:
    print(stdout.split('\n')[-1])
print()

# 2. Rimuovi backup tar.gz
print("2. Rimozione backup tar.gz...")
backup_dir = Path(".cowork-optimization/backups/sessions")
if backup_dir.exists():
    total_freed = 0
    for tar_file in backup_dir.glob("*.tar.gz"):
        size = get_size(tar_file)
        try:
            tar_file.unlink()
            total_freed += size
            print(f"   ✅ Rimosso: {tar_file.name} ({format_size(size)})")
        except Exception as e:
            print(f"   ⚠️  Errore rimozione {tar_file.name}: {e}")
    if total_freed > 0:
        print(f"   ✅ Totale liberato: {format_size(total_freed)}")
else:
    print("   ℹ️  Directory backup non trovata")
print()

# 3. Trova file grandi
print("3. File grandi nel progetto (>50MB):")
large_files = []
for root, dirs, files in os.walk("."):
    # Skip .git e node_modules
    dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules']]
    for file in files:
        filepath = os.path.join(root, file)
        try:
            size = os.path.getsize(filepath)
            if size > 50 * 1024 * 1024:  # >50MB
                large_files.append((filepath, size))
        except:
            pass

large_files.sort(key=lambda x: x[1], reverse=True)
for filepath, size in large_files[:10]:
    print(f"   {format_size(size):>8} - {filepath}")
print()

# 4. Analizza node_modules
print("4. Analisi node_modules:")
node_modules_dirs = []
for root, dirs, files in os.walk("apps"):
    if 'node_modules' in dirs:
        nm_path = os.path.join(root, 'node_modules')
        size = get_size(nm_path)
        if size > 0:
            node_modules_dirs.append((nm_path, size))

node_modules_dirs.sort(key=lambda x: x[1])
for path, size in node_modules_dirs:
    print(f"   {format_size(size):>8} - {path}")
print()

# 5. Analizza .next
print("5. Analisi cartelle .next:")
next_dirs = []
for root, dirs, files in os.walk("."):
    if '.next' in dirs:
        next_path = os.path.join(root, '.next')
        size = get_size(next_path)
        if size > 0:
            next_dirs.append((next_path, size))

next_dirs.sort(key=lambda x: x[1])
for path, size in next_dirs:
    print(f"   {format_size(size):>8} - {path}")
print()

# 6. Pulizia cache pip
print("6. Pulizia cache pip...")
stdout, stderr, code = run_cmd("pip cache purge")
if code == 0:
    print("   ✅ Cache pip pulita")
else:
    print("   ℹ️  pip non disponibile o già pulito")
print()

# 7. Verifica spazio finale
print("=== STATO FINALE ===")
stdout, stderr, code = run_cmd("df -h /")
if stdout:
    print(stdout.split('\n')[-1])
print()

# 8. Memoria RAM
print("=== MEMORIA RAM ===")
stdout, stderr, code = run_cmd("vm_stat")
if stdout:
    for line in stdout.split('\n'):
        if 'Pages free' in line or 'Pages inactive' in line:
            print(f"   {line.strip()}")

print("\n✅ Pulizia completata!")
