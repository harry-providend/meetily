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
  /** Refresh is due. The app stays usable regardless. */
  needs_refresh: boolean;
  /** False when the build has no Entra IDs configured. */
  configured: boolean;
}

/**
 * Tokens never cross this boundary — they stay in the OS keychain, read only by
 * Rust. Anything in the webview is reachable by any script running there.
 */
export const authService = {
  /** Refreshes if due. Safe to call on every start. */
  async getSession(): Promise<SessionInfo> {
    return invoke<SessionInfo>('auth_get_session');
  },

  /** Opens the system browser and completes the interactive sign-in. */
  async signIn(): Promise<SessionInfo> {
    return invoke<SessionInfo>('auth_sign_in');
  },

  /** Local meetings and recordings are untouched. */
  async signOut(): Promise<SessionInfo> {
    return invoke<SessionInfo>('auth_sign_out');
  },
};

/** Best available display name for a signed-in user. */
export function displayName(account: Account | null): string {
  if (!account) return 'Unknown user';
  return account.name || account.username || account.oid;
}
