import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ChatInputBar } from './ChatInputBar';
import React from 'react';

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
      { id: '1', base64: 'data:image/png;base64,123', name: 'test.png', size: 100 },
    ];
    render(<ChatInputBar {...defaultProps} attachedImages={attachedImages} />);

    expect(screen.getByAltText('test.png')).toBeInTheDocument();
    expect(screen.getByLabelText('Remove test.png')).toBeInTheDocument();
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

    fireEvent.click(screen.getByLabelText('Remove test.png'));
    expect(onRemoveImage).toHaveBeenCalledWith('1');
  });

  it('shows attachment menu when showAttachMenu is true', () => {
    render(<ChatInputBar {...defaultProps} showAttachMenu={true} />);

    expect(screen.getByText('Upload file')).toBeInTheDocument();
    expect(screen.getByText('Generate image')).toBeInTheDocument();
  });

  it('calls setShowAttachMenu when attachment button is clicked', () => {
    render(<ChatInputBar {...defaultProps} />);

    fireEvent.click(screen.getByLabelText('Attach file'));
    expect(defaultProps.setShowAttachMenu).toHaveBeenCalledWith(true);
  });
});
