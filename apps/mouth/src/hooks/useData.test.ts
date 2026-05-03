import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

// Mock SWR
const mockMutate = vi.fn();
vi.mock("swr", () => ({
  default: vi.fn(),
}));

import SWR from "swr";
import { useData } from "./useData";

const mockSWR = SWR as unknown as ReturnType<typeof vi.fn>;

describe("useData", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns loading state initially", () => {
    mockSWR.mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: true,
      mutate: mockMutate,
    });

    const { result } = renderHook(() => useData("/api/test"));

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
    expect(result.current.isError).toBeUndefined();
  });

  it("returns data when loaded", () => {
    mockSWR.mockReturnValue({
      data: { id: 1, name: "Test" },
      error: undefined,
      isLoading: false,
      mutate: mockMutate,
    });

    const { result } = renderHook(() =>
      useData<{ id: number; name: string }>("/api/test"),
    );

    expect(result.current.isLoading).toBe(false);
    expect(result.current.data).toEqual({ id: 1, name: "Test" });
    expect(result.current.isError).toBeUndefined();
  });

  it("returns error on failure", () => {
    const error = new Error("fetch failed");
    mockSWR.mockReturnValue({
      data: undefined,
      error,
      isLoading: false,
      mutate: mockMutate,
    });

    const { result } = renderHook(() => useData("/api/broken"));

    expect(result.current.isError).toBe(error);
    expect(result.current.data).toBeUndefined();
  });

  it("exposes mutate function", () => {
    mockSWR.mockReturnValue({
      data: { value: 42 },
      error: undefined,
      isLoading: false,
      mutate: mockMutate,
    });

    const { result } = renderHook(() => useData("/api/test"));

    expect(result.current.mutate).toBe(mockMutate);
  });

  it("passes null URL to SWR (disabling the request)", () => {
    mockSWR.mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: false,
      mutate: mockMutate,
    });

    renderHook(() => useData(null));

    expect(mockSWR).toHaveBeenCalledWith(null, expect.any(Function), expect.any(Object));
  });

  it("passes SWR config with revalidateOnFocus=false", () => {
    mockSWR.mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: false,
      mutate: mockMutate,
    });

    renderHook(() => useData("/api/test"));

    const config = mockSWR.mock.calls[0][2];
    expect(config.revalidateOnFocus).toBe(false);
    expect(config.keepPreviousData).toBe(true);
  });
});
