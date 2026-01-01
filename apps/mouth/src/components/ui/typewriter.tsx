'use client';

import React from 'react';
import { TypeAnimation } from 'react-type-animation';
import { cn } from '@/lib/utils';

interface TypewriterProps {
  /** Array of strings to type, or sequence with delays */
  sequence: (string | number)[];
  /** Speed preset (1-99, lower = faster) */
  speed?: 1 | 10 | 20 | 30 | 40 | 50 | 60 | 70 | 75 | 80 | 90 | 99;
  /** Whether to loop the animation */
  repeat?: number | typeof Infinity;
  /** Custom cursor character */
  cursor?: boolean;
  /** Wrapper element type */
  wrapper?: 'span' | 'div' | 'p' | 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
  /** CSS class name */
  className?: string;
  /** Custom styles */
  style?: React.CSSProperties;
}

/**
 * Typewriter - Animated typing effect
 *
 * Usage:
 * <Typewriter
 *   sequence={[
 *     'Hello World',
 *     1000, // Pause 1 second
 *     'Hello Developer',
 *     1000,
 *   ]}
 *   repeat={Infinity}
 * />
 */
export function Typewriter({
  sequence,
  speed = 50,
  repeat = Infinity,
  cursor = true,
  wrapper = 'span',
  className,
  style,
}: TypewriterProps) {
  return (
    <TypeAnimation
      sequence={sequence}
      speed={speed}
      repeat={repeat}
      cursor={cursor}
      wrapper={wrapper}
      className={cn(className)}
      style={{
        display: 'inline-block',
        ...style,
      }}
    />
  );
}

/**
 * TypewriterHeading - A heading with typewriter effect
 */
interface TypewriterHeadingProps {
  /** Static prefix text */
  prefix?: string;
  /** Array of words to cycle through */
  words: string[];
  /** Pause between words in ms */
  pauseTime?: number;
  /** Heading level */
  as?: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
  /** CSS class name */
  className?: string;
  /** Class for the animated part */
  highlightClassName?: string;
}

export function TypewriterHeading({
  prefix = '',
  words,
  pauseTime = 2000,
  as: Component = 'h1',
  className,
  highlightClassName,
}: TypewriterHeadingProps) {
  // Build sequence: word, pause, word, pause...
  const sequence = words.flatMap((word) => [word, pauseTime]);

  return (
    <Component className={cn(className)}>
      {prefix && <span>{prefix} </span>}
      <span className={cn('text-gradient', highlightClassName)}>
        <Typewriter sequence={sequence} />
      </span>
    </Component>
  );
}

/**
 * TypewriterCode - Typewriter effect styled as code
 */
interface TypewriterCodeProps {
  /** Code to type */
  code: string;
  /** Programming language for styling hint */
  language?: string;
  /** CSS class name */
  className?: string;
}

export function TypewriterCode({
  code,
  language = 'typescript',
  className,
}: TypewriterCodeProps) {
  return (
    <div
      className={cn(
        'rounded-lg bg-[var(--background-secondary)] border border-[var(--border)] p-4 overflow-x-auto',
        className
      )}
    >
      {language && (
        <div className="text-xs text-[var(--foreground-muted)] mb-2 font-mono">
          {language}
        </div>
      )}
      <pre className="font-mono text-sm text-[var(--foreground)]">
        <TypeAnimation
          sequence={[code]}
          speed={40}
          repeat={0}
          cursor={true}
          style={{ display: 'block', whiteSpace: 'pre-wrap' }}
        />
      </pre>
    </div>
  );
}

export default Typewriter;
