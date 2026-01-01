import type { IApiClient } from '../types/api-client.types';

/**
 * Image generation API response
 */
interface ImageGenerationResponse {
  images: string[];
  success: boolean;
  error?: string;
}

/**
 * Image generation API methods
 */
export class ImageApi {
  constructor(private client: IApiClient) {}

  async generateImage(prompt: string): Promise<{ image_url: string }> {
    const response = await this.client.request<ImageGenerationResponse>(
      '/api/v1/image/generate',
      {
        method: 'POST',
        body: JSON.stringify({ prompt }),
      },
      60000 // 60s timeout for AI generation
    );

    if (!response.success || !response.images || response.images.length === 0) {
      throw new Error(response.error || 'Failed to generate image');
    }

    return { image_url: response.images[0] };
  }
}

