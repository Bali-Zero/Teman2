import { FILE_LIMITS } from '@/constants';

/**
 * Validates image file magic bytes to prevent malicious file uploads
 */
export function validateImageMagicBytes(file: File): Promise<boolean> {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const arrayBuffer = reader.result as ArrayBuffer;
      const uint8Array = new Uint8Array(arrayBuffer);

      // Check magic bytes for common image formats
      const isValidImage =
        // JPEG: FF D8 FF
        (uint8Array[0] === 0xff && uint8Array[1] === 0xd8 && uint8Array[2] === 0xff) ||
        // PNG: 89 50 4E 47
        (uint8Array[0] === 0x89 &&
          uint8Array[1] === 0x50 &&
          uint8Array[2] === 0x4e &&
          uint8Array[3] === 0x47) ||
        // GIF: 47 49 46 38
        (uint8Array[0] === 0x47 &&
          uint8Array[1] === 0x49 &&
          uint8Array[2] === 0x46 &&
          uint8Array[3] === 0x38) ||
        // WebP: RIFF...WEBP (check first 4 bytes are RIFF and bytes 8-11 are WEBP)
        (uint8Array[0] === 0x52 &&
          uint8Array[1] === 0x49 &&
          uint8Array[2] === 0x46 &&
          uint8Array[3] === 0x46 &&
          uint8Array.length > 11 &&
          String.fromCharCode(uint8Array[8], uint8Array[9], uint8Array[10], uint8Array[11]) ===
            'WEBP');

      resolve(isValidImage);
    };
    reader.readAsArrayBuffer(file);
  });
}

/**
 * Validates image dimensions
 */
export function validateImageDimensions(file: File): Promise<boolean> {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const img = document.createElement('img');
      img.onload = () => {
        const isValid =
          img.width <= FILE_LIMITS.MAX_IMAGE_DIMENSION &&
          img.height <= FILE_LIMITS.MAX_IMAGE_DIMENSION;
        resolve(isValid);
      };
      img.onerror = () => resolve(false);
      img.src = reader.result as string;
    };
    reader.readAsDataURL(file);
  });
}

/**
 * Validates avatar file (MIME type, size, magic bytes, dimensions)
 */
export async function validateAvatarFile(file: File): Promise<{
  valid: boolean;
  error?: string;
}> {
  // Validate MIME type
  if (!file.type.startsWith('image/')) {
    return { valid: false, error: 'Please select an image file' };
  }

  // Validate file size
  if (file.size > FILE_LIMITS.MAX_FILE_SIZE) {
    return {
      valid: false,
      error: `Image must be less than ${FILE_LIMITS.MAX_FILE_SIZE_MB}MB`,
    };
  }

  // Validate magic bytes
  const isValidMagicBytes = await validateImageMagicBytes(file);
  if (!isValidMagicBytes) {
    return {
      valid: false,
      error: 'Invalid image file. Please upload a valid JPEG, PNG, GIF, or WebP image.',
    };
  }

  // Validate dimensions
  const isValidDimensions = await validateImageDimensions(file);
  if (!isValidDimensions) {
    return {
      valid: false,
      error: `Image dimensions must be less than ${FILE_LIMITS.MAX_IMAGE_DIMENSION}x${FILE_LIMITS.MAX_IMAGE_DIMENSION}px`,
    };
  }

  return { valid: true };
}

