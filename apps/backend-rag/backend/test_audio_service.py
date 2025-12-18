
import asyncio
import os
from dotenv import load_dotenv
import sys

# Add current directory to path so imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load .env from parent directory
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
print(f"Loading .env from: {dotenv_path}")
load_dotenv(dotenv_path)

from app.services.audio_service import AudioService
from app.core.config import settings

async def test_audio():
    print("--- Testing Audio Service ---")
    # Force reload of settings if needed, but usually env var set before import helps
    # However, 'settings' object is instantiated at import time in config.py. 
    # Since we import settings AFTER load_dotenv might not be enough if config.py was already imported? 
    # Actually python imports are cached. 
    # But here we import it after load_dotenv.
    
    print(f"API Key present: {bool(settings.openai_api_key)}")
    if settings.openai_api_key:
        print(f"API Key prefix: {settings.openai_api_key[:8]}...")
    
    try:
        service = AudioService()
        if not service.client:
            print("ERROR: Client not initialized (missing key?)")
            return

        print("1. Testing TTS (Speech Generation)...")
        # Generate a small speech file
        text = "Hello, this is a test of the Zantara Audio System."
        audio_bytes = await service.generate_speech(text)
        print(f"SUCCESS: Generated {len(audio_bytes)} bytes of audio.")
        
        # Save it momentarily to test transcription
        test_filename = "test_audio.mp3"
        with open(test_filename, "wb") as f:
            f.write(audio_bytes)
            
        print("2. Testing Transcription (Whisper)...")
        with open(test_filename, "rb") as f:
            # Mocking the file-like object structure usually passed
            # File object from open() has .name attribute, confusing Whisper sometimes if not string path?
            # modifying to pass path directly for simplicity in logic check, but service handles both.
             transcription = await service.transcribe_audio(test_filename)
        
        print(f"SUCCESS: Transcription result: '{transcription}'")
        
        # Cleanup
        os.remove(test_filename)
        print("--- Audio Service Test PASSED ---")

    except Exception as e:
        print(f"--- Audio Service Test FAILED ---")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_audio())
