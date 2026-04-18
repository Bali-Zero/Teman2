import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { VaultSearchBar } from "./VaultSearchBar";

describe("VaultSearchBar", () => {
  it("renders controlled value from prop", () => {
    render(<VaultSearchBar value="hello" onChange={() => {}} />);
    const input = screen.getByRole("searchbox") as HTMLInputElement;
    expect(input.value).toBe("hello");
  });

  it("debounces onChange by 200ms", () => {
    vi.useFakeTimers();
    const onChange = vi.fn();
    render(<VaultSearchBar value="" onChange={onChange} />);
    const input = screen.getByRole("searchbox");

    // Reset after initial mount effect fires
    act(() => {
      vi.advanceTimersByTime(200);
    });
    onChange.mockClear();

    fireEvent.change(input, { target: { value: "abc" } });

    // Not called immediately
    act(() => {
      vi.advanceTimersByTime(100);
    });
    expect(onChange).not.toHaveBeenCalled();

    // Called after 200ms
    act(() => {
      vi.advanceTimersByTime(150);
    });
    expect(onChange).toHaveBeenCalledWith("abc");
    vi.useRealTimers();
  });

  it("has aria-label", () => {
    render(<VaultSearchBar value="" onChange={() => {}} />);
    expect(screen.getByLabelText("Search vault files")).toBeInTheDocument();
  });
});
