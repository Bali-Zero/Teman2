import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ChatInputBar } from './ChatInputBar';
import React from 'react';

// Mock dependencies
vi.mock('./ChatRecordingOverlay', () => ({
  ChatRecordingOverlay: () => <div data-testid="recording-overlay" />,
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

  it('renders image previews when attachedImages are provided', () => {
    const attachedImages = [
      { id: '1', base64: 'data:image/png;base64,123', name: 'image1.png', size: 100 },
      { id: '2', base64: 'data:image/png;base64,456', name: 'image2.png', size: 200 },
    ];

    render(<ChatInputBar {...defaultProps} attachedImages={attachedImages} />);

    expect(screen.getByAltText('image1.png')).toBeDefined();
    expect(screen.getByAltText('image2.png')).toBeDefined();
  });

  it('calls onRemoveImage when remove button is clicked', () => {
    const onRemoveImage = vi.fn();
    const attachedImages = [
      { id: '1', base64: 'data:image/png;base64,123', name: 'image1.png', size: 100 },
    ];

    render(
      <ChatInputBar
        {...defaultProps}
        attachedImages={attachedImages}
        onRemoveImage={onRemoveImage}
      />
    );

    const removeButton = screen.getByLabelText('Remove image: image1.png');
    fireEvent.click(removeButton);

    expect(onRemoveImage).toHaveBeenCalledWith('1');
  });
});
