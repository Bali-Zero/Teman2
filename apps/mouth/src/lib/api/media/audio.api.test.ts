import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AudioApi } from './audio.api';
import { ApiClientBase } from '../client';

describe('AudioApi', () => {
  let audioApi: AudioApi;
  let mockClient: ApiClientBase;

  beforeEach(() => {
    global.fetch = vi.fn();
    mockClient = {
      getCsrfToken: vi.fn(() => 'csrf-token'),
      getToken: vi.fn(() => 'auth-token'),
      getBaseUrl: vi.fn(() => 'https://api.test.com'),
    } as any;
    audioApi = new AudioApi(mockClient);
  });

  describe('transcribeAudio', () => {
    it('should transcribe audio with webm format', async () => {
      const audioBlob = new Blob(['audio data'], { type: 'audio/webm' });
      const mockResponse = { text: 'Transcribed text' };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await audioApi.transcribeAudio(audioBlob, 'audio/webm');

      expect(global.fetch).toHaveBeenCalledWith(
        'https://api.test.com/api/audio/transcribe',
        expect.objectContaining({
          method: 'POST',
          headers: {
            Authorization: 'Bearer auth-token',
            'X-CSRF-Token': 'csrf-token',
          },
          credentials: 'include',
        })
      );
      expect(result).toBe('Transcribed text');
    });

    it('should handle different audio formats', async () => {
      const mockResponse = { text: 'Transcribed' };
      (global.fetch as any).mockResolvedValue({ ok: true, json: async () => mockResponse });

      await audioApi.transcribeAudio(new Blob(['data']), 'audio/mp4');
      expect((global.fetch as any).mock.calls[0][1].body).toBeInstanceOf(FormData);

      await audioApi.transcribeAudio(new Blob(['data']), 'audio/wav');
      await audioApi.transcribeAudio(new Blob(['data']), 'audio/mpeg');
    });

    it('should throw error on failed transcription', async () => {
      const audioBlob = new Blob(['data'], { type: 'audio/webm' });

      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: 'Transcription failed' }),
      });

      await expect(audioApi.transcribeAudio(audioBlob)).rejects.toThrow('Transcription failed');
    });

    it('should handle JSON parse error gracefully', async () => {
      const audioBlob = new Blob(['data'], { type: 'audio/webm' });

      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        json: async () => {
          throw new Error('Parse error');
        },
      });

      await expect(audioApi.transcribeAudio(audioBlob)).rejects.toThrow();
    });
  });

  describe('generateSpeech', () => {
    it('should generate speech with default voice', async () => {
      const mockBlob = new Blob(['audio data'], { type: 'audio/mpeg' });

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        blob: async () => mockBlob,
      });

      const result = await audioApi.generateSpeech('Hello world');

      expect(global.fetch).toHaveBeenCalledWith(
        'https://api.test.com/api/audio/speech',
        expect.objectContaining({
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: 'Bearer auth-token',
            'X-CSRF-Token': 'csrf-token',
          },
          body: JSON.stringify({ text: 'Hello world', voice: 'alloy' }),
          credentials: 'include',
        })
      );
      expect(result).toBe(mockBlob);
    });

    it('should generate speech with custom voice', async () => {
      const mockBlob = new Blob(['audio'], { type: 'audio/mpeg' });
      (global.fetch as any).mockResolvedValueOnce({ ok: true, blob: async () => mockBlob });

      await audioApi.generateSpeech('Hello', 'nova');

      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: expect.stringContaining('"voice":"nova"'),
        })
      );
    });

    it('should throw error on failed speech generation', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        statusText: 'Internal Server Error',
      });

      await expect(audioApi.generateSpeech('Hello')).rejects.toThrow(
        'Speech generation failed'
      );
    });
  });
});

