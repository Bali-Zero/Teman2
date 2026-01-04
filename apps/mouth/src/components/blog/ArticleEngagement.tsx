'use client';

import * as React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Heart,
  MessageCircle,
  Share2,
  Twitter,
  Linkedin,
  Facebook,
  Link2,
  Send,
  X,
  ChevronDown,
  ChevronUp,
  User,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';

// Types
interface Comment {
  id: string;
  author: string;
  avatar?: string;
  content: string;
  createdAt: Date;
  likes: number;
  isLiked: boolean;
}

interface ArticleEngagementProps {
  articleId: string;
  articleTitle: string;
  articleUrl: string;
  initialLikes?: number;
  initialComments?: Comment[];
  className?: string;
}

// Like Button Component
function LikeButton({
  likes,
  isLiked,
  onLike,
}: {
  likes: number;
  isLiked: boolean;
  onLike: () => void;
}) {
  return (
    <motion.button
      onClick={onLike}
      whileTap={{ scale: 0.9 }}
      className={cn(
        'flex items-center gap-2 px-4 py-2 rounded-full transition-all',
        isLiked
          ? 'bg-red-500/20 text-red-400 border border-red-500/30'
          : 'bg-white/5 text-white/60 hover:text-white hover:bg-white/10 border border-white/10'
      )}
    >
      <motion.div
        animate={isLiked ? { scale: [1, 1.3, 1] } : {}}
        transition={{ duration: 0.3 }}
      >
        <Heart
          className={cn('w-5 h-5', isLiked && 'fill-current')}
        />
      </motion.div>
      <span className="font-medium">{likes}</span>
    </motion.button>
  );
}

