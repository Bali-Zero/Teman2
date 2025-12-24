import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThinkingIndicator } from './ThinkingIndicator';

describe('ThinkingIndicator', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should not render when isVisible is false', () => {
    const { container } = render(<ThinkingIndicator isVisible={false} />);
    expect(container.firstChild).toBeNull();
  });

  it('should render when isVisible is true', () => {
    render(<ThinkingIndicator isVisible={true} />);
    expect(screen.getByText(/Zantara is thinking/)).toBeInTheDocument();
  });

  it('should show elapsed time when provided', () => {
    render(<ThinkingIndicator isVisible={true} elapsedTime={15} />);
    expect(screen.getByText('15s')).toBeInTheDocument();
  });

  it('should show custom status message', () => {
    render(<ThinkingIndicator isVisible={true} currentStatus="Searching databases..." />);
    expect(screen.getByText('Searching databases...')).toBeInTheDocument();
  });

  it('should show default rotating phrase when no custom status', () => {
    render(<ThinkingIndicator isVisible={true} />);
    // First phrase in rotation
    expect(screen.getByText('Analyzing your question...')).toBeInTheDocument();
  });

  it('should show activity list when steps are provided', () => {
    const steps = [
      { type: 'tool_start' as const, data: { name: 'vector_search', args: {} }, timestamp: new Date() },
      { type: 'tool_end' as const, data: { result: 'found' }, timestamp: new Date() },
    ];
    render(<ThinkingIndicator isVisible={true} steps={steps} />);
    expect(screen.getByText('Searching Knowledge Base')).toBeInTheDocument();
    expect(screen.getByText('Done')).toBeInTheDocument();
  });

  it('should show sources count when tools complete', () => {
    const steps = [
      { type: 'tool_start' as const, data: { name: 'vector_search', args: {} }, timestamp: new Date() },
      { type: 'tool_end' as const, data: { result: 'found' }, timestamp: new Date() },
    ];
    render(<ThinkingIndicator isVisible={true} steps={steps} />);
    expect(screen.getByText('1 source found')).toBeInTheDocument();
  });

  it('should show plural sources when multiple tools complete', () => {
    const steps = [
      { type: 'tool_start' as const, data: { name: 'vector_search', args: {} }, timestamp: new Date() },
      { type: 'tool_end' as const, data: { result: 'found' }, timestamp: new Date() },
      { type: 'tool_start' as const, data: { name: 'database_query', args: {} }, timestamp: new Date() },
      { type: 'tool_end' as const, data: { result: 'found' }, timestamp: new Date() },
    ];
    render(<ThinkingIndicator isVisible={true} steps={steps} />);
    expect(screen.getByText('2 sources found')).toBeInTheDocument();
  });

  it('should show database_query tool correctly', () => {
    const steps = [
      { type: 'tool_start' as const, data: { name: 'database_query', args: {} }, timestamp: new Date() },
    ];
    render(<ThinkingIndicator isVisible={true} steps={steps} />);
    expect(screen.getByText('Reading Full Document')).toBeInTheDocument();
  });

  it('should show web_search tool correctly', () => {
    const steps = [
      { type: 'tool_start' as const, data: { name: 'web_search', args: {} }, timestamp: new Date() },
    ];
    render(<ThinkingIndicator isVisible={true} steps={steps} />);
    expect(screen.getByText('Searching the Web')).toBeInTheDocument();
  });

  it('should use default label for unknown tools', () => {
    const steps = [
      { type: 'tool_start' as const, data: { name: 'unknown_tool', args: {} }, timestamp: new Date() },
    ];
    render(<ThinkingIndicator isVisible={true} steps={steps} />);
    expect(screen.getByText('Processing')).toBeInTheDocument();
  });
});
