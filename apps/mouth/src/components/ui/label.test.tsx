import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Label } from './label';

describe('Label', () => {
  it('should render label element', () => {
    render(<Label>Test Label</Label>);
    const label = screen.getByText('Test Label');
    expect(label.tagName).toBe('LABEL');
  });

  it('should accept className prop', () => {
    render(<Label className="custom-class">Test</Label>);
    const label = screen.getByText('Test');
    expect(label).toHaveClass('custom-class');
  });

  it('should accept htmlFor prop', () => {
    render(<Label htmlFor="input-id">Test</Label>);
    const label = screen.getByText('Test');
    expect(label).toHaveAttribute('for', 'input-id');
  });

  it('should merge className with default classes', () => {
    render(<Label className="test-class">Test</Label>);
    const label = screen.getByText('Test');
    expect(label.className).toContain('test-class');
    expect(label.className).toContain('text-sm');
  });

  it('should accept ref', () => {
    const ref = vi.fn();
    render(<Label ref={ref}>Test</Label>);
    expect(ref).toHaveBeenCalled();
  });

  it('should accept all standard label attributes', () => {
    render(
      <Label id="label-id" data-testid="test-label">
        Test
      </Label>
    );
    const label = screen.getByTestId('test-label');
    expect(label).toHaveAttribute('id', 'label-id');
  });
});
