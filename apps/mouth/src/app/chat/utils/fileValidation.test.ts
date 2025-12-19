import { describe, it, expect } from 'vitest';
import { validateFileUpload } from './fileValidation';
import { FILE_LIMITS } from '@/constants';

describe('fileValidation', () => {
  describe('validateFileUpload', () => {
    it('should validate file within size limit', () => {
      const file = new File(['test content'], 'test.txt', { type: 'text/plain' });
      Object.defineProperty(file, 'size', { value: FILE_LIMITS.MAX_FILE_SIZE - 1000 });

      const result = validateFileUpload(file);
      expect(result.valid).toBe(true);
      expect(result.error).toBeUndefined();
    });

    it('should reject file exceeding size limit', () => {
      const file = new File(['test content'], 'test.txt', { type: 'text/plain' });
      Object.defineProperty(file, 'size', { value: FILE_LIMITS.MAX_FILE_SIZE + 1000 });

      const result = validateFileUpload(file);
      expect(result.valid).toBe(false);
      expect(result.error).toContain('less than');
    });

    it('should validate empty file', () => {
      const file = new File([], 'empty.txt', { type: 'text/plain' });
      Object.defineProperty(file, 'size', { value: 0 });

      const result = validateFileUpload(file);
      expect(result.valid).toBe(true);
    });
  });
});

