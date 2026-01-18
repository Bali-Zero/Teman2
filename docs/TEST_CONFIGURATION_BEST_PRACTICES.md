# Test Configuration Best Practices

**Data:** 2026-01-19  
**Status:** ✅ Best Practices Document  
**Scope:** Gestione configurazioni e secrets nei test

---

## 🚨 REGOLA FONDAMENTALE: MAI CONFIGURAZIONI REALI NEI TEST

**Anche con venv, NON usare mai configurazioni reali nei test.**

### Perché?

1. **Venv ≠ Isolamento Secrets**
   - Venv isola le **dipendenze Python** (pacchetti, versioni)
   - Venv **NON isola** secrets, API keys, database credentials
   - I test possono accedere a file system, variabili d'ambiente, rete

2. **Rischi di Sicurezza**
   - Test possono fallire e esporre secrets nei log
   - Test possono inviare richieste reali a servizi esterni (costoso/pericoloso)
   - Test possono modificare dati reali in produzione
   - Secrets possono finire in commit, pull requests, CI/CD logs

3. **Riproducibilità**
   - Test devono essere deterministici (stesso risultato sempre)
   - Configurazioni reali dipendono da stato esterno (API rate limits, DB state)
   - Test devono funzionare offline, senza connessioni esterne

---

## 🏢 COME FUNZIONA NELLE ENTERPRISE

### 1. Separazione Ambienti (Environment Separation)

```
┌─────────────────────────────────────────────────────────┐
│                    AMBIENTI SEPARATI                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Development  →  Staging  →  Production                 │
│      ↓              ↓            ↓                      │
│  Config Dev    Config Staging  Config Prod              │
│  Secrets Dev   Secrets Staging  Secrets Prod            │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

**Ogni ambiente ha:**

- Database separato
- API keys separate
- Secrets separati
- Configurazioni separate

### 2. Secrets Management

#### Opzione A: Secrets Manager (AWS Secrets Manager, HashiCorp Vault, Azure Key Vault)

```python
# Production
from aws_secretsmanager import get_secret

api_key = get_secret("zantara/openai_api_key")  # Recuperato da AWS Secrets Manager

# Test
api_key = "sk-test-mock-key"  # Mock locale
```

#### Opzione B: Environment Variables (più comune)

```bash
# Production (.env non committato)
OPENAI_API_KEY=sk-real-key-12345

# Test (hardcoded o da conftest.py)
OPENAI_API_KEY=sk-test-mock-key
```

#### Opzione C: Config Files (non committati)

```python
# Production: config/production.yaml (non in git)
api_keys:
  openai: sk-real-key-12345

# Test: config/test.yaml (in git, con valori mock)
api_keys:
  openai: sk-test-mock-key
```

### 3. Test Isolation Pattern

```python
# ✅ CORRETTO: Mock nei test
@pytest.fixture
def mock_openai_client():
    with patch("backend.llm.openai_client.OpenAIClient") as mock:
        mock.return_value.generate.return_value = "Mock response"
        yield mock

# ❌ SBAGLIATO: Usare API key reale
def test_something():
    client = OpenAIClient(api_key=os.getenv("OPENAI_API_KEY"))  # NO!
```

---

## 📋 BEST PRACTICES PER NUZANTARA

### 1. Test Configuration (conftest.py)

```python
# ✅ CORRETTO: Mock Settings nei test
import os
import sys
from unittest.mock import MagicMock

# Set test environment variables (valori mock)
os.environ.setdefault("OPENAI_API_KEY", "sk-test-mock-key")
os.environ.setdefault("GOOGLE_API_KEY", "test-google-key")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

# Mock Settings class
_mock_settings = MagicMock()
_mock_settings.openai_api_key = "sk-test-mock-key"
_mock_settings.database_url = "postgresql://test:test@localhost:5432/test"
```

### 2. Separazione Configurazioni

```
apps/backend-rag/
├── backend/
│   ├── app/
│   │   └── core/
│   │       └── config.py          # Settings (legge da env vars)
│   └── tests/
│       └── unit/
│           └── services/
│               └── misc/
│                   └── conftest.py # Test config (mock values)
├── .env                           # ❌ NON COMMITTARE (gitignore)
├── .env.example                   # ✅ Template (committato)
└── .env.test                      # ✅ Test config (committato, valori mock)
```

### 3. Gitignore Pattern

```gitignore
# Secrets e configurazioni reali
.env
.env.local
.env.production
*.key
*.pem
secrets/
config/production.yaml
config/staging.yaml

# ✅ Committare
.env.example          # Template senza valori reali
.env.test             # Config test con valori mock
config/test.yaml      # Config test
```

### 4. CI/CD Configuration

```yaml
# .github/workflows/test.yml
env:
  # Test environment variables (valori mock)
  OPENAI_API_KEY: sk-test-mock-key
  GOOGLE_API_KEY: test-google-key
  DATABASE_URL: postgresql://test:test@localhost:5432/test

  # Production secrets (da GitHub Secrets, mai hardcoded)
  # OPENAI_API_KEY_PROD: ${{ secrets.OPENAI_API_KEY_PROD }}
