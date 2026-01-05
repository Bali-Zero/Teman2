# Chat Page - 100% Coverage Plan

**Obiettivo**: Coverage al 100% per:
1. ✅ Test (Unit + Integration + API)
2. ✅ Logging (100% funzioni critiche)
3. ✅ Metriche (100% azioni utente)

---

## 📊 STATO ATTUALE

### Test Esistenti
- ✅ E2E tests: `e2e/chat/*.spec.ts` (6 file)
- ✅ API test: `lib/api/chat/chat.api.test.ts` (completo)
- ❌ Unit test ChatPage: **MANCANTE**
- ❌ Integration test ChatPage: **MANCANTE**

### Logging Attuale
- ✅ Logger esiste: `lib/logger.ts`
- ⚠️ Solo 5 chiamate logger nel file chat/page.tsx:
  - `loadUserProfile` error
  - `handleSend` error
  - `handleConversationClick` error
  - Audio transcription debug/error
- ❌ **Mancano ~50+ punti di logging**

### Metriche Attuali
- ✅ Analytics esiste: `lib/analytics.ts`
- ❌ **Zero metriche nella ChatPage**

---

## 🎯 PIANO DI IMPLEMENTAZIONE

### FASE 1: Logging 100% ✅

**Funzioni da loggare**:

1. **Initialization & Mount**
   - Component mount/unmount
   - Auth check
   - Initial data load (success/error)

2. **User Profile**
   - Profile load start/success/error
   - Avatar load from localStorage
   - Avatar upload start/success/error

3. **Messages**
   - Message send start
   - Message send success (con metadata: length, hasImages, execution_time)
   - Message send error (con error type)
   - Message chunk received (debug)
   - Message stream complete
   - Conversation save start/success/error

4. **Conversations**
   - Conversation list load start/success/error
   - Conversation click
   - Conversation delete start/success/error
   - New chat created

5. **Audio Recording**
   - Recording start/success/error (con error type)
   - Recording stop
   - Transcription start/success/error (con metadata: blobSize, duration)

6. **TTS (Text-to-Speech)**
   - TTS start (con messageId, textLength)
   - TTS success (con duration)
   - TTS error (con error type)
   - TTS playback start/stop/error

7. **Image Operations**
   - Image attach start/success/error
   - Image remove
   - Image generation modal open/close
   - Image generation submit

8. **UI Interactions**
   - Sidebar open/close
   - Search docs modal open/close
   - Toast show (debug)

9. **Clock/Team Status**
   - Clock status load start/success/error
   - Clock toggle start/success/error

---

### FASE 2: Metriche 100% ✅

**Eventi da tracciare** (usando `trackEvent` da `lib/analytics.ts`):

1. **Message Events**
   - `chat_message_sent` - Messaggio inviato
     - Properties: `hasImages`, `imageCount`, `textLength`, `sessionId`
   - `chat_message_received` - Messaggio ricevuto
     - Properties: `responseLength`, `executionTime`, `hasSources`, `sourceCount`, `routeUsed`
   - `chat_stream_chunk` - Chunk ricevuto (sampled, non tutti)
   - `chat_conversation_saved` - Conversazione salvata
     - Properties: `messageCount`, `sessionId`

2. **Conversation Events**
   - `chat_new_conversation` - Nuova conversazione
   - `chat_conversation_loaded` - Conversazione caricata
     - Properties: `conversationId`, `messageCount`
   - `chat_conversation_deleted` - Conversazione eliminata
     - Properties: `conversationId`

3. **Audio Events**
   - `chat_audio_recording_started` - Registrazione audio iniziata
   - `chat_audio_recording_stopped` - Registrazione audio fermata
     - Properties: `duration`, `blobSize`, `mimeType`
   - `chat_audio_transcribed` - Audio trascritto
     - Properties: `duration`, `blobSize`, `textLength`, `success`

4. **TTS Events**
   - `chat_tts_started` - TTS iniziato
     - Properties: `messageId`, `textLength`, `voice`
   - `chat_tts_completed` - TTS completato
     - Properties: `messageId`, `duration`
   - `chat_tts_error` - TTS errore
     - Properties: `messageId`, `errorType`

5. **Image Events**
   - `chat_image_attached` - Immagine allegata
     - Properties: `imageCount`, `totalSize`
   - `chat_image_removed` - Immagine rimossa
   - `chat_image_generation_requested` - Generazione immagine richiesta
     - Properties: `promptLength`

6. **UI Events**
   - `chat_sidebar_opened` - Sidebar aperta
   - `chat_sidebar_closed` - Sidebar chiusa
   - `chat_search_docs_opened` - Search docs aperto

