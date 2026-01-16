#!/bin/bash
# Start Backend - Local Mac Version (Fixed v4 - with .env loading)

# Get the script's directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "📍 Working directory: $(pwd)"
echo ""

# Load .env file if it exists
if [ -f ".env" ]; then
    echo "📄 Loading environment variables from .env..."
    export $(grep -v '^#' .env | xargs)
    echo "✅ Environment loaded"
    echo ""
fi

# Remove and recreate venv if it's corrupted
if [ -d ".venv" ] && [ ! -f ".venv/bin/pip" ]; then
    echo "⚠️  Virtual environment corrupted, recreating..."
    rm -rf .venv
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "🔧 Creating fresh virtual environment..."
    python3 -m venv .venv

    # Verify it was created properly
    if [ ! -f ".venv/bin/pip" ]; then
        echo "❌ Failed to create virtual environment!"
        echo "   Trying with system python3..."
        /usr/bin/python3 -m venv .venv
    fi
fi

echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Verify we're using venv python
echo "🐍 Using Python: $(which python)"
echo "📦 Using Pip: $(which pip)"
echo ""

# Only install if needed
if [ ! -f ".venv/bin/uvicorn" ]; then
    echo "📦 Installing dependencies in virtual environment..."
    echo "   This will take 10-15 minutes on first run..."
    echo ""

    # Upgrade pip first
    python -m pip install --upgrade pip

    # Install dependencies
    pip install -r requirements-prod.txt

    echo ""
    echo "✅ Dependencies installed!"
    echo ""
else
    echo "✅ Dependencies already installed (skipping)"
    echo ""
fi

# Verify uvicorn is installed
if ! command -v uvicorn &> /dev/null; then
    echo "⚠️  Uvicorn missing, installing explicitly..."
    pip install "uvicorn[standard]>=0.30.0"
fi

echo "🚀 Starting backend on http://localhost:8080"
echo "📝 Logs will appear below..."
echo "⏹️  Press Ctrl+C to stop"
echo ""

export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
cd backend

# Use uvicorn from activated venv
uvicorn app.main_cloud:app --host 0.0.0.0 --port 8080 --reload
