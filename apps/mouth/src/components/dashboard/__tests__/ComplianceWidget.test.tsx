import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ComplianceWidget } from '../ComplianceWidget';
import { ComplianceAlert } from '@/types/compliance';

const mockAlerts: ComplianceAlert[] = [
  {
    alert_id: '1',
    compliance_item_id: 'item-1',
    client_id: 'client-1',
    severity: 'critical',
    title: 'Visa Expiry',
    message: 'Your visa is about to expire',
    deadline: new Date().toISOString(),
    days_until_deadline: 5,
    action_required: 'Renew now',
    status: 'pending',
    created_at: new Date().toISOString(),
  },
];

describe('ComplianceWidget', () => {
  it('renders correctly and has accessibility attributes', () => {
    // Pass onDismiss to ensure dismiss buttons are rendered
    const onDismiss = vi.fn();
    render(<ComplianceWidget alerts={mockAlerts} onDismiss={onDismiss} />);

    const bellButton = screen.getByRole('button', { name: /view compliance alerts/i });
    expect(bellButton).toBeInTheDocument();
    expect(bellButton).toHaveAttribute('aria-haspopup', 'true');
    expect(bellButton).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(bellButton);
    expect(bellButton).toHaveAttribute('aria-expanded', 'true');

    const dashboardButton = screen.getByRole('button', { name: /view compliance dashboard/i });
    expect(dashboardButton).toBeInTheDocument();

    const dismissButton = screen.getByRole('button', { name: /dismiss alert: visa expiry/i });
    expect(dismissButton).toBeInTheDocument();
  });

  it('calls onDismiss when dismiss button is clicked', () => {
    const onDismiss = vi.fn();
    render(<ComplianceWidget alerts={mockAlerts} onDismiss={onDismiss} />);

    const bellButton = screen.getByRole('button', { name: /view compliance alerts/i });
    fireEvent.click(bellButton);

    const dismissButton = screen.getByRole('button', { name: /dismiss alert: visa expiry/i });
    fireEvent.click(dismissButton);

    expect(onDismiss).toHaveBeenCalledWith('1');
  });
});
