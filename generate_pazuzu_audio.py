# To run this code you need to install the following dependencies:
# pip install google-genai
import mimetypes
import os
import struct
from google import genai
from google.genai import types

def save_binary_file(file_name, data):
    with open(file_name, "wb") as f:
        f.write(data)
    print(f"File saved to: {file_name}")

def generate():
    import os
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        return
    client = genai.Client(
        api_key=api_key,
    )

    # Debug: lista i modelli per verificare la disponibilità
    print("Verifica modelli disponibili...")
    try:
        models = client.models.list()
        for m in models:
            if "tts" in m.name.lower():
                print(f"Modello TTS trovato: {m.name}")
    except Exception as e:
        print(f"Errore durante il recupero dei modelli: {e}")

    model = "gemini-2.5-flash-preview-tts"
    
    pazuzu_script_simple = (
        "Udkurukkurra. Pazuzu. "
        "lugal imim. Anto. "
        "igi lú-ulu bad-bad. Anto. "
        "Gi-gir-gir. Ar-gug-gug. "
        "Nu-ù. Gaba-ri-mu. Anto. "
        "Si. Gu-la."
    )

    style_instructions = (
        "Speak with a deep, guttural, and gravelly demonic voice. "
        "Slow and ancient tone."
    )

    generate_content_config = types.GenerateContentConfig(
        temperature=0.45,
        response_modalities=["audio"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Fenrir"
                )
            )
        ),
    )

    print("Evocazione in corso (modello FLASH)...")
    try:
        response = client.models.generate_content(
            model=model,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=f"{style_instructions}\n\nText to speak: {pazuzu_script_simple}"),
                    ],
                ),
            ],
            config=generate_content_config,
        )

        for i, part in enumerate(response.parts):
            if part.inline_data and part.inline_data.data:
                file_name = f"pazuzu_message_{i}"
                inline_data = part.inline_data
                data_buffer = inline_data.data
                
                file_extension = mimetypes.guess_extension(inline_data.mime_type)
                if file_extension is None:
                    file_extension = ".wav"
                    data_buffer = convert_to_wav(inline_data.data, inline_data.mime_type)
                    
                save_binary_file(f"{file_name}{file_extension}", data_buffer)
            elif part.text:
                print(f"Log: {part.text}")
    except Exception as e:
        print(f"Error: {e}")

def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    parameters = parse_audio_mime_type(mime_type)
    bits_per_sample = parameters["bits_per_sample"]
    sample_rate = parameters["rate"]
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", chunk_size, b"WAVE", b"fmt ", 16, 1,
        num_channels, sample_rate, byte_rate, block_align,
        bits_per_sample, b"data", data_size
    )
    return header + audio_data

def parse_audio_mime_type(mime_type: str) -> dict:
    bits_per_sample = 16
    rate = 24000
    parts = mime_type.split(";")
    for param in parts:
        param = param.strip().lower()
        if param.startswith("rate="):
            rate = int(param.split("=")[1])
        elif "audio/l" in param:
            bits_per_sample = int(param.split("l")[1])
    return {"bits_per_sample": bits_per_sample, "rate": rate}

if __name__ == "__main__":
    generate()
