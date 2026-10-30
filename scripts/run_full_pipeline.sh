#!/usr/bin/env bash
# Full end-to-end pipeline example
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== SCAMGUARD Dataset Pipeline ==="
echo "Working directory: $ROOT"

# 1. Install minimal deps if needed
python3 -m pip install -q -r requirements.txt

# 2. Scrape sample
echo ""
echo ">>> Step 1: Scrape sample URLs"
python3 -m src.pipeline \
  --csv data/input/sample_urls.csv \
  --out-dir data/raw \
  --prefix sample \
  --concurrency 3 \
  --timeout 20

# Find the newest raw file
RAW_JSONL=$(ls -t data/raw/sample_*.jsonl 2>/dev/null | head -1)
if [[ -z "$RAW_JSONL" ]]; then
  echo "No raw output found"
  exit 1
fi
echo "Raw file: $RAW_JSONL"

# 3. Clean
echo ""
echo ">>> Step 2: Clean & deduplicate"
python3 -m src.cleaning "$RAW_JSONL" --out-dir data/cleaned --prefix sample

echo ""
echo "=== Pipeline finished ==="
echo "Raw      → data/raw/"
echo "Cleaned  → data/cleaned/"
echo "Next: manually verify labels → data/verified/"
echo "Then prepare ML-ready split → data/ml_ready/"
