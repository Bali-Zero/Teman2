# Manual Test Guide - Zantara Fixes

Guida per testare manualmente i fix implementati su Zantara.

## 🔐 Prerequisiti

1. **Login e ottenere token JWT:**
```bash
TOKEN=$(curl -s -X POST https://nuzantara-rag.fly.dev/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"zero@balizero.com","pin":"010719"}' | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['data']['token'])")

echo "Token: $TOKEN"
```

## 🧪 Test 1: Greetings Detection

**Obiettivo:** Verificare che "ciao" restituisca una risposta diretta senza chiamare RAG.

```bash
# Test greeting
curl -X POST https://nuzantara-rag.fly.dev/api/agentic-rag/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "query": "ciao",
    "user_id": "zero@balizero.com",
    "session_id": "'$(uuidgen)'"
  }' | python3 -m json.tool
```

**Risultato atteso:**
- ✅ `route_used` contiene "greeting-pattern"
- ✅ `tools_called` è 0
- ✅ `answer` contiene "Ciao! Come posso aiutarti oggi?" o simile
- ✅ Nessuna chiamata a `vector_search`

**Verifica:**
```bash
# Controlla route_used e tools_called
curl -X POST https://nuzantara-rag.fly.dev/api/agentic-rag/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query":"ciao","user_id":"zero@balizero.com","session_id":"'$(uuidgen)'"}' | \
  python3 -c "import sys, json; d=json.load(sys.stdin); print(f\"Route: {d.get('route_used')}, Tools: {d.get('tools_called')}\")"
```

## 🧪 Test 2: Session Isolation

**Obiettivo:** Verificare che sessioni diverse abbiano contesti isolati.

### Step 1: Creare Session 1 con nome "Marco"

```bash
SESSION_1=$(uuidgen)

curl -X POST https://nuzantara-rag.fly.dev/api/agentic-rag/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "query": "Il mio nome è Marco",
    "user_id": "zero@balizero.com",
    "session_id": "'$SESSION_1'"
  }' | python3 -m json.tool
```

### Step 2: Creare Session 2 con nome "Luca"

```bash
SESSION_2=$(uuidgen)

curl -X POST https://nuzantara-rag.fly.dev/api/agentic-rag/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "query": "Il mio nome è Luca",
    "user_id": "zero@balizero.com",
    "session_id": "'$SESSION_2'"
  }' | python3 -m json.tool
```

### Step 3: Chiedere nome in Session 1 (dovrebbe dire "Marco")

```bash
curl -X POST https://nuzantara-rag.fly.dev/api/agentic-rag/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "query": "Come mi chiamo?",
    "user_id": "zero@balizero.com",
    "session_id": "'$SESSION_1'"
  }' | python3 -c "import sys, json; print(json.load(sys.stdin)['answer'])"
```

**Risultato atteso:** ✅ Risposta contiene "Marco" e NON contiene "Luca"

### Step 4: Chiedere nome in Session 2 (dovrebbe dire "Luca")

```bash
curl -X POST https://nuzantara-rag.fly.dev/api/agentic-rag/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "query": "Come mi chiamo?",
    "user_id": "zero@balizero.com",
    "session_id": "'$SESSION_2'"
  }' | python3 -c "import sys, json; print(json.load(sys.stdin)['answer'])"
```

**Risultato atteso:** ✅ Risposta contiene "Luca" e NON contiene "Marco"

## 🧪 Test 3: Memory Hallucination Prevention

**Obiettivo:** Verificare che la prima query di una nuova sessione non menzioni fatti da sessioni precedenti.

### Step 1: Creare una nuova sessione completamente nuova

```bash
NEW_SESSION=$(uuidgen)

curl -X POST https://nuzantara-rag.fly.dev/api/agentic-rag/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "query": "Ciao, sono nuovo qui",
    "user_id": "zero@balizero.com",
    "session_id": "'$NEW_SESSION'"
  }' | python3 -c "import sys, json; print(json.load(sys.stdin)['answer'])"
```

**Risultato atteso:**
- ✅ Risposta NON contiene frasi come:
  - "So che..."
  - "Ricordo che..."
  - "Hai detto che..."
  - "Il tuo colore preferito è..."
  - "Preferisci..."
- ✅ Risposta è generica e non menziona fatti da sessioni precedenti

### Verifica pattern di memory hallucination:

```bash
# Controlla se la risposta contiene pattern di memory hallucination
curl -X POST https://nuzantara-rag.fly.dev/api/agentic-rag/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "query": "Ciao, sono nuovo qui",
    "user_id": "zero@balizero.com",
    "session_id": "'$(uuidgen)'"
  }' | python3 -c "
import sys, json
answer = json.load(sys.stdin)['answer'].lower()
patterns = ['so che', 'ricordo che', 'hai detto', 'preferisci', 'il tuo']
found = [p for p in patterns if p in answer]
if found:
    print(f'❌ Memory hallucination detected: {found}')
else:
    print('✅ No memory hallucination detected')
"
```

## 📊 Test Completo - Script Bash

Copia e incolla questo script completo:

