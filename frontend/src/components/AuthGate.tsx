'use client';

import React from 'react';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { LoginScreen } from './LoginScreen';

/**
 * Renders the app only once a session exists, otherwise the sign-in screen.
 *
 * Gating here rather than inside the app means none of the recording, database,
 * or transcript providers mount before sign-in.
 *
 * A *stored* session is enough — Rust treats an expired access token as still
 * signed in and refreshes opportunistically — so this does not lock the user out
 * when they are offline mid-meeting.
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
