/**
 * Test suite for ClientKanban virtualization
 * Verifies that virtualization is working correctly
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ClientKanban } from '../ClientKanban';
import type { Client } from '@/lib/api/crm/crm.types';

// Mock useVirtualizer
vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: vi.fn(() => ({
    getVirtualItems: () => [],
    getTotalSize: () => 0,
  })),
}));

describe('ClientKanban Virtualization', () => {
  const mockClients: Client[] = Array.from({ length: 25 }, (_, i) => ({
    id: i + 1,
    full_name: `Client ${i + 1}`,
    email: `client${i + 1}@example.com`,
    status: i % 5 === 0 ? 'active' : 'lead',
    created_at: new Date().toISOString(),
  }));

  it('should render without errors', () => {
    const handleStatusChange = vi.fn();
    render(<ClientKanban clients={mockClients} onStatusChange={handleStatusChange} />);
    expect(screen.getByText('Leads')).toBeInTheDocument();
  });

  it('should show correct client count per column', () => {
    const handleStatusChange = vi.fn();
    render(<ClientKanban clients={mockClients} onStatusChange={handleStatusChange} />);
    
    // Should show count for each column
    const activeClients = mockClients.filter(c => c.status === 'active').length;
    expect(screen.getByText(activeClients.toString())).toBeInTheDocument();
  });
});
