# FAILOVER PLAN — Cosa succede quando un Mac va offline

**Version:** 2.0 (2026-02-14)

---

## Scenari di Failure

### Scenario 1: Air va offline (CRITICO)

**Impatto:** Alto. L'Air e il gateway primario. Se muore:

- WhatsApp/Telegram smettono di rispondere
- Zan non puo smistare task
- Generali non possono essere spawnati
- Cron jobs si fermano
- Clienti non ricevono risposta

**Rilevamento:**

- Pro pinga Air ogni 30 minuti (Z4 cron)
- Se 2 ping consecutivi falliscono → Air e down
- Fly.io backend continua a funzionare (e in cloud, non dipende da Air)
- Frontend Vercel continua a funzionare (e in cloud)

**Recovery automatico:**

| Step | Azione                                 | Chi la fa                | Tempo              |
| ---- | -------------------------------------- | ------------------------ | ------------------ |
| 1    | Pro rileva Air down                    | Pro OpenClaw (Z4 mirror) | 30-60 min          |
| 2    | Pro attiva modalita gateway primario   | Pro OpenClaw             | ~5 sec             |
| 3    | Pro prende in carico WhatsApp/Telegram | Pro OpenClaw             | Richiede rebinding |
| 4    | Notifica Zero via Telegram (dal Pro)   | Pro                      | Immediato          |
| 5    | Pro esegue cron critici (G1, G2)       | Pro                      | Immediato          |

**Limitazione:** Il rebinding WhatsApp/Telegram richiede che i webhook puntino al Pro. Questo necessita:

1. Aggiornare URL webhook WhatsApp su Meta Dashboard (manuale o script)
2. Aggiornare URL webhook Telegram via `setWebhook` API
3. Il Pro deve avere i token WhatsApp/Telegram configurati

**Pre-configurazione richiesta:**

```bash
# Sul Pro, configurare le stesse credenziali di messaging
# In openclaw.json del Pro, aggiungere sezione channels identica all'Air
# Tenere aggiornato, testare mensilmente
```

**Recovery manuale (Zero):**

1. Provare a riavviare Air (ssh, wake-on-lan, o fisicamente)
2. Se Air non si riavvia → usare Pro come gateway temporaneo
3. Se Pro come gateway → aggiornare webhook endpoints

---

### Scenario 2: Pro va offline (MEDIO)

**Impatto:** Medio. Il Pro e il nodo compute. Se muore:

- Cursor Agent non disponibile
- Modelli Ollama locali non disponibili
- Task pesanti non possono essere delegati
- MA: Zan continua a funzionare normalmente dall'Air

**Rilevamento:**

- Zan pinga Pro ogni 30 minuti (Z4 cron)
- SSH check: `ssh nuzantara@192.168.0.17 "echo OK"`
- Webhook check: `curl http://192.168.0.17:18789/hooks/wake`

**Recovery automatico:**

| Step | Azione                                          | Chi la fa      | Tempo      |
| ---- | ----------------------------------------------- | -------------- | ---------- |
| 1    | Zan rileva Pro down                             | Zan (Z4 cron)  | 30 min max |
| 2    | Zan logga warning                               | Zan            | Immediato  |
| 3    | Kodex smette di delegare al Pro                 | Kodex          | Immediato  |
| 4    | Kodex usa modelli cloud invece di Cursor/Ollama | Kodex          | Automatico |
| 5    | Notifica Zero                                   | Zan (Telegram) | Immediato  |

**Degradation graceful:**

| Funzione         | Normale                   | Pro Down         |
| ---------------- | ------------------------- | ---------------- |
| Coding (Kodex)   | Sonnet 4.5 + Cursor Agent | Sonnet 4.5 only  |
| Heavy compute    | Pro Ollama (14B models)   | Cloud only       |
| IDE-aware coding | cursor-ultra via Pro      | Claude Code only |
| Embedding backup | nomic-embed-text locale   | OpenAI API only  |

**Recovery manuale:**

1. Zero riavvia Pro (fisicamente o via wake-on-lan)
2. Verificare OpenClaw running: `ssh nuzantara@192.168.0.17 "pgrep -f openclaw"`
3. Se non running: `ssh nuzantara@192.168.0.17 "nohup openclaw gateway --force &"`
4. Verificare Ollama: `ssh nuzantara@192.168.0.17 "ollama list"`

---

### Scenario 3: Entrambi i Mac offline (CRITICO)

**Impatto:** Massimo per operazioni locali. MA:

- **Backend Fly.io continua** → API funzionano, chat web funziona
- **Frontend Vercel continua** → sito web funziona
- **WhatsApp/Telegram** → down (webhook non raggiungibile)

**Cosa continua a funzionare senza Mac:**

- https://zantara.balizero.com (chat web via Fly.io backend)
- API REST per integrazioni esterne
- Health endpoint
- PostgreSQL, Qdrant, Redis (tutti in cloud)

**Cosa si ferma:**

- Risposte WhatsApp (webhook locale)
- Risposte Telegram (webhook locale)
- Cron jobs dei generali
- KB updates
- Deployments

**Recovery:**

1. Riavviare almeno un Mac (Air prioritario)
2. Se impossibile → configurare webhook WhatsApp/Telegram su Fly.io (richiede work)

---

### Scenario 4: Fly.io va offline (RARO MA CRITICO)

**Impatto:** Backend e database down.

