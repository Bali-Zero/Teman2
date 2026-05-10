#!/usr/bin/env python3
"""Generate config/job-ownership.yaml from Pro+Mini plist inventory.

Heuristics for classification:
- side_effects:
    - 'brevo' if label matches *newsletter*|*weekly-digest*|*renewal*
    - 'telegram' if family in matagaruda|garuda|siano OR name contains
      *briefing*|*alert*|*watcher*|*regulatory*
    - 'social' if label matches *bz-daily-visual*|*ig-scraper*|*public-channel*
    - 'canva' if label matches *canva*|*visual-pipeline*
    - 'drive' if label matches *drive-sync*|*backup*|*gdrive*
    - 'file_only' if other batch
    - 'none' for monitors/watchers
- idempotent: false for brevo/social/canva (irreversible);
  true for file_only/none/most monitors;
  unknown otherwise (require manual review)
- resource_class:
    - 'residence' if RunAtLoad=true AND StartInterval is empty (long-running)
    - 'continuous' if StartInterval <= 600 (10 min)
    - 'cron_light' if cron-like
    - 'codex' if name contains 'codex'
    - 'ollama' if name contains 'translate' (uses gemma) OR known Ollama batch
    - 'sync' if name contains *sync*|*memory-sync*|*git-pull*
- candidate_migrate:
    - false for residence (Cluster A) AND wr2.queue/supervisor/pg-proxy/canva-renderer
    - false for sync daemons (Cluster B)
    - false for translate (Ollama gemma4 doesn't fit)
    - false for cell/organism residents
    - true for cron_light/cron_heavy non-Pro-bound
- owner: pro by default; mini-only-undocumented for plists only on Mini;
  both-conflict if same label exists on both with different state.
"""
import re
import sys

PRO_TSV = "/tmp/pro-plists.tsv"
MINI_TXT = "/tmp/mini-plists.txt"
OUT = "/tmp/job-ownership.yaml"

# === Cluster A residence (NON-migrate, see spec §3 Cluster A) ===
CLUSTER_A_PATTERNS = [
    r"wr2\.(queue-server|supervisor|supervisor-watchdog|pg-proxy|canva-renderer|canva-oauth-watchdog|deploy-puller|plist-watchdog|measurer|sla-worker|fact-extractor|fact-checker|image-generator|draft-generator|trend-hunter|hardening)",
    r"^com\.cell\.",
    r"^com\.nuzantara\.organism\.",
    r"cell-observatory",
    r"observatory(-server|-export)?$",
    r"observatory$",
    r"meta-dispatcher",
    r"intel-dedup-gateway",
    r"nlm-bridge",
    r"claude-max-api",
    r"prime-tunnel",
    r"automap-(server|telegram|watchdog)",
    r"heartbeat-bridge",
    r"federation-alert-dispatcher",
    r"sentinel-aggregate",
    r"sentinel-meta-watchdog",
    r"^com\.nuzantara\.sentinel$",
    r"launchagent-state-bridge",
    r"openclaw-children-watchdog",
    r"supervisor-liveness-watchdog",
    r"zombie-hunter",
    r"cpu-monitor",
    r"disk-monitor",
    r"login-healthcheck",
    r"fly-restart-loop-detector",
    r"launchd-env-loader",
    r"^ai\.openclaw\.gateway$",
    r"^ai\.flowkit\.gateway$",
    r"post-publish-(poller|webhook)",
    r"cron-log-sentinel",
    r"research-sentinel",
    r"pg-organism-bridge",
    r"observatory$",
]

# === Cluster B sync (NOT migrate, already live) ===
CLUSTER_B_PATTERNS = [
    r"memory-sync-bidirectional",
    r"claude-config-sync",
    r"secrets-sync-mini",
    r"nuzantara-drive-sync",
    r"git-pull-main",
]

# === Hardcoded exceptions: stay on Pro by design (Postgres/Qdrant/KB) ===
PRO_BOUND_PATTERNS = [
    r"translate\.hourly",  # gemma4:26b, doesn't fit
    r"wr2\.(oracle|strategos|dossier-compiler|connector|newsletter|topic-selector)",  # Postgres queries
    r"vector-reindex-check",  # Qdrant Pro
    r"indexing-sweep",  # KB Pro
    r"sota\.m13",  # Postgres
    r"domain-mesh",  # depends on Pro org cells
    r"matagaruda\.bridge\.adaptive",  # Pro org dependency suspected
    r"matagaruda\.wr2-bridge",  # Pro WR2 dep
    r"^com\.openai\.atlas",  # ChatGPT desktop helper
    r"^com\.google\.",  # Google updater
    r"^homebrew\.mxcl\.",  # local services (Pro has postgresql@17, redis, ollama, syncthing)
]

