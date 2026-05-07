import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChatSidebar, ChatSidebarProps } from "./ChatSidebar";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

describe("ChatSidebar", () => {
  const mockConversations = [
    { id: 1, title: "Test Conversation", created_at: new Date().toISOString() },
    { id: 2, title: null, created_at: new Date().toISOString() },
  ];

  const defaultProps: ChatSidebarProps = {
    isOpen: true,
    onClose: vi.fn(),
    onNewChat: vi.fn(),
    onConversationClick: vi.fn(),
    onDeleteConversation: vi.fn(),
    onSearchDocsOpen: vi.fn(),
    conversations: mockConversations,
    currentConversationId: null,
    isLoading: false,
  };

  it("renders conversation titles correctly", () => {
    render(<ChatSidebar {...defaultProps} />);
    expect(screen.getByText("Test Conversation")).toBeInTheDocument();
    expect(screen.getByText("Untitled")).toBeInTheDocument();
  });

  it("has descriptive aria-labels for delete buttons", () => {
    render(<ChatSidebar {...defaultProps} />);

    const deleteButton1 = screen.getByLabelText("Delete conversation: Test Conversation");
    const deleteButton2 = screen.getByLabelText("Delete conversation: Untitled");

    expect(deleteButton1).toBeInTheDocument();
    expect(deleteButton2).toBeInTheDocument();
  });

  it("buttons have type='button'", () => {
    render(<ChatSidebar {...defaultProps} />);

    const buttons = screen.getAllByRole("button");
    buttons.forEach(button => {
      expect(button).toHaveAttribute("type", "button");
    });
  });
});
