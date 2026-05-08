import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AskZantara } from "./AskZantara";

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => <>{children}</>,
}));

describe("AskZantara", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(Date, "now").mockReturnValue(1700000000000);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("answers scripted questions without calling the network", async () => {
    vi.useFakeTimers();
    const fetchSpy = vi.spyOn(global, "fetch");

    render(
      <AskZantara
        scripted={[
          {
            q: "What is a PT PMA?",
            a: "A foreign investment company in Indonesia.",
            sources: [{ title: "PMA guide", url: "/guides/pma" }],
          },
        ]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /what is a pt pma/i }));

    expect(screen.getByText("What is a PT PMA?")).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(500);
    });

    expect(
      screen.getByText("A foreign investment company in Indonesia."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /pma guide/i })).toHaveAttribute(
      "href",
      "/guides/pma",
    );
    expect(screen.getByText("All questions answered! Need more help? Contact us.")).toBeInTheDocument();
  });

  it("sends suggested AI questions to the configured endpoint with context", async () => {
    const fetchMock = vi.mocked(global.fetch);
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        answer: "Use the PMA checklist before OSS submission.",
        sources: [{ title: "OSS", url: "https://oss.go.id" }],
      }),
    } as Response);

    render(
      <AskZantara
        context="company setup"
        apiEndpoint="/api/test/ask"
        suggestedQuestions={["What should I prepare?"]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /what should i prepare/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Use the PMA checklist before OSS submission."),
      ).toBeInTheDocument();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/test/ask",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          question: "What should I prepare?",
          context: "company setup",
        }),
      }),
    );
    expect(screen.getByRole("link", { name: /oss/i })).toHaveAttribute(
      "href",
      "https://oss.go.id",
    );
  });

  it("submits typed questions with Enter and renders a deterministic error response", async () => {
    const fetchMock = vi.mocked(global.fetch);
    fetchMock.mockRejectedValueOnce(new Error("offline"));

    render(<AskZantara placeholder="Ask here" />);

    fireEvent.change(screen.getByLabelText("Ask Zantara a question"), {
      target: { value: "Can I use this KBLI?" },
    });
    fireEvent.keyDown(screen.getByLabelText("Ask Zantara a question"), {
      key: "Enter",
    });

    await waitFor(() => {
      expect(
        screen.getByText("Sorry, I couldn't process your question. Please try again."),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("Can I use this KBLI?")).toBeInTheDocument();
  });

  it("opens and closes the floating panel", () => {
    render(<AskZantara variant="floating" />);

    const toggle = screen.getByRole("button", { name: /ask zantara/i });
    expect(screen.queryByText("AI-powered answers from our knowledge base")).not.toBeInTheDocument();

    fireEvent.click(toggle);
    expect(screen.getByText("AI-powered answers from our knowledge base")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByText("AI-powered answers from our knowledge base")).not.toBeInTheDocument();
  });
});
