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
        relative my-6 p-6 rounded-lg border-l-4 border-accent-sand
        bg-gradient-to-r from-[#D4B483]/10 to-transparent
        ${className}
      `}
      data-answer-capsule="true"
    >
      <div className="absolute top-2 right-2 text-xs text-accent-sand/60 uppercase tracking-wider font-medium">
        Quick Answer
      </div>
      <div className="text-lg leading-relaxed text-silver font-medium">
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
  points: string[];
  className?: string;
}

export function KeyTakeaway({ points, className = "" }: KeyTakeawayProps) {
  return (
    <div
      className={`
        my-6 p-6 rounded-lg bg-[#2A3241]/30 border border-accent-sand/20
        ${className}
      `}
      data-key-takeaway="true"
    >
      <h3 className="text-sm uppercase tracking-wider text-accent-sand mb-3 font-semibold">
        Key Takeaways
      </h3>
      <ul className="space-y-2">
        {points.map((point, index) => (
          <li key={index} className="flex items-start gap-3 text-silver">
            <span className="text-accent-sand mt-1">•</span>
            <span>{point}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default AnswerBox;
