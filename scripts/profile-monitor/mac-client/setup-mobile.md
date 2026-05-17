# Setup Mobile — Smartphone aziendale Bali Zero

> **Audience**: Antonello (esecutore unico — setup tecnico smartphone non delegabile)
> **Quando**: dopo firma PKWTT lunedì 19 maggio 2026, in parallelo a setup Mac
> **Durata stimata**: 15-20 minuti per dipendente

Lo smartphone è il punto più sensibile (dati clienti via WhatsApp Business, accesso CRM mobile). Per questo motivo questa procedura NON è automatizzabile con uno script — la fai tu, manualmente, su ogni telefono.

## Materiali da avere a portata di mano

- 8 kartu SIM Telkomsel (vedi `sim-registry.md` per allocazione)
- Smartphone del dipendente acceso e sbloccato (chiedi password)
- Pro connesso al tailnet (per generare QR wa-mirror)
- Cavo USB-C compatibile con il device del dipendente (per emergenza backup)

## Procedura per ogni dipendente (15-20 min)

### Step 1 — Inserimento SIM (2 min)

1. Chiedi al dipendente di mostrarti il vassoio SIM del telefono.
2. **Se ha già una SIM personale**: chiedi se vuole tenerla (dual-SIM) o rimuoverla.
   - Se dual-SIM (iPhone XS+, Android moderni): inserisci SIM Bali Zero nello slot 2, lascia la SIM personale nello slot 1.
   - Se single-SIM: il dipendente deve scegliere. Spiega che la SIM personale resta fisicamente sua, solo non è inserita durante l'orario di lavoro.
3. Inserisci la SIM allocata (vedi `sim-registry.md` per numero corretto).
4. Aspetta riconoscimento rete Telkomsel (~30 sec). Verifica segnale.

### Step 2 — Backup + logout WhatsApp personale (3-5 min)

Solo se il dipendente ha WhatsApp personale attivo sul telefono e vuole sostituirlo con WhatsApp Business aziendale (NON dual-app).

