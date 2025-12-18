#!/bin/bash
# Setup script for Peraturan Spider

set -e

echo "🚀 Setting up Peraturan Spider..."

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p data/raw_laws
mkdir -p logs

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Install Playwright browsers
echo "🌐 Installing Playwright browsers..."
playwright install chromium

echo "✅ Setup complete!"
echo ""
echo "To test the scraper, run:"
echo "  python peraturan_spider.py --test"
echo ""
echo "To scrape documents, run:"
echo "  python peraturan_spider.py --limit 100"
