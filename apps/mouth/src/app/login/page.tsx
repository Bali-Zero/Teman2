'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api } from '@/lib/api';
import { Loader2 } from 'lucide-react';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await api.login(email, pin);
      router.push('/chat');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
      <div className="w-full max-w-md p-8 relative">
        {/* Monas Background - Centered & Blended */}
        <div className="absolute inset-x-0 bottom-0 top-[10%] z-0 flex justify-center pointer-events-none opacity-40 md:opacity-50">
          <div className="relative w-full h-full max-w-lg">
            <Image
              src="/images/monas-bg.jpg"
              alt="Monas"
              fill
              className="object-contain object-bottom drop-shadow-2xl"
              priority
            />
          </div>
        </div>

        {/* Header Grid Section: Logo + Text */}
        <div className="relative z-10 grid grid-cols-1 md:grid-cols-3 gap-4 items-center mb-8 w-full">
          {/* Desktop Left: Unlock Indonesia */}
          <div className="hidden md:block text-right">
            <h1 className="text-sm md:text-base font-bold italic tracking-wide text-white whitespace-nowrap">
              Unlock{' '}
              <span className="text-[var(--accent)] drop-shadow-[0_0_8px_rgba(239,68,68,0.4)]">
                Indonesia
              </span>
            </h1>
          </div>

          {/* Center: Logo (Floating above flame) */}
          <div className="flex justify-center">
            <div className="relative w-28 h-28 md:w-36 md:h-36 group">
              {/* Elegant White Backlight */}
              <div className="absolute inset-0 bg-white/10 rounded-full blur-2xl group-hover:bg-white/20 transition-all duration-1000"></div>
              <Image
                src="/images/logo_zan.png"
                alt="Zantara Logo"
                fill
                className="object-contain relative z-10 p-2"
                priority
              />
            </div>
          </div>

          {/* Desktop Right: Unleash Potential */}
          <div className="hidden md:block text-left pt-6">
            <h2 className="text-sm md:text-base font-bold italic tracking-wide text-white/90 whitespace-nowrap">
              Unleash Potential
            </h2>
          </div>

          {/* Mobile Only: Stacked Text */}
          <div className="md:hidden col-span-1 text-center space-y-1 mt-[-1rem]">
            <h1 className="text-sm font-bold italic tracking-wide text-white">
              Unlock{' '}
              <span className="text-[var(--accent)] drop-shadow-[0_0_8px_rgba(239,68,68,0.4)]">
                Indonesia
              </span>
            </h1>
            <h2 className="text-xs font-bold italic tracking-wide text-white/90">
              Unleash Potential
            </h2>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="relative z-10 space-y-6">
          <div className="space-y-2">
            <Label htmlFor="email" className="text-white font-medium">
              Email
            </Label>
            <Input
              id="email"
              name="email"
              type="email"
              placeholder="you@balizero.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className="bg-[#f5f5f5] text-black border-transparent placeholder:text-gray-400 focus-visible:ring-[var(--accent)] h-11"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="pin" className="text-white font-medium">
              Pin
            </Label>
            <Input
              id="pin"
              name="pin"
              type="password"
              inputMode="numeric"
              pattern="[0-9]*"
              placeholder="••••••"
              value={pin}
              onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
              required
              autoComplete="current-password"
              maxLength={6}
              className="bg-[#f5f5f5] text-black border-transparent placeholder:text-gray-400 focus-visible:ring-[var(--accent)] font-bold tracking-widest h-11"
            />
          </div>

          {error && (
            <div className="p-3 rounded-md bg-[var(--error)]/10 border border-[var(--error)]/20">
              <p className="text-sm text-[var(--error)]">{error}</p>
            </div>
          )}

          <Button
            type="submit"
            className="w-full h-11 text-base font-medium"
            disabled={isLoading || !email || pin.length !== 6}
            aria-label={isLoading ? 'Signing in...' : 'Sign in to your account'}
          >
            {isLoading ? (
              <>
                <Loader2 className="animate-spin mr-2" />
                Signing in...
              </>
            ) : (
              'Sign in'
            )}
          </Button>
        </form>

        {/* Footer */}
        <p className="relative z-10 mt-8 text-center text-sm text-[var(--foreground-muted)]">
          Bali Zero @2020
        </p>
      </div>
    </div>
  );
}
