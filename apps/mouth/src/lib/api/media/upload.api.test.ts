import { describe, it, expect, vi, beforeEach } from 'vitest';
import { UploadApi } from './upload.api';
import { ApiClientBase } from '../client';

describe('UploadApi', () => {
  let uploadApi: UploadApi;
  let mockClient: ApiClientBase;

  beforeEach(() => {
    global.fetch = vi.fn();
    mockClient = {
      getCsrfToken: vi.fn(() => 'csrf-token'),
      getToken: vi.fn(() => 'auth-token'),
      getBaseUrl: vi.fn(() => 'https://api.test.com'),
    } as any;
    uploadApi = new UploadApi(mockClient);
  });

  describe('uploadFile', () => {
    it('should upload file successfully', async () => {
      const file = new File(['test content'], 'test.txt', { type: 'text/plain' });
      const mockResponse = {
        success: true,
        url: 'https://cdn.test.com/file.txt',
        filename: 'test.txt',
        type: 'text/plain',
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await uploadApi.uploadFile(file);

      expect(global.fetch).toHaveBeenCalledWith(
        'https://api.test.com/media/upload',
        expect.objectContaining({
          method: 'POST',
          headers: {
            'X-CSRF-Token': 'csrf-token',
            Authorization: 'Bearer auth-token',
          },
          credentials: 'include',
        })
      );
      expect(result).toEqual(mockResponse);
    });

    it('should upload file without CSRF token if not available', async () => {
      (mockClient.getCsrfToken as any).mockReturnValue(null);
      const file = new File(['test'], 'test.txt');
      const mockResponse = { success: true, url: 'test', filename: 'test.txt', type: 'text/plain' };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      await uploadApi.uploadFile(file);

      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.not.objectContaining({
            'X-CSRF-Token': expect.anything(),
          }),
        })
      );
    });

    it('should throw error on failed upload', async () => {
      const file = new File(['test'], 'test.txt');

      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        statusText: 'Bad Request',
      });

      await expect(uploadApi.uploadFile(file)).rejects.toThrow('Upload failed: Bad Request');
    });
  });
});

