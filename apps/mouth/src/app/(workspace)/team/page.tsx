'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function TeamRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/team-management');
  }, [router]);

  return null;
}
