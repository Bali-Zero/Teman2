```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import Layout from './layout';

// Mocking external dependencies
vi.mock('@/components/Navbar', () => () => <div data-testid="navbar" />);
vi.mock('@/components/Footer', () => () => <div data-testid="footer" />);
vi.mock('@/lib/api', () => ({
  getBlogPosts: vi.fn(),
}));

describe('Layout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render correctly with default props', () => {
    render(<Layout />);
    expect(screen.getByTestId('navbar')).toBeInTheDocument();
    expect(screen.getByTestId('footer')).toBeInTheDocument();
  });

  it('should fetch blog posts on mount', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockResolvedValue([{ title: 'Test Post' }]);

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Test Post')).toBeInTheDocument();
    });
  });

  it('should handle error case when fetching blog posts', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockRejectedValue(new Error('API Error'));

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Error: API Error')).toBeInTheDocument();
    });
  });

  it('should display loading state when fetching blog posts', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockResolvedValue([]);

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });
  });

  it('should display empty state when no blog posts are fetched', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockResolvedValue([]);

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('No blog posts available')).toBeInTheDocument();
    });
  });

  it('should handle empty array of blog posts', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockResolvedValue([]);

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('No blog posts available')).toBeInTheDocument();
    });
  });

  it('should handle undefined blog posts', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockResolvedValue(undefined);

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Error: API Error')).toBeInTheDocument();
    });
  });

  it('should handle null blog posts', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockResolvedValue(null);

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Error: API Error')).toBeInTheDocument();
    });
  });

  it('should handle empty object of blog posts', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockResolvedValue({});

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('No blog posts available')).toBeInTheDocument();
    });
  });

  it('should handle undefined loading state', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockResolvedValue([{ title: 'Test Post' }]);

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Test Post')).toBeInTheDocument();
    });
  });

  it('should handle null loading state', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockResolvedValue([{ title: 'Test Post' }]);

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Test Post')).toBeInTheDocument();
    });
  });

  it('should handle empty loading state', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockResolvedValue([{ title: 'Test Post' }]);

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Test Post')).toBeInTheDocument();
    });
  });

  it('should handle empty string loading state', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockResolvedValue([{ title: 'Test Post' }]);

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Test Post')).toBeInTheDocument();
    });
  });

  it('should handle empty array of blog posts with loading state', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockResolvedValue([]);

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });
  });

  it('should handle empty object of blog posts with loading state', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockResolvedValue({});

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });
  });

  it('should handle null blog posts with loading state', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockResolvedValue(null);

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });
  });

  it('should handle undefined blog posts with loading state', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockResolvedValue(undefined);

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });
  });

  it('should handle empty string blog posts with loading state', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockResolvedValue('');

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });
  });

  it('should handle empty array of blog posts with error state', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockRejectedValue(new Error('API Error'));

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Error: API Error')).toBeInTheDocument();
    });
  });

  it('should handle empty object of blog posts with error state', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockRejectedValue(new Error('API Error'));

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Error: API Error')).toBeInTheDocument();
    });
  });

  it('should handle null blog posts with error state', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockRejectedValue(new Error('API Error'));

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Error: API Error')).toBeInTheDocument();
    });
  });

  it('should handle undefined blog posts with error state', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockRejectedValue(new Error('API Error'));

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Error: API Error')).toBeInTheDocument();
    });
  });

  it('should handle empty string blog posts with error state', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockRejectedValue(new Error('API Error'));

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Error: API Error')).toBeInTheDocument();
    });
  });

  it('should handle empty array of blog posts with success state', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockResolvedValue([{ title: 'Test Post' }]);

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Test Post')).toBeInTheDocument();
    });
  });

  it('should handle empty object of blog posts with success state', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockResolvedValue([{ title: 'Test Post' }]);

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Test Post')).toBeInTheDocument();
    });
  });

  it('should handle null blog posts with success state', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockResolvedValue(null);

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });
  });

  it('should handle undefined blog posts with success state', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockResolvedValue(undefined);

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });
  });

  it('should handle empty string blog posts with success state', async () => {
    const getBlogPostsMock = vi.mocked(getBlogPosts);
    getBlogPostsMock.mockResolvedValue('');

    render(<Layout />);

    await waitFor(() => {
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });
  });