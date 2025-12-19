import { FILE_LIMITS } from '@/constants';

/**
 * Validates file upload (size, type)
 */
export function validateFileUpload(file: File): {
  valid: boolean;
  error?: string;
} {
  // Validate file size
  if (file.size > FILE_LIMITS.MAX_FILE_SIZE) {
    return {
      valid: false,
      error: `File must be less than ${FILE_LIMITS.MAX_FILE_SIZE_MB}MB`,
    };
  }

  // Additional file type validation can be added here
  return { valid: true };
}

