#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 scripts/prepare_demo.py
exec python3 server.py --db data/demo.db
