'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Brain, User, Globe, ChevronDown, ChevronUp, Loader2, Sparkles } from 'lucide-react';
import { api } from '@/lib/api';
import { UserMemoryContext } from '@/types';
import { motion, AnimatePresence } from 'framer-motion';
import { logError, logWarn, logInfo, LogCategory } from '@/lib/logging/structured-logger';

// Circuit breaker configuration
const CIRCUIT_BREAKER_THRESHOLD = 3; // Number of failures before opening circuit
const CIRCUIT_BREAKER_TIMEOUT = 300000; // 5 minutes before attempting to close circuit
const POLL_INTERVAL = 120000; // 2 minutes

export function MemoryPulse() {
  const [memory, setMemory] = useState<UserMemoryContext | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  // Circuit breaker state
  const failureCount = useRef(0);
  const circuitOpen = useRef(false);
  const circuitOpenedAt = useRef<number | null>(null);

  const loadMemory = async () => {
    // Circuit breaker: skip request if circuit is open and timeout hasn't passed
    if (circuitOpen.current && circuitOpenedAt.current) {
      const timeSinceOpened = Date.now() - circuitOpenedAt.current;
      if (timeSinceOpened < CIRCUIT_BREAKER_TIMEOUT) {
        logInfo(LogCategory.MEMORY, 'Circuit breaker open, skipping memory pulse request', {
          failureCount: failureCount.current,
          timeRemaining: Math.round((CIRCUIT_BREAKER_TIMEOUT - timeSinceOpened) / 1000) + 's'
        });
        return;
      }
      // Timeout passed, attempt to close circuit
      logInfo(LogCategory.MEMORY, 'Circuit breaker timeout passed, attempting to close circuit');
      circuitOpen.current = false;
      circuitOpenedAt.current = null;
      failureCount.current = 0;
    }

    setIsLoading(true);
    try {
      // Use the new memory context endpoint
      const response = await api.getUserMemoryContext();
      if (response && response.success) {
        setMemory(response);
        // Reset circuit breaker on success
        failureCount.current = 0;
        circuitOpen.current = false;
        circuitOpenedAt.current = null;
      }
    } catch (error) {
      failureCount.current++;
      logError(LogCategory.MEMORY, 'Failed to load memory pulse', {
        error: error instanceof Error ? error.message : 'Unknown error',
        failureCount: failureCount.current,
        circuitOpen: circuitOpen.current
      });

      // Open circuit breaker if threshold reached
      if (failureCount.current >= CIRCUIT_BREAKER_THRESHOLD && !circuitOpen.current) {
        circuitOpen.current = true;
        circuitOpenedAt.current = Date.now();
        logWarn(LogCategory.MEMORY,
          `Circuit breaker opened after ${CIRCUIT_BREAKER_THRESHOLD} failures. Will retry in ${CIRCUIT_BREAKER_TIMEOUT / 1000} seconds`
        );
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadMemory();
    // Refresh memory every 2 minutes or when a new chat starts
    const interval = setInterval(loadMemory, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, []);

  if (!memory?.has_data && !isLoading) return null;

  return (
    <div className="mx-2 mb-4 overflow-hidden rounded-xl border border-white/10 bg-white/5 backdrop-blur-md">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex w-full items-center justify-between p-3 hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-2">
          <div className="relative">
            <Brain className="h-4 w-4 text-indigo-400" />
            <span className="absolute -right-1 -top-1 flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
            </span>
          </div>
          <span className="text-xs font-semibold tracking-wider text-indigo-200 uppercase">AI Pulse</span>
        </div>
        {isLoading ? (
          <Loader2 className="h-3 w-3 animate-spin text-indigo-400" />
        ) : isExpanded ? (
          <ChevronUp className="h-3 w-3 text-white/40" />
        ) : (
          <ChevronDown className="h-3 w-3 text-white/40" />
        )}
      </button>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-white/5"
          >
            <div className="p-3 space-y-3">
              {/* Profile Facts */}
              {memory?.profile_facts && memory.profile_facts.length > 0 && (
                <div className="space-y-1.5">
                  <div className="flex items-center gap-1.5 text-[10px] font-bold text-white/40 uppercase tracking-widest">
                    <User size={10} />
                    <span>Personal Context</span>
                  </div>
                  <div className="space-y-1">
                    {memory.profile_facts.slice(0, 5).map((fact, i) => (
                      <div key={i} className="text-[11px] text-white/70 flex items-start gap-1.5 leading-tight">
                        <span className="mt-1 h-1 w-1 rounded-full bg-indigo-500 flex-shrink-0" />
                        <span>{fact}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Summary */}
              {memory?.summary && (
                <div className="space-y-1.5">
                  <div className="flex items-center gap-1.5 text-[10px] font-bold text-white/40 uppercase tracking-widest">
                    <Sparkles size={10} />
                    <span>Current Focus</span>
                  </div>
                  <p className="text-[11px] text-white/60 italic leading-tight">
                    "{memory.summary}"
                  </p>
                </div>
              )}

              {/* Collective Knowledge */}
              <div className="space-y-1.5 pt-1">
                <div className="flex items-center gap-1.5 text-[10px] font-bold text-teal-400/60 uppercase tracking-widest">
                  <Globe size={10} />
                  <span>Collective Wisdom</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="h-1 flex-1 rounded-full bg-white/5 overflow-hidden">
                    <div className="h-full bg-teal-500/50 w-[65%]" />
                  </div>
                  <span className="text-[9px] text-teal-400/80 font-mono">ACTIVE</span>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
