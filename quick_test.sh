#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
echo "🧪 Running quick AI test..."
python advanced_test.py
echo ""
echo "🏥 Checking backend health..."
curl -s http://localhost:8000/health | python -m json.tool || echo "Backend not running"
