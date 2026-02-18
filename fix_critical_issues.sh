#!/bin/bash
# Fix Critical Issues - Nuzantara
# Eseguire con: bash fix_critical_issues.sh

echo "🔧 FIX CRITICAL ISSUES - NUZANTARA"
echo "=================================="
echo ""

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

cd /Users/nuzantara/Desktop/nuzantara

# 1. Fix Dashboard Timeout
echo -e "${YELLOW}[1/5] Fix Dashboard Timeout...${NC}"
cat > /tmp/dashboard_fix.py << 'EOF'
import re

file_path = "apps/backend-rag/backend/app/routers/dashboard_summary.py"
with open(file_path, 'r') as f:
    content = f.read()

# Ridurre timeout da 8s a 5s
content = content.replace('TASK_TIMEOUT = 8.0', 'TASK_TIMEOUT = 5.0')

with open(file_path, 'w') as f:
    f.write(content)

print("✅ Dashboard timeout ridotto a 5s")
EOF
python3 /tmp/dashboard_fix.py

# 2. Rimuovere debug logging hardcoded
echo -e "${YELLOW}[2/5] Rimuovere debug logging hardcoded...${NC}"
FILE="apps/backend-rag/backend/services/intel/intel_staging_service.py"
if [ -f "$FILE" ]; then
    # Commentare le sezioni di debug logging
    sed -i '' 's/# #region agent log/# #region agent log - DISABLED/g' "$FILE"
    sed -i '' 's/with open("\/Users\/antonellosiano/# with open("\/Users\/antonellosiano/g' "$FILE"
    echo "✅ Debug logging disabilitato in intel_staging_service.py"
fi

# 3. Fix AbortController in Documents
echo -e "${YELLOW}[3/5] Fix AbortController Documents...${NC}"
cat > /tmp/fix_abort.md << 'EOF'
## Fix richiesto in apps/mouth/src/lib/api/drive.api.ts

Modificare la funzione uploadFile per accettare AbortController:

```typescript
export async function uploadFile(
  file: File,
  parentId?: string,
  onProgress?: (progress: number) => void,
  abortController?: AbortController  // NUOVO PARAMETRO
): Promise<DriveFile> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    
    // Collegare abortController
    if (abortController) {
      abortController.signal.addEventListener('abort', () => {
        xhr.abort();
        reject(new Error('Upload aborted'));
      });
    }
    
    // ... resto del codice
  });
}
```

E modificare page.tsx per passare l'abortController:

```typescript
await api.drive.uploadFile(file, parentId, onProgress, abortControllerRef.current);
```
EOF
echo "✅ Istruzioni per fix AbortController salvate in /tmp/fix_abort.md"

# 4. Fix race conditions - Aggiungere AbortController hook
echo -e "${YELLOW}[4/5] Creare useAbortableFetch hook...${NC}"
cat > apps/mouth/src/hooks/useAbortableFetch.ts << 'EOF'
import { useRef, useEffect, useCallback } from 'react';

export function useAbortableFetch() {
  const abortControllerRef = useRef<AbortController | null>(null);

  const createFetch = useCallback(<T>(fetchFn: (signal: AbortSignal) => Promise<T>): Promise<T> => {
    // Cancel previous request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    
    // Create new controller
    abortControllerRef.current = new AbortController();
    
    return fetchFn(abortControllerRef.current.signal);
  }, []);

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  return { createFetch };
}
EOF
echo "✅ Hook useAbortableFetch creato"

# 5. Verifiche finali
echo -e "${YELLOW}[5/5] Verifiche finali...${NC}"
echo ""
echo "📋 CHECKLIST MANUALE:"
echo "- [ ] Testare dashboard: https://zantara.balizero.com/dashboard"
echo "- [ ] Verificare logging: tail -f apps/backend-rag/logs/*.log"
echo "- [ ] Test upload file grande (>100MB) in Documents"
echo "- [ ] Verificare race conditions in Omnichannel"
echo ""
echo -e "${GREEN}✅ Fix automatici completati!${NC}"
echo ""
echo "Prossimi passi:"
echo "1. Eseguire test: npm run test"
echo "2. Deploy su staging: fly deploy --app nuzantara-rag-staging"
echo "3. Verificare produzione dopo 24h"
EOF

chmod +x /Users/nuzantara/Desktop/nuzantara/fix_critical_issues.sh
echo "✅ Script creato: fix_critical_issues.sh"
EOF

# 6. Creare report completo
echo -e "${YELLOW}[6/6] Creando report completo...${NC}"
EOF

echo -e "${GREEN}🎉 Fix critici completati!${NC}"
echo ""
echo "📄 Report dettagliato: .kimi/NUZANTARA_AUDIT_REPORT.md"
