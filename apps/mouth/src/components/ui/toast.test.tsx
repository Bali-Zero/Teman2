import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, act, waitFor } from "@testing-library/react";
import { ToastProvider, useToast } from "./toast";

// Test component that exposes useToast
function ToastTester() {
  const { toast, success, error, warning, info, dismiss, clear } = useToast();
  return (
    <div>
      <button onClick={() => success("Success!")}>Add Success</button>
      <button onClick={() => error("Error!", "Something failed")}>
        Add Error
      </button>
      <button onClick={() => warning("Warning!")}>Add Warning</button>
      <button onClick={() => info("Info!")}>Add Info</button>
      <button onClick={() => clear()}>Clear All</button>
    </div>
  );
}

function renderWithProvider() {
  return render(
    <ToastProvider>
      <ToastTester />
    </ToastProvider>,
  );
}

describe("ToastProvider and useToast", () => {
  it("renders children within the provider", () => {
    renderWithProvider();
    expect(screen.getByText("Add Success")).toBeInTheDocument();
  });

  it("adds a success toast", () => {
    renderWithProvider();

    act(() => {
      fireEvent.click(screen.getByText("Add Success"));
    });

    expect(screen.getByText("Success!")).toBeInTheDocument();
  });

  it("adds an error toast with description", () => {
    renderWithProvider();

    act(() => {
      fireEvent.click(screen.getByText("Add Error"));
    });

    expect(screen.getByText("Error!")).toBeInTheDocument();
    expect(screen.getByText("Something failed")).toBeInTheDocument();
  });

  it("adds a warning toast", () => {
    renderWithProvider();

    act(() => {
      fireEvent.click(screen.getByText("Add Warning"));
    });

    expect(screen.getByText("Warning!")).toBeInTheDocument();
  });

  it("adds an info toast", () => {
    renderWithProvider();

    act(() => {
      fireEvent.click(screen.getByText("Add Info"));
    });

    expect(screen.getByText("Info!")).toBeInTheDocument();
  });

  it("clears all toasts", async () => {
    renderWithProvider();

    act(() => {
      fireEvent.click(screen.getByText("Add Success"));
      fireEvent.click(screen.getByText("Add Warning"));
    });

    expect(screen.getByText("Success!")).toBeInTheDocument();
    expect(screen.getByText("Warning!")).toBeInTheDocument();

    act(() => {
      fireEvent.click(screen.getByText("Clear All"));
    });

    // AnimatePresence may keep elements during exit animation;
    // wait for them to be removed from the DOM
    await waitFor(() => {
      expect(screen.queryByText("Success!")).not.toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.queryByText("Warning!")).not.toBeInTheDocument();
    });
  });
});

describe("useToast outside provider", () => {
  it("throws when used without ToastProvider", () => {
    // Suppress console.error for this test
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<ToastTester />)).toThrow(
      "useToast must be used within a ToastProvider",
    );
    spy.mockRestore();
  });
});
