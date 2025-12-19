'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import Image from 'next/image';
import { ArrowRight, Lock, Mail } from 'lucide-react';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [pin, setPin] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    // Simulate login delay
    setTimeout(() => setIsLoading(false), 2000);
  };

  return (
    <div className="relative min-h-screen w-full bg-[#202020] text-white overflow-hidden flex flex-col items-center justify-end font-sans">
      
      {/* BACKGROUND ASSET - CINEMATIC MONAS */}
      <div className="absolute inset-0 z-0 select-none pointer-events-none">
        <Image
           src="/images/login_concept_cinematic_retry_1766114529510.png"
           alt="Cinematic Monas Background"
           fill
           className="object-cover object-bottom opacity-90"
           quality={100}
           priority
        />
        {/* Overlay to ensure text readability if image is too bright */}
        <div className="absolute inset-0 bg-gradient-to-t from-[#202020] via-transparent to-transparent opacity-80" />
      </div>

      {/* FLOATING TEXT - STAGGERED LAYOUT */}
      <div className="absolute inset-0 z-10 pointer-events-none flex flex-col justify-center items-center w-full h-full">
         <div className="relative w-full max-w-7xl h-full mx-auto">
            {/* UNLOCK INDONESIA - LEFT & HIGHER */}
            <motion.h1 
              initial={{ opacity: 0, x: -50 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 1, delay: 0.5, ease: "easeOut" }}
              className="absolute left-8 top-[35%] lg:left-24 lg:top-[30%] text-4xl lg:text-7xl font-bold italic tracking-wide text-transparent bg-clip-text bg-gradient-to-r from-white to-gray-400 drop-shadow-2xl"
            >
              Unlock <br/> Indonesia
            </motion.h1>

            {/* UNLEASH POTENTIAL - RIGHT & LOWER */}
            <motion.h1 
              initial={{ opacity: 0, x: 50 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 1, delay: 0.8, ease: "easeOut" }}
              className="absolute right-8 top-[50%] lg:right-24 lg:top-[45%] text-4xl lg:text-7xl font-bold italic tracking-wide text-right text-transparent bg-clip-text bg-gradient-to-l from-white to-gray-400 drop-shadow-2xl"
            >
              Unleash <br/> Potential
            </motion.h1>
         </div>
      </div>

      {/* LOGIN FORM - GLASSMORPHISM CARD AT BOTTOM */}
      <motion.div 
        initial={{ opacity: 0, y: 50 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 1.2 }}
        className="relative z-20 w-full max-w-md p-8 mb-12 lg:mb-24 bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl ring-1 ring-white/10"
      >
        <div className="flex flex-col items-center mb-8">
           {/* ZANTARA LOGO - Centered above form */}
           <div className="w-16 h-16 bg-gradient-to-br from-red-600 to-red-900 rounded-full flex items-center justify-center shadow-lg mb-4 ring-2 ring-red-500/50">
             <span className="text-2xl font-bold text-white">Z</span>
           </div>
           <h2 className="text-xl font-medium tracking-widest text-gray-300 uppercase">Identify Yourself</h2>
        </div>

        <form onSubmit={handleLogin} className="space-y-6">
          <div className="space-y-2">
            <div className="relative group">
              <Mail className="absolute left-3 top-3.5 h-5 w-5 text-gray-400 group-focus-within:text-red-500 transition-colors" />
              <input
                type="email"
                placeholder="Agent Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-black/40 border border-white/10 rounded-lg py-3 pl-10 pr-4 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-red-500/50 focus:border-transparent transition-all"
                required
              />
            </div>
          </div>
          
          <div className="space-y-2">
             <div className="relative group">
              <Lock className="absolute left-3 top-3.5 h-5 w-5 text-gray-400 group-focus-within:text-red-500 transition-colors" />
              <input
                type="password"
                placeholder="Secure PIN"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                className="w-full bg-black/40 border border-white/10 rounded-lg py-3 pl-10 pr-4 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-red-500/50 focus:border-transparent transition-all"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full bg-gradient-to-r from-red-600 to-red-800 hover:from-red-500 hover:to-red-700 text-white font-bold py-3.5 rounded-lg shadow-lg transform transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] flex items-center justify-center gap-2 group disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <>
                Initiate Sequence <ArrowRight className="h-5 w-5 group-hover:translate-x-1 transition-transform" />
              </>
            )}
          </button>
        </form>

        <div className="text-center mt-6">
          <p className="text-xs text-gray-500 font-mono">SECURE CONNECTION ESTABLISHED // V.5.4.0</p>
        </div>
      </motion.div>

    </div>
  );
}
