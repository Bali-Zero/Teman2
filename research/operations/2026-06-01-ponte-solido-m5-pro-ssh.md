# Ponte solido M5↔Pro (SSH + DB + remote exec) — deep research 2026-06-01

> Fonti: 20 primarie (Tailscale docs/blog/issue tracker + mosh.org). 19 claim confermati / 25 verificati adversarial (3-voti). Workflow deep-research 102 agenti.
> Incrociato con diagnostica reale M5 (`/tmp/m5-net-diag-1519.txt`).

## TL;DR — la config raccomandata
**NON** usare il Tailscale SSH nativo. Usare: **Tailscale CLI Homebrew (tailscaled non-sandboxed) come overlay + OpenSSH classico (Remote Login macOS, porta 22) raggiunto via l'IP Tailscale stabile 100.x del Pro.**
- L'IP `100.x` non cambia mai al cambio WiFi/subnet → risolve il roaming
- L'overlay Tailscale è immune all'AP/Client Isolation (DERP è relay HTTPS in uscita) → risolve l'isolation
- Si evita il bug TCP-hang del Tailscale SSH nativo su macOS

## Findings verificati

### 1. Sandbox: solo tailscaled CLI può fare SSH server (HIGH)
La tabella varianti Tailscale: "Can be a Tailscale SSH server" → App Store=**no**, Standalone GUI=**no**, open-source tailscaled=**sì**. Anche la GUI standalone (non App Store) NON può ospitare il server SSH — **solo la CLI Homebrew**. La variante App Store non può nemmeno usare `tailscale ssh` come CLIENT ("must use regular ssh"). [tailscale.com/docs/concepts/macos-variants, /docs/features/tailscale-ssh, issue #4628]

### 2. Tailscale SSH richiede DUE cose (HIGH)
Flag device-side sull'host (`tailscale set --ssh`) + sezione ACL `ssh` nella admin console. Nessuna delle due da sola basta. La GUI sandboxed rifiuta proprio il flag device-side → l'opzione "solo ACL" è impossibile sul Mac sandboxed.

### 3. ping passa ma TCP-22 timeout = bug NOTO e IRRISOLTO (HIGH)
GitHub #15983 (Mac mini Sequoia, aperto 2025-05-15, **0 commenti maintainer**): `tailscale ping` pong OK ma TCP SSH/HTTP hang, `tcpdump -i tailscale0` mostra **zero pacchetti** ricevuti su :22. Issue sorelle #18967, #8985 confermano il pattern ricorrente. **Nessuna root-cause ufficiale.** Ipotesi più forte (community): **MTU/MSS black-holing** o bug MagicSock receive-path — NON la differenza ICMP-vs-TCP in sé (DERP trasporta entrambi).

### 4. Perché ICMP passa e UDP/TCP diretto no (HIGH)
Connessione diretta Tailscale richiede UDP hole-punching bidirezionale, che **fallisce sotto NAT simmetrico/hard** (source port randomizzato per ogni connessione). Senza UDP diretto → fallback DERP relay (più lento/fragile). MA: DERP trasporta sia ICMP sia TCP, quindi il fallback relay da solo NON spiega un timeout TCP COMPLETO mentre il ping passa → punta a MTU/MSS o bug MagicSock. [docs/reference/connection-types, kb/1257, nat-traversal blog]

### 5. Relay-first = meccanismo di robustezza (HIGH)
Tutte le connessioni partono via DERP poi fanno upgrade a diretta se il NAT lo permette. È ciò che fa sopravvivere il tunnel ai cambi subnet e all'AP isolation (DERP = relay HTTPS in uscita, immune all'isolation LAN).

### 6. Mosh NON aggira il TCP-22 rotto (HIGH)
Mosh fa PRIMA login via SSH/TCP-22, POI apre sessione UDP 60000-61000. Se TCP-22 è rotto, Mosh fallisce al bootstrap. Mosh aiuta il roaming SOLO dopo che SSH funziona. [mosh.org]

## INCROCIO coi dati reali M5 (2026-06-01)
- M5 Tailscale = GUI App Store sandboxed v1.98.2 → **conferma finding 1**: serve passare a CLI Homebrew
- `MappingVariesByDestIP: TRUE` = **NAT simmetrico** → conferma finding 4: P2P diretto impossibile, relay obbligato
- `PortMapping: vuoto` (no UPnP/PMP) = router ISP-locked → niente foratura NAT
- Nearest DERP Singapore + dopo cambio rete ping=timeout → relay fragile su questa rete
- **Doppio problema confermato**: (a) sandbox blocca SSH, (b) NAT ostile rende il relay instabile

## PIANO OPERATIVO (macOS giugno 2026)

### Fase 1 — su ENTRAMBE le macchine: passare a Tailscale CLI Homebrew
```bash
# esci dalla GUI App Store (barra menu) + disinstallala (Launchpad) — confligge col daemon
brew install tailscale
sudo brew services start tailscale          # avvia tailscaled non-sandboxed
sudo tailscale up --accept-routes           # auth browser, stessa tailnet
```
(NB: il conflitto GUI/CLI visto su M5 stasera = la GUI riparte da sola via login-item-helper. Disinstallare la .app, non solo chiuderla.)

### Fase 2 — server (Pro): OpenSSH classico, NON Tailscale SSH
```bash
sudo systemsetup -setremotelogin on   # gia' ON sul Pro (verificato)
# sshd ascolta :22, raggiungibile via IP Tailscale 100.107.22.111
```

### Fase 3 — client (M5): ssh via IP Tailscale stabile
```
Host pro
    HostName 100.107.22.111      # IP Tailscale, immune a cambi WiFi
    User nuzantara
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 30
    ServerAliveCountMax 3
```
DB query: `ssh pro 'sqlite3 ~/.claude/memory.db "SELECT ..."'`

### Fase 4 — se TCP-22 ancora hang (bug #15983): abbassa MTU
```bash
# su entrambe, trova utun di Tailscale poi:
sudo ifconfig utun<N> mtu 1280
```
Test PMTU black-holing. Se risolve → rendere persistente.

### Fase 5 — robustezza roaming: autossh o Mosh (DOPO che SSH funziona)
```bash
brew install autossh mosh
# autossh -M 0 pro   (riconnette al cambio rete)
# mosh pro           (sessione UDP sopravvive ai cambi IP) — solo se TCP-22 ok
```

## CAVEAT (dal report)
- #15983 OPEN senza fix ufficiale dal 2025-05-15: l'ipotesi MTU è inferenziale, non provata per questo sintomo
- Il reproducer #15983 era Mac→Ubuntu, non Mac→Mac (ma pattern corroborato)
- La GUI standalone Tailscale è stata REFUTATA come variante separata sufficiente — solo CLI tailscaled fa SSH server
- Open question: il tailscaled SSH server parte affidabile su Tahoe/26 Apple Silicon? (#18957 inconcludente) → OpenSSH-over-Tailscale è il path più sicuro

## Open questions
1. Root cause vera del TCP-hang macOS (#15983): MTU? MagicSock? SIP/firewall? L'abbassamento MTU a 1280 ripristina empiricamente il TCP?
2. tailscaled SSH server affidabile su Tahoe/26 ARM giugno 2026?
3. "Peer relay" (tier 2026 intermedio DERP↔diretto) migliora il caso 2-Mac roaming?
4. WireGuard manuale come alternativa zero-cost che evita del tutto il bug Tailscale macOS?
