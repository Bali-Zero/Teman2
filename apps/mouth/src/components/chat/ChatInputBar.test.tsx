import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatInputBar, ChatInputBarProps } from "./ChatInputBar";
import { createRef } from "react";

describe("ChatInputBar", () => {
  const defaultProps: ChatInputBarProps = {
    input: "",
    setInput: vi.fn(),
    isLoading: false,
    showImagePrompt: false,
    setShowImagePrompt: vi.fn(),
    onSend: vi.fn(),
    onImageGenerate: vi.fn(),
    showAttachMenu: false,
    setShowAttachMenu: vi.fn(),
    attachMenuRef: createRef<HTMLDivElement>(),
    fileInputRef: createRef<HTMLInputElement>(),
    onFileChange: vi.fn(),
    isRecording: false,
    recordingTime: 0,
    onStartRecording: vi.fn(),
    onStopRecording: vi.fn(),
    attachedImages: [],
    onRemoveImage: vi.fn(),
  };

  it("should render textarea", () => {
    render(<ChatInputBar {...defaultProps} />);
    expect(screen.getByLabelText("Type your message")).toBeInTheDocument();
  });

  it("should render attached images when provided", () => {
    const attachedImages = [
      { id: "1", base64: "data:image/png;base64,test1", name: "test1.png", size: 100 },
      { id: "2", base64: "data:image/png;base64,test2", name: "test2.png", size: 200 },
    ];
    render(<ChatInputBar {...defaultProps} attachedImages={attachedImages} />);

    expect(screen.getByAltText("test1.png")).toBeInTheDocument();
    expect(screen.getByAltText("test2.png")).toBeInTheDocument();
    expect(screen.getAllByLabelText(/Remove image/)).toHaveLength(2);
  });

  it("should call onRemoveImage when remove button is clicked", async () => {
    const user = userEvent.setup();
    const onRemoveImage = vi.fn();
    const attachedImages = [
      { id: "1", base64: "data:image/png;base64,test1", name: "test1.png", size: 100 },
    ];
    render(<ChatInputBar {...defaultProps} attachedImages={attachedImages} onRemoveImage={onRemoveImage} />);

    await user.click(screen.getByLabelText("Remove image test1.png"));
    expect(onRemoveImage).toHaveBeenCalledWith("1");
  });

  it("should have correct aria-label on remove button", () => {
    const attachedImages = [
      { id: "1", base64: "data:image/png;base64,test1", name: "test1.png", size: 100 },
    ];
    render(<ChatInputBar {...defaultProps} attachedImages={attachedImages} />);

    const removeButton = screen.getByLabelText("Remove image test1.png");
    expect(removeButton).toBeInTheDocument();
  });
});
