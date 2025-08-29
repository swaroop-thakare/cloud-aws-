#!/bin/bash

# Start Script for AI Document Processing App on EC2

echo "🚀 Starting AI Document Processing App..."

# Navigate to project directory
cd ~/ai-document-processing

# Activate virtual environment
source venv/bin/activate

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "Please create .env file with your AWS credentials:"
    echo "cp env_example.txt .env"
    echo "nano .env"
    exit 1
fi

# Check if AWS credentials are set
if ! grep -q "AWS_ACCESS_KEY_ID" .env || ! grep -q "AWS_SECRET_ACCESS_KEY" .env; then
    echo "⚠️  AWS credentials not found in .env file"
    echo "Please edit .env file with your AWS credentials"
    echo "nano .env"
    exit 1
fi

echo "✅ Environment configured"
echo "🌐 Starting Streamlit app on port 8501..."
echo "📱 Access the app at: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8501"

# Start Streamlit app
streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
