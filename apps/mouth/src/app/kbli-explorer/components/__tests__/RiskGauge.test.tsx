/**
 * Unit tests for RiskGauge component
 *
 * Tests cover:
 * - SVG rendering for each risk level
 * - Label text accuracy
 * - Needle and center dot presence
 * - Gradient arc rendering
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import RiskGauge from '../RiskGauge';

describe('RiskGauge', () => {
  it('should render an SVG element', () => {
    const { container } = render(<RiskGauge level="medium" />);
    const svg = container.querySelector('svg');
    expect(svg).toBeTruthy();
  });

  it('should display "Low Risk" label for low level', () => {
    render(<RiskGauge level="low" />);
    expect(screen.getByText('Low Risk')).toBeTruthy();
  });

  it('should display "Medium-Low" label for medium-low level', () => {
    render(<RiskGauge level="medium-low" />);
    expect(screen.getByText('Medium-Low')).toBeTruthy();
  });

  it('should display "Medium Risk" label for medium level', () => {
    render(<RiskGauge level="medium" />);
    expect(screen.getByText('Medium Risk')).toBeTruthy();
  });

  it('should display "Medium-High" label for medium-high level', () => {
    render(<RiskGauge level="medium-high" />);
    expect(screen.getByText('Medium-High')).toBeTruthy();
  });

  it('should display "High Risk" label for high level', () => {
    render(<RiskGauge level="high" />);
    expect(screen.getByText('High Risk')).toBeTruthy();
  });

  it('should render a needle (line element)', () => {
    const { container } = render(<RiskGauge level="medium" />);
    const line = container.querySelector('line');
    expect(line).toBeTruthy();
  });

  it('should render center dot circles', () => {
    const { container } = render(<RiskGauge level="medium" />);
    const circles = container.querySelectorAll('circle');
    // 2 circles: outer dot + inner dot
    expect(circles.length).toBe(2);
  });

  it('should render the gradient arc path', () => {
    const { container } = render(<RiskGauge level="high" />);
    const paths = container.querySelectorAll('path');
    // 2 paths: track + colored arc
    expect(paths.length).toBe(2);
  });

  it('should include a gradient definition', () => {
    const { container } = render(<RiskGauge level="low" />);
    const gradient = container.querySelector('linearGradient');
    expect(gradient).toBeTruthy();
    expect(gradient?.id).toBe('risk-arc-grad');
  });

  it('should use correct color for low risk', () => {
    render(<RiskGauge level="low" />);
    const label = screen.getByText('Low Risk');
    expect(label.style.color).toBe('rgb(52, 211, 153)'); // #34d399
  });

  it('should use correct color for high risk', () => {
    render(<RiskGauge level="high" />);
    const label = screen.getByText('High Risk');
    expect(label.style.color).toBe('rgb(239, 68, 68)'); // #ef4444
  });
});
