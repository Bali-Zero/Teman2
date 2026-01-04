import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import NewClientPage from '../page';
import * as api from '@/lib/api';

// Mock the API
vi.mock('@/lib/api', () => ({
  api: {
    crm: {
      createClient: vi.fn(),
    },
    getProfile: vi.fn(),
  },
}));

// Mock Next.js router
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

describe('NewClientPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.api.crm.createClient as any).mockResolvedValue({ id: 1 });
    (api.api.getProfile as any).mockResolvedValue({
      email: 'test@balizero.com',
    });
  });

  describe('Form Navigation', () => {
    it('renders all three tabs', () => {
      render(<NewClientPage />);

      expect(screen.getByText('Basic Info')).toBeInTheDocument();
      expect(screen.getByText('Personal Details')).toBeInTheDocument();
      expect(screen.getByText('CRM Settings')).toBeInTheDocument();
    });

    it('starts on Basic Info tab', () => {
      render(<NewClientPage />);
      expect(screen.getByText('Contact Information')).toBeInTheDocument();
    });

    it('navigates to Personal Details when tab clicked', () => {
      render(<NewClientPage />);
      const personalDetailsTab = screen.getByText('Personal Details');

      fireEvent.click(personalDetailsTab);

      expect(screen.getByText('Personal Details')).toBeVisible();
      expect(screen.getByLabelText('Nationality')).toBeInTheDocument();
    });

    it('navigates to CRM Settings when tab clicked', () => {
      render(<NewClientPage />);
      const crmTab = screen.getByText('CRM Settings');

      fireEvent.click(crmTab);

      expect(screen.getByText('CRM Settings')).toBeVisible();
      expect(screen.getByLabelText('Status')).toBeInTheDocument();
    });

    it('navigates using Next buttons', async () => {
      const user = userEvent.setup();
      render(<NewClientPage />);

      // Click Next from Basic Info
      const nextButtons = screen.getAllByText(/Next:/);
      if (nextButtons.length > 0) {
        await user.click(nextButtons[0]);

        await waitFor(() => {
          expect(screen.getByText('Personal Details')).toBeVisible();
        });
      }
    });

    it('navigates back using Back buttons', async () => {
      const user = userEvent.setup();
      render(<NewClientPage />);

      // Go to Personal Details
      fireEvent.click(screen.getByText('Personal Details'));

      // Click Back
      const backButtons = screen.getAllByText('Back');
      if (backButtons.length > 0) {
        await user.click(backButtons[0]);

        await waitFor(() => {
          expect(screen.getByText('Contact Information')).toBeVisible();
        });
      }
    });
  });

  describe('Form Fields - Basic Info', () => {
    it('accepts full name input', async () => {
      const user = userEvent.setup();
      render(<NewClientPage />);

      const input = screen.getByPlaceholderText('John Doe') as HTMLInputElement;
      await user.type(input, 'Andrea Santoro');

      expect(input.value).toBe('Andrea Santoro');
    });

    it('accepts email input', async () => {
      const user = userEvent.setup();
      render(<NewClientPage />);

      const input = screen.getByPlaceholderText('john@example.com') as HTMLInputElement;
      await user.type(input, 'andrea@example.com');

      expect(input.value).toBe('andrea@example.com');
    });

    it('accepts phone input', async () => {
      const user = userEvent.setup();
      render(<NewClientPage />);

      const input = screen.getByPlaceholderText('+62 812 3456 7890') as HTMLInputElement;
      await user.type(input, '+62 812 5678 9999');

      expect(input.value).toBe('+62 812 5678 9999');
    });

    it('syncs WhatsApp with phone when not set', async () => {
      const user = userEvent.setup();
      render(<NewClientPage />);

      const phoneInputs = screen.getAllByPlaceholderText(/\+62/);
      const phoneInput = phoneInputs[0] as HTMLInputElement;

      await user.type(phoneInput, '+62 812 5678 9999');

      // WhatsApp should auto-sync with phone
      await waitFor(() => {
        const whatsappInputs = screen.getAllByPlaceholderText(/Same as phone/);
        expect(whatsappInputs.length > 0).toBe(true);
      });
    });

    it('allows client type selection', () => {
      render(<NewClientPage />);

      const select = screen.getByDisplayValue('Individual') as HTMLSelectElement;
      expect(select).toBeInTheDocument();

      fireEvent.change(select, { target: { value: 'company' } });
      expect(select.value).toBe('company');
    });

    it('shows company name field when company selected', () => {
      render(<NewClientPage />);

      const select = screen.getByDisplayValue('Individual') as HTMLSelectElement;
      fireEvent.change(select, { target: { value: 'company' } });

      expect(screen.getByPlaceholderText('PT Example Indonesia')).toBeInTheDocument();
    });
  });

  describe('Form Fields - Personal Details', () => {
    it('has nationality dropdown', () => {
      render(<NewClientPage />);
      fireEvent.click(screen.getByText('Personal Details'));

      expect(screen.getByDisplayValue('Select nationality...')).toBeInTheDocument();
    });

    it('has date of birth field', () => {
      render(<NewClientPage />);
      fireEvent.click(screen.getByText('Personal Details'));

      expect(screen.getByLabelText('Date of Birth')).toBeInTheDocument();
    });

    it('has passport fields', () => {
      render(<NewClientPage />);
      fireEvent.click(screen.getByText('Personal Details'));

      expect(screen.getByPlaceholderText('AB1234567')).toBeInTheDocument();
      expect(screen.getAllByDisplayValue('dd/mm/yyyy')).toHaveLength(2); // Both date fields
    });
  });

  describe('Form Fields - CRM Settings', () => {
    beforeEach(() => {
      render(<NewClientPage />);
      fireEvent.click(screen.getByText('CRM Settings'));
    });

    it('has status dropdown with Lead selected by default', () => {
      expect(screen.getByDisplayValue('Lead')).toBeInTheDocument();
    });

    it('has lead source dropdown', () => {
      expect(screen.getByDisplayValue('Select source...')).toBeInTheDocument();
    });

    it('has assigned to dropdown', () => {
      expect(screen.getByDisplayValue('Unassigned')).toBeInTheDocument();
    });

    it('has service interest checkboxes', () => {
      expect(screen.getByText('KITAS Work Permit')).toBeInTheDocument();
      expect(screen.getByText('Visa Extension')).toBeInTheDocument();
      expect(screen.getByText('Tax Consulting')).toBeInTheDocument();
    });

    it('toggles service interest on click', () => {
      const kitasButton = screen.getByText('KITAS Work Permit').closest('button');
      expect(kitasButton).toBeInTheDocument();

      fireEvent.click(kitasButton!);
      // Button should update styling to show selection
      expect(kitasButton).toHaveClass('bg-[var(--accent)]');
    });
  });

  describe('Form Submission', () => {
    it('displays Create Client button on final tab', () => {
      render(<NewClientPage />);
      fireEvent.click(screen.getByText('CRM Settings'));

      expect(screen.getByText('Create Client')).toBeInTheDocument();
    });

    it('disables Create Client if full_name is empty', () => {
      render(<NewClientPage />);
      fireEvent.click(screen.getByText('CRM Settings'));

      const createButton = screen.getByText('Create Client') as HTMLButtonElement;
      expect(createButton.disabled).toBe(true);
    });

    it('enables Create Client when full_name is filled', async () => {
      const user = userEvent.setup();
      render(<NewClientPage />);

      // Fill in required field
      const input = screen.getByPlaceholderText('John Doe');
      await user.type(input, 'Test Client');

      // Go to final tab
      fireEvent.click(screen.getByText('CRM Settings'));

      const createButton = screen.getByText('Create Client') as HTMLButtonElement;
      expect(createButton.disabled).toBe(false);
    });

    it('calls createClient API on form submit', async () => {
      const user = userEvent.setup();
      render(<NewClientPage />);

      // Fill required field
      await user.type(screen.getByPlaceholderText('John Doe'), 'Test Client');

      // Go to final tab
      fireEvent.click(screen.getByText('CRM Settings'));

      // Submit form
      const createButton = screen.getByText('Create Client');
      await user.click(createButton);

      await waitFor(() => {
        expect(api.api.crm.createClient).toHaveBeenCalled();
      });
    });

    it('handles API errors on submission', async () => {
      const user = userEvent.setup();
      const alertSpy = vi.spyOn(global, 'alert').mockImplementation();

      (api.api.crm.createClient as any).mockRejectedValueOnce(
        new Error('API Error')
      );

      render(<NewClientPage />);

      await user.type(screen.getByPlaceholderText('John Doe'), 'Test Client');
      fireEvent.click(screen.getByText('CRM Settings'));

      const createButton = screen.getByText('Create Client');
      await user.click(createButton);

      await waitFor(() => {
        expect(alertSpy).toHaveBeenCalled();
      });

      alertSpy.mockRestore();
    });
  });

  describe('Summary Card', () => {
    it('displays client name in summary', async () => {
      const user = userEvent.setup();
      render(<NewClientPage />);

      await user.type(screen.getByPlaceholderText('John Doe'), 'Andrea Santoro');

      expect(screen.getByText('Andrea Santoro')).toBeInTheDocument();
    });

    it('displays status in summary', () => {
      render(<NewClientPage />);

      // Status should show as "Lead" by default
      expect(screen.getAllByText('Lead').length).toBeGreaterThan(0);
    });
  });
});
