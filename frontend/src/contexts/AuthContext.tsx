'use client';

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { authService, type Account, type SessionInfo } from '@/services/authService';

interface AuthContextValue {
  /** null while the initial session check is still running. */
  session: SessionInfo | null;
  account: Account | null;
  isSignedIn: boolean;
  /** True until the first session check settles, so the UI can avoid flashing the login screen. */
  isLoading: boolean;
  /** True while an interactive browser sign-in is in flight. */
  isSigningIn: boolean;
  error: string | null;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSigningIn, setIsSigningIn] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Initial check. A stored session counts as signed in even if its token has
  // expired, so this succeeds offline.
  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const current = await authService.getSession();
        if (!cancelled) setSession(current);
      } catch (e) {
        console.error('Failed to read sign-in state:', e);
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
          // Treat an unreadable keychain as signed out rather than hanging on a
          // loading screen with no way forward.
          setSession({
            signed_in: false,
            account: null,
            needs_refresh: false,
            configured: true,
          });
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async () => {
    setIsSigningIn(true);
    setError(null);
    try {
      setSession(await authService.signIn());
    } catch (e) {
      console.error('Sign-in failed:', e);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setIsSigningIn(false);
    }
  }, []);

  const signOut = useCallback(async () => {
    setError(null);
    try {
      setSession(await authService.signOut());
    } catch (e) {
      console.error('Sign-out failed:', e);
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        session,
        account: session?.account ?? null,
        isSignedIn: session?.signed_in ?? false,
        isLoading,
        isSigningIn,
        error,
        signIn,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
