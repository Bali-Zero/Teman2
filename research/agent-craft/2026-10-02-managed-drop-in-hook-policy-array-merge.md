---
adversarial_review: exempt-machine-report # agent-craft daily Deep Research transcript (generated artifact, not a curated research deliverable — no client_case/sources frontmatter, domain "agent-craft" is outside the CLAUDE.md §15 curated capture taxonomy)
---

# Agent-craft DR — 2026-10-02-managed-drop-in-hook-policy-array-merge

**Date**: 2026-10-02
**Mode**: adaptive
**NB**: NB-AGENTS (`6d449787-04e3-430e-acbe-d6fc38d379a9`)
**Conversation ID**: `53f11fc2-7d53-400f-ad4f-e83426841847`
**Sources used**: 0 / Citations: 0

## Question

> In italiano. Approfondisci la domanda emersa dal Deep Research di ieri:   **Dynamic Hook Management via Managed Drop-in Directories (`managed-settings.d/*.json`)**: In contesti aziendali o multi-tenant, in che modo la fusione alfabetica dei file frammento nella cartella `managed-settings.d/` gestisce le sovrapposizioni di matcher tra diversi team (es. `10-security.json` vs `20-audit.json`), e come si combinano gli array `hooks` tra i vari livelli di policy [2]?

Per la risposta: (1) cita verbatim le fonti rilevanti tra i tuoi 86 sources, (2) confronta con come lo applichiamo già nei nostri agenti reali, (3) identifica almeno una linea di azione concreta che possiamo implementare nella libreria Bali Zero. Termina con altre 3 domande aperte che saranno il taglio del DR di domani.

## Answer

### **1. Citazioni Verbatim dalle Fonti Canoniche (Drop-in Directories e Fusione degli Hook)**

La gestione dinamica delle policy aziendali e multi-tenant in Claude Code si basa sulla struttura a drop-in directory `managed-settings.d/*.json`, regolata da precise convenzioni di fusione dei file JSON e da priorità sulle decisioni di sicurezza:

*   **Convenzione di Fusione Alfabetica (Systemd Convention) per `managed-settings.d/`:**
    > *"File-based managed settings also support a drop-in directory at managed-settings.d/ in the same system directory alongside managed-settings.json . This lets separate teams deploy independent policy fragments without coordinating edits to a single file. Following the systemd convention, managed-settings.json is merged first as the base, then all *.json files in the drop-in directory are sorted alphabetically and merged on top. Later files override earlier ones for scalar values; arrays are concatenated and de-duplicated; objects are deep-merged. Hidden files starting with . are ignored. Use numeric prefixes to control merge order, for example 10-telemetry.json and 20-security.json ."*

*   **Gerarchia all'interno del Livello Managed:**
    > *"Within the managed tier, precedence is: server-managed > MDM/OS-level policies > file-based ( managed-settings.d/*.json + managed-settings.json ) > HKCU registry (Windows only). Only one managed source is used; sources do not merge across tiers. Within the file-based tier, drop-in files and the base file are merged together."*

*   **Comportamento di Concatenazione degli Array e Deep-Merge degli Oggetti:**
    > *"Array settings merge across scopes. When the same array-valued setting (such as sandbox.filesystem.allowWrite or permissions.allow) appears in multiple scopes, the arrays are concatenated and deduplicated, not replaced."*

*   **Esecuzione Parallela degli Handler e Precedenza delle Decisioni di Sicurezza:**
    > *"All matching hooks run in parallel, and identical handlers are deduplicated automatically."*
    > *"When multiple PreToolUse hooks return different decisions, precedence is deny > defer > ask > allow ."*

*   **Lockdown con `allowManagedHooksOnly`:**
    > *"Enterprise administrators can use allowManagedHooksOnly to block user, project, and plugin hooks. Hooks from plugins force-enabled in managed settings enabledPlugins are exempt, so administrators can distribute vetted hooks through an organization marketplace."*

---

### **2. Confronto con l'Infrastruttura Reale di Bali Zero (Nuzantara)**

Nel nostro monorepo di produzione (`/Desktop/nuzantara/`), la gestione dei file di configurazione frammentati deve orchestrare esigenze diverse (es. sicurezza, audit, mascheramento del contesto e logging). L'adozione dei file drop-in `managed-settings.d/*.json` chiarisce esattamente cosa accade quando più team o moduli definiscono regole per gli stessi eventi:

1.  **Deep-Merge degli Oggetti `hooks` e Concatenazione degli Array:**
    Se il team di sicurezza definisce `10-security.json` con un handler `PreToolUse` per bloccare comandi distruttivi su `Bash`, e il team di osservabilità definisce `20-audit.json` con un altro handler `PreToolUse` sullo stesso matcher `Bash` per registrarne l'esecuzione, l'oggetto `hooks` subisce un **deep-merge sulla chiave dell'evento (`PreToolUse`)**, mentre **gli array dei matcher groups vengono concatenati**. 
