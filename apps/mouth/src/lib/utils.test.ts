import { describe, it, expect } from 'vitest';
import { cn, formatMessageTime } from './utils';

describe('utils', () => {
  describe('cn', () => {
    it('should merge class names', () => {
      expect(cn('foo', 'bar')).toBe('foo bar');
    });

    it('should handle conditional classes', () => {
      expect(cn('foo', false && 'bar', 'baz')).toBe('foo baz');
      expect(cn('foo', true && 'bar', 'baz')).toBe('foo bar baz');
    });

    it('should handle null and undefined', () => {
      expect(cn('foo', null, undefined, 'bar')).toBe('foo bar');
    });

    it('should merge tailwind classes correctly', () => {
      expect(cn('px-2 py-1', 'px-4')).toBe('py-1 px-4');
    });

    it('should handle arrays', () => {
      expect(cn(['foo', 'bar'], 'baz')).toBe('foo bar baz');
    });

    it('should handle objects', () => {
      expect(cn({ foo: true, bar: false, baz: true })).toBe('foo baz');
    });

    it('should handle empty inputs', () => {
      expect(cn()).toBe('');
      expect(cn('')).toBe('');
    });

    it('should handle mixed inputs', () => {
      expect(cn('foo', ['bar'], { baz: true }, 'qux')).toBe('foo bar baz qux');
    });
  });

  describe('formatMessageTime', () => {
    it('should format date correctly', () => {
      const date = new Date('2024-01-15T14:30:00');
      const formatted = formatMessageTime(date);
      expect(formatted).toMatch(/\d{1,2}:\d{2}\s?(AM|PM)/);
    });

    it('should format morning time', () => {
      const date = new Date('2024-01-15T09:15:00');
      const formatted = formatMessageTime(date);
      expect(formatted).toContain('AM');
    });

    it('should format afternoon time', () => {
      const date = new Date('2024-01-15T15:45:00');
      const formatted = formatMessageTime(date);
      expect(formatted).toContain('PM');
    });

    it('should format midnight', () => {
      const date = new Date('2024-01-15T00:00:00');
      const formatted = formatMessageTime(date);
      expect(formatted).toBeTruthy();
    });

    it('should format noon', () => {
      const date = new Date('2024-01-15T12:00:00');
      const formatted = formatMessageTime(date);
      expect(formatted).toBeTruthy();
    });

    it('should handle different dates', () => {
      const date1 = new Date('2024-01-15T10:30:00');
      const date2 = new Date('2024-01-15T22:30:00');
      const formatted1 = formatMessageTime(date1);
      const formatted2 = formatMessageTime(date2);
      expect(formatted1).not.toBe(formatted2);
    });
  });
});
