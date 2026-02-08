#!/usr/bin/env bash
# Build the React dashboard and copy into the backend static directory
# Run from the repo root: ./scripts/build-dashboard.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DASHBOARD_SRC="$REPO_ROOT/services/dashboard"
DASHBOARD_DEST="$REPO_ROOT/decisiongraph-complete/service/static/dashboard"

echo "=== Building DecisionGraph Dashboard ==="
echo "Source:  $DASHBOARD_SRC"
echo "Output:  $DASHBOARD_DEST"

# Install dependencies
cd "$DASHBOARD_SRC"
npm ci --silent 2>/dev/null || npm install --silent

# Build
npx vite build --outDir "$DASHBOARD_DEST" --emptyOutDir

echo ""
echo "=== Dashboard built successfully ==="
ls -la "$DASHBOARD_DEST/"
ls -la "$DASHBOARD_DEST/assets/"
echo ""
echo "Commit the built files and push to deploy:"
echo "  git add decisiongraph-complete/service/static/dashboard/"
echo "  git commit -m 'build: update dashboard SPA'"
echo "  git push"
