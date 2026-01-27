#!/bin/bash

# setup_ml_pipeline.sh
# Automates the setup of the sports prediction ML pipeline.

echo "=================================================="
echo "   Sports Prediction Model - Pipeline Setup"
echo "=================================================="

# Check if we are in the right directory
if [ ! -d "backend" ]; then
    echo "Error: Please run this script from the project root (where 'backend' folder is)."
    exit 1
fi

cd backend

echo ""
echo "[1/4] Setting up Virtual Environment..."

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# We use the explicit path to ensure we use the venv python
VENV_PYTHON="./venv/bin/python"
VENV_PIP="./venv/bin/pip"

echo "Using Python: $VENV_PYTHON"
$VENV_PYTHON --version

echo ""
echo "[1.5/4] Installing Dependencies..."
echo "        Installing requirements (may take a moment)..."
# Upgrade pip first
$VENV_PIP install --upgrade pip
# Install requirements, allowing continue on error (for sportsreference)
$VENV_PIP install -r requirements.txt || echo "Warning: Some packages failed to install, continuing..."

echo ""
echo "[2/4] Backfilling Historical Data..."
echo "      This may take a while depending on date range..."
# Run from backend/ directory as module using venv python
$VENV_PYTHON -m scripts.backfill_nba_data

echo ""
echo "[3/4] Training Models..."

echo "      Training Game Outcome Models (Win/Loss)..."
$VENV_PYTHON -m ml.training.train_all_sports

echo "      Training Player Prop Models (Pts, Reb, Ast)..."
$VENV_PYTHON -m ml.training.train_props

echo ""
echo "[4/4] Generating Initial Predictions..."
# Run one-liners
$VENV_PYTHON -c "import asyncio; from app.services.prediction_service import update_predictions; asyncio.run(update_predictions())"
$VENV_PYTHON -c "import asyncio; from app.services.prediction_service import generate_prop_predictions; asyncio.run(generate_prop_predictions())"

echo ""
echo "=================================================="
echo "   Pipeline Setup Complete!"
echo "=================================================="
echo "Models are trained and saved in backend/ml/saved_models/"
echo "Predictions have been generated in the database."
echo ""
echo "To start the application:"
echo "1. Backend:  cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
echo "2. Frontend: cd frontend && npm run dev"
echo "3. Worker:   cd backend && source venv/bin/activate && celery -A app.core.celery_app worker --loglevel=info"
