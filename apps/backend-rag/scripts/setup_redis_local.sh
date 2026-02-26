#!/bin/bash
# Setup Redis for local development

set -e

echo "🔧 Setting up Redis for Article Composer (local development)"

# Check if Docker is available
if command -v docker &> /dev/null; then
    echo "✅ Docker found"
    
    # Check if Redis container is already running
    if docker ps | grep -q redis; then
        echo "✅ Redis container already running"
        docker ps | grep redis
    else
        echo "🚀 Starting Redis container..."
        docker run -d \
            --name redis-article-composer \
            -p 6379:6379 \
            redis:7-alpine
        
        echo "✅ Redis container started"
        echo "   Connection: redis://localhost:6379/0"
    fi
else
    echo "⚠️  Docker not found"
    echo ""
    echo "Alternative setup options:"
    echo ""
    echo "1. Install Redis locally:"
    echo "   macOS: brew install redis"
    echo "   Ubuntu: sudo apt-get install redis-server"
    echo ""
    echo "2. Start Redis:"
    echo "   redis-server"
    echo ""
    echo "3. Or use cloud Redis service"
fi

echo ""
echo "📋 To verify Redis is working:"
echo "   redis-cli ping"
echo "   # Should return: PONG"
echo ""
echo "📋 To stop Redis container:"
echo "   docker stop redis-article-composer"
echo "   docker rm redis-article-composer"
