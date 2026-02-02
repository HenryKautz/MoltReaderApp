#!/bin/bash
set -e

echo "Installing Python dependencies..."
pip install -r requirements_web.txt

echo "Installing Playwright browsers..."
playwright install chromium
playwright install-deps chromium

echo "Build complete!"
