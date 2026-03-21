import httpx
import os

def generate_pazuzu_audio():
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("Error: ELEVENLABS_API_KEY environment variable not set.")
        return
    
    headers = {
        "Accept": "application/json",
        "xi-api-key": api_key
    }

    # 1. Recupera le voci disponibili
    print("Recupero le voci disponibili...")
    with httpx.Client() as client:
        voices_response = client.get("https://api.elevenlabs.io/v1/voices", headers=headers)
        if voices_response.status_code != 200:
            print("Errore nel recupero delle voci.")
            return
            
        voices_data = voices_response.json()
        voices = voices_data.get("voices", [])
        
        if not voices:
            print("Nessuna voce trovata nell'account.")
            return
            
        # Cerca una voce adatta (nomi tipici di voci profonde/demoniache in ElevenLabs)
        target_names = ["The Beast", "Shadow", "Glinda", "Antoni", "Josh", "Arnold", "Callum", "Charlie", "Clyde"]
        selected_voice_id = None
        selected_voice_name = None
        
        for name in target_names:
            for v in voices:
                if v["name"].lower() == name.lower():
                    selected_voice_id = v["voice_id"]
                    selected_voice_name = v["name"]
                    break
            if selected_voice_id:
                break
                
        # Se non trova quelle specifiche, prende la prima voce disponibile che non sia "Cloned" (preferibilmente pre-made)
        if not selected_voice_id:
            for v in voices:
                if v.get("category") == "premade":
                    selected_voice_id = v["voice_id"]
                    selected_voice_name = v["name"]
                    break
                    
        # Fallback assoluto: la prima della lista
        if not selected_voice_id:
            selected_voice_id = voices[0]["voice_id"]
            selected_voice_name = voices[0]["name"]
            
        print(f"Voce selezionata: {selected_voice_name} (ID: {selected_voice_id})")

    # 2. Genera l'audio
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{selected_voice_id}"
    
    headers_tts = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    
    pazuzu_script = (
        "... [pause short] ... Ud-kur-uk-kur-ra ... [pause long] ... Pa-zu-zu ... "
        "Lu-gal i-mim ... Anto ... Igi lú-ulu bad-bad ... Anto ... "
        "Gi-gir-gir ... Ar-gug-gug ... Nu-ù ... Gaba-ri-mu ... Anto ... Si ... Gu-la."
    )
    
    data = {
        "text": pazuzu_script,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.20,        # Molto bassa per forzare instabilità demoniaca
            "similarity_boost": 0.85, 
            "style": 0.95,            # Massimo stile
            "use_speaker_boost": True
        }
    }

    print("Invocazione di Pazuzu via ElevenLabs in corso...")
    
    with httpx.Client() as client:
        response = client.post(url, json=data, headers=headers_tts, timeout=60.0)
        
        if response.status_code == 200:
            with open("pazuzu_invocation.mp3", "wb") as f:
                f.write(response.content)
            print("Evocazione completata! File salvato come: pazuzu_invocation.mp3")
        else:
            print(f"Errore ElevenLabs: {response.status_code} - {response.text}")

if __name__ == "__main__":
    generate_pazuzu_audio()