# Family
def family_of(label):
    parts = label.split(".")
    if label.startswith("ai.openclaw"):
        return "openclaw"
    if label.startswith("ai.flowkit"):
        return "flowkit"
    if label.startswith("homebrew."):
        return "brew"
    if label.startswith("com.google."):
        return "google"
    if label.startswith("com.openai."):
        return "openai"
    if label.startswith("com.cell."):
        return "cell"
    if label.startswith("com.garuda."):
        return "garuda"
    if label.startswith("com.siano."):
        return "siano"
    if label.startswith("com.matagaruda."):
        return "matagaruda"
    if label.startswith("com.balizero."):
        return "balizero"
    if label.startswith("com.nuzantara."):
        return "nuzantara"
    return "other"

# Side-effects
def side_effects_of(label):
    se = set()
    if re.search(r"newsletter|weekly-digest|renewal", label):
        se.add("brevo")
    if re.search(r"briefing|alert|watcher|regulatory|reg-alert|public-channel|telegram", label):
        se.add("telegram")
    if re.search(r"bz-daily-visual|ig-scraper|public-channel", label):
        se.add("social")
    if re.search(r"canva|visual-pipeline", label):
        se.add("canva")
    if re.search(r"drive-sync|backup|gdrive", label):
        se.add("drive")
    if not se:
        # default for monitors/watchers
        if re.search(r"monitor|watcher|watchdog|sentinel|healthcheck|usage|cost|sweep|prune|gc|metrics|automations-reference", label):
            se.add("none")
        else:
            se.add("file_only")
    return sorted(se)

# Idempotency
def idempotent_of(label, side_effects):
    if "brevo" in side_effects or "social" in side_effects or "canva" in side_effects:
        return "false"  # external broadcast, not idempotent
    if "telegram" in side_effects:
        return "false"  # broadcast (telegram alerts CAN be deduped but assume worst)
    if "drive" in side_effects:
        return "true"  # rsync is idempotent
    if "file_only" in side_effects:
        return "unknown"
    if "none" in side_effects:
        return "true"
    return "unknown"

# Resource class
def resource_class_of(label, ral, si):
    if "codex" in label:
        return "codex"
    if "translate" in label and "hourly" in label:
        return "ollama"
    if re.search(r"sync|git-pull|secrets-sync|claude-config", label):
        return "sync"
    if ral == "true" and (si == "" or si is None):
        return "residence"
    try:
        si_int = int(si)
        if si_int <= 600:
            return "continuous"
    except (ValueError, TypeError):
        pass
    if "weekly" in label or "monthly" in label or "28d" in label:
        return "cron_light"  # weekly/monthly low-frequency
    return "cron_light"

# Schedule label
def schedule_of(label, ral, si):
    if ral == "true" and (si == "" or si is None):
        return "on_load"
    try:
        si_int = int(si)
        if si_int <= 60:
            return "continuous"
        if si_int <= 600:
            return "every_10min"
        if si_int <= 3700:
            return "hourly"
        return "interval"
    except (ValueError, TypeError):
        pass
    if "monthly" in label or "28d" in label:
        return "monthly"
    if "weekly" in label:
        return "weekly"
    if "daily" in label or "nightly" in label:
        return "daily"
    if "hourly" in label or "30min" in label:
        return "hourly"
    return "calendar"

def candidate_migrate(label, family, resource_class):
    # Check Pro-bound exceptions first (overrides everything)
    for pat in PRO_BOUND_PATTERNS:
        if re.search(pat, label):
            return "false"
    # Cluster A residence: never migrate
    for pat in CLUSTER_A_PATTERNS:
        if re.search(pat, label):
            return "false"
    # Cluster B sync: never migrate
    for pat in CLUSTER_B_PATTERNS:
        if re.search(pat, label):
            return "false"
    if family in ("brew", "google", "openai"):
        return "false"
    if resource_class == "residence":
        return "false"
    if resource_class == "sync":
        return "false"
    return "true"

def cluster_of(label, family, resource_class, candidate):
    for pat in CLUSTER_A_PATTERNS:
        if re.search(pat, label):
            return "A_residence_pro"
    for pat in CLUSTER_B_PATTERNS:
        if re.search(pat, label):
            return "B_sync"
    for pat in PRO_BOUND_PATTERNS:
        if re.search(pat, label):
            return "C_pro_bound_exception"
    if "codex" in label:
        return "D_codex"
    if family in ("brew", "google", "openai"):
        return "X_system"
    if candidate == "true":
        return "C_migrate_candidate"
    return "C_pro_bound_exception"

