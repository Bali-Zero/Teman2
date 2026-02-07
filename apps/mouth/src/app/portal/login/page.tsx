'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { Loader2, ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { api } from '@/lib/api';
import { toast } from 'sonner';

export default function PortalLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [pin, setPin] = useState('');
  const [step, setStep] = useState<'email' | 'pin'>('email');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmitEmail = (e: React.FormEvent) => {
    e.preventDefault();
    if (email) setStep('pin');
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      // Use existing auth login (it supports PIN)
      await api.login(email, pin);
      router.push('/portal');
    } catch (error) {
      toast.error('Login failed', { description: 'Invalid email or PIN' });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#2a2a2a] p-4">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center space-y-2">
          <div className="flex items-center justify-center mb-4">
            <div className="relative w-16 h-16 rounded-full overflow-hidden">
              <Image
                src="/assets/logo/balizero-logo-clean.png"
                alt="Bali Zero"
                fill
                className="object-cover scale-110"
              />
            </div>
          </div>
          <p className="text-[#9AA0AE]">Client Portal Access</p>
        </div>

        <div className="bg-[#242424] border border-white/5 rounded-2xl p-6 md:p-8 space-y-6">
          {step === 'email' ? (
            <form onSubmit={handleSubmitEmail} className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-[#E6E7EB]">Email Address</label>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="bg-[#1A1D24] border-white/5 text-[#E6E7EB] placeholder:text-[#9AA0AE] focus:border-[#4FD1C5]/50"
                  required
                  autoFocus
                />
              </div>
              <Button
                type="submit"
                className="w-full bg-[#4FD1C5] hover:bg-[#4FD1C5]/80 text-[#0B0E13] font-medium"
              >
                Continue <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </form>
          ) : (
            <form
              onSubmit={handleLogin}
              className="space-y-4 animate-in slide-in-from-right-4 fade-in"
            >
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <label className="text-sm font-medium text-[#E6E7EB]">Access PIN</label>
                  <button
                    type="button"
                    onClick={() => setStep('email')}
                    className="text-xs text-[#4FD1C5] hover:underline"
                  >
                    Change Email
                  </button>
                </div>
                <Input
                  type="password"
                  value={pin}
                  onChange={(e) => setPin(e.target.value)}
                  placeholder="••••••"
                  className="bg-[#1A1D24] border-white/5 text-[#E6E7EB] placeholder:text-[#9AA0AE] focus:border-[#4FD1C5]/50 text-center text-2xl tracking-widest"
                  maxLength={6}
                  required
                  autoFocus
                />
              </div>
              <Button
                type="submit"
                className="w-full bg-[#4FD1C5] hover:bg-[#4FD1C5]/80 text-[#0B0E13] font-medium"
                disabled={isLoading}
              >
                {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Enter Portal'}
              </Button>
            </form>
          )}

          <div className="pt-4 text-center">
            <p className="text-xs text-[#9AA0AE]">
              Don't have a PIN? Check your invitation email or contact support.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