```

---

## 🔒 SECURITY CHECKLIST

### ✅ DO (Fare)

1. **Usare sempre valori mock nei test**

   ```python
   os.environ.setdefault("OPENAI_API_KEY", "sk-test-mock-key")
   ```

2. **Mockare chiamate API esterne**

   ```python
   @patch("backend.llm.openai_client.OpenAIClient")
   def test_something(mock_client):
       mock_client.return_value.generate.return_value = "Mock"
   ```

3. **Usare database di test separato**

   ```python
   DATABASE_URL = "postgresql://test:test@localhost:5432/test_db"
   ```

4. **Documentare configurazioni necessarie**

   ```python
   # .env.example
   OPENAI_API_KEY=your-openai-api-key-here
   DATABASE_URL=postgresql://user:pass@host:port/db
   ```

5. **Verificare .gitignore**
   ```bash
   git check-ignore .env  # Deve restituire .env
   ```

### ❌ DON'T (Non Fare)

1. **NON committare secrets**

   ```bash
   # ❌ SBAGLIATO
   git add .env
   git commit -m "Add config"
   ```

2. **NON usare API keys reali nei test**

   ```python
   # ❌ SBAGLIATO
   client = OpenAIClient(api_key=os.getenv("OPENAI_API_KEY"))
   ```

3. **NON hardcodare secrets nel codice**

   ```python
   # ❌ SBAGLIATO
   API_KEY = "sk-real-key-12345"
   ```

4. **NON loggare secrets**

   ```python
   # ❌ SBAGLIATO
   logger.info(f"API Key: {api_key}")

   # ✅ CORRETTO
   logger.info(f"API Key: {api_key[:10]}...")
   ```

5. **NON condividere secrets via chat/email**
   - Usare password manager (1Password, LastPass)
   - Usare secrets manager (AWS Secrets Manager, Vault)
   - Usare variabili d'ambiente protette

---

## 🎯 PATTERN RACCOMANDATO PER NUZANTARA

### 1. Struttura File

```
apps/backend-rag/
├── .env.example              # Template (committato)
├── .env.test                 # Test config (committato, valori mock)
├── .env                      # Real config (gitignore, NON committare)
├── backend/
│   ├── app/core/config.py    # Settings (legge da env)
│   └── tests/
│       └── conftest.py       # Test setup (mock values)
└── .gitignore                # Include .env
```

### 2. .env.example (Template)

```bash
# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key-here

# Google Configuration
GOOGLE_API_KEY=your-google-api-key-here

# Database Configuration
DATABASE_URL=postgresql://user:password@host:port/database

# Qdrant Configuration
QDRANT_URL=http://localhost:6333

# JWT Configuration
JWT_SECRET_KEY=your-secret-key-min-32-chars
```

### 3. .env.test (Test Config - Committato)

```bash
# Test Configuration (valori mock, sicuri da committare)
OPENAI_API_KEY=sk-test-mock-key-for-testing-only
GOOGLE_API_KEY=test-google-key-mock
DATABASE_URL=postgresql://test:test@localhost:5432/test_db
QDRANT_URL=http://localhost:6333
JWT_SECRET_KEY=test_jwt_secret_key_for_testing_only_min_32_chars
ENVIRONMENT=test
```

### 4. conftest.py Pattern

```python
"""
Test configuration - Always uses mock values
"""
import os
import sys
from unittest.mock import MagicMock

# Set test environment variables (mock values)
os.environ.setdefault("OPENAI_API_KEY", "sk-test-mock-key")
os.environ.setdefault("GOOGLE_API_KEY", "test-google-key")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("ENVIRONMENT", "test")

# Mock Settings to prevent validation errors
_mock_settings = MagicMock()
_mock_settings.openai_api_key = "sk-test-mock-key"
_mock_settings.database_url = "postgresql://test:test@localhost:5432/test"
_mock_settings.environment = "test"

# Patch config module before imports
if "backend.app.core.config" not in sys.modules:
    fake_config = type(sys)("backend.app.core.config")
    fake_config.settings = _mock_settings
    sys.modules["backend.app.core.config"] = fake_config
```

---

## 📊 COMPARAZIONE: Venv vs Secrets Management

| Aspetto             | Venv                | Secrets Management        |
| ------------------- | ------------------- | ------------------------- |
| **Cosa isola**      | Dipendenze Python   | Credenziali, API keys     |
| **Dove**            | Locale (`.venv/`)   | Esterno (Secrets Manager) |
| **Committato?**     | No (gitignore)      | Mai                       |
| **Usato nei test?** | Sì (dipendenze)     | No (mock values)          |
| **Sicurezza**       | Isolamento versioni | Isolamento dati sensibili |

**Conclusione:** Venv e Secrets Management risolvono problemi diversi. Entrambi sono necessari.

---

## 🎓 ESEMPI ENTERPRISE

### Google Cloud

```python
# Production
from google.cloud import secretmanager

client = secretmanager.SecretManagerServiceClient()
name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
response = client.access_secret_version(request={"name": name})
api_key = response.payload.data.decode("UTF-8")

# Test
api_key = "test-mock-key"
```

### AWS

```python
# Production
import boto3
client = boto3.client('secretsmanager')
response = client.get_secret_value(SecretId='zantara/openai_api_key')
api_key = json.loads(response['SecretString'])['api_key']

# Test
api_key = "test-mock-key"
```

### HashiCorp Vault

```python
# Production
import hvac
client = hvac.Client(url='https://vault.example.com')
client.token = os.getenv('VAULT_TOKEN')
secret = client.secrets.kv.v2.read_secret_version(path='zantara/openai')
api_key = secret['data']['data']['api_key']

# Test
api_key = "test-mock-key"
```

---

## ✅ RACCOMANDAZIONE FINALE PER NUZANTARA

1. **Mantenere pattern attuale** (mock nei test)
2. **Aggiungere .env.example** (template senza valori reali)
3. **Aggiungere .env.test** (valori mock, committato)
4. **Verificare .gitignore** (include .env)
5. **Documentare** (questo documento)

**Venv è per isolare dipendenze, NON per gestire secrets. I secrets devono sempre essere mockati nei test.**

---

**Last Updated:** 2026-01-19
