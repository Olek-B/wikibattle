"""PythonAnywhere WSGI entry point for WikiBattle.

Copy the contents of this file into your PythonAnywhere WSGI configuration file,
or update the path in PythonAnywhere's web tab to point here.

Before using:
  Set these in the "Environment variables" section of the Web tab:
    GROQ_API_KEY          - Groq API key for AI effect generation
    WIKIBATTLE_CACHE_DB   - Optional: custom path for SQLite cache
                            (default: /tmp/wikibattle_card_cache.db)
"""

import sys
import os

# Auto-detect username from environment, with manual override fallback
USERNAME = os.environ.get('USER', 'YOUR_USERNAME')
PROJECT_DIR = f'/home/{USERNAME}/wikibattle/server'

# Add project directory to Python path
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# Set environment variables in PythonAnywhere Web tab - DO NOT hardcode here
# Required: GROQ_API_KEY
# Optional: WIKIBATTLE_CACHE_DB (for card effect caching with SQLite)

from app import app, start_cleanup_thread

# Start the background cleanup thread for expired games
start_cleanup_thread()

# PythonAnywhere expects a variable called 'application'
application = app
