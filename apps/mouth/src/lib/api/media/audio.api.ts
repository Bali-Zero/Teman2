import { ApiClientBase } from '../client';

/**
 * Audio Services API methods
 */
export class AudioApi {
  constructor(private client: ApiClientBase) {}

  async transcribeAudio(audioBlob: Blob, mimeType: string = 'audio/webm'): Promise<string> {
    const formData = new FormData();

    // Determine extension based on mimeType
    let extension = 'webm';
    if (mimeType.includes('mp4')) {
      extension = 'mp4';
    } else if (mimeType.includes('wav')) {
      extension = 'wav';
    } else if (mimeType.includes('mpeg') || mimeType.includes('mp3')) {
      extension = 'mp3';
    }

    // OpenAI API often requires a filename with an extension for MIME type detection
    formData.append('file', audioBlob, `recording.${extension}`);

    // We use fetch directly here to handle FormData properly without stringifying
    const baseUrl = this.client.getBaseUrl();
    const token = this.client.getToken();
    const csrf = this.client.getCsrfToken();

    const response = await fetch(`${baseUrl}/api/audio/transcribe`, {
      method: 'POST',
      headers: {
        // Content-Type is set automatically by fetch when using FormData
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(csrf ? { 'X-CSRF-Token': csrf } : {}),
      },
      body: formData,
      credentials: 'include',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Transcription failed');
    }

    const data = await response.json();
    return data.text;
  }

  async generateSpeech(
    text: string,
    voice: 'alloy' | 'echo' | 'fable' | 'onyx' | 'nova' | 'shimmer' = 'alloy'
  ): Promise<Blob> {
    const baseUrl = this.client.getBaseUrl();
    const token = this.client.getToken();
    const csrf = this.client.getCsrfToken();

    const response = await fetch(`${baseUrl}/api/audio/speech`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(csrf ? { 'X-CSRF-Token': csrf } : {}),
      },
      body: JSON.stringify({ text, voice }),
      credentials: 'include',
    });

    if (!response.ok) {
      throw new Error('Speech generation failed');
    }
    return response.blob();
  }
}

