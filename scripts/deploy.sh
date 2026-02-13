#!/bin/bash
# Deployment script for AI Corporation

set -e

echo "🚀 Deploying AI Corporation 2.0..."

# Build images
docker-compose build

# Start services
docker-compose up -d

# Wait for services to start
echo "⏳ Waiting for services to start..."
sleep 30

# Check health
if curl -f http://localhost:8000/health; then
    echo "✅ AI Corporation is running!"
    echo "🌐 Web Panel: http://localhost:8080"
    echo "📱 Telegram Bot: @your_bot_username"
else
    echo "❌ Health check failed!"
    exit 1
fi
