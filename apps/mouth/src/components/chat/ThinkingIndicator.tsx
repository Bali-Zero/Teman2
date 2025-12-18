import React from 'react';
import { motion } from 'framer-motion';
import { BrainCircuit } from 'lucide-react';

interface ThinkingIndicatorProps {
  status?: string;
}

export const ThinkingIndicator: React.FC<ThinkingIndicatorProps> = ({ status = 'Thinking...' }) => {
  return (
    <div className="flex items-center gap-3 p-4 rounded-xl bg-white/5 backdrop-blur-sm border border-white/10 w-fit my-2">
      <div className="relative">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
        >
          <BrainCircuit className="w-5 h-5 text-[var(--accent)]" />
        </motion.div>
        <motion.div
          className="absolute inset-0 rounded-full"
          animate={{
            boxShadow: ['0 0 0px var(--accent)', '0 0 10px var(--accent)', '0 0 0px var(--accent)'],
          }}
          transition={{ duration: 2, repeat: Infinity }}
        />
      </div>
      <div className="flex flex-col">
        <span className="text-sm font-medium text-gray-200">Zantara</span>
        <span className="text-xs text-gray-400 animate-pulse">{status}</span>
      </div>
    </div>
  );
};
