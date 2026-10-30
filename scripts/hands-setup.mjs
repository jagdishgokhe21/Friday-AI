// FRIDAY hands setup — makes hands/.venv and installs hands/requirements.txt.
//
// The bridge looks for hands/.venv/bin/python at startup and serves the hands
// MCP server only when it exists, so running this once is what gives FRIDAY
// control of the desktop. Safe to run again: pip skips what is installed.

import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const hands = join(dirname(fileURLToPath(import.meta.url)), '..', 'hands');
const venv = join(hands, '.venv');
const python = join(venv, 'bin', 'python');

function run(cmd, args) {
  console.log(`> ${cmd} ${args.join(' ')}`);
  const res = spawnSync(cmd, args, { stdio: 'inherit', cwd: hands });
  if (res.status !== 0) {
    console.error(`\nFailed: ${cmd} ${args.join(' ')}`);
    process.exit(res.status ?? 1);
  }
}

if (!existsSync(python)) {
  const system = process.platform === 'win32' ? 'python' : 'python3';
  run(system, ['-m', 'venv', venv]);
}
run(python, ['-m', 'pip', 'install', '--upgrade', 'pip']);
run(python, ['-m', 'pip', 'install', '-r', 'requirements.txt']);

// Fetch the speech model now, so the first thing she hears does not wait on it.
run(python, ['-c', "from faster_whisper import WhisperModel; WhisperModel('small.en', device='cpu', compute_type='int8')"]);

console.log('\nHands and hearing ready. Restart the bridge and FRIDAY can reach the desktop.');
console.log('macOS: allow your terminal under System Settings → Privacy & Security →');
console.log('Accessibility and Screen Recording, or typing, clicking and screenshots will fail.');
