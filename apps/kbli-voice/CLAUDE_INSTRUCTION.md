Claude, I need you to automate the retrieval of my valid ElevenLabs API key.

1. Navigate to https://elevenlabs.io/app/settings/api-keys
2. Ensure you are logged in (session should be active).
3. Look for the "Master API Key" or "Profile API Key" (it often starts with `sk_...` or is a 32-character string that has Full Access to Text-to-Speech).
4. If the key is hidden, click the "eye" icon or the "copy" button to reveal/copy it.
5. Once you have the valid key, execute the following command in my terminal to test it immediately:

```bash
export ELEVENLABS_API_KEY="THE_KEY_YOU_FOUND"
cd /Users/nuzantara/Desktop/nuzantara/apps/kbli-voice
python3 talk.py
```

_(Note: If talk.py prompts for input, just pass a test string like "echo 'Testing voice' | python3 talk.py" or just verify the key is correct)._

6. If you cannot find the master key, create a new one with "Text to Speech" permissions set to "Access" and use that one.
