import { ApiClientBase } from '../client';

/**
 * Image generation API methods
 */
export class ImageApi {
  constructor(private client: ApiClientBase) {}

  async generateImage(prompt: string): Promise<{ image_url: string }> {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const response = await (this.client as any).request(
      '/api/v1/image/generate',
      {
        method: 'POST',
        body: JSON.stringify({ prompt }),
      },
      60000
    ) as {
      images: string[];
      success: boolean;
      error?: string;
    }; // 60s timeout for AI generation

    if (!response.success || !response.images || response.images.length === 0) {
      throw new Error(response.error || 'Failed to generate image');
    }

    return { image_url: response.images[0] };
  }
}

