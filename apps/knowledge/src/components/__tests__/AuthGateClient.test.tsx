import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import AuthGateClient from '../AuthGateClient';

// Track location.href assignments
const locationAssignSpy = vi.fn();
const originalLocation = window.location;

beforeEach(() => {
  vi.clearAllMocks();
  // Reset cookies
  Object.defineProperty(document, 'cookie', {
    writable: true,
    value: '',
  });

  // Mock window.location
  Object.defineProperty(window, 'location', {
    value: {
      ...originalLocation,
      href: 'https://knowledge.balizero.com/',
      set href(url: string) {
        locationAssignSpy(url);
      },
      get href() {
        return 'https://knowledge.balizero.com/';
      },
    },
    writable: true,
    configurable: true,
  });
});

describe('AuthGateClient', () => {
  it('shows loading state initially when no token', () => {
    render(
      <AuthGateClient>
        <div>Protected content</div>
      </AuthGateClient>
    );
    expect(screen.getByText('Verifying access...')).toBeInTheDocument();
  });

  it('renders children when auth cookie is present', () => {
    Object.defineProperty(document, 'cookie', {
      writable: true,
      value: 'nz_access_token=valid-token-123',
    });

    render(
      <AuthGateClient>
        <div>Protected content</div>
      </AuthGateClient>
    );

    expect(screen.getByText('Protected content')).toBeInTheDocument();
  });

  it("renders header with 'Bali Zero Knowledge' branding", () => {
    Object.defineProperty(document, 'cookie', {
      writable: true,
      value: 'nz_access_token=valid-token',
    });

    render(
      <AuthGateClient>
        <div>Content</div>
      </AuthGateClient>
    );

    expect(screen.getByText('Bali Zero Knowledge')).toBeInTheDocument();
  });

  it('renders back to kita link when authenticated', () => {
    Object.defineProperty(document, 'cookie', {
      writable: true,
      value: 'auth_token=valid-token',
    });

    render(
      <AuthGateClient>
        <div>Content</div>
      </AuthGateClient>
    );

    const backLink = screen.getByText(/Back to Kita/);
    expect(backLink).toBeInTheDocument();
    expect(backLink.closest('a')).toHaveAttribute('href', 'https://kita.balizero.com');
  });

  it('renders app switcher button', () => {
    Object.defineProperty(document, 'cookie', {
      writable: true,
      value: 'token=valid',
    });

    render(
      <AuthGateClient>
        <div>Content</div>
      </AuthGateClient>
    );

    expect(screen.getByLabelText('Cambia applicazione')).toBeInTheDocument();
  });

  it('redirects to login when no token found', () => {
    render(
      <AuthGateClient>
        <div>Protected content</div>
      </AuthGateClient>
    );

    expect(locationAssignSpy).toHaveBeenCalledWith(
      expect.stringContaining('https://kita.balizero.com/login')
    );
  });
});
