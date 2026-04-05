import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { DriveBreadcrumb } from '../DriveBreadcrumb';
import type { BreadcrumbItem } from '@/lib/api/drive/drive.types';

// Mock file-icon
vi.mock('../file-icon', () => ({
  getDepartmentInfo: () => null,
}));

const breadcrumbItems: BreadcrumbItem[] = [
  { id: 'folder-a', name: 'Projects' },
  { id: 'folder-b', name: '2024' },
  { id: 'folder-c', name: 'Reports' },
];

const defaultProps = {
  items: breadcrumbItems,
  onNavigate: vi.fn(),
};

describe('DriveBreadcrumb', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the home button with 'Il Mio Drive'", () => {
    render(<DriveBreadcrumb {...defaultProps} />);
    expect(screen.getByText('Il Mio Drive')).toBeInTheDocument();
  });

  it('renders all breadcrumb item names', () => {
    render(<DriveBreadcrumb {...defaultProps} />);
    expect(screen.getByText('Projects')).toBeInTheDocument();
    expect(screen.getByText('2024')).toBeInTheDocument();
    expect(screen.getByText('Reports')).toBeInTheDocument();
  });

  it('calls onNavigate(-1) when home is clicked', () => {
    const onNavigate = vi.fn();
    render(<DriveBreadcrumb {...defaultProps} onNavigate={onNavigate} />);
    fireEvent.click(screen.getByText('Il Mio Drive'));
    expect(onNavigate).toHaveBeenCalledWith(-1);
  });

  it('calls onNavigate with correct index when item is clicked', () => {
    const onNavigate = vi.fn();
    render(<DriveBreadcrumb {...defaultProps} onNavigate={onNavigate} />);
    fireEvent.click(screen.getByText('Projects'));
    expect(onNavigate).toHaveBeenCalledWith(0);
  });

  it('marks the last breadcrumb item as current page', () => {
    render(<DriveBreadcrumb {...defaultProps} />);
    const lastItem = screen.getByText('Reports').closest('button')!;
    expect(lastItem).toHaveAttribute('aria-current', 'page');
  });

  it('does not mark non-last items as current page', () => {
    render(<DriveBreadcrumb {...defaultProps} />);
    const firstItem = screen.getByText('Projects').closest('button')!;
    expect(firstItem).not.toHaveAttribute('aria-current');
  });

  it('renders empty breadcrumb without items', () => {
    render(<DriveBreadcrumb items={[]} onNavigate={vi.fn()} />);
    expect(screen.getByText('Il Mio Drive')).toBeInTheDocument();
  });

  it('applies pointer-events-none to the last item', () => {
    render(<DriveBreadcrumb {...defaultProps} />);
    const lastButton = screen.getByText('Reports').closest('button')!;
    expect(lastButton.className).toContain('pointer-events-none');
  });
});
