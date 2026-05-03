/**
 * Custom hook for managing chat input state and attachments
 *
 * Handles:
 * - Text input state
 * - Image attachments (upload, preview, remove)
 * - Image generation prompt
 * - File validation
 *
 * @returns Input state and handlers
 */

import { useState, useCallback, useRef } from "react";
import { logger } from "@/lib/logger";
import { chatMetrics } from "@/lib/metrics";

export interface AttachedImage {
  id: string;
  base64: string;
  name: string;
  size: number;
}

export interface UseChatInputReturn {
  // Input state
  input: string;
  setInput: (value: string) => void;

  // Image attachments
  attachedImages: AttachedImage[];
  setAttachedImages: React.Dispatch<React.SetStateAction<AttachedImage[]>>;

  // Image generation
  imageGenPrompt: string;
  setImageGenPrompt: (value: string) => void;

  // Refs
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  imageInputRef: React.RefObject<HTMLInputElement | null>;

  // Handlers
  handleImageAttach: (e: React.ChangeEvent<HTMLInputElement>) => void;
  removeAttachedImage: (imageId: string) => void;
  handleImageButtonClick: () => void;
  handleScreenshotClick: () => void;
  clearInput: () => void;
  clearAttachments: () => void;

  // Toast callback
  showToast: (message: string, type: "success" | "error") => void;
  setShowToast: (
    callback: (message: string, type: "success" | "error") => void,
  ) => void;
}

const MAX_IMAGE_SIZE = 10 * 1024 * 1024; // 10MB
const MAX_IMAGES = 5;

export function useChatInput(): UseChatInputReturn {
  const [input, setInput] = useState("");
  const [attachedImages, setAttachedImages] = useState<AttachedImage[]>([]);
  const [imageGenPrompt, setImageGenPrompt] = useState("");
  const [toastCallback, setToastCallback] = useState<
    ((message: string, type: "success" | "error") => void) | null
  >(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const toastCallbackRef = useRef<
    ((message: string, type: "success" | "error") => void) | null
  >(null);

  // Keep ref in sync with state (synchronously for immediate access)
  toastCallbackRef.current = toastCallback;

  const showToast = useCallback(
    (message: string, type: "success" | "error") => {
      if (toastCallbackRef.current) {
        toastCallbackRef.current(message, type);
      }
    },
    [],
  );

  const setShowToastWrapper = useCallback(
    (callback: (message: string, type: "success" | "error") => void) => {
      // Wrap in function to avoid React treating callback as updater function
      setToastCallback(() => callback);
    },
    [],
  );

  const handleImageAttach = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (!files) return;

      logger.debug("Image attachment started", {
        component: "useChatInput",
        action: "handleImageAttach",
        metadata: {
          fileCount: files.length,
          currentImageCount: attachedImages.length,
        },
      });

      let attachedCount = 0;

      Array.from(files).forEach((file) => {
        if (!file.type.startsWith("image/")) {
          logger.warn("Invalid file type for image attachment", {
            component: "useChatInput",
            action: "handleImageAttach",
            metadata: { fileType: file.type, fileName: file.name },
          });
          if (toastCallbackRef.current) {
            toastCallbackRef.current("Please select an image file", "error");
          }
          return;
        }

        if (file.size > MAX_IMAGE_SIZE) {
          logger.warn("Image file too large", {
            component: "useChatInput",
            action: "handleImageAttach",
            metadata: { fileSize: file.size, fileName: file.name },
          });
          if (toastCallbackRef.current) {
            toastCallbackRef.current("Image must be less than 10MB", "error");
          }
          return;
        }

        if (attachedImages.length + attachedCount >= MAX_IMAGES) {
          logger.warn("Maximum images limit reached", {
            component: "useChatInput",
            action: "handleImageAttach",
            metadata: {
              currentCount: attachedImages.length,
              attemptCount: attachedCount,
            },
          });
          if (toastCallbackRef.current) {
            toastCallbackRef.current("Maximum 5 images allowed", "error");
          }
          return;
        }

        const reader = new FileReader();
        reader.onloadend = () => {
          const base64String = reader.result as string;
          setAttachedImages((prev) => {
            const newImages = [
              ...prev,
              {
                id: `img_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
                base64: base64String,
                name: file.name,
                size: file.size,
              },
            ];
            logger.info("Image attached successfully", {
              component: "useChatInput",
              action: "handleImageAttach",
              metadata: {
                imageCount: newImages.length,
                fileName: file.name,
                fileSize: file.size,
              },
            });

            // Track metrics
            const totalSize = newImages.reduce((sum, img) => sum + img.size, 0);
            chatMetrics.imageAttached(newImages.length, totalSize);

            return newImages;
          });
        };
        reader.onerror = () => {
          logger.error(
            "Failed to read image file",
            {
              component: "useChatInput",
              action: "handleImageAttach",
              metadata: { fileName: file.name },
            },
            new Error("FileReader error"),
          );
          if (toastCallbackRef.current) {
            toastCallbackRef.current("Failed to read image file", "error");
          }
        };
        reader.readAsDataURL(file);
        attachedCount++;
      });

      // Reset input to allow selecting same file again
      e.target.value = "";
    },
    [attachedImages.length],
  );

  const removeAttachedImage = useCallback(
    (imageId: string) => {
      logger.debug("Removing attached image", {
        component: "useChatInput",
        action: "removeAttachedImage",
        metadata: { imageId, currentCount: attachedImages.length },
      });
      setAttachedImages((prev) => prev.filter((img) => img.id !== imageId));
    },
    [attachedImages.length],
  );

  const handleImageButtonClick = useCallback(() => {
    imageInputRef.current?.click();
  }, []);

  const handleScreenshotClick = useCallback(() => {
    imageInputRef.current?.click();
  }, []);

  const clearInput = useCallback(() => {
    setInput("");
  }, []);

  const clearAttachments = useCallback(() => {
    setAttachedImages([]);
  }, []);

  return {
    input,
    setInput,
    attachedImages,
    setAttachedImages,
    imageGenPrompt,
    setImageGenPrompt,
    fileInputRef,
    imageInputRef,
    handleImageAttach,
    removeAttachedImage,
    handleImageButtonClick,
    handleScreenshotClick,
    clearInput,
    clearAttachments,
    showToast,
    setShowToast: setShowToastWrapper,
  };
}
