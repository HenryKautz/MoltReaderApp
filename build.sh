#!/bin/bash
set -e

echo "Installing Python dependencies..."
pip install -r requirements_web.txt

echo "Installing Playwright Chromium browser..."
playwright install chromium

echo "Build complete!"
