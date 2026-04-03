import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { EmailList } from "../EmailList";
import type { EmailSummary } from "@/lib/email.types";

// Mock lucide-react icons
vi.mock("lucide-react", () => {
  const createIcon = (name: string) => {
    const Icon = (props: Record<string, unknown>) => (
      <svg data-testid={`icon-${name}`} {...props} />
    );
    Icon.displayName = name;
    return Icon;
  };
  return {
    Star: createIcon("Star"),
    Paperclip: createIcon("Paperclip"),
    Mail: createIcon("Mail"),
    MailOpen: createIcon("MailOpen"),
    Trash2: createIcon("Trash2"),
    Check: createIcon("Check"),
    Search: createIcon("Search"),
    ChevronLeft: createIcon("ChevronLeft"),
    ChevronRight: createIcon("ChevronRight"),
  };
});

// Mock cn utility
vi.mock("@/lib/utils", () => ({
  cn: (...classes: (string | boolean | undefined)[]) =>
    classes.filter(Boolean).join(" "),
}));

const mockEmails: EmailSummary[] = [
  {
    message_id: "msg-1",
    subject: "Important Update",
    from: { address: "sender@example.com", name: "John Doe" },
    to: [{ address: "me@balizero.com" }],
    date: new Date().toISOString(),
    snippet: "Here is an important update about...",
    is_read: false,
    is_flagged: true,
    has_attachments: true,
    folder_id: "inbox",
  },
  {
    message_id: "msg-2",
    subject: "Meeting Notes",
    from: { address: "colleague@example.com", name: "Jane Smith" },
    to: [{ address: "me@balizero.com" }],
    date: new Date(Date.now() - 86400000).toISOString(),
    snippet: "Notes from today's meeting...",
    is_read: true,
    is_flagged: false,
    has_attachments: false,
    folder_id: "inbox",
  },
];

const defaultProps = {
  emails: mockEmails,
  selectedEmailId: null,
  selectedIds: new Set<string>(),
  onSelectEmail: vi.fn(),
  onToggleSelect: vi.fn(),
  onSelectAll: vi.fn(),
  onMarkRead: vi.fn(),
  onToggleFlag: vi.fn(),
  onDelete: vi.fn(),
  onSearch: vi.fn(),
  searchQuery: "",
  totalEmails: 2,
};

