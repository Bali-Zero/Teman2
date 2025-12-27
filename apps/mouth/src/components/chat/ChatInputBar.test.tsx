import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatInputBar, ChatInputBarProps } from './ChatInputBar';
import { createRef } from 'react';

describe('ChatInputBar', () => {
  const defaultProps: ChatInputBarProps = {
    input: '',
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
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Textarea', () => {
    it('should render textarea with placeholder', () => {
      render(<ChatInputBar {...defaultProps} />);
      expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
    });

    it('should show image prompt placeholder when in image mode', () => {
      render(<ChatInputBar {...defaultProps} showImagePrompt={true} />);
      expect(screen.getByPlaceholderText('Describe your image...')).toBeInTheDocument();
    });

    it('should call setInput on change', async () => {
      const user = userEvent.setup();
      render(<ChatInputBar {...defaultProps} />);

      const textarea = screen.getByPlaceholderText('Type your message...');
      await user.type(textarea, 'Hello');

      expect(defaultProps.setInput).toHaveBeenCalled();
    });

    it('should be disabled when loading', () => {
      render(<ChatInputBar {...defaultProps} isLoading={true} />);
      expect(screen.getByPlaceholderText('Type your message...')).toBeDisabled();
    });
  });

  describe('Send button', () => {
    it('should render send button', () => {
      render(<ChatInputBar {...defaultProps} />);
      expect(screen.getByLabelText('Send message')).toBeInTheDocument();
    });

    it('should be disabled when input is empty', () => {
      render(<ChatInputBar {...defaultProps} input="" />);
      expect(screen.getByLabelText('Send message')).toBeDisabled();
    });

    it('should be enabled when input has text', () => {
      render(<ChatInputBar {...defaultProps} input="Hello" />);
      expect(screen.getByLabelText('Send message')).not.toBeDisabled();
    });

    it('should call onSend when clicked', async () => {
      const user = userEvent.setup();
      render(<ChatInputBar {...defaultProps} input="Hello" />);

      await user.click(screen.getByLabelText('Send message'));
      expect(defaultProps.onSend).toHaveBeenCalledTimes(1);
    });

    it('should call onImageGenerate when in image mode', async () => {
      const user = userEvent.setup();
      render(<ChatInputBar {...defaultProps} input="A cat" showImagePrompt={true} />);

      await user.click(screen.getByLabelText('Generate image'));
      expect(defaultProps.onImageGenerate).toHaveBeenCalledTimes(1);
    });

    it('should show loading spinner when loading', () => {
      const { container } = render(<ChatInputBar {...defaultProps} isLoading={true} />);
      expect(container.querySelector('.animate-spin')).toBeInTheDocument();
    });
  });

  describe('Enter key behavior', () => {
    it('should call onSend on Enter key', () => {
      render(<ChatInputBar {...defaultProps} input="Hello" />);

      const textarea = screen.getByPlaceholderText('Type your message...');
      fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });

      expect(defaultProps.onSend).toHaveBeenCalledTimes(1);
    });

    it('should not send on Shift+Enter', () => {
      render(<ChatInputBar {...defaultProps} input="Hello" />);

      const textarea = screen.getByPlaceholderText('Type your message...');
      fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true });

      expect(defaultProps.onSend).not.toHaveBeenCalled();
    });

    it('should call onImageGenerate on Enter in image mode', () => {
      render(<ChatInputBar {...defaultProps} input="A cat" showImagePrompt={true} />);

      const textarea = screen.getByPlaceholderText('Describe your image...');
      fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });

      expect(defaultProps.onImageGenerate).toHaveBeenCalledTimes(1);
    });
  });

  describe('Image prompt banner', () => {
    it('should not show banner by default', () => {
      render(<ChatInputBar {...defaultProps} />);
      expect(screen.queryByText('Describe the image you want to generate')).not.toBeInTheDocument();
    });

    it('should show banner when showImagePrompt is true', () => {
      render(<ChatInputBar {...defaultProps} showImagePrompt={true} />);
      expect(screen.getByText('Describe the image you want to generate')).toBeInTheDocument();
    });

    it('should have cancel button in banner', async () => {
      const user = userEvent.setup();
      render(<ChatInputBar {...defaultProps} showImagePrompt={true} />);

      await user.click(screen.getByText('Cancel'));
      expect(defaultProps.setShowImagePrompt).toHaveBeenCalledWith(false);
    });
  });

  describe('Attachment menu', () => {
    it('should render attachment button', () => {
      render(<ChatInputBar {...defaultProps} />);
      expect(screen.getByLabelText('Attach file')).toBeInTheDocument();
    });

    it('should not show menu by default', () => {
      render(<ChatInputBar {...defaultProps} />);
      expect(screen.queryByText('Upload file')).not.toBeInTheDocument();
    });

    it('should show menu when showAttachMenu is true', () => {
      render(<ChatInputBar {...defaultProps} showAttachMenu={true} />);
      expect(screen.getByText('Upload file')).toBeInTheDocument();
      expect(screen.getByText('Generate image')).toBeInTheDocument();
    });

    it('should toggle menu on click', async () => {
      const user = userEvent.setup();
      render(<ChatInputBar {...defaultProps} />);

      await user.click(screen.getByLabelText('Attach file'));
      expect(defaultProps.setShowAttachMenu).toHaveBeenCalledWith(true);
    });
  });

  describe('Media buttons', () => {
    it('should render upload button', () => {
      render(<ChatInputBar {...defaultProps} />);
      expect(screen.getByTitle('Upload File')).toBeInTheDocument();
    });

    it('should render mic button', () => {
      render(<ChatInputBar {...defaultProps} />);
      expect(screen.getByTitle('Hold to Record')).toBeInTheDocument();
    });

    it('should render camera button', () => {
      render(<ChatInputBar {...defaultProps} />);
      expect(screen.getByTitle('Generate/Analyze Image')).toBeInTheDocument();
    });

    it('should show recording state on mic button', () => {
      const { container } = render(<ChatInputBar {...defaultProps} isRecording={true} />);
      expect(container.querySelector('.bg-red-500')).toBeInTheDocument();
    });
  });

  describe('Recording controls', () => {
    it('should call onStartRecording on mouseDown', () => {
      render(<ChatInputBar {...defaultProps} />);

      const micButton = screen.getByTitle('Hold to Record');
      fireEvent.mouseDown(micButton);

      expect(defaultProps.onStartRecording).toHaveBeenCalledTimes(1);
    });

    it('should call onStopRecording on mouseUp', () => {
      render(<ChatInputBar {...defaultProps} />);

      const micButton = screen.getByTitle('Hold to Record');
      fireEvent.mouseUp(micButton);

      expect(defaultProps.onStopRecording).toHaveBeenCalledTimes(1);
    });

    it('should call onStopRecording on mouseLeave', () => {
      render(<ChatInputBar {...defaultProps} />);

      const micButton = screen.getByTitle('Hold to Record');
      fireEvent.mouseLeave(micButton);

      expect(defaultProps.onStopRecording).toHaveBeenCalledTimes(1);
    });
  });
});
