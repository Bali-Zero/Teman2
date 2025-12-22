import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ImageApi } from './image.api';
import { ApiClientBase } from '../client';

describe('ImageApi', () => {
  let imageApi: ImageApi;
  let mockClient: ApiClientBase;
  let mockRequest: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mockRequest = vi.fn();
    mockClient = {
      request: mockRequest,
    } as any;
    imageApi = new ImageApi(mockClient);
  });

  describe('generateImage', () => {
    it('should generate image successfully', async () => {
      const mockResponse = {
        success: true,
        images: ['https://cdn.test.com/image.png'],
      };

      mockRequest.mockResolvedValueOnce(mockResponse);

      const result = await imageApi.generateImage('A beautiful sunset');

      expect(mockRequest).toHaveBeenCalledWith(
        '/api/v1/image/generate',
        {
          method: 'POST',
          body: JSON.stringify({ prompt: 'A beautiful sunset' }),
        },
        60000
      );
      expect(result).toEqual({ image_url: 'https://cdn.test.com/image.png' });
    });

    it('should throw error when generation fails', async () => {
      const mockResponse = {
        success: false,
        images: [],
        error: 'Generation failed',
      };

      mockRequest.mockResolvedValueOnce(mockResponse);

      await expect(imageApi.generateImage('test')).rejects.toThrow('Generation failed');
    });

    it('should throw error when no images returned', async () => {
      const mockResponse = {
        success: true,
        images: [],
      };

      mockRequest.mockResolvedValueOnce(mockResponse);

      await expect(imageApi.generateImage('test')).rejects.toThrow('Failed to generate image');
    });

    it('should use 60s timeout for AI generation', async () => {
      const mockResponse = {
        success: true,
        images: ['https://cdn.test.com/image.png'],
      };

      mockRequest.mockResolvedValueOnce(mockResponse);

      await imageApi.generateImage('test');

      expect(mockRequest).toHaveBeenCalledWith(
        expect.any(String),
        expect.any(Object),
        60000
      );
    });
  });
});
