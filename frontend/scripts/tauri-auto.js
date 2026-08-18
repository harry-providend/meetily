#!/usr/bin/env node
/**
 * Auto-detect GPU and run Tauri with appropriate features
 */

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

// Get the command (dev or build)
const command = process.argv[2];
if (!command || !['dev', 'build'].includes(command)) {
  console.error('Usage: node tauri-auto.js [dev|build] [dev|staging|prod]');
  process.exit(1);
}

// `dev` runs default to the dev environment so a local run cannot touch production data;
// builds default to prod so an unqualified release build is the expected artifact.
const ENVIRONMENTS = ['dev', 'staging', 'prod'];
const targetEnv =
  process.argv[3] || process.env.MEETILY_ENV || (command === 'dev' ? 'dev' : 'prod');

if (!ENVIRONMENTS.includes(targetEnv)) {
  console.error(
    `Unknown environment '${targetEnv}'. Expected one of: ${ENVIRONMENTS.join(', ')}`
  );
  process.exit(1);
}

// Prod lives in the base tauri.conf.json; the others merge an overlay that
// changes the bundle identifier, which is what isolates their data directories.
const configArg =
  targetEnv === 'prod' ? '' : ` --config src-tauri/tauri.${targetEnv}.conf.json`;

// Detect GPU feature
let feature = '';

// Check for environment variable override first
if (process.env.TAURI_GPU_FEATURE) {
  feature = process.env.TAURI_GPU_FEATURE;
  console.log(`🔧 Using forced GPU feature from environment: ${feature}`);
} else {
  try {
    const result = execSync('node scripts/auto-detect-gpu.js', {
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'inherit']
    });
    feature = result.trim();
  } catch (err) {
    // If detection fails, continue with no features
  }
}

console.log(''); // Empty line for spacing

// Platform-specific environment variables
const platform = os.platform();
const env = { ...process.env };

if (platform === 'linux' && feature === 'cuda') {
  console.log('🐧 Linux/CUDA detected: Setting CMAKE flags for NVIDIA GPU');
  env.CMAKE_CUDA_ARCHITECTURES = '75';
  env.CMAKE_CUDA_STANDARD = '17';
  env.CMAKE_POSITION_INDEPENDENT_CODE = 'ON';
}

// Build the tauri command. --config is a Tauri CLI argument so it must precede
// the `--` that forwards the rest to cargo.
let tauriCmd = `tauri ${command}${configArg}`;
if (feature && feature !== 'none') {
  tauriCmd += ` -- --features ${feature}`;
  console.log(
    `🚀 Running: tauri ${command} [env: ${targetEnv}] with features: ${feature}`
  );
} else {
  console.log(`🚀 Running: tauri ${command} [env: ${targetEnv}] (CPU-only mode)`);
}
console.log('');

// Execute the command
try {
  execSync(tauriCmd, { stdio: 'inherit', env });
} catch (err) {
  process.exit(err.status || 1);
}
