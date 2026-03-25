#!/usr/bin/env bash
#
# build-frontend.sh - Build deer-flow frontend to dist/deer-flow directory
#
# Usage:
#   ./scripts/build-frontend.sh          # Build to dist/deer-flow
#   ./scripts/build-frontend.sh --clean # Clean dist first
#
# Output:
#   dist/deer-flow/ - Next.js production build

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DIST_DIR="$REPO_ROOT/dist"
DEERFLOW_DIST="$DIST_DIR/deer-flow"

# Parse arguments
CLEAN=false
for arg in "$@"; do
    case "$arg" in
        --clean) CLEAN=true ;;
        --help)
            echo "Usage: $0 [--clean]"
            echo "  --clean  Clean dist directory before building"
            exit 0
            ;;
    esac
done

# Clean if requested
if $CLEAN; then
    echo "Cleaning dist directory..."
    rm -rf "$DIST_DIR"
fi

# Create dist directory
mkdir -p "$DIST_DIR"

# Check if deer-flow exists
if [ ! -d "$REPO_ROOT/deer-flow" ]; then
    echo "Error: deer-flow directory not found at $REPO_ROOT/deer-flow"
    exit 1
fi

# Check frontend dependencies
if [ ! -d "$REPO_ROOT/deer-flow/frontend/node_modules" ]; then
    echo "Installing deer-flow frontend dependencies..."
    cd "$REPO_ROOT/deer-flow/frontend"
    pnpm install
    cd "$REPO_ROOT"
fi

# Build deer-flow frontend
echo "Building deer-flow frontend..."
cd "$REPO_ROOT/deer-flow/frontend"
SKIP_ENV_VALIDATION=1 pnpm build

# Create deer-flow dist directory
mkdir -p "$DEERFLOW_DIST"

# Move build to dist/deer-flow
echo "Moving build to dist/deer-flow..."
mv "$REPO_ROOT/deer-flow/frontend/.next" "$DEERFLOW_DIST/"

# Copy public directory if it exists
if [ -d "$REPO_ROOT/deer-flow/frontend/public" ]; then
    cp -r "$REPO_ROOT/deer-flow/frontend/public" "$DEERFLOW_DIST/" 2>/dev/null || true
fi

echo ""
echo "=========================================="
echo "  deer-flow frontend build complete!"
echo "=========================================="
echo ""
echo "  Output: $DEERFLOW_DIST"
echo ""
echo "  To serve (requires backend services):"
echo "    cd $DEERFLOW_DIST"
echo "    BETTER_AUTH_SECRET=<your-secret> pnpm start"
echo ""