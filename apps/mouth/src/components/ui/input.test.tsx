import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Input } from './input';

describe('Input', () => {
  it('should render input element', () => {
    render(<Input />);
    const input = screen.getByRole('textbox');
    expect(input).toBeInTheDocument();
  });

  it('should accept className prop', () => {
    render(<Input className="custom-class" />);
    const input = screen.getByRole('textbox');
    expect(input).toHaveClass('custom-class');
  });

  it('should accept type prop', () => {
    const { container } = render(<Input type="password" />);
    const input = container.querySelector('input[type="password"]');
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute('type', 'password');
  });

  it('should accept placeholder prop', () => {
    render(<Input placeholder="Enter text" />);
    const input = screen.getByPlaceholderText('Enter text');
    expect(input).toBeInTheDocument();
  });

  it('should accept value and onChange', async () => {
    const user = userEvent.setup();
    const handleChange = vi.fn();
    render(<Input value="test" onChange={handleChange} />);
    const input = screen.getByRole('textbox') as HTMLInputElement;
    expect(input.value).toBe('test');

    await user.type(input, 'x');
    expect(handleChange).toHaveBeenCalled();
  });

  it('should be disabled when disabled prop is true', () => {
    render(<Input disabled />);
    const input = screen.getByRole('textbox');
    expect(input).toBeDisabled();
  });

  it('should accept ref', () => {
    const ref = vi.fn();
    render(<Input ref={ref} />);
    expect(ref).toHaveBeenCalled();
  });

  it('should merge className with default classes', () => {
    render(<Input className="test-class" />);
    const input = screen.getByRole('textbox');
    expect(input.className).toContain('test-class');
    expect(input.className).toContain('flex');
  });
});
