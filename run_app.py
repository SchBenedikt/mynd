#!/usr/bin/env python
"""
Entry point to run the MYND application.
This script loads and runs the Flask app from the backend.
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

if __name__ == '__main__':
    from backend.core.app import app, start_background_services
    
    # Run the Flask app
    print("\n🚀 MYND AI-Chat-Anwendung wird gestartet...")
    print("📍 Öffne http://localhost:5001 im Browser\n")
    
    # Allow enabling debug mode via MYND_DEBUG env var without the auto-reloader
    debug_mode = os.getenv("MYND_DEBUG", "0").lower() in ("1", "true", "yes")
    print(f"Starting backend (debug={debug_mode}, no auto-reloader)")
    # Disable the auto-reloader to avoid spawning multiple processes during restarts
    start_background_services()
    app.run(host='0.0.0.0', port=5001, debug=debug_mode, use_reloader=False)