```bash
#!/bin/bash

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔐 Logging in..."
TOKEN=$(curl -s -X POST https://nuzantara-rag.fly.dev/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"zero@balizero.com","pin":"010719"}' | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['data']['token'])")

if [ -z "$TOKEN" ]; then
  echo "${RED}❌ Login failed${NC}"
  exit 1
fi

echo "${GREEN}✅ Login successful${NC}\n"

# Test 1: Greeting
echo "🧪 TEST 1: Greetings Detection"
RESPONSE=$(curl -s -X POST https://nuzantara-rag.fly.dev/api/agentic-rag/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query":"ciao","user_id":"zero@balizero.com","session_id":"'$(uuidgen)'"}')

ROUTE=$(echo $RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('route_used',''))")
TOOLS=$(echo $RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('tools_called',-1))")

if [[ "$ROUTE" == *"greeting"* ]] && [ "$TOOLS" == "0" ]; then
  echo "${GREEN}✅ PASS: Greeting detected, no tools called${NC}"
else
  echo "${RED}❌ FAIL: Route=$ROUTE, Tools=$TOOLS${NC}"
fi

# Test 2: Session Isolation
echo "\n🧪 TEST 2: Session Isolation"
SESSION_1=$(uuidgen)
SESSION_2=$(uuidgen)

# Set names in different sessions
curl -s -X POST https://nuzantara-rag.fly.dev/api/agentic-rag/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query":"Il mio nome è Marco","user_id":"zero@balizero.com","session_id":"'$SESSION_1'"}' > /dev/null

curl -s -X POST https://nuzantara-rag.fly.dev/api/agentic-rag/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query":"Il mio nome è Luca","user_id":"zero@balizero.com","session_id":"'$SESSION_2'"}' > /dev/null

# Check names
ANSWER_1=$(curl -s -X POST https://nuzantara-rag.fly.dev/api/agentic-rag/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query":"Come mi chiamo?","user_id":"zero@balizero.com","session_id":"'$SESSION_1'"}' | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['answer'].lower())")

ANSWER_2=$(curl -s -X POST https://nuzantara-rag.fly.dev/api/agentic-rag/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query":"Come mi chiamo?","user_id":"zero@balizero.com","session_id":"'$SESSION_2'"}' | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['answer'].lower())")

if [[ "$ANSWER_1" == *"marco"* ]] && [[ "$ANSWER_1" != *"luca"* ]] && \
   [[ "$ANSWER_2" == *"luca"* ]] && [[ "$ANSWER_2" != *"marco"* ]]; then
  echo "${GREEN}✅ PASS: Sessions isolated correctly${NC}"
else
  echo "${RED}❌ FAIL: Session 1: $ANSWER_1 | Session 2: $ANSWER_2${NC}"
fi

# Test 3: Memory Prevention
echo "\n🧪 TEST 3: Memory Hallucination Prevention"
NEW_SESSION=$(uuidgen)
ANSWER=$(curl -s -X POST https://nuzantara-rag.fly.dev/api/agentic-rag/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query":"Ciao, sono nuovo qui","user_id":"zero@balizero.com","session_id":"'$NEW_SESSION'"}' | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['answer'].lower())")

PATTERNS=("so che" "ricordo che" "hai detto" "preferisci" "il tuo")
FOUND=false
for pattern in "${PATTERNS[@]}"; do
  if [[ "$ANSWER" == *"$pattern"* ]]; then
    FOUND=true
    break
  fi
done

if [ "$FOUND" = false ]; then
  echo "${GREEN}✅ PASS: No memory hallucination detected${NC}"
else
  echo "${RED}❌ FAIL: Memory hallucination detected in: $ANSWER${NC}"
fi

echo "\n${YELLOW}📊 Test Summary Complete${NC}"
```

## 🌐 Test via Frontend (zantara.balizero.com)

Puoi anche testare direttamente dal frontend:

1. **Test Greeting:**
   - Vai su https://zantara.balizero.com/chat
   - Scrivi "ciao"
   - ✅ Dovrebbe rispondere immediatamente senza chiamare RAG

2. **Test Session Isolation:**
   - Apri due finestre/browser diversi (o incognito)
   - Finestra 1: Scrivi "Il mio nome è Marco"
   - Finestra 2: Scrivi "Il mio nome è Luca"
   - Finestra 1: Chiedi "Come mi chiamo?"
   - ✅ Dovrebbe dire "Marco" (non "Luca")
   - Finestra 2: Chiedi "Come mi chiamo?"
   - ✅ Dovrebbe dire "Luca" (non "Marco")

3. **Test Memory Prevention:**
   - Apri una nuova finestra incognito
   - Scrivi "Ciao, sono nuovo qui"
   - ✅ La risposta NON dovrebbe menzionare fatti da sessioni precedenti

## 📝 Note

- Il rate limit sul login è di 5 richieste per 60 secondi
- Se vedi errori 429, aspetta 60 secondi prima di riprovare
- I test richiedono autenticazione JWT valida
- I session_id devono essere UUID univoci per ogni test