def main():
    pro = {}
    with open(PRO_TSV) as f:
        for line in f:
            parts = line.strip().split("|")
            if len(parts) < 4:
                continue
            label, active, ral, si = parts[0], parts[1], parts[2], parts[3]
            pro[label] = {"active": active, "ral": ral, "si": si}

    mini = set()
    with open(MINI_TXT) as f:
        for line in f:
            label = line.strip()
            if label:
                mini.add(label)

    all_labels = sorted(set(pro.keys()) | mini)

    out = []
    out.append("# config/job-ownership.yaml")
    out.append("# Source-of-truth per migrazione cron Pro->Mini.")
    out.append("# Generated 2026-05-10 by scripts/mini-migration/gen-inventory.py")
    out.append("# DO NOT edit `owner` field manually — only migrate-job.sh / rollback-job.sh.")
    out.append("# Other fields hand-curated as needed.")
    out.append("")
    out.append("schema_version: 1")
    out.append("generated_at: '2026-05-10T10:30:00+08:00'")
    out.append(f"pro_plist_count: {len(pro)}")
    out.append(f"mini_plist_count: {len(mini)}")
    out.append(f"both_count: {len(set(pro.keys()) & mini)}")
    out.append("")

    # Both-on-Pro-and-Mini (conflict candidates) FIRST
    conflicts = sorted(set(pro.keys()) & mini)
    if conflicts:
        out.append(f"# === {len(conflicts)} CONFLITTI: stesso label su Pro E Mini (ATTENZIONE) ===")
        out.append("")

    counts = {"A_residence_pro": 0, "B_sync": 0, "C_migrate_candidate": 0, "C_pro_bound_exception": 0, "D_codex": 0, "X_system": 0}

    out.append("jobs:")
    for label in all_labels:
        in_pro = label in pro
        in_mini = label in mini
        meta = pro.get(label, {"active": "n/a", "ral": "", "si": ""})
        active = meta["active"]
        ral = meta["ral"]
        si = meta["si"]
        family = family_of(label)
        se = side_effects_of(label)
        idem = idempotent_of(label, se)
        rc = resource_class_of(label, ral, si)
        sched = schedule_of(label, ral, si)
        cand = candidate_migrate(label, family, rc)
        cl = cluster_of(label, family, rc, cand)
        counts[cl] = counts.get(cl, 0) + 1

        if in_pro and in_mini:
            owner = "both-conflict"
        elif in_mini and not in_pro:
            owner = "mini-only-undocumented"
        elif in_pro and not in_mini:
            owner = "pro"

        # Pro state shown only if in_pro
        state = active if in_pro else "mini-only"

        notes_parts = []
        if owner == "both-conflict":
            notes_parts.append("CONFLICT: stesso label su entrambe macchine, decidere owner")
        if owner == "mini-only-undocumented":
            notes_parts.append("Migrazione precedente non documentata, era gia su Mini")
        notes = "; ".join(notes_parts) if notes_parts else ""

        se_yaml = "[" + ", ".join(se) + "]"
        notes_yaml = f' "{notes}"' if notes else ' ""'

        out.append(f"  {label}:")
        out.append(f"    owner: {owner}")
        out.append(f"    family: {family}")
        out.append(f"    cluster: {cl}")
        out.append(f"    state: {state}")
        out.append(f"    side_effects: {se_yaml}")
        out.append(f"    idempotent: {idem}")
        out.append(f"    resource_class: {rc}")
        out.append(f"    schedule: {sched}")
        out.append(f"    candidate_migrate: {cand}")
        out.append(f"    last_migrated: null")
        out.append(f"    git_sha: null")
        out.append(f"    notes:{notes_yaml}")
        out.append("")

    out.append("# === STATS ===")
    for k, v in counts.items():
        out.append(f"# {k}: {v}")

    with open(OUT, "w") as f:
        f.write("\n".join(out))

    print(f"Wrote {OUT} ({len(out)} lines)")
    print(f"Pro: {len(pro)} | Mini: {len(mini)} | Both: {len(conflicts)}")
    print("Cluster counts:")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    if conflicts:
        print(f"\nCONFLICTS ({len(conflicts)}):")
        for c in conflicts:
            print(f"  - {c}")

if __name__ == "__main__":
    main()
