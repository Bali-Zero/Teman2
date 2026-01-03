'use client';

import * as React from 'react';
import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronRight,
  RotateCcw,
  CheckCircle2,
  ArrowRight,
  HelpCircle,
  ExternalLink
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ============================================================================
// Types
// ============================================================================

export interface DecisionNode {
  id: string;
  question: string;
  description?: string;
  options: DecisionOption[];
  /** If true, this is a final result node */
  isResult?: boolean;
  /** Result details (only for result nodes) */
  result?: {
    title: string;
    description: string;
    icon?: string;
    color?: 'blue' | 'green' | 'amber' | 'red' | 'purple';
    learnMoreUrl?: string;
    learnMoreLabel?: string;
    recommendations?: string[];
    nextSteps?: string[];
  };
}

export interface DecisionOption {
  label: string;
  description?: string;
  icon?: string;
  /** ID of the next node */
  nextNodeId: string;
}

export interface DecisionTreeProps {
  /** Unique ID for saving progress */
  id?: string;
  /** Title of the decision tree */
  title: string;
  /** Subtitle/description */
  subtitle?: string;
  description?: string;
  /** All nodes in the tree */
  nodes: DecisionNode[];
  /** ID of the starting node (defaults to "start" or first node) */
  startNodeId?: string;
  /** Show progress indicator */
  showProgress?: boolean;
  /** Callback when result is reached */
  onComplete?: (resultNodeId: string, path: string[]) => void;
  /** Custom class name */
  className?: string;
}

// ============================================================================
// Color utilities
// ============================================================================

const resultColors = {
  blue: {
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/30',
    text: 'text-blue-400',
    icon: 'text-blue-400',
  },
  green: {
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
    text: 'text-emerald-400',
    icon: 'text-emerald-400',
  },
  amber: {
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    text: 'text-amber-400',
    icon: 'text-amber-400',
  },
  red: {
    bg: 'bg-red-500/10',
    border: 'border-red-500/30',
    text: 'text-red-400',
    icon: 'text-red-400',
  },
  purple: {
    bg: 'bg-purple-500/10',
    border: 'border-purple-500/30',
    text: 'text-purple-400',
    icon: 'text-purple-400',
  },
};

// ============================================================================
// Main Component
// ============================================================================

