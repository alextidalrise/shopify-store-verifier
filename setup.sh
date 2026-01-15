#!/bin/bash

# Shopify Verifier Setup Script

echo "=========================================="
echo "Shopify Store Verifier - Setup"
echo "=========================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.10 or higher."
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"
echo ""

# Create virtual environment (optional but recommended)
read -p "Create a virtual environment? (recommended) [Y/n]: " create_venv
create_venv=${create_venv:-Y}

if [[ $create_venv =~ ^[Yy]$ ]]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    
    echo "Activating virtual environment..."
    source venv/bin/activate
    
    echo "✓ Virtual environment created and activated"
    echo ""
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Failed to install Python dependencies"
    exit 1
fi

echo "✓ Python dependencies installed"
echo ""

# Install Playwright browsers
echo "Installing Playwright browsers (this may take a few minutes)..."
playwright install chromium

if [ $? -ne 0 ]; then
    echo "❌ Failed to install Playwright browsers"
    exit 1
fi

echo "✓ Playwright browsers installed"
echo ""

# Create results directory
mkdir -p results
echo "✓ Created results directory"
echo ""

echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Quick test with sample stores:"
echo "   python quick_start.py"
echo ""
echo "2. Batch process your own stores:"
echo "   - Create a text file with store URLs (one per line)"
echo "   - Run: python batch_verifier.py"
echo ""
echo "3. Read the README for more details:"
echo "   cat README.md"
echo ""

if [[ $create_venv =~ ^[Yy]$ ]]; then
    echo "Note: To activate the virtual environment in future sessions:"
    echo "      source venv/bin/activate"
    echo ""
fi

echo "=========================================="
