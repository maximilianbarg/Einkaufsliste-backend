#!/bin/bash

if [ "$DEBUG" = "1" ]; then
  echo "🔧 Starte im Debug-Modus..."
  exec python3 -m debugpy --listen 0.0.0.0:5678 -m fastapi run app/main.py --port 8000 --no-reload --workers 4
else
  echo "🚀 Starte im Production-Modus..."
  exec fastapi run app/main.py --port 8000 --workers 4
fi