#!/bin/bash
# Script per eseguire tutti i test di integrazione

set -e

echo "🧪 Esecuzione Test di Integrazione Nuzantara"
echo "=============================================="

# Colori per output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Verifica variabili d'ambiente
echo -e "${YELLOW}Verifica variabili d'ambiente...${NC}"

if [ -z "$DATABASE_URL" ]; then
    echo -e "${YELLOW}⚠️  DATABASE_URL non impostata, uso default${NC}"
    export DATABASE_URL="postgresql://test:test@localhost:5432/test"
fi

if [ -z "$QDRANT_URL" ]; then
    echo -e "${YELLOW}⚠️  QDRANT_URL non impostata, uso default${NC}"
    export QDRANT_URL="http://localhost:6333"
fi

if [ -z "$JWT_SECRET_KEY" ]; then
    echo -e "${YELLOW}⚠️  JWT_SECRET_KEY non impostata, uso test key${NC}"
    export JWT_SECRET_KEY="test_jwt_secret_key_for_testing_only_min_32_chars"
fi

# Verifica connessione database
echo -e "${YELLOW}Verifica connessione PostgreSQL...${NC}"
if command -v psql &> /dev/null; then
    if psql "$DATABASE_URL" -c "SELECT 1" &> /dev/null; then
        echo -e "${GREEN}✅ PostgreSQL connesso${NC}"
    else
        echo -e "${RED}❌ Errore connessione PostgreSQL${NC}"
        echo "Assicurati che PostgreSQL sia in esecuzione e DATABASE_URL sia corretta"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  psql non trovato, skip verifica${NC}"
fi

# Verifica connessione Qdrant
echo -e "${YELLOW}Verifica connessione Qdrant...${NC}"
if command -v curl &> /dev/null; then
    if curl -s "$QDRANT_URL/collections" &> /dev/null; then
        echo -e "${GREEN}✅ Qdrant connesso${NC}"
    else
        echo -e "${RED}❌ Errore connessione Qdrant${NC}"
        echo "Assicurati che Qdrant sia in esecuzione e QDRANT_URL sia corretta"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  curl non trovato, skip verifica${NC}"
fi

# Naviga alla directory backend
cd "$(dirname "$0")/../backend" || exit 1

# Esegui test
echo -e "\n${GREEN}Esecuzione test di integrazione...${NC}\n"

# Opzioni di default
PYTEST_OPTS="-v --tb=short --color=yes"

# Parse argomenti
RUN_ALL=false
RUN_SLOW=false
RUN_FAST=false
FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --all)
            RUN_ALL=true
            shift
            ;;
        --slow)
            RUN_SLOW=true
            shift
            ;;
        --fast)
            RUN_FAST=true
            shift
            ;;
        --file)
            FILE="$2"
            shift 2
            ;;
        --coverage)
            PYTEST_OPTS="$PYTEST_OPTS --cov=app --cov=services --cov-report=html"
            shift
            ;;
        *)
            echo "Opzione sconosciuta: $1"
            echo "Uso: $0 [--all|--slow|--fast] [--file FILE] [--coverage]"
            exit 1
            ;;
    esac
done

# Determina quali test eseguire
if [ -n "$FILE" ]; then
    TEST_PATH="tests/integration/$FILE"
elif [ "$RUN_ALL" = true ]; then
    TEST_PATH="tests/integration/"
elif [ "$RUN_SLOW" = true ]; then
    TEST_PATH="tests/integration/ -m slow"
elif [ "$RUN_FAST" = true ]; then
    TEST_PATH="tests/integration/ -m 'integration and not slow'"
else
    # Default: esegui tutti tranne slow
    TEST_PATH="tests/integration/ -m 'integration and not slow'"
fi

# Esegui pytest
echo -e "${GREEN}Esecuzione: pytest $PYTEST_OPTS $TEST_PATH${NC}\n"

if pytest $PYTEST_OPTS $TEST_PATH; then
    echo -e "\n${GREEN}✅ Tutti i test passati!${NC}"
    exit 0
else
    echo -e "\n${RED}❌ Alcuni test sono falliti${NC}"
    exit 1
fi

