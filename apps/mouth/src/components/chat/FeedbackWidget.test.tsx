import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FeedbackWidget } from "./FeedbackWidget";

// Mock framer-motion to avoid animation issues in tests
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

describe("FeedbackWidget", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("renders when turnCount is 8 or more", () => {
    render(<FeedbackWidget sessionId="test-session" turnCount={8} />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("has correct ARIA attributes for the dialog", () => {
    render(<FeedbackWidget sessionId="test-session" turnCount={8} />);
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-labelledby", "feedback-title");
    expect(screen.getByText("How is your experience?")).toHaveAttribute("id", "feedback-title");
  });

  it("associates labels with textareas correctly when a feedback type is selected", async () => {
    const user = userEvent.setup();
    render(<FeedbackWidget sessionId="test-session" turnCount={8} />);

    // Select "I had some issues"
    await user.click(screen.getByText("I had some issues"));

    // Check message textarea label
    const messageTextarea = screen.getByLabelText(/What went wrong\?/i);
    expect(messageTextarea).toHaveAttribute("id", "feedback-message");

    // Check correction textarea label
    const correctionTextarea = screen.getByLabelText(/Help us learn: What was the correct answer\?/i);
    expect(correctionTextarea).toHaveAttribute("id", "feedback-correction");
  });

  it("dismiss button has focus-ring class", () => {
    render(<FeedbackWidget sessionId="test-session" turnCount={8} />);
    const dismissButton = screen.getByLabelText("Dismiss feedback");
    expect(dismissButton).toHaveClass("focus-ring");
  });

  it("feedback type buttons have focus-ring class", () => {
    render(<FeedbackWidget sessionId="test-session" turnCount={8} />);
    const positiveButton = screen.getByText("It's going well").closest("button");
    const negativeButton = screen.getByText("I had some issues").closest("button");
    const issueButton = screen.getByText("I found a bug").closest("button");

    expect(positiveButton).toHaveClass("focus-ring");
    expect(negativeButton).toHaveClass("focus-ring");
    expect(issueButton).toHaveClass("focus-ring");
  });

  it("back and send buttons have focus-ring class", async () => {
    const user = userEvent.setup();
    render(<FeedbackWidget sessionId="test-session" turnCount={8} />);
    await user.click(screen.getByText("It's going well"));

    const backButton = screen.getByText("Back");
    const sendButton = screen.getByText("Send Feedback");

    expect(backButton).toHaveClass("focus-ring");
    expect(sendButton).toHaveClass("focus-ring");
  });
});
