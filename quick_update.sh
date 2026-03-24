#!/bin/bash

# Quick Update for Sports Model
# Updates code WITHOUT killing the Cloudflare Tunnel

set -e

# Interactive Setup
echo "========================================"
echo "  Sports Model: Quick Update"
echo "  (Preserves Tunnel URL)"
echo "========================================"
echo ""

# Ensure we are in the project directory
cd "$(dirname "$0")"

# Ask for Username
read -p "Enter Raspberry Pi username (default: max): " PI_USER
PI_USER=${PI_USER:-max}

# Ask for Hostname or IP
read -p "Enter Raspberry Pi IP or Hostname (default: 192.168.1.254): " PI_ADDRESS
PI_ADDRESS=${PI_ADDRESS:-192.168.1.254}

PI_HOST="$PI_USER@$PI_ADDRESS"
REMOTE_BASE="sports_model_app"

echo ""
echo "=== 1. Uploading New Code ==="
echo "Copying files..."
scp -r backend frontend docker-compose.yml "$PI_HOST:~/$REMOTE_BASE/"

echo ""
echo "=== 2. Refreshing App Container ==="
ssh "$PI_HOST" << EOF
    cd ~/$REMOTE_BASE
    
    # Rebuild and restart services (excluding tunnel/db/redis to save time/state if possible)
    # Actually, safely rebuilding backend and frontend is best.
    echo "Swapping out application code..."
    docker compose up -d --no-deps --build backend frontend
EOF

echo ""
echo "============================================"
echo "  SUCCESS! Code updated."
echo "============================================"
