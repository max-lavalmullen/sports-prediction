#!/bin/bash

# Deploy Sports Model to Raspberry Pi (Docker + Tunnel)

set -e

# Interactive Setup
echo "========================================"
echo "  Sports Model Deployment"
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
echo "Target: $PI_HOST"
echo "----------------------------------------"
read -p "Press Enter to start deployment (or Ctrl+C to cancel)..."

echo ""
echo "=== 1. Preparing files on Pi ==="
ssh "$PI_HOST" "mkdir -p ~/$REMOTE_BASE"

echo "Copying files (skipping heavy folders)..."
# Use rsync to efficiently upload only source files
rsync -avz --exclude 'node_modules' --exclude 'venv' --exclude '.git' --exclude '.DS_Store' \
    ./ "$PI_HOST:~/$REMOTE_BASE/"

echo ""
echo "=== 2. Launching Docker Stack on Pi ==="
ssh "$PI_HOST" << EOF
    cd ~/$REMOTE_BASE
    
    # Aggressive cleanup
    docker compose down --remove-orphans || true
    docker rm -f sports_frontend sports_backend sports_db sports_redis sports_tunnel || true

    # Start the stack
    echo "Starting services..."
    docker compose up -d --build
EOF

echo ""
echo "============================================"
echo "  SUCCESS! Sports Model is running."
echo "  Local Frontend: http://$PI_ADDRESS:3005"
echo "  Local Backend:  http://$PI_ADDRESS:8005"
echo ""
echo "  Tunnel URL:"
echo "  ssh $PI_HOST 'docker logs sports_tunnel 2>&1 | grep trycloudflare.com | tail -n 1'"
echo "============================================"
