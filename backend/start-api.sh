#!/bin/bash

if [ "$DEBUG" = "true" ]; then
  echo "🔧 Starte im Debug-Modus mit Hot Reload..."
  exec python3 -m debugpy --listen 0.0.0.0:5678 -m fastapi run app/main.py --port 8000 --reload
else
  echo "🚀 Starte im Production-Modus..."
  exec fastapi run app/main.py --port 8000
fi