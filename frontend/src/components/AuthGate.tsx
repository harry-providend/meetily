'use client';

import React from 'react';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { LoginScreen } from './LoginScreen';

/**
 * Renders the app only once a session exists. Gating here keeps the recording,
 * database, and transcript providers from mounting before sign-in.
 *
 * A stored session is enough, even with an expired token, so this does not lock
 * the user out when offline.
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const { isSignedIn, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-gray-50">
        <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
      </div>
    );
  }

  if (!isSignedIn) {
    return <LoginScreen />;
  }

  return <>{children}</>;
}

export default AuthGate;
