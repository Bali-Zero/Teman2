# Unified OpenClaw Setup — ZERO + ZANTARA (Feb 27, 2026)

## Status: READY TO ACTIVATE

✅ Configuration deployed | ✅ Verification script created | 🔄 Syncthing sync pending

## Agent Identities

- **ZERO** (MacBook Pro, 192.168.0.16): Master Commander, `authority: true`
- **ZANTARA** (Mac Air, 192.168.0.17): Field Agent, `authority: false`, subordinate to ZERO
- **Command Chain**: All operations signed by ZERO, even executed by ZANTARA

## Unified Memory Path

```
~/.openclaw/workspace/
├── MEMORY.md                    # Shared curated knowledge
├── memory/
│   ├── ZERO.sqlite              # ZERO sessions only
│   ├── ZANTARA.sqlite           # ZANTARA sessions only
│   └── daily logs (append-only)
└── _backup/                     # Auto-backup before flush
```

## Configuration Summary

Both agents have identical config except identity/authority:

**ZERO (Pro):**

- `agents.identity.name: "ZERO"`
- `agents.identity.authority: true`
- `agents.identity.role: "Master Commander (Nuzantara)"`

**ZANTARA (Air):**

- `agents.identity.name: "ZANTARA"`
- `agents.identity.authority: false`
- `agents.identity.commandedBy: "ZERO"`

**Both (identical):**

- `agents.defaults.workspace: "~/.openclaw/workspace"`
- `agents.defaults.model.primary: "google-gemini-cli/gemini-3-pro"`
- `plugins.slots.memory: "memory-core"`
- `meta.unifiedMemory: true`

## Next Step: Activate Syncthing

1. Open http://127.0.0.1:8384 on Pro
2. Click "Add Folder"
3. Path: `/Users/nuzantara/.openclaw/workspace`
4. Folder type: Send & Receive
5. Rescan interval: 10s
6. Devices: air + pro
7. Accept on Air when prompted

## Testing (after Syncthing active)

- Test 1: ZERO updates MEMORY.md, verify ZANTARA sees it (5-10s sync)
- Test 2: ZANTARA reads unified memory via OpenClaw command
- Test 3: Verify .sqlite file isolation (no write conflicts)

## Key Settings

- Memory flush: 4000 tokens
- Heartbeat: 4h (auto-reconnect)
- Reload mode: hybrid
- Gateway: loopback-only
- Context: 1M tokens (Gemini 3 Pro)

---

**Deployed:** 2026-02-27 02:35 AM  
**Status:** Configuration complete, awaiting Syncthing activation
