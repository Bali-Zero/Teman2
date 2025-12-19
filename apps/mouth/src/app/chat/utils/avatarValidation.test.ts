import { describe, it, expect, vi, beforeEach } from 'vitest';
import { validateImageMagicBytes, validateImageDimensions, validateAvatarFile } from './avatarValidation';
import { FILE_LIMITS } from '@/constants';

// Mock FileReader
class MockFileReader {
  result: ArrayBuffer | string | null = null;
  onloadend: ((this: FileReader, ev: ProgressEvent<FileReader>) => void) | null = null;

  readAsArrayBuffer(file: File) {
    setTimeout(() => {
      if (this.onloadend) {
        this.onloadend(new ProgressEvent('loadend') as any);
      }
    }, 0);
  }

  readAsDataURL(file: File) {
    setTimeout(() => {
      if (this.onloadend) {
        this.onloadend(new ProgressEvent('loadend') as any);
      }
    }, 0);
  }
}

global.FileReader = MockFileReader as any;

describe('avatarValidation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('validateImageMagicBytes', () => {
    it('should validate JPEG magic bytes', async () => {
      const jpegBytes = new Uint8Array([0xff, 0xd8, 0xff, 0x00]);
      const file = new File([jpegBytes], 'test.jpg', { type: 'image/jpeg' });

      const reader = new MockFileReader();
      reader.result = jpegBytes.buffer;
      global.FileReader = vi.fn(() => reader) as any;

      const result = await validateImageMagicBytes(file);
      expect(result).toBe(true);
    });

    it('should validate PNG magic bytes', async () => {
      const pngBytes = new Uint8Array([0x89, 0x50, 0x4e, 0x47]);
      const file = new File([pngBytes], 'test.png', { type: 'image/png' });

      const reader = new MockFileReader();
      reader.result = pngBytes.buffer;
      global.FileReader = vi.fn(() => reader) as any;

      const result = await validateImageMagicBytes(file);
      expect(result).toBe(true);
    });

    it('should validate GIF magic bytes', async () => {
      const gifBytes = new Uint8Array([0x47, 0x49, 0x46, 0x38]);
      const file = new File([gifBytes], 'test.gif', { type: 'image/gif' });

      const reader = new MockFileReader();
      reader.result = gifBytes.buffer;
      global.FileReader = vi.fn(() => reader) as any;

      const result = await validateImageMagicBytes(file);
      expect(result).toBe(true);
    });

    it('should validate WebP magic bytes', async () => {
      const webpBytes = new Uint8Array([
        0x52, 0x49, 0x46, 0x46, 0x00, 0x00, 0x00, 0x00, 0x57, 0x45, 0x42, 0x50,
      ]);
      const file = new File([webpBytes], 'test.webp', { type: 'image/webp' });

      const reader = new MockFileReader();
      reader.result = webpBytes.buffer;
      global.FileReader = vi.fn(() => reader) as any;

      const result = await validateImageMagicBytes(file);
      expect(result).toBe(true);
    });

    it('should reject invalid magic bytes', async () => {
      const invalidBytes = new Uint8Array([0x00, 0x00, 0x00, 0x00]);
      const file = new File([invalidBytes], 'test.txt', { type: 'text/plain' });

      const reader = new MockFileReader();
      reader.result = invalidBytes.buffer;
      global.FileReader = vi.fn(() => reader) as any;

      const result = await validateImageMagicBytes(file);
      expect(result).toBe(false);
    });
  });

  describe('validateImageDimensions', () => {
    it('should validate dimensions within limit', async () => {
      const file = new File([''], 'test.jpg', { type: 'image/jpeg' });

      const reader = new MockFileReader();
      reader.result = 'data:image/jpeg;base64,test';
      global.FileReader = vi.fn(() => reader) as any;

      // Mock Image
      const mockImage = {
        width: FILE_LIMITS.MAX_IMAGE_DIMENSION - 100,
        height: FILE_LIMITS.MAX_IMAGE_DIMENSION - 100,
        onload: null as any,
        onerror: null as any,
        src: '',
      };

      global.Image = vi.fn(() => mockImage) as any;

      setTimeout(() => {
        if (mockImage.onload) mockImage.onload({} as any);
      }, 0);

      const result = await validateImageDimensions(file);
      expect(result).toBe(true);
    });

    it('should reject dimensions exceeding limit', async () => {
      const file = new File([''], 'test.jpg', { type: 'image/jpeg' });

      const reader = new MockFileReader();
      reader.result = 'data:image/jpeg;base64,test';
      global.FileReader = vi.fn(() => reader) as any;

      const mockImage = {
        width: FILE_LIMITS.MAX_IMAGE_DIMENSION + 100,
        height: FILE_LIMITS.MAX_IMAGE_DIMENSION + 100,
        onload: null as any,
        onerror: null as any,
        src: '',
      };

      global.Image = vi.fn(() => mockImage) as any;

      setTimeout(() => {
        if (mockImage.onload) mockImage.onload({} as any);
      }, 0);

      const result = await validateImageDimensions(file);
      expect(result).toBe(false);
    });
  });

  describe('validateAvatarFile', () => {
    it('should validate valid image file', async () => {
      const jpegBytes = new Uint8Array([0xff, 0xd8, 0xff, 0x00]);
      const file = new File([jpegBytes], 'test.jpg', { type: 'image/jpeg' });
      Object.defineProperty(file, 'size', { value: FILE_LIMITS.MAX_FILE_SIZE - 1000 });

      const result = await validateAvatarFile(file);
      expect(result.valid).toBe(true);
    });

    it('should reject non-image MIME type', async () => {
      const file = new File([''], 'test.txt', { type: 'text/plain' });

      const result = await validateAvatarFile(file);
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Please select an image file');
    });

    it('should reject file exceeding size limit', async () => {
      const jpegBytes = new Uint8Array([0xff, 0xd8, 0xff, 0x00]);
      const file = new File([jpegBytes], 'test.jpg', { type: 'image/jpeg' });
      Object.defineProperty(file, 'size', { value: FILE_LIMITS.MAX_FILE_SIZE + 1000 });

      const result = await validateAvatarFile(file);
      expect(result.valid).toBe(false);
      expect(result.error).toContain('less than');
    });
  });
});

