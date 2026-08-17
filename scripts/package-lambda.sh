#!/usr/bin/env bash
#
# package-lambda.sh — Build the Lambda deployment zip.
#
# Creates lambda.zip at the project root containing:
#   - Production Python dependencies
#   - The src/nutritrack/ application code
#
# Usage:
#   ./scripts/package-lambda.sh
#
# Prerequisites:
#   - Python 3.12+ and pip
#   - zip command

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/.lambda-build"
ZIP_FILE="$PROJECT_ROOT/lambda.zip"

echo "==> Cleaning previous build..."
rm -rf "$BUILD_DIR"
rm -f "$ZIP_FILE"

echo "==> Installing production dependencies..."
mkdir -p "$BUILD_DIR"
pip install \
  --target "$BUILD_DIR" \
  --platform manylinux2014_aarch64 \
  --implementation cp \
  --python-version 3.12 \
  --only-binary=:all: \
  boto3 2>/dev/null || \
python3 -m pip install --target "$BUILD_DIR" boto3

echo "==> Copying application code..."
cp -r "$PROJECT_ROOT/src/nutritrack" "$BUILD_DIR/nutritrack"

echo "==> Removing __pycache__ directories..."
find "$BUILD_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

echo "==> Creating lambda.zip..."
cd "$BUILD_DIR"
zip -r "$ZIP_FILE" . -x "*.pyc" "*.pyo" > /dev/null

echo "==> Cleaning up build directory..."
rm -rf "$BUILD_DIR"

ZIP_SIZE=$(du -h "$ZIP_FILE" | cut -f1)
echo "==> Done! Lambda package: $ZIP_FILE ($ZIP_SIZE)"
