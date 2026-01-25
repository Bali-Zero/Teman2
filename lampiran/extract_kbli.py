import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
import json
import re
import os

# --- CONFIGURAZIONE ---
# Usa percorsi assoluti per evitare errori di "File not found"
base_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = "KBLI_Masterpiece_FULL.json"
output_filename = "KBLI_Cleaned_Ready.json"

input_path = os.path.join(base_dir, input_filename)
output_path = os.path.join(base_dir, output_filename)

# --- 1. CARICAMENTO DATI (La parte mancante) ---
print(f"🔍 Cerco il file in: {input_path}")

try:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ File caricato con successo: {len(data)} record trovati.")
except FileNotFoundError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è stato trovato.")
    print("   Assicurati che il file JSON sia nella stessa cartella dello script.")
    exit(1)
except json.JSONDecodeError:
    print(f"❌ ERRORE CRITICO: Il file '{input_filename}' non è un JSON valido.")
    exit(1)

# --- 2. DEFINIZIONE REGEX ---
# Regex per trovare parole spezzate da a capo (es: "pembangun- \n an")
hyphen_pattern = re.compile(r"(\w+)-\s+(\w+)")

# Regex per rimuovere intestazioni ricorrenti (Noise)
header_patterns = [
    r"PRES\s?IDEN\s+REPUBLIK\s+INDONESIA",
    r"No\s+Kode\s+Judul\s+Ruang\s+Skala",
    r"SK\s+No\s+\d+\s+C",
    r"I\.C\.\d+",
]

cleaned_data = []

# --- 3. ELABORAZIONE ---
print("⚙️  Avvio pulizia testo...")
for entry in data:
    text = entry.get("text_originale", "")

    if text:
        # A. Rimuovi intestazioni (Headers)
        for pattern in header_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # B. Ripara parole spezzate (De-hyphenation)
        # Esegue il loop finché non ci sono più match
        while hyphen_pattern.search(text):
            text = hyphen_pattern.sub(r"\1\2", text)

        # C. Rimuovi spazi multipli e newlines
        text = re.sub(r"\s+", " ", text).strip()

        # Aggiorna il testo nel dizionario
        entry["text_originale"] = text

    cleaned_data.append(entry)

# --- 4. SALVATAGGIO ---
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print(f"🚀 Successo! File pulito salvato in: {output_filename}")
