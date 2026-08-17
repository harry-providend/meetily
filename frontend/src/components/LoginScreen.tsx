'use client';

import React from 'react';
import Image from 'next/image';
import { Loader2, AlertTriangle } from 'lucide-react';
import { Button } from './ui/button';
import { EnvironmentBadge } from './EnvironmentBadge';
import { useAuth } from '@/contexts/AuthContext';

/**
 * Sign-in happens in the system browser, not an embedded webview, so the user
 * sees the real Microsoft origin and tenant MFA applies.
 */
export function LoginScreen() {
  const { signIn, isSigningIn, error, session } = useAuth();
  const notConfigured = session ? !session.configured : false;

  return (
    <div className="flex h-screen w-full items-center justify-center bg-gray-50 p-6">
      <div className="w-full max-w-sm text-center">
        <Image
          src="/logo.png"
          alt="Providend Meeting Assistant"
          width={845}
          height={295}
          priority
          className="mx-auto mb-6 h-auto w-48"
        />

        <div className="flex items-center justify-center gap-2">
          <h1 className="text-lg font-semibold text-gray-900">Providend Meeting Assistant</h1>
          <EnvironmentBadge />
        </div>
        <p className="mt-2 text-sm text-gray-600">
          Sign in with your Providend account to continue.
        </p>

        {notConfigured ? (
          <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-4 text-left">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
              <div>
                <p className="text-sm font-medium text-amber-900">Sign-in is not configured</p>
                <p className="mt-1 text-xs text-amber-800">
                  This build has no Entra tenant or client ID. Set{' '}
                  <code className="font-mono">MEETILY_AUTH_TENANT_ID</code> and{' '}
                  <code className="font-mono">MEETILY_AUTH_CLIENT_ID</code>, or fill them into{' '}
                  <code className="font-mono">src/auth/config.rs</code>.
                </p>
              </div>
            </div>
          </div>
        ) : (
          <Button
            onClick={signIn}
            disabled={isSigningIn}
            className="mt-6 w-full bg-gray-900 text-white hover:bg-gray-800"
          >
            {isSigningIn ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Waiting for browser...
              </>
            ) : (
              'Sign in with Microsoft'
            )}
          </Button>
        )}

        {isSigningIn && (
          <p className="mt-3 text-xs text-gray-500">
            A browser window has opened. Complete sign-in there, then return here.
          </p>
        )}

        {error && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-left">
            <p className="text-xs text-red-800 break-words">{error}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default LoginScreen;
