import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { usePathname } from 'next/navigation';
import IntelligenceLayout from './layout';

vi.mock('next/navigation', () => ({
  usePathname: vi.fn(),
}));

describe('IntelligenceLayout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render header with title and description', () => {
    vi.mocked(usePathname).mockReturnValue('/intelligence/visa-oracle');

    render(
      <IntelligenceLayout>
        <div>Test Content</div>
      </IntelligenceLayout>
    );

    expect(screen.getByText('Intelligence Center')).toBeInTheDocument();
    expect(screen.getByText('AI-powered monitoring of Indonesian immigration regulations')).toBeInTheDocument();
  });

  it('should show "Agent Active" indicator', () => {
    vi.mocked(usePathname).mockReturnValue('/intelligence/visa-oracle');

    render(
      <IntelligenceLayout>
        <div>Test Content</div>
      </IntelligenceLayout>
    );

    expect(screen.getByText('Agent Active')).toBeInTheDocument();
  });

  it('should render all 3 tabs', () => {
    vi.mocked(usePathname).mockReturnValue('/intelligence/visa-oracle');

    render(
      <IntelligenceLayout>
        <div>Test Content</div>
      </IntelligenceLayout>
    );

    expect(screen.getByText('Visa Oracle')).toBeInTheDocument();
    expect(screen.getByText('News Room')).toBeInTheDocument();
    expect(screen.getByText('System Pulse')).toBeInTheDocument();
  });

  it('should highlight Visa Oracle tab when active', () => {
    vi.mocked(usePathname).mockReturnValue('/intelligence/visa-oracle');

    const { container } = render(
      <IntelligenceLayout>
        <div>Test Content</div>
      </IntelligenceLayout>
    );

    const visaOracleLink = screen.getByText('Visa Oracle').closest('a');
    expect(visaOracleLink).toHaveAttribute('href', '/intelligence/visa-oracle');
    expect(visaOracleLink?.className).toContain('bg-[var(--accent)]/10');
  });

  it('should highlight News Room tab when active', () => {
    vi.mocked(usePathname).mockReturnValue('/intelligence/news-room');

    const { container } = render(
      <IntelligenceLayout>
        <div>Test Content</div>
      </IntelligenceLayout>
    );

    const newsRoomLink = screen.getByText('News Room').closest('a');
    expect(newsRoomLink).toHaveAttribute('href', '/intelligence/news-room');
    expect(newsRoomLink?.className).toContain('bg-[var(--accent)]/10');
  });

  it('should highlight System Pulse tab when active', () => {
    vi.mocked(usePathname).mockReturnValue('/intelligence/system-pulse');

    const { container } = render(
      <IntelligenceLayout>
        <div>Test Content</div>
      </IntelligenceLayout>
    );

    const systemPulseLink = screen.getByText('System Pulse').closest('a');
    expect(systemPulseLink).toHaveAttribute('href', '/intelligence/system-pulse');
    expect(systemPulseLink?.className).toContain('bg-[var(--accent)]/10');
  });

  it('should render tab descriptions', () => {
    vi.mocked(usePathname).mockReturnValue('/intelligence/visa-oracle');

    render(
      <IntelligenceLayout>
        <div>Test Content</div>
      </IntelligenceLayout>
    );

    expect(screen.getByText('Review automated visa regulation discoveries')).toBeInTheDocument();
    expect(screen.getByText('Curate immigration news articles')).toBeInTheDocument();
    expect(screen.getByText('Monitor agent health and performance')).toBeInTheDocument();
  });

  it('should render children content', () => {
    vi.mocked(usePathname).mockReturnValue('/intelligence/visa-oracle');

    render(
      <IntelligenceLayout>
        <div data-testid="test-child">Test Child Content</div>
      </IntelligenceLayout>
    );

    expect(screen.getByTestId('test-child')).toBeInTheDocument();
    expect(screen.getByText('Test Child Content')).toBeInTheDocument();
  });

  it('should have correct href attributes for all tabs', () => {
    vi.mocked(usePathname).mockReturnValue('/intelligence/visa-oracle');

    render(
      <IntelligenceLayout>
        <div>Test Content</div>
      </IntelligenceLayout>
    );

    const visaOracleLink = screen.getByText('Visa Oracle').closest('a');
    const newsRoomLink = screen.getByText('News Room').closest('a');
    const systemPulseLink = screen.getByText('System Pulse').closest('a');

    expect(visaOracleLink).toHaveAttribute('href', '/intelligence/visa-oracle');
    expect(newsRoomLink).toHaveAttribute('href', '/intelligence/news-room');
    expect(systemPulseLink).toHaveAttribute('href', '/intelligence/system-pulse');
  });

  it('should not highlight inactive tabs', () => {
    vi.mocked(usePathname).mockReturnValue('/intelligence/visa-oracle');

    const { container } = render(
      <IntelligenceLayout>
        <div>Test Content</div>
      </IntelligenceLayout>
    );

    const newsRoomLink = screen.getByText('News Room').closest('a');
    const systemPulseLink = screen.getByText('System Pulse').closest('a');

    expect(newsRoomLink?.className).not.toContain('bg-[var(--accent)]/10');
    expect(systemPulseLink?.className).not.toContain('bg-[var(--accent)]/10');
  });

  it('should handle deep paths for active tab detection', () => {
    vi.mocked(usePathname).mockReturnValue('/intelligence/visa-oracle/some-deep-path');

    const { container } = render(
      <IntelligenceLayout>
        <div>Test Content</div>
      </IntelligenceLayout>
    );

    const visaOracleLink = screen.getByText('Visa Oracle').closest('a');
    expect(visaOracleLink?.className).toContain('bg-[var(--accent)]/10');
  });
});
