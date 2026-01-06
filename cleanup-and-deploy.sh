#!/bin/bash
set -e

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}=== CLEANUP & DEPLOY SCRIPT ===${NC}\n"

# 1. Mostra macchine attuali
echo -e "${YELLOW}1. Macchine attuali nuzantara-rag:${NC}"
fly machine list -a nuzantara-rag

# 2. Conteggio
MACHINE_COUNT=$(fly machine list -a nuzantara-rag --json | jq '. | length')
echo -e "\n${YELLOW}Totale macchine: ${MACHINE_COUNT}${NC}"

# 3. Chiedi conferma distruzione
echo -e "\n${RED}Vuoi distruggere tutte le macchine tranne 1? (yes/no)${NC}"
read -r CONFIRM

if [ "$CONFIRM" = "yes" ]; then
    # Prendi lista machine IDs
    MACHINE_IDS=$(fly machine list -a nuzantara-rag --json | jq -r '.[].id')

    # Converti in array
    IDS_ARRAY=($MACHINE_IDS)
    KEEP_FIRST="${IDS_ARRAY[0]}"

    echo -e "${GREEN}Mantengo la macchina: ${KEEP_FIRST}${NC}"
    echo -e "${RED}Distruggo le altre...${NC}\n"

    # Distruggi tutte tranne la prima
    for id in "${IDS_ARRAY[@]:1}"; do
        echo "Distruggendo ${id}..."
        fly machine destroy "$id" -a nuzantara-rag --force
        sleep 1
    done

    echo -e "\n${GREEN}✓ Cleanup completato!${NC}"
else
    echo -e "${YELLOW}Cleanup saltato${NC}"
fi

# 4. Deploy apps con autostop
echo -e "\n${YELLOW}=== DEPLOY CON AUTOSTOP ===${NC}\n"

echo -e "${YELLOW}Deploy backend-rag...${NC}"
cd apps/backend-rag
fly deploy --ha=false
cd ../..

echo -e "\n${YELLOW}Deploy mouth...${NC}"
cd apps/mouth
fly deploy --ha=false
cd ../..

echo -e "\n${YELLOW}Deploy bali-intel-scraper...${NC}"
cd apps/bali-intel-scraper
fly deploy --ha=false
cd ../..

# 5. Verifica finale
echo -e "\n${GREEN}=== VERIFICA FINALE ===${NC}\n"

echo "nuzantara-rag:"
fly machine list -a nuzantara-rag

echo -e "\nnuzantara-mouth:"
fly machine list -a nuzantara-mouth

echo -e "\nbali-intel-scraper:"
fly machine list -a bali-intel-scraper

echo -e "\n${GREEN}✓ Tutto completato!${NC}"
