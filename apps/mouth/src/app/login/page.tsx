'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import Image from 'next/image';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [pin, setPin] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    // Simulate login
    setTimeout(() => setIsLoading(false), 2000);
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-[var(--background)] text-white font-sans selection:bg-red-500/30 relative isolate">
      {/* Background Image (Low Opacity) - Same as /chat and /dashboard */}
      <div className="fixed inset-0 z-[-1] opacity-[0.08] pointer-events-none">
        <Image
          src="/images/monas-bg.jpg"
          alt="Background"
          fill
          className="object-cover object-center"
          priority
        />
        <div className="absolute inset-0 bg-gradient-to-b from-[var(--background)]/80 via-transparent to-[var(--background)]" />
      </div>
      
      {/* LEFT COLUMN DISINTEGRATED (Removed as per request) */}
      
      {/* RIGHT COLUMN - NOW CENTER STAGE */}
      {/* "la colonna di destra non si tocca" -> Preserving the exact interior style of the right column */}
      <motion.div 
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-md p-8 flex flex-col items-center justify-center"
        >
          {/* Header */}
          <div className="w-full space-y-2 mb-10 text-center">
             {/* Optional: Add Logo here since Left is gone? User said "Left disintegrates", didn't explicitly say "move logo". 
                 But a login page usually needs a logo. I'll stick to the "Right column untouched" rule strictly first. 
                 The Right column didn't have the big logo. It had "Access Portal". */}
            <h3 className="text-2xl font-medium tracking-tight text-white">Access Portal</h3>
            <p className="text-sm text-gray-500">Secure entry for authorized personnel only.</p>
          </div>

          <form onSubmit={handleLogin} className="w-full space-y-6">
            
            {/* Input Group 1 */}
            <div className="space-y-2">
              <label htmlFor="email" className="block text-xs font-medium text-gray-500 uppercase tracking-widest">
                Identity
              </label>
              <div className="relative">
                 <input
                  id="email"
                  type="email"
                  placeholder="user@zantara.id"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-transparent border-b border-white/20 py-3 text-white placeholder-gray-700 focus:outline-none focus:border-red-500 transition-colors rounded-none" 
                />
              </div>
            </div>
            
            {/* Input Group 2 */}
            <div className="space-y-2">
              <label htmlFor="pin" className="block text-xs font-medium text-gray-500 uppercase tracking-widest">
                Security Key
              </label>
              <div className="relative">
                <input
                  id="pin"
                  type="password"
                  placeholder="••••••••"
                  value={pin}
                  onChange={(e) => setPin(e.target.value)}
                  className="w-full bg-transparent border-b border-white/20 py-3 text-white placeholder-gray-700 focus:outline-none focus:border-red-500 transition-colors rounded-none"
                />
              </div>
            </div>

            <div className="pt-6">
              <button
                type="submit"
                disabled={isLoading}
                className="w-full bg-white hover:bg-gray-200 text-black font-semibold py-4 rounded-sm transition-all flex items-center justify-center gap-3"
              >
                {isLoading ? (
                  <span className="w-4 h-4 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                ) : (
                  <>
                    <span>Authenticate</span>
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </div>
          </form>
           
          {/* Footer */}
          <div className="w-full pt-12 mt-4 border-t border-white/5">
            <div className="flex justify-between items-center text-xs text-gray-600 font-mono">
               <span>V 5.4 ULTRA HYBRID</span>
               <span className="text-green-900/40 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500/50"></span>
                  ONLINE
               </span>
            </div>
          </div>

      </motion.div>
    </div>
  );
}