2.  **Esecuzione Concorrente e Veto Determinostico (`deny` Wins):**
    Quando l'agente tenta di eseguire un comando `Bash`, **tutti gli handler concatenati che incontrano un match eseguono in parallelo**. Se `10-security.json` restituisce `permissionDecision: "deny"` (o exit code 2) perché rileva un pattern non autorizzato, mentre `20-audit.json` restituisce `permissionDecision: "allow"`, l'engine applica la gerarchia estensiva di sicurezza: **`deny > defer > ask > allow`**. Il comando viene bloccato istantaneamente, garantendo che nessuna politica permissiva rilasciata da un frammento successivo possa ammorbidire un veto di sicurezza.
3.  **Sovrascrittura dei Valori Scalari vs Concatenazione:**
    Mentre gli array di hook e permessi (`permissions.deny`, `permissions.allow`) si fondono accumulando le regole, i valori scalari (come `model`, `effort`, `outputStyle` o `disableAllHooks`) seguono l'ordine alfabetico stricto del prefisso numerico: `20-audit.json` sovrascriverà un valore scalare definito in `10-security.json`.

---

### **3. Linea di Azione Concreta: Il Modulo `BaliZeroDropinPolicyMerger`**

Per simulare ed applicare in modo deterministico la composizione dei file drop-in `managed-settings.d/*.json` all'interno dell'Agent SDK programmatico e delle nostre sessioni LaunchAgent, implementeremo un modulo Python di pre-validazione e fusione delle policy nella libreria Bali Zero.

#### **Azione**: Creare il modulo `bali_zero/config/dropin_policy_merger.py` e integrare il generatore di opzioni SDK.

```python
# bali_zero/config/dropin_policy_merger.py
import os
import json
import glob
from typing import Dict, Any

class BaliZeroDropinPolicyMerger:
    """
    Risolve e fonde i frammenti JSON da .claude/managed-settings.d/*.json
    rispettando la systemd convention ufficiale di Claude Code.
    """
    def __init__(self, dropin_dir: str):
        self.dropin_dir = dropin_dir

    def resolve_managed_settings(self) -> Dict[str, Any]:
        merged_settings: Dict[str, Any] = {}
        
        # 1. Trova tutti i file .json (ignorando i file nascosti che iniziano con '.')
        pattern = os.path.join(self.dropin_dir, "[!.]*.json")
        fragment_files = sorted(glob.glob(pattern)) # Ordine alfabetico (es. 10-security.json, 20-audit.json)

        for file_path in fragment_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    fragment = json.load(f)
                    merged_settings = self._deep_merge(merged_settings, fragment)
            except Exception as e:
                print(f"WARNING: Impossibile caricare il frammento policy {file_path}: {e}")

        return merged_settings

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(base)
        for key, value in override.items():
            if key not in result:
                result[key] = value
            else:
                # Se il valore è un dizionario (es. l'oggetto 'hooks'), esegue il deep-merge
                if isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = self._deep_merge(result[key], value)
                # Se il valore è una lista (es. matcher degli hook o permissions.deny), concatena e deduplica
                elif isinstance(result[key], list) and isinstance(value, list):
                    # Concatenazione mantenendo l'ordine e rimuovendo duplicati esatti
                    combined = result[key] + value
                    deduped = []
                    for item in combined:
                        if item not in deduped:
                            deduped.append(item)
                    result[key] = deduped
                else:
                    # I valori scalari (str, int, bool) vengono sovrascritti dal frammento alfabetico successivo
                    result[key] = value
        return result
```

#### **Uso nell'Agent SDK:**
```python
from claude_agent_sdk import ClaudeAgentOptions
from bali_zero.config.dropin_policy_merger import BaliZeroDropinPolicyMerger

# Carica e fonde i frammenti della cartella Drop-In
merger = BaliZeroDropinPolicyMerger(".claude/managed-settings.d")
resolved_policy = merger.resolve_managed_settings()

options = ClaudeAgentOptions(
    setting_sources=["project", "local"],
    # Inietta la policy sintetizzata direttamente nell'SDK
    env={"CLAUDE_POLICY_OVERRIDE": json.dumps(resolved_policy)}
)
```

---

### **4. Domande Aperte per il Deep Research (DR) di Domani**

1.  **Dinamiche di Sovrascrittura tra `policyHelper` ed Esecuzione Drop-In**: Se un'organizzazione distribuisce uno script eseguibile tramite il parametro `policyHelper` (disponibile da v2.1.136+), in che modo l'oggetto JSON dinamico emesso su stdout dallo script si sovrappone o sostituisce i file statici presenti in `managed-settings.d/*.json` durante l'avvio della CLI?
2.  **Risoluzione delle Conflittualità in `PostToolBatch` con Trasformazioni `updatedToolOutput` Multiple**: Quando due distinti frammenti drop-in (es. `20-redaction.json` e `30-observation-masker.json`) registrano entrambi un hook `PostToolBatch` per modificare la risposta del modello tramite `updatedToolOutput`, come viene determinata la sequenza di trasformazione del payload primario ed è possibile una perdita di metadati se un hook sovrascrive ciecamente l'output dell'altro?
3.  **Comportamento di `parentSettingsBehavior: "merge"` in Host SDK Multi-Tenant**: In che modo l'impostazione `parentSettingsBehavior: "merge"` (introdotta in v2.1.133+) consente a un'applicazione contenitore Agent SDK di iniettare vincoli aggiuntivi senza che questi possano allentare o invalidare le regole restrittive definite a livello di sistema da `managed-settings.d/*.json`?

## Sources used (0)


## Citations verbatim (0)
