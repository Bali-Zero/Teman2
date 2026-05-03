# Applicazione Componenti e Utility Refactored

**Data:** 2026-01-24  
**Obiettivo:** Applicare `AutoResizeTextarea`, `renderMiniMarkdown`, e `fileToBase64` dove possibile

---

## 📊 ANALISI TROVATI

### 1. **AutoResizeTextarea** - Textarea da Migliorare

#### ✅ Priorità Alta

1. **`apps/mouth/src/app/(workspace)/intelligence/news-room/components/ArticleEditor.tsx`** (linea 115)
   - Textarea normale con `resize-y`
   - Min-height 400px
   - **Beneficio:** Auto-resize migliorerebbe UX

#### ⚠️ Priorità Media

2. Altri textarea nel codebase (27 file trovati)
   - Molti potrebbero beneficiare di auto-resize
   - Da valutare caso per caso

---

### 2. **renderMiniMarkdown** - Rendering Markdown da Migliorare

#### ✅ Priorità Alta

1. **`apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`** (linee 491-510)
   - Usa `dangerouslySetInnerHTML` con replace manuale
   - Codice duplicato e non sicuro
   - **Beneficio:** Rendering sicuro e consistente

2. **`apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`** (linea 621)
   - Altro uso di `dangerouslySetInnerHTML`
   - Potrebbe beneficiare di `renderMiniMarkdown`

#### ⚠️ Priorità Bassa

3. Altri usi di `dangerouslySetInnerHTML` per markdown
   - `MessageBubble.tsx` usa `ReactMarkdown` (già ottimizzato)
   - `ArticleClient.tsx` usa `ReactMarkdown` (già ottimizzato)

---

### 3. **fileToBase64** - Conversione File da Semplificare

#### ✅ Priorità Alta

1. **`apps/mouth/src/app/(workspace)/intelligence/news-room/components/CoverImageUploader.tsx`** (linee 51-84)
   - Codice duplicato per conversione base64
   - Usa regex per estrarre base64
   - **Beneficio:** Codice più pulito e riutilizzabile

2. **`apps/mouth/src/app/(workspace)/clients/[id]/page.tsx`** (linee 1185-1210)
   - Codice duplicato per upload passport
   - **Beneficio:** Semplificazione

3. **`apps/mouth/src/app/(workspace)/clients/[id]/page.tsx`** (linee 1442-1467)
   - Codice duplicato per upload documenti
   - **Beneficio:** Semplificazione

#### ⚠️ Priorità Media

4. **`apps/mouth/src/hooks/useChatInput.ts`** (linee 138-178)
   - Codice per conversione immagini chat
   - Potrebbe beneficiare di `fileToBase64`

5. **`apps/mouth/src/hooks/useChatPage.ts`** (linee 400-408)
   - Codice per avatar upload
   - Potrebbe beneficiare di `fileToBase64`

6. **`apps/mouth/src/lib/utils/imageResize.ts`**
   - Ha già logica per FileReader
   - Potrebbe usare `fileToBase64` come base

---

## 🎯 PIANO DI IMPLEMENTAZIONE

### Fase 1: Priorità Alta (Immediato)

1. ✅ Applicare `AutoResizeTextarea` in `ArticleEditor.tsx`
2. ✅ Applicare `renderMiniMarkdown` in `news-room/page.tsx` (2 punti)
3. ✅ Applicare `fileToBase64` in `CoverImageUploader.tsx`

### Fase 2: Priorità Media (Prossimo)

4. Applicare `fileToBase64` in `clients/[id]/page.tsx` (2 punti)
5. Valutare altri textarea per `AutoResizeTextarea`

### Fase 3: Priorità Bassa (Futuro)

6. Applicare `fileToBase64` in hooks chat
7. Ottimizzare `imageResize.ts` con `fileToBase64`

---

## 📝 NOTE TECNICHE

### AutoResizeTextarea

- Usa `useLayoutEffect` per evitare flicker
- Supporta tutte le props standard di textarea
- Compatibile con className personalizzati

### renderMiniMarkdown

- Rendering sicuro (escape HTML)
- Supporta: **Bold**, Link, newlines
- Ritorna `{ __html: string }` per `dangerouslySetInnerHTML`

### fileToBase64

- Promise-based
- Ritorna solo base64 (senza prefix `data:image/...`)
- Gestione errori integrata

---

## ✅ BENEFICI ATTESI

1. **Codice più pulito:** Meno duplicazione
2. **Manutenibilità:** Cambiamenti in un solo posto
3. **Consistenza:** Stesso comportamento ovunque
4. **Sicurezza:** Rendering markdown sicuro
5. **UX:** Textarea auto-ridimensionanti
