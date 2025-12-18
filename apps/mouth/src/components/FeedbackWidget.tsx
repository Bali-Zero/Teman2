'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { X, MessageSquare, ThumbsUp, ThumbsDown, AlertCircle } from 'lucide-react';

interface FeedbackData {
  type: 'positive' | 'negative' | 'issue';
  message: string;
  sessionId: string | null;
  turnCount: number;
  timestamp: Date;
}

/**
 * Feedback Widget - Collect user feedback on long conversations
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

  // Show widget after 8+ turns
  useEffect(() => {
    if (turnCount >= 8 && !localStorage.getItem('feedbackSubmitted')) {
      setIsVisible(true);
    }
  }, [turnCount]);

  const handleSubmit = async () => {
    if (!feedbackType || !message.trim()) {
      return;
    }

    setIsSubmitting(true);

    const feedback: FeedbackData = {
      type: feedbackType,
      message: message.trim(),
      sessionId,
      turnCount,
      timestamp: new Date(),
    };

    try {
      // Log feedback (in production, send to backend)
      // console.log('[USER FEEDBACK]', feedback);

      // Store in localStorage for now (in production, send to API)
      const existingFeedback = JSON.parse(localStorage.getItem('conversationFeedback') || '[]');
      existingFeedback.push(feedback);
      localStorage.setItem('conversationFeedback', JSON.stringify(existingFeedback));

      // Mark as submitted
      localStorage.setItem('feedbackSubmitted', 'true');

      // Show success message
      alert('Grazie per il feedback! Il tuo input ci aiuta a migliorare il servizio.');

      setIsVisible(false);
    } catch (error) {
      console.error('Failed to submit feedback:', error);
      alert("Errore nell'invio del feedback. Riprova più tardi.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDismiss = () => {
    setIsVisible(false);
    // Don't show again for this session
    localStorage.setItem('feedbackDismissed', 'true');
  };

  if (!isVisible) {
    return null;
  }

  return (
    <div className="fixed bottom-20 left-4 right-4 md:left-auto md:right-4 md:max-w-sm bg-[var(--background-secondary)] border border-[var(--border)] rounded-lg p-4 shadow-lg z-50">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold text-[var(--foreground)] flex items-center gap-2">
            <MessageSquare className="w-4 h-4" />
            Come sta andando la conversazione?
          </h3>
          <p className="text-xs text-[var(--foreground-muted)] mt-1">
            Hai fatto {turnCount} messaggi. Il tuo feedback ci aiuta a migliorare!
          </p>
        </div>
        <button
          onClick={handleDismiss}
          className="text-[var(--foreground-muted)] hover:text-[var(--foreground)]"
          aria-label="Dismiss feedback"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {!feedbackType ? (
        <div className="space-y-2">
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start gap-2"
            onClick={() => setFeedbackType('positive')}
          >
            <ThumbsUp className="w-4 h-4" />
            Sta andando bene
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start gap-2"
            onClick={() => setFeedbackType('negative')}
          >
            <ThumbsDown className="w-4 h-4" />
            Ho riscontrato problemi
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start gap-2"
            onClick={() => setFeedbackType('issue')}
          >
            <AlertCircle className="w-4 h-4" />
            Ho trovato un bug
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          <div>
            <label className="text-xs text-[var(--foreground-muted)] block mb-1">
              {feedbackType === 'positive' && 'Cosa ti è piaciuto?'}
              {feedbackType === 'negative' && 'Quali problemi hai riscontrato?'}
              {feedbackType === 'issue' && 'Descrivi il bug:'}
            </label>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Scrivi qui..."
              className="w-full p-2 text-sm bg-[var(--background)] border border-[var(--border)] rounded resize-none"
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
            >
              Indietro
            </Button>
            <Button
              size="sm"
              onClick={handleSubmit}
              disabled={!message.trim() || isSubmitting}
              className="flex-1"
            >
              {isSubmitting ? 'Invio...' : 'Invia Feedback'}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
