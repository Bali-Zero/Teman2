import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { DriveToolbar } from "../DriveToolbar";

const defaultProps = {
  searchQuery: "",
  onSearchChange: vi.fn(),
  viewMode: "grid" as const,
  onViewModeChange: vi.fn(),
  onUploadClick: vi.fn(),
  onCreateClick: vi.fn(),
  isConnected: true,
};

describe("DriveToolbar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the search input", () => {
    render(<DriveToolbar {...defaultProps} />);
    expect(screen.getByLabelText("Cerca file e cartelle")).toBeInTheDocument();
  });

  it("renders the search input with current value", () => {
    render(<DriveToolbar {...defaultProps} searchQuery="test" />);
    const input = screen.getByLabelText("Cerca file e cartelle") as HTMLInputElement;
    expect(input.value).toBe("test");
  });

  it("calls onSearchChange when typing", () => {
    const onSearchChange = vi.fn();
    render(<DriveToolbar {...defaultProps} onSearchChange={onSearchChange} />);
    const input = screen.getByLabelText("Cerca file e cartelle");
    fireEvent.change(input, { target: { value: "hello" } });
    expect(onSearchChange).toHaveBeenCalledWith("hello");
  });

  it("renders grid and list view toggle buttons", () => {
    render(<DriveToolbar {...defaultProps} />);
    expect(screen.getByLabelText("Vista griglia")).toBeInTheDocument();
    expect(screen.getByLabelText("Vista lista")).toBeInTheDocument();
  });

  it("calls onViewModeChange when list button is clicked", () => {
    const onViewModeChange = vi.fn();
    render(<DriveToolbar {...defaultProps} onViewModeChange={onViewModeChange} />);
    fireEvent.click(screen.getByLabelText("Vista lista"));
    expect(onViewModeChange).toHaveBeenCalledWith("list");
  });

  it("renders upload and create buttons", () => {
    render(<DriveToolbar {...defaultProps} />);
    expect(screen.getByLabelText("Vista griglia")).toBeInTheDocument();
  });

  it("calls onUploadClick when upload button is clicked", () => {
    const onUploadClick = vi.fn();
    render(<DriveToolbar {...defaultProps} onUploadClick={onUploadClick} />);
    fireEvent.click(screen.getByText("Carica"));
    expect(onUploadClick).toHaveBeenCalledTimes(1);
  });

  it("calls onCreateClick when Nuovo button is clicked", () => {
    const onCreateClick = vi.fn();
    render(<DriveToolbar {...defaultProps} onCreateClick={onCreateClick} />);
    fireEvent.click(screen.getByText("Nuovo"));
    expect(onCreateClick).toHaveBeenCalledTimes(1);
  });

  it("shows connect drive button when not connected", () => {
    render(
      <DriveToolbar {...defaultProps} isConnected={false} onConnect={vi.fn()} />,
    );
    expect(screen.getByText("Connetti Drive")).toBeInTheDocument();
  });

  it("does not show connect button when connected", () => {
    render(<DriveToolbar {...defaultProps} isConnected={true} />);
    expect(screen.queryByText("Connetti Drive")).not.toBeInTheDocument();
  });

  it("shows clear button when search has value", () => {
    render(<DriveToolbar {...defaultProps} searchQuery="test" />);
    expect(screen.getByLabelText("Cancella ricerca")).toBeInTheDocument();
  });

  it("clears search when clear button is clicked", () => {
    const onSearchChange = vi.fn();
    render(
      <DriveToolbar
        {...defaultProps}
        searchQuery="test"
        onSearchChange={onSearchChange}
      />,
    );
    fireEvent.click(screen.getByLabelText("Cancella ricerca"));
    expect(onSearchChange).toHaveBeenCalledWith("");
  });

  it("renders info panel toggle when handler provided", () => {
    render(
      <DriveToolbar
        {...defaultProps}
        onToggleInfoPanel={vi.fn()}
        showInfoPanel={false}
        hasSelection={true}
      />,
    );
    expect(screen.getByLabelText("Mostra dettagli")).toBeInTheDocument();
  });

  it("disables info panel toggle when no selection", () => {
    render(
      <DriveToolbar
        {...defaultProps}
        onToggleInfoPanel={vi.fn()}
        showInfoPanel={false}
        hasSelection={false}
      />,
    );
    const button = screen.getByLabelText("Mostra dettagli");
    expect(button).toBeDisabled();
  });
});
