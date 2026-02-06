/**
 * Unit tests for KBLIInspector component and helper functions
 *
 * Tests cover:
 * - Loading state rendering
 * - Empty state rendering
 * - Data rendering with all fields
 * - getPmaBadge helper (all statuses)
 * - getRiskBadge helper (all levels)
 * - getRiskLevel helper
 * - Related codes click handler
 * - Mobile close button
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import KBLIInspector, { getPmaBadge, getRiskBadge, getRiskLevel } from '../KBLIInspector';
import type { KBLIDetail } from '@/lib/api/kbli.api';

const mockData: KBLIDetail = {
  code: '56101',
  title: 'Restoran',
  description: 'Usaha penyediaan makanan dan minuman',
  pma_status: 'TERBUKA',
  licensing_status: 'Perizinan Berusaha',
  sector: 'Akomodasi dan Makan Minum',
  risk_profile: 'Menengah Rendah',
  licenses: [
    {
      type: 'NIB',
      scale: ['Mikro', 'Kecil'],
      risk_level: 'Rendah',
      sla: '1 hari',
      requirements: ['KTP', 'NPWP'],
    },
    {
      type: 'Sertifikat Laik Hygiene',
      scale: ['Menengah', 'Besar'],
      risk_level: 'Menengah',
      sla: '14 hari',
      requirements: ['Inspeksi lokasi', 'Dokumen sanitasi'],
    },
  ],
  related_codes: ['56102', '56103'],
};

describe('KBLIInspector', () => {
  it('should render loading state', () => {
    render(<KBLIInspector data={null} isLoading={true} />);
    expect(screen.getByText('Loading details...')).toBeTruthy();
  });

  it('should render empty state when no data', () => {
    render(<KBLIInspector data={null} isLoading={false} />);
    expect(screen.getByText('Click on any result to see full details')).toBeTruthy();
  });

  it('should render KBLI code badge', () => {
    render(<KBLIInspector data={mockData} isLoading={false} />);
    expect(screen.getByText('KBLI 56101')).toBeTruthy();
  });

  it('should render title', () => {
    render(<KBLIInspector data={mockData} isLoading={false} />);
    expect(screen.getByText('Restoran')).toBeTruthy();
  });

  it('should render PMA badge', () => {
    render(<KBLIInspector data={mockData} isLoading={false} />);
    expect(screen.getByText('Open to Foreign Investment')).toBeTruthy();
  });

  it('should render description', () => {
    render(<KBLIInspector data={mockData} isLoading={false} />);
    expect(screen.getByText(/Usaha penyediaan makanan/)).toBeTruthy();
  });

  it('should render licenses', () => {
    render(<KBLIInspector data={mockData} isLoading={false} />);
    expect(screen.getByText('NIB')).toBeTruthy();
    expect(screen.getByText('Sertifikat Laik Hygiene')).toBeTruthy();
  });

  it('should render related codes', () => {
    render(<KBLIInspector data={mockData} isLoading={false} />);
    expect(screen.getByText('56102')).toBeTruthy();
    expect(screen.getByText('56103')).toBeTruthy();
  });

  it('should render sector', () => {
    render(<KBLIInspector data={mockData} isLoading={false} />);
    expect(screen.getByText(/Akomodasi dan Makan Minum/)).toBeTruthy();
  });

  it('should call onInspect when related code is clicked', () => {
    const onInspect = vi.fn();
    render(<KBLIInspector data={mockData} isLoading={false} onInspect={onInspect} />);

    fireEvent.click(screen.getByText('56102'));
    expect(onInspect).toHaveBeenCalledWith('56102');
  });

  it('should render close button on mobile when onClose is provided', () => {
    const onClose = vi.fn();
    const { container } = render(<KBLIInspector data={mockData} isLoading={false} onClose={onClose} />);

    // Should have the drag handle
    const dragHandle = container.querySelector('.bg-white\\/20');
    expect(dragHandle).toBeTruthy();
  });

  it('should render license requirements', () => {
    render(<KBLIInspector data={mockData} isLoading={false} />);
    expect(screen.getByText(/KTP/)).toBeTruthy();
  });
});

describe('getPmaBadge', () => {
  it('should return success badge for TERBUKA', () => {
    const badge = getPmaBadge('TERBUKA');
    expect(badge.label).toBe('Open to Foreign Investment');
    expect(badge.className).toContain('success');
  });

  it('should return warning badge for TERBATAS', () => {
    const badge = getPmaBadge('TERBATAS');
    expect(badge.label).toBe('Restricted - Conditions Apply');
    expect(badge.className).toContain('warning');
  });

  it('should return error badge for TERTUTUP', () => {
    const badge = getPmaBadge('TERTUTUP');
    expect(badge.label).toBe('Closed to Foreign Investment');
    expect(badge.className).toContain('error');
  });

  it('should return neutral badge for unknown status', () => {
    const badge = getPmaBadge('UNKNOWN');
    expect(badge.label).toBe('Status Unknown');
    expect(badge.className).toContain('neutral');
  });

  it('should be case-insensitive', () => {
    const badge = getPmaBadge('terbuka');
    expect(badge.label).toBe('Open to Foreign Investment');
  });

  it('should handle empty string', () => {
    const badge = getPmaBadge('');
    expect(badge.label).toBe('Status Unknown');
  });
});

describe('getRiskBadge', () => {
  it('should return info badge for low risk', () => {
    const badge = getRiskBadge('Rendah');
    expect(badge.label).toBe('Low Risk');
    expect(badge.className).toContain('info');
  });

  it('should return warning badge for medium risk', () => {
    const badge = getRiskBadge('Menengah');
    expect(badge.label).toBe('Medium Risk');
    expect(badge.className).toContain('warning');
  });

  it('should return error badge for high risk', () => {
    const badge = getRiskBadge('Tinggi');
    expect(badge.label).toBe('High Risk');
    expect(badge.className).toContain('error');
  });

  it('should detect medium-low risk', () => {
    const badge = getRiskBadge('Menengah Rendah');
    expect(badge.label).toBe('Medium-Low Risk');
  });

  it('should detect medium-high risk', () => {
    const badge = getRiskBadge('Menengah Tinggi');
    expect(badge.label).toBe('Medium-High Risk');
  });

  it('should handle English values', () => {
    expect(getRiskBadge('low').label).toBe('Low Risk');
    expect(getRiskBadge('medium').label).toBe('Medium Risk');
    expect(getRiskBadge('high').label).toBe('High Risk');
  });
});

describe('getRiskLevel', () => {
  it('should return correct levels', () => {
    expect(getRiskLevel('Rendah')).toBe('low');
    expect(getRiskLevel('Menengah Rendah')).toBe('medium-low');
    expect(getRiskLevel('Menengah')).toBe('medium');
    expect(getRiskLevel('Menengah Tinggi')).toBe('medium-high');
    expect(getRiskLevel('Tinggi')).toBe('high');
  });

  it('should default to low for unknown', () => {
    expect(getRiskLevel('')).toBe('low');
    expect(getRiskLevel('Unknown')).toBe('low');
  });
});
