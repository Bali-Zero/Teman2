import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { CitationPopover } from './CitationPopover';
import type { Source } from '@/types';

const SOURCE: Source = {
  title: 'Indonesian Visa Rules',
  content:
    'Holders of a C1 visa may stay up to 60 days and renew twice for a total of 180 days. Source: Permenkumham 22/2023.',
  url: 'https://example.org/visa',
};

const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

describe('CitationPopover', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });

  it('opens on hover after delay and shows preview text', async () => {
    render(
      <CitationPopover source={SOURCE}>
        <button>Source 1</button>
      </CitationPopover>
    );

    const trigger = screen.getByText('Source 1').parentElement!;
    fireEvent.mouseEnter(trigger);
    expect(screen.queryByTestId('citation-popover')).toBeNull();

    await act(async () => {
      await wait(320);
    });

    expect(screen.getByTestId('citation-popover')).toBeInTheDocument();
    expect(screen.getByText(/Holders of a C1 visa/)).toBeInTheDocument();
  });

  it('opens on focus for keyboard accessibility', async () => {
    render(
      <CitationPopover source={SOURCE}>
        <button>Source 1</button>
      </CitationPopover>
    );

    const trigger = screen.getByText('Source 1').parentElement!;
    fireEvent.focus(trigger);
    await act(async () => {
      await wait(320);
    });
    expect(screen.getByTestId('citation-popover')).toBeInTheDocument();
  });

  it('closes on Escape', async () => {
    render(
      <CitationPopover source={SOURCE}>
        <button>Source 1</button>
      </CitationPopover>
    );

    const trigger = screen.getByText('Source 1').parentElement!;
    fireEvent.mouseEnter(trigger);
    await act(async () => {
      await wait(320);
    });
    expect(screen.getByTestId('citation-popover')).toBeInTheDocument();

    await act(async () => {
      fireEvent.keyDown(window, { key: 'Escape' });
      await wait(20);
    });

    expect(screen.queryByTestId('citation-popover')).toBeNull();
  });

  it('renders nothing when disabled', async () => {
    render(
      <CitationPopover source={SOURCE} disabled>
        <button>Source 1</button>
      </CitationPopover>
    );
    fireEvent.mouseEnter(screen.getByText('Source 1'));
    await act(async () => {
      await wait(320);
    });
    expect(screen.queryByTestId('citation-popover')).toBeNull();
  });

  it('truncates long content with ellipsis', async () => {
    const longSource: Source = {
      title: 'Long',
      content: 'lorem ipsum '.repeat(100),
    };
    render(
      <CitationPopover source={longSource}>
        <button>Long Source</button>
      </CitationPopover>
    );
    const trigger = screen.getByText('Long Source').parentElement!;
    fireEvent.mouseEnter(trigger);
    await act(async () => {
      await wait(320);
    });
    const node = screen.getByTestId('citation-popover');
    expect(node.textContent ?? '').toMatch(/…/);
  });
});