// Share Menu Component
function ShareMenu({
  articleTitle,
  articleUrl,
  isOpen,
  onClose,
}: {
  articleTitle: string;
  articleUrl: string;
  isOpen: boolean;
  onClose: () => void;
}) {
  const [copied, setCopied] = React.useState(false);

  const shareOptions = [
    {
      name: 'Twitter / X',
      icon: Twitter,
      color: 'hover:bg-sky-500/20 hover:text-sky-400',
      action: () => {
        window.open(
          `https://twitter.com/intent/tweet?text=${encodeURIComponent(articleTitle)}&url=${encodeURIComponent(articleUrl)}`,
          '_blank'
        );
      },
    },
    {
      name: 'LinkedIn',
      icon: Linkedin,
      color: 'hover:bg-blue-500/20 hover:text-blue-400',
      action: () => {
        window.open(
          `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(articleUrl)}`,
          '_blank'
        );
      },
    },
    {
      name: 'Facebook',
      icon: Facebook,
      color: 'hover:bg-blue-600/20 hover:text-blue-500',
      action: () => {
        window.open(
          `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(articleUrl)}`,
          '_blank'
        );
      },
    },
    {
      name: 'WhatsApp',
      icon: Send,
      color: 'hover:bg-green-500/20 hover:text-green-400',
      action: () => {
        window.open(
          `https://wa.me/?text=${encodeURIComponent(`${articleTitle} ${articleUrl}`)}`,
          '_blank'
        );
      },
    },
  ];

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(articleUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40"
            onClick={onClose}
          />

          {/* Menu */}
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute bottom-full left-0 mb-2 p-2 bg-[#0a1929] border border-white/10 rounded-xl shadow-xl z-50 min-w-[200px]"
          >
            <p className="px-3 py-2 text-xs font-medium text-white/40 uppercase tracking-wider">
              Share this article
            </p>

            {shareOptions.map((option) => (
              <button
                key={option.name}
                onClick={() => {
                  option.action();
                  onClose();
                }}
                className={cn(
                  'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-white/70 transition-colors',
                  option.color
                )}
              >
                <option.icon className="w-4 h-4" />
                <span className="text-sm">{option.name}</span>
              </button>
            ))}

            <div className="border-t border-white/10 my-2" />

            <button
              onClick={copyLink}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors',
                copied
                  ? 'bg-emerald-500/20 text-emerald-400'
                  : 'text-white/70 hover:bg-white/10 hover:text-white'
              )}
            >
              <Link2 className="w-4 h-4" />
              <span className="text-sm">{copied ? 'Copied!' : 'Copy link'}</span>
            </button>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

// Comment Form Component
function CommentForm({
  onSubmit,
  isSubmitting,
}: {
  onSubmit: (content: string, author: string) => void;
  isSubmitting: boolean;
}) {
  const [content, setContent] = React.useState('');
  const [author, setAuthor] = React.useState('');
  const [isFocused, setIsFocused] = React.useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (content.trim() && author.trim()) {
      onSubmit(content.trim(), author.trim());
      setContent('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="flex gap-3">
        <div className="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center flex-shrink-0">
          <User className="w-5 h-5 text-white/40" />
        </div>
        <div className="flex-1 space-y-3">
          <input
            type="text"
            value={author}
            onChange={(e) => setAuthor(e.target.value)}
            placeholder="Your name"
            className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-white/30 focus:outline-none focus:border-[#2251ff]/50 focus:ring-1 focus:ring-[#2251ff]/50 transition-colors text-sm"
          />
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder="Add a comment..."
            rows={isFocused || content ? 3 : 1}
            className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/30 focus:outline-none focus:border-[#2251ff]/50 focus:ring-1 focus:ring-[#2251ff]/50 transition-all resize-none"
          />
        </div>
      </div>

      <AnimatePresence>
        {(isFocused || content) && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="flex justify-end"
          >
            <button
              type="submit"
              disabled={!content.trim() || !author.trim() || isSubmitting}
              className={cn(
                'px-5 py-2 rounded-lg font-medium text-sm transition-all',
                content.trim() && author.trim()
                  ? 'bg-[#2251ff] text-white hover:bg-[#1a40cc]'
                  : 'bg-white/10 text-white/30 cursor-not-allowed'
              )}
            >
              {isSubmitting ? 'Posting...' : 'Post Comment'}
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </form>
  );
}

// Single Comment Component
function CommentItem({
  comment,
  onLike,
}: {
  comment: Comment;
  onLike: (id: string) => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex gap-3"
    >
      {comment.avatar ? (
        <img
          src={comment.avatar}
          alt={comment.author}
          className="w-10 h-10 rounded-full"
        />
      ) : (
        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#2251ff] to-[#4d73ff] flex items-center justify-center flex-shrink-0">
          <span className="text-white font-medium text-sm">
            {comment.author.charAt(0).toUpperCase()}
          </span>
        </div>
      )}

      <div className="flex-1">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-medium text-white text-sm">{comment.author}</span>
          <span className="text-xs text-white/40">
            {formatDistanceToNow(new Date(comment.createdAt), { addSuffix: true })}
          </span>
        </div>
        <p className="text-white/70 text-sm leading-relaxed">{comment.content}</p>

        <button
          onClick={() => onLike(comment.id)}
          className={cn(
            'mt-2 flex items-center gap-1 text-xs transition-colors',
            comment.isLiked
              ? 'text-red-400'
              : 'text-white/40 hover:text-white/60'
          )}
        >
          <Heart className={cn('w-3.5 h-3.5', comment.isLiked && 'fill-current')} />
          <span>{comment.likes}</span>
        </button>
      </div>
    </motion.div>
  );
}

// Main Component
export function ArticleEngagement({
  articleId,
  articleTitle,
  articleUrl,
  initialLikes = 0,
  initialComments = [],
  className,
}: ArticleEngagementProps) {
  const [likes, setLikes] = React.useState(initialLikes);
  const [isLiked, setIsLiked] = React.useState(false);
  const [comments, setComments] = React.useState<Comment[]>(initialComments);
  const [showComments, setShowComments] = React.useState(false);
  const [showShareMenu, setShowShareMenu] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  // Load liked status from localStorage
  React.useEffect(() => {
    const likedArticles = JSON.parse(localStorage.getItem('likedArticles') || '{}');
    if (likedArticles[articleId]) {
      setIsLiked(true);
    }
  }, [articleId]);

  const handleLike = () => {
    const newIsLiked = !isLiked;
    setIsLiked(newIsLiked);
    setLikes((prev) => (newIsLiked ? prev + 1 : prev - 1));

    // Save to localStorage
    const likedArticles = JSON.parse(localStorage.getItem('likedArticles') || '{}');
    if (newIsLiked) {
      likedArticles[articleId] = true;
    } else {
      delete likedArticles[articleId];
    }
    localStorage.setItem('likedArticles', JSON.stringify(likedArticles));

    // TODO: Send to backend
    // fetch(`/api/articles/${articleId}/like`, { method: 'POST' });
  };

  const handleCommentSubmit = async (content: string, author: string) => {
    setIsSubmitting(true);

    // Create new comment (in production, this would come from the API)
    const newComment: Comment = {
      id: Date.now().toString(),
      author,
      content,
      createdAt: new Date(),
      likes: 0,
      isLiked: false,
    };

    // Simulate API delay
    await new Promise((resolve) => setTimeout(resolve, 500));

    setComments((prev) => [newComment, ...prev]);
    setIsSubmitting(false);

    // TODO: Send to backend
    // await fetch(`/api/articles/${articleId}/comments`, {
    //   method: 'POST',
    //   body: JSON.stringify({ content, author }),
    // });
  };

  const handleCommentLike = (commentId: string) => {
    setComments((prev) =>
      prev.map((comment) =>
        comment.id === commentId
          ? {
              ...comment,
              isLiked: !comment.isLiked,
              likes: comment.isLiked ? comment.likes - 1 : comment.likes + 1,
            }
          : comment
      )
    );
  };

  return (
    <div className={cn('space-y-6', className)}>
      {/* Engagement Bar */}
      <div className="flex items-center justify-between p-4 bg-white/5 border border-white/10 rounded-xl">
        <div className="flex items-center gap-3">
          <LikeButton likes={likes} isLiked={isLiked} onLike={handleLike} />

          <button
            onClick={() => setShowComments(!showComments)}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-full transition-all border',
              showComments
                ? 'bg-[#2251ff]/20 text-[#2251ff] border-[#2251ff]/30'
                : 'bg-white/5 text-white/60 hover:text-white hover:bg-white/10 border-white/10'
            )}
          >
            <MessageCircle className="w-5 h-5" />
            <span className="font-medium">{comments.length}</span>
            {showComments ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </button>
        </div>

        <div className="relative">
          <button
            onClick={() => setShowShareMenu(!showShareMenu)}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-full transition-all border',
              showShareMenu
                ? 'bg-[#2251ff]/20 text-[#2251ff] border-[#2251ff]/30'
                : 'bg-white/5 text-white/60 hover:text-white hover:bg-white/10 border-white/10'
            )}
          >
            <Share2 className="w-5 h-5" />
            <span className="font-medium hidden sm:inline">Share</span>
          </button>

          <ShareMenu
            articleTitle={articleTitle}
            articleUrl={articleUrl}
            isOpen={showShareMenu}
            onClose={() => setShowShareMenu(false)}
          />
        </div>
      </div>

      {/* Comments Section */}
      <AnimatePresence>
        {showComments && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="space-y-6 overflow-hidden"
          >
            {/* Comment Form */}
            <div className="p-4 bg-white/5 border border-white/10 rounded-xl">
              <h3 className="text-lg font-semibold text-white mb-4">
                Comments ({comments.length})
              </h3>
              <CommentForm onSubmit={handleCommentSubmit} isSubmitting={isSubmitting} />
            </div>

            {/* Comments List */}
            {comments.length > 0 && (
              <div className="p-4 bg-white/5 border border-white/10 rounded-xl space-y-6">
                {comments.map((comment) => (
                  <CommentItem
                    key={comment.id}
                    comment={comment}
                    onLike={handleCommentLike}
                  />
                ))}
              </div>
            )}

            {comments.length === 0 && (
              <div className="text-center py-8 text-white/40">
                <MessageCircle className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>No comments yet. Be the first to share your thoughts!</p>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Floating Engagement Bar (for mobile)
export function FloatingEngagementBar({
  articleId,
  articleTitle,
  likes,
  commentCount,
  onLike,
  onCommentClick,
  onShare,
  isLiked,
}: {
  articleId: string;
  articleTitle: string;
  likes: number;
  commentCount: number;
  onLike: () => void;
  onCommentClick: () => void;
  onShare: () => void;
  isLiked: boolean;
}) {
  const [isVisible, setIsVisible] = React.useState(false);

  React.useEffect(() => {
    const handleScroll = () => {
      const scrollY = window.scrollY;
      setIsVisible(scrollY > 400);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ y: 100, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 100, opacity: 0 }}
          className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 lg:hidden"
        >
          <div className="flex items-center gap-2 px-4 py-2 bg-[#0a1929]/95 backdrop-blur-lg border border-white/10 rounded-full shadow-xl">
            <button
              onClick={onLike}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-full transition-colors',
                isLiked ? 'text-red-400' : 'text-white/60 hover:text-white'
              )}
            >
              <Heart className={cn('w-4 h-4', isLiked && 'fill-current')} />
              <span className="text-sm font-medium">{likes}</span>
            </button>

            <div className="w-px h-6 bg-white/10" />

            <button
              onClick={onCommentClick}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-white/60 hover:text-white transition-colors"
            >
              <MessageCircle className="w-4 h-4" />
              <span className="text-sm font-medium">{commentCount}</span>
            </button>

            <div className="w-px h-6 bg-white/10" />

            <button
              onClick={onShare}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-white/60 hover:text-white transition-colors"
            >
              <Share2 className="w-4 h-4" />
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
