import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ChatInputBar } from './ChatInputBar';
import React from 'react';

// Mock Framer Motion to avoid issues in JSDOM
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

// Mock Lucide icons
vi.mock('lucide-react', () => ({
  Send: () => <div data-testid="send-icon" />,
  ImageIcon: () => <div data-testid="image-icon" />,
  Plus: () => <div data-testid="plus-icon" />,
  Loader2: () => <div data-testid="loader-icon" />,
  Upload: () => <div data-testid="upload-icon" />,
  Camera: () => <div data-testid="camera-icon" />,
  Mic: () => <div data-testid="mic-icon" />,
  X: () => <div data-testid="x-icon" />,
}));

describe('ChatInputBar', () => {
  const defaultProps = {
    input: '',
    setInput: vi.fn(),
    isLoading: false,
    showImagePrompt: false,
    setShowImagePrompt: vi.fn(),
    onSend: vi.fn(),
    onImageGenerate: vi.fn(),
    showAttachMenu: false,
    setShowAttachMenu: vi.fn(),
    attachMenuRef: { current: null },
    fileInputRef: { current: null },
    onFileChange: vi.fn(),
    isRecording: false,
    recordingTime: 0,
    onStartRecording: vi.fn(),
    onStopRecording: vi.fn(),
  };

  it('renders correctly', () => {
    render(<ChatInputBar {...defaultProps} />);
    expect(screen.getByPlaceholderText(/Type your message/i)).toBeDefined();
  });

  it('renders image previews when attachedImages are provided', () => {
    const attachedImages = [
      { id: '1', base64: 'data:image/png;base64,abc', name: 'image1.png', size: 100 },
    ];
    render(<ChatInputBar {...defaultProps} attachedImages={attachedImages} />);

    const img = screen.getByAltText('image1.png');
    expect(img).toBeDefined();
    expect(screen.getByLabelText('Remove image1.png')).toBeDefined();
  });

  it('calls onRemoveImage when remove button is clicked', () => {
    const onRemoveImage = vi.fn();
    const attachedImages = [
      { id: '1', base64: 'data:image/png;base64,abc', name: 'image1.png', size: 100 },
    ];
    render(
      <ChatInputBar
        {...defaultProps}
        attachedImages={attachedImages}
        onRemoveImage={onRemoveImage}
      />
    );

    const removeBtn = screen.getByLabelText('Remove image1.png');
    fireEvent.click(removeBtn);

    expect(onRemoveImage).toHaveBeenCalledWith('1');
  });
});
