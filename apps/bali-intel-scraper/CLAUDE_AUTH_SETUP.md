# Configurazione Autenticazione Claude CLI

Il CLI di Claude (`@anthropic-ai/claude-code`) richiede autenticazione interattiva per usare l'abbonamento Claude Max. **Non supporta variabili d'ambiente** per le credenziali.

## Opzione 1: Autenticazione Manuale via SSH (Consigliata)

Dopo il deploy, connettiti via SSH e autentica manualmente:

```bash
# Connettiti alla macchina Fly.io
fly ssh console -a bali-intel-scraper

# Esegui lo script di setup
cd /app
bash scripts/setup_claude_auth.sh

# Oppure autentica direttamente
claude setup-token
```

Segui le istruzioni sullo schermo per completare l'autenticazione con:
- Email: `antonellosiano@gmail.com`
- Password: `Balizeroai1987`

## Opzione 2: Volume Fly.io (Persistente)

Se hai già autenticato il CLI localmente, puoi copiare la directory `~/.claude` su Fly.io:

### Step 1: Crea volume
```bash
fly volumes create claude_config --size 1 --region sin -a bali-intel-scraper
```

### Step 2: Monta volume in fly.toml
Aggiungi a `fly.toml`:
```toml
[[mounts]]
  source = "claude_config"
  destination = "/home/scraper/.claude"
```

### Step 3: Copia configurazione locale
```bash
# Connettiti via SSH
fly ssh console -a bali-intel-scraper

# Crea directory se non esiste
mkdir -p /home/scraper/.claude

# Esci e copia da locale (da terminale locale)
# Nota: devi usare fly sftp o tar/untar
```

## Opzione 3: Build-time Copy (Non Consigliato)

Puoi copiare `~/.claude` nel Dockerfile, ma **NON è sicuro** perché le credenziali finiscono nell'immagine Docker.

## Verifica Autenticazione

Dopo l'autenticazione, verifica che funzioni:

```bash
fly ssh console -a bali-intel-scraper
claude -p "test"
```

Se funziona, vedrai una risposta da Claude invece di errori di autenticazione.

## Note Importanti

- ✅ Il CLI è già installato nel Dockerfile
- ✅ Non serve `ANTHROPIC_API_KEY` se usi l'abbonamento Max
- ⚠️ L'autenticazione deve essere fatta manualmente (non automatizzabile)
- ⚠️ Le credenziali sono salvate in `~/.claude` (non in env vars)
