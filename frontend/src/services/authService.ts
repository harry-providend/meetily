import { invoke } from '@tauri-apps/api/core';

export interface Account {
  oid: string;
  tid: string;
  name: string | null;
  username: string | null;
}

export interface SessionInfo {
  signed_in: boolean;
  account: Account | null;
  /** Access token is due for renewal. Informational only — the app stays usable. */
  needs_refresh: boolean;
  /** False when the Entra tenant/client IDs have not been configured in the build. */
  configured: boolean;
}

/**
 * Sign-in state, as reported by Rust.
 *
 * Access and refresh tokens deliberately never cross this boundary — they live
 * in the OS keychain and are only read inside Rust. Anything in the webview is
 * reachable by any script running there.
 */
export const authService = {
  /** Current state. Attempts a token refresh if one is due; safe on every start. */
  async getSession(): Promise<SessionInfo> {
    return invoke<SessionInfo>('auth_get_session');
  },

  /** Opens the system browser and completes the interactive sign-in. */
  async signIn(): Promise<SessionInfo> {
    return invoke<SessionInfo>('auth_sign_in');
  },

  /** Clears the stored session. Local meetings and recordings are untouched. */
  async signOut(): Promise<SessionInfo> {
    return invoke<SessionInfo>('auth_sign_out');
  },
};

/** Best available display name for a signed-in user. */
export function displayName(account: Account | null): string {
  if (!account) return 'Unknown user';
  return account.name || account.username || account.oid;
}
