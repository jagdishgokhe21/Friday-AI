#!/bin/zsh
# FRIDAY launcher for macOS — double-click to start her with full computer
# control (write mode) and open the interface in Chrome.
# Close this Terminal window, or press Ctrl-C in it, to stop FRIDAY.

cd "$(dirname "$0")/../.." 2>/dev/null || true
# When copied to the Desktop, fall back to the project's known location.
[ -f package.json ] || cd "$HOME/WEBSITES/Jarvis AI/Friday" || exit 1

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

( for i in {1..40}; do
    curl -s -o /dev/null http://localhost:5173 && break
    sleep 0.5
  done
  open -a "Google Chrome" http://localhost:5173 ) &

npm run start:writes
