import React, { useRef } from "react";
import { describe, it, expect, vi } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { useClickOutside, useClickOutsideMultiple } from "./useClickOutside";

function TestComponent({
  handler,
  enabled = true,
}: {
  handler: (e: MouseEvent) => void;
  enabled?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useClickOutside(ref, handler, enabled);
  return (
    <div>
      <div ref={ref} data-testid="inside">
        Inside
      </div>
      <div data-testid="outside">Outside</div>
    </div>
  );
}

function TestMultiComponent({
  handler,
  enabled = true,
}: {
  handler: (e: MouseEvent) => void;
  enabled?: boolean;
}) {
  const ref1 = useRef<HTMLDivElement>(null);
  const ref2 = useRef<HTMLDivElement>(null);
  useClickOutsideMultiple([ref1, ref2], handler, enabled);
  return (
    <div>
      <div ref={ref1} data-testid="box1">
        Box 1
      </div>
      <div ref={ref2} data-testid="box2">
        Box 2
      </div>
      <div data-testid="outside">Outside</div>
    </div>
  );
}

describe("useClickOutside", () => {
  it("calls handler when clicking outside the referenced element", () => {
    const handler = vi.fn();
    const { getByTestId } = render(<TestComponent handler={handler} />);

    fireEvent.mouseDown(getByTestId("outside"));
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("does not call handler when clicking inside the referenced element", () => {
    const handler = vi.fn();
    const { getByTestId } = render(<TestComponent handler={handler} />);

    fireEvent.mouseDown(getByTestId("inside"));
    expect(handler).not.toHaveBeenCalled();
  });

  it("does not call handler when disabled", () => {
    const handler = vi.fn();
    const { getByTestId } = render(
      <TestComponent handler={handler} enabled={false} />,
    );

    fireEvent.mouseDown(getByTestId("outside"));
    expect(handler).not.toHaveBeenCalled();
  });

  it("cleans up event listener on unmount", () => {
    const handler = vi.fn();
    const removeEventListenerSpy = vi.spyOn(document, "removeEventListener");
    const { unmount } = render(<TestComponent handler={handler} />);

    unmount();

    expect(removeEventListenerSpy).toHaveBeenCalledWith(
      "mousedown",
      expect.any(Function),
    );
    removeEventListenerSpy.mockRestore();
  });
});

describe("useClickOutsideMultiple", () => {
  it("calls handler when clicking outside all referenced elements", () => {
    const handler = vi.fn();
    const { getByTestId } = render(<TestMultiComponent handler={handler} />);

    fireEvent.mouseDown(getByTestId("outside"));
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("does not call handler when clicking inside any referenced element", () => {
    const handler = vi.fn();
    const { getByTestId } = render(<TestMultiComponent handler={handler} />);

    fireEvent.mouseDown(getByTestId("box1"));
    expect(handler).not.toHaveBeenCalled();

    fireEvent.mouseDown(getByTestId("box2"));
    expect(handler).not.toHaveBeenCalled();
  });

  it("does not call handler when disabled", () => {
    const handler = vi.fn();
    const { getByTestId } = render(
      <TestMultiComponent handler={handler} enabled={false} />,
    );

    fireEvent.mouseDown(getByTestId("outside"));
    expect(handler).not.toHaveBeenCalled();
  });
});
