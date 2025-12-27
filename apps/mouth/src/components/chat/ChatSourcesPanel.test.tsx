import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatSourcesPanel, ChatSourcesPanelProps } from './ChatSourcesPanel';
import { Source } from '@/types';

describe('ChatSourcesPanel', () => {
  const mockSources: Source[] = [
    {
      id: 1,
      title: 'Test Document 1',
      content: 'This is the full content of document 1',
      snippet: 'This is a snippet',
      collection: 'knowledge_base',
      score: 0.95,
      url: 'https://example.com/doc1',
    },
    {
      id: 2,
      title: 'Test Document 2',
      content: 'Content of document 2',
      collection: 'legal',
      score: 0.82,
    },
  ];

  const defaultProps: ChatSourcesPanelProps = {
    sources: mockSources,
    isOpen: true,
    onClose: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Visibility', () => {
    it('should not render when closed', () => {
      const { container } = render(<ChatSourcesPanel {...defaultProps} isOpen={false} />);
      expect(container.firstChild).toBeNull();
    });

    it('should not render when no sources', () => {
      const { container } = render(<ChatSourcesPanel {...defaultProps} sources={[]} />);
      expect(container.firstChild).toBeNull();
    });

    it('should render when open with sources', () => {
      render(<ChatSourcesPanel {...defaultProps} />);
      expect(screen.getByText('Sources (2)')).toBeInTheDocument();
    });
  });

  describe('Header', () => {
    it('should display correct source count', () => {
      render(<ChatSourcesPanel {...defaultProps} />);
      expect(screen.getByText('Sources (2)')).toBeInTheDocument();
    });

    it('should render close button', () => {
      render(<ChatSourcesPanel {...defaultProps} />);
      expect(screen.getByLabelText('Close sources panel')).toBeInTheDocument();
    });

    it('should call onClose when close button clicked', async () => {
      const user = userEvent.setup();
      render(<ChatSourcesPanel {...defaultProps} />);

      await user.click(screen.getByLabelText('Close sources panel'));
      expect(defaultProps.onClose).toHaveBeenCalledTimes(1);
    });
  });

  describe('Source cards', () => {
    it('should render all sources', () => {
      render(<ChatSourcesPanel {...defaultProps} />);
      expect(screen.getByText('Test Document 1')).toBeInTheDocument();
      expect(screen.getByText('Test Document 2')).toBeInTheDocument();
    });

    it('should display collection name', () => {
      render(<ChatSourcesPanel {...defaultProps} />);
      expect(screen.getByText('knowledge_base')).toBeInTheDocument();
      expect(screen.getByText('legal')).toBeInTheDocument();
    });

    it('should display snippet when available', () => {
      render(<ChatSourcesPanel {...defaultProps} />);
      expect(screen.getByText('This is a snippet')).toBeInTheDocument();
    });

    it('should display content when no snippet', () => {
      render(<ChatSourcesPanel {...defaultProps} />);
      expect(screen.getByText('Content of document 2')).toBeInTheDocument();
    });

    it('should display relevance score', () => {
      render(<ChatSourcesPanel {...defaultProps} />);
      expect(screen.getByText('Relevance: 95%')).toBeInTheDocument();
      expect(screen.getByText('Relevance: 82%')).toBeInTheDocument();
    });
  });

  describe('External links', () => {
    it('should render external link when url provided', () => {
      render(<ChatSourcesPanel {...defaultProps} />);
      const link = screen.getByRole('link', { name: /open/i });
      expect(link).toHaveAttribute('href', 'https://example.com/doc1');
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    });

    it('should not render link when no url', () => {
      const sourcesWithoutUrl: Source[] = [
        { id: 1, title: 'No URL Source', content: 'Content' },
      ];
      render(<ChatSourcesPanel sources={sourcesWithoutUrl} isOpen={true} onClose={vi.fn()} />);

      expect(screen.queryByRole('link')).not.toBeInTheDocument();
    });
  });

  describe('Fallback handling', () => {
    it('should show Untitled Source when no title', () => {
      const sourcesWithoutTitle: Source[] = [
        { id: 1, content: 'Some content' },
      ];
      render(<ChatSourcesPanel sources={sourcesWithoutTitle} isOpen={true} onClose={vi.fn()} />);

      expect(screen.getByText('Untitled Source')).toBeInTheDocument();
    });

    it('should handle undefined score gracefully', () => {
      const sourcesWithoutScore: Source[] = [
        { id: 1, title: 'Test', content: 'Content' },
      ];
      render(<ChatSourcesPanel sources={sourcesWithoutScore} isOpen={true} onClose={vi.fn()} />);

      expect(screen.queryByText(/Relevance:/)).not.toBeInTheDocument();
    });
  });
});
