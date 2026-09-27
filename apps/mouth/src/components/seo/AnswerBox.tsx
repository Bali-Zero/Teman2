/**
 * AnswerBox Component
 *
 * Displays a concise answer (40-60 words) optimized for AI citations.
 * Place immediately after H1 for maximum AI discoverability.
 *
 * Usage in MDX:
 * <AnswerBox>
 *   Your concise answer here (40-60 words).
 * </AnswerBox>
 */

import React from "react";

interface AnswerBoxProps {
  children: React.ReactNode;
  className?: string;
}

export function AnswerBox({ children, className = "" }: AnswerBoxProps) {
  return (
    <div
      className={`
        relative my-6 p-6 rounded-[8px] border-l-4 border-[var(--r19-copper)]
        bg-[var(--r19-wash)]
        ${className}
      `}
      data-answer-capsule="true"
    >
      <div className="absolute top-2 right-2 text-xs text-[var(--r19-copper)] uppercase tracking-wider font-medium">
        Quick Answer
      </div>
      <div className="text-lg leading-relaxed text-[var(--r19-ink)] font-medium">
        {children}
      </div>
    </div>
  );
}

/**
 * KeyTakeaway Component
 *
 * Bullet-point key takeaways for AI extraction.
 * Use for complex topics that need structured summarization.
 */
interface KeyTakeawayProps {
  points?: string[];
  children?: React.ReactNode;
  className?: string;
}

export function KeyTakeaway({
  points,
  children,
  className = "",
}: KeyTakeawayProps) {
  const hasPoints = Array.isArray(points) && points.length > 0;

  return (
    <div
      className={`
        my-6 p-6 rounded-[8px] bg-[var(--r19-surface)] border border-[var(--r19-line)]
        ${className}
      `}
      data-key-takeaway="true"
    >
      <h3 className="text-sm uppercase tracking-wider text-[var(--r19-copper)] mb-3 font-semibold">
        Key Takeaways
      </h3>
      {hasPoints ? (
        <ul className="space-y-2">
          {points.map((point, index) => (
            <li
              key={index}
              className="flex items-start gap-3 text-[var(--r19-ink)]"
            >
              <span className="text-[var(--r19-copper)] mt-1">•</span>
              <span>{point}</span>
            </li>
          ))}
        </ul>
      ) : (
        <div className="text-[var(--r19-ink)]">{children}</div>
      )}
    </div>
  );
}

export default AnswerBox;
