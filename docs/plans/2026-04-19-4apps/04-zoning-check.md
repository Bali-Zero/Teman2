# Build Plan 04 — Zoning Check

**Prerequisito:** `00-shared-infrastructure.md`

## Idea

Tool map-based: user pinna un punto sulla mappa di Bali → tool risponde con zona LP2B (rice field, Perda 4/2026 criminal), classificazione zoning, restrizioni foreign ownership, tipo titolo suggerito (Hak Pakai 80y / leasehold / HGB via PT PMA). Shareable URL, no sign-up.

**Single flow (no rami)** — segmento è unico: chi sta valutando un lotto in Bali. Ma **3 CTA contestuali** in base al result:

- Zone OK → due diligence paid
- LP2B / problematica → "ti troviamo un lotto equivalente"
- Fuori coverage → manual check free 48h

Costruita su infra PostGIS già esistente (`prime.balizero.com`). La più veloce delle 4 a shippare.

## User flow

```
[Homepage section property]
  └─▶ <ZoningCheckHero />
      └─▶ Mappa Bali interattiva + search bar
          ├─▶ Click mappa → pin drop
          ├─▶ Paste Google Maps URL → parse lat/lng
          └─▶ Address search → geocode
              └─▶ [GET /api/property/zoning?lat=X&lng=Y]
                  └─▶ Result overlay (3 varianti in base a zona)
                      ├─▶ Save pin (opt) → /property/check/[pin_id] persistente
                      └─▶ WhatsApp CTA (contextual)
```

## Output: scheda zoning

4 dimensioni:

1. **Zone** — residential / tourism / commercial / green / mixed
2. **LP2B (rice field)** — YES / NO (se YES: warning rosso "Perda 4/2026 — criminal")
3. **HGB via PT PMA** — eligible / not eligible
4. **Hak Pakai** — eligible fino a 80 anni / not eligible

Più:

- **Regulation refs**: pasal + URL (PP 18/2021, Perda 4/2026)
- **Coverage indicator**: se pin è fuori area coperta (80% Canggu/Ubud/Seminyak/Uluwatu)

## 3 CTA contestuali (in base al result)

### CTA 1 — Zone OK (HGB eligible, no LP2B, zona sana)

> **"Due diligence completa su questo lotto: IDR [PricingTool] fee, 7 giorni turnaround. Include sertifikat verification + seller history + UBO check."**
>
> **[Start WhatsApp →]** (context: lat/lng + zone_class + link pin)

### CTA 2 — Zone problematica (LP2B, green zone, non edificabile)

> **"Questo lotto non è edificabile (rice field, Perda 4/2026 criminal law). Vuoi che ti aiutiamo a trovare un lotto equivalente nella stessa area, con zoning compatibile?"**
>
> **[Start WhatsApp →]** (context: lat/lng + problem + desired area)

### CTA 3 — Fuori coverage

> **"Il tuo pin è fuori dalla nostra area mappata (siamo al 80% su Canggu/Ubud/Seminyak/Uluwatu). Ti controlliamo a mano in 48h, gratis — senza impegno."**
>
> **[Request manual check →]** (context: lat/lng + timestamp)

Il gap di coverage **diventa il lead più qualificato**: chi richiede manual check è motivato (non solo curioso).

## Engagement loop

- **Saved pins**: user salva pin con nickname (es. "Berawa villa 1") per confrontare dopo
- **Regulation alerts**: "Perda emendata — il tuo pin è ancora OK?" email push
- **Share map**: link pubblico `balizero.com/property/check/[pin_id]` con marker e scheda → user lo manda al partner/investor/agent

## API

```python
GET /api/property/zoning?lat={lat}&lng={lng}
  Response: ZoningResult {
    zone_class: "residential" | "tourism" | "commercial" | "green" | "mixed",
    lp2b: bool,
    hgb_eligible: bool,
    hak_pakai_eligible: bool,
    foreign_ownership_notes: str,
    regulation_refs: ["PP 18/2021", "Perda 4/2026"],
    coverage_complete: bool,    # false se fuori area mappata
    recommended_title_type: str,
    cta_variant: "ok" | "problematic" | "out_of_coverage"
  }

POST /api/property/pins       # save pin
  Body: { lat, lng, label?, client_fp }
  Response: { pin_id, result_url }

GET /api/property/pins/{pin_id}

POST /api/property/manual_check_request     # CTA 3 path (fuori coverage)
  Body: { lat, lng, desired_timeline?, notes? }
  Response: { request_id, whatsapp_url }
```

## Migration 122 — `property_pins`

```sql
CREATE TABLE property_pins (
  id            VARCHAR(20) PRIMARY KEY,    -- pin_<nanoid>
  lat           DECIMAL(9,6) NOT NULL,
  lng           DECIMAL(9,6) NOT NULL,
  label         VARCHAR(128),
  zone_class    VARCHAR(32),
  lp2b          BOOLEAN,
  hgb_eligible  BOOLEAN,
  hak_pakai_eligible BOOLEAN,
  foreign_ownership_notes TEXT,
  regulation_refs VARCHAR(64)[],
  coverage_complete BOOLEAN NOT NULL,
  cta_variant   VARCHAR(16) NOT NULL,
  client_fp     VARCHAR(32),
  view_count    INT NOT NULL DEFAULT 0,
  share_count   INT NOT NULL DEFAULT 0,
  subscription_count INT NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_checked_at TIMESTAMPTZ
);

CREATE INDEX idx_pins_created ON property_pins(created_at DESC);
CREATE INDEX idx_pins_lp2b ON property_pins(lp2b) WHERE lp2b = TRUE;
CREATE INDEX idx_pins_location ON property_pins USING GIST(
  ST_SetSRID(ST_MakePoint(lng, lat), 4326)
);
```

