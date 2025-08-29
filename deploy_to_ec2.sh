#!/bin/bash

# Deploy to EC2 Script
# Usage: ./deploy_to_ec2.sh <EC2_IP> <KEY_FILE>

if [ $# -ne 2 ]; then
    echo "Usage: $0 <EC2_IP> <KEY_FILE>"
    echo "Example: $0 52.23.45.67 ~/.ssh/my-key.pem"
    exit 1
fi

EC2_IP=$1
KEY_FILE=$2

echo "🚀 Deploying to EC2 instance: $EC2_IP"

# Check if key file exists
if [ ! -f "$KEY_FILE" ]; then
    echo "❌ Key file not found: $KEY_FILE"
    exit 1
fi

# Create deployment package
echo "📦 Creating deployment package..."
mkdir -p deploy_temp
cp streamlit_app.py deploy_temp/
cp requirements.txt deploy_temp/
cp env_example.txt deploy_temp/
cp README_FA1.md deploy_temp/

# Copy to EC2
echo "📤 Copying files to EC2..."
scp -i "$KEY_FILE" -r deploy_temp/* ec2-user@$EC2_IP:~/ai-document-processing/

# Run setup commands on EC2
echo "🔧 Running setup on EC2..."
ssh -i "$KEY_FILE" ec2-user@$EC2_IP << 'EOF'
    cd ~/ai-document-processing
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Install dependencies
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # Create .env file if it doesn't exist
    if [ ! -f ".env" ]; then
        cp env_example.txt .env
        echo "⚠️  Please edit .env file with your AWS credentials"
    fi
    
    # Make startup script executable
    chmod +x start_app.sh
    
    echo "✅ Deployment completed!"
    echo "📝 Next steps:"
    echo "1. Edit .env file with your AWS credentials:"
    echo "   nano .env"
    echo "2. Start the app:"
    echo "   ./start_app.sh"
    echo "3. Access at: http://$EC2_IP:8501"
EOF

# Clean up
rm -rf deploy_temp

echo "✅ Deployment completed!"
echo "🌐 Access your app at: http://$EC2_IP:8501"
echo "📝 Don't forget to:"
echo "   1. Configure EC2 security group to allow port 8501"
echo "   2. Edit .env file on EC2 with your AWS credentials"
