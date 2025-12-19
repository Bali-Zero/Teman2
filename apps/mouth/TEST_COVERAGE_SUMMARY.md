# Test Coverage Summary - Frontend Refactoring

## Overview
Aumentata la coverage dei test per i moduli refactorizzati del frontend. Creati test completi per tutti i nuovi moduli API e utility functions.

## Test Files Creati

### API Client Tests
- ✅ `lib/api/client.test.ts` - Test per ApiClientBase (token management, request method, CSRF handling)
- ✅ `lib/api/auth/auth.api.test.ts` - Test per AuthApi (login, logout, getProfile)
- ✅ `lib/api/chat/chat.api.test.ts` - Test per ChatApi (sendMessage, sendMessageStreaming con abortSignal)
- ✅ `lib/api/knowledge/knowledge.api.test.ts` - Test per KnowledgeApi (searchDocs con vari parametri)
- ✅ `lib/api/conversations/conversations.api.test.ts` - Test per ConversationsApi (CRUD completo)
- ✅ `lib/api/team/team.api.test.ts` - Test per TeamApi (clockIn, clockOut, getClockStatus)
- ✅ `lib/api/admin/admin.api.test.ts` - Test per AdminApi (team status, hours, export)
- ✅ `lib/api/media/upload.api.test.ts` - Test per UploadApi (file upload)
- ✅ `lib/api/media/audio.api.test.ts` - Test per AudioApi (transcribeAudio, generateSpeech)
- ✅ `lib/api/media/image.api.test.ts` - Test per ImageApi (generateImage)
- ✅ `lib/api/websocket/websocket.utils.test.ts` - Test per WebSocketUtils (URL conversion, subprotocol)

### Utility Tests
- ✅ `app/chat/utils/avatarValidation.test.ts` - Test per validazione avatar (magic bytes, dimensions)
- ✅ `app/chat/utils/fileValidation.test.ts` - Test per validazione file upload
- ✅ `components/search/utils/citationFormatter.test.ts` - Test per formattazione citazioni
- ✅ `components/search/hooks/useSearchDocs.test.ts` - Test per hook ricerca documenti
- ✅ `components/search/hooks/useSearchSelection.test.ts` - Test per hook selezione risultati

## Coverage Areas

### Token & Authentication
- Token management (set, get, clear)
- Authentication status checking
- CSRF token handling (memory + cookie fallback)
- User profile management
- Login/logout flows

### API Request Handling
- GET/POST/PUT/DELETE requests
- Request timeout handling
- Error handling (HTTP errors, network errors)
- Empty response handling (204)
- Header management (Authorization, CSRF)

### Streaming
- SSE streaming parsing
- Chunk handling
- Tool steps (tool_start, tool_end, status)
- Sources and metadata extraction
- Abort signal support (nuovo)
- Error handling during streaming

### Domain-Specific APIs
- **Auth**: Login, logout, profile retrieval
- **Chat**: Message sending, streaming with conversation history
- **Knowledge**: Document search with level/limit/tier filtering
- **Conversations**: CRUD operations, memory context
- **Team**: Clock in/out, status retrieval
- **Admin**: Team status, hours tracking, CSV export
- **Media**: File upload, audio transcription, speech generation, image generation
- **WebSocket**: URL conversion, subprotocol generation

### Validation
- Avatar file validation (MIME type, size, magic bytes, dimensions)
- File upload validation (size limits)
- Citation formatting
- Search result selection

### Hooks
- useSearchDocs: Query management, search execution, error handling
- useSearchSelection: Expanded/selected state management

## Test Statistics

- **Total Test Files**: 15 nuovi file di test
- **Estimated Test Cases**: 100+ test cases
- **Coverage Target**: >80% per i moduli refactorizzati

## Note

- Tutti i test usano Vitest come framework
- Mock appropriati per fetch, localStorage, FileReader, Image
- Test isolati con beforeEach/afterEach per cleanup
- Test per edge cases e error handling
- Supporto per abortSignal nel streaming (nuova feature)

## Running Tests

```bash
# Run all tests
npm test

# Run specific test file
npm test src/lib/api/client.test.ts

# Run with coverage
npm test -- --coverage
```

