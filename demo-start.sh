#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# ZTP-Demo: Mock-BMC + KI-Layer starten
# Voraussetzung: docker compose up -d läuft bereits
# ──────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")"

MOCK_PORT=18888
SCENARIOS=(normal temp_warning temp_critical fan_failure sel_critical post_error normal)
PAUSE=12   # Sekunden pro Szenario

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   ZTP-KI-Framework  Demo                     ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "→ Grafana:    http://localhost:3000  (admin / change-me-grafana-admin)"
echo "→ Prometheus: http://localhost:9090"
echo "→ Metriken:   http://localhost:8888/metrics"
echo ""

# ── 1. Mock-BMC im Hintergrund starten ──
echo "[1/2] Starte Mock-BMC auf Port $MOCK_PORT ..."
python3 -c "
import threading, uvicorn, sys
from tests.mock_bmc.server import app
config = uvicorn.Config(app, host='127.0.0.1', port=$MOCK_PORT, log_level='error')
server = uvicorn.Server(config)
threading.Thread(target=server.run, daemon=True).start()
import time; time.sleep(1)
print('Mock-BMC läuft.')
# Halte den Prozess am Leben — wird von KI-Layer-Prozess übernommen
time.sleep(999999)
" &
MOCK_PID=$!
sleep 1.5

# ── 2. KI-Layer starten ──
echo "[2/2] Starte KI-Layer (Metriken auf :8888) ..."
python3 -m ki.main ki/config-demo.yaml &
KI_PID=$!

cleanup() {
  echo ""
  echo "Demo beendet."
  kill $MOCK_PID $KI_PID 2>/dev/null || true
}
trap cleanup EXIT INT TERM

sleep 2
echo ""
echo "Alles läuft. Szenarien werden alle ${PAUSE}s gewechselt."
echo "Strg+C zum Beenden."
echo ""

# ── 3. Szenarien durchrotieren ──
IDX=0
while true; do
  SCENARIO="${SCENARIOS[$IDX % ${#SCENARIOS[@]}]}"
  echo "  → Szenario: $SCENARIO"
  curl -s -X POST "http://127.0.0.1:$MOCK_PORT/control/scenario/$SCENARIO" > /dev/null
  sleep $PAUSE
  IDX=$((IDX + 1))
done
