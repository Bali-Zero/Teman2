/**
 * Unit tests for MatchScoreRing component
 *
 * Tests cover:
 * - SVG rendering
 * - Score display
 * - Color thresholds (gold, amber, dim)
 * - Boundary values (0, 100)
 * - Clamping out-of-range values
 */

import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import MatchScoreRing from '../MatchScoreRing';

describe('MatchScoreRing', () => {
  it('should render an SVG element', () => {
    const { container } = render(<MatchScoreRing score={50} />);
    const svg = container.querySelector('svg');
    expect(svg).toBeTruthy();
  });

  it('should display the score number', () => {
    const { container } = render(<MatchScoreRing score={75} />);
    const scoreText = container.querySelector('.font-mono');
    expect(scoreText?.textContent).toBe('75');
  });

  it('should render two circles (track and fill)', () => {
    const { container } = render(<MatchScoreRing score={50} />);
    const circles = container.querySelectorAll('circle');
    expect(circles.length).toBe(2);
  });

  it('should use gold color for score >= 70', () => {
    const { container } = render(<MatchScoreRing score={85} />);
    const scoreText = container.querySelector('.font-mono');
    expect(scoreText?.style.color).toBe('rgb(212, 180, 131)'); // #D4B483
  });

  it('should use amber color for score 40-69', () => {
    const { container } = render(<MatchScoreRing score={55} />);
    const scoreText = container.querySelector('.font-mono');
    expect(scoreText?.style.color).toBe('rgb(245, 158, 11)'); // #F59E0B
  });

  it('should use dim color for score < 40', () => {
    const { container } = render(<MatchScoreRing score={20} />);
    const scoreText = container.querySelector('.font-mono');
    expect(scoreText?.style.color).toBe('rgb(85, 85, 85)'); // #555
  });

  it('should handle score of 0', () => {
    const { container } = render(<MatchScoreRing score={0} />);
    const scoreText = container.querySelector('.font-mono');
    expect(scoreText?.textContent).toBe('0');
  });

  it('should handle score of 100', () => {
    const { container } = render(<MatchScoreRing score={100} />);
    const scoreText = container.querySelector('.font-mono');
    expect(scoreText?.textContent).toBe('100');
  });

  it('should clamp negative values to 0', () => {
    const { container } = render(<MatchScoreRing score={-10} />);
    const scoreText = container.querySelector('.font-mono');
    expect(scoreText?.textContent).toBe('0');
  });

  it('should clamp values above 100 to 100', () => {
    const { container } = render(<MatchScoreRing score={150} />);
    const scoreText = container.querySelector('.font-mono');
    expect(scoreText?.textContent).toBe('100');
  });

  it('should have correct dimensions (40x40)', () => {
    const { container } = render(<MatchScoreRing score={50} />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.style.width).toBe('40px');
    expect(wrapper.style.height).toBe('40px');
  });
});
