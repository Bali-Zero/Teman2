import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { NewMessagesPill } from './NewMessagesPill';

describe('NewMessagesPill', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('renders nothing when show=false', () => {
    render(<NewMessagesPill show={false} unreadCount={2} onClick={() => {}} />);
    expect(screen.queryByTestId('new-messages-pill')).toBeNull();
  });

  it('renders unread count in default locale (en)', () => {
    render(<NewMessagesPill show unreadCount={3} onClick={() => {}} />);
    expect(screen.getByTestId('new-messages-pill')).toBeInTheDocument();
    expect(screen.getByText(/3 new messages/i)).toBeInTheDocument();
  });

  it('uses singular form for one message in english', () => {
    render(<NewMessagesPill show unreadCount={1} onClick={() => {}} />);
    expect(screen.getByText(/^1 new message$/i)).toBeInTheDocument();
  });

  it('falls back to a default label when count is zero', () => {
    render(<NewMessagesPill show unreadCount={0} onClick={() => {}} />);
    expect(screen.getByText(/jump to latest/i)).toBeInTheDocument();
  });

  it('respects italian locale from localStorage', () => {
    window.localStorage.setItem('blog-language', 'it');
    render(<NewMessagesPill show unreadCount={2} onClick={() => {}} />);
    expect(screen.getByText(/2 nuovi messaggi/i)).toBeInTheDocument();
  });

  it('calls onClick when pressed', () => {
    const onClick = vi.fn();
    render(<NewMessagesPill show unreadCount={1} onClick={onClick} />);
    fireEvent.click(screen.getByTestId('new-messages-pill'));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