- Chat web non funziona
- API non funzionano
- Ma: WhatsApp/Telegram su Zan possono rispondere con dati cached

**Recovery:**

- Fly.io ha SLA 99.99%. Downtime tipico: <5 min
- Se extended (>30 min):
  1. Gravity tenta rollback automatico
  2. Gravity tenta restart machines: `fly machine restart`
  3. Se non risolve → Gravity notifica Zero

**Degradation con Fly.io down:**

| Funzione          | Normale            | Fly Down                           |
| ----------------- | ------------------ | ---------------------------------- |
| Chat web          | Funziona           | **DOWN**                           |
| WhatsApp/Telegram | Funziona (via Zan) | Zan risponde con dati locali       |
| Pricing queries   | PricingTool (API)  | PRICING_REFERENCE.md (file locale) |
| KBLI search       | Qdrant API         | **DOWN**                           |
| KG queries        | PostgreSQL API     | **DOWN**                           |

---

## Matrice di Criticita

| Componente         | Failure Impact | Recovery Time              | Automazione                     |
| ------------------ | -------------- | -------------------------- | ------------------------------- |
| Air                | ALTO           | 5-30 min (se Zero sveglio) | Parziale (Pro come backup)      |
| Pro                | MEDIO          | 5-30 min                   | Completa (graceful degradation) |
| Fly.io Backend     | ALTO           | 1-5 min (auto-heal)        | Completa (Fly auto-restart)     |
| Fly.io PostgreSQL  | CRITICO        | 5-30 min                   | Parziale (Fly managed)          |
| Qdrant             | MEDIO          | 5-15 min                   | Completa (Fly auto-restart)     |
| Vercel (frontend)  | BASSO          | 1-5 min                    | Completa (Vercel auto-heal)     |
| Internet (locale)  | ALTO           | Variabile                  | Nessuna                         |
| Corrente elettrica | ALTO           | Variabile                  | Nessuna (no UPS)                |

---

## Pre-configurazione per Failover

### Checklist una tantum

- [ ] **Pro: Configurare stesse credenziali messaging dell'Air**
  - Telegram bot token in openclaw.json
  - WhatsApp token in openclaw.json
  - Testare che Pro puo inviare messaggi Telegram

- [ ] **Pro: Installare script di failover**

  ```bash
  # ~/bin/failover-to-primary.sh
  #!/bin/bash
  echo "Activating Pro as primary gateway..."
  # Update Telegram webhook to Pro IP
  curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook?url=http://192.168.0.17:18789/hooks/telegram"
  echo "Telegram webhook updated to Pro"
  ```

- [ ] **Air: launchd per auto-restart OpenClaw** (da INSTALL_CHECKLIST.md)

- [ ] **Entrambi: cron di liveness check reciproco**

  ```bash
  # Ogni 30 min, controllare che l'altro Mac risponda
  */30 * * * * ping -c 1 -W 5 192.168.0.17 || echo "PRO DOWN" >> /tmp/mac-health.log
  ```

- [ ] **Backup webhook URLs**
  - Documentare URL correnti di WhatsApp e Telegram webhook
  - Avere script pronto per switchare

- [ ] **Test mensile failover**
  - Spegnere Air per 10 minuti
  - Verificare che Pro rileva e attiva failover
  - Verificare che messaging funziona dal Pro
  - Riaccendere Air e verificare ripristino

---

## Diagramma Decisionale Failover

```
Mac Down Detected?
│
├─ Air Down?
│   ├─ Pro funziona?
│   │   ├─ SI → Pro diventa gateway primario
│   │   │       ├─ Attiva messaging
│   │   │       ├─ Esegui cron critici
│   │   │       └─ Notifica Zero
│   │   └─ NO → Entrambi down
│   │           ├─ Cloud continua (Fly.io, Vercel)
│   │           ├─ Messaging DOWN
│   │           └─ Zero deve intervenire fisicamente
│   └─ Tentativo recovery Air:
│       ├─ SSH alive? → Restart OpenClaw via SSH
│       ├─ Ping alive? → Probabile crash OpenClaw, restart
│       └─ No ping? → Mac spento, serve intervento fisico
│
├─ Pro Down?
│   ├─ Impatto: solo compute locale
│   ├─ Degradation: cloud-only mode
│   ├─ Notifica Zero
│   └─ Tentativo recovery:
│       ├─ SSH alive? → Restart OpenClaw + Ollama
│       └─ No ping? → Mac spento, continua senza
│
└─ Fly.io Down?
    ├─ Gravity tenta restart
    ├─ Se > 5 min → Gravity tenta rollback
    ├─ Se > 30 min → Notifica Zero
    └─ Zan risponde ai clienti con dati locali cached
```

---

## Considerazione: UPS

**Consigliato ma non critico.** Un UPS per l'Air (che e il gateway always-on) proteggerebbe da:

- Blackout brevi (<30 min)
- Sbalzi di tensione

**Costo:** ~$50-100 per un UPS base (APC o CyberPower)
**Autonomia:** 15-30 min per un MacBook Air (gia ha batteria integrata)

**Decisione:** La batteria interna del MacBook Air e gia un mini-UPS. Se il Mac e collegato alla corrente e la corrente va via, continua per ~8-10 ore. Il vero rischio e un crash del software, non un blackout. Il launchd auto-restart copre questo caso.
