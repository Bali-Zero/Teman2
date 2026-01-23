import React, { useState } from 'react';
import { useGeminiNano } from '../../hooks/useGeminiNano';

export const EdgeAiDebug: React.FC = () => {
  const { status, isReady, generate, latency, error } = useGeminiNano();
  const [prompt, setPrompt] = useState('Explain "Edge Intelligence" in 10 words.');
  const [response, setResponse] = useState('');
  const [loading, setLoading] = useState(false);

  const handleTest = async () => {
    if (!prompt) return;
    setLoading(true);
    setResponse('');
    try {
      const result = await generate(prompt);
      setResponse(result);
    } catch (e) {
      console.error(e); // Error is already handled in hook state
    } finally {
      setLoading(false);
    }
  };

  const statusColor = {
    checking: 'text-gray-400',
    ready: 'text-green-500',
    downloading: 'text-yellow-500',
    unsupported: 'text-red-500',
    error: 'text-red-500',
  }[status];

  return (
    <div className="p-4 border border-gray-800 rounded-lg bg-gray-900/50 backdrop-blur-sm max-w-md">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-mono text-sm font-bold text-gray-300">
          EDGE_INTELLIGENCE // GEMINI NANO
        </h3>
        <div className={`flex items-center gap-2 font-mono text-xs ${statusColor}`}>
          <div
            className={`w-2 h-2 rounded-full bg-current ${status === 'ready' ? 'animate-pulse' : ''}`}
          />
          {status.toUpperCase()}
        </div>
      </div>

      {error && (
        <div className="mb-4 p-2 bg-red-900/20 text-red-400 text-xs font-mono rounded border border-red-900/50">
          ERROR: {error}
        </div>
      )}

      {status === 'unsupported' && (
        <div className="mb-4 text-xs text-gray-400 font-mono">
          <p>Flags required in chrome://flags:</p>
          <ul className="list-disc pl-4 mt-1 space-y-1">
            <li>Prompt API for Gemini Nano</li>
            <li>Enforce Safety Hub</li>
          </ul>
        </div>
      )}

      <div className="space-y-3">
        <div>
          <label className="block text-xs font-mono text-gray-500 mb-1">PROMPT_BUFFER</label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={!isReady || loading}
            rows={2}
            className="w-full bg-black/50 border border-gray-800 rounded p-2 text-xs font-mono text-gray-300 focus:border-green-500/50 focus:outline-none disabled:opacity-50"
          />
        </div>

        <button
          onClick={handleTest}
          disabled={!isReady || loading}
          className="w-full py-1.5 px-3 bg-green-900/20 hover:bg-green-900/30 border border-green-900/50 text-green-400 text-xs font-mono rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {loading ? 'PROCESSING_TENSOR...' : 'EXECUTE_INFERENCE'}
        </button>

        {response && (
          <div className="mt-4 pt-4 border-t border-gray-800">
            <div className="flex justify-between items-center mb-1">
              <label className="block text-xs font-mono text-gray-500">OUTPUT_TENSOR</label>
              {latency && (
                <span className="text-[10px] font-mono text-green-600">{latency.toFixed(2)}ms</span>
              )}
            </div>
            <div className="p-2 bg-black rounded border border-gray-800/50 text-xs font-mono text-gray-300 whitespace-pre-wrap">
              {response}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
