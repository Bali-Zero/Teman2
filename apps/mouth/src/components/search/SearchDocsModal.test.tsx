import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SearchDocsModal } from './SearchDocsModal';

const mockSearchDocs = vi.fn();
const mockIsAuthenticated = vi.fn();
const mockIsAdmin = vi.fn();

vi.mock('@/lib/api', () => ({
  api: {
    searchDocs: (...args: unknown[]) => mockSearchDocs(...args),
    isAuthenticated: () => mockIsAuthenticated(),
    isAdmin: () => mockIsAdmin(),
  },
}));

describe('SearchDocsModal', () => {
  const onInsert = vi.fn();
  const onClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockIsAuthenticated.mockReturnValue(true);
    mockIsAdmin.mockReturnValue(false);
  });

  function baseResult() {
    return {
      text: 'Example excerpt text that should appear in the result list.',
      metadata: {
        book_title: 'Visa Handbook',
        book_author: 'Jane Doe',
        tier: 'A',
        min_level: 1,
        chunk_index: 0,
        page_number: 12,
        topics: ['visa', 'renewal'],
        file_path: '/docs/visa.pdf',
        total_chunks: 1,
      },
      similarity_score: 0.72,
    };
  }

  const buildResult = (overrides?: Partial<ReturnType<typeof baseResult>>) => ({
    ...baseResult(),
    ...overrides,
  });

  it('requires authentication before performing search', async () => {
    const user = userEvent.setup();
    mockIsAuthenticated.mockReturnValue(false);

    render(<SearchDocsModal open onClose={onClose} onInsert={onInsert} initialQuery="kitas" />);

    await user.click(screen.getByRole('button', { name: /search/i }));

    await waitFor(() => {
      expect(mockSearchDocs).not.toHaveBeenCalled();
      expect(screen.getByText(/Authentication required/i)).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /login/i })).toBeInTheDocument();
  });

  it('shows results and allows inserting selected sources', async () => {
    const user = userEvent.setup();
    mockSearchDocs.mockResolvedValue({
      results: [buildResult()],
      total_found: 1,
      execution_time_ms: 14,
      user_level: 1,
    });

    render(<SearchDocsModal open onClose={onClose} onInsert={onInsert} initialQuery="kitas" />);

    await user.click(screen.getByRole('button', { name: /search/i }));

    await screen.findByText('Visa Handbook');

    const insertSelectedButton = screen.getByRole('button', { name: /insert selected/i });
    expect(insertSelectedButton).toBeDisabled();

    await user.click(screen.getByLabelText(/Select result 1/i));

    expect(insertSelectedButton).toBeEnabled();

    await user.click(insertSelectedButton);

    expect(onInsert).toHaveBeenCalledTimes(1);
    expect(onInsert).toHaveBeenCalledWith(expect.stringContaining('Use these sources'));
    expect(onClose).toHaveBeenCalled();
  });

  it('displays empty state when no results are returned and clears selection', async () => {
    const user = userEvent.setup();
    mockSearchDocs
      .mockResolvedValueOnce({
        results: [buildResult()],
        total_found: 1,
        execution_time_ms: 10,
        user_level: 1,
      })
      .mockResolvedValueOnce({
        results: [],
        total_found: 0,
        execution_time_ms: 5,
        user_level: 1,
      });

    render(<SearchDocsModal open onClose={onClose} onInsert={onInsert} initialQuery="first" />);

    await user.click(screen.getByRole('button', { name: /search/i }));
    await screen.findByText('Visa Handbook');
    await user.click(screen.getByLabelText(/Select result 1/i));

    const queryInput = screen.getByPlaceholderText(/Search the knowledge base/i);
    await user.clear(queryInput);
    await user.type(queryInput, 'second');

    await user.click(screen.getByRole('button', { name: /search/i }));

    await waitFor(() => {
      expect(mockSearchDocs).toHaveBeenCalledTimes(2);
    });

    expect(await screen.findByText(/No results found for this query/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /insert selected/i })).toBeDisabled();
  });
});
