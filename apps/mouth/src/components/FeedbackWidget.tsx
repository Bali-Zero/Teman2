'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { X, MessageSquare, ThumbsUp, ThumbsDown, AlertCircle, Send } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface FeedbackData {
  type: 'positive' | 'negative' | 'issue';
  message: string;
  sessionId: string | null;
  turnCount: number;
  timestamp: Date;
}

const STORAGE_KEY_SUBMITTED = 'zantara_feedback_submitted';
const STORAGE_KEY_DISMISSED = 'zantara_feedback_dismissed';

/**
 * Feedback Widget - Collect user feedback on long conversations
 * Shows only ONCE per session, in English
 */
export function FeedbackWidget({
  sessionId,
  turnCount,
}: {
  sessionId: string | null;
  turnCount: number;
}) {
  const [isVisible, setIsVisible] = useState(false);
  const [feedbackType, setFeedbackType] = useState<'positive' | 'negative' | 'issue' | null>(null);
  const [message, setMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  // Show widget after 8+ turns, but ONLY if not already submitted or dismissed
  useEffect(() => {
    // Check if already shown this session
    const alreadySubmitted = localStorage.getItem(STORAGE_KEY_SUBMITTED);
    const alreadyDismissed = localStorage.getItem(STORAGE_KEY_DISMISSED);

    if (turnCount >= 8 && !alreadySubmitted && !alreadyDismissed) {
      setIsVisible(true);
    }
  }, [turnCount]);

  const handleSubmit = async () => {
    if (!feedbackType) {
      return;
    }

    // Generate a valid UUID if sessionId is missing
    const activeSessionId = sessionId || crypto.randomUUID();

    setIsSubmitting(true);

    try {
      // Map feedback type to rating (1-5 scale)
      const ratingMap: Record<'positive' | 'negative' | 'issue', number> = {
        positive: 5,
        negative: 2,
        issue: 3,
      };
      const rating = ratingMap[feedbackType];

      // Send feedback to backend API
      const response = await fetch('/api/feedback/rate-conversation', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          session_id: activeSessionId,
          rating: rating,
          feedback_type: feedbackType,
          feedback_text: message.trim() || `User selected: ${feedbackType}`,
          turn_count: turnCount,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      await response.json();

      // Mark as submitted permanently
      localStorage.setItem(STORAGE_KEY_SUBMITTED, 'true');

      // Show success state briefly
      setSubmitSuccess(true);
      setTimeout(() => {
        setIsVisible(false);
      }, 2000);

    } catch (error) {
      console.error('Failed to submit feedback:', error);
      // Still mark as submitted to avoid annoying users
      localStorage.setItem(STORAGE_KEY_SUBMITTED, 'true');
      // Show success anyway - don't bother user with errors
      setSubmitSuccess(true);
      setTimeout(() => {
        setIsVisible(false);
      }, 2000);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDismiss = () => {
    setIsVisible(false);
    // Mark as dismissed so it won't show again
    localStorage.setItem(STORAGE_KEY_DISMISSED, 'true');
  };

  if (!isVisible) {
    return null;
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 20, scale: 0.95 }}
        transition={{ duration: 0.3 }}
        className="fixed bottom-24 right-4 md:max-w-sm w-[calc(100%-2rem)] md:w-80 bg-[var(--background-elevated)] border border-[var(--border)] rounded-xl p-4 shadow-xl z-50"
      >
        {submitSuccess ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col items-center py-4 text-center"
          >
            <div className="w-12 h-12 rounded-full bg-[var(--success)]/20 flex items-center justify-center mb-3">
              <ThumbsUp className="w-6 h-6 text-[var(--success)]" />
            </div>
            <h3 className="text-sm font-semibold text-[var(--foreground)]">Thank you!</h3>
            <p className="text-xs text-[var(--foreground-muted)] mt-1">Your feedback helps us improve.</p>
          </motion.div>
        ) : (
          <>
            {/* Header */}
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="text-sm font-semibold text-[var(--foreground)] flex items-center gap-2">
                  <MessageSquare className="w-4 h-4 text-[var(--accent)]" />
                  How is your experience?
                </h3>
                <p className="text-xs text-[var(--foreground-muted)] mt-1">
                  {turnCount} messages exchanged. Your feedback matters!
                </p>
              </div>
              <button
                onClick={handleDismiss}
                className="text-[var(--foreground-muted)] hover:text-[var(--foreground)] transition-colors p-1 -mr-1 -mt-1"
                aria-label="Dismiss feedback"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {!feedbackType ? (
              /* Step 1: Choose feedback type */
              <div className="space-y-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full justify-start gap-2 hover:bg-[var(--success)]/10 hover:border-[var(--success)]/30 hover:text-[var(--success)]"
                  onClick={() => setFeedbackType('positive')}
                >
                  <ThumbsUp className="w-4 h-4" />
                  It&apos;s going well
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full justify-start gap-2 hover:bg-yellow-500/10 hover:border-yellow-500/30 hover:text-yellow-500"
                  onClick={() => setFeedbackType('negative')}
                >
                  <ThumbsDown className="w-4 h-4" />
                  I had some issues
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full justify-start gap-2 hover:bg-red-500/10 hover:border-red-500/30 hover:text-red-500"
                  onClick={() => setFeedbackType('issue')}
                >
                  <AlertCircle className="w-4 h-4" />
                  I found a bug
                </Button>
              </div>
            ) : (
              /* Step 2: Optional message + submit */
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                className="space-y-3"
              >
                <div>
                  <label className="text-xs text-[var(--foreground-muted)] block mb-1.5">
                    {feedbackType === 'positive' && 'What did you like? (optional)'}
                    {feedbackType === 'negative' && 'What went wrong? (optional)'}
                    {feedbackType === 'issue' && 'Describe the bug: (optional)'}
                  </label>
                  <textarea
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder="Tell us more..."
                    className="w-full p-2.5 text-sm bg-[var(--background)] border border-[var(--border)] rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 focus:border-[var(--accent)]"
                    rows={3}
                  />
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setFeedbackType(null);
                      setMessage('');
                    }}
                    disabled={isSubmitting}
                    className="text-[var(--foreground-muted)]"
                  >
                    Back
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleSubmit}
                    disabled={isSubmitting}
                    className="flex-1 gap-2"
                  >
                    {isSubmitting ? (
                      <>
                        <motion.div
                          animate={{ rotate: 360 }}
                          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                        >
                          <Send className="w-4 h-4" />
                        </motion.div>
                        Sending...
                      </>
                    ) : (
                      <>
                        <Send className="w-4 h-4" />
                        Send Feedback
                      </>
                    )}
                  </Button>
                </div>
              </motion.div>
            )}
          </>
        )}
      </motion.div>
    </AnimatePresence>
  );
}
