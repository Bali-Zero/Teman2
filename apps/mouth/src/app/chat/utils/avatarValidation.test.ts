import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  validateImageMagicBytes,
  validateImageDimensions,
  validateAvatarFile,
} from './avatarValidation';
import { FILE_LIMITS } from '@/constants';

// Mock FileReader class
class MockFileReader {
  result: ArrayBuffer | string | null = null;
  onloadend: ((this: FileReader, ev: ProgressEvent<FileReader>) => void) | null = null;

  readAsArrayBuffer(_file: File) {
    // eslint-disable-line @typescript-eslint/no-unused-vars
    setTimeout(() => {
      if (this.onloadend) {
        this.onloadend(new ProgressEvent('loadend') as ProgressEvent<FileReader>);
      }
    }, 0);
  }

  readAsDataURL(_file: File) {
    // eslint-disable-line @typescript-eslint/no-unused-vars
    setTimeout(() => {
      if (this.onloadend) {
        this.onloadend(new ProgressEvent('loadend') as ProgressEvent<FileReader>);
      }
    }, 0);
  }
}

describe('avatarValidation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Setup FileReader mock globally
    vi.stubGlobal('FileReader', MockFileReader);
  });

  describe('validateImageMagicBytes', () => {
    it('should validate JPEG magic bytes', async () => {
      const jpegBytes = new Uint8Array([0xff, 0xd8, 0xff, 0x00]);
      const file = new File([jpegBytes], 'test.jpg', { type: 'image/jpeg' });

      // Override FileReader for this test to return a specific mock
      const mockReader = new MockFileReader();
      mockReader.result = jpegBytes.buffer;

      const FileReaderConstructor = function (this: FileReader) {
        Object.assign(this, mockReader);
      } as unknown as typeof FileReader;
      FileReaderConstructor.prototype = MockFileReader.prototype;
      vi.stubGlobal('FileReader', FileReaderConstructor);

      const result = await validateImageMagicBytes(file);
      expect(result).toBe(true);
    });

    it('should validate PNG magic bytes', async () => {
      const pngBytes = new Uint8Array([0x89, 0x50, 0x4e, 0x47]);
      const file = new File([pngBytes], 'test.png', { type: 'image/png' });

      const mockReader = new MockFileReader();
      mockReader.result = pngBytes.buffer;

      const FileReaderConstructor = function (this: FileReader) {
        this.result = mockReader.result;
        this.onloadend = mockReader.onloadend;
        this.readAsArrayBuffer = mockReader.readAsArrayBuffer.bind(this);
        this.readAsDataURL = mockReader.readAsDataURL.bind(this);
      } as unknown as typeof FileReader;
      FileReaderConstructor.prototype = MockFileReader.prototype;
      vi.stubGlobal('FileReader', FileReaderConstructor);

      const result = await validateImageMagicBytes(file);
      expect(result).toBe(true);
    });

    it('should validate GIF magic bytes', async () => {
      const gifBytes = new Uint8Array([0x47, 0x49, 0x46, 0x38]);
      const file = new File([gifBytes], 'test.gif', { type: 'image/gif' });

      const mockReader = new MockFileReader();
      mockReader.result = gifBytes.buffer;

      const FileReaderConstructor = function (this: FileReader) {
        Object.assign(this, mockReader);
      } as unknown as typeof FileReader;
      FileReaderConstructor.prototype = MockFileReader.prototype;
      vi.stubGlobal('FileReader', FileReaderConstructor);

      const result = await validateImageMagicBytes(file);
      expect(result).toBe(true);
    });

    it('should validate WebP magic bytes', async () => {
      const webpBytes = new Uint8Array([
        0x52, 0x49, 0x46, 0x46, 0x00, 0x00, 0x00, 0x00, 0x57, 0x45, 0x42, 0x50,
      ]);
      const file = new File([webpBytes], 'test.webp', { type: 'image/webp' });

      const mockReader = new MockFileReader();
      mockReader.result = webpBytes.buffer;

      const FileReaderConstructor = function (this: FileReader) {
        Object.assign(this, mockReader);
      } as unknown as typeof FileReader;
      FileReaderConstructor.prototype = MockFileReader.prototype;
      vi.stubGlobal('FileReader', FileReaderConstructor);

      const result = await validateImageMagicBytes(file);
      expect(result).toBe(true);
    });

    it('should reject invalid magic bytes', async () => {
      const invalidBytes = new Uint8Array([0x00, 0x00, 0x00, 0x00]);
      const file = new File([invalidBytes], 'test.txt', { type: 'text/plain' });

      const mockReader = new MockFileReader();
      mockReader.result = invalidBytes.buffer;

      const FileReaderConstructor = function (this: FileReader) {
        Object.assign(this, mockReader);
      } as unknown as typeof FileReader;
      FileReaderConstructor.prototype = MockFileReader.prototype;
      vi.stubGlobal('FileReader', FileReaderConstructor);

      const result = await validateImageMagicBytes(file);
      expect(result).toBe(false);
    });
  });

  describe('validateImageDimensions', () => {
    it('should validate dimensions within limit', async () => {
      const file = new File([''], 'test.jpg', { type: 'image/jpeg' });

      const mockReader = new MockFileReader();
      mockReader.result = 'data:image/jpeg;base64,test';

      const FileReaderConstructor = function (this: FileReader) {
        this.result = mockReader.result;
        this.onloadend = mockReader.onloadend;
        this.readAsArrayBuffer = mockReader.readAsArrayBuffer.bind(this);
        this.readAsDataURL = mockReader.readAsDataURL.bind(this);
      } as unknown as typeof FileReader;
      FileReaderConstructor.prototype = MockFileReader.prototype;
      vi.stubGlobal('FileReader', FileReaderConstructor);

      const mockImage = {
        width: FILE_LIMITS.MAX_IMAGE_DIMENSION - 100,
        height: FILE_LIMITS.MAX_IMAGE_DIMENSION - 100,
        onload: null as ((this: HTMLImageElement, ev: Event) => void) | null,
        onerror: null as ((this: HTMLImageElement, ev: Event | string) => void) | null,
        src: '',
      };

      // Mock document.createElement to return our mock image
      const originalCreateElement = document.createElement;
      document.createElement = vi.fn((tagName: string) => {
        if (tagName === 'img') {
          setTimeout(() => {
            if (mockImage.onload) mockImage.onload(new Event('load') as Event);
          }, 0);
          return mockImage as HTMLImageElement;
        }
        return originalCreateElement.call(document, tagName);
      });

      const result = await validateImageDimensions(file);
      expect(result).toBe(true);

      // Restore
      document.createElement = originalCreateElement;
    });

    it('should reject dimensions exceeding limit', async () => {
      const file = new File([''], 'test.jpg', { type: 'image/jpeg' });

      const mockReader = new MockFileReader();
      mockReader.result = 'data:image/jpeg;base64,test';

      const FileReaderConstructor = function (this: FileReader) {
        this.result = mockReader.result;
        this.onloadend = mockReader.onloadend;
        this.readAsArrayBuffer = mockReader.readAsArrayBuffer.bind(this);
        this.readAsDataURL = mockReader.readAsDataURL.bind(this);
      } as unknown as typeof FileReader;
      FileReaderConstructor.prototype = MockFileReader.prototype;
      vi.stubGlobal('FileReader', FileReaderConstructor);

      const mockImage = {
        width: FILE_LIMITS.MAX_IMAGE_DIMENSION + 100,
        height: FILE_LIMITS.MAX_IMAGE_DIMENSION + 100,
        onload: null as ((this: HTMLImageElement, ev: Event) => void) | null,
        onerror: null as ((this: HTMLImageElement, ev: Event | string) => void) | null,
        src: '',
      };

      // Mock document.createElement to return our mock image
      const originalCreateElement = document.createElement;
      document.createElement = vi.fn((tagName: string) => {
        if (tagName === 'img') {
          setTimeout(() => {
            if (mockImage.onload) mockImage.onload(new Event('load') as Event);
          }, 0);
          return mockImage as HTMLImageElement;
        }
        return originalCreateElement.call(document, tagName);
      });

      const result = await validateImageDimensions(file);
      expect(result).toBe(false);

      // Restore
      document.createElement = originalCreateElement;
    });
  });

  describe('validateAvatarFile', () => {
    it('should validate valid image file', async () => {
      const jpegBytes = new Uint8Array([0xff, 0xd8, 0xff, 0x00]);
      const file = new File([jpegBytes], 'test.jpg', { type: 'image/jpeg' });
      Object.defineProperty(file, 'size', { value: FILE_LIMITS.MAX_FILE_SIZE - 1000 });

      const mockReader = new MockFileReader();
      mockReader.result = jpegBytes.buffer;

      const FileReaderConstructor = function (this: FileReader) {
        this.result = mockReader.result;
        this.onloadend = mockReader.onloadend;
        this.readAsArrayBuffer = mockReader.readAsArrayBuffer.bind(this);
        this.readAsDataURL = mockReader.readAsDataURL.bind(this);
      } as unknown as typeof FileReader;
      FileReaderConstructor.prototype = MockFileReader.prototype;
      vi.stubGlobal('FileReader', FileReaderConstructor);

      const mockImage = {
        width: FILE_LIMITS.MAX_IMAGE_DIMENSION - 100,
        height: FILE_LIMITS.MAX_IMAGE_DIMENSION - 100,
        onload: null as ((this: HTMLImageElement, ev: Event) => void) | null,
        onerror: null as ((this: HTMLImageElement, ev: Event | string) => void) | null,
        src: '',
      };

      // Mock document.createElement to return our mock image
      const originalCreateElement = document.createElement;
      document.createElement = vi.fn((tagName: string) => {
        if (tagName === 'img') {
          setTimeout(() => {
            if (mockImage.onload) mockImage.onload(new Event('load') as Event);
          }, 0);
          return mockImage as HTMLImageElement;
        }
        return originalCreateElement.call(document, tagName);
      });

      const result = await validateAvatarFile(file);
      expect(result.valid).toBe(true);

      // Restore
      document.createElement = originalCreateElement;
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