describe("EmailList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders email subjects", () => {
    render(<EmailList {...defaultProps} />);
    expect(screen.getByText("Important Update")).toBeInTheDocument();
    expect(screen.getByText("Meeting Notes")).toBeInTheDocument();
  });

  it("renders sender names", () => {
    render(<EmailList {...defaultProps} />);
    expect(screen.getByText("John Doe")).toBeInTheDocument();
    expect(screen.getByText("Jane Smith")).toBeInTheDocument();
  });

  it("renders email snippets", () => {
    render(<EmailList {...defaultProps} />);
    expect(
      screen.getByText("Here is an important update about..."),
    ).toBeInTheDocument();
  });

  it("renders search input", () => {
    render(<EmailList {...defaultProps} />);
    expect(screen.getByLabelText("Cerca email")).toBeInTheDocument();
  });

  it("calls onSelectEmail when email content is clicked", () => {
    const onSelectEmail = vi.fn();
    render(
      <EmailList {...defaultProps} onSelectEmail={onSelectEmail} />,
    );
    fireEvent.click(screen.getByText("Important Update"));
    expect(onSelectEmail).toHaveBeenCalledWith("msg-1");
  });

  it("renders select all checkbox", () => {
    render(<EmailList {...defaultProps} />);
    const selectAllBtn = screen.getByLabelText(
      "Seleziona tutte le email",
    );
    expect(selectAllBtn).toBeInTheDocument();
  });

  it("calls onSelectAll when select-all is clicked", () => {
    const onSelectAll = vi.fn();
    render(<EmailList {...defaultProps} onSelectAll={onSelectAll} />);
    fireEvent.click(
      screen.getByLabelText("Seleziona tutte le email"),
    );
    expect(onSelectAll).toHaveBeenCalledWith(true);
  });

  it("shows batch action buttons when emails are selected", () => {
    render(
      <EmailList
        {...defaultProps}
        selectedIds={new Set(["msg-1"])}
      />,
    );
    expect(screen.getByLabelText("Segna come lette")).toBeInTheDocument();
    expect(
      screen.getByLabelText("Segna come non lette"),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Elimina selezionate"),
    ).toBeInTheDocument();
  });

  it("does not show batch actions when nothing selected", () => {
    render(<EmailList {...defaultProps} />);
    expect(
      screen.queryByLabelText("Segna come lette"),
    ).not.toBeInTheDocument();
  });

  it("calls onMarkRead for batch mark-as-read", () => {
    const onMarkRead = vi.fn();
    render(
      <EmailList
        {...defaultProps}
        selectedIds={new Set(["msg-1", "msg-2"])}
        onMarkRead={onMarkRead}
      />,
    );
    fireEvent.click(screen.getByLabelText("Segna come lette"));
    expect(onMarkRead).toHaveBeenCalledWith(["msg-1", "msg-2"], true);
  });

  it("calls onDelete for batch delete", () => {
    const onDelete = vi.fn();
    render(
      <EmailList
        {...defaultProps}
        selectedIds={new Set(["msg-1"])}
        onDelete={onDelete}
      />,
    );
    fireEvent.click(screen.getByLabelText("Elimina selezionate"));
    expect(onDelete).toHaveBeenCalledWith(["msg-1"]);
  });

  it("shows empty state when no emails", () => {
    render(
      <EmailList {...defaultProps} emails={[]} totalEmails={0} />,
    );
    expect(
      screen.getByText("No emails in this folder"),
    ).toBeInTheDocument();
  });

  it("shows search-specific empty state", () => {
    render(
      <EmailList
        {...defaultProps}
        emails={[]}
        searchQuery="nonexistent"
        totalEmails={0}
      />,
    );
    expect(
      screen.getByText("No emails match your search"),
    ).toBeInTheDocument();
  });

  it("shows loading skeletons when loading", () => {
    const { container } = render(
      <EmailList {...defaultProps} isLoading={true} />,
    );
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBe(10);
  });

  it("renders pagination when totalEmails > 0", () => {
    render(
      <EmailList
        {...defaultProps}
        totalEmails={100}
        currentPage={1}
        hasMore={true}
      />,
    );
    expect(screen.getByText(/1 – 50 of 100 emails/)).toBeInTheDocument();
  });

  it("renders pagination buttons", () => {
    render(
      <EmailList
        {...defaultProps}
        totalEmails={100}
        currentPage={1}
        hasMore={true}
      />,
    );
    expect(screen.getByLabelText("Pagina precedente")).toBeInTheDocument();
    expect(screen.getByLabelText("Pagina successiva")).toBeInTheDocument();
  });

  it("disables previous page button on first page", () => {
    render(
      <EmailList
        {...defaultProps}
        totalEmails={100}
        currentPage={1}
        hasMore={true}
      />,
    );
    expect(screen.getByLabelText("Pagina precedente")).toBeDisabled();
  });

  it("disables next page button when no more", () => {
    render(
      <EmailList
        {...defaultProps}
        totalEmails={50}
        currentPage={1}
        hasMore={false}
      />,
    );
    expect(screen.getByLabelText("Pagina successiva")).toBeDisabled();
  });

  it("submits search form", () => {
    const onSearch = vi.fn();
    render(<EmailList {...defaultProps} onSearch={onSearch} />);

    const searchInput = screen.getByLabelText("Cerca email");
    fireEvent.change(searchInput, { target: { value: "test query" } });
    fireEvent.submit(searchInput.closest("form")!);

    expect(onSearch).toHaveBeenCalledWith("test query");
  });
});