## Frontend stack

- **Map library**: `@vis.gl/react-google-maps` (50KB vs 150KB di `@react-google-maps/api` — critico per mobile Lighthouse)
- **Static map fallback**: Google Static Maps API per OG share image (1200x630 PNG con marker)
- **Coverage heatmap**: pre-generated GeoJSON in `public/data/zoning-coverage.geojson`, overlay semitrasparente
- **Lazy load**: `next/dynamic({ ssr: false })` su map component + pre-connect `maps.googleapis.com` in `<head>`
- **Tap-to-load fallback**: se Lighthouse mobile < 70, show static map preview + "Tap to load interactive map"

## Acceptance criteria

### Functional

- [ ] Click mappa → pin drop + result entro 800ms
- [ ] Paste Google Maps URL → coords parsed (4 pattern supportati: `?q=`, `/@lat,lng`, plus code, bare "lat,lng")
- [ ] Address search → geocode OK
- [ ] Result mostra 4 dimensioni (zone, LP2B, HGB, Hak Pakai)
- [ ] CTA variant adattivo: OK / problematic / out_of_coverage
- [ ] Pin LP2B → warning chiaro "Cannot build" + regulation ref linkato
- [ ] Out-of-coverage → manual_check_request endpoint genera lead
- [ ] Save pin → redirect persistente `/property/check/[pin_id]`
- [ ] Share URL pubblico apribile senza login
- [ ] OG image statica rendered per link preview (iOS/Android)
- [ ] WA CTA context: lat/lng + zone_class + cta_variant

### Performance (critico per mobile)

- [ ] Form page Lighthouse mobile ≥ 80 (Google Maps penalty mitigated)
- [ ] Result page Lighthouse mobile ≥ 85
- [ ] Map interactive entro 3s 4G connection
- [ ] Pin drop → result overlay < 1s
- [ ] `GET /api/property/zoning` p95 < 200ms

### Analytics

- [ ] `app_viewed`, `app_form_submitted` (pin drop), `app_result_viewed`, `app_cta_clicked`, `app_whatsapp_handoff`
- [ ] NEW: `app_pin_saved`
- [ ] NEW: `app_manual_check_requested` (cta_variant=out_of_coverage)
- [ ] NEW: `app_url_paste` vs `app_map_click` vs `app_address_search` (source pin)

### Data quality

- [ ] Coverage heatmap riflette PostGIS data accuratamente
- [ ] Zoning result matches `prime.balizero.com` per stesse coordinate
- [ ] Regulation refs linkano a URL validi (no 404)

### Integration

- [ ] E2E: map click → result OK → save → share URL apre
- [ ] E2E: pin LP2B → CTA variant "problematic" → WA
- [ ] E2E: pin fuori coverage → CTA variant "out_of_coverage" → manual_check_request → lead_intent
- [ ] Visual regression test: 3 CTA variant render correct

## Killer risk + mitigation

**Risk 1:** Mobile performance (Google Maps JS penalty).

- Mitigation: `@vis.gl/react-google-maps` lighter bundle, lazy load, pre-connect hints, static map preview fallback. Sprint perf audit dedicato: se Lighthouse < 70 dopo fix, ship con static map first + interactive on-tap.

**Risk 2:** Coverage gaps (bali_zoning_layers parziale nord/est Bali).

- Mitigation: coverage heatmap visible (user vede prima di cliccare), CTA 3 "manual check free" converte gap in lead più qualificato. V2: espansione coverage via BPN scraping + OSS integration.

**Risk 3:** URL parser fallisce su format esotico.

- Mitigation: 4 pattern supportati + fallback geocoding API per bare address. Se fail: hint visibile "Paste a URL like 'google.com/maps?q=-8.65,115.22' or click the map."

**Risk 4:** CTA 2 (problematic) non converte perché "we help find alternative" è vago.

- Mitigation: linking diretto a WhatsApp con richiesta precompilata "Cercate un lotto equivalente in [area] con zoning [desired_type]". Il team ha lead specifico, può mandare proposte concrete in 48h (esiste network real estate locale).

## Dependencies

- Shared infra 00 DONE
- Migration 004 + 005 (PostGIS + bali_zoning_layers) GIÀ APPLICATA
- Migration 122 appliable dopo 121
- `NEXT_PUBLIC_GOOGLE_MAPS_KEY` attiva
- Coverage GeoJSON pre-generato e esportato in `public/data/zoning-coverage.geojson`
- PricingTool: `get_service_price("property_due_diligence")`
- Regulation URL fonti (PP 18/2021, Perda 4/2026) validate + archived

## Post-ship telemetry (30gg)

- Pins created per day
- Map click vs URL paste vs search split
- Coverage hit rate (% pin dentro coverage)
- CTA variant distribution (ok / problematic / out_of_coverage)
- Manual check request rate (indicator coverage gaps)
- Save pin rate (retention signal, target ≥ 15%)
- Share click rate
- WA handoff rate
- Matched lead rate (per CTA variant)

**Alert Telegram:**

- Lighthouse mobile < 70 → performance regression
- coverage_hit_rate < 70% → user clickano fuori aree note, rivedi default zoom
- manual_check_rate > 40% → coverage troppo stretto, espandi
- matched_rate < 35% → WA messaging inaccurate

## V2 roadmap

- Multiple pin comparison ("compare these 3 plots side by side")
- Saved pin portfolio per user (richiede auth via `my.balizero.com`)
- Historical pin alerts ("Zoning rule for your saved pin changed")
- Direct DD booking `/property/dd/[pin_id]/book` con pricing trasparente + 7-day SLA
- Integration con `prime.balizero.com` 3D per power users
- Agent network integration: se CTA 2 (lotto problematico), auto-match con inventory real estate partner
