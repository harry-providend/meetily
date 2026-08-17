'use client';

import React, { useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';

interface EnvironmentInfo {
  name: string;
  label: string | null;
  is_production: boolean;
}

/**
 * Marks non-production builds. All three environments install side by side, so
 * this is what stops a demo from a dev build. Production renders nothing.
 */
export function EnvironmentBadge() {
  const [env, setEnv] = useState<EnvironmentInfo | null>(null);

  useEffect(() => {
    invoke<EnvironmentInfo>('get_environment')
      .then(setEnv)
      .catch((e) => console.error('Failed to read environment:', e));
  }, []);

  if (!env || env.is_production || !env.label) {
    return null;
  }

  const tone =
    env.name === 'staging'
      ? 'bg-amber-100 text-amber-900 border-amber-300'
      : 'bg-purple-100 text-purple-900 border-purple-300';

  return (
    <span
      className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-semibold tracking-wide ${tone}`}
      title={`Running the ${env.name} environment — separate database, recordings, and sign-in from production`}
    >
      {env.label}
    </span>
  );
}

export default EnvironmentBadge;
