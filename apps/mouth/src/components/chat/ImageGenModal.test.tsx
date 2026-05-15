import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ImageGenModal } from './ImageGenModal';

import { beforeEach } from 'vitest';

describe('ImageGenModal', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    onSubmit: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders correctly when open', () => {
    render(<ImageGenModal {...defaultProps} />);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Generate Image')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/a magical unicorn/i)).toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', () => {
    render(<ImageGenModal {...defaultProps} />);
    fireEvent.click(screen.getByLabelText('Close image generator'));
    expect(defaultProps.onClose).toHaveBeenCalled();
  });

  it('calls onClose when backdrop is clicked', () => {
    render(<ImageGenModal {...defaultProps} />);
    // The backdrop is the outermost div with role="dialog"
    fireEvent.click(screen.getByRole('dialog'));
    expect(defaultProps.onClose).toHaveBeenCalled();
  });

  it('does not call onClose when modal content is clicked', () => {
    render(<ImageGenModal {...defaultProps} />);
    fireEvent.click(screen.getByText('Generate Image'));
    expect(defaultProps.onClose).not.toHaveBeenCalled();
  });

  it('calls onSubmit with prompt when Generate button is clicked', () => {
    render(<ImageGenModal {...defaultProps} />);
    const textarea = screen.getByLabelText('Image generation prompt');
    fireEvent.change(textarea, { target: { value: 'A cool dragon' } });
    fireEvent.click(screen.getByText('Generate', { selector: 'button' }));
    expect(defaultProps.onSubmit).toHaveBeenCalledWith('A cool dragon');
  });

  it('disables Generate button when prompt is empty', () => {
    render(<ImageGenModal {...defaultProps} />);
    const button = screen.getByText('Generate', { selector: 'button' });
    expect(button).toBeDisabled();
  });
});
