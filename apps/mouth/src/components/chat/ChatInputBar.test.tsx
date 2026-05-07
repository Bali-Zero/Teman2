import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ChatInputBar } from './ChatInputBar';
import React from 'react';

// Mock UI constant
vi.mock('@/constants', () => ({
  UI: {
    MAX_TEXTAREA_HEIGHT: 200,
  },
}));

// Mock framer-motion to avoid animation issues in tests
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

// Mock Next.js Image component
vi.mock('next/image', () => ({
  __esModule: true,
  default: (props: any) => <img {...props} />,
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
    attachMenuRef: { current: null } as any,
    fileInputRef: { current: null } as any,
    onFileChange: vi.fn(),
    isRecording: false,
    recordingTime: 0,
    onStartRecording: vi.fn(),
    onStopRecording: vi.fn(),
    attachedImages: [],
    onRemoveImage: vi.fn(),
  };

  it('renders correctly', () => {
    render(<ChatInputBar {...defaultProps} />);
    expect(screen.getByPlaceholderText(/Type your message.../i)).toBeInTheDocument();
  });

  it('shows attached images', () => {
    const attachedImages = [
      { id: '1', base64: 'data:image/png;base64,123', name: 'test.png', size: 100 },
    ];
    render(<ChatInputBar {...defaultProps} attachedImages={attachedImages} />);
    expect(screen.getByAltText('test.png')).toBeInTheDocument();
  });

  it('calls onRemoveImage when remove button is clicked', () => {
    const onRemoveImage = vi.fn();
    const attachedImages = [
      { id: '1', base64: 'data:image/png;base64,123', name: 'test.png', size: 100 },
    ];
    render(
      <ChatInputBar
        {...defaultProps}
        attachedImages={attachedImages}
        onRemoveImage={onRemoveImage}
      />
    );

    const removeBtn = screen.getByLabelText(/Remove image test.png/i);
    fireEvent.click(removeBtn);
    expect(onRemoveImage).toHaveBeenCalledWith('1');
  });

  it('toggles attachment menu', () => {
    const setShowAttachMenu = vi.fn();
    render(<ChatInputBar {...defaultProps} setShowAttachMenu={setShowAttachMenu} />);

    const attachBtn = screen.getByLabelText(/Attach file/i);
    fireEvent.click(attachBtn);
    expect(setShowAttachMenu).toHaveBeenCalledWith(true);
  });
});
