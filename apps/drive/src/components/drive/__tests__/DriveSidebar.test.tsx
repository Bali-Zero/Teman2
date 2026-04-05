import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { DriveSidebar } from '../DriveSidebar';

const defaultProps = {
  onNewClick: vi.fn(),
  onUploadClick: vi.fn(),
  activeView: 'my-drive' as const,
  onViewChange: vi.fn(),
  storageUsed: 5 * 1024 * 1024 * 1024, // 5 GB
  storageTotal: 15 * 1024 * 1024 * 1024, // 15 GB
};

describe('DriveSidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the 'Nuovo' button", () => {
    render(<DriveSidebar {...defaultProps} />);
    expect(screen.getByText('Nuovo')).toBeInTheDocument();
  });

  it("renders the navigation item 'Bali Zero Drive'", () => {
    render(<DriveSidebar {...defaultProps} />);
    expect(screen.getByText('Bali Zero Drive')).toBeInTheDocument();
  });

  it('renders the storage indicator with total', () => {
    render(<DriveSidebar {...defaultProps} />);
    expect(screen.getByText('15.0 GB')).toBeInTheDocument();
  });

  it('renders the used storage text', () => {
    render(<DriveSidebar {...defaultProps} />);
    expect(screen.getByText('5.0 GB utilizzati')).toBeInTheDocument();
  });

  it('renders MB format for small storage values', () => {
    render(
      <DriveSidebar
        {...defaultProps}
        storageUsed={500 * 1024 * 1024}
        storageTotal={1024 * 1024 * 1024}
      />
    );
    expect(screen.getByText('500 MB utilizzati')).toBeInTheDocument();
  });

  it('calls onNewClick when Nuovo button is clicked', () => {
    const onNewClick = vi.fn();
    render(<DriveSidebar {...defaultProps} onNewClick={onNewClick} />);
    fireEvent.click(screen.getByText('Nuovo'));
    expect(onNewClick).toHaveBeenCalledTimes(1);
  });

  it('calls onViewChange when nav item is clicked', () => {
    const onViewChange = vi.fn();
    render(<DriveSidebar {...defaultProps} onViewChange={onViewChange} />);
    fireEvent.click(screen.getByText('Bali Zero Drive'));
    expect(onViewChange).toHaveBeenCalledWith('my-drive');
  });

  it('highlights active nav item', () => {
    render(<DriveSidebar {...defaultProps} activeView="my-drive" />);
    const navButton = screen.getByText('Bali Zero Drive').closest('button')!;
    expect(navButton.className).toContain('text-[#d4845a]');
  });

  it('renders the navigation aria-label', () => {
    render(<DriveSidebar {...defaultProps} />);
    expect(screen.getByRole('navigation', { name: 'Navigazione Drive' })).toBeInTheDocument();
  });

  it('renders collapsed view with icon-only buttons', () => {
    render(<DriveSidebar {...defaultProps} isCollapsed={true} />);
    // Collapsed view should have aria-label for new file button
    expect(screen.getByLabelText('Nuovo file o cartella')).toBeInTheDocument();
    // Should have aria-label for nav item
    expect(screen.getByLabelText('Bali Zero Drive')).toBeInTheDocument();
  });

  it('renders Spazio label in storage section', () => {
    render(<DriveSidebar {...defaultProps} />);
    expect(screen.getByText('Spazio')).toBeInTheDocument();
  });
});
