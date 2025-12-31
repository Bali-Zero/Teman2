'use client';

import * as React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mail, Check, Loader2, Sparkles, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { subscribeToNewsletter } from '@/lib/blog/newsletter';
import type { ArticleCategory, NewsletterFormProps } from '@/lib/blog/types';

// Category options for newsletter
const CATEGORY_OPTIONS: { value: ArticleCategory; label: string }[] = [
  { value: 'immigration', label: 'Immigration & Visas' },
  { value: 'business', label: 'Business Setup' },
  { value: 'tax-legal', label: 'Tax & Legal' },
  { value: 'property', label: 'Property' },
  { value: 'lifestyle', label: 'Lifestyle' },
  { value: 'tech', label: 'Tech & Digital Nomad' },
];

// Frequency options
const FREQUENCY_OPTIONS: { value: 'daily' | 'weekly' | 'monthly'; label: string }[] = [
  { value: 'weekly', label: 'Weekly Digest' },
  { value: 'daily', label: 'Daily Updates' },
  { value: 'monthly', label: 'Monthly Roundup' },
];

// Inline form variant (default)
function InlineForm({
  defaultCategories = [],
  onSuccess,
  className,
}: NewsletterFormProps) {
  const [email, setEmail] = React.useState('');
  const [status, setStatus] = React.useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = React.useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email || !email.includes('@')) {
      setErrorMessage('Please enter a valid email address');
      setStatus('error');
      return;
    }

    setStatus('loading');
    setErrorMessage('');

    try {
      const result = await subscribeToNewsletter({
        email,
        categories: defaultCategories.length > 0 ? defaultCategories : ['immigration', 'business'],
        frequency: 'weekly',
        language: 'en',
      });

      if (result.success) {
        setStatus('success');
        setEmail('');
        onSuccess?.();
      } else {
        setStatus('error');
        setErrorMessage(result.message);
      }
    } catch {
      setStatus('error');
      setErrorMessage('Something went wrong. Please try again.');
    }
  };

  return (
    <div className={cn('relative', className)}>
      <AnimatePresence mode="wait">
        {status === 'success' ? (
          <motion.div
            key="success"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="flex items-center gap-3 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20"
          >
            <div className="flex-shrink-0 w-10 h-10 rounded-full bg-emerald-500/20 flex items-center justify-center">
              <Check className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <p className="font-medium text-emerald-400">You&apos;re subscribed!</p>
              <p className="text-sm text-white/60">Check your email to confirm.</p>
            </div>
          </motion.div>
        ) : (
          <motion.form
            key="form"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onSubmit={handleSubmit}
            className="space-y-3"
          >
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Enter your email"
                  disabled={status === 'loading'}
                  className={cn(
                    'w-full h-12 pl-11 pr-4 rounded-xl',
                    'bg-white/5 border border-white/10',
                    'text-white placeholder-white/40',
                    'focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50',
                    'disabled:opacity-50',
                    'transition-all duration-200'
                  )}
                />
              </div>
              <button
                type="submit"
                disabled={status === 'loading'}
                className={cn(
                  'px-6 h-12 rounded-xl font-medium transition-all',
                  'bg-gradient-to-r from-violet-600 to-fuchsia-600',
                  'hover:from-violet-500 hover:to-fuchsia-500',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                  'flex items-center gap-2'
                )}
              >
                {status === 'loading' ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    Subscribe
                    <Sparkles className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>

            {status === 'error' && errorMessage && (
              <motion.p
                initial={{ opacity: 0, y: -5 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-sm text-red-400"
              >
                {errorMessage}
              </motion.p>
            )}
          </motion.form>
        )}
      </AnimatePresence>
    </div>
  );
}

// Sidebar variant (with category selection)
function SidebarForm({
  defaultCategories = [],
  onSuccess,
  className,
}: NewsletterFormProps) {
  const [email, setEmail] = React.useState('');
  const [name, setName] = React.useState('');
  const [categories, setCategories] = React.useState<ArticleCategory[]>(
    defaultCategories.length > 0 ? defaultCategories : ['immigration', 'business']
  );
  const [frequency, setFrequency] = React.useState<'daily' | 'weekly' | 'monthly'>('weekly');
  const [showCategories, setShowCategories] = React.useState(false);
  const [status, setStatus] = React.useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = React.useState('');

  const toggleCategory = (cat: ArticleCategory) => {
    setCategories((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email || !email.includes('@')) {
      setErrorMessage('Please enter a valid email address');
      setStatus('error');
      return;
    }

    if (categories.length === 0) {
      setErrorMessage('Please select at least one category');
      setStatus('error');
      return;
    }

    setStatus('loading');
    setErrorMessage('');

    try {
      const result = await subscribeToNewsletter({
        email,
        name: name || undefined,
        categories,
        frequency,
        language: 'en',
      });

      if (result.success) {
        setStatus('success');
        setEmail('');
        setName('');
        onSuccess?.();
      } else {
        setStatus('error');
        setErrorMessage(result.message);
      }
    } catch {
      setStatus('error');
      setErrorMessage('Something went wrong. Please try again.');
    }
  };

  if (status === 'success') {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className={cn(
          'p-6 rounded-2xl bg-gradient-to-br from-emerald-500/10 to-teal-500/10 border border-emerald-500/20',
          className
        )}
      >
        <div className="text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-emerald-500/20 flex items-center justify-center">
            <Check className="w-8 h-8 text-emerald-400" />
          </div>
          <h3 className="font-serif text-xl font-semibold text-white mb-2">
            Welcome Aboard!
          </h3>
          <p className="text-white/60">
            Check your inbox to confirm your subscription.
          </p>
        </div>
      </motion.div>
    );
  }

  return (
    <div
      className={cn(
        'p-6 rounded-2xl bg-gradient-to-br from-violet-500/10 to-fuchsia-500/10 border border-violet-500/20',
        className
      )}
    >
      {/* Header */}
      <div className="mb-6 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-violet-500/20 text-violet-400 text-xs font-medium mb-3">
          <Sparkles className="w-3 h-3" />
          Newsletter
        </div>
        <h3 className="font-serif text-xl font-semibold text-white mb-2">
          Stay Ahead of the Curve
        </h3>
        <p className="text-sm text-white/60">
          Get the latest insights on business, immigration, and life in Bali.
        </p>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Name (optional) */}
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Your name (optional)"
          className={cn(
            'w-full h-11 px-4 rounded-xl',
            'bg-white/5 border border-white/10',
            'text-white placeholder-white/40 text-sm',
            'focus:outline-none focus:ring-2 focus:ring-violet-500/50'
          )}
        />

        {/* Email */}
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Your email address"
          required
          className={cn(
            'w-full h-11 px-4 rounded-xl',
            'bg-white/5 border border-white/10',
            'text-white placeholder-white/40 text-sm',
            'focus:outline-none focus:ring-2 focus:ring-violet-500/50'
          )}
        />

        {/* Category selector */}
        <div>
          <button
            type="button"
            onClick={() => setShowCategories(!showCategories)}
            className={cn(
              'w-full flex items-center justify-between px-4 py-3 rounded-xl',
              'bg-white/5 border border-white/10',
              'text-white text-sm',
              'hover:bg-white/10 transition-colors'
            )}
          >
            <span>
              {categories.length === 0
                ? 'Select topics'
                : `${categories.length} topic${categories.length > 1 ? 's' : ''} selected`}
            </span>
            <ChevronDown
              className={cn(
                'w-4 h-4 transition-transform',
                showCategories && 'rotate-180'
              )}
            />
          </button>

          <AnimatePresence>
            {showCategories && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <div className="pt-2 space-y-1">
                  {CATEGORY_OPTIONS.map((cat) => (
                    <button
                      key={cat.value}
                      type="button"
                      onClick={() => toggleCategory(cat.value)}
                      className={cn(
                        'w-full flex items-center gap-3 px-4 py-2 rounded-lg text-sm transition-colors',
                        categories.includes(cat.value)
                          ? 'bg-violet-500/20 text-violet-400'
                          : 'text-white/60 hover:text-white hover:bg-white/5'
                      )}
                    >
                      <div
                        className={cn(
                          'w-4 h-4 rounded border flex items-center justify-center',
                          categories.includes(cat.value)
                            ? 'bg-violet-500 border-violet-500'
                            : 'border-white/20'
                        )}
                      >
                        {categories.includes(cat.value) && (
                          <Check className="w-3 h-3 text-white" />
                        )}
                      </div>
                      {cat.label}
                    </button>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Frequency */}
        <div className="flex gap-2">
          {FREQUENCY_OPTIONS.map((freq) => (
            <button
              key={freq.value}
              type="button"
              onClick={() => setFrequency(freq.value)}
              className={cn(
                'flex-1 py-2 px-3 rounded-lg text-xs font-medium transition-colors',
                frequency === freq.value
                  ? 'bg-violet-500/20 text-violet-400'
                  : 'bg-white/5 text-white/60 hover:text-white hover:bg-white/10'
              )}
            >
              {freq.label}
            </button>
          ))}
        </div>

        {/* Error message */}
        {status === 'error' && errorMessage && (
          <p className="text-sm text-red-400">{errorMessage}</p>
        )}

        {/* Submit button */}
        <button
          type="submit"
          disabled={status === 'loading'}
          className={cn(
            'w-full h-11 rounded-xl font-medium transition-all',
            'bg-gradient-to-r from-violet-600 to-fuchsia-600',
            'hover:from-violet-500 hover:to-fuchsia-500',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'flex items-center justify-center gap-2'
          )}
        >
          {status === 'loading' ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <>
              Subscribe
              <Sparkles className="w-4 h-4" />
            </>
          )}
        </button>

        {/* Privacy note */}
        <p className="text-xs text-white/40 text-center">
          We respect your privacy. Unsubscribe anytime.
        </p>
      </form>
    </div>
  );
}

// Main component with variant support
export function NewsletterForm({
  variant = 'inline',
  ...props
}: NewsletterFormProps) {
  if (variant === 'sidebar' || variant === 'modal') {
    return <SidebarForm {...props} />;
  }
  return <InlineForm {...props} />;
}

// Export variants directly
export { InlineForm as NewsletterInline, SidebarForm as NewsletterSidebar };
