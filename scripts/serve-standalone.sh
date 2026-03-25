#!/usr/bin/env bash
#
# serve-standalone.sh - Serve the bundled frontend from dist directory
#
# This script serves the pre-built Next.js frontend from dist/frontend
# without requiring Docker or the full backend stack.
#
# Usage:
#   ./scripts/serve-standalone.sh          # Start on default port 3000
#   ./scripts/serve-standalone.sh --port 8080  # Custom port

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PORT=3000
for arg in "$@"; do
    case "$arg" in
        --port)
            PORT="$2"
            shift 2
            ;;
        --port=*)
            PORT="${arg#*=}"
            ;;
        --help)
            echo "Usage: $0 [--port PORT]"
            echo "  --port PORT  Port to serve on (default: 3000)"
            exit 0
            ;;
    esac
done

FRONTEND_DIST="$REPO_ROOT/dist/frontend"

# Check if frontend is built
if [ ! -d "$FRONTEND_DIST" ]; then
    echo "Frontend not found at $FRONTEND_DIST"
    echo "Run ./scripts/build-frontend.sh first"
    exit 1
fi

if [ ! -d "$FRONTEND_DIST/.next" ]; then
    echo "Next.js build not found at $FRONTEND_DIST/.next"
    echo "Run ./scripts/build-frontend.sh first"
    exit 1
fi

echo "Starting standalone frontend server on port $PORT..."
echo "Frontend: $FRONTEND_DIST"
echo ""

cd "$FRONTEND_DIST"
BETTER_AUTH_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(16))')" pnpm start --port "$PORT"