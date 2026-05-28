import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { cropToSquare, resizeImage } from "./imageResize";

type ImageSize = {
  width: number;
  height: number;
};

type MockCanvasContext = Pick<
  CanvasRenderingContext2D,
  "drawImage" | "imageSmoothingEnabled" | "imageSmoothingQuality"
>;

class MockFileReader {
  onload: ((event: ProgressEvent<FileReader>) => void) | null = null;
  onerror: (() => void) | null = null;

  readAsDataURL(): void {
    if (mockState.readerFails) {
      this.onerror?.();
      return;
    }

    this.onload?.({
      target: { result: "data:image/mock;base64,original" },
    } as ProgressEvent<FileReader>);
  }
}

const originalFileReader = globalThis.FileReader;
const originalImage = globalThis.Image;
const originalCreateElement = document.createElement.bind(document);

const mockState: {
  canvas: HTMLCanvasElement | null;
  context: MockCanvasContext | null;
  createElementSpy: ReturnType<typeof vi.spyOn> | null;
  imageFails: boolean;
  imageSize: ImageSize;
  readerFails: boolean;
  toDataURL: ReturnType<typeof vi.fn>;
} = {
  canvas: null,
  context: null,
  createElementSpy: null,
  imageFails: false,
  imageSize: { width: 800, height: 400 },
  readerFails: false,
  toDataURL: vi.fn(),
};

function installImageMock(): void {
  class MockImage {
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;
    width = mockState.imageSize.width;
    height = mockState.imageSize.height;

    set src(_value: string) {
      queueMicrotask(() => {
        if (mockState.imageFails) {
          this.onerror?.();
          return;
        }

        this.onload?.();
      });
    }
  }

  globalThis.Image = MockImage as unknown as typeof Image;
}

function installCanvasMock(hasContext = true): void {
  mockState.context = {
    drawImage: vi.fn(),
    imageSmoothingEnabled: false,
    imageSmoothingQuality: "low",
  } as MockCanvasContext;
  mockState.toDataURL = vi.fn(() => "data:image/resized;base64,output");
  mockState.canvas = {
    width: 0,
    height: 0,
    getContext: vi.fn(() => (hasContext ? mockState.context : null)),
    toDataURL: mockState.toDataURL,
  } as unknown as HTMLCanvasElement;
  mockState.createElementSpy = vi
    .spyOn(document, "createElement")
    .mockImplementation((tagName: string) => {
      if (tagName === "canvas") {
        return mockState.canvas as HTMLCanvasElement;
      }

      return originalCreateElement(tagName);
    });
}

function makeImageFile(type = "image/jpeg"): File {
  return new File(["image-bytes"], "profile-image.jpg", { type });
}

describe("imageResize utilities", () => {
  beforeEach(() => {
    mockState.imageFails = false;
    mockState.readerFails = false;
    mockState.imageSize = { width: 800, height: 400 };

    globalThis.FileReader =
      MockFileReader as unknown as typeof globalThis.FileReader;
    installImageMock();
    installCanvasMock();
  });

  afterEach(() => {
    globalThis.FileReader = originalFileReader;
    globalThis.Image = originalImage;
    mockState.createElementSpy?.mockRestore();
    vi.restoreAllMocks();
  });

  it("resizes landscape JPEGs within max bounds while preserving aspect ratio", async () => {
    await expect(resizeImage(makeImageFile(), 200, 200, 0.7)).resolves.toBe(
      "data:image/resized;base64,output",
    );

    expect(mockState.canvas?.width).toBe(200);
    expect(mockState.canvas?.height).toBe(100);
    expect(mockState.context?.drawImage).toHaveBeenCalledWith(
      expect.any(Object),
      0,
      0,
      200,
      100,
    );
    expect(mockState.toDataURL).toHaveBeenCalledWith("image/jpeg", 0.7);
  });

  it("resizes portrait PNGs using the PNG output type", async () => {
    mockState.imageSize = { width: 200, height: 800 };
    installImageMock();

    await resizeImage(makeImageFile("image/png"), 400, 100, 0.6);

    expect(mockState.canvas?.width).toBe(25);
    expect(mockState.canvas?.height).toBe(100);
    expect(mockState.toDataURL).toHaveBeenCalledWith("image/png", 0.6);
  });

  it("keeps images below the resize limits at their original dimensions", async () => {
    mockState.imageSize = { width: 120, height: 80 };
    installImageMock();

    await resizeImage(makeImageFile(), 400, 400);

    expect(mockState.canvas?.width).toBe(120);
    expect(mockState.canvas?.height).toBe(80);

    mockState.imageSize = { width: 80, height: 120 };
    installImageMock();

    await resizeImage(makeImageFile(), 400, 400);

    expect(mockState.canvas?.width).toBe(80);
    expect(mockState.canvas?.height).toBe(120);
  });

  it("center-crops rectangular images to the requested square size", async () => {
    await expect(
      cropToSquare(makeImageFile("image/png"), 128, 0.8),
    ).resolves.toBe("data:image/resized;base64,output");

    expect(mockState.canvas?.width).toBe(128);
    expect(mockState.canvas?.height).toBe(128);
    expect(mockState.context?.drawImage).toHaveBeenCalledWith(
      expect.any(Object),
      200,
      0,
      400,
      400,
      0,
      0,
      128,
      128,
    );
    expect(mockState.toDataURL).toHaveBeenCalledWith("image/png", 0.8);

    await cropToSquare(makeImageFile(), 64, 0.5);

    expect(mockState.toDataURL).toHaveBeenLastCalledWith("image/jpeg", 0.5);
  });

  it("rejects when the canvas context cannot be created", async () => {
    mockState.createElementSpy?.mockRestore();
    installCanvasMock(false);

    await expect(resizeImage(makeImageFile())).rejects.toThrow(
      "Failed to get canvas context",
    );

    mockState.createElementSpy?.mockRestore();
    installCanvasMock(false);
    await expect(cropToSquare(makeImageFile())).rejects.toThrow(
      "Failed to get canvas context",
    );
  });

  it("rejects read and image load failures", async () => {
    mockState.readerFails = true;
    await expect(resizeImage(makeImageFile())).rejects.toThrow(
      "Failed to read file",
    );

    mockState.readerFails = false;
    mockState.imageFails = true;
    await expect(resizeImage(makeImageFile())).rejects.toThrow(
      "Failed to load image",
    );

    mockState.imageFails = false;
    mockState.readerFails = true;
    await expect(cropToSquare(makeImageFile())).rejects.toThrow(
      "Failed to read file",
    );

    mockState.readerFails = false;
    mockState.imageFails = true;
    await expect(cropToSquare(makeImageFile())).rejects.toThrow(
      "Failed to load image",
    );
  });
});
