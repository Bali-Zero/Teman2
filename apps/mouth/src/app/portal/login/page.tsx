'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
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
    <div className="min-h-screen flex items-center justify-center bg-neutral-950 p-4">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold tracking-tighter text-white">
            <span className="text-emerald-500">BALI</span>ZERO
          </h1>
          <p className="text-neutral-400">Client Portal Access</p>
        </div>

        <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 md:p-8 space-y-6">
          {step === 'email' ? (
            <form onSubmit={handleSubmitEmail} className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-neutral-300">Email Address</label>
                <Input 
                  type="email" 
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="bg-neutral-950 border-neutral-800 text-white placeholder:text-neutral-600 focus:border-emerald-500/50"
                  required
                  autoFocus
                />
              </div>
              <Button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-500 text-white">
                Continue <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </form>
          ) : (
            <form onSubmit={handleLogin} className="space-y-4 animate-in slide-in-from-right-4 fade-in">
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <label className="text-sm font-medium text-neutral-300">Access PIN</label>
                  <button 
                    type="button" 
                    onClick={() => setStep('email')}
                    className="text-xs text-emerald-500 hover:underline"
                  >
                    Change Email
                  </button>
                </div>
                <Input 
                  type="password" 
                  value={pin}
                  onChange={(e) => setPin(e.target.value)}
                  placeholder="••••••"
                  className="bg-neutral-950 border-neutral-800 text-white placeholder:text-neutral-600 focus:border-emerald-500/50 text-center text-2xl tracking-widest"
                  maxLength={6}
                  required
                  autoFocus
                />
              </div>
              <Button 
                type="submit" 
                className="w-full bg-emerald-600 hover:bg-emerald-500 text-white"
                disabled={isLoading}
              >
                {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Enter Portal'}
              </Button>
            </form>
          )}

          <div className="pt-4 text-center">
            <p className="text-xs text-neutral-600">
              Don't have a PIN? Check your invitation email or contact support.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
