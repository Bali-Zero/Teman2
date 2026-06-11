import { describe, it, expect, vi, afterEach } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { SearchBox } from "./SearchBox";

describe("SearchBox", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders input with placeholder and aria-label", () => {
    const { getByLabelText } = render(
      <SearchBox
        value=""
        onValueChange={() => undefined}
        placeholder="Search clients… (press / to focus)"
        ariaLabel="Search clients"
      />,
    );
    const input = getByLabelText("Search clients") as HTMLInputElement;
    expect(input.placeholder).toBe("Search clients… (press / to focus)");
  });

  it("focuses the input when '/' is pressed outside an editable element", () => {
    const { getByLabelText } = render(
      <SearchBox value="" onValueChange={() => undefined} ariaLabel="Search" />,
    );
    const input = getByLabelText("Search") as HTMLInputElement;
    expect(document.activeElement).not.toBe(input);
    fireEvent.keyDown(window, { key: "/", target: document.body });
    expect(document.activeElement).toBe(input);
  });

  it("clears and blurs on Escape while focused", () => {
    const onValueChange = vi.fn();
    const { getByLabelText } = render(
      <SearchBox
        value="abc"
        onValueChange={onValueChange}
        ariaLabel="Search"
      />,
    );
    const input = getByLabelText("Search") as HTMLInputElement;
    input.focus();
    fireEvent.keyDown(input, { key: "Escape" });
    expect(onValueChange).toHaveBeenCalledWith("");
    expect(document.activeElement).not.toBe(input);
  });

  it("fires onDebouncedChange only after debounceMs", () => {
    vi.useFakeTimers();
    const onDebouncedChange = vi.fn();
    const { rerender } = render(
      <SearchBox
        value=""
        onValueChange={() => undefined}
        onDebouncedChange={onDebouncedChange}
        debounceMs={300}
        ariaLabel="Search"
      />,
    );
    onDebouncedChange.mockClear();
    rerender(
      <SearchBox
        value="kitas"
        onValueChange={() => undefined}
        onDebouncedChange={onDebouncedChange}
        debounceMs={300}
        ariaLabel="Search"
      />,
    );
    vi.advanceTimersByTime(299);
    expect(onDebouncedChange).not.toHaveBeenCalledWith("kitas");
    vi.advanceTimersByTime(1);
    expect(onDebouncedChange).toHaveBeenCalledWith("kitas");
  });

  it("shows the clear button only when clearable and there is a value", () => {
    const onValueChange = vi.fn();
    const { queryByLabelText, rerender, getByLabelText } = render(
      <SearchBox value="" onValueChange={onValueChange} clearable />,
    );
    expect(queryByLabelText("Clear search")).toBeNull();
    rerender(<SearchBox value="x" onValueChange={onValueChange} clearable />);
    fireEvent.click(getByLabelText("Clear search"));
    expect(onValueChange).toHaveBeenCalledWith("");
  });
});
