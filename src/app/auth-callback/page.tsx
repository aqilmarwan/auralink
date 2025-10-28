'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';

const Page = () => {
  const router = useRouter();

  const searchParams = useSearchParams();
  const origin = searchParams.get('origin');

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      try {
        const result = await invoke<{ success: boolean }>('auth_callback');
        if (cancelled) return;

        if (result?.success) {
          router.push(origin ? `/${origin}` : '/dashboard');
          return;
        }

        // Fallback if no success flag
        router.push('/sign-in');
      } catch (e: any) {
        // If backend signals unauthorized via error, send to sign-in
        router.push('/sign-in');
      }
    };

    run();
    return () => {
      cancelled = true;
    };
  }, [router, origin]);

  return (
    <div className="w-full mt-24 flex justify-center">
      <div className="flex flex-col items-center gap-2">
        <Loader2 className="h-8 w-8 animate-spin text-zinc-800" />
        <h3 className="font-semibold text-xl">Setting up your account...</h3>
        <p>You will be redirected automatically.</p>
      </div>
    </div>
  );
};

export default Page;