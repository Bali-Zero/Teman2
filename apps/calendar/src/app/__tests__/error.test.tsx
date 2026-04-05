import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Error from '../error';

// Mock lucide-react
vi.mock('lucide-react', () => ({
  AlertTriangle: (props: Record<string, unknown>) => <svg data-testid="alert-icon" {...props} />,
  RefreshCw: (props: Record<string, unknown>) => <svg data-testid="refresh-icon" {...props} />,
}));

describe('Calendar Error Page', () => {
  const mockError = new Error('Calendar error') as Error & {
    digest?: string;
  };
  const mockReset = vi.fn();

  it('renders error heading', () => {
    render(<Error error={mockError} reset={mockReset} />);
    expect(screen.getByText('Qualcosa è andato storto')).toBeInTheDocument();
  });

  it('renders error description', () => {
    render(<Error error={mockError} reset={mockReset} />);
    expect(
      screen.getByText(/Si è verificato un errore durante il caricamento del Calendario/)
    ).toBeInTheDocument();
  });

  it('renders retry button', () => {
    render(<Error error={mockError} reset={mockReset} />);
    expect(screen.getByText('Riprova')).toBeInTheDocument();
  });

  it('calls reset when retry is clicked', () => {
    render(<Error error={mockError} reset={mockReset} />);
    fireEvent.click(screen.getByText('Riprova'));
    expect(mockReset).toHaveBeenCalledTimes(1);
  });

  it('renders home link', () => {
    render(<Error error={mockError} reset={mockReset} />);
    const homeLink = screen.getByText('Torna alla home');
    expect(homeLink.closest('a')).toHaveAttribute('href', 'https://kita.balizero.com');
  });
});
