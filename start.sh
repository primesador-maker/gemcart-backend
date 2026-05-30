#!/bin/bash
# Start bot in background
python bot.py &
# Start Flask with Gunicorn
gunicorn app:app --bind 0.0.0.0:$PORT
