#!/bin/bash
# ─────────────────────────────────────────────────────────────────
#  Facebook Auto-Reply Bot — start Flask + ngrok together
# ─────────────────────────────────────────────────────────────────
cd "$(dirname "$0")"
source venv/bin/activate

# Kill any leftover processes on port 5000
fuser -k 5000/tcp 2>/dev/null

echo "Starting Flask server..."
python app.py &
FLASK_PID=$!

sleep 2

echo "Starting ngrok tunnel..."
~/.local/bin/ngrok http 5000 --log=stdout &
NGROK_PID=$!

sleep 3

# Fetch the public URL from ngrok's local API
PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "
import sys, json
data = json.load(sys.stdin)
tunnels = data.get('tunnels', [])
for t in tunnels:
    if t.get('proto') == 'https':
        print(t['public_url'])
        break
")

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  Flask running at : http://localhost:5000"
echo "  Public HTTPS URL : $PUBLIC_URL"
echo "  Webhook URL      : $PUBLIC_URL/webhook"
echo "  Verify Token     : my_secret_verify_token_2024"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Press Ctrl+C to stop everything."

# Cleanup on exit
trap "kill $FLASK_PID $NGROK_PID 2>/dev/null; echo 'Stopped.'" EXIT INT TERM
wait
