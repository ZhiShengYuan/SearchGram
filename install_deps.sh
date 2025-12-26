#!/bin/bash
#
# Install SearchGram dependencies including HTTP/2 support
#
# This script installs all required Python packages from requirements.txt
#

set -e  # Exit on error

echo "=========================================="
echo "Installing SearchGram Dependencies"
echo "=========================================="
echo ""

# Check if pip3 is available
if ! command -v pip3 &> /dev/null; then
    echo "Error: pip3 not found. Please install Python 3 and pip first."
    exit 1
fi

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo "Error: requirements.txt not found!"
    echo "Please run this script from the SearchGram root directory."
    exit 1
fi

echo "Installing packages from requirements.txt..."
echo ""

# Try different installation methods based on the system
if pip3 install -r requirements.txt 2>/dev/null; then
    echo "✓ Packages installed successfully"
elif pip3 install --user -r requirements.txt 2>/dev/null; then
    echo "✓ Packages installed successfully (user mode)"
elif pip3 install --break-system-packages -r requirements.txt 2>/dev/null; then
    echo "✓ Packages installed successfully (system override)"
else
    echo ""
    echo "Standard installation methods failed."
    echo ""
    echo "Please try one of the following options:"
    echo ""
    echo "1. Use a virtual environment (recommended):"
    echo "   python3 -m venv venv"
    echo "   source venv/bin/activate"
    echo "   pip install -r requirements.txt"
    echo ""
    echo "2. Check permissions and try again"
    echo ""
    echo "3. Use pipx or conda if available"
    echo ""
    exit 1
fi

echo ""
echo "Verifying installation..."
echo ""

# Verify httpx installation
if python3 -c "import httpx; print(f'httpx version: {httpx.__version__}')" 2>/dev/null; then
    echo "✓ httpx installed correctly"
else
    echo "✗ httpx verification failed"
    exit 1
fi

# Verify h2 installation
if python3 -c "import h2; print(f'h2 version: {h2.__version__}')" 2>/dev/null; then
    echo "✓ h2 installed correctly"
else
    echo "✗ h2 verification failed"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ All Dependencies Installed Successfully"
echo "=========================================="
echo ""
echo "HTTP/2 support is ready!"
echo ""
echo "Next steps:"
echo "  1. Rebuild Go service:"
echo "     cd searchgram-engine && go build"
echo ""
echo "  2. Test HTTP/2 connection:"
echo "     python3 test_http2_standalone.py"
echo ""
echo "  3. Start SearchGram:"
echo "     python3 searchgram/client.py"
echo "     python3 searchgram/bot.py"
echo ""
