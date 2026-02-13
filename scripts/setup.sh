#!/bin/bash
# Setup script for AI Corporation

set -e

echo "🤖 Setting up AI Corporation 2.0..."

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create data directories
mkdir -p data/{models,cache,outputs}
mkdir -p logs

# Copy environment file
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️  Please edit .env with your configuration"
fi

# Pull base models
echo "📥 Pulling base models..."
ollama pull deepseek-coder:1.3b-q4_K_M

echo "✅ Setup completed!"
echo "🚀 Run: docker-compose up -d"
