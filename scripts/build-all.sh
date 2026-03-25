#!/usr/bin/env bash
#
# build-all.sh - Build all components (frontend + backend)
#
# Usage:
#   ./scripts/build-all.sh              # Build everything to dist directory
#   ./scripts/build-all.sh --frontend   # Build only frontend
#   ./scripts/build-all.sh --clean      # Clean dist first
#
# Output:
#   dist/deer-flow/   - deer-flow Next.js production build

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DIST_DIR="$REPO_ROOT/dist"
BUILD_FRONTEND=true

# Parse arguments
CLEAN=false
for arg in "$@"; do
    case "$arg" in
        --clean) CLEAN=true ;;
        --frontend) BUILD_FRONTEND=true ;;
        --help)
            echo "Usage: $0 [--clean] [--frontend]"
            echo "  --clean    Clean dist directory before building"
            echo "  --frontend Build only frontend"
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

# Build frontend
if $BUILD_FRONTEND; then
    echo "=========================================="
    echo "  Building deer-flow Frontend"
    echo "=========================================="
    echo ""
    ./scripts/build-frontend.sh
    echo ""
fi

echo "=========================================="
echo "  Build Summary"
echo "=========================================="
echo ""
echo "  deer-flow Frontend: $DIST_DIR/deer-flow"
echo "  Next.js build: $DIST_DIR/deer-flow/.next"
echo ""
echo "To serve the frontend standalone:"
echo "  cd $DIST_DIR/deer-flow"
echo "  BETTER_AUTH_SECRET=<secret> pnpm start"
echo ""
echo "Or use nginx to proxy to your backend services."