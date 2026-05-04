import { render, screen, fireEvent } from '@testing-library/react';
import { ChatInputBar } from './ChatInputBar';
import { vi, describe, it, expect } from 'vitest';

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
    attachedImages: [],
    onRemoveImage: vi.fn(),
  };

  it('renders input field', () => {
    render(<ChatInputBar {...defaultProps} />);
    expect(screen.getByPlaceholderText(/Type your message/i)).toBeDefined();
  });

  it('displays image previews when attachedImages are provided', () => {
    const attachedImages = [
      { id: '1', base64: 'data:image/png;base64,abc', name: 'test.png', size: 100 },
    ];
    render(<ChatInputBar {...defaultProps} attachedImages={attachedImages} />);
    expect(screen.getByAltText('test.png')).toBeDefined();
    expect(screen.getByLabelText(/Remove image test.png/i)).toBeDefined();
  });

  it('calls onRemoveImage when remove button is clicked', () => {
    const onRemoveImage = vi.fn();
    const attachedImages = [
      { id: '1', base64: 'data:image/png;base64,abc', name: 'test.png', size: 100 },
    ];
    render(<ChatInputBar {...defaultProps} attachedImages={attachedImages} onRemoveImage={onRemoveImage} />);

    const removeButton = screen.getByLabelText(/Remove image test.png/i);
    fireEvent.click(removeButton);

    expect(onRemoveImage).toHaveBeenCalledWith('1');
  });
});