7. **Error Events**
   - `chat_error` - Errore generico
     - Properties: `errorType`, `errorMessage`, `action`

---

### FASE 3: Test Unit 100% ✅

**File**: `apps/mouth/src/app/chat/__tests__/ChatPage.test.tsx`

**Test da creare**:

1. **Component Rendering**
   - Renders correctly when authenticated
   - Redirects to login when not authenticated
   - Shows loading state initially
   - Renders welcome screen when no messages

2. **User Profile**
   - Loads user profile on mount
   - Handles profile load error
   - Loads avatar from localStorage

3. **Message Handling**
   - handleSend: validates input (empty, images only)
   - handleSend: creates user and assistant messages
   - handleSend: calls API correctly
   - handleSend: handles streaming chunks
   - handleSend: handles completion
   - handleSend: handles errors
   - handleSend: saves conversation on success

4. **Conversations**
   - handleNewChat: resets state
   - handleConversationClick: loads conversation
   - handleDeleteConversation: deletes conversation
   - handleDeleteConversation: confirms deletion

5. **Audio**
   - handleMicClick: starts/stops recording
   - handleMicClick: handles permission errors
   - Audio transcription: processes blob
   - Audio transcription: handles errors

6. **TTS**
   - handleTTS: starts TTS
   - handleTTS: stops current TTS
   - handleTTS: handles errors
   - handleTTS: cleanup on unmount

7. **Images**
   - handleImageAttach: validates files
   - handleImageAttach: handles multiple files
   - handleImageAttach: enforces limits
   - removeAttachedImage: removes image
   - handleImageGenSubmit: submits generation

8. **UI Interactions**
   - Sidebar: open/close
   - Search docs: open/close
   - Toast: shows and auto-dismisses

9. **Helpers**
   - showToast: sets toast state
   - UserAvatarDisplay: renders correctly
   - generateId: generates unique IDs

---

### FASE 4: Test Integration 100% ✅

**File**: `apps/mouth/src/app/chat/__tests__/ChatPage.integration.test.tsx`

**Test da creare**:

1. **Message Flow Integration**
   - Complete message send flow (input → API → display)
   - Multiple messages in sequence
   - Message with images
   - Streaming response display

2. **Conversation Flow Integration**
   - Load conversation list → select conversation → display messages
   - Create new conversation → send message → save
   - Delete conversation → verify removal

3. **Audio Flow Integration**
   - Record audio → stop → transcribe → display in input
   - Record audio error handling

4. **TTS Flow Integration**
   - Generate TTS → play → stop
   - TTS error handling

5. **Image Flow Integration**
   - Attach images → send message → verify display
   - Remove images
   - Image generation flow

6. **State Management Integration**
   - Optimistic updates work correctly
   - State persists across interactions
   - Cleanup on unmount

---

### FASE 5: Test API 100% ✅

**Verificare coverage `lib/api/chat/chat.api.test.ts`**:

Attualmente copre:
- ✅ sendMessage
- ✅ sendMessageStreaming (completo)

**Da aggiungere se mancano**:
- Audio API: `transcribeAudio`
- TTS API: `generateSpeech`
- Image API: `generateImage`
- Conversations API: già testato separatamente

---

## 📝 IMPLEMENTAZIONE

### Priorità

1. **Logging** (Facile, impatto immediato)
2. **Metriche** (Facile, richiede analytics)
3. **Test Unit** (Media complessità)
4. **Test Integration** (Alta complessità)

### Stima

- **Logging**: 2-3 ore
- **Metriche**: 2-3 ore
- **Test Unit**: 4-6 ore
- **Test Integration**: 4-6 ore

**Totale**: ~12-18 ore

---

## ✅ CHECKLIST

### Logging
- [ ] Component mount/unmount
- [ ] Auth check
- [ ] Initial data load
- [ ] User profile operations (10+ punti)
- [ ] Message operations (15+ punti)
- [ ] Conversation operations (8+ punti)
- [ ] Audio operations (10+ punti)
- [ ] TTS operations (8+ punti)
- [ ] Image operations (8+ punti)
- [ ] UI interactions (5+ punti)
- [ ] Clock/Team status (4+ punti)

### Metriche
- [ ] Message events (5 eventi)
- [ ] Conversation events (3 eventi)
- [ ] Audio events (4 eventi)
- [ ] TTS events (3 eventi)
- [ ] Image events (3 eventi)
- [ ] UI events (3 eventi)
- [ ] Error events (1 evento)

### Test
- [ ] Unit tests: 30+ test cases
- [ ] Integration tests: 15+ test cases
- [ ] API tests: Verificare coverage esistente

---

**Fine Piano**

