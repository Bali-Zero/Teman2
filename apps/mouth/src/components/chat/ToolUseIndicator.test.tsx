import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ToolUseIndicator } from './ToolUseIndicator';
import { getToolLabel, isKnownTool } from './tool-labels';

describe('ToolUseIndicator', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('renders the running label for a known tool in English', () => {
    render(<ToolUseIndicator toolName="search_emails" status="running" localeOverride="en" />);
    expect(screen.getByRole('status')).toHaveAccessibleName('searching emails');
    expect(screen.getByText('searching emails')).toBeInTheDocument();
  });

  it('renders the done label in Italian', () => {
    render(<ToolUseIndicator toolName="search_emails" status="done" localeOverride="it" />);
    expect(screen.getByText('email controllate')).toBeInTheDocument();
  });

  it('falls back to a generic label for unknown tools', () => {
    render(
      <ToolUseIndicator toolName="some_brand_new_tool" status="running" localeOverride="en" />
    );
    expect(screen.getByText(/running tool: some_brand_new_tool/)).toBeInTheDocument();
  });

  it('reads locale from localStorage when no override is given', () => {
    window.localStorage.setItem('blog-language', 'id');
    render(<ToolUseIndicator toolName="search_emails" status="running" />);
    expect(screen.getByText('mencari email')).toBeInTheDocument();
  });
});

describe('tool-labels helpers', () => {
  it('knows the curated tool list', () => {
    expect(isKnownTool('search_emails')).toBe(true);
    expect(isKnownTool('get_pricing')).toBe(true);
    expect(isKnownTool('not_a_tool')).toBe(false);
  });

  it('getToolLabel returns localised strings for every supported locale', () => {
    const locales = ['en', 'it', 'id', 'fr', 'ru'] as const;
    for (const locale of locales) {
      const usingLabel = getToolLabel('search_emails', locale, 'running');
      const doneLabel = getToolLabel('search_emails', locale, 'done');
      expect(usingLabel).not.toBe('');
      expect(doneLabel).not.toBe('');
      expect(usingLabel).not.toBe(doneLabel);
    }
  });
});