1. Apri WhatsApp personale del dipendente.
2. **Settings → Chats → Chat Backup → Back Up Now** (Google Drive del dipendente / iCloud personale).
3. Aspetta completamento backup (può richiedere 2-3 min per >1GB di chat).
4. **Settings → Account → Delete My Account** (radicale ma pulito) OPPURE **Logout** (preserva l'account WhatsApp del numero personale, da reinstallare poi su altro telefono se vuole).

**Alternativa più pulita**: il dipendente installa WhatsApp Business AFFIANCO a WhatsApp personale (sono 2 app separate). Vantaggio: niente backup/logout, separazione fisica per app. Svantaggio: confusione se non chiari "uso questa per lavoro, quella per vita privata". Decidi caso per caso.

### Step 3 — Install WhatsApp Business + registrazione (5 min)

1. App Store (iPhone) o Play Store (Android) → cerca **WhatsApp Business** (la versione verde con valigetta, NON WhatsApp normale).
2. Install → Open.
3. Country: **Indonesia (+62)**.
4. Numero: SIM aziendale appena inserita (es. 813 3946 856 per Surya).
5. Verifica SMS (arriva sul numero appena inserito).
6. **NON ripristinare backup** (l'account è nuovo).
7. Permission: contatti = NO (il dipendente non deve avere accesso contatti aziendali via WA Business app).
8. Notifiche = SÌ.

### Step 4 — Configurazione profilo Business (3 min)

1. **Business Settings → Profile**:
   - Business Name: `Nome Dipendente — Bali Zero` (es. `Surya — Bali Zero`)
   - Category: **Professional Services**
   - Description: `Bali Zero — Indonesian business services. Immigration · Tax · Company Setup · Property.`
   - Email: email aziendale dipendente (es. `surya@balizero.com`)
   - Website: `https://balizero.com`
2. **Profile Photo**: foto professionale del dipendente (chiedi loro di scattarla sul momento con sfondo neutro, o usare la foto KTP/passaporto se decente). NON foto personali con fidanzato/amici/festa.
3. **Business Hours**: Mon-Fri 09:00-18:00 WITA. Closed Sat-Sun.
4. **Greeting Message**: testo standard pre-approvato (ti mando io via WhatsApp il template ufficiale).
5. **Away Message**: disabilitato (lascia che il dipendente risponda manualmente).

### Step 5 — Collegamento a wa-mirror (2-3 min)

1. Sul Pro (tuo), apri terminale e avvia wa-mirror per quel numero specifico:
   ```bash
   cd ~/Desktop/nuzantara/apps/wa-mirror
   npm start -- --employee=surya
   ```
   (Aggiorna `--employee=<nome>` per ogni dipendente)
2. Aspetta che appaia il QR code nel terminale.
3. Sul telefono dipendente, WhatsApp Business → **Settings → Linked Devices → Link a Device**.
4. Scansiona il QR code dal terminale del Pro.
5. Aspetta conferma "Linked" (5-10 secondi).
6. **Verifica server-side**: sul Pro, controlla che il numero sia comparso in DB:
   ```bash
   psql "$(grep DATABASE_URL_LOCAL ~/.nuzantara-secrets.env | cut -d= -f2-)" \
     -c "SELECT counterpart_phone, baileys_message_id, created_at FROM whatsapp_message_context ORDER BY created_at DESC LIMIT 3;"
   ```

### Step 6 — Test end-to-end (2 min)

1. Da un altro telefono (es. il tuo), manda un messaggio test al numero appena attivato:
   `"Test setup Bali Zero — [nome dipendente] — [timestamp]"`
2. Verifica che arrivi sulla WhatsApp Business del dipendente.
3. Il dipendente risponde con un altro messaggio.
4. Sul Pro, controlla che ENTRAMBI i messaggi siano stati catturati da wa-mirror in DB.
5. ✅ Setup completo.

## Disinstallazione futura (offboarding)

Se il dipendente lascia Bali Zero, esegui in quest'ordine:

1. **Sul Pro**: revoca il link wa-mirror per quel numero (ferma il processo Baileys).
2. **Sul telefono dipendente**: WhatsApp Business → Settings → Account → Delete My Account (cancella tutto).
3. **Rimuovi SIM Telkomsel** dal telefono.
4. **Sospendi SIM** sul portale Telkomsel Halo Business (https://mybusiness.telkomsel.com).
5. Aggiorna `sim-registry.md` con data exit.

## Troubleshooting comune

### SMS verifica non arriva
- Aspetta 2 min. Se non arriva, scegli "Resend".
- Se anche il secondo SMS fallisce, scegli "Call me" (Telkomsel manderà chiamata con codice vocale).
- Se anche la chiamata fallisce: SIM non attivata correttamente, contattare 188 (CS Telkomsel).

### QR wa-mirror scaduto
- I QR WhatsApp scadono dopo 20 secondi. Ripeti `npm start` per generare nuovo QR.

### "Number already in use on another account"
- Significa che il numero SIM era stato usato in passato su WhatsApp da qualcun altro. Forza logout previous: WhatsApp Business → "This phone number is registered to another account. Log out other devices?" → SÌ.

### Telefono non riconosce SIM Telkomsel
- Spegni telefono, rimuovi SIM, pulisci contatti dorati con panno asciutto, reinserisci, accendi.
- Verifica APN settings (Settings → Mobile Network → APN → "internet" per Telkomsel).
- Se persiste: SIM difettosa, sostituire con SIM spare dal registro.

### Dual-SIM iPhone — quale slot per Bali Zero?
- Slot 1 (fisica): personale del dipendente
- Slot 2 (eSIM o fisica nel vassoio doppio): Bali Zero
- iMessage / FaceTime: SOLO sul numero personale
- WhatsApp Business: SOLO sul numero Bali Zero
- Default Voice/SMS: scegliere "Ask Every Time" per evitare errori

## Documentazione team

Dopo il setup di ogni dipendente, aggiorna **sim-registry.md** colonna `MDM enrolled` → `WA-Business linked YYYY-MM-DD`.

Esempio:
```
| 001 | 0813 3946 856 | +62 813 3946 856 | Surya | BBN/001 | WA-Business linked 2026-05-19 | Tax | — |
```
