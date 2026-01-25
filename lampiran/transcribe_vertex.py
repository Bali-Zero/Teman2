import vertexai
from vertexai.generative_models import GenerativeModel, Part
import os
import json

# Percorsi Assoluti (Hardcoded per sicurezza)
PDF_PATH = "/Users/antonellosiano/Desktop/nuzantara/lampiran/2.3 Lampiran I.C PP Nomor 28 Tahun 2025 (I.C.1-182) (1).pdf"
OUTPUT_FILE = (
    "/Users/antonellosiano/Desktop/nuzantara/lampiran/KBLI_Lampiran_I_C_Extracted.json"
)

# Configurazione Ambiente (usa gcloud application-default credentials)
PROJECT_ID = "nuzantara"
LOCATION = "us-central1"  # Changed from 'global' to supported region
MODEL_NAME = "gemini-1.5-pro"  # Standard model name without version suffix


def main():
    print(f"🚀 Avvio Vertex AI: {PROJECT_ID}")

    # Init Vertex
    try:
        vertexai.init(project=PROJECT_ID, location=LOCATION)
    except Exception as e:
        print(f"❌ Errore Init: {e}")
        return

    # Check File
    if not os.path.exists(PDF_PATH):
        print(f"❌ Errore: File PDF non trovato: {PDF_PATH}")
        return

    # Load Model & File
    print("📄 Caricamento PDF...")
    try:
        model = GenerativeModel(MODEL_NAME)
        with open(PDF_PATH, "rb") as f:
            pdf_bytes = f.read()
        pdf_part = Part.from_data(data=pdf_bytes, mime_type="application/pdf")
    except Exception as e:
        print(f"❌ Errore caricamento: {e}")
        return

    # Prompt Semplificato (per evitare errori di parsing shell)
    prompt_text = """
    Analizza il documento PDF. Estrai TUTTI i record della tabella in un array JSON valido.
    
    REGOLE:
    1. Trascrizione INTEGRALE di ogni colonna (Persyaratan, Kewajiban, ecc).
    2. Unisci le parole che vanno a capo.
    3. Ogni numero nella colonna 'No' e' un nuovo oggetto.
    4. Usa le chiavi: no, kode_kbli, judul_kbli, ruang_lingkup, tingkat_risiko, perizinan, jangka_waktu, persyaratan, kewajiban, kewenangan.
    
    Restituisci SOLO il JSON puro, senza markdown.
    """

    print("⚡️ Invio a Gemini (Attendi)...")
    try:
        resp = model.generate_content(
            [pdf_part, prompt_text],
            generation_config={
                "max_output_tokens": 8192,
                "temperature": 0.0,
                "response_mime_type": "application/json",
            },
        )

        # Pulizia e Salvataggio
        clean_json = resp.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
            json.dump(data, out, indent=2, ensure_ascii=False)

        print(f"🎉 Successo! File salvato: {OUTPUT_FILE}")
        print(f"📊 Estratti {len(data)} record.")

    except Exception as e:
        print(f"❌ Errore esecuzione: {e}")
        if "resp" in locals():
            with open("debug_error.txt", "w") as f:
                f.write(resp.text)


if __name__ == "__main__":
    main()
