#!/bin/bash

# Script to create GitHub repository and push code

echo "=========================================="
echo "Creating GitHub Repository"
echo "=========================================="
echo ""

# Check if already authenticated
if ! gh auth status &> /dev/null; then
    echo "Not authenticated with GitHub CLI."
    echo "Please run: gh auth login"
    echo ""
    exit 1
fi

echo "✓ GitHub CLI authenticated"
echo ""

# Create repository
echo "Creating repository 'shopify-store-verifier'..."
gh repo create shopify-store-verifier \
    --public \
    --source=. \
    --description "Production-ready web scraper for verifying Shopify stores' multi-currency support and post-purchase upsells at scale" \
    --push

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✓ Repository created successfully!"
    echo "=========================================="
    echo ""
    echo "Your repository is now available at:"
    gh repo view --web --json url -q .url 2>/dev/null || echo "https://github.com/$(gh api user -q .login)/shopify-store-verifier"
    echo ""
    echo "Next steps:"
    echo "  - View on GitHub: gh repo view --web"
    echo "  - Clone elsewhere: git clone https://github.com/$(gh api user -q .login)/shopify-store-verifier"
    echo ""
else
    echo ""
    echo "❌ Failed to create repository"
    echo ""
    echo "Alternative: Create repository manually"
    echo "1. Go to https://github.com/new"
    echo "2. Name: shopify-store-verifier"
    echo "3. Make it public"
    echo "4. Don't initialize with README (we already have files)"
    echo "5. Create repository"
    echo "6. Then run:"
    echo "   git remote add origin https://github.com/YOUR_USERNAME/shopify-store-verifier.git"
    echo "   git push -u origin main"
    echo ""
fi
