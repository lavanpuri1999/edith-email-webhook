#!/bin/bash
# Script to run edith-gmail-webhook locally

set -e

echo "🚀 Starting Gmail Webhook Service Locally"
echo ""

# Navigate to webhook directory
cd "$(dirname "$0")"

# Step 1: Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Step 2: Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Step 3: Install/upgrade dependencies
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Step 4: Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "   Please create .env file with:"
    echo "   - DATABASE_URL"
    echo "   - CELERY_BROKER_URL"
    echo "   - TOKEN_ENCRYPTION_KEY"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Step 5: Test connections (optional)
if [ -f "test_connection.py" ]; then
    echo "🧪 Testing connections..."
    python test_connection.py || echo "⚠️  Connection test failed, but continuing..."
    echo ""
fi

# Step 6: Start the service
echo "🌟 Starting webhook service on http://localhost:8001"
echo "   Press Ctrl+C to stop"
echo ""
python main.py

