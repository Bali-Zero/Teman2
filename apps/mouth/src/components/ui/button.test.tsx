import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Button } from './button';

describe('Button', () => {
  it('should render', () => {
    render(<Button>Test</Button>);
    // TODO: Add assertions
    expect(true).toBe(true);
  });

  // TODO: Add more test cases
});
