'use client';

import { useRouter } from 'next/navigation';
import { useSystemSound } from '@/hooks/useSystemSound';
import { useState } from 'react';
import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import Image from 'next/image';
import { api } from '@/lib/api';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [pin, setPin] = useState('');
  const [loginStage, setLoginStage] = useState<'idle' | 'authenticating' | 'success' | 'denied'>(
    'idle'
  );
  const router = useRouter();
  const { play } = useSystemSound();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loginStage !== 'idle') return;

    // 1. Sound: Authenticate Start
    play('auth_start');
    setLoginStage('authenticating');

    try {
      // 2. Real API call
      await api.login(email, pin);

      // 3. Success
      setLoginStage('success');
      play('access_granted');

      // Verify token is saved before redirect
      // Use window.location for full page reload to ensure clean state
      setTimeout(() => {
        // Double-check token is saved - read directly from localStorage to be sure
        const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
        if (token && token.length > 0) {
          // Force full page reload to ensure clean state
          window.location.href = '/dashboard';
        } else {
          console.error('Token not saved after login');
          setLoginStage('idle');
        }
      }, 2000); // Increased delay to ensure token is fully saved
    } catch (error) {
      // 4. Failure
      console.error('Login failed:', error);
      setLoginStage('denied');
      play('access_denied');
      // Reset after delay
      setTimeout(() => {
        setLoginStage('idle');
      }, 2000);
    }
  };

  return (
    <div className="flex w-full min-h-screen bg-black overflow-hidden font-sans text-white selection:bg-cyan-500/30 relative">
      <style
        dangerouslySetInnerHTML={{
          __html: `
        input:-webkit-autofill,
        input:-webkit-autofill:hover, 
        input:-webkit-autofill:focus, 
        input:-webkit-autofill:active {
            -webkit-box-shadow: 0 0 0 30px #212222 inset !important;
            -webkit-text-fill-color: white !important;
            caret-color: #CE1126 !important;
        }
      `,
        }}
      />

      {/* ACCESS GRANTED OVERLAY */}
      {loginStage === 'success' && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.1 }}
          className="absolute inset-0 z-50 bg-black flex items-center justify-center"
        >
          <h1 className="text-4xl md:text-6xl font-mono font-bold text-white tracking-widest uppercase">
            Access Granted
          </h1>
        </motion.div>
      )}

      {/* ACCESS DENIED OVERLAY */}
      {loginStage === 'denied' && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.1 }}
          className="absolute inset-0 z-50 bg-black/90 flex items-center justify-center backdrop-blur-sm"
        >
          <h1 className="text-4xl md:text-6xl font-mono font-bold text-[#CE1126] tracking-widest uppercase">
            Access Denied
          </h1>
        </motion.div>
      )}

      {/* LEFT COLUMN - Brand, Identity & Access */}
      <motion.div
        initial={{ x: -50, opacity: 0 }}
        animate={{
          x: 0,
          opacity: loginStage === 'authenticating' ? 0.5 : 1, // Dim on authenticating
        }}
        transition={{ duration: 0.8, ease: 'easeOut' }}
        className="w-full lg:w-[35%] h-full min-h-screen bg-[#212222] relative z-20 flex flex-col px-12 lg:px-16 py-12"
      >
        {/* Top: Brand Identity */}
        <div className="flex flex-col items-center w-full pt-8 mb-auto">
          {/* Logo - Classic Metallic 3D */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{
              opacity: 1,
              scale: loginStage === 'authenticating' ? 1.015 : 1, // Logo Zoom on Auth
            }}
            transition={{ duration: loginStage === 'authenticating' ? 1 : 1 }}
            className="relative w-32 md:w-40"
          >
            <Image
              src="/assets/login/zantara-logo-classic.png"
              alt="Zantara Classic Logo"
              width={400}
              height={400}
              className="w-full h-auto drop-shadow-[0_10px_30px_rgba(0,0,0,0.5)]"
              priority
              unoptimized
            />
          </motion.div>
        </div>

        {/* Center: Generic Login Form */}
        <div className="w-full max-w-sm mb-auto">
          <div className="mb-8">
            <p className="text-xs text-gray-500 mt-1 tracking-wider uppercase">
              Authorized Personnel Only
            </p>
          </div>

          <form onSubmit={handleLogin} className="space-y-6">
            <div className="space-y-2">
              <label
                htmlFor="email"
                className="block text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em] pl-1"
              >
                Identity
              </label>
              <input
                id="email"
                name="email"
                type="email"
                placeholder="user@zantara.id"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onFocus={() => play('focus')}
                disabled={loginStage !== 'idle'}
                className="w-full bg-black/20 border-b border-white/10 py-3 pl-0 text-red-50 placeholder-white/20 caret-[#CE1126] focus:outline-none focus:border-[#CE1126] focus:shadow-[0_0_10px_rgba(206,17,38,0.2)] focus:bg-white/[0.02] transition-colors duration-0 text-sm font-light tracking-wide rounded-none"
              />
            </div>

            <div className="space-y-2">
              <label
                htmlFor="pin"
                className="block text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em] pl-1"
              >
                Security Key
              </label>
              <input
                id="pin"
                name="pin"
                type="password"
                placeholder="••••••••"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                onFocus={() => play('focus')}
                disabled={loginStage !== 'idle'}
                className="w-full bg-black/20 border-b border-white/10 py-3 pl-0 text-red-50 placeholder-white/20 caret-[#CE1126] focus:outline-none focus:border-[#CE1126] focus:shadow-[0_0_10px_rgba(206,17,38,0.2)] focus:bg-white/[0.02] transition-colors duration-0 text-sm font-light tracking-wide rounded-none"
              />
            </div>

            <div className="pt-8">
              <button
                type="submit"
                disabled={loginStage !== 'idle'}
                className="w-full group relative overflow-hidden bg-white/5 hover:bg-[#CE1126] hover:border-[#CE1126] hover:shadow-[0_0_30px_rgba(206,17,38,0.4)] border border-white/10 text-white text-xs font-bold tracking-[0.2em] uppercase py-4 transition-all duration-300 flex items-center justify-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span className="opacity-80 group-hover:opacity-100 transition-opacity">
                  Authenticate
                </span>
                <ArrowRight className="h-3 w-3 text-cyan-500 opacity-70 group-hover:text-white group-hover:translate-x-1 group-hover:opacity-100 transition-all" />

                {/* Glow Effect only on idle */}
                {loginStage === 'idle' && (
                  <div className="absolute bottom-0 left-0 h-[1px] w-full bg-gradient-to-r from-transparent via-white/50 to-transparent scale-x-0 group-hover:scale-x-100 transition-transform duration-500" />
                )}
              </button>
            </div>
          </form>
        </div>

        {/* Footer */}
        <div className="w-full pt-8 border-t border-white/5">
          <div className="flex justify-between items-end">
            <div className="text-[10px] text-white/20 tracking-[0.2em] font-mono">SYSTEM v5.4</div>
            <div className="flex flex-col items-end gap-1">
              <div className="flex items-center gap-2">
                <span className="w-1 h-1 rounded-full bg-cyan-500/50 animate-pulse" />
                <span className="text-[10px] text-cyan-500/40 tracking-wider font-mono">
                  ONLINE
                </span>
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      {/* RIGHT COLUMN - Kintsugi Capital */}
      <div className="hidden lg:block lg:w-[65%] relative z-0 h-screen bg-[#212222]">
        <motion.div
          className="relative w-full h-full"
          animate={{
            filter:
              loginStage === 'authenticating'
                ? 'brightness(1.2) contrast(1.1)'
                : 'brightness(1) contrast(1)',
          }}
          transition={{ duration: 0.2 }} // Fast reaction to auth start
        >
          <Image
            src="/assets/login/kintsugi-stone.png"
            alt="Kintsugi Capital - Value from the Raw"
            fill
            className="object-cover object-center scale-110"
            priority
            quality={100}
            unoptimized
          />
        </motion.div>

        {/* Cinematic Gradient Overlay */}
        <div className="absolute inset-0 bg-gradient-to-r from-[#212222] via-transparent to-transparent" />
        <div className="absolute inset-0 bg-gradient-to-t from-[#212222] via-transparent to-transparent opacity-90" />

        {/* Kintsugi Text Overlay */}
        <div className="absolute bottom-12 right-16 text-right max-w-md flex flex-col items-end">
          <h2 className="text-3xl font-serif text-amber-100/90 leading-tight mb-2">
            Order from the raw
          </h2>
          <div className="w-full h-px bg-[#D4AF37]/50 mb-3" />
          <span className="text-[18px] uppercase tracking-[0.6em] text-[#D4AF37]/65 font-sans font-light">
            N I L A I
          </span>
        </div>
      </div>
    </div>
  );
}