export function DecisionTree({
  id,
  title,
  subtitle,
  description,
  nodes,
  startNodeId,
  showProgress = true,
  onComplete,
  className,
}: DecisionTreeProps) {
  // Compute defaults
  const effectiveId = id || title.toLowerCase().replace(/\s+/g, '-');
  const effectiveStartNodeId = startNodeId || nodes.find(n => n.id === 'start')?.id || nodes[0]?.id || '';
  const effectiveSubtitle = subtitle || description;

  // Track the path of node IDs visited
  const [path, setPath] = useState<string[]>([effectiveStartNodeId]);
  const [isAnimating, setIsAnimating] = useState(false);

  // Get current node
  const currentNodeId = path[path.length - 1];
  const currentNode = nodes.find((n) => n.id === currentNodeId);

  // Calculate progress
  const nodesMap = new Map(nodes.map((n) => [n.id, n]));
  const maxDepth = calculateMaxDepth(nodesMap, effectiveStartNodeId);
  const progress = maxDepth > 0 ? Math.min(((path.length - 1) / maxDepth) * 100, 100) : 0;

  // Handle option selection
  const handleSelect = useCallback(
    (nextNodeId: string) => {
      if (isAnimating) return;

      setIsAnimating(true);
      const newPath = [...path, nextNodeId];
      setPath(newPath);

      const nextNode = nodesMap.get(nextNodeId);
      if (nextNode?.isResult && onComplete) {
        onComplete(nextNodeId, newPath);
      }

      setTimeout(() => setIsAnimating(false), 300);
    },
    [path, isAnimating, nodesMap, onComplete]
  );

  // Handle going back
  const handleBack = useCallback(() => {
    if (path.length > 1 && !isAnimating) {
      setPath(path.slice(0, -1));
    }
  }, [path, isAnimating]);

  // Handle restart
  const handleRestart = useCallback(() => {
    setPath([effectiveStartNodeId]);
  }, [effectiveStartNodeId]);

  if (!currentNode) {
    return (
      <div className="p-6 bg-red-500/10 rounded-xl text-red-400">
        Error: Node not found (ID: {currentNodeId})
      </div>
    );
  }

  return (
    <div className={cn('bg-black/40 rounded-2xl border border-white/10 overflow-hidden', className)}>
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/10 bg-gradient-to-r from-[#2251ff]/10 to-transparent">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-serif text-xl font-semibold text-white">{title}</h3>
            {subtitle && <p className="text-white/60 text-sm mt-1">{subtitle}</p>}
          </div>
          <div className="flex items-center gap-2">
            {path.length > 1 && (
              <button
                onClick={handleBack}
                className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-colors"
                title="Go back"
              >
                <ChevronRight className="w-4 h-4 rotate-180" />
              </button>
            )}
            <button
              onClick={handleRestart}
              className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-colors"
              title="Start over"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Progress bar */}
        {showProgress && (
          <div className="mt-4">
            <div className="flex items-center justify-between text-xs text-white/40 mb-1">
              <span>Progress</span>
              <span>{Math.round(progress)}%</span>
            </div>
            <div className="h-1 bg-white/10 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-[#2251ff] to-[#4d73ff]"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.3 }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-6">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentNodeId}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.2 }}
          >
            {currentNode.isResult ? (
              // Result view
              <ResultView node={currentNode} onRestart={handleRestart} />
            ) : (
              // Question view
              <QuestionView node={currentNode} onSelect={handleSelect} />
            )}
          </motion.div>
        </AnimatePresence>

        {/* Breadcrumb path */}
        {path.length > 1 && !currentNode.isResult && (
          <div className="mt-6 pt-4 border-t border-white/10">
            <div className="flex flex-wrap items-center gap-2 text-xs text-white/40">
              {path.map((nodeId, index) => {
                const node = nodesMap.get(nodeId);
                if (!node || index === path.length - 1) return null;
                return (
                  <React.Fragment key={nodeId}>
                    <button
                      onClick={() => setPath(path.slice(0, index + 1))}
                      className="hover:text-white/60 transition-colors truncate max-w-[150px]"
                    >
                      {node.question.length > 30
                        ? node.question.slice(0, 30) + '...'
                        : node.question}
                    </button>
                    <ChevronRight className="w-3 h-3 flex-shrink-0" />
                  </React.Fragment>
                );
              })}
              <span className="text-white/60 truncate max-w-[150px]">
                {currentNode.question.length > 30
                  ? currentNode.question.slice(0, 30) + '...'
                  : currentNode.question}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Question View
// ============================================================================

function QuestionView({
  node,
  onSelect,
}: {
  node: DecisionNode;
  onSelect: (nextNodeId: string) => void;
}) {
  return (
    <div>
      {/* Question */}
      <div className="flex items-start gap-3 mb-6">
        <div className="p-2 rounded-lg bg-[#2251ff]/20 text-[#2251ff]">
          <HelpCircle className="w-5 h-5" />
        </div>
        <div>
          <h4 className="text-lg font-medium text-white">{node.question}</h4>
          {node.description && (
            <p className="text-white/60 text-sm mt-1">{node.description}</p>
          )}
        </div>
      </div>

      {/* Options */}
      <div className="space-y-3">
        {node.options.map((option, index) => (
          <motion.button
            key={option.nextNodeId}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.05 }}
            onClick={() => onSelect(option.nextNodeId)}
            className={cn(
              'w-full p-4 rounded-xl text-left',
              'bg-white/5 hover:bg-white/10 border border-white/10 hover:border-[#2251ff]/50',
              'transition-all duration-200 group'
            )}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {option.icon && <span className="text-xl">{option.icon}</span>}
                <div>
                  <span className="font-medium text-white group-hover:text-[#2251ff] transition-colors">
                    {option.label}
                  </span>
                  {option.description && (
                    <p className="text-white/50 text-sm mt-0.5">{option.description}</p>
                  )}
                </div>
              </div>
              <ArrowRight className="w-4 h-4 text-white/30 group-hover:text-[#2251ff] group-hover:translate-x-1 transition-all" />
            </div>
          </motion.button>
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// Result View
// ============================================================================

function ResultView({
  node,
  onRestart,
}: {
  node: DecisionNode;
  onRestart: () => void;
}) {
  const result = node.result;
  if (!result) return null;

  const colors = resultColors[result.color || 'blue'];

  return (
    <div>
      {/* Result card */}
      <div className={cn('p-6 rounded-xl border', colors.bg, colors.border)}>
        <div className="flex items-start gap-4">
          <div className={cn('p-3 rounded-xl', colors.bg)}>
            {result.icon ? (
              <span className="text-3xl">{result.icon}</span>
            ) : (
              <CheckCircle2 className={cn('w-8 h-8', colors.icon)} />
            )}
          </div>
          <div className="flex-1">
            <h4 className={cn('text-xl font-semibold', colors.text)}>{result.title}</h4>
            <p className="text-white/70 mt-2">{result.description}</p>
          </div>
        </div>

        {/* Recommendations */}
        {result.recommendations && result.recommendations.length > 0 && (
          <div className="mt-6 pt-4 border-t border-white/10">
            <h5 className="text-sm font-medium text-white/80 mb-3">Recommendations</h5>
            <ul className="space-y-2">
              {result.recommendations.map((rec, index) => (
                <li key={index} className="flex items-start gap-2 text-sm text-white/60">
                  <CheckCircle2 className={cn('w-4 h-4 mt-0.5 flex-shrink-0', colors.icon)} />
                  <span>{rec}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Next steps */}
        {result.nextSteps && result.nextSteps.length > 0 && (
          <div className="mt-4 pt-4 border-t border-white/10">
            <h5 className="text-sm font-medium text-white/80 mb-3">Next Steps</h5>
            <ol className="space-y-2">
              {result.nextSteps.map((step, index) => (
                <li key={index} className="flex items-start gap-3 text-sm text-white/60">
                  <span className={cn('w-5 h-5 rounded-full flex items-center justify-center text-xs font-medium', colors.bg, colors.text)}>
                    {index + 1}
                  </span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </div>
        )}

        {/* Learn more link */}
        {result.learnMoreUrl && (
          <a
            href={result.learnMoreUrl}
            className={cn(
              'inline-flex items-center gap-2 mt-6 px-4 py-2 rounded-lg',
              'bg-white/5 hover:bg-white/10 transition-colors',
              colors.text
            )}
          >
            <span>{result.learnMoreLabel || 'Learn more'}</span>
            <ExternalLink className="w-4 h-4" />
          </a>
        )}
      </div>

      {/* Restart button */}
      <button
        onClick={onRestart}
        className="mt-4 flex items-center gap-2 text-white/60 hover:text-white transition-colors"
      >
        <RotateCcw className="w-4 h-4" />
        <span>Start over</span>
      </button>
    </div>
  );
}

// ============================================================================
// Utility Functions
// ============================================================================

function calculateMaxDepth(
  nodesMap: Map<string, DecisionNode>,
  nodeId: string,
  visited = new Set<string>()
): number {
  if (visited.has(nodeId)) return 0;
  visited.add(nodeId);

  const node = nodesMap.get(nodeId);
  if (!node || node.isResult || !node.options.length) return 0;

  let maxChildDepth = 0;
  for (const option of node.options) {
    const childDepth = calculateMaxDepth(nodesMap, option.nextNodeId, visited);
    maxChildDepth = Math.max(maxChildDepth, childDepth);
  }

  return 1 + maxChildDepth;
}
